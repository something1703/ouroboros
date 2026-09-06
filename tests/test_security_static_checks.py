"""PHASE_09.md §9.3 static security checks: no secret value ever reaches a log call,
and every untrusted-text path actually calls Model Armor's `screen()`. Both are
grep-style checks over real source files, not unit tests of behavior -- exactly the
two checks PHASE_09.md's own text asks for ("log scrubber test", "grep test that
screen() is called in ingest, search, extract, task-output paths").
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_SOURCE_DIRS = ("packages", "services", "agents")


def _python_files() -> list[Path]:
    files = []
    for d in _SOURCE_DIRS:
        files.extend((_ROOT / d).rglob("*.py"))
    return [f for f in files if "__pycache__" not in f.parts]


# A log call whose arguments directly embed a live secret/credential value. Matches
# `log.<level>(..., get_secret(...)...)` and a raw `Authorization`/`authorization`
# dict-style header value passed straight through — deliberately narrow (grep-style,
# not a full parser) so it flags real risky patterns without false-positiving on
# every log call that happens to mention the word "secret" or "token" in a message
# string (e.g. `log.error("secret_access_failed", secret_name=name)` — the *name*,
# not the value, is fine and expected; packages/common/secrets.py does exactly this).
_RISKY_LOG_PATTERNS = [
    re.compile(r"log\.\w+\([^)]*get_secret\("),
    re.compile(r"log\.\w+\([^)]*\bheaders\[.{0,20}[Aa]uthorization"),
    re.compile(r"log\.\w+\([^)]*\btoken=(?!None)[a-zA-Z_]"),
]


def test_no_log_call_embeds_a_raw_secret_value() -> None:
    offenders: list[str] = []
    for path in _python_files():
        text = path.read_text()
        for pattern in _RISKY_LOG_PATTERNS:
            for match in pattern.finditer(text):
                line_no = text.count("\n", 0, match.start()) + 1
                offenders.append(f"{path.relative_to(_ROOT)}:{line_no}: {match.group(0)!r}")
    assert not offenders, "log call(s) appear to embed a raw secret value:\n" + "\n".join(offenders)


# One `screen(...)` call site expected per untrusted-text path (PHASE_09.md §9.3's own
# four named paths). Each is a real, specific file (not a directory scan) so this
# fails loudly and specifically if a path's screening call is ever removed or moved
# without a replacement landing somewhere else.
_EXPECTED_SCREEN_CALL_SITES = {
    "ingest": "services/ingest/main.py",
    "search (web excerpts)": "packages/parallel_client/search.py",
    "extract": "packages/parallel_client/extract.py",
    "task_output (evidence)": "agents/ouroboros/tools/evidence.py",
}


def test_model_armor_screen_is_called_on_every_untrusted_text_path() -> None:
    missing = []
    for label, rel_path in _EXPECTED_SCREEN_CALL_SITES.items():
        path = _ROOT / rel_path
        if not path.exists() or "screen(" not in path.read_text():
            missing.append(f"{label} ({rel_path})")
    assert not missing, f"Model Armor screen() call missing for: {', '.join(missing)}"
