"""Append-only JSONL trace: which route ran and which model answered. No message text by default."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path


def hash_session(session_id: str) -> str:
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:12]


def write_trace(path: Path, record: dict) -> None:
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **record},
                               ensure_ascii=False) + "\n")
    except OSError:
        pass  # tracing must never break a reply
