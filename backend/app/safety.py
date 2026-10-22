"""Crisis handling. Runs BEFORE any model call, translation or memory lookup.

Detection reuses the project's pre-existing keyword net (translation/crisis_safety.py, unchanged).
The response is fixed, pre-written text, never model output, and it needs no network.
"""
from __future__ import annotations

import json
from pathlib import Path

from translation.crisis_safety import check_crisis_keywords

# Lamnso text carried over from the original project's crisis_responder.py fallback message.
# TODO(fluent speaker): confirm this wording before any real-world use.
CRISIS_LAMNSO = (
    "M yù tóŋ yémé e mò. Éè Nyùy Tàr, ku wìy. Nyùy wom, ku lùŋèr mo. "
    "M dzə̀ fèn fo à lán feyì."
)

CRISIS_ENGLISH = (
    "I am really sorry you are going through this. You matter, and you do not have to face it alone. "
    "Please reach out to someone you trust right now. If you are in immediate danger, contact your "
    "local emergency services."
)


def is_crisis(text: str) -> bool:
    return check_crisis_keywords(text)


def load_verified_resources(path: Path) -> list[dict]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [r for r in data.get("resources", []) if r.get("verified") and r.get("contact")]


def crisis_response(resources: list[dict]) -> dict:
    english = CRISIS_ENGLISH
    if resources:
        english += " " + " ".join(f"{r['name']}: {r['contact']}." for r in resources)
    return {"reply_english": english, "reply_lamnso": CRISIS_LAMNSO}
