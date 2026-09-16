"""RunningHub MiniMax H3 FL2VA first/last-frame video adapter.

This is intentionally separate from the official MiniMax H3 V2 adapter.  The
RunningHub workflow is a public AI App whose node contract is:

* node 6 / ``image``: first frame
* node 4 / ``image``: last frame
* node 7 / ``duration_seconds``: duration
* node 24 / ``select``: aspect-ratio option (the published example uses ``3``)
* node 8 / ``prompt``: motion prompt

RunningHub result URLs expire after 24 hours, so this tool always downloads the
result before returning and never includes the remote URL in its result.
"""

from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Optional, Type

import requests
from pydantic import BaseModel, Field

from custom_tools.audio_generation.base_tool_compat import BaseTool
from src.utils.output_paths import require_under_output
from .output_dir_utils import default_video_output_dir, resolve_video_output_dir


DEFAULT_BASE_URL = "https://www.runninghub.cn"
DEFAULT_APP_ID = "2084086089706459137"
DEFAULT_OUTPUT_DIR = default_video_output_dir("runninghub_minimax_h3")
DEFAULT_RATIO_SELECT = "3"
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_MAX_WAIT_SECONDS = 1800
TERMINAL_FAILURE_STATES = {"FAILED", "FAIL", "ERROR", "CANCELED", "CANCELLED"}


class RunningHubMiniMaxH3VideoSchema(BaseModel):
    first_frame_path: str = Field(..., description="首帧图片的本地路径、公开 URL 或 data URI")
    last_frame_path: str = Field(..., description="尾帧图片的本地路径、公开 URL 或 data URI")
    prompt: str = Field(..., description="描述 0-5 秒运动和镜头的提示词")
    output_dir: str = Field(DEFAULT_OUTPUT_DIR, description="默认输出目录")
    output_path: Optional[str] = Field(None, description="精确的本地 MP4 输出路径")
    duration_seconds: int = Field(5, description="生成时长；工作流示例为 5 秒")
    ratio_select: str = Field(
        DEFAULT_RATIO_SELECT,
        description="RunningHub 节点 24 的 select 值；公开示例使用 3（工作流标称 832×480，实际尺寸以输出为准）",
    )
    instance_type: str = Field("default", description="default（24G）或 plus（48G）")
    use_personal_queue: bool = Field(False, description="是否使用个人独占队列")
    retain_seconds: Optional[int] = Field(None, description="企业共享 Key 的实例保留秒数，10-180")
    webhook_url: Optional[str] = Field(None, description="可选的完成回调 URL")
    poll_interval: int = Field(10, description="查询间隔秒数")
    max_wait: int = Field(DEFAULT_MAX_WAIT_SECONDS, description="最长等待秒数")


def _is_remote_or_data(value: str) -> bool:
    return value.startswith(("https://", "http://", "data:"))


def _safe_error(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:300]
    if isinstance(payload, dict):
        return str(payload.get("errorMessage") or payload.get("message") or payload.get("msg") or payload)[:300]
    return str(payload)[:300]


def _result_video(results: Any) -> tuple[str, str]:
    """Return (url, output_type) from a RunningHub results list."""
    if not isinstance(results, list):
        return "", ""
    for item in results:
        if not isinstance(item, dict):
            continue
        url = item.get("url") or item.get("download_url") or item.get("fileUrl")
        output_type = str(item.get("outputType") or item.get("output_type") or "").lower()
        if isinstance(url, str) and url.startswith(("https://", "http://")):
            if output_type in {"", "mp4", "mov", "webm"} or url.lower().split("?", 1)[0].endswith((".mp4", ".mov", ".webm")):
                return url, output_type or "mp4"
    return "", ""


class RunningHubMiniMaxH3VideoGeneratorTool(BaseTool):
    name: str = "RunningHub MiniMax H3 首尾帧视频生成器"
    description: str = (
        "通过 RunningHub AI App 2084086089706459137 调用 MiniMax H3 FL2VA，"
        "使用首帧和尾帧参考生成工作流标称 832×480、默认 5 秒视频，并下载到本地；实际尺寸以 ffprobe 为准。"
    )
    args_schema: Type[BaseModel] = RunningHubMiniMaxH3VideoSchema

    def _run(
        self,
        first_frame_path: str,
        last_frame_path: str,
        prompt: str,
        output_dir: str = DEFAULT_OUTPUT_DIR,
        output_path: Optional[str] = None,
        duration_seconds: int = 5,
        ratio_select: str = DEFAULT_RATIO_SELECT,
        instance_type: str = "default",
        use_personal_queue: bool = False,
        retain_seconds: Optional[int] = None,
        webhook_url: Optional[str] = None,
        poll_interval: int = 10,
        max_wait: int = DEFAULT_MAX_WAIT_SECONDS,
    ) -> dict[str, Any]:
        api_key = os.getenv("RUNNINGHUB_API_KEY")
        if not api_key:
            return {"success": False, "error": "Missing required env var: RUNNINGHUB_API_KEY"}

        try:
            first_frame_path, last_frame_path = str(first_frame_path).strip(), str(last_frame_path).strip()
            prompt = str(prompt).strip()
            if not first_frame_path or not last_frame_path:
                raise ValueError("first_frame_path and last_frame_path are required")
            if not prompt:
                raise ValueError("prompt must not be empty")
            duration = int(duration_seconds)
            if duration < 1 or duration > 60:
                raise ValueError("duration_seconds must be between 1 and 60")
            if instance_type not in {"default", "plus"}:
                raise ValueError("instance_type must be default or plus")
            if retain_seconds is not None and not 10 <= int(retain_seconds) <= 180:
                raise ValueError("retain_seconds must be between 10 and 180")
            if int(poll_interval) < 1 or int(max_wait) < 1:
                raise ValueError("poll_interval and max_wait must be positive")

            base_url = (os.getenv("RUNNINGHUB_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
            timeout = max(1, int(os.getenv("RUNNINGHUB_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))))
            headers = {"Authorization": f"Bearer {api_key}"}

            first_ref = self._prepare_media(first_frame_path, base_url, headers, timeout)
            last_ref = self._prepare_media(last_frame_path, base_url, headers, timeout)

            node_info = [
                {"nodeId": "6", "fieldName": "image", "fieldValue": first_ref, "description": "上传首帧"},
                {"nodeId": "4", "fieldName": "image", "fieldValue": last_ref, "description": "上传尾帧"},
                {"nodeId": "7", "fieldName": "duration_seconds", "fieldValue": str(duration), "description": "时长（秒）"},
                {"nodeId": "24", "fieldName": "select", "fieldValue": str(ratio_select), "description": "设置比例"},
                {"nodeId": "8", "fieldName": "prompt", "fieldValue": prompt, "description": "输入文本"},
            ]
            payload: dict[str, Any] = {
                "nodeInfoList": node_info,
                "instanceType": instance_type,
                "usePersonalQueue": bool(use_personal_queue),
            }
            if retain_seconds is not None:
                payload["retainSeconds"] = int(retain_seconds)
            if webhook_url:
                payload["webhookUrl"] = webhook_url

            submitted = requests.post(
                f"{base_url}/openapi/v2/run/ai-app/{DEFAULT_APP_ID}",
                json=payload,
                headers={**headers, "Content-Type": "application/json"},
                timeout=timeout,
            )
            if submitted.status_code >= 400:
                return {"success": False, "error": f"RunningHub submit failed: HTTP {submitted.status_code}", "provider_error": _safe_error(submitted)}
            submitted_payload = submitted.json()
            task_id = str(submitted_payload.get("taskId") or "") if isinstance(submitted_payload, dict) else ""
            if not task_id:
                return {"success": False, "error": "RunningHub response did not contain taskId"}

            started = time.monotonic()
            task: dict[str, Any] = {}
            status = ""
            video_url = ""
            output_type = ""
            while time.monotonic() - started <= int(max_wait):
                queried = requests.post(
                    f"{base_url}/openapi/v2/query",
                    json={"taskId": task_id},
                    headers={**headers, "Content-Type": "application/json"},
                    timeout=timeout,
                )
                if queried.status_code >= 400:
                    return {"success": False, "error": f"RunningHub query failed: HTTP {queried.status_code}", "provider_error": _safe_error(queried), "task_id": task_id}
                queried_payload = queried.json()
                task = queried_payload if isinstance(queried_payload, dict) else {}
                status = str(task.get("status") or "").upper()
                video_url, output_type = _result_video(task.get("results"))
                if status == "SUCCESS":
                    break
                if status in TERMINAL_FAILURE_STATES:
                    return {"success": False, "error": f"RunningHub task ended with status {status}", "provider_error": str(task.get("errorMessage") or task.get("failedReason") or "")[:300], "task_id": task_id}
                time.sleep(int(poll_interval))

            if status != "SUCCESS" or not video_url:
                return {"success": False, "error": f"RunningHub task timed out or returned no video (status={status or 'unknown'})", "task_id": task_id}

            resolved_dir = resolve_video_output_dir(output_dir, output_path, DEFAULT_OUTPUT_DIR, ())
            destination = Path(output_path).expanduser() if output_path else Path(resolved_dir) / f"runninghub_minimax_h3_{task_id}.mp4"
            destination = Path(require_under_output(destination, "output_path"))
            self._download(video_url, destination, timeout)
            media = self._probe(destination)
            return {
                "success": True,
                "provider": "runninghub",
                "workflow": DEFAULT_APP_ID,
                "task_id": task_id,
                "status": status,
                "output_path": str(destination),
                "output_type": output_type or "mp4",
                "duration_seconds": duration,
                "ratio_select": str(ratio_select),
                "media": media,
            }
        except ValueError as exc:
            return {"success": False, "error": f"RunningHub MiniMax H3 validation error: {exc}"}
        except (requests.RequestException, OSError, TypeError, KeyError) as exc:
            return {"success": False, "error": f"RunningHub MiniMax H3 error: {exc.__class__.__name__}"}

    @staticmethod
    def _prepare_media(value: str, base_url: str, headers: dict[str, str], timeout: int) -> str:
        if _is_remote_or_data(value):
            return value
        path = Path(value).expanduser()
        if not path.is_file():
            raise ValueError(f"media file does not exist: {value}")
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with path.open("rb") as handle:
            response = requests.post(
                f"{base_url}/openapi/v2/media/upload/binary",
                files={"file": (path.name, handle, mime)},
                headers={"Authorization": headers["Authorization"]},
                timeout=timeout,
            )
        if response.status_code >= 400:
            raise requests.HTTPError(f"upload HTTP {response.status_code}: {_safe_error(response)}")
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise ValueError("RunningHub upload response did not contain data")
        reference = data.get("download_url") or data.get("fileName")
        if not isinstance(reference, str) or not reference.strip():
            raise ValueError("RunningHub upload response did not contain a file reference")
        return reference

    @staticmethod
    def _download(url: str, destination: Path, timeout: int) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(url, stream=True, timeout=timeout)
        response.raise_for_status()
        with destination.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)

    @staticmethod
    def _probe(path: Path) -> dict[str, Any]:
        """Best-effort local media probe; provider output remains authoritative."""
        try:
            completed = subprocess.run(
                [
                    "ffprobe", "-v", "error", "-show_entries",
                    "format=duration:stream=codec_type,width,height",
                    "-of", "json", str(path),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            payload = json.loads(completed.stdout)
            streams = payload.get("streams") or []
            video = next((item for item in streams if item.get("codec_type") == "video"), {})
            return {
                "width": video.get("width"),
                "height": video.get("height"),
                "duration_seconds": float((payload.get("format") or {}).get("duration")),
                "has_audio": any(item.get("codec_type") == "audio" for item in streams),
            }
        except (OSError, ValueError, TypeError, subprocess.SubprocessError):
            return {}


RunningHubMiniMaxH3FirstLastFrameVideoGeneratorTool = RunningHubMiniMaxH3VideoGeneratorTool

__all__ = [
    "RunningHubMiniMaxH3VideoGeneratorTool",
    "RunningHubMiniMaxH3FirstLastFrameVideoGeneratorTool",
    "RunningHubMiniMaxH3VideoSchema",
]
