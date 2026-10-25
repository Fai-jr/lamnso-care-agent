"""The app's data layer on Zetaris.

Three tables in one Iceberg datalake (Zetaris creates tables under a DATALAKE: datalake.directory.table):
  resources        vetted coping ideas the agent may offer (the model is told to offer nothing else)
  interaction_log  one row per request: route, which model answered, latency, translation outcome
  checkins         an optional 1-5 mood check-in per person (hashed key), read back as a weekly trend

Only simple types (STRING, BIGINT) are used, and no user-written text ever reaches SQL: every value is a number,
a hash, or a string from a fixed list or a strict character set.
"""
from __future__ import annotations

import re
import time
from typing import Any, Callable, Optional

from backend.app.zetaris import ZetarisClient, ZetarisError

LAKE = "lamnso_care"
NS = f"{LAKE}.app"

TABLES: dict[str, str] = {
    "resources": "(id STRING, kind STRING, title_en STRING, body_en STRING, tags STRING, region STRING, contact STRING, verified BIGINT)",
    "interaction_log": "(ts BIGINT, session STRING, route STRING, model_used STRING, latency_ms BIGINT, translation_ok BIGINT, memory_on BIGINT, memories_used BIGINT, in_chars BIGINT)",
    "checkins": "(ts BIGINT, user_key STRING, mood BIGINT, tag STRING)",
}

TOPICS: dict[str, tuple[str, ...]] = {
    "sleep": ("sleep", "insomnia", "tired", "awake", "night", "nightmare"),
    "anxiety": ("anxious", "anxiety", "worry", "worried", "nervous", "panic", "afraid", "scared", "fear", "breath"),
    "stress": ("stress", "overwhelm", "pressure", "exam", "deadline"),
    "low_mood": ("sad", "depress", "down", "hopeless", "empty", "cry", "unhappy"),
    "loneliness": ("alone", "lonely", "isolated", "nobody", "friendless"),
}
CHECKIN_TAGS = ("sleep", "anxiety", "stress", "low_mood", "loneliness", "other")

# Texts avoid apostrophes on purpose, so seed SQL needs no escaping.
SEED_RESOURCES: list[tuple[str, str, str, str, str]] = [
    ("coping-breathing", "Slow breathing",
     "Breathe in slowly for four counts, pause, then breathe out for six counts. Repeat five times.", "anxiety,stress,sleep"),
    ("coping-grounding", "Five senses grounding",
     "Name five things you can see, four you can touch, three you can hear, two you can smell and one you can taste.", "anxiety,stress"),
    ("coping-sleep", "Wind down for sleep",
     "Keep the same bedtime, put the phone away for thirty minutes before bed, and write your worries for tomorrow on paper.", "sleep"),
    ("coping-walk", "A short walk",
     "A walk outside, even ten minutes, can lift your mood and ease tension.", "stress,low_mood,anxiety"),
    ("coping-talk", "Tell someone you trust",
     "Tell one person you trust how you feel today. You do not have to explain everything.", "loneliness,low_mood,stress,anxiety"),
    ("coping-small-step", "One small step",
     "Choose one small thing for today, like washing your face or eating a meal, and let that be enough.", "low_mood"),
]

_SAFE_TEXT = re.compile(r"^[A-Za-z0-9 _:./,()@+\-]{0,120}$")
_USER_KEY = re.compile(r"^[0-9a-f]{32}$")
_SESSION = re.compile(r"^[0-9a-f]{12}$")


def detect_topics(message: str, limit: int = 2) -> list[str]:
    """Fixed keyword lookup. Only the matched topic NAMES (from the lists above) are ever used in SQL."""
    text = message.lower()
    found = [name for name, words in TOPICS.items() if any(w in text for w in words)]
    return found[:limit]


def _safe(value: Any, default: str = "") -> str:
    text = "" if value is None else str(value)
    return text if _SAFE_TEXT.match(text) else default


def _int(value: Any) -> int:
    return int(value) if value is not None else 0


class ZetarisStore:
    def __init__(self, client: ZetarisClient, storage_path: str, clock: Callable[[], float] = time.time):
        self.client, self.storage_path, self._clock = client, storage_path, clock

    # ---------------------------------------------------------------- setup
    def _exists(self, table: str) -> bool:
        try:
            self.client.query(f"SELECT 1 AS x FROM {NS}.{table} LIMIT 1")
            return True
        except ZetarisError:
            return False

    def setup(self, ensure_dir: Optional[Callable[[str], str]] = None) -> dict:
        """Idempotent: creates the datalake, tables and seed rows only if they are missing."""
        report: dict = {"datalake": "exists", "tables": {}, "seeded": 0}
        if not any(self._exists(t) for t in TABLES):
            if ensure_dir:
                report["directory"] = ensure_dir(self.storage_path)
            try:
                self.client.query(f"CREATE DATALAKE {LAKE} OPTIONS (storageType 'Local', storagePath '{self.storage_path}')")
                report["datalake"] = "created"
            except ZetarisError as exc:
                if "exist" not in str(exc).lower():
                    raise
        for table, columns in TABLES.items():
            if self._exists(table):
                report["tables"][table] = "exists"
            else:
                self.client.query(f"CREATE TABLE {NS}.{table} {columns} USING iceberg")
                report["tables"][table] = "created"
        if self.count("resources") == 0:
            report["seeded"] = self._seed()
        return report

    def _seed(self) -> int:
        rows = [f"('{i}', 'coping', '{t}', '{b}', '{tags}', '', '', 0)" for i, t, b, tags in SEED_RESOURCES]
        try:
            self.client.query(f"INSERT INTO {NS}.resources VALUES " + ", ".join(rows))
        except ZetarisError:           # some engines reject multi-row VALUES: fall back to one row at a time
            for row in rows:
                self.client.query(f"INSERT INTO {NS}.resources VALUES {row}")
        return len(rows)

    def count(self, table: str) -> int:
        if table not in TABLES:
            raise ZetarisError(f"unknown table {table}")
        rows = self.client.query(f"SELECT COUNT(*) AS n FROM {NS}.{table}")
        return _int(rows[0]["n"]) if rows else 0

    # ---------------------------------------------------------------- reads used by the agent
    def coping_ideas(self, topics: list[str], limit: int = 3) -> list[dict]:
        topics = [t for t in topics if t in TOPICS]
        if not topics:
            return []
        cond = " OR ".join(f"tags LIKE '%{t}%'" for t in topics)
        rows = self.client.query(
            f"SELECT id, title_en, body_en FROM {NS}.resources WHERE kind = 'coping' AND verified >= 0 AND ({cond}) LIMIT {int(limit)}")
        return [{"id": r["id"], "title": r["title_en"], "body": r["body_en"]} for r in rows]

    def mood_trend(self, user_key: str, days: int = 7) -> Optional[dict]:
        if not _USER_KEY.match(user_key):
            raise ZetarisError("invalid user key")
        since = int((self._clock() - days * 86400) * 1000)
        rows = self.client.query(
            f"SELECT COUNT(*) AS n, AVG(mood) AS avg_mood, MIN(mood) AS lowest FROM {NS}.checkins "
            f"WHERE user_key = '{user_key}' AND ts >= {since}")
        if not rows or _int(rows[0]["n"]) == 0:
            return None
        r = rows[0]
        return {"count": _int(r["n"]), "average": round(float(r["avg_mood"]), 1), "lowest": _int(r["lowest"]), "days": days}

    # ---------------------------------------------------------------- writes
    def add_checkin(self, user_key: str, mood: int, tag: str = "other") -> None:
        if not _USER_KEY.match(user_key):
            raise ZetarisError("invalid user key")
        if not isinstance(mood, int) or isinstance(mood, bool) or not 1 <= mood <= 5:
            raise ZetarisError("mood must be a whole number from 1 to 5")
        tag = tag if tag in CHECKIN_TAGS else "other"
        self.client.query(f"INSERT INTO {NS}.checkins VALUES ({int(self._clock() * 1000)}, '{user_key}', {mood}, '{tag}')")

    def forget_checkins(self, user_key: str) -> None:
        if not _USER_KEY.match(user_key):
            raise ZetarisError("invalid user key")
        self.client.query(f"DELETE FROM {NS}.checkins WHERE user_key = '{user_key}'")

    def log_interaction(self, *, session: str, route: str, model_used: Optional[str], latency_ms: int,
                        translation_ok: Optional[bool], memory_on: bool, memories_used: int, in_chars: int) -> None:
        ok = -1 if translation_ok is None else int(bool(translation_ok))
        session = session if _SESSION.match(session or "") else "000000000000"
        self.client.query(
            f"INSERT INTO {NS}.interaction_log VALUES ({int(self._clock() * 1000)}, '{session}', '{_safe(route, 'unknown')}', "
            f"'{_safe(model_used)}', {_int(latency_ms)}, {ok}, {int(bool(memory_on))}, {_int(memories_used)}, {_int(in_chars)})")

    # ---------------------------------------------------------------- analytics for the demo
    def stats(self) -> dict:
        rows = self.client.query(
            f"SELECT route, model_used, COUNT(*) AS requests, ROUND(AVG(latency_ms)) AS avg_latency_ms, "
            f"SUM(translation_ok) AS translated FROM {NS}.interaction_log GROUP BY route, model_used ORDER BY requests DESC")
        out = [{"route": r["route"], "model_used": r["model_used"] or None, "requests": _int(r["requests"]),
                "avg_latency_ms": _int(r["avg_latency_ms"]), "translated": max(_int(r["translated"]), 0)} for r in rows]
        return {"total_requests": sum(r["requests"] for r in out), "by_route_and_model": out}

    def health(self) -> str:
        try:
            return "online" if self.client.query("SELECT 1 AS x") else "offline"
        except ZetarisError:
            return "offline"
