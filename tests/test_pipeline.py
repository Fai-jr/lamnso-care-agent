import json

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app import main as app_main
from backend.app.memory import SessionMemory
from backend.app.nightshift import (LLMResult, NightshiftClient, NightshiftError,
                                    NightshiftUnauthorized, normalise_base_url)
from backend.app.pipeline import handle_message


class FakeLLM:
    def __init__(self, text="I hear you. That sounds hard.", fail=False):
        self.text, self.fail, self.calls = text, fail, 0

    def chat(self, messages, **kw):
        self.calls += 1
        if self.fail:
            raise NightshiftError("down")
        return LLMResult(self.text, "nvidia/nemotron-test", "meterless/auto", 12)

    def health(self):
        return "online"


class FakeTranslator:
    def __init__(self, out="LN:"):
        self.out = out

    def translate(self, t):
        return f"{self.out}{t}" if self.out else ""


def run(msg, llm=None, tr="default", resources=None):
    llm = llm or FakeLLM()
    tr = FakeTranslator() if tr == "default" else tr
    return handle_message(msg, "s1", llm=llm, translator=tr, memory=SessionMemory(),
                          resources=resources or []), llm


# ---------- safety ----------
@pytest.mark.parametrize("text", ["i want to die", "I want to DIE.", "sometimes i feel like giving up on life",
                                  "M yòʼ kpú"])
def test_crisis_never_calls_the_model(text):
    out, llm = run(text)
    assert out["route"] == "crisis" and llm.calls == 0
    assert out["reply_lamnso"] and out["reply_english"] and out["model_used"] is None


@pytest.mark.parametrize("text", ["hello", "the diesel engine is loud", "Wàn kpù fó laʼ, m joó adzə̀m"])
def test_non_crisis_is_not_flagged(text):
    out, _ = run(text)
    assert out["route"] != "crisis"


def test_only_verified_resources_are_shown():
    res = [{"name": "Clinic", "contact": "123", "verified": True}]
    out, _ = run("i want to die", resources=res)
    assert "Clinic: 123" in out["reply_english"]


# ---------- normal flow ----------
def test_agent_route_translates_and_reports_model():
    out, llm = run("I feel very sad today")
    assert out["route"] == "agent" and llm.calls == 1
    assert out["model_used"] == "nvidia/nemotron-test"
    assert out["reply_lamnso"].startswith("LN:") and out["translation_ok"] is True
    assert any("answered by nvidia/nemotron-test" in t for t in out["trace"])


def test_empty_translation_still_returns_english():
    out, _ = run("I feel very sad today", tr=FakeTranslator(out=""))
    assert out["reply_lamnso"] is None and out["translation_ok"] is False and out["reply_english"]


def test_missing_translator_still_returns_english():
    out, _ = run("I feel very sad today", tr=None)
    assert out["reply_lamnso"] is None and out["reply_english"]


def test_nightshift_down_is_graceful():
    out, _ = run("I feel very sad today", llm=FakeLLM(fail=True))
    assert out["route"] == "agent_unavailable" and out["reply_english"]


def test_lamnso_input_is_not_sent_to_the_model():
    out, llm = run("Wìy ó fèn")
    assert out["route"] == "lamnso_input_unsupported" and llm.calls == 0


def test_memory_is_passed_to_the_model_on_second_turn():
    mem, seen = SessionMemory(), []

    class Spy(FakeLLM):
        def chat(self, messages, **kw):
            seen.append(messages)
            return super().chat(messages)

    spy = Spy()
    for m in ("I cannot sleep", "It is worse at night"):
        handle_message(m, "s1", llm=spy, translator=FakeTranslator(), memory=mem, resources=[])
    assert len(seen[1]) == len(seen[0]) + 2  # previous user + assistant turn were included


# ---------- Nightshift client ----------
def test_base_url_is_normalised_without_double_v1():
    for u in ("http://127.0.0.1:8088", "127.0.0.1:8088/v1", "http://127.0.0.1:8088/v1/chat/completions/",
              "http://127.0.0.1:8088/v1/models", "http://127.0.0.1:8088/healthz"):
        assert normalise_base_url(u).endswith(":8088/v1") and "/v1/v1" not in normalise_base_url(u)


def _client(handler):
    return NightshiftClient("http://x:8088", "tok", "meterless/auto", "lamnso-care-agent",
                            transport=httpx.MockTransport(handler), sleep=lambda s: None)


def test_client_sends_auth_headers_and_reads_model():
    seen = {}

    def handler(req):
        seen["h"], seen["url"], seen["body"] = req.headers, str(req.url), json.loads(req.content)
        return httpx.Response(200, json={"model": "nvidia/nemotron-3.5-super", "choices": [
            {"message": {"content": [{"type": "text", "text": "Hello there."}]}}]})

    r = _client(handler).chat([{"role": "user", "content": "hi"}])
    assert r.text == "Hello there." and r.model == "nvidia/nemotron-3.5-super"
    assert seen["url"] == "http://x:8088/v1/chat/completions"
    assert seen["h"]["authorization"] == "Bearer tok" and seen["h"]["meterless-app"] == "lamnso-care-agent"
    assert seen["body"]["stream"] is False


def test_client_unauthorized_and_retry_on_429():
    with pytest.raises(NightshiftUnauthorized):
        _client(lambda req: httpx.Response(401)).chat([{"role": "user", "content": "hi"}])
    calls = {"n": 0}

    def flaky(req):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    assert _client(flaky).chat([{"role": "user", "content": "hi"}]).text == "ok" and calls["n"] == 3


def test_health_states():
    assert _client(lambda r: httpx.Response(200, json={})).health() == "online"
    assert _client(lambda r: httpx.Response(401)).health() == "unauthorized"

    def boom(req):
        raise httpx.ConnectError("no")

    assert _client(boom).health() == "offline"


# ---------- API (sample mode) ----------
def test_api_sample_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("SAMPLE_MODE", "true")
    monkeypatch.setenv("TRACE_LOG_PATH", str(tmp_path / "trace.jsonl"))
    app_main.get_components.cache_clear()
    c = TestClient(app_main.app)
    assert c.get("/health").json()["sample_mode"] is True
    r = c.post("/chat", json={"message": "I feel very sad today", "session_id": "a"}).json()
    assert r["route"] == "agent" and r["model_used"] == "sample-mode" and r["reply_lamnso"].startswith("[sample-lamnso]")
    r2 = c.post("/chat", json={"message": "i want to die", "session_id": "a"}).json()
    assert r2["route"] == "crisis"
    assert c.post("/chat", json={"message": ""}).status_code == 422
    lines = (tmp_path / "trace.jsonl").read_text().splitlines()
    assert len(lines) == 2 and "feel very sad" not in "".join(lines)  # content is not logged by default
    app_main.get_components.cache_clear()


# ---------- config ----------
def test_meterless_env_names_win_over_legacy_names(monkeypatch):
    from backend.app.config import get_settings
    for k in ("METERLESS_BASE_URL", "METERLESS_RUNTIME_TOKEN", "METERLESS_MODEL",
              "NIGHTSHIFT_BASE_URL", "NIGHTSHIFT_TOKEN", "NIGHTSHIFT_MODEL"):
        monkeypatch.delenv(k, raising=False)
    assert get_settings().nightshift_model == "meterless/auto"      # default
    monkeypatch.setenv("NIGHTSHIFT_TOKEN", "old")
    assert get_settings().nightshift_token == "old"                 # legacy name still works
    monkeypatch.setenv("METERLESS_RUNTIME_TOKEN", "new")
    monkeypatch.setenv("METERLESS_BASE_URL", "http://192.168.1.20:8088/v1")
    s = get_settings()
    assert s.nightshift_token == "new" and s.nightshift_base_url == "http://192.168.1.20:8088/v1"
