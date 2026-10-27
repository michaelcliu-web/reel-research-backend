import json
import re


def split_summary(text):
    """Split the summary model's output into (summary, narration_script)."""
    if "NARRATION:" in text:
        parts = text.split("NARRATION:")
        return parts[0].replace("SUMMARY:", "").strip(), parts[1].strip()
    return text, text


def _sanitize_json_strings(text):
    """Escape literal newlines/tabs inside JSON string values."""
    result = []
    in_string = False
    escape_next = False
    for ch in text:
        if escape_next:
            result.append(ch)
            escape_next = False
        elif ch == '\\' and in_string:
            result.append(ch)
            escape_next = True
        elif ch == '"':
            in_string = not in_string
            result.append(ch)
        elif in_string and ch == '\n':
            result.append('\\n')
        elif in_string and ch == '\t':
            result.append('\\t')
        elif in_string and ch == '\r':
            pass
        else:
            result.append(ch)
    return ''.join(result)


def parse_storyboard(text):
    """Extract and parse JSON array from LLM output, with sanitization fallback."""
    if not text.strip():
        return None
    json_match = re.search(r'\[.*\]', text, re.DOTALL)
    raw = json_match.group() if json_match else text
    raw = raw.replace('“', '"').replace('”', '"')
    raw = raw.replace('‘', "'").replace('’', "'")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(_sanitize_json_strings(raw))
