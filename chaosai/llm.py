"""Thin optional wrapper around the Gemini API. Everything works without it."""
import json
import os


def model_name(cfg):
    return os.environ.get("CHAOSAI_MODEL", cfg["llm"]["model"])


def available(cfg):
    if not cfg["llm"]["enabled"] or not os.environ.get("GEMINI_API_KEY"):
        return False
    try:
        from google import genai  # noqa: F401
        return True
    except ImportError:
        return False


def ask_json(cfg, system, payload, max_tokens=1500):
    from google import genai

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    model = model_name(cfg)
    response = client.models.generate_content(
        model=model,
        contents=json.dumps(payload),
        config=genai.types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
        ),
    )
    if not response.text:
        raise ValueError("Gemini returned an empty response.")
    return json.loads(response.text)
