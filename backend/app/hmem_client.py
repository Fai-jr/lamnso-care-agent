"""Client for the local H-MEM service (engines/hmem, a Meterless engine).

The service stores short, non-identifying notes per person and ranks them with H-MEM's hybrid formula.
This client never sends a raw id: callers pass user_key(raw_id), a one-way hash.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

import httpx


class HmemError(RuntimeError):
    """The memory service is unreachable or returned an unexpected error."""


class HmemPolicyError(HmemError):
    """The service refused a note (personal identifier suspected, too long, duplicate cap, ...)."""

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


@dataclass(frozen=True)
class Note:
    id: str
    content: str
    score: float
    type: str = "personal"
    source: str = ""


def user_key(raw_id: str) -> str:
    """Pseudonymous, fixed-length key. The raw browser/session id is never stored by the memory service."""
    return hashlib.sha256(("lamnso-care:" + raw_id).encode("utf-8")).hexdigest()[:32]


class HmemClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8765", token: str = "", timeout: float = 3.0,
                 transport: Optional[httpx.BaseTransport] = None):
        self.base_url = base_url.rstrip("/")
        self._headers = {"Content-Type": "application/json"}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"
        self._http = httpx.Client(timeout=timeout, transport=transport)

    def _call(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        try:
            r = self._http.request(method, self.base_url + path, headers=self._headers, json=body)
        except httpx.HTTPError as exc:
            raise HmemError(f"memory service unavailable ({exc.__class__.__name__})") from exc
        if r.status_code == 422:
            data = _json(r)
            raise HmemPolicyError(str(data.get("error", "rejected")), str(data.get("message", "")))
        if r.status_code >= 400:
            raise HmemError(f"memory service returned HTTP {r.status_code}")
        return _json(r)

    def health(self) -> str:
        try:
            return "online" if self._call("GET", "/health").get("ok") else "offline"
        except HmemError:
            return "offline"

    def recall(self, key: str, query: str, top_n: Optional[int] = None) -> list[Note]:
        body: dict = {"user_id": key, "query": query}
        if top_n:
            body["top_n"] = top_n
        data = self._call("POST", "/recall", body)
        return [Note(m["id"], m["content"], float(m["score"]), m.get("type", "personal"), m.get("source", ""))
                for m in data.get("memories", [])]

    def remember(self, key: str, content: str, source: str = "care-agent:session-note") -> dict:
        return self._call("POST", "/remember", {"user_id": key, "content": content, "source": source})

    def feedback(self, key: str, memory_id: str, kind: str) -> dict:
        return self._call("POST", "/feedback", {"user_id": key, "memory_id": memory_id, "kind": kind})

    def export(self, key: str) -> list[dict]:
        return self._call("POST", "/export", {"user_id": key}).get("memories", [])

    def forget(self, key: str) -> int:
        return int(self._call("POST", "/forget", {"user_id": key}).get("erased", 0))


def _json(r: httpx.Response) -> dict:
    try:
        data = r.json()
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}
