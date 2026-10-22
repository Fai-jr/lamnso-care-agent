"""Per-session short-term memory, held in RAM only (English text, last few turns).

This is the seam where Meterless H-MEM (persistent memory) and Zetaris-backed storage plug in next:
keep the recall()/remember() interface and swap the implementation.
"""
from __future__ import annotations

from collections import defaultdict


class SessionMemory:
    def __init__(self, max_turns: int = 6):
        self.max_turns = max_turns
        self._turns: dict[str, list[tuple[str, str]]] = defaultdict(list)

    def recall(self, session_id: str) -> list[dict[str, str]]:
        msgs: list[dict[str, str]] = []
        for user, assistant in self._turns[session_id]:
            msgs.append({"role": "user", "content": user})
            msgs.append({"role": "assistant", "content": assistant})
        return msgs

    def remember(self, session_id: str, user_text: str, assistant_text: str) -> None:
        turns = self._turns[session_id]
        turns.append((user_text, assistant_text))
        del turns[: -self.max_turns]
