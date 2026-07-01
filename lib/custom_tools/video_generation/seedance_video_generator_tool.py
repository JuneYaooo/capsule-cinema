"""Seedance video generator (CrewAI tool).

Seedance 1.0 与 jimeng35pro 共享同一组 OpenAI-compatible video REST API
（POST /v1/videos 创建任务，GET /v1/videos/{task_id} 轮询），差异只在
``model`` 字段和选档。

通过 ``seedance_tier`` 参数或环境变量 ``SEEDANCE_TIER`` 选档；
通过环境变量 ``SEEDANCE_DEFAULT_DURATION`` 可以切换默认时长 ("5s"/"10s")。
Seedance 2.0 通过 ``Seedance20VideoGeneratorTool`` 暴露，走公开 Ark
``/contents/generations/tasks`` 接口；凭证只从 ``ARK_API_KEY`` 读取。
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Type, Union

import requests
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from src.logger import get_logger
from .jimeng35pro_video_generator_tool import Jimeng35ProVideoClient
from .output_dir_utils import default_video_output_dir, resolve_video_output_dir

logger = get_logger("seedance_video_generator")

DEFAULT_SEEDANCE_OUTPUT_DIR = default_video_output_dir("seedance")
LEGACY_SEEDANCE_OUTPUT_DIRS = ("seedance_videos",)
ARK_SEEDANCE20_DEFAULT_BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3"


def expected_aspect_ratio_value(aspect_ratio: str) -> Optional[float]:
    if not aspect_ratio or ":" not in aspect_ratio:
        return None
    try:
        width, height = aspect_ratio.split(":", 1)
        return float(width) / float(height)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def probe_video_dimensions(video_path: str) -> tuple[int, int]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0",
            video_path,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    width_text, height_text = result.stdout.strip().split(",", 1)
    return int(width_text), int(height_text)


def validate_video_aspect_ratio(
    video_path: str,
    aspect_ratio: str,
    tolerance: float = 0.03,
) -> None:
    expected = expected_aspect_ratio_value(aspect_ratio)
    if expected is None:
        return

    width, height = probe_video_dimensions(video_path)
    if not width or not height:
        raise ValueError(f"视频尺寸无效，无法校验比例: {video_path}")

    actual = width / height
    if abs(actual - expected) > tolerance:
        raise ValueError(
            f"视频实际输出比例不符合 {aspect_ratio}: "
            f"实际尺寸 {width}x{height}，实际比例 {actual:.4f}"
        )


class _SeedanceClient(Jimeng35ProVideoClient):
    """复用 jimeng 客户端，只覆盖模型名映射。

    通过环境变量 ``SEEDANCE_TIER`` 选档：
      - ``pro``  (默认): seedance-1.0-pro / seedance-1.0-pro-10s    画质最好
      - ``fast``        : seedance-1.0-fast / seedance-1.0-fast-10s  快速档
      - ``mini``        : seedance-1.0-mini / seedance-1.0-mini-10s  最便宜
    """

    _TIER_MAP = {
        "pro": {
            "5s": "seedance-1.0-pro",
            "10s": "seedance-1.0-pro-10s",
        },
        "fast": {
            "5s": "seedance-1.0-fast",
            "10s": "seedance-1.0-fast-10s",
        },
        "mini": {
            "5s": "seedance-1.0-mini",
            "10s": "seedance-1.0-mini-10s",
        },
    }

    def __init__(
        self,
        api_key=None,
        base_url=None,
        output_dir: str = DEFAULT_SEEDANCE_OUTPUT_DIR,
        *,
        tier: Optional[str] = None,
        **kwargs,
        ):
        output_dir = resolve_video_output_dir(
            output_dir,
            None,
            DEFAULT_SEEDANCE_OUTPUT_DIR,
            LEGACY_SEEDANCE_OUTPUT_DIRS,
        )
        super().__init__(api_key=api_key, base_url=base_url, output_dir=output_dir, **kwargs)
        tier = (tier or os.getenv("SEEDANCE_TIER") or "pro").lower()
        self.DURATION_TO_MODEL = self._TIER_MAP.get(tier, self._TIER_MAP["pro"])


class SeedanceVideoGeneratorSchema(BaseModel):
    prompt: str = Field(..., description="视频生成提示词")
    generation_type: str = Field(
        "text_to_video",
        description="text_to_video 或 image_to_video",
    )
    output_dir: str = Field(default=DEFAULT_SEEDANCE_OUTPUT_DIR, description="保存目录")
    output_path: Optional[str] = Field(default=None, description="完整输出路径，优先于 output_dir")
    image_path: Optional[str] = Field(default=None, description="图生视频时的输入图")
    aspect_ratio: str = Field(default="9:16", description="宽高比 9:16 / 16:9 / 1:1")
    size: str = Field(default="720P", description="分辨率 720P / 1080P")
    duration: str = Field(default="5s", description="时长 5s / 10s")


class SeedanceVideoGeneratorTool(BaseTool):
    """Seedance 1.0 视频生成工具。"""

    name: str = "Seedance视频生成工具"
    description: str = (
        "使用 Seedance 1.0 模型生成视频；支持 pro / fast / mini 档，"
        "与 jimeng35pro 共享 REST API，差别在 model 名。"
    )
    args_schema: Type[BaseModel] = SeedanceVideoGeneratorSchema

    def _run(
        self,
        prompt: str,
        generation_type: str = "text_to_video",
        output_dir: str = DEFAULT_SEEDANCE_OUTPUT_DIR,
        output_path: Optional[str] = None,
        image_path: Optional[str] = None,
        aspect_ratio: str = "9:16",
        size: str = "720P",
        duration: Optional[str] = None,
        seedance_tier: Optional[str] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        engine_name = f"seedance-{seedance_tier}" if seedance_tier else "seedance"
        if generation_type not in ("text_to_video", "image_to_video"):
            return {
                "error": f"seedance 不支持 generation_type={generation_type}",
                "engine": engine_name,
            }
        if generation_type == "image_to_video" and not image_path:
            return {"error": "image_to_video 需要 image_path", "engine": engine_name}

        duration = duration or os.getenv("SEEDANCE_DEFAULT_DURATION", "5s")
        client_output_dir = resolve_video_output_dir(
            output_dir,
            output_path,
            DEFAULT_SEEDANCE_OUTPUT_DIR,
            LEGACY_SEEDANCE_OUTPUT_DIRS,
        )

        try:
            client = _SeedanceClient(output_dir=client_output_dir, tier=seedance_tier)
            kwargs: Dict[str, Any] = {
                "prompt": prompt,
                "duration": duration,
                "aspect_ratio": aspect_ratio,
                "size": size,
                "auto_download": True,
            }
            if output_path:
                kwargs["output_path"] = output_path

            if generation_type == "text_to_video":
                result = client.text_to_video(**kwargs)
            else:
                result = client.image_to_video(image=image_path, **kwargs)

            generated_path = result.get("output_path")
            if generated_path:
                validate_video_aspect_ratio(generated_path, aspect_ratio)

            return {
                "engine": engine_name,
                "generation_type": generation_type,
                "result": result,
                "output_path": result.get("output_path"),
            }
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Seedance 视频生成失败: {exc}")
            return {"error": str(exc), "engine": engine_name}


class SeedanceFastVideoGeneratorTool(SeedanceVideoGeneratorTool):
    """Seedance 1.0 Fast 视频生成工具别名。"""

    name: str = "Seedance Fast视频生成工具"
    description: str = (
        "使用 Seedance 1.0 Fast 模型生成视频；与 SeedanceVideoGeneratorTool 相同，"
        "但固定 seedance_tier=fast。"
    )

    def _run(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        kwargs["seedance_tier"] = "fast"
        return super()._run(*args, **kwargs)


def _duration_to_seconds(duration: Any) -> int:
    if duration is None:
        duration = os.getenv("SEEDANCE20_DEFAULT_DURATION", os.getenv("SEEDANCE_DEFAULT_DURATION", "5s"))
    if isinstance(duration, (int, float)):
        seconds = int(round(float(duration)))
    else:
        text = str(duration).strip().lower()
        if text.endswith("seconds"):
            text = text[:-7]
        if text.endswith("second"):
            text = text[:-6]
        if text.endswith("s"):
            text = text[:-1]
        seconds = int(round(float(text)))
    if seconds <= 0:
        raise ValueError(f"duration must be positive, got {duration!r}")
    return seconds


def _coerce_media_list(value: Any) -> List[Union[str, Path]]:
    if not value:
        return []
    if isinstance(value, (str, Path)):
        return [value]
    if isinstance(value, Iterable):
        return [item for item in value if item]
    return [value]


def _dedupe_media(values: Iterable[Union[str, Path]]) -> List[Union[str, Path]]:
    seen: set[str] = set()
    result: List[Union[str, Path]] = []
    for value in values:
        marker = str(value)
        if not marker or marker in seen:
            continue
        seen.add(marker)
        result.append(value)
    return result


class _ArkSeedance20Client:
    """Ark contents/generations/tasks client for Seedance 2.0."""

    _SUCCESS_STATUSES = {"succeeded", "success", "completed", "complete", "done", "finished"}
    _FAILED_STATUSES = {"failed", "failure", "error", "cancelled", "canceled", "expired", "rejected"}
    _STATUS_KEYS = ("status", "state", "task_status", "taskStatus")

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        output_dir: str = DEFAULT_SEEDANCE_OUTPUT_DIR,
    ):
        self.api_key = api_key or os.getenv("ARK_API_KEY")
        if not self.api_key:
            raise ValueError("Missing required env var: ARK_API_KEY")

        self.base_url = (base_url or os.getenv("ARK_BASE_URL") or ARK_SEEDANCE20_DEFAULT_BASE_URL).rstrip("/")
        self.model = (
            model
            or os.getenv("ARK_SEEDANCE20_MODEL")
            or os.getenv("SEEDANCE20_MODEL")
        )
        if not self.model:
            raise ValueError("Missing required env var: ARK_SEEDANCE20_MODEL")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    @property
    def tasks_url(self) -> str:
        if self.base_url.endswith("/contents/generations/tasks"):
            return self.base_url
        return f"{self.base_url}/contents/generations/tasks"

    def _media_to_url(self, media: Union[str, Path], fallback_mime: str) -> str:
        media_str = str(media)
        if media_str.startswith(("http://", "https://", "data:")):
            return media_str

        media_path = Path(media_str).expanduser()
        if not media_path.exists():
            raise FileNotFoundError(f"参考素材不存在: {media_path}")

        mime_type = mimetypes.guess_type(media_path.name)[0] or fallback_mime
        with media_path.open("rb") as handle:
            encoded = base64.b64encode(handle.read()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    def _media_content_item(self, media: Union[str, Path], media_type: str, role: str) -> Dict[str, Any]:
        fallback_mime = {
            "image": "image/jpeg",
            "video": "video/mp4",
            "audio": "audio/mpeg",
        }[media_type]
        field = f"{media_type}_url"
        return {
            "type": field,
            field: {"url": self._media_to_url(media, fallback_mime)},
            "role": role,
        }

    def _build_content(
        self,
        prompt: str,
        image_paths: Optional[Iterable[Union[str, Path]]] = None,
        reference_video_path: Optional[Union[str, Path]] = None,
        reference_audio_path: Optional[Union[str, Path]] = None,
    ) -> List[Dict[str, Any]]:
        content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
        for image_path in image_paths or []:
            content.append(self._media_content_item(image_path, "image", "reference_image"))
        if reference_video_path:
            content.append(self._media_content_item(reference_video_path, "video", "reference_video"))
        if reference_audio_path:
            content.append(self._media_content_item(reference_audio_path, "audio", "reference_audio"))
        return content

    def _create_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"POST {self.tasks_url}")
        logger.info(
            "Ark Seedance 2.0 payload: "
            f"model={payload.get('model')}, ratio={payload.get('ratio')}, "
            f"duration={payload.get('duration')}, content_items={len(payload.get('content', []))}, "
            f"generate_audio={payload.get('generate_audio')}, watermark={payload.get('watermark')}"
        )
        response = requests.post(self.tasks_url, json=payload, headers=self.headers, timeout=180)
        if response.status_code >= 400:
            raise RuntimeError(f"Ark Seedance 2.0 create task failed: HTTP {response.status_code} {response.text[:1000]}")
        return response.json()

    def _query_task(self, task_id: str) -> Dict[str, Any]:
        url = f"{self.tasks_url}/{task_id}"
        response = requests.get(url, headers=self.headers, timeout=60)
        if response.status_code >= 400:
            raise RuntimeError(f"Ark Seedance 2.0 query task failed: HTTP {response.status_code} {response.text[:1000]}")
        return response.json()

    @classmethod
    def _iter_dicts(cls, value: Any):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from cls._iter_dicts(child)
        elif isinstance(value, list):
            for child in value:
                yield from cls._iter_dicts(child)

    @staticmethod
    def _url_from_value(value: Any) -> Optional[str]:
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
        if isinstance(value, dict):
            nested = value.get("url")
            if isinstance(nested, str) and nested.startswith(("http://", "https://")):
                return nested
        return None

    @classmethod
    def _extract_task_id(cls, payload: Dict[str, Any]) -> Optional[str]:
        for item in cls._iter_dicts(payload):
            for key in ("id", "task_id", "taskId"):
                value = item.get(key)
                if isinstance(value, (str, int)):
                    return str(value)
        return None

    @classmethod
    def _extract_status(cls, payload: Dict[str, Any]) -> str:
        for item in cls._iter_dicts(payload):
            for key in cls._STATUS_KEYS:
                value = item.get(key)
                if value is not None:
                    return str(value).strip().lower()
        return ""

    @classmethod
    def _extract_error(cls, payload: Dict[str, Any]) -> str:
        for item in cls._iter_dicts(payload):
            for key in ("error", "error_message", "message", "reason"):
                value = item.get(key)
                if value:
                    return json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        return "未知错误"

    @classmethod
    def _extract_video_url(cls, payload: Dict[str, Any]) -> Optional[str]:
        for item in cls._iter_dicts(payload):
            if item.get("role") == "reference_video":
                continue
            for key in ("video_url", "videoUrl", "download_url", "downloadUrl", "output_url", "outputUrl"):
                url = cls._url_from_value(item.get(key))
                if url:
                    return url
            if item.get("type") in {"video_url", "video"}:
                url = cls._url_from_value(item.get("video_url") or item.get("url"))
                if url:
                    return url

        for item in cls._iter_dicts(payload):
            if item.get("role") == "reference_video":
                continue
            for value in item.values():
                if isinstance(value, str) and value.startswith(("http://", "https://")):
                    lowered = value.lower()
                    if ".mp4" in lowered or ".mov" in lowered or "video" in lowered:
                        return value
        return None

    def _poll_until_done(self, task_id: str, interval: int = 8, max_wait: int = 900) -> Dict[str, Any]:
        elapsed = 0
        while elapsed <= max_wait:
            result = self._query_task(task_id)
            status = self._extract_status(result)
            video_url = self._extract_video_url(result)
            logger.info(f"Ark Seedance 2.0 task {task_id} status={status or 'unknown'} waited={elapsed}s")

            if status in self._FAILED_STATUSES:
                raise RuntimeError(f"Ark Seedance 2.0 task failed: {self._extract_error(result)}")
            if status in self._SUCCESS_STATUSES or (video_url and status not in self._FAILED_STATUSES):
                return result

            time.sleep(interval)
            elapsed += interval

        raise TimeoutError(f"Ark Seedance 2.0 task timed out after {max_wait}s: {task_id}")

    def download_video(self, url: str, output_path: Union[str, Path]) -> bool:
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    handle.write(chunk)
        logger.info(f"Seedance 2.0 视频已保存到: {output_file}")
        return True

    def generate(
        self,
        prompt: str,
        generation_type: str,
        image_paths: Optional[Iterable[Union[str, Path]]] = None,
        reference_video_path: Optional[Union[str, Path]] = None,
        reference_audio_path: Optional[Union[str, Path]] = None,
        aspect_ratio: str = "9:16",
        duration: Any = "5s",
        generate_audio: bool = False,
        watermark: bool = False,
        auto_download: bool = True,
        output_path: Optional[str] = None,
        poll_interval: int = 8,
        max_wait: int = 900,
    ) -> Dict[str, Any]:
        start_time = time.time()
        duration_seconds = _duration_to_seconds(duration)
        payload = {
            "model": self.model,
            "content": self._build_content(
                prompt=prompt,
                image_paths=image_paths,
                reference_video_path=reference_video_path,
                reference_audio_path=reference_audio_path,
            ),
            "generate_audio": bool(generate_audio),
            "ratio": aspect_ratio,
            "duration": duration_seconds,
            "watermark": bool(watermark),
        }

        response = self._create_task(payload)
        task_id = self._extract_task_id(response)
        result = response
        if not self._extract_video_url(response):
            if not task_id:
                raise RuntimeError(f"Ark Seedance 2.0 response missing task id: {response}")
            result = self._poll_until_done(task_id, interval=poll_interval, max_wait=max_wait)

        video_url = self._extract_video_url(result)
        if auto_download:
            if not video_url:
                raise RuntimeError(f"Ark Seedance 2.0 task completed but no video URL was found: {result}")
            if output_path:
                output_file = Path(output_path)
            else:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                output_file = self.output_dir / f"{generation_type}_{timestamp}.mp4"
            self.download_video(video_url, output_file)
            result["output_path"] = str(output_file)

        if task_id:
            result.setdefault("task_id", task_id)
        result.setdefault("video_url", video_url)
        result.setdefault("elapsed_time", round(time.time() - start_time, 2))
        return result


class Seedance20VideoGeneratorSchema(BaseModel):
    prompt: str = Field(..., description="视频生成提示词")
    generation_type: str = Field("text_to_video", description="text_to_video / image_to_video / first_last_frame")
    output_dir: str = Field(default=DEFAULT_SEEDANCE_OUTPUT_DIR, description="保存目录")
    output_path: Optional[str] = Field(default=None, description="完整输出路径，优先于 output_dir")
    image_path: Optional[str] = Field(default=None, description="图生视频时的输入图")
    start_image_path: Optional[str] = Field(default=None, description="首帧参考图")
    end_image_path: Optional[str] = Field(default=None, description="尾帧参考图")
    images: Optional[List[str]] = Field(default=None, description="参考图片列表")
    reference_image_path: Optional[Union[str, List[str]]] = Field(default=None, description="兼容单图/多图参考字段")
    reference_image_paths: Optional[List[str]] = Field(default=None, description="参考图片路径或 URL 列表")
    reference_video_path: Optional[str] = Field(default=None, description="参考视频路径或 URL")
    reference_audio_path: Optional[str] = Field(default=None, description="参考音频路径或 URL")
    aspect_ratio: str = Field(default="9:16", description="宽高比 9:16 / 16:9 / 1:1")
    size: str = Field(default="720P", description="保留兼容字段；Ark Seedance 2.0 当前不使用")
    duration: Union[str, int, float] = Field(default="5s", description="视频时长，支持 5s / 10s / 11 / 11.0")
    generate_audio: bool = Field(default=False, description="是否启用 Ark 原生音频")
    watermark: bool = Field(default=False, description="是否添加水印")
    poll_interval: int = Field(default=8, description="轮询间隔秒数")
    max_wait: int = Field(default=900, description="最长等待秒数")


class Seedance20VideoGeneratorTool(SeedanceVideoGeneratorTool):
    """Seedance 2.0 视频生成工具。"""

    name: str = "Seedance 2.0视频生成工具"
    description: str = (
        "使用 Seedance 2.0 模型生成视频；支持文生视频和图生视频，"
        "通过 Ark contents/generations/tasks 接口创建并轮询任务。"
    )
    args_schema: Type[BaseModel] = Seedance20VideoGeneratorSchema

    def _run(
        self,
        prompt: str,
        generation_type: str = "text_to_video",
        output_dir: str = DEFAULT_SEEDANCE_OUTPUT_DIR,
        output_path: Optional[str] = None,
        image_path: Optional[str] = None,
        start_image_path: Optional[str] = None,
        end_image_path: Optional[str] = None,
        images: Optional[List[str]] = None,
        reference_image_path: Optional[Union[str, List[str]]] = None,
        reference_image_paths: Optional[List[str]] = None,
        reference_video_path: Optional[str] = None,
        reference_audio_path: Optional[str] = None,
        aspect_ratio: str = "9:16",
        size: str = "720P",
        duration: Any = None,
        generate_audio: bool = False,
        watermark: bool = False,
        poll_interval: int = 8,
        max_wait: int = 900,
        **_: Any,
    ) -> Dict[str, Any]:
        del size
        engine_name = "seedance2.0"
        if generation_type not in ("text_to_video", "image_to_video", "first_last_frame"):
            return {
                "error": f"seedance2.0 不支持 generation_type={generation_type}",
                "engine": engine_name,
            }

        duration = duration or os.getenv("SEEDANCE20_DEFAULT_DURATION", os.getenv("SEEDANCE_DEFAULT_DURATION", "5s"))
        client_output_dir = resolve_video_output_dir(
            output_dir,
            output_path,
            DEFAULT_SEEDANCE_OUTPUT_DIR,
            LEGACY_SEEDANCE_OUTPUT_DIRS,
        )
        if reference_image_paths is None and reference_image_path is not None:
            reference_image_paths = _coerce_media_list(reference_image_path)  # type: ignore[assignment]

        image_refs = _dedupe_media(
            [
                *_coerce_media_list(image_path),
                *_coerce_media_list(images),
                *_coerce_media_list(start_image_path),
                *_coerce_media_list(end_image_path),
                *_coerce_media_list(reference_image_paths),
            ]
        )
        if generation_type == "image_to_video" and not image_refs:
            return {"error": "image_to_video 需要 image_path 或 reference_image_paths", "engine": engine_name}

        try:
            client = _ArkSeedance20Client(output_dir=client_output_dir)
            result = client.generate(
                prompt=prompt,
                generation_type=generation_type,
                image_paths=image_refs,
                reference_video_path=reference_video_path,
                reference_audio_path=reference_audio_path,
                aspect_ratio=aspect_ratio,
                duration=duration,
                generate_audio=generate_audio,
                watermark=watermark,
                auto_download=True,
                output_path=output_path,
                poll_interval=poll_interval,
                max_wait=max_wait,
            )

            generated_path = result.get("output_path")
            if generated_path:
                validate_video_aspect_ratio(generated_path, aspect_ratio)

            return {
                "engine": engine_name,
                "generation_type": generation_type,
                "task_id": result.get("task_id"),
                "result": result,
                "output_path": result.get("output_path"),
            }
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Seedance 2.0 视频生成失败: {exc}")
            return {"error": str(exc), "engine": engine_name}
