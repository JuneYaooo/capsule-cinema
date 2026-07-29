"""Stable, secret-free Provider request IDs scoped to one Factory job."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


_SAFE_COMPONENT = re.compile(r"[^a-zA-Z0-9._-]+")


def job_scope(output_dir: Path) -> str:
    """Return a stable opaque scope without exposing an absolute workspace path.

    Factory jobs are mounted below ``/workspace/jobs/<job-id>``.  Local tests
    and non-Factory callers use a digest of the resolved output directory so
    that repeated execution in the same directory is stable while two output
    directories remain isolated.
    """

    resolved = output_dir.expanduser().resolve()
    parts = resolved.parts
    for index, part in enumerate(parts[:-1]):
        if part == "jobs" and index + 1 < len(parts):
            candidate = _SAFE_COMPONENT.sub("-", parts[index + 1]).strip("-._")
            if candidate:
                return candidate[:48]
    return "local-" + hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:20]


def scoped_request_id(*, prefix: str, output_dir: Path, logical_key: str) -> str:
    """Build one deterministic ID for a logical paid call inside one job."""

    safe_prefix = _SAFE_COMPONENT.sub("-", prefix).strip("-._").lower()
    if not safe_prefix:
        raise ValueError("Provider request ID prefix must contain a safe character")
    logical_digest = hashlib.sha256(logical_key.encode("utf-8")).hexdigest()[:16]
    return f"{safe_prefix}-{job_scope(output_dir)}-{logical_digest}"
