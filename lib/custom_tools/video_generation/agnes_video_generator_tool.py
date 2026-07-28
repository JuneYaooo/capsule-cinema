"""Official Agnes text-to-video adapter."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Optional, Type
from urllib.parse import urlparse

import requests
from pydantic import BaseModel, Field

from custom_tools.audio_generation.base_tool_compat import BaseTool
from .output_dir_utils import default_video_output_dir, resolve_video_output_dir


DEFAULT_AGNES_BASE_URL = "https://apihub.agnes-ai.com"
DEFAULT_AGNES_VIDEO_MODEL = "agnes-video-v2.0"
DEFAULT_OUTPUT_DIR = default_video_output_dir("agnes_video")
AGNES_VIDEO_DIMENSIONS = {
    "9:16": (512, 912),
    "16:9": (912, 512),
    "1:1": (512, 512),
}
_VIDEO_SUBMIT_LOCK = threading.Lock()
_LAST_VIDEO_SUBMIT_AT = 0.0


class AgnesVideoSchema(BaseModel):
    prompt: str = Field(..., description="Video prompt")
    generation_type: str = Field("text_to_video", description="Only text_to_video is supported")
    output_dir: str = Field(DEFAULT_OUTPUT_DIR, description="Local output directory")
    output_path: Optional[str] = Field(None, description="Exact local output path")
    aspect_ratio: str = Field("9:16", description="9:16, 16:9, or 1:1")
    width: Optional[int] = Field(None, description="Optional even request width")
    height: Optional[int] = Field(None, description="Optional even request height")
    num_frames: int = Field(41, description="Requested frame count")
    frame_rate: int = Field(24, description="Requested frames per second")
    preserve_native_audio: bool = Field(
        False,
        description="Keep provider audio; false removes it before returning the local file",
    )
    poll_interval: int = Field(5, description="Task polling interval in seconds")
    max_wait: int = Field(720, description="Maximum task wait in seconds")
    max_submit_retries: int = Field(1, description="Retries after provider rate limiting")
    rate_limit_retry_seconds: int = Field(60, description="Fallback delay after HTTP 429")


def build_agnes_video_payload(
    *,
    prompt: str,
    model: str = DEFAULT_AGNES_VIDEO_MODEL,
    aspect_ratio: str = "9:16",
    width: Optional[int] = None,
    height: Optional[int] = None,
    num_frames: int = 41,
    frame_rate: int = 24,
) -> dict[str, Any]:
    """Build the tested Agnes Video v2.0 text-to-video request."""

    if not prompt.strip():
        raise ValueError("prompt must not be empty")
    normalized_ratio = aspect_ratio.strip()
    if normalized_ratio not in AGNES_VIDEO_DIMENSIONS:
        raise ValueError(f"Unsupported Agnes video aspect_ratio: {aspect_ratio}")
    default_width, default_height = AGNES_VIDEO_DIMENSIONS[normalized_ratio]
    resolved_width = int(width if width is not None else default_width)
    resolved_height = int(height if height is not None else default_height)
    if resolved_width < 64 or resolved_height < 64 or resolved_width % 2 or resolved_height % 2:
        raise ValueError("width and height must be even integers of at least 64 pixels")
    if not 2 <= int(num_frames) <= 240:
        raise ValueError("num_frames must be between 2 and 240")
    if not 1 <= int(frame_rate) <= 60:
        raise ValueError("frame_rate must be between 1 and 60")
    return {
        "model": model,
        "prompt": prompt,
        "width": resolved_width,
        "height": resolved_height,
        "num_frames": int(num_frames),
        "frame_rate": int(frame_rate),
    }


def _find_first(payload: Any, keys: tuple[str, ...]) -> str:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                return str(value)
        for value in payload.values():
            found = _find_first(value, keys)
            if found:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _find_first(value, keys)
            if found:
                return found
    return ""


def _find_video_url(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("video_url", "output_url", "download_url", "url"):
            value = payload.get(key)
            if not isinstance(value, str) or not value.startswith(("https://", "http://")):
                continue
            path = urlparse(value).path.lower()
            if key != "url" or path.endswith((".mp4", ".mov", ".webm")):
                return value
        for value in payload.values():
            found = _find_video_url(value)
            if found:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _find_video_url(value)
            if found:
                return found
    return ""


def _response_error_code(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ""
    error = payload.get("error") if isinstance(payload, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    return str(code) if code not in {None, ""} else ""


def _retry_after_seconds(response: requests.Response, fallback: int) -> int:
    value = response.headers.get("Retry-After") if response.headers else None
    try:
        return max(1, int(float(value))) if value else max(1, fallback)
    except (TypeError, ValueError):
        return max(1, fallback)


def _submit_video(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: int,
    max_retries: int,
    retry_seconds: int,
) -> requests.Response:
    global _LAST_VIDEO_SUBMIT_AT

    minimum_interval = max(
        0.0,
        float(os.getenv("AGNES_VIDEO_MIN_SUBMIT_INTERVAL_SECONDS", "60")),
    )
    response: requests.Response | None = None
    for attempt in range(max(0, int(max_retries)) + 1):
        with _VIDEO_SUBMIT_LOCK:
            elapsed = time.monotonic() - _LAST_VIDEO_SUBMIT_AT
            if _LAST_VIDEO_SUBMIT_AT and elapsed < minimum_interval:
                time.sleep(minimum_interval - elapsed)
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            _LAST_VIDEO_SUBMIT_AT = time.monotonic()
        if response.status_code != 429 or attempt >= int(max_retries):
            return response
        time.sleep(_retry_after_seconds(response, retry_seconds))
    assert response is not None
    return response


def _download(url: str, destination: Path, *, timeout: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, stream=True, timeout=timeout)
    response.raise_for_status()
    with destination.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                handle.write(chunk)


def _strip_native_audio(path: Path) -> tuple[bool, str | None]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False, "ffmpeg is unavailable; provider audio was preserved"
    temporary = path.with_name(f".{path.stem}.video-only{path.suffix or '.mp4'}")
    completed = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-c:v",
            "copy",
            "-an",
            str(temporary),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not temporary.is_file():
        temporary.unlink(missing_ok=True)
        return False, "ffmpeg could not remove provider audio; provider audio was preserved"
    temporary.replace(path)
    return True, None


def _probe_video(path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {}
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height,avg_frame_rate,nb_frames",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return {}
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {}
    streams = payload.get("streams") if isinstance(payload, dict) else None
    streams = streams if isinstance(streams, list) else []
    video = next((item for item in streams if item.get("codec_type") == "video"), {})
    audio = any(item.get("codec_type") == "audio" for item in streams)
    format_data = payload.get("format") if isinstance(payload.get("format"), dict) else {}
    return {
        "actual_width": video.get("width"),
        "actual_height": video.get("height"),
        "actual_frame_rate": video.get("avg_frame_rate"),
        "actual_frames": video.get("nb_frames"),
        "actual_duration": format_data.get("duration"),
        "has_audio": audio,
    }


class AgnesVideoGeneratorTool(BaseTool):
    name: str = "Agnes Video v2.0 generator"
    description: str = "Generate an official Agnes text-to-video task and download it locally."
    args_schema: Type[BaseModel] = AgnesVideoSchema

    def _run(
        self,
        prompt: str,
        generation_type: str = "text_to_video",
        output_dir: str = DEFAULT_OUTPUT_DIR,
        output_path: Optional[str] = None,
        aspect_ratio: str = "9:16",
        width: Optional[int] = None,
        height: Optional[int] = None,
        num_frames: int = 41,
        frame_rate: int = 24,
        preserve_native_audio: bool = False,
        poll_interval: int = 5,
        max_wait: int = 720,
        max_submit_retries: int = 1,
        rate_limit_retry_seconds: int = 60,
        **_: Any,
    ) -> dict[str, Any]:
        api_key = os.getenv("AGNES_API_KEY")
        if not api_key:
            return {"success": False, "error": "Missing required env var: AGNES_API_KEY"}
        if generation_type != "text_to_video":
            return {
                "success": False,
                "error": "Agnes public video adapter supports text_to_video only",
            }

        model = os.getenv("AGNES_VIDEO_MODEL") or DEFAULT_AGNES_VIDEO_MODEL
        base_url = (os.getenv("AGNES_BASE_URL") or DEFAULT_AGNES_BASE_URL).rstrip("/")
        timeout = max(1, int(os.getenv("AGNES_TIMEOUT_SECONDS", "300")))
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        try:
            payload = build_agnes_video_payload(
                prompt=prompt,
                model=model,
                aspect_ratio=aspect_ratio,
                width=width,
                height=height,
                num_frames=num_frames,
                frame_rate=frame_rate,
            )
            created = _submit_video(
                url=f"{base_url}/v1/videos",
                headers=headers,
                payload=payload,
                timeout=timeout,
                max_retries=max_submit_retries,
                retry_seconds=rate_limit_retry_seconds,
            )
            if created.status_code >= 400:
                error_code = _response_error_code(created)
                suffix = f" ({error_code})" if error_code else ""
                return {
                    "success": False,
                    "error": f"Agnes video request failed: HTTP {created.status_code}{suffix}",
                    "provider_error_code": error_code or None,
                }

            result = created.json()
            video_id = _find_first(result, ("video_id", "task_id", "id"))
            video_url = _find_video_url(result)
            if not video_id and not video_url:
                return {"success": False, "error": "Agnes response did not contain a video task"}

            started = time.monotonic()
            last_status = "submitted"
            while not video_url and time.monotonic() - started <= max(1, int(max_wait)):
                status_response = requests.get(
                    f"{base_url}/agnesapi",
                    headers={"Authorization": f"Bearer {api_key}"},
                    params={"video_id": video_id},
                    timeout=timeout,
                )
                if status_response.status_code >= 400:
                    error_code = _response_error_code(status_response)
                    suffix = f" ({error_code})" if error_code else ""
                    return {
                        "success": False,
                        "error": f"Agnes video task query failed: HTTP {status_response.status_code}{suffix}",
                        "provider_error_code": error_code or None,
                    }
                result = status_response.json()
                last_status = _find_first(result, ("status", "state", "task_status")) or "unknown"
                if last_status.lower() in {"failed", "error", "cancelled", "canceled", "rejected"}:
                    return {
                        "success": False,
                        "error": f"Agnes video task ended with status {last_status}",
                    }
                video_url = _find_video_url(result)
                if not video_url:
                    time.sleep(max(1, int(poll_interval)))
            if not video_url:
                return {
                    "success": False,
                    "error": f"Agnes video task timed out with status {last_status}",
                }

            resolved_dir = resolve_video_output_dir(output_dir, output_path, DEFAULT_OUTPUT_DIR, ())
            destination = (
                Path(output_path).expanduser()
                if output_path
                else Path(resolved_dir) / f"agnes_{int(time.time())}.mp4"
            )
            _download(video_url, destination, timeout=timeout)
            native_audio_removed = False
            warning = None
            if not preserve_native_audio:
                native_audio_removed, warning = _strip_native_audio(destination)
            metadata = _probe_video(destination)
            response_payload: dict[str, Any] = {
                "success": True,
                "provider": "agnes_official",
                "model": result.get("model") or model,
                "output_path": str(destination),
                "generation_type": "text_to_video",
                "requested_width": payload["width"],
                "requested_height": payload["height"],
                "requested_frames": payload["num_frames"],
                "requested_frame_rate": payload["frame_rate"],
                "preserve_native_audio": bool(preserve_native_audio),
                "native_audio_removed": native_audio_removed,
                **metadata,
            }
            if warning:
                response_payload["warning"] = warning
            return response_payload
        except ValueError as exc:
            return {"success": False, "error": f"Agnes video validation error: {exc}"}
        except (requests.RequestException, OSError) as exc:
            return {"success": False, "error": f"Agnes video error: {exc.__class__.__name__}"}


__all__ = [
    "AgnesVideoGeneratorTool",
    "AgnesVideoSchema",
    "build_agnes_video_payload",
]
