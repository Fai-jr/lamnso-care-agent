"""The agent pipeline.

  1. Safety net on the raw text (fixed response, no model call)      <- crisis_safety.py, pre-existing
  2. Language gate (the translator is English -> Lamnso only)
  3. Recall short-term memory
  4. Nightshift (Meterless runtime, e.g. NVIDIA Nemotron) writes the reply in English
  5. The project's own transformer translates the reply English -> Lamnso
"""
from __future__ import annotations

from typing import Any, Protocol

from backend.app.memory import SessionMemory
from backend.app.nightshift import NightshiftError
from backend.app.safety import crisis_response, is_crisis

# Characters that appear in Lamnso tonal writing and never in plain English (from the original project).
LAMNSO_MARKERS = set("əŋʼèéìíòóùúàáǎě")

SYSTEM_PROMPT = (
    "You are a warm, supportive listener for people who may be feeling stressed, sad or anxious. "
    "You are not a therapist or doctor: do not diagnose, do not give medical or medication advice. "
    "Reply in 2 or 3 short, simple sentences using plain everyday words, because your reply will be "
    "machine-translated into Lamnso. Avoid idioms, metaphors and lists. Ask at most one gentle question. "
    "If the person talks about harming themselves or someone else, say you are concerned and encourage "
    "them to contact someone they trust or their local emergency services."
)

UNSUPPORTED_LAMNSO_MSG = (
    "For now I can read English only. Please write your message in English, or ask someone you trust "
    "to help you write it."
)
LLM_DOWN_MSG = "I am having trouble connecting right now. Please try again in a moment."


class Translator(Protocol):
    def translate(self, english_text: str) -> str: ...


def looks_like_lamnso(text: str) -> bool:
    return any(c in LAMNSO_MARKERS for c in text.lower())


def handle_message(message: str, session_id: str, *, llm: Any, translator: Translator | None,
                   memory: SessionMemory, resources: list[dict]) -> dict:
    """Returns a dict with reply_lamnso, reply_english, route, model_used, translation_ok, trace."""
    message = message.strip()
    base: dict = {"reply_lamnso": None, "reply_english": None, "route": "", "model_used": None,
                  "translation_ok": None, "latency_ms": 0, "trace": []}

    # 1. Safety first. No model, no translation, no network.
    if is_crisis(message):
        base.update(crisis_response(resources))
        base.update(route="crisis", translation_ok=True)
        base["trace"] = ["safety:crisis_keywords -> fixed response (no model called)"]
        return base

    # 2. Language gate.
    if looks_like_lamnso(message):
        base.update(reply_english=UNSUPPORTED_LAMNSO_MSG, route="lamnso_input_unsupported")
        base["trace"] = ["safety:no_crisis", "language:lamnso_input -> English-only for now"]
        return base

    # 3-4. Memory + Nightshift.
    base["trace"].append("safety:no_crisis")
    messages = ([{"role": "system", "content": SYSTEM_PROMPT}] + memory.recall(session_id)
                + [{"role": "user", "content": message}])
    try:
        result = llm.chat(messages)
    except NightshiftError as exc:
        base.update(reply_english=LLM_DOWN_MSG, route="agent_unavailable")
        base["trace"].append(f"nightshift:error:{exc.__class__.__name__}")
        return base
    english = result.text
    base.update(model_used=result.model, latency_ms=result.latency_ms)
    base["trace"].append(f"nightshift:{result.requested_model} -> answered by {result.model}")

    # 5. Translate the reply into Lamnso.
    lamnso = ""
    if translator is not None:
        try:
            lamnso = (translator.translate(english) or "").strip()
        except Exception as exc:  # a translator failure must never hide a good reply
            base["trace"].append(f"translate:error:{exc.__class__.__name__}")
    ok = bool(lamnso)
    base["trace"].append(f"translate:{'ok' if ok else 'empty_or_unavailable'}")
    base.update(reply_english=english, reply_lamnso=lamnso or None, route="agent", translation_ok=ok)

    memory.remember(session_id, message, english)
    return base
