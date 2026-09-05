"""`render(prompt_name, **vars)` — loads `prompts/<name>.md`, substitutes `{{var}}`
placeholders. See ADK_AGENTS.md §6's prompt-file checklist.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


@cache
def _template(prompt_name: str) -> str:
    return (_PROMPTS_DIR / f"{prompt_name}.md").read_text()


def render(prompt_name: str, **variables: object) -> str:
    text = _template(prompt_name)
    for key, value in variables.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text
