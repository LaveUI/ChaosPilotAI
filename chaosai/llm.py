"""Structured JSON clients for Gemini and local Ollama models."""
from datetime import datetime, timezone
import email.utils
import json
import os
import random
import re
import time
import urllib.error
import urllib.request


MAX_ATTEMPTS = 3
MAX_RETRY_DELAY_S = 8.0
BASE_RETRY_DELAY_S = 0.5

_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}

OBSERVER_SCHEMA = {
    "type": "object",
    "properties": {
        "healthy": {"type": "boolean"},
        "summary": {"type": "string"},
        "concerns": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["healthy", "summary", "concerns"],
}
PLANNER_SCHEMA = {
    "type": "object",
    "properties": {
        "experiments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "service": {"type": "string"},
                    "action": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["service", "action", "rationale"],
            },
        },
    },
    "required": ["experiments"],
}
INJECTOR_SCHEMA = {
    "type": "object",
    "properties": {
        "inject": {"type": "boolean"},
        "duration_s": {"type": "integer"},
        "reason": {"type": "string"},
    },
    "required": ["inject", "duration_s", "reason"],
}
ROLLBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "rollback": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["rollback", "reason"],
}
ANALYST_SCHEMA = {
    "type": "object",
    "properties": {
        "diagnosis": {"type": "string"},
        "severity": {"type": "string", "enum": ["critical", "high", "medium", "low", "none"]},
        "root_cause_hypotheses": {"type": "array", "items": {"type": "string"}},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "fixes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"title": {"type": "string"}, "detail": {"type": "string"}},
                "required": ["title", "detail"],
            },
        },
    },
    "required": ["diagnosis", "severity", "fixes"],
}
REPORTER_SCHEMA = {
    "type": "object",
    "properties": {
        "overall": {"type": "string"},
        "ranked_weaknesses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "service": {"type": "string"},
                    "action": {"type": "string"},
                    "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                    "why": {"type": "string"},
                },
                "required": ["service", "action", "severity", "why"],
            },
        },
        "score_explanation": {"type": "string"},
    },
    "required": ["overall", "ranked_weaknesses", "score_explanation"],
}
SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"],
}


def with_provider(cfg, provider):
    configured = dict(cfg)
    configured["llm"] = {**cfg["llm"], "provider": provider}
    return configured


def provider_name(cfg):
    return "Ollama" if cfg.get("llm", {}).get("provider") == "ollama" else "Gemini"


def model_name(cfg):
    if cfg.get("llm", {}).get("provider") == "ollama":
        return cfg["local_agent"]["model"]
    return os.environ.get("CHAOSAI_MODEL", cfg["llm"]["model"])


def backend(cfg=None):
    """Which client library is installed: "langchain", "google-genai" or None."""
    if cfg and cfg.get("llm", {}).get("provider") == "ollama":
        return "ollama"
    forced = os.environ.get("CHAOSAI_LLM_BACKEND")
    if forced != "google-genai":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: F401
            return "langchain"
        except ImportError:
            pass
    try:
        from google import genai  # noqa: F401
        return "google-genai"
    except ImportError:
        return None


def available(cfg):
    if not cfg["llm"]["enabled"]:
        return False
    if cfg.get("llm", {}).get("provider") == "ollama":
        return True
    return bool(os.environ.get("GEMINI_API_KEY")) and backend(cfg) is not None


def _parse(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("The model returned an empty response.")
    content = text.strip()
    fenced = re.fullmatch(r"```\s*(?:json\s*)?(.*?)\s*```", content, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        content = fenced.group(1).strip()
    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError("Model JSON response must be an object.")
    return value


def _ask_langchain(cfg, system, payload, max_tokens, schema):
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_google_genai import ChatGoogleGenerativeAI

    chat = ChatGoogleGenerativeAI(
        model=model_name(cfg),
        api_key=os.environ["GEMINI_API_KEY"],
        max_tokens=max_tokens,
        response_mime_type="application/json",
        response_schema=schema,
        temperature=0.2,
        retries=0,
    )
    message = chat.invoke([SystemMessage(content=system), HumanMessage(content=json.dumps(payload))])
    content = message.content
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return _parse(content)


def _ask_google_genai(cfg, system, payload, max_tokens, schema):
    from google import genai

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model=model_name(cfg),
        contents=json.dumps(payload),
        config=genai.types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )
    return _parse(response.text)


def _ask_ollama(cfg, system, payload, max_tokens, schema):
    from .local_agent import _endpoint

    settings = cfg["local_agent"]
    request_payload = {
        "model": settings["model"],
        "stream": False,
        "format": schema or "json",
        "keep_alive": settings["keep_alive"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload)},
        ],
        "options": {
            "temperature": 0.2,
            "num_ctx": settings["num_ctx"],
            "num_predict": max_tokens,
        },
    }
    request = urllib.request.Request(
        _endpoint(settings["ollama_url"]),
        data=json.dumps(request_payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings["ollama_timeout_s"]) as response:
            body = json.loads(response.read().decode())
        if not isinstance(body, dict):
            raise RuntimeError("Ollama returned an invalid response.")
        if body.get("error"):
            raise RuntimeError(f"Ollama request failed: {str(body['error'])[:500]}")
        content = body.get("message", {}).get("content")
        if not isinstance(content, str):
            raise RuntimeError("Ollama response is missing message content.")
        try:
            return _parse(content)
        except (TypeError, ValueError) as exc:
            reason = body.get("done_reason", "unknown")
            raise RuntimeError(f"Ollama returned invalid JSON (finish reason: {reason}).") from exc
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise RuntimeError(f"Ollama HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Cannot reach local Ollama: {exc.reason}. Start Ollama and pull {settings['model']}."
        ) from exc
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Ollama returned a malformed response.") from exc


def _status_code(exc):
    candidates = [exc, getattr(exc, "response", None)]
    for candidate in candidates:
        if candidate is None:
            continue
        for name in ("status_code", "status", "code"):
            value = getattr(candidate, name, None)
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
            if value in _RETRYABLE_STATUSES:
                return value
    match = re.search(r"\b(429|500|502|503|504)\b", str(exc))
    return int(match.group(1)) if match else None


def is_transient_error(exc):
    """Return whether an exception represents a retryable Gemini service response."""
    return _status_code(exc) in _RETRYABLE_STATUSES


def _retry_after(exc):
    candidates = [exc, getattr(exc, "response", None)]
    for candidate in candidates:
        if candidate is None:
            continue
        value = getattr(candidate, "retry_after", None)
        if value is not None:
            try:
                return max(0.0, float(value))
            except (TypeError, ValueError):
                pass
        headers = getattr(candidate, "headers", None)
        if headers:
            value = headers.get("Retry-After") or headers.get("retry-after")
            if value:
                try:
                    return max(0.0, float(value))
                except (TypeError, ValueError):
                    try:
                        retry_at = email.utils.parsedate_to_datetime(value)
                        if retry_at.tzinfo is None:
                            retry_at = retry_at.replace(tzinfo=timezone.utc)
                        return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
                    except (TypeError, ValueError, OverflowError):
                        pass

    text = str(exc)
    match = re.search(r"""retryDelay['"]?\s*[:=]\s*['"]?(\d+(?:\.\d+)?)s""", text)
    if match:
        return float(match.group(1))
    match = re.search(r"retry in\s+(?:(\d+)h)?(?:(\d+)m)?(\d+(?:\.\d+)?)s", text, re.IGNORECASE)
    if match:
        hours, minutes, seconds = (float(value or 0) for value in match.groups())
        return hours * 3600 + minutes * 60 + seconds
    return None


def _request_delay(exc, retry_number):
    retry_after = _retry_after(exc)
    if retry_after is not None:
        if retry_after > MAX_RETRY_DELAY_S:
            return None
        return retry_after
    exponential = BASE_RETRY_DELAY_S * (2 ** (retry_number - 1))
    return min(MAX_RETRY_DELAY_S, exponential + random.uniform(0, exponential * 0.25))


def ask_json(cfg, system, payload, max_tokens=1500, schema=None, metadata=None):
    """Call the selected model with JSON schema output.

    If Retry-After exceeds the bounded retry window, the call fails immediately rather than
    retrying before the server says it is safe or sleeping for an unbounded time.
    """
    details = metadata if metadata is not None else {}
    details.update({
        "provider": provider_name(cfg),
        "model": model_name(cfg),
        "requested": True,
        "succeeded": False,
        "fallback": False,
        "retry_count": 0,
    })
    started = time.monotonic()
    selected_backend = backend(cfg)
    details["backend"] = selected_backend
    try:
        if selected_backend is None:
            raise RuntimeError("Gemini client is unavailable; install google-genai or langchain-google-genai.")
        request_schema = schema or {"type": "object"}
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                if selected_backend == "langchain":
                    result = _ask_langchain(cfg, system, payload, max_tokens, request_schema)
                elif selected_backend == "ollama":
                    result = _ask_ollama(cfg, system, payload, max_tokens, request_schema)
                else:
                    result = _ask_google_genai(cfg, system, payload, max_tokens, request_schema)
                details["succeeded"] = True
                details["attempts"] = attempt
                return result
            except Exception as exc:
                details["error"] = f"{exc.__class__.__name__}: {exc}"
                if not is_transient_error(exc) or attempt == MAX_ATTEMPTS:
                    details["attempts"] = attempt
                    raise
                delay = _request_delay(exc, attempt)
                if delay is None:
                    details["attempts"] = attempt
                    details["retry_after_too_long"] = _retry_after(exc)
                    raise
                details["retry_count"] = attempt
                time.sleep(delay)
    finally:
        details["duration_s"] = round(time.monotonic() - started, 3)
