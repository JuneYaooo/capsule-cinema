from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import requests
from crewai.tools import BaseTool
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from src.logger import get_logger
from .output_dir_utils import default_video_output_dir, resolve_video_output_dir

load_dotenv()

logger = get_logger("veo31_video_generator")

DEFAULT_VEO31_OUTPUT_DIR = default_video_output_dir("veo31")
LEGACY_VEO31_OUTPUT_DIRS = ("veo31_videos",)


class Veo31VideoGeneratorSchema(BaseModel):
    prompt: str = Field(..., description="视频生成提示词")
    generation_type: str = Field(
        "image_to_video",
        description="text_to_video | image_to_video | first_last_frame",
    )
    output_dir: str = Field(DEFAULT_VEO31_OUTPUT_DIR, description="保存目录")
    output_path: Optional[str] = Field(None, description="完整输出路径，优先于 output_dir")
    image_path: Optional[str] = Field(None, description="单图图生视频输入")
    start_image_path: Optional[str] = Field(None, description="首帧图片路径或 URL")
    end_image_path: Optional[str] = Field(None, description="尾帧图片路径或 URL")
    images: Optional[List[str]] = Field(None, description="首尾帧图片 URL/path 列表")
    aspect_ratio: str = Field("9:16", description="9:16 / 16:9 / 1:1")
    model: Optional[str] = Field(None, description="默认 JULING_VEO31_MODEL 或 veo3.1_fast")


class Veo31VideoClient:
    POLL_INTERVAL = 8
    POLL_TIMEOUT = 1200

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        output_dir: str = DEFAULT_VEO31_OUTPUT_DIR,
    ):
        self.api_key = api_key or os.getenv("JULING_API_KEY")
        self.base_url = (base_url or os.getenv("JULING_BASE_URL") or "").rstrip("/")
        self.model = os.getenv("JULING_VEO31_MODEL", "veo3.1_fast")
        if not self.api_key:
            raise ValueError("Missing required env var: JULING_API_KEY")
        if not self.base_url:
            raise ValueError("Missing required env var: JULING_BASE_URL")

        output_dir = resolve_video_output_dir(
            output_dir,
            None,
            DEFAULT_VEO31_OUTPUT_DIR,
            LEGACY_VEO31_OUTPUT_DIRS,
        )
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def image_to_url(self, image: str) -> str:
        if image.startswith(("http://", "https://", "data:image/")):
            return image

        path = Path(image)
        if not path.exists():
            raise FileNotFoundError(f"图片文件不存在: {path}")

        mime = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }.get(path.suffix.lower(), "image/jpeg")
        encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
        return f"data:{mime};base64,{encoded}"

    def normalize_images(
        self,
        generation_type: str,
        image_path: Optional[str],
        start_image_path: Optional[str],
        end_image_path: Optional[str],
        images: Optional[List[str]],
    ) -> List[str]:
        if generation_type == "first_last_frame":
            selected = images or [start_image_path, end_image_path]
            selected = [item for item in selected if item]
            if len(selected) != 2:
                raise ValueError(
                    "first_last_frame requires exactly two images via images "
                    "or start_image_path/end_image_path"
                )
            return [self.image_to_url(item) for item in selected]

        if generation_type == "image_to_video":
            if not image_path:
                raise ValueError("image_to_video requires image_path")
            return [self.image_to_url(image_path)]

        return []

    def build_payload(
        self,
        prompt: str,
        generation_type: str,
        aspect_ratio: str,
        images: Optional[List[str]] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model or self.model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
        }

        if generation_type == "first_last_frame":
            if not images or len(images) != 2:
                raise ValueError("first_last_frame requires exactly two images")
            payload["type"] = 2
            payload["images"] = images
        elif generation_type == "image_to_video":
            if not images or len(images) != 1:
                raise ValueError("image_to_video requires exactly one image")
            payload["type"] = 1
            payload["images"] = images
        elif generation_type == "text_to_video":
            payload["type"] = 0
        else:
            raise ValueError(f"Unsupported generation_type: {generation_type}")

        return payload

    def create_task(self, payload: Dict[str, Any]) -> str:
        response = requests.post(
            f"{self.base_url}/v1/videos",
            json=payload,
            headers=self.headers,
            timeout=180,
        )
        response.raise_for_status()
        data = response.json()
        task_id = data.get("id") or data.get("task_id") or data.get("video_id")
        if not task_id:
            raise ValueError(f"未获取到任务ID，响应字段: {list(data.keys())}")
        return str(task_id)

    def query_task(self, task_id: str) -> Dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/v1/videos/{task_id}",
            headers=self.headers,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def poll_until_done(self, task_id: str) -> Dict[str, Any]:
        started = time.time()
        while time.time() - started < self.POLL_TIMEOUT:
            data = self.query_task(task_id)
            status = str(data.get("status", "")).lower()
            if status in {"success", "completed", "done"}:
                return data
            if status in {"failed", "error"}:
                raise RuntimeError(data.get("error") or data.get("message") or "视频任务失败")
            time.sleep(self.POLL_INTERVAL)

        raise TimeoutError(f"任务超时（已等待 {self.POLL_TIMEOUT}s）")

    def resolve_output_path(self, output_path: Optional[str], prefix: str) -> Path:
        if output_path:
            path = Path(output_path)
        else:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            path = self.output_dir / f"{prefix}_{timestamp}.mp4"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def download_result(self, task_id: str, result: Dict[str, Any], output_path: Path) -> str:
        video_url = result.get("video_url") or result.get("url") or result.get("output_url")
        url = video_url or f"{self.base_url}/v1/videos/{task_id}/content"
        headers = None if video_url else self.headers
        response = requests.get(url, headers=headers, stream=True, timeout=300)
        response.raise_for_status()
        with output_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    handle.write(chunk)
        return str(output_path)

    def generate(
        self,
        prompt: str,
        generation_type: str,
        aspect_ratio: str,
        output_path: Optional[str],
        image_path: Optional[str],
        start_image_path: Optional[str],
        end_image_path: Optional[str],
        images: Optional[List[str]],
        model: Optional[str],
    ) -> str:
        normalized_images = self.normalize_images(
            generation_type,
            image_path,
            start_image_path,
            end_image_path,
            images,
        )
        payload = self.build_payload(
            prompt,
            generation_type,
            aspect_ratio,
            normalized_images,
            model=model,
        )
        task_id = self.create_task(payload)
        result = self.poll_until_done(task_id)
        target = self.resolve_output_path(output_path, generation_type)
        return self.download_result(task_id, result, target)


class Veo31VideoGeneratorTool(BaseTool):
    name: str = "Veo3.1视频生成工具"
    description: str = (
        "使用 Juling veo3.1_fast 生成视频，支持文生视频、单图图生视频和首尾帧视频。"
    )
    args_schema: Type[BaseModel] = Veo31VideoGeneratorSchema

    def _run(
        self,
        prompt: str,
        generation_type: str = "image_to_video",
        output_dir: str = DEFAULT_VEO31_OUTPUT_DIR,
        output_path: Optional[str] = None,
        image_path: Optional[str] = None,
        start_image_path: Optional[str] = None,
        end_image_path: Optional[str] = None,
        images: Optional[List[str]] = None,
        aspect_ratio: str = "9:16",
        model: Optional[str] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        try:
            client_output_dir = resolve_video_output_dir(
                output_dir,
                output_path,
                DEFAULT_VEO31_OUTPUT_DIR,
                LEGACY_VEO31_OUTPUT_DIRS,
            )
            client = Veo31VideoClient(output_dir=client_output_dir)
            final_path = client.generate(
                prompt=prompt,
                generation_type=generation_type,
                aspect_ratio=aspect_ratio,
                output_path=output_path,
                image_path=image_path,
                start_image_path=start_image_path,
                end_image_path=end_image_path,
                images=images,
                model=model,
            )
            return {
                "status": "success",
                "engine": "veo3.1",
                "generation_type": generation_type,
                "output_path": final_path,
            }
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Veo3.1 视频生成失败: {exc}")
            return {"status": "failed", "engine": "veo3.1", "error": str(exc)}
