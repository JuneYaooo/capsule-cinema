"""Seedance 1.0 Pro video generator (CrewAI tool).

Seedance 与 jimeng35pro 在巨灵 (api.177911.com) 共享同一组 REST API
（POST /v1/videos 创建任务，GET /v1/videos/{task_id} 轮询）。差异只在
``model`` 字段。

通过环境变量 ``SEEDANCE_DEFAULT_DURATION`` 可以切换默认时长 ("5s"/"10s")。
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from src.logger import get_logger
from .jimeng35pro_video_generator_tool import Jimeng35ProVideoClient

logger = get_logger("seedance_video_generator")


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tier = (os.getenv("SEEDANCE_TIER") or "pro").lower()
        self.DURATION_TO_MODEL = self._TIER_MAP.get(tier, self._TIER_MAP["pro"])


class SeedanceVideoGeneratorSchema(BaseModel):
    prompt: str = Field(..., description="视频生成提示词")
    generation_type: str = Field(
        "text_to_video",
        description="text_to_video 或 image_to_video",
    )
    output_dir: str = Field(default="seedance_videos", description="保存目录")
    output_path: Optional[str] = Field(default=None, description="完整输出路径，优先于 output_dir")
    image_path: Optional[str] = Field(default=None, description="图生视频时的输入图")
    aspect_ratio: str = Field(default="9:16", description="宽高比 9:16 / 16:9 / 1:1")
    size: str = Field(default="720P", description="分辨率 720P / 1080P")
    duration: str = Field(default="5s", description="时长 5s / 10s")


class SeedanceVideoGeneratorTool(BaseTool):
    """Seedance 1.0 Pro 视频生成工具。"""

    name: str = "Seedance视频生成工具"
    description: str = (
        "使用 Seedance 1.0 Pro 模型生成视频；与 jimeng35pro 共享 REST API，"
        "差别在 model 名（seedance-1.0-pro / seedance-1.0-pro-10s）。"
    )
    args_schema: Type[BaseModel] = SeedanceVideoGeneratorSchema

    def _run(
        self,
        prompt: str,
        generation_type: str = "text_to_video",
        output_dir: str = "seedance_videos",
        output_path: Optional[str] = None,
        image_path: Optional[str] = None,
        aspect_ratio: str = "9:16",
        size: str = "720P",
        duration: Optional[str] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        if generation_type not in ("text_to_video", "image_to_video"):
            return {
                "error": f"seedance 不支持 generation_type={generation_type}",
                "engine": "seedance",
            }
        if generation_type == "image_to_video" and not image_path:
            return {"error": "image_to_video 需要 image_path", "engine": "seedance"}

        duration = duration or os.getenv("SEEDANCE_DEFAULT_DURATION", "5s")

        try:
            client = _SeedanceClient(output_dir=output_dir)
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

            return {
                "engine": "seedance",
                "generation_type": generation_type,
                "result": result,
                "output_path": result.get("output_path"),
            }
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Seedance 视频生成失败: {exc}")
            return {"error": str(exc), "engine": "seedance"}
