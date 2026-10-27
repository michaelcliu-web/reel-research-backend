import json
import os
import re

import anthropic

client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

FAST_MODEL = "claude-haiku-4-5-20251001"
SMART_MODEL = "claude-opus-5-5"


async def stream_text(prompt, model, max_tokens):
    """Yield the model's response text as it streams in."""
    async with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def complete(prompt, model, max_tokens):
    """Return the model's full response text."""
    return "".join([text async for text in stream_text(prompt, model, max_tokens)])


def extract_json_array(text):
    """Parse the first [...] span in the text, or return [] if there is none."""
    m = re.search(r'\[.*\]', text, re.DOTALL)
    return json.loads(m.group()) if m else []


async def ask_json_array(prompt):
    """Ask the fast model for a JSON array; any failure yields []."""
    try:
        return extract_json_array(await complete(prompt, FAST_MODEL, 1024))
    except Exception:
        return []


def strip_code_fences(text):
    """Remove a leading ```lang line and trailing ``` from model-generated code."""
    text = text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    text = text.strip()
    if text.endswith("```"):
        text = "\n".join(text.split("\n")[:-1]).strip()
    return text
