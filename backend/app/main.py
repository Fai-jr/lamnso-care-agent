"""FastAPI app.   Run from the repo root:   uvicorn backend.app.main:app --reload"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Optional

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.app.config import Settings, get_settings
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


@lru_cache(maxsize=1)
def get_components() -> Components:
    s = get_settings()
    translator, terr = None, None
    if s.sample_mode:
        llm, translator = SampleNightshift(), SampleTranslator()
    else:
        llm = NightshiftClient(s.nightshift_base_url, s.nightshift_token, s.nightshift_model,
                               s.app_id, timeout=s.nightshift_timeout)
        try:
            translator = LamnsoTranslator(s.weights_path, s.tokenizer_path)
        except TranslatorUnavailable as exc:
            terr = str(exc)  # app still answers in English; /health shows why
    return Components(s, llm, translator, terr, SessionMemory(), load_verified_resources(s.resources_path))


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(default="default", max_length=100)


class ChatOut(BaseModel):
    reply_lamnso: Optional[str]
    reply_english: Optional[str]
    route: str
    model_used: Optional[str]
    translation_ok: Optional[bool]
    trace: list[str]
    notice: str = "Not a substitute for professional care. In an emergency contact local emergency services."


app = FastAPI(title="Lamnso Care Agent")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"],
                   allow_methods=["*"], allow_headers=["*"])


@app.post("/chat", response_model=ChatOut)
def chat(body: ChatIn, c: Components = Depends(get_components)) -> ChatOut:
    out = handle_message(body.message, body.session_id, llm=c.llm, translator=c.translator,
                         memory=c.memory, resources=c.resources)
    record = {"session": hash_session(body.session_id), "route": out["route"],
              "model_used": out["model_used"], "latency_ms": out["latency_ms"],
              "translation_ok": out["translation_ok"], "in_chars": len(body.message)}
    if c.settings.log_content:
        record.update(message=body.message, reply_english=out["reply_english"])
    write_trace(c.settings.log_path, record)
    return ChatOut(**{k: out[k] for k in ChatOut.model_fields if k in out})


@app.get("/health")
def health(c: Components = Depends(get_components)) -> dict:
    return {"sample_mode": c.settings.sample_mode, "nightshift": c.llm.health(),
            "translator": getattr(c.translator, "name", None), "translator_error": c.translator_error,
            "verified_crisis_resources": len(c.resources)}
