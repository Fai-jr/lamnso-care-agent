import pytest
from fastapi.testclient import TestClient

from backend.app import main as app_main
from backend.app.config import get_settings
from backend.app.hmem_client import HmemError, HmemPolicyError, Note, user_key
from backend.app.learning import EXTRACT_PROMPT, learn_from_turn, parse_notes
from backend.app.memory import SessionMemory
from backend.app.nightshift import LLMResult, NightshiftError
from backend.app.pipeline import MEMORY_INTRO, handle_message


class FakeHmem:
    """In-memory stand-in for the H-MEM service with the same client interface."""

    def __init__(self, down=False):
        self.notes: dict[str, list[tuple[str, str]]] = {}
        self.down, self.recall_calls, self._n = down, 0, 0

    def _check(self):
        if self.down:
            raise HmemError("down")

    def health(self):
        return "offline" if self.down else "online"

    def recall(self, key, query, top_n=None):
        self._check()
        self.recall_calls += 1
        words = set(query.lower().split())
        return [Note(i, c, 0.5) for i, c in self.notes.get(key, []) if words & set(c.lower().split())]

    def remember(self, key, content, source="care-agent:session-note"):
        self._check()
        if "@" in content:
            raise HmemPolicyError("pii_suspected")
        self._n += 1
        self.notes.setdefault(key, []).append((f"mem-{self._n}", content))
        return {"id": f"mem-{self._n}", "deduped": False}

    def feedback(self, key, memory_id, kind):
        self._check()
        return {"id": memory_id, "confidence": 0.75}

    def export(self, key):
        self._check()
        return [{"id": i, "content": c} for i, c in self.notes.get(key, [])]

    def forget(self, key):
        self._check()
        return len(self.notes.pop(key, []))


class ScriptedLLM:
    """Answers chat turns with `reply`; answers the note-extraction prompt with `notes_json`."""

    def __init__(self, reply="I hear you. Rest a little.", notes_json='["Feels anxious at night and sleeps badly"]'):
        self.reply, self.notes_json, self.chats, self.extractions = reply, notes_json, [], 0

    def chat(self, messages, **kw):
        if messages[0]["content"] == EXTRACT_PROMPT:
            self.extractions += 1
            return LLMResult(self.notes_json, "m", "m", 1)
        self.chats.append(messages)
        return LLMResult(self.reply, "m", "m", 1)

    def health(self):
        return "online"


class Echo:
    def translate(self, t):
        return f"LN[{t}]"


KEY = user_key("browser-id-1")


def run(message="I feel anxious tonight", llm=None, hmem=None, key=KEY):
    return handle_message(message, "s", llm=llm or ScriptedLLM(), translator=Echo(), memory=SessionMemory(),
                          resources=[], longterm=hmem, user_key=key)


# ---------- pipeline ----------
def test_recalled_notes_are_added_to_the_prompt_and_reported():
    hmem, llm = FakeHmem(), ScriptedLLM()
    hmem.remember(KEY, "Evening walks help with feeling anxious before bed")
    out = run(llm=llm, hmem=hmem)
    system_blocks = [m["content"] for m in llm.chats[0] if m["role"] == "system"]
    assert len(system_blocks) == 2 and system_blocks[1].startswith(MEMORY_INTRO) and "Evening walks" in system_blocks[1]
    assert out["memories_used"] == [{"id": "mem-1", "content": "Evening walks help with feeling anxious before bed", "score": 0.5}]
    assert "hmem:recalled 1 note(s)" in out["trace"]


def test_no_key_means_no_recall_at_all():
    hmem = FakeHmem()
    hmem.remember(KEY, "Evening walks help with feeling anxious before bed")
    out = run(hmem=hmem, key=None)
    assert hmem.recall_calls == 0 and out["memories_used"] == []


def test_crisis_and_unsupported_language_never_touch_memory():
    hmem, llm = FakeHmem(), ScriptedLLM()
    assert run("i want to die", llm=llm, hmem=hmem)["route"] == "crisis"
    assert run("Wìy ó fèn", llm=llm, hmem=hmem)["route"] == "lamnso_input_unsupported"
    assert hmem.recall_calls == 0 and llm.chats == []


def test_memory_service_down_does_not_break_the_reply():
    out = run(hmem=FakeHmem(down=True))
    assert out["route"] == "agent" and out["reply_english"] and "hmem:unavailable" in out["trace"]


# ---------- learning ----------
def test_parse_notes_is_tolerant_and_bounded():
    assert parse_notes('```json\n["Feels anxious at night", "Likes evening walks"]\n```') == [
        "Feels anxious at night", "Likes evening walks"]
    assert parse_notes('Sure! ["Feels anxious at night"] hope that helps') == ["Feels anxious at night"]
    assert parse_notes('["short", "' + "x" * 300 + '", 5, null]') == []
    assert parse_notes('["Same note here", "Same note here", "Another valid note", "A third valid note"]') == [
        "Same note here", "Another valid note"]
    assert parse_notes("[]") == [] and parse_notes("no json") == [] and parse_notes("[unclosed") == []


def test_learn_stores_counts_skips_and_survives_outages():
    h = FakeHmem()
    assert learn_from_turn(h, ScriptedLLM(), KEY, "u", "r") == {"stored": 1, "skipped": 0, "service": "online"}
    pii = ScriptedLLM(notes_json='["Contact is a@b.co for support", "Feels lonely since moving house"]')
    assert learn_from_turn(h, pii, KEY, "u", "r") == {"stored": 1, "skipped": 1, "service": "online"}
    assert learn_from_turn(FakeHmem(down=True), ScriptedLLM(), KEY, "u", "r")["service"] == "unavailable"

    class Down(ScriptedLLM):
        def chat(self, messages, **kw):
            raise NightshiftError("down")
    assert learn_from_turn(h, Down(), KEY, "u", "r")["stored"] == 0


def test_user_key_is_stable_fixed_length_and_hides_the_raw_id():
    assert user_key("a") == user_key("a") and user_key("a") != user_key("b")
    assert len(user_key("browser-id-1")) == 32 and "browser" not in user_key("browser-id-1")


# ---------- API ----------
@pytest.fixture
def api(monkeypatch, tmp_path):
    monkeypatch.setenv("TRACE_LOG_PATH", str(tmp_path / "trace.jsonl"))
    hmem, llm = FakeHmem(), ScriptedLLM()
    comps = app_main.Components(get_settings(), llm, Echo(), None, SessionMemory(), [], hmem)
    app_main.app.dependency_overrides[app_main.get_components] = lambda: comps
    yield TestClient(app_main.app), hmem, llm, tmp_path
    app_main.app.dependency_overrides.clear()


def chat(client, message, **kw):
    return client.post("/chat", json={"message": message, "session_id": "s1", "user_id": "browser-id-1", **kw}).json()


def test_memory_is_off_by_default(api):
    client, hmem, llm, _ = api
    out = chat(client, "I feel anxious tonight")
    assert out["memory_enabled"] is False and hmem.notes == {} and llm.extractions == 0 and hmem.recall_calls == 0


def test_two_sessions_learn_then_recall_and_trace_never_contains_text(api):
    client, hmem, llm, tmp = api
    first = chat(client, "I feel anxious tonight", remember=True)
    assert first["memory_enabled"] is True and first["memories_used"] == []
    assert [c for _, c in hmem.notes[KEY]] == ["Feels anxious at night and sleeps badly"]   # learned in the background
    second = chat(client, "I feel anxious again", remember=True)
    assert [m["content"] for m in second["memories_used"]] == ["Feels anxious at night and sleeps badly"]
    log = (tmp / "trace.jsonl").read_text()
    assert "anxious" not in log and '"event": "learn"' in log


def test_crisis_message_is_never_learned_from(api):
    client, hmem, llm, _ = api
    out = chat(client, "i want to die", remember=True)
    assert out["route"] == "crisis" and hmem.notes == {} and llm.extractions == 0


def test_export_forget_feedback_endpoints(api):
    client, hmem, _, _ = api
    chat(client, "I feel anxious tonight", remember=True)
    assert len(client.post("/memory/export", json={"user_id": "browser-id-1"}).json()["memories"]) == 1
    fb = client.post("/memory/feedback", json={"user_id": "browser-id-1", "memory_id": "mem-1", "kind": "helpful"})
    assert fb.status_code == 200
    assert client.post("/memory/feedback", json={"user_id": "x", "memory_id": "bad", "kind": "helpful"}).status_code == 422
    assert client.post("/memory/forget", json={"user_id": "browser-id-1"}).json() == {"erased": 1}
    assert client.post("/memory/export", json={"user_id": "browser-id-1"}).json()["memories"] == []
    hmem.down = True
    assert client.post("/memory/forget", json={"user_id": "browser-id-1"}).status_code == 503
