"""Thin optional wrapper around Gemini. Everything works without it.

If `langchain-google-genai` is installed, the model is called through a LangChain chat model
(ChatGoogleGenerativeAI). Otherwise the plain `google-genai` SDK is used. Both need GEMINI_API_KEY.
"""
import json
import os
import re


def model_name(cfg):
    return os.environ.get("CHAOSAI_MODEL", cfg["llm"]["model"])


def backend():
    """Which client library is installed: "langchain", "google-genai" or None."""
    forced = os.environ.get("CHAOSAI_LLM_BACKEND")      # set to "google-genai" to skip LangChain
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
    if not cfg["llm"]["enabled"] or not os.environ.get("GEMINI_API_KEY"):
        return False
    return backend() is not None


def _parse(text):
    if not text or not text.strip():
        raise ValueError("Gemini returned an empty response.")
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return json.loads(text)


def _ask_langchain(cfg, system, payload, max_tokens):
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_google_genai import ChatGoogleGenerativeAI

    chat = ChatGoogleGenerativeAI(
        model=model_name(cfg),
        api_key=os.environ["GEMINI_API_KEY"],
        max_output_tokens=max_tokens,
        response_mime_type="application/json",
        temperature=0.2,
        max_retries=2,
    )
    message = chat.invoke([SystemMessage(content=system), HumanMessage(content=json.dumps(payload))])
    content = message.content
    if isinstance(content, list):           # newer versions return a list of content parts
        content = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return _parse(content)


def _ask_google_genai(cfg, system, payload, max_tokens):
    from google import genai

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model=model_name(cfg),
        contents=json.dumps(payload),
        config=genai.types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
        ),
    )
    return _parse(response.text)


def ask_json(cfg, system, payload, max_tokens=1500):
    """Send one system prompt and a JSON payload to Gemini and return the parsed JSON answer."""
    if backend() == "langchain":
        return _ask_langchain(cfg, system, payload, max_tokens)
    return _ask_google_genai(cfg, system, payload, max_tokens)