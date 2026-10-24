"""The agent pipeline.

  1. Safety net on the raw text (fixed response, no model call)      <- crisis_safety.py, pre-existing
  2. Language gate (the translator is English -> Lamnso only)
  3. Recall short-term memory
  4. Nightshift (Meterless runtime, e.g. NVIDIA Nemotron) writes the reply in English
  5. The project's own transformer translates the reply English -> Lamnso
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Optional, Protocol

from backend.app.hmem_client import HmemError
from backend.app.memory import SessionMemory
from backend.app.nightshift import NightshiftError
from backend.app.safety import crisis_response, is_crisis

# Characters that appear in Lamnso tonal writing and never in plain English (from the original project).
LAMNSO_MARKERS = set("əŋʼèéìíòóùúàáǎě")

SYSTEM_PROMPT = (
    "You are a warm, supportive listener for people who may be feeling stressed, sad or anxious. "
    "You are not a therapist or doctor: do not diagnose, do not give medical or medication advice. "
    "Reply in 2 or 3 very short, simple sentences (under 9 words each) using plain everyday words. Do not use contractions (write \"I am\", never \"I'm\") and avoid idioms such as \"tough day\", because your reply will be "
    "machine-translated into Lamnso. Avoid idioms, metaphors and lists. Ask at most one gentle question. "
    "If the person talks about harming themselves or someone else, say you are concerned and encourage "
    "them to contact someone they trust or their local emergency services."
)

MEMORY_INTRO = (
    "What you remember from earlier conversations with this person. Use it only if it is relevant right now, "
    "gently and in your own words. Never quote it, never say you have a memory system:\n"
)

SIMPLIFY_PROMPT = (
    "Please say that again in 2 very short, plain sentences of 8 words or fewer each. "
    "No contractions, no idioms, no questions."
)

UNSUPPORTED_LAMNSO_MSG = (
    "For now I can read English only. Please write your message in English, or ask someone you trust "
    "to help you write it."
)
LLM_DOWN_MSG = "I am having trouble connecting right now. Please try again in a moment."


class Translator(Protocol):
    def translate(self, english_text: str) -> str: ...


def split_sentences(text: str) -> list[str]:
    """The translation model was trained on short sentences, so it is given one sentence at a time."""
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]


def _tokens(text: str) -> list[str]:
    toks = (t.strip(".,;:?!\"'") for t in text.lower().split())
    return [t for t in toks if t]


def looks_degenerate(text: str) -> bool:
    """Catches the looping output a greedy decoder produces on inputs it handles badly:
    many words with few distinct ones, or the same three-word run three or more times."""
    toks = _tokens(text)
    if len(toks) >= 8 and len(set(toks)) / len(toks) < 0.5:
        return True
    trigrams = Counter(zip(toks, toks[1:], toks[2:]))
    return bool(trigrams) and max(trigrams.values()) >= 3


def _translate(translator: Optional[Translator], english: str):
    """-> (pairs, lamnso_or_None, trace). pairs = [(english_sentence, lamnso_sentence_or_None)].
    All-or-nothing for the joined Lamnso reply: if any sentence comes back empty, failed or repetitive, no
    joined Lamnso is returned (the pairs and the English reply still are). Better no translation than a
    wrong one in a mental-health setting."""
    sentences = split_sentences(english)
    if translator is None:
        return [(x, None) for x in sentences], None, "translate:unavailable"
    if not sentences:
        return [], None, "translate:nothing_to_translate"
    pairs: list[tuple[str, Optional[str]]] = []
    for sentence in sentences:
        try:
            piece = (translator.translate(sentence) or "").strip()
        except Exception:
            piece = ""
        pairs.append((sentence, piece if piece and not looks_degenerate(piece) else None))
    good = [lam for _, lam in pairs if lam]
    if len(good) != len(pairs):
        return pairs, None, f"translate:withheld ({len(good)}/{len(pairs)} sentences usable)"
    return pairs, " ".join(good), f"translate:ok ({len(good)}/{len(pairs)} sentences)"


def translate_reply(translator: Optional[Translator], english: str) -> tuple[Optional[str], str]:
    _, lamnso, trace = _translate(translator, english)
    return lamnso, trace


def looks_like_lamnso(text: str) -> bool:
    return any(c in LAMNSO_MARKERS for c in text.lower())


def handle_message(message: str, session_id: str, *, llm: Any, translator: Translator | None,
                   memory: SessionMemory, resources: list[dict], longterm: Any = None,
                   user_key: str | None = None) -> dict:
    """Returns a dict with reply_lamnso, reply_english, route, model_used, translation_ok, trace."""
    message = message.strip()
    base: dict = {"reply_lamnso": None, "reply_english": None, "route": "", "model_used": None,
                  "translation_ok": None, "latency_ms": 0, "trace": [], "sentences": [], "memories_used": []}

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
    notes = []
    if longterm is not None and user_key:  # long-term memory is opt-in: the caller passes a key only if switched on
        try:
            notes = longterm.recall(user_key, message)
            base["trace"].append(f"hmem:recalled {len(notes)} note(s)" if notes else "hmem:no_relevant_notes")
        except HmemError:
            base["trace"].append("hmem:unavailable")
    base["memories_used"] = [{"id": n.id, "content": n.content, "score": n.score} for n in notes]
    system = [{"role": "system", "content": SYSTEM_PROMPT}]
    if notes:
        system.append({"role": "system", "content": MEMORY_INTRO + "\n".join(f"- {n.content}" for n in notes)})
    messages = system + memory.recall(session_id) + [{"role": "user", "content": message}]
    try:
        result = llm.chat(messages)
    except NightshiftError as exc:
        base.update(reply_english=LLM_DOWN_MSG, route="agent_unavailable")
        base["trace"].append(f"nightshift:error:{exc.__class__.__name__}")
        return base
    english = result.text
    base.update(model_used=result.model, latency_ms=result.latency_ms)
    base["trace"].append(f"nightshift:{result.requested_model} -> answered by {result.model}")

    # 5. Translate the reply into Lamnso, one sentence at a time.
    pairs, lamnso, translate_trace = _translate(translator, english)
    base["trace"].append(translate_trace)

    # 5b. If the translator could not cope, ask the model once for a simpler reply and try again.
    if lamnso is None and translator is not None and pairs:
        try:
            retry = llm.chat(messages + [{"role": "assistant", "content": english},
                                         {"role": "user", "content": SIMPLIFY_PROMPT}])
        except NightshiftError:
            retry = None
        if retry is not None:
            r_pairs, r_lamnso, r_trace = _translate(translator, retry.text)
            base["trace"].append(f"retry:simplified -> {r_trace}")
            if r_lamnso is not None:  # keep the simpler reply only if it actually translated
                english, pairs, lamnso = retry.text, r_pairs, r_lamnso
                base["model_used"] = retry.model

    base.update(reply_english=english, reply_lamnso=lamnso, route="agent", translation_ok=lamnso is not None,
                sentences=[{"english": e, "lamnso": l} for e, l in pairs])

    memory.remember(session_id, message, english)
    return base
