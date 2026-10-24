"""FastAPI app.   Run from the repo root:   uvicorn backend.app.main:app --reload"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Optional

from typing import Literal

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.app.config import Settings, get_settings
from backend.app.hmem_client import HmemClient, HmemError, user_key
from backend.app.learning import learn_from_turn
from backend.app.memory import SessionMemory
from backend.app.nightshift import NightshiftClient, SampleNightshift
from backend.app.pipeline import handle_message
from backend.app.safety import load_verified_resources
from backend.app.trace import hash_session, write_trace
from translation.translator import LamnsoTranslator, SampleTranslator, TranslatorUnavailable


@dataclass
class Components:
    settings: Settings
    llm: Any
    translator: Any
    translator_error: Optional[str]
    memory: SessionMemory
    resources: list
    hmem: Any = None


@lru_cache(maxsize=1)
def get_components() -> Components:
    s = get_settings()
    translator, terr = None, None
    if s.sample_mode:
        llm, translator = SampleNightshift(), SampleTranslator()
    else:
        llm = NightshiftClient(s.nightshift_base_url, s.nightshift_token, s.nightshift_model,
                               s.app_id, timeout=s.nightshift_timeout,
                               extra_body=s.nightshift_extra_body)
        try:
            translator = LamnsoTranslator(s.weights_path, s.tokenizer_path)
        except TranslatorUnavailable as exc:
            terr = str(exc)  # app still answers in English; /health shows why
    return Components(s, llm, translator, terr, SessionMemory(), load_verified_resources(s.resources_path),
                      HmemClient(s.hmem_url, s.hmem_token))


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(default="default", max_length=100)
    # Long-term memory is OFF unless the person switches it on. user_id is a stable random id kept by the
    # browser; it is hashed before it reaches the memory service.
    remember: bool = False
    user_id: Optional[str] = Field(default=None, max_length=100)


class SentencePair(BaseModel):
    english: str
    lamnso: Optional[str] = None


class MemoryUsed(BaseModel):
    id: str
    content: str
    score: float


class ChatOut(BaseModel):
    reply_lamnso: Optional[str]
    reply_english: Optional[str]
    route: str
    model_used: Optional[str]
    translation_ok: Optional[bool]
    trace: list[str]
    sentences: list[SentencePair] = []
    memories_used: list[MemoryUsed] = []
    memory_enabled: bool = False
    notice: str = "Not a substitute for professional care. In an emergency contact local emergency services."


app = FastAPI(title="Lamnso Care Agent")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://localhost:3001"],
                   allow_methods=["*"], allow_headers=["*"])


def _learn_and_trace(c: "Components", key: str, user_text: str, reply_text: str, session: str) -> None:
    result = learn_from_turn(c.hmem, c.llm, key, user_text, reply_text)
    write_trace(c.settings.log_path, {"event": "learn", "session": hash_session(session), **result})


@app.post("/chat", response_model=ChatOut)
def chat(body: ChatIn, background: BackgroundTasks, c: Components = Depends(get_components)) -> ChatOut:
    key = user_key(body.user_id or body.session_id) if body.remember else None
    out = handle_message(body.message, body.session_id, llm=c.llm, translator=c.translator,
                         memory=c.memory, resources=c.resources, longterm=c.hmem if key else None, user_key=key)
    record = {"session": hash_session(body.session_id), "route": out["route"],
              "model_used": out["model_used"], "latency_ms": out["latency_ms"],
              "translation_ok": out["translation_ok"], "in_chars": len(body.message),
              "memory": bool(key), "memories_used": len(out["memories_used"])}
    if c.settings.log_content:
        record.update(message=body.message, reply_english=out["reply_english"])
    write_trace(c.settings.log_path, record)
    # Learn only from normal replies, never from crisis or unsupported-language messages, and never before replying.
    if key and out["route"] == "agent" and out["reply_english"]:
        background.add_task(_learn_and_trace, c, key, body.message, out["reply_english"], body.session_id)
    fields = {k: out[k] for k in ChatOut.model_fields if k in out}
    return ChatOut(**fields, memory_enabled=bool(key))


class MemoryReq(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)


class FeedbackReq(MemoryReq):
    memory_id: str = Field(pattern=r"^mem-\d+$")
    kind: Literal["helpful", "not_helpful", "wrong"]


def _memory_call(fn):
    try:
        return fn()
    except HmemError as exc:
        raise HTTPException(status_code=503, detail=f"Memory service unavailable: {exc}") from exc


@app.post("/memory/export")
def memory_export(body: MemoryReq, c: Components = Depends(get_components)) -> dict:
    """Everything remembered about this person (their own data, in readable form)."""
    return {"memories": _memory_call(lambda: c.hmem.export(user_key(body.user_id)))}


@app.post("/memory/forget")
def memory_forget(body: MemoryReq, c: Components = Depends(get_components)) -> dict:
    """Erase everything remembered about this person, including the audit-trail copies."""
    return {"erased": _memory_call(lambda: c.hmem.forget(user_key(body.user_id)))}


@app.post("/memory/feedback")
def memory_feedback(body: FeedbackReq, c: Components = Depends(get_components)) -> dict:
    """Mark a remembered note helpful / not helpful / wrong; H-MEM adjusts its confidence by the spec's deltas."""
    return _memory_call(lambda: c.hmem.feedback(user_key(body.user_id), body.memory_id, body.kind))


@app.get("/health")
def health(c: Components = Depends(get_components)) -> dict:
    return {"sample_mode": c.settings.sample_mode, "nightshift": c.llm.health(),
            "translator": getattr(c.translator, "name", None), "translator_error": c.translator_error,
            "verified_crisis_resources": len(c.resources),
            "hmem": c.hmem.health() if c.hmem else "off"}
