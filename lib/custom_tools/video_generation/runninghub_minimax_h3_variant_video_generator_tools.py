"""RunningHub MiniMax H3 multi-image and text-to-video workflow adapters.

The three RunningHub MiniMax H3 FL2VA apps are separate workflows with
different node contracts.  This module contains the two additional contracts;
the first/last-frame workflow remains in
``runninghub_minimax_h3_video_generator_tool.py``.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional, Type

import requests
from pydantic import BaseModel, Field

from custom_tools.audio_generation.base_tool_compat import BaseTool
from src.utils.output_paths import require_under_output

from .output_dir_utils import default_video_output_dir, resolve_video_output_dir
from .runninghub_minimax_h3_video_generator_tool import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_WAIT_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    RunningHubMiniMaxH3VideoGeneratorTool,
    _result_video,
    _safe_error,
)


MULTI_IMAGE_APP_ID = "2084192196529582081"
TEXT_TO_VIDEO_APP_ID = "2084109189609246721"
RATIO_OPTIONS = ["auto", "21:9", "16:9", "4:3", "1:1", "3:4", "9:16"]
MULTI_RATIO_FIELD_DATA = json.dumps([RATIO_OPTIONS, {"default": "auto"}], ensure_ascii=False, separators=(",", ":"))
TEXT_RATIO_FIELD_DATA = json.dumps([RATIO_OPTIONS, {"default": "16:9"}], ensure_ascii=False, separators=(",", ":"))


class RunningHubMiniMaxH3MultiReferenceVideoSchema(BaseModel):
    image_paths: list[str] = Field(..., min_length=1, max_length=3, description="1-3 张参考图片")
    prompt: str = Field(..., description="参考图片内容和视频运动提示词")
    output_dir: str = Field(default_video_output_dir("runninghub_minimax_h3_multi"), description="默认输出目录")
    output_path: Optional[str] = Field(None, description="精确的本地 MP4 输出路径")
    aspect_ratio: str = Field("16:9", description="auto、21:9、16:9、4:3、1:1、3:4 或 9:16")
    width: int = Field(832, description="工作流宽度参数")
    height: int = Field(480, description="工作流高度参数")
    duration_seconds: int = Field(10, description="生成时长；文档示例为 10 秒")
    instance_type: str = Field("default", description="default（24G）或 plus（48G）")
    use_personal_queue: bool = Field(False, description="是否使用个人独占队列")
    retain_seconds: Optional[int] = Field(None, description="企业共享 Key 的实例保留秒数，10-180")
    webhook_url: Optional[str] = Field(None, description="可选的完成回调 URL")
    poll_interval: int = Field(10, description="查询间隔秒数")
    max_wait: int = Field(DEFAULT_MAX_WAIT_SECONDS, description="最长等待秒数")


class RunningHubMiniMaxH3TextToVideoSchema(BaseModel):
    prompt: str = Field(..., description="文生视频提示词")
    output_dir: str = Field(default_video_output_dir("runninghub_minimax_h3_text"), description="默认输出目录")
    output_path: Optional[str] = Field(None, description="精确的本地 MP4 输出路径")
    aspect_ratio: str = Field("16:9", description="auto、21:9、16:9、4:3、1:1、3:4 或 9:16")
    width: int = Field(832, description="工作流宽度参数")
    height: int = Field(480, description="工作流高度参数")
    duration_seconds: int = Field(5, description="生成时长；文档示例为 5 秒")
    instance_type: str = Field("default", description="default（24G）或 plus（48G）")
    use_personal_queue: bool = Field(False, description="是否使用个人独占队列")
    retain_seconds: Optional[int] = Field(None, description="企业共享 Key 的实例保留秒数，10-180")
    webhook_url: Optional[str] = Field(None, description="可选的完成回调 URL")
    poll_interval: int = Field(10, description="查询间隔秒数")
    max_wait: int = Field(DEFAULT_MAX_WAIT_SECONDS, description="最长等待秒数")


def _validate_common(
    *,
    prompt: str,
    aspect_ratio: str,
    width: int,
    height: int,
    duration_seconds: int,
    instance_type: str,
    retain_seconds: Optional[int],
    poll_interval: int,
    max_wait: int,
) -> tuple[str, str, int, int, int]:
    prompt = str(prompt).strip()
    if not prompt:
        raise ValueError("prompt must not be empty")
    aspect_ratio = str(aspect_ratio).strip()
    if aspect_ratio not in RATIO_OPTIONS:
        raise ValueError(f"Unsupported RunningHub aspect_ratio: {aspect_ratio}")
    width, height, duration_seconds = int(width), int(height), int(duration_seconds)
    if width < 64 or height < 64 or width % 2 or height % 2:
        raise ValueError("width and height must be even integers of at least 64 pixels")
    if duration_seconds < 1 or duration_seconds > 60:
        raise ValueError("duration_seconds must be between 1 and 60")
    if instance_type not in {"default", "plus"}:
        raise ValueError("instance_type must be default or plus")
    if retain_seconds is not None and not 10 <= int(retain_seconds) <= 180:
        raise ValueError("retain_seconds must be between 10 and 180")
    if int(poll_interval) < 1 or int(max_wait) < 1:
        raise ValueError("poll_interval and max_wait must be positive")
    return prompt, aspect_ratio, width, height, duration_seconds


def _run_app(
    *,
    app_id: str,
    node_info: list[dict[str, Any]],
    output_dir: str,
    output_path: Optional[str],
    duration_seconds: int,
    ratio: str,
    instance_type: str,
    use_personal_queue: bool,
    retain_seconds: Optional[int],
    webhook_url: Optional[str],
    poll_interval: int,
    max_wait: int,
    output_prefix: str,
) -> dict[str, Any]:
    api_key = os.getenv("RUNNINGHUB_API_KEY")
    if not api_key:
        return {"success": False, "error": "Missing required env var: RUNNINGHUB_API_KEY"}
    base_url = (os.getenv("RUNNINGHUB_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    try:
        timeout = max(1, int(os.getenv("RUNNINGHUB_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))))
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
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
            f"{base_url}/openapi/v2/run/ai-app/{app_id}",
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        if submitted.status_code >= 400:
            return {"success": False, "error": f"RunningHub submit failed: HTTP {submitted.status_code}", "provider_error": _safe_error(submitted)}
        submitted_payload = submitted.json()
        task_id = str(submitted_payload.get("taskId") or "") if isinstance(submitted_payload, dict) else ""
        if not task_id:
            return {"success": False, "error": "RunningHub response did not contain taskId"}

        started = time.monotonic()
        status = ""
        video_url = ""
        output_type = ""
        while time.monotonic() - started <= int(max_wait):
            queried = requests.post(
                f"{base_url}/openapi/v2/query",
                json={"taskId": task_id},
                headers=headers,
                timeout=timeout,
            )
            if queried.status_code >= 400:
                return {"success": False, "error": f"RunningHub query failed: HTTP {queried.status_code}", "provider_error": _safe_error(queried), "task_id": task_id}
            queried_payload = queried.json()
            data = queried_payload if isinstance(queried_payload, dict) else {}
            status = str(data.get("status") or "").upper()
            video_url, output_type = _result_video(data.get("results"))
            if status == "SUCCESS":
                break
            if status in {"FAILED", "FAIL", "ERROR", "CANCELED", "CANCELLED"}:
                return {"success": False, "error": f"RunningHub task ended with status {status}", "provider_error": str(data.get("errorMessage") or data.get("failedReason") or "")[:300], "task_id": task_id}
            time.sleep(int(poll_interval))

        if status != "SUCCESS" or not video_url:
            return {"success": False, "error": f"RunningHub task timed out or returned no video (status={status or 'unknown'})", "task_id": task_id}

        resolved_dir = resolve_video_output_dir(output_dir, output_path, output_dir, ())
        destination = Path(output_path).expanduser() if output_path else Path(resolved_dir) / f"{output_prefix}_{task_id}.mp4"
        destination = Path(require_under_output(destination, "output_path"))
        RunningHubMiniMaxH3VideoGeneratorTool._download(video_url, destination, timeout)
        media = RunningHubMiniMaxH3VideoGeneratorTool._probe(destination)
        return {
            "success": True,
            "provider": "runninghub",
            "workflow": app_id,
            "task_id": task_id,
            "status": status,
            "output_path": str(destination),
            "output_type": output_type or "mp4",
            "duration_seconds": duration_seconds,
            "aspect_ratio": ratio,
            "media": media,
        }
    except ValueError as exc:
        return {"success": False, "error": f"RunningHub MiniMax H3 validation error: {exc}"}
    except (requests.RequestException, OSError, TypeError, KeyError) as exc:
        return {"success": False, "error": f"RunningHub MiniMax H3 error: {exc.__class__.__name__}"}


class RunningHubMiniMaxH3MultiReferenceVideoGeneratorTool(BaseTool):
    name: str = "RunningHub MiniMax H3 多图参考视频生成器"
    description: str = "通过 RunningHub AI App 2084192196529582081 使用最多 3 张参考图生成 MiniMax H3 FL2VA 视频。"
    args_schema: Type[BaseModel] = RunningHubMiniMaxH3MultiReferenceVideoSchema

    def _run(
        self,
        image_paths: list[str],
        prompt: str,
        output_dir: str = default_video_output_dir("runninghub_minimax_h3_multi"),
        output_path: Optional[str] = None,
        aspect_ratio: str = "16:9",
        width: int = 832,
        height: int = 480,
        duration_seconds: int = 10,
        instance_type: str = "default",
        use_personal_queue: bool = False,
        retain_seconds: Optional[int] = None,
        webhook_url: Optional[str] = None,
        poll_interval: int = 10,
        max_wait: int = DEFAULT_MAX_WAIT_SECONDS,
    ) -> dict[str, Any]:
        try:
            if not os.getenv("RUNNINGHUB_API_KEY"):
                return {"success": False, "error": "Missing required env var: RUNNINGHUB_API_KEY"}
            image_paths = list(image_paths or [])
            if not 1 <= len(image_paths) <= 3:
                raise ValueError("image_paths must contain between 1 and 3 images")
            prompt, aspect_ratio, width, height, duration_seconds = _validate_common(
                prompt=prompt, aspect_ratio=aspect_ratio, width=width, height=height,
                duration_seconds=duration_seconds, instance_type=instance_type,
                retain_seconds=retain_seconds, poll_interval=poll_interval, max_wait=max_wait,
            )
            client = RunningHubMiniMaxH3VideoGeneratorTool()
            node_info = []
            upload_base_url = (os.getenv("RUNNINGHUB_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
            upload_headers = {"Authorization": f"Bearer {os.environ['RUNNINGHUB_API_KEY']}"}
            upload_timeout = max(1, int(os.getenv("RUNNINGHUB_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))))
            for node_id, image_path, description in zip(("4", "19", "20"), image_paths, ("上传图像1", "上传图像2", "上传图像3")):
                reference = client._prepare_media(
                    str(image_path).strip(), upload_base_url, upload_headers, upload_timeout
                )
                node_info.append(
                    {"nodeId": node_id, "fieldName": "image", "fieldValue": reference, "description": description}
                )
            node_info.extend([
                {"nodeId": "6", "fieldName": "aspect_ratio", "fieldData": MULTI_RATIO_FIELD_DATA, "fieldValue": aspect_ratio, "description": "设置比例"},
                {"nodeId": "6", "fieldName": "duration_seconds", "fieldValue": str(duration_seconds), "description": "时长（秒）"},
                {"nodeId": "6", "fieldName": "height", "fieldValue": str(height), "description": "高度"},
                {"nodeId": "6", "fieldName": "width", "fieldValue": str(width), "description": "宽度"},
                {"nodeId": "7", "fieldName": "prompt", "fieldValue": prompt, "description": "输入文本"},
            ])
            return _run_app(
                app_id=MULTI_IMAGE_APP_ID, node_info=node_info, output_dir=output_dir,
                output_path=output_path, duration_seconds=duration_seconds, ratio=aspect_ratio,
                instance_type=instance_type, use_personal_queue=use_personal_queue,
                retain_seconds=retain_seconds, webhook_url=webhook_url,
                poll_interval=poll_interval, max_wait=max_wait,
                output_prefix="runninghub_minimax_h3_multi",
            )
        except ValueError as exc:
            return {"success": False, "error": f"RunningHub MiniMax H3 validation error: {exc}"}
        except (requests.RequestException, OSError, TypeError, KeyError) as exc:
            return {"success": False, "error": f"RunningHub MiniMax H3 error: {exc.__class__.__name__}"}


class RunningHubMiniMaxH3TextToVideoGeneratorTool(BaseTool):
    name: str = "RunningHub MiniMax H3 文生视频生成器"
    description: str = "通过 RunningHub AI App 2084109189609246721 使用文本生成 MiniMax H3 FL2VA 视频。"
    args_schema: Type[BaseModel] = RunningHubMiniMaxH3TextToVideoSchema

    def _run(
        self,
        prompt: str,
        output_dir: str = default_video_output_dir("runninghub_minimax_h3_text"),
        output_path: Optional[str] = None,
        aspect_ratio: str = "16:9",
        width: int = 832,
        height: int = 480,
        duration_seconds: int = 5,
        instance_type: str = "default",
        use_personal_queue: bool = False,
        retain_seconds: Optional[int] = None,
        webhook_url: Optional[str] = None,
        poll_interval: int = 10,
        max_wait: int = DEFAULT_MAX_WAIT_SECONDS,
    ) -> dict[str, Any]:
        try:
            prompt, aspect_ratio, width, height, duration_seconds = _validate_common(
                prompt=prompt, aspect_ratio=aspect_ratio, width=width, height=height,
                duration_seconds=duration_seconds, instance_type=instance_type,
                retain_seconds=retain_seconds, poll_interval=poll_interval, max_wait=max_wait,
            )
            node_info = [
                {"nodeId": "4", "fieldName": "aspect_ratio", "fieldData": TEXT_RATIO_FIELD_DATA, "fieldValue": aspect_ratio, "description": "设置比例"},
                {"nodeId": "4", "fieldName": "width", "fieldValue": str(width), "description": "宽度"},
                {"nodeId": "4", "fieldName": "height", "fieldValue": str(height), "description": "高度"},
                {"nodeId": "4", "fieldName": "duration_seconds", "fieldValue": str(duration_seconds), "description": "时长（秒）"},
                {"nodeId": "5", "fieldName": "prompt", "fieldValue": prompt, "description": "输入文本"},
            ]
            return _run_app(
                app_id=TEXT_TO_VIDEO_APP_ID, node_info=node_info, output_dir=output_dir,
                output_path=output_path, duration_seconds=duration_seconds, ratio=aspect_ratio,
                instance_type=instance_type, use_personal_queue=use_personal_queue,
                retain_seconds=retain_seconds, webhook_url=webhook_url,
                poll_interval=poll_interval, max_wait=max_wait,
                output_prefix="runninghub_minimax_h3_text",
            )
        except ValueError as exc:
            return {"success": False, "error": f"RunningHub MiniMax H3 validation error: {exc}"}
        except (requests.RequestException, OSError, TypeError, KeyError) as exc:
            return {"success": False, "error": f"RunningHub MiniMax H3 error: {exc.__class__.__name__}"}


__all__ = [
    "RunningHubMiniMaxH3MultiReferenceVideoGeneratorTool",
    "RunningHubMiniMaxH3MultiReferenceVideoSchema",
    "RunningHubMiniMaxH3TextToVideoGeneratorTool",
    "RunningHubMiniMaxH3TextToVideoSchema",
]
