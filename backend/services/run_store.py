from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class StoredRun:
    run_id: str
    query: str
    result: dict[str, Any]
    created_at: float


class RunStore:
    """In-memory run result store with TTL and bounded size."""

    def __init__(self, *, max_items: int = 500, ttl_seconds: int = 24 * 3600) -> None:
        self._max_items = max(100, max_items)
        self._ttl_seconds = max(60, ttl_seconds)
        self._lock = threading.Lock()
        self._items: dict[str, StoredRun] = {}

    def save(self, *, run_id: str, query: str, result: dict[str, Any]) -> None:
        now = time.time()
        with self._lock:
            self._purge_locked(now=now)
            self._items[run_id] = StoredRun(run_id=run_id, query=query, result=result, created_at=now)
            if len(self._items) > self._max_items:
                oldest = min(self._items.values(), key=lambda x: x.created_at)
                self._items.pop(oldest.run_id, None)

    def get(self, run_id: str) -> Optional[StoredRun]:
        now = time.time()
        with self._lock:
            self._purge_locked(now=now)
            return self._items.get(run_id)

    def _purge_locked(self, *, now: float) -> None:
        cutoff = now - self._ttl_seconds
        expired = [rid for rid, item in self._items.items() if item.created_at < cutoff]
        for rid in expired:
            self._items.pop(rid, None)


run_store = RunStore()
