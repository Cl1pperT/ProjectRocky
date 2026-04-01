from __future__ import annotations

from time import monotonic


class PrintDeduper:
    """Tracks print ids for a bounded TTL window."""

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl_seconds = ttl_seconds
        self._entries: dict[str, float] = {}

    def try_mark(self, print_id: str) -> bool:
        self._prune()
        if print_id in self._entries:
            return False
        self._entries[print_id] = monotonic() + self._ttl_seconds
        return True

    def clear(self, print_id: str) -> None:
        self._entries.pop(print_id, None)

    def _prune(self) -> None:
        now = monotonic()
        expired = [print_id for print_id, expires_at in self._entries.items() if expires_at <= now]
        for print_id in expired:
            self._entries.pop(print_id, None)
