#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Veo3视频生成CrewAI工具
使用Veo3异步API生成视频,支持文生视频、图生视频
"""

import os
import time
import requests
from typing import Dict, Any, Type, Optional, List
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from pathlib import Path

# 加载环境变量
load_dotenv()


class Veo3VideoGeneratorSchema(BaseModel):
    """Veo3视频生成工具的输入参数"""
    prompt: str = Field(
        ...,
        description="视频生成的文本提示词，描述要生成的视频内容"
    )
    generation_type: str = Field(
        default="text_to_video",
        description="生成类型：'text_to_video'(文生视频), 'image_to_video'(图生视频)"
    )
    output_dir: str = Field(
        default="veo3_videos",
        description="生成视频的保存目录（当output_path未提供时使用）"
    )
    output_path: str = Field(
        default=None,
        description="完整的输出文件路径（优先使用，如果提供则忽略output_dir）"
    )
    image_path: str = Field(
        default=None,
        description="输入图片路径，用于图生视频功能（可选）"
    )
    aspect_ratio: str = Field(
        default="9:16",
        description="视频比例：'16:9'(横屏)、'9:16'(竖屏)、'1:1'(方形)"
    )


class Veo3VideoGeneratorTool(BaseTool):
    name: str = "Veo3视频生成工具"
    description: str = (
        "使用Veo3 API生成高质量视频的工具。支持文生视频、图生视频等多种生成方式。"
        "可以生成各种风格的动态视频内容，适合创意视频制作。支持竖屏、横屏、方形多种比例。"
    )
    args_schema: Type[BaseModel] = Veo3VideoGeneratorSchema

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _run(
        self,
        prompt: str,
        generation_type: str = "text_to_video",
        output_dir: str = "veo3_videos",
        output_path: str = None,
        image_path: str = None,
        aspect_ratio: str = "9:16",
    ) -> str:
        """
        执行Veo3视频生成

        Args:
            prompt: 视频生成提示词
            generation_type: 生成类型
            output_dir: 输出目录（当output_path未提供时使用）
            output_path: 完整的输出文件路径（优先使用）
            image_path: 输入图片路径
            aspect_ratio: 视频比例

        Returns:
            生成结果的描述信息或视频路径
        """
        try:
            # 初始化Veo3客户端
            client = Veo3ApiClient(output_dir=output_dir)

            # 根据生成类型执行不同的生成方法
            if generation_type == "text_to_video":
                video_path = client.text_to_video(prompt=prompt, output_path=output_path, aspect_ratio=aspect_ratio)
                if video_path:
                    return {"output_path": video_path, "status": "success", "message": f"✅ Veo3文生视频成功！视频已保存到: {video_path}"}
                else:
                    return {"status": "failed", "message": "❌ Veo3文生视频失败"}

            elif generation_type == "image_to_video":
                if not image_path or not os.path.exists(image_path):
                    return {"status": "failed", "message": "❌ 图生视频需要提供有效的输入图片路径"}

                video_path = client.image_to_video(
                    image_path=image_path,
                    prompt=prompt,
                    output_path=output_path,
                    aspect_ratio=aspect_ratio
                )
                if video_path:
                    return {"output_path": video_path, "status": "success", "message": f"✅ Veo3图生视频成功！视频已保存到: {video_path}"}
                else:
                    return {"status": "failed", "message": "❌ Veo3图生视频失败"}

            else:
                return {"status": "failed", "message": f"❌ 不支持的生成类型: {generation_type}"}

        except Exception as e:
            return {"status": "failed", "message": f"❌ Veo3视频生成失败: {str(e)}"}


class Veo3ApiClient:
    """Veo3 API客户端（异步轮询模式）"""

    # aspect_ratio → size 映射
    ASPECT_RATIO_TO_SIZE = {
        "9:16": "720x1280",
        "16:9": "1280x720",
        "1:1": "720x720",
    }

    POLL_INTERVAL = 10  # 轮询间隔（秒）
    POLL_TIMEOUT = 1800  # 超时时间（秒，30分钟）

    def __init__(self, output_dir: str = "veo3_videos"):
        """初始化API客户端"""
        self.base_url = os.getenv('VEO3_BASE_URL', 'http://localhost:8000')
        self.api_key = os.getenv('VEO3_API_KEY', 'your-api-key')
        self.model = os.getenv('VEO3_MODEL', 'veo3')

        # 从 VEO3_BASE_URL 推导异步 API base（去掉末尾 /v1）
        self.async_api_base = self.base_url.rstrip('/').removesuffix('/v1')

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_video_task(self, prompt: str, size: str, image_path: Optional[str] = None) -> str:
        """
        提交视频生成任务

        Args:
            prompt: 视频生成提示词
            size: 视频尺寸，如 720x1280
            image_path: 输入图片路径（图生视频时提供）

        Returns:
            task ID

        Raises:
            Exception: 提交失败时抛出
        """
        url = f"{self.async_api_base}/veo/v1/videos"
        headers = {
            "Authorization": self.api_key,
        }

        data = {
            "prompt": prompt,
            "model": self.model,
            "size": size,
        }

        files = None
        if image_path:
            files = {
                "input_reference": open(image_path, "rb"),
            }

        try:
            print(f"📤 提交视频生成任务到: {url}")
            response = requests.post(url, headers=headers, data=data, files=files, timeout=60)
            response.raise_for_status()
            result = response.json()
            print(f"📋 API响应: {result}")

            # 提取 task ID
            task_id = result.get("video_id") or result.get("task_id") or result.get("id")
            if not task_id:
                raise Exception(f"响应中未找到 task ID: {result}")

            print(f"✅ 任务已提交，task ID: {task_id}")
            return task_id

        except requests.exceptions.HTTPError as e:
            raise Exception(f"提交任务失败 (HTTP {e.response.status_code}): {e.response.text}")
        finally:
            if files and "input_reference" in files:
                files["input_reference"].close()

    def poll_video_task(self, video_id: str) -> str:
        """
        轮询视频生成任务状态，直到完成或超时

        Args:
            video_id: 任务 ID

        Returns:
            视频下载 URL

        Raises:
            Exception: 任务失败或超时时抛出
        """
        url = f"{self.async_api_base}/veo/v1/videos/{video_id}"
        headers = {
            "Authorization": self.api_key,
        }

        start_time = time.time()
        last_progress = None

        print(f"⏳ 开始轮询任务状态 (间隔 {self.POLL_INTERVAL}s, 超时 {self.POLL_TIMEOUT // 60}min)...", flush=True)

        while True:
            elapsed = time.time() - start_time
            if elapsed > self.POLL_TIMEOUT:
                raise Exception(f"任务超时（已等待 {self.POLL_TIMEOUT // 60} 分钟）")

            try:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                result = response.json()
            except requests.exceptions.RequestException as e:
                print(f"⚠️  轮询请求失败，将重试: {e}", flush=True)
                time.sleep(self.POLL_INTERVAL)
                continue

            status = result.get("status", "unknown")
            progress = result.get("progress")

            # 打印进度
            if progress is not None and progress != last_progress:
                print(f"📊 进度: {progress}% (已等待 {elapsed:.0f}s)", flush=True)
                last_progress = progress
            else:
                print(f"⏳ 状态: {status} (已等待 {elapsed:.0f}s)", flush=True)

            if status == "completed":
                video_url = result.get("video_url")
                if not video_url:
                    raise Exception(f"任务完成但未返回 video_url: {result}")
                print(f"✅ 视频生成完成！(耗时 {elapsed:.0f}s)")
                return video_url

            elif status == "failed":
                error_msg = result.get("error") or result.get("message") or "未知错误"
                raise Exception(f"视频生成失败: {error_msg}")

            time.sleep(self.POLL_INTERVAL)

    def download_video(self, url: str, output_path: str) -> bool:
        """
        下载视频文件

        Args:
            url: 视频URL
            output_path: 输出路径

        Returns:
            是否下载成功
        """
        try:
            print(f"\n📥 正在下载视频: {url}")
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            file_size = os.path.getsize(output_path)
            print(f"✅ 视频已保存到: {output_path}")
            print(f"📊 文件大小: {file_size / (1024*1024):.2f} MB")
            return True

        except Exception as e:
            print(f"❌ 下载失败: {e}")
            return False

    def _resolve_output_path(self, output_path: Optional[str], prefix: str) -> str:
        """解析输出路径"""
        if output_path:
            output_dir_from_path = os.path.dirname(output_path)
            if output_dir_from_path:
                os.makedirs(output_dir_from_path, exist_ok=True)
            return output_path
        else:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            return str(self.output_dir / f"{prefix}_{timestamp}.mp4")

    def text_to_video(self, prompt: str, output_path: Optional[str] = None, aspect_ratio: str = "9:16") -> Optional[str]:
        """
        文生视频功能

        Args:
            prompt: 视频生成提示词
            output_path: 自定义输出路径（可选）
            aspect_ratio: 视频比例

        Returns:
            生成的视频文件路径，失败返回None
        """
        print(f"\n{'='*60}")
        print("🎬 Veo3 文生视频 (Text to Video)")
        print(f"{'='*60}")
        print(f"📝 提示词: {prompt}")
        print(f"📐 视频比例: {aspect_ratio}")

        start_time = time.time()
        try:
            size = self.ASPECT_RATIO_TO_SIZE.get(aspect_ratio, "720x1280")
            print(f"📐 视频尺寸: {size}")

            # 提交任务
            task_id = self.create_video_task(prompt=prompt, size=size)

            # 轮询等待完成
            video_url = self.poll_video_task(task_id)

            # 下载视频
            final_path = self._resolve_output_path(output_path, "text_to_video")
            if self.download_video(video_url, final_path):
                elapsed_time = time.time() - start_time
                print(f"⏱️  总耗时: {elapsed_time:.2f} 秒")
                return final_path

            return None

        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"\n❌ 请求失败 (耗时: {elapsed_time:.2f} 秒): {e}")
            import traceback
            traceback.print_exc()
            return None

    def image_to_video(self, image_path: str, prompt: str, output_path: Optional[str] = None, aspect_ratio: str = "9:16", **kwargs) -> Optional[str]:
        """
        图生视频功能

        Args:
            image_path: 输入图片路径
            prompt: 视频生成提示词
            output_path: 自定义输出路径（可选）
            aspect_ratio: 视频比例

        Returns:
            生成的视频文件路径，失败返回None
        """
        print(f"\n{'='*60}")
        print("🎬 Veo3 图生视频 (Image to Video)")
        print(f"{'='*60}")
        print(f"📝 提示词: {prompt}")
        print(f"🖼️  输入图片: {image_path}")
        print(f"📐 视频比例: {aspect_ratio}")

        start_time = time.time()
        try:
            size = self.ASPECT_RATIO_TO_SIZE.get(aspect_ratio, "720x1280")
            print(f"📐 视频尺寸: {size}")

            # 提交任务（带图片）
            task_id = self.create_video_task(prompt=prompt, size=size, image_path=image_path)

            # 轮询等待完成
            video_url = self.poll_video_task(task_id)

            # 下载视频
            final_path = self._resolve_output_path(output_path, "image_to_video")
            if self.download_video(video_url, final_path):
                elapsed_time = time.time() - start_time
                print(f"⏱️  总耗时: {elapsed_time:.2f} 秒")
                return final_path

            return None

        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"\n❌ 请求失败 (耗时: {elapsed_time:.2f} 秒): {e}")
            import traceback
            traceback.print_exc()
            return None
