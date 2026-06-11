#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jimeng 3.5 Pro 视频生成CrewAI工具
使用即梦视频 jimeng-video-3.5-pro 模型API生成视频，支持文生视频、图生视频
采用 REST API + 轮询模式
"""

import os
import time
import base64
import json
import requests
from typing import Dict, Any, Type, Optional, Union
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from pathlib import Path

from src.logger import get_logger

# 加载环境变量
load_dotenv()

# 初始化日志
logger = get_logger("jimeng35pro_video_generator")


class Jimeng35ProVideoClient:
    """
    即梦视频 3.5 Pro 客户端

    使用 REST API + 轮询模式:
    - POST /v1/videos 创建任务
    - GET /v1/videos/{task_id} 查询状态

    支持:
    - 文生视频 (Text-to-Video)
    - 图生视频 (Image-to-Video)
    """

    DURATION_TO_MODEL = {
        "5s": "jimeng-video-3.5-pro",
        "10s": "jimeng-video-3.5-pro-10s",
        "12s": "jimeng-video-3.5-pro-12s",
    }

    def __init__(self, api_key=None, base_url=None, output_dir="output/jimeng35pro"):
        self.api_key = api_key or os.getenv("JULING_API_KEY")
        if not self.api_key:
            raise ValueError("API key is required. Set JULING_API_KEY env variable or pass api_key parameter.")

        self.base_url = (base_url or os.getenv("JULING_BASE_URL", "")).rstrip("/")
        if not self.base_url:
            raise ValueError("Base URL is required. Set JULING_BASE_URL env variable or pass base_url parameter.")

        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _image_to_url(self, image: Union[str, Path]) -> str:
        """将图片路径或URL转为可用的URL/data URI"""
        image_str = str(image)
        # 已经是URL，直接返回
        if image_str.startswith("http://") or image_str.startswith("https://"):
            return image_str

        # 本地文件，转为 base64 data URI
        image_path = Path(image_str)
        if not image_path.exists():
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        mime_types = {
            '.jpeg': 'image/jpeg', '.jpg': 'image/jpeg',
            '.png': 'image/png', '.webp': 'image/webp', '.gif': 'image/gif'
        }
        mime_type = mime_types.get(image_path.suffix.lower(), 'image/jpeg')

        with open(image_path, "rb") as f:
            base64_str = base64.b64encode(f.read()).decode('utf-8')

        return f"data:{mime_type};base64,{base64_str}"

    def download_video(self, url: str, output_path: Union[str, Path]) -> bool:
        try:
            logger.info(f"正在下载视频: {url}")
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()

            output_path = Path(output_path)
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"视频已保存到: {output_path}")
            return True
        except Exception as e:
            logger.error(f"下载失败: {e}")
            return False

    def _create_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """创建视频生成任务（带重试，应对中转商偶发 read timeout）"""
        url = f"{self.base_url}/v1/videos"
        logger.info(f"POST {url}")
        logger.info(f"Payload: {json.dumps({k: v for k, v in payload.items() if k != 'image'}, ensure_ascii=False)}")

        last_err: Optional[Exception] = None
        for attempt in range(1, 4):  # 总共最多 3 次
            try:
                resp = requests.post(
                    url, json=payload, headers=self.headers, timeout=180
                )
                resp.raise_for_status()
                data = resp.json()
                logger.info(f"创建任务响应: {json.dumps(data, ensure_ascii=False)}")
                return data
            except (requests.exceptions.ReadTimeout,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.HTTPError) as exc:
                last_err = exc
                # 5xx / 网络抖动才重试，4xx 立即抛
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status and 400 <= status < 500:
                    raise
                wait = 5 * attempt
                logger.warning(
                    f"创建任务第 {attempt} 次失败 ({exc.__class__.__name__})，{wait}s 后重试"
                )
                time.sleep(wait)
        raise last_err if last_err else Exception("创建任务失败")

    def _query_task(self, task_id: str) -> Dict[str, Any]:
        """查询任务状态（带短重试）"""
        url = f"{self.base_url}/v1/videos/{task_id}"
        last_err: Optional[Exception] = None
        for attempt in range(1, 4):
            try:
                resp = requests.get(url, headers=self.headers, timeout=60)
                resp.raise_for_status()
                return resp.json()
            except (requests.exceptions.ReadTimeout,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.HTTPError) as exc:
                last_err = exc
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status and 400 <= status < 500:
                    raise
                time.sleep(2 * attempt)
        raise last_err if last_err else Exception("查询任务失败")

    def _poll_until_done(self, task_id: str, interval: int = 8, max_wait: int = 900) -> Dict[str, Any]:
        """轮询任务直到完成"""
        elapsed = 0
        while elapsed < max_wait:
            result = self._query_task(task_id)
            status = result.get("status", "")
            logger.info(f"任务 {task_id} 状态: {status} (已等待 {elapsed}s)")

            if status in ("success", "completed", "done"):
                video_url = result.get("video_url")
                logger.info(f"视频生成完成! video_url: {video_url}")
                return result
            if status in ("failed", "error"):
                error_msg = result.get("error") or result.get("message") or "未知错误"
                raise Exception(f"任务失败: {error_msg}")

            time.sleep(interval)
            elapsed += interval

        raise Exception(f"任务超时 (已等待 {max_wait}s)")

    def _get_model(self, duration: str) -> str:
        """根据时长获取模型名"""
        model = self.DURATION_TO_MODEL.get(duration)
        if not model:
            raise ValueError(f"不支持的时长: {duration}。支持: {list(self.DURATION_TO_MODEL.keys())}")
        return model

    def text_to_video(
        self,
        prompt: str,
        duration: str = "5s",
        aspect_ratio: str = "16:9",
        size: str = "720P",
        auto_download: bool = True,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """文生视频"""
        model = self._get_model(duration)

        logger.info(f"{'='*60}")
        logger.info("即梦3.5Pro 文生视频 (Text to Video)")
        logger.info(f"{'='*60}")
        logger.info(f"模型: {model} (时长: {duration})")
        logger.info(f"提示词: {prompt}")
        logger.info(f"宽高比: {aspect_ratio}, 分辨率: {size}")

        start_time = time.time()

        payload = {
            "model": model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "size": size,
        }

        resp = self._create_task(payload)
        task_id = resp.get("id")
        if not task_id:
            raise Exception(f"未获取到任务ID，响应: {resp}")

        logger.info(f"任务ID: {task_id}")
        result = self._poll_until_done(task_id)

        elapsed_time = time.time() - start_time
        logger.info(f"总耗时: {elapsed_time:.2f} 秒")

        # 自动下载视频
        if auto_download:
            video_url = result.get("video_url")
            if video_url:
                if output_path:
                    output_file = Path(output_path)
                else:
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    output_file = self.output_dir / f"text_to_video_{timestamp}.mp4"

                output_file.parent.mkdir(parents=True, exist_ok=True)
                self.download_video(video_url, output_file)
                result['output_path'] = str(output_file)

        return result

    def image_to_video(
        self,
        image: Union[str, Path],
        prompt: Optional[str] = None,
        duration: str = "5s",
        aspect_ratio: str = "16:9",
        size: str = "720P",
        auto_download: bool = True,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """图生视频"""
        model = self._get_model(duration)

        logger.info(f"{'='*60}")
        logger.info("即梦3.5Pro 图生视频 (Image to Video)")
        logger.info(f"{'='*60}")
        logger.info(f"模型: {model} (时长: {duration})")
        logger.info(f"图片: {image}")
        logger.info(f"宽高比: {aspect_ratio}, 分辨率: {size}")
        if prompt:
            logger.info(f"提示词: {prompt}")

        start_time = time.time()

        image_url = self._image_to_url(image)

        payload = {
            "model": model,
            "aspect_ratio": aspect_ratio,
            "size": size,
            "image": image_url,
        }
        if prompt:
            payload["prompt"] = prompt

        resp = self._create_task(payload)
        task_id = resp.get("id")
        if not task_id:
            raise Exception(f"未获取到任务ID，响应: {resp}")

        logger.info(f"任务ID: {task_id}")
        result = self._poll_until_done(task_id)

        elapsed_time = time.time() - start_time
        logger.info(f"总耗时: {elapsed_time:.2f} 秒")

        # 自动下载视频
        if auto_download:
            video_url = result.get("video_url")
            if video_url:
                if output_path:
                    output_file = Path(output_path)
                else:
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    output_file = self.output_dir / f"image_to_video_{timestamp}.mp4"

                output_file.parent.mkdir(parents=True, exist_ok=True)
                self.download_video(video_url, output_file)
                result['output_path'] = str(output_file)

        return result


class Jimeng35ProVideoGeneratorSchema(BaseModel):
    """Jimeng 3.5 Pro 视频生成工具的输入参数"""
    prompt: str = Field(
        ...,
        description="视频生成的提示词，描述要生成的视频内容"
    )
    generation_type: str = Field(
        default="text_to_video",
        description="生成类型：'text_to_video'(文生视频), 'image_to_video'(图生视频)"
    )
    output_dir: str = Field(
        default="jimeng35pro_videos",
        description="生成视频的保存目录（当output_path未提供时使用）"
    )
    output_path: str = Field(
        default=None,
        description="完整的输出文件路径（优先使用，如果提供则忽略output_dir）"
    )
    image_path: str = Field(
        default=None,
        description="输入图片路径或URL，用于图生视频功能"
    )
    aspect_ratio: str = Field(
        default="16:9",
        description="视频宽高比: '16:9'(横屏) 或 '9:16'(竖屏)"
    )
    size: str = Field(
        default="720P",
        description="视频分辨率: '720P' 或 '1080P'"
    )
    duration: str = Field(
        default="5s",
        description="视频时长: '5s', '10s' 或 '12s'"
    )


class Jimeng35ProVideoGeneratorTool(BaseTool):
    name: str = "Jimeng35Pro视频生成工具"
    description: str = (
        "使用即梦视频3.5Pro模型API生成高质量视频的工具。"
        "支持文生视频和图生视频两种模式。"
        "支持指定宽高比(16:9/9:16)和分辨率(720P/1080P)。"
    )
    args_schema: Type[BaseModel] = Jimeng35ProVideoGeneratorSchema

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _run(
        self,
        prompt: str,
        generation_type: str = "text_to_video",
        output_dir: str = "jimeng35pro_videos",
        output_path: str = None,
        image_path: str = None,
        aspect_ratio: str = "16:9",
        size: str = "720P",
        duration: str = "5s",
        # 兼容通用接口的额外参数（忽略）
        start_image_path: str = None,
        end_image_path: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            if generation_type not in ["text_to_video", "image_to_video"]:
                raise ValueError(f"不支持的生成类型: {generation_type}。jimeng35pro 支持 text_to_video 和 image_to_video")

            if generation_type == "image_to_video" and not image_path:
                raise ValueError("图生视频需要提供image_path参数")

            # 初始化客户端
            api_key = os.getenv("JULING_API_KEY")
            base_url = os.getenv("JULING_BASE_URL")

            if not api_key or not base_url:
                raise ValueError("缺少JULING_API_KEY或JULING_BASE_URL环境变量")

            client = Jimeng35ProVideoClient(api_key=api_key, base_url=base_url, output_dir=output_dir)

            logger.info(f"开始Jimeng35Pro {generation_type}: prompt: {prompt[:50]}...")

            if generation_type == "text_to_video":
                response = client.text_to_video(
                    prompt=prompt,
                    duration=duration,
                    aspect_ratio=aspect_ratio,
                    size=size,
                    auto_download=True,
                    output_path=output_path
                )
            elif generation_type == "image_to_video":
                response = client.image_to_video(
                    image=image_path,
                    prompt=prompt,
                    duration=duration,
                    aspect_ratio=aspect_ratio,
                    size=size,
                    auto_download=True,
                    output_path=output_path
                )

            final_path = response.get('output_path')

            if final_path and os.path.exists(final_path):
                logger.info(f"Jimeng35Pro {generation_type} 成功: {final_path}")
                return {
                    "output_path": final_path,
                    "status": "success",
                    "message": f"Jimeng35Pro {generation_type} 成功！视频已保存到: {final_path}"
                }
            else:
                raise Exception("未能从响应中获取有效的视频路径")

        except Exception as e:
            error_msg = f"Jimeng35Pro视频生成失败: {str(e)}"
            logger.error(error_msg)
            return {"status": "failed", "error": error_msg}
