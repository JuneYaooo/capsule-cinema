"""Retry a single idempotent HTTP step (status query, result download) through brief network failures."""

from __future__ import annotations

import time
from typing import Callable, TypeVar

import requests

T = TypeVar("T")
_RETRY_STATUS = {429, 500, 502, 503, 504}


def retry_transient(step: Callable[[], T], attempts: int = 5, base_delay: float = 2.0) -> T:
    """Run step, retrying network errors and retryable statuses. Never wrap a paid submit in this."""
    for attempt in range(attempts):
        last = attempt == attempts - 1
        try:
            result = step()
            if last or getattr(result, "status_code", 200) not in _RETRY_STATUS:
                return result
        except requests.RequestException:
            if last:
                raise
        time.sleep(base_delay * 2**attempt)
    raise RuntimeError("unreachable")
