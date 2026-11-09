import json
import re

from shotwise.providers.base import ProviderError


def parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):                                 # tolerate fenced output from chat-style models
        text = re.sub(r"^```[a-zA-Z]*\n|\n```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ProviderError("invalid_output", f"model returned invalid JSON: {e}")
