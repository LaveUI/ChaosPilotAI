"""Thin optional wrapper around the Anthropic API. Everything works without it."""
import json
import os
import re


def available(cfg):
    if not cfg["llm"]["enabled"] or not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def ask_json(cfg, system, payload, max_tokens=1500):
    import anthropic
    client = anthropic.Anthropic()
    model = os.environ.get("CHAOSAI_MODEL", cfg["llm"]["model"])
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": json.dumps(payload)}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    return json.loads(text)
