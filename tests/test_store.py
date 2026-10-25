import pytest
from fastapi.testclient import TestClient

from backend.app import main as app_main
from backend.app.config import get_settings
from backend.app.hmem_client import user_key
from backend.app.memory import SessionMemory
from backend.app.nightshift import LLMResult
from backend.app.pipeline import IDEAS_INTRO, TREND_INTRO, handle_message
from backend.app.store import NS, SEED_RESOURCES, TABLES, ZetarisStore, detect_topics
from backend.app.zetaris import ZetarisError

KEY = "a" * 32
PATH = "/home/zetaris/customer-data/shared/lamnso-lakehouse"


class SQL:
    """Records every statement; `respond(sql)` returns rows or raises ZetarisError."""
    def __init__(self, respond=None):
        self.sql, self.respond = [], respond or (lambda s: [])

    def query(self, sql):
        self.sql.append(sql)
        return self.respond(sql)

    def close(self):
        pass


def store(respond=None, now=1_800_000_000.0):
    c = SQL(respond)
    return ZetarisStore(c, PATH, clock=lambda: now), c


# ---------------------------------------------------------------- setup
def test_setup_on_a_fresh_instance_creates_everything_in_order():
    def respond(sql):
        if sql.startswith("SELECT 1 AS x FROM"):
            raise ZetarisError("not found")
        if sql.startswith("SELECT COUNT"):
            return [{"n": 0}]
        return []
    s, c = store(respond)
    report = s.setup(ensure_dir=lambda p: "ok")
    assert report["datalake"] == "created" and report["seeded"] == len(SEED_RESOURCES) and report["directory"] == "ok"
    creates = [q for q in c.sql if q.startswith("CREATE")]
    assert creates[0] == f"CREATE DATALAKE lamnso_care OPTIONS (storageType 'Local', storagePath '{PATH}')"
    assert [q.split()[2] for q in creates[1:]] == [f"{NS}.{t}" for t in TABLES]
    assert all(q.endswith("USING iceberg") for q in creates[1:])
    inserts = [q for q in c.sql if q.startswith("INSERT")]
    assert len(inserts) == 1 and inserts[0].count("'coping'") == len(SEED_RESOURCES)


def test_setup_is_idempotent_when_everything_exists():
    s, c = store(lambda q: [{"n": 6}] if q.startswith("SELECT COUNT") else [{"x": 1}])
    report = s.setup()
    assert report["datalake"] == "exists" and report["seeded"] == 0
    assert not [q for q in c.sql if q.startswith(("CREATE", "INSERT"))]


def test_setup_tolerates_an_existing_datalake_but_not_other_errors():
    def exists_err(sql):
        if sql.startswith("SELECT 1 AS x"):
            raise ZetarisError("nf")
        if sql.startswith("CREATE DATALAKE"):
            raise ZetarisError("Datalake lamnso_care already exists")
        return [{"n": 1}] if sql.startswith("SELECT COUNT") else []
    assert store(exists_err)[0].setup()["datalake"] == "exists"

    def bad_path(sql):
        if sql.startswith("SELECT 1 AS x"):
            raise ZetarisError("nf")
        if sql.startswith("CREATE DATALAKE"):
            raise ZetarisError("Invalid file path to access")
        return []
    with pytest.raises(ZetarisError, match="Invalid file path"):
        store(bad_path)[0].setup()


def test_seed_falls_back_to_one_row_at_a_time():
    def respond(sql):
        if sql.startswith("SELECT 1 AS x"):
            return [{"x": 1}]
        if sql.startswith("SELECT COUNT"):
            return [{"n": 0}]
        if sql.startswith("INSERT") and sql.count("'coping'") > 1:
            raise ZetarisError("multi-row not supported")
        return []
    s, c = store(respond)
    assert s.setup()["seeded"] == len(SEED_RESOURCES)
    assert len([q for q in c.sql if q.startswith("INSERT")]) == 1 + len(SEED_RESOURCES)


def test_seed_text_needs_no_sql_escaping():
    assert all("'" not in field for row in SEED_RESOURCES for field in row)


# ---------------------------------------------------------------- reads
def test_detect_topics():
    assert detect_topics("I cannot sleep and I feel anxious") == ["sleep", "anxiety"]
    assert detect_topics("I feel so lonely") == ["loneliness"]
    assert detect_topics("what is the weather") == []
    # the three suggestion pills on the first screen each find an idea
    assert detect_topics("I feel stressed about school") == ["stress"]
    assert detect_topics("Help me sleep better") == ["sleep"]
    assert detect_topics("Guide me through breathing") == ["anxiety"]
    assert len(detect_topics("anxious sad alone tired stress")) == 2


def test_coping_ideas_query_uses_only_known_topics_and_skips_empty():
    s, c = store(lambda q: [{"id": "coping-walk", "title_en": "A short walk", "body_en": "Walk."}])
    assert s.coping_ideas([]) == [] and s.coping_ideas(["'; DROP TABLE x;--"]) == [] and c.sql == []
    ideas = s.coping_ideas(["sleep", "evil"])
    assert ideas == [{"id": "coping-walk", "title": "A short walk", "body": "Walk."}]
    assert "tags LIKE '%sleep%'" in c.sql[0] and "evil" not in c.sql[0] and c.sql[0].endswith("LIMIT 3")


def test_mood_trend():
    s, c = store(lambda q: [{"n": 4, "avg_mood": 2.25, "lowest": 1}], now=1_800_000_000)
    assert s.mood_trend(KEY) == {"count": 4, "average": 2.2, "lowest": 1, "days": 7}
    assert f"ts >= {(1_800_000_000 - 7 * 86400) * 1000}" in c.sql[0] and f"user_key = '{KEY}'" in c.sql[0]
    assert store(lambda q: [{"n": 0, "avg_mood": None, "lowest": None}])[0].mood_trend(KEY) is None
    with pytest.raises(ZetarisError):
        s.mood_trend("x' OR '1'='1")


# ---------------------------------------------------------------- writes
def test_add_checkin_validates_and_formats():
    s, c = store(now=1_800_000_000)
    s.add_checkin(KEY, 4, "sleep")
    s.add_checkin(KEY, 2, "not-a-tag")
    assert c.sql[0] == f"INSERT INTO {NS}.checkins VALUES (1800000000000, '{KEY}', 4, 'sleep')"
    assert c.sql[1].endswith(", 2, 'other')")
    for bad in (0, 6, "3", 3.5, True, None):
        with pytest.raises(ZetarisError):
            s.add_checkin(KEY, bad)
    with pytest.raises(ZetarisError):
        s.add_checkin("short", 3)


def test_log_interaction_is_positional_and_sanitised():
    s, c = store(now=1_800_000_000)
    s.log_interaction(session="0123456789ab", route="agent", model_used="nvidia/nemotron-3.5-lightning-30b-a3b",
                      latency_ms=610, translation_ok=True, memory_on=True, memories_used=2, in_chars=40)
    assert c.sql[0] == (f"INSERT INTO {NS}.interaction_log VALUES (1800000000000, '0123456789ab', 'agent', "
                        "'nvidia/nemotron-3.5-lightning-30b-a3b', 610, 1, 1, 2, 40)")
    s.log_interaction(session="bad session", route="a'b", model_used="x'); DROP TABLE t;--", latency_ms=0,
                      translation_ok=None, memory_on=False, memories_used=0, in_chars=3)
    assert "'000000000000', 'unknown', ''" in c.sql[1] and "DROP" not in c.sql[1] and ", -1, 0, 0, 3)" in c.sql[1]


def test_forget_checkins_and_stats():
    s, c = store(lambda q: [{"route": "agent", "model_used": "m1", "requests": 3, "avg_latency_ms": 640, "translated": 2},
                            {"route": "crisis", "model_used": "", "requests": 1, "avg_latency_ms": 0, "translated": 1}])
    s.forget_checkins(KEY)
    assert c.sql[0] == f"DELETE FROM {NS}.checkins WHERE user_key = '{KEY}'"
    st = s.stats()
    assert st["total_requests"] == 4 and st["by_route_and_model"][1]["model_used"] is None


# ---------------------------------------------------------------- pipeline
class LLM:
    def __init__(self):
        self.seen = []

    def chat(self, messages, **kw):
        self.seen.append(messages)
        return LLMResult("I hear you. Rest a little.", "m", "m", 1)


class Echo:
    def translate(self, t):
        return f"LN[{t}]"


class FakeStore:
    def __init__(self, down=False):
        self.down, self.calls = down, []

    def _chk(self):
        if self.down:
            raise ZetarisError("down")

    def coping_ideas(self, topics, limit=3):
        self._chk()
        self.calls.append(("ideas", topics))
        return [{"id": "coping-sleep", "title": "Wind down for sleep", "body": "Keep a bedtime."}] if topics else []

    def mood_trend(self, key):
        self._chk()
        self.calls.append(("trend", key))
        return {"count": 3, "average": 2.0, "lowest": 1, "days": 7}

    def add_checkin(self, key, mood, tag="other"):
        self._chk()
        self.calls.append(("checkin", mood, tag))

    def forget_checkins(self, key):
        self._chk()
        self.calls.append(("forget", key))

    def log_interaction(self, **kw):
        self._chk()
        self.calls.append(("log", kw["route"], kw["model_used"]))

    def stats(self):
        self._chk()
        return {"total_requests": 2, "by_route_and_model": []}

    def health(self):
        return "offline" if self.down else "online"


def run(msg, st, key=None, llm=None):
    llm = llm or LLM()
    out = handle_message(msg, "s", llm=llm, translator=Echo(), memory=SessionMemory(), resources=[], store=st, store_key=key)
    return out, llm


def test_vetted_ideas_are_offered_to_the_model_and_reported():
    out, llm = run("I cannot sleep at night", FakeStore())
    blocks = [m["content"] for m in llm.seen[0] if m["role"] == "system"]
    assert any(b.startswith(IDEAS_INTRO) and "Wind down for sleep" in b for b in blocks)
    assert out["ideas_used"] == [{"id": "coping-sleep", "title": "Wind down for sleep"}]
    assert "zetaris:1 coping idea(s)" in out["trace"]


def test_mood_trend_only_with_a_key_and_never_without_consent():
    st = FakeStore()
    _, llm = run("I cannot sleep at night", st, key=None)
    assert not any(c[0] == "trend" for c in st.calls)
    _, llm2 = run("I cannot sleep at night", st, key=KEY)
    assert any(m["content"].startswith(TREND_INTRO) for m in llm2.seen[0] if m["role"] == "system")


def test_unrelated_message_gets_no_ideas_and_zetaris_outage_is_harmless():
    out, llm = run("hello there", FakeStore())
    assert out["ideas_used"] == [] and len([m for m in llm.seen[0] if m["role"] == "system"]) == 1
    out2, _ = run("I cannot sleep", FakeStore(down=True))
    assert out2["route"] == "agent" and "zetaris:unavailable" in out2["trace"]


def test_crisis_never_reaches_the_data_layer():
    st = FakeStore()
    out, llm = run("i want to die", st)
    assert out["route"] == "crisis" and st.calls == [] and llm.seen == []


# ---------------------------------------------------------------- API
@pytest.fixture
def api(monkeypatch, tmp_path):
    monkeypatch.setenv("TRACE_LOG_PATH", str(tmp_path / "trace.jsonl"))
    st = FakeStore()
    comps = app_main.Components(get_settings(), LLM(), Echo(), None, SessionMemory(), [], None, st)
    app_main.app.dependency_overrides[app_main.get_components] = lambda: comps
    yield TestClient(app_main.app), st, comps
    app_main.app.dependency_overrides.clear()


def test_chat_is_logged_to_zetaris_in_the_background(api):
    client, st, _ = api
    r = client.post("/chat", json={"message": "I cannot sleep", "session_id": "s1"}).json()
    assert r["ideas_used"][0]["id"] == "coping-sleep"
    assert ("log", "agent", "m") in st.calls


def test_stats_checkin_and_forget_endpoints(api):
    client, st, comps = api
    assert client.get("/stats").json()["total_requests"] == 2
    assert client.post("/checkin", json={"user_id": "u1", "mood": 4, "tag": "sleep"}).json() == {"saved": True}
    assert ("checkin", 4, "sleep") in st.calls
    assert client.post("/checkin", json={"user_id": "u1", "mood": 9}).status_code == 422
    assert client.post("/checkin", json={"user_id": "u1", "mood": 3, "tag": "bad"}).status_code == 422

    class H:
        def forget(self, k):
            return 2
    comps.hmem = H()
    assert client.post("/memory/forget", json={"user_id": "u1"}).json() == {"erased": 2, "checkins_erased": True}
    st.down = True
    assert client.post("/memory/forget", json={"user_id": "u1"}).json()["checkins_erased"] is False
    assert client.get("/stats").status_code == 503 and client.post("/checkin", json={"user_id": "u", "mood": 3}).status_code == 503


def test_data_layer_endpoints_report_503_when_zetaris_is_not_connected(api):
    client, _, comps = api
    comps.store = None
    assert client.get("/stats").status_code == 503
    assert client.post("/checkin", json={"user_id": "u1", "mood": 3}).status_code == 503
