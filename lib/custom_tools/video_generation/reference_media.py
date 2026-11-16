"""Turn local reference media into URLs a provider accepts, and pre-check them.

Volcengine Ark (Seedance) accepts:

* ``image_url``: public URL, base64 data URL, or ``asset://<id>``;
* ``audio_url``: public URL, base64 data URL, or ``asset://<id>``;
* ``video_url``: public URL or ``asset://<id>`` only — **no base64**.

The whole request body is capped at 64 MB. So local images and audio are inlined,
while local videos are uploaded through a configurable :class:`MediaUploader`
(Volcengine TOS by default) and passed as a presigned URL.

Uploader selection (``CAPSULE_MEDIA_UPLOADER``):

* ``tos`` — Volcengine TOS; needs ``TOS_ACCESS_KEY``, ``TOS_SECRET_KEY``,
  ``TOS_BUCKET``, and optional ``TOS_ENDPOINT`` / ``TOS_REGION`` /
  ``TOS_KEY_PREFIX`` / ``TOS_URL_EXPIRES``. Selected automatically when
  ``TOS_BUCKET`` is set. Requires ``pip install tos``.
* unset — local videos are rejected before any paid request is made.
"""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Protocol, Sequence


REMOTE_PREFIXES = ("https://", "http://", "asset://")
INLINE_PREFIX = "data:"
# Ark rejects request bodies over 64 MB; keep headroom for JSON and the prompt.
MAX_INLINE_BODY_BYTES = 48 * 1024 * 1024


class MediaUploadError(RuntimeError):
    """Raised when local media cannot be turned into a provider-reachable URL."""


class MediaUploader(Protocol):
    def upload(self, path: Path) -> str:  # pragma: no cover - protocol
        ...


def is_remote(value: str) -> bool:
    return value.startswith(REMOTE_PREFIXES)


def is_inline(value: str) -> bool:
    return value.startswith(INLINE_PREFIX)


def local_path(value: str) -> Path:
    source = Path(value).expanduser()
    if not source.is_file():
        raise FileNotFoundError(f"Reference media does not exist: {source}")
    return source


def data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class TosUploader:
    """Upload to Volcengine TOS and return a presigned GET URL."""

    def __init__(self) -> None:
        missing = [name for name in ("TOS_ACCESS_KEY", "TOS_SECRET_KEY", "TOS_BUCKET") if not os.getenv(name)]
        if missing:
            raise MediaUploadError("TOS uploader needs env vars: " + ", ".join(missing))
        try:
            import tos  # type: ignore[import-not-found]
        except ImportError as exc:
            raise MediaUploadError("TOS uploader needs the Volcengine TOS SDK: pip install tos") from exc
        self._tos = tos
        region = os.getenv("TOS_REGION", "cn-beijing")
        endpoint = os.getenv("TOS_ENDPOINT") or f"tos-{region}.volces.com"
        self._client = tos.TosClientV2(os.environ["TOS_ACCESS_KEY"], os.environ["TOS_SECRET_KEY"], endpoint, region)
        self._bucket = os.environ["TOS_BUCKET"]
        self._prefix = os.getenv("TOS_KEY_PREFIX", "capsule-cinema/refs/").lstrip("/")
        self._expires = int(os.getenv("TOS_URL_EXPIRES", "86400"))

    def upload(self, path: Path) -> str:
        # Content-addressed key: re-running the same job reuses the same object.
        key = f"{self._prefix}{_sha256(path)[:24]}{path.suffix.lower()}"
        self._client.put_object_from_file(self._bucket, key, str(path))
        signed = self._client.pre_signed_url(
            self._tos.HttpMethodType.Http_Method_Get, self._bucket, key, expires=self._expires
        )
        return signed.signed_url


_UPLOADER_FACTORIES: dict[str, Callable[[], MediaUploader]] = {"tos": TosUploader}


def register_uploader(name: str, factory: Callable[[], MediaUploader]) -> None:
    """Let a local overlay plug in another object store (S3, OSS…)."""
    _UPLOADER_FACTORIES[name.strip().lower()] = factory


def configured_uploader_name() -> str:
    name = os.getenv("CAPSULE_MEDIA_UPLOADER", "").strip().lower()
    if name:
        return name
    return "tos" if os.getenv("TOS_BUCKET") else ""


def get_uploader() -> MediaUploader:
    name = configured_uploader_name()
    if not name:
        raise MediaUploadError(
            "Local reference videos must be uploaded first: Ark video_url accepts only http(s) "
            "or asset:// URLs, not base64. Set CAPSULE_MEDIA_UPLOADER=tos with TOS_ACCESS_KEY / "
            "TOS_SECRET_KEY / TOS_BUCKET, or pass public URLs in video_paths."
        )
    factory = _UPLOADER_FACTORIES.get(name)
    if factory is None:
        raise MediaUploadError(f"Unknown CAPSULE_MEDIA_UPLOADER {name!r}; known: {', '.join(sorted(_UPLOADER_FACTORIES))}")
    return factory()


@dataclass
class MediaResolver:
    """Resolve a request's media in one pass so the inline budget is shared.

    ``inline_kinds`` lists the media kinds the provider accepts as base64.
    """

    inline_kinds: frozenset[str] = frozenset({"image", "audio"})
    max_inline_bytes: int = MAX_INLINE_BODY_BYTES
    uploader_factory: Callable[[], MediaUploader] = get_uploader
    _inline_bytes: int = 0
    _uploader: Optional[MediaUploader] = None

    def resolve(self, value: str, kind: str) -> str:
        if is_remote(value):
            return value
        if is_inline(value):
            if kind not in self.inline_kinds:
                raise ValueError(f"{kind} references cannot be base64 data URLs for this provider; pass a URL")
            self._inline_bytes += len(value)
            self._check_budget()
            return value
        source = local_path(value)
        if kind in self.inline_kinds:
            # base64 grows the payload by 4/3.
            projected = self._inline_bytes + (source.stat().st_size * 4 + 2) // 3
            if projected <= self.max_inline_bytes:
                self._inline_bytes = projected
                return data_url(source)
        return self._upload(source)

    def _upload(self, source: Path) -> str:
        if self._uploader is None:
            self._uploader = self.uploader_factory()
        try:
            return self._uploader.upload(source)
        except MediaUploadError:
            raise
        except Exception as exc:  # SDK errors vary by backend
            raise MediaUploadError(f"Uploading {source.name} failed: {exc.__class__.__name__}") from exc

    def _check_budget(self) -> None:
        if self._inline_bytes > self.max_inline_bytes:
            raise ValueError(
                f"Inline media exceeds {self.max_inline_bytes // (1024 * 1024)} MB; pass URLs or configure an uploader"
            )


def probe_seconds(value: str) -> Optional[float]:
    """Return a local media file's duration via ffprobe, or None if unknown."""
    if is_remote(value) or is_inline(value) or not shutil.which("ffprobe"):
        return None
    try:
        completed = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(local_path(value))],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return float(json.loads(completed.stdout)["format"]["duration"])
    except (OSError, subprocess.SubprocessError, KeyError, TypeError, ValueError):
        return None


def check_durations(
    values: Sequence[str],
    *,
    kind: str,
    per_item_range: Optional[Sequence[float]],
    max_total: Optional[float],
    probe: Optional[Callable[[str], Optional[float]]] = None,
) -> None:
    """Reject local references whose length breaks provider limits (before paying)."""
    if not values or (per_item_range is None and max_total is None):
        return
    probe = probe or probe_seconds
    total = 0.0
    for index, value in enumerate(values, start=1):
        seconds = probe(value)
        if seconds is None:
            continue
        if per_item_range is not None:
            low, high = per_item_range
            # 0.05 s tolerance: container durations are rarely exact.
            if seconds < float(low) - 0.05 or seconds > float(high) + 0.05:
                raise ValueError(f"Reference {kind} {index} is {seconds:.2f}s; allowed {low}-{high}s")
        total += seconds
    if max_total is not None and total > float(max_total) + 0.05:
        raise ValueError(f"Reference {kind}s total {total:.2f}s; allowed at most {max_total}s")
