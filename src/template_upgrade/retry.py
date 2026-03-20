from __future__ import annotations
import heapq
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from .exceptions import MaxRetriesExceeded
log = logging.getLogger(__name__)

@dataclass(order=True)
class _Entry:
    run_at: float
    attempt: int
    task_id: Any = field(compare=False)

class RetryScheduler:
    BASE: float = 2.0
    CAP: float = 60.0
    MAX_ATTEMPTS: int = 4

    def __init__(self, base: float=2.0, cap: float=60.0, max_attempts: int=4) -> None:
        self.BASE = base
        self.CAP = cap
        self.MAX_ATTEMPTS = max_attempts
        self._heap: list[_Entry] = []

    def schedule(self, task_id: Any, attempt: int=0) -> None:
        delay = min(self.BASE ** attempt, self.CAP)
        run_at = time.monotonic() + delay
        entry = _Entry(run_at=run_at, attempt=attempt, task_id=task_id)
        heapq.heappush(self._heap, entry)
        log.debug("Scheduled '%s' attempt=%d in %.1fs", task_id, attempt, delay)

    def next_ready(self) -> Optional[tuple[Any, int]]:
        if not self._heap:
            return None
        entry = self._heap[0]
        if time.monotonic() >= entry.run_at:
            heapq.heappop(self._heap)
            return (entry.task_id, entry.attempt)
        return None

    def has_budget(self, attempt: int) -> bool:
        return attempt < self.MAX_ATTEMPTS

    def seconds_until_next(self) -> Optional[float]:
        if not self._heap:
            return None
        return max(0.0, self._heap[0].run_at - time.monotonic())

    def is_empty(self) -> bool:
        return len(self._heap) == 0
