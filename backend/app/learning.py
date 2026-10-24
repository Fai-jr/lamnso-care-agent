"""Turn a finished conversation turn into at most two short, non-identifying memory notes.

Runs only when the person has switched memory on, only after a normal ('agent') reply, never for crisis
messages, and in the background so it never delays the reply. The model that writes the notes is the same
Nightshift/Meterless provider as everything else; the memory service then applies its own privacy checks.
"""
from __future__ import annotations

import json
import re
from typing import Any

from backend.app.hmem_client import HmemClient, HmemError, HmemPolicyError
from backend.app.nightshift import NightshiftError

EXTRACT_PROMPT = (
    "You write memory notes for a supportive-listener app. From the exchange below, output a JSON array of at "
    "most 2 short notes (8 to 120 characters each) about what the person is struggling with or what helps them. "
    "Rules: record only what THE PERSON said about themselves (their feelings, situation, or what helps them), "
    "never advice or general statements the listener made; write in the third person; paraphrase, never copy their "
    "words; no names, places, dates, numbers, contact details or anything that could identify them; no diagnoses; "
    "no instructions. If nothing is worth remembering, or the exchange is about harming themselves or others, "
    "output []. Output only the JSON array."
)

MIN_CHARS, MAX_CHARS, MAX_NOTES = 8, 200, 2


def parse_notes(text: str) -> list[str]:
    """Tolerant parser: strips markdown fences and surrounding chatter, keeps valid short strings only."""
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        items = json.loads(text[start:end + 1])
    except ValueError:
        return []
    notes: list[str] = []
    for item in items if isinstance(items, list) else []:
        if isinstance(item, str):
            note = re.sub(r"\s+", " ", item).strip()
            if MIN_CHARS <= len(note) <= MAX_CHARS and note not in notes:
                notes.append(note)
    return notes[:MAX_NOTES]


def extract_notes(llm: Any, user_text: str, reply_text: str) -> list[str]:
    messages = [
        {"role": "system", "content": EXTRACT_PROMPT},
        {"role": "user", "content": f"Person: {user_text}\nListener: {reply_text}"},
    ]
    try:
        return parse_notes(llm.chat(messages, max_tokens=200, temperature=0.2).text)
    except NightshiftError:
        return []


def learn_from_turn(hmem: HmemClient, llm: Any, key: str, user_text: str, reply_text: str) -> dict:
    """Never raises. Returns counts so the caller can trace them (never the note text)."""
    stored = skipped = 0
    for note in extract_notes(llm, user_text, reply_text):
        try:
            hmem.remember(key, note)
            stored += 1
        except HmemPolicyError:
            skipped += 1   # the memory service refused it (e.g. looked like a personal identifier)
        except HmemError:
            return {"stored": stored, "skipped": skipped, "service": "unavailable"}
    return {"stored": stored, "skipped": skipped, "service": "online"}
