#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
InfiniteTalkV2V 视频对口型工具（RunningHub AI App）

输入：视频 + 音频 → 输出：对口型后的新视频
工作流 App ID: 1961415775317856257
"""

import os
import time
import requests
from typing import Dict, Any, Type, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from custom_tools.base_tool import BaseTool
from pathlib import Path
import subprocess

from src.logger import get_logger

load_dotenv()
logger = get_logger("infinitetalk_v2v")

# RunningHub App 常量
APP_ID = "1961415775317856257"
BASE_URL = "https://www.runninghub.ai"


class InfiniteTalkV2VSchema(BaseModel):
    video_path: str = Field(..., description="输入视频路径（需含人脸，mp4/mov 等）")
    audio_path: str = Field(..., description="输入音频路径（mp3/wav 等）")
    output_path: str = Field(..., description="输出视频路径")
    width: int = Field(default=576, description="输出宽度（像素），默认 576")
    height: int = Field(default=1024, description="输出高度（像素），默认 1024（竖屏 9:16）")
    instance_type: str = Field(default="plus", description="实例类型：default（24G）/ plus（48G）")


class InfiniteTalkV2VTool(BaseTool):
    name: str = "InfiniteTalkV2V视频对口型工具"
    description: str = (
        "使用 InfiniteTalkV2V 模型让视频中的人物根据音频内容对口型说话。"
        "输入一段含人脸的视频和一段音频，输出人物口型与音频完全同步的新视频。"
        "适用于：替换视频配音、让 AI 生成的角色说话、二创配音对口型等场景。"
    )
    args_schema: Type[BaseModel] = InfiniteTalkV2VSchema

    def _run(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        width: int = 576,
        height: int = 1024,
        instance_type: str = "plus",
    ) -> Dict[str, Any]:
        api = InfiniteTalkV2VAPI()
        return api.process(
            video_path=video_path,
            audio_path=audio_path,
            output_path=output_path,
            width=width,
            height=height,
            instance_type=instance_type,
        )


class InfiniteTalkV2VAPI:
    """InfiniteTalkV2V RunningHub API 客户端"""

    def __init__(self):
        self.api_key = os.getenv("RUNNINGHUB_API_KEY")
        if not self.api_key:
            raise ValueError("请设置环境变量 RUNNINGHUB_API_KEY")
        self.auth_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    # ─────────────────── 上传 ───────────────────

    def upload_file(self, file_path: str) -> Optional[str]:
        """上传本地文件，返回 RunningHub 文件名（用于节点参数）"""
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return None

        file_size = os.path.getsize(file_path)
        logger.info(f"📤 正在上传: {Path(file_path).name} ({file_size / 1024:.2f} KB)")

        url = f"{BASE_URL}/task/openapi/upload"
        try:
            with open(file_path, "rb") as f:
                resp = requests.post(
                    url,
                    files={"file": (Path(file_path).name, f)},
                    data={"apiKey": self.api_key},
                    timeout=120,
                )
            if resp.status_code == 200:
                data = resp.json()
                # 支持两种响应格式
                if data.get("code") == 0:
                    file_name = data["data"]["fileName"]
                    logger.info(f"✅ 上传成功: {file_name}")
                    return file_name
                # v2 格式
                if data.get("data", {}).get("fileName"):
                    file_name = data["data"]["fileName"]
                    logger.info(f"✅ 上传成功: {file_name}")
                    return file_name
                logger.error(f"上传失败: {data}")
            else:
                logger.error(f"上传请求失败，状态码: {resp.status_code}, 响应: {resp.text[:200]}")
        except Exception as e:
            logger.error(f"上传异常: {e}")
        return None

    # ─────────────────── 提交任务 ───────────────────

    def submit_task(
        self,
        video_file_name: str,
        audio_file_name: str,
        duration_seconds: int,
        width: int,
        height: int,
        instance_type: str = "plus",
    ) -> Optional[str]:
        """提交 InfiniteTalkV2V AI App 任务，返回 taskId"""
        url = f"{BASE_URL}/openapi/v2/run/ai-app/{APP_ID}"
        payload = {
            "nodeInfoList": [
                {
                    "nodeId": "412",
                    "fieldName": "video",
                    "fieldValue": video_file_name,
                    "description": "Upload video",
                },
                {
                    "nodeId": "407",
                    "fieldName": "audio",
                    "fieldValue": audio_file_name,
                    "description": "Upload audio",
                },
                {
                    "nodeId": "408",
                    "fieldName": "value",
                    "fieldValue": str(duration_seconds),
                    "description": "Duration/seconds",
                },
                {
                    "nodeId": "401",
                    "fieldName": "value",
                    "fieldValue": str(width),
                    "description": "Width",
                },
                {
                    "nodeId": "417",
                    "fieldName": "value",
                    "fieldValue": str(height),
                    "description": "Height",
                },
            ],
            "instanceType": instance_type,
            "usePersonalQueue": "false",
        }
        try:
            logger.info(f"🚀 提交 InfiniteTalkV2V 任务...")
            logger.info(f"   视频: {video_file_name}")
            logger.info(f"   音频: {audio_file_name}")
            logger.info(f"   时长: {duration_seconds}s  尺寸: {width}x{height}  实例: {instance_type}")
            resp = requests.post(url, json=payload, headers=self.auth_headers, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                task_id = data.get("taskId")
                if task_id:
                    logger.info(f"✅ 任务提交成功，taskId: {task_id}")
                    return task_id
                logger.error(f"提交失败，响应: {data}")
            else:
                logger.error(f"提交请求失败，状态码: {resp.status_code}, 响应: {resp.text[:300]}")
        except Exception as e:
            logger.error(f"提交异常: {e}")
        return None

    # ─────────────────── 轮询 ───────────────────

    def poll_task(
        self,
        task_id: str,
        max_wait: int = 7200,
        interval: int = 10,
    ) -> Optional[list]:
        """轮询任务状态，成功后返回 results 列表"""
        url = f"{BASE_URL}/openapi/v2/query"
        start = time.time()
        elapsed_log = 0

        logger.info(f"⏳ 等待任务完成 (taskId: {task_id})...")
        while time.time() - start < max_wait:
            elapsed = int(time.time() - start)
            try:
                resp = requests.post(
                    url,
                    json={"taskId": task_id},
                    headers=self.auth_headers,
                    timeout=30,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status", "")
                    if elapsed - elapsed_log >= 30 or status in ("SUCCESS", "FAILED"):
                        logger.info(f"   [{elapsed}s] 状态: {status}")
                        elapsed_log = elapsed
                    if status == "SUCCESS":
                        logger.info(f"✅ 任务完成！耗时: {elapsed}s")
                        return data.get("results", [])
                    if status == "FAILED":
                        logger.error(f"❌ 任务失败: {data.get('errorMessage', '')}")
                        return None
            except Exception as e:
                logger.warning(f"轮询异常: {e}")
            time.sleep(interval)

        logger.error(f"⏱️ 超时：等待超过 {max_wait}s")
        return None

    # ─────────────────── 下载 ───────────────────

    def download(self, url: str, output_path: str) -> bool:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        try:
            logger.info(f"📥 正在下载: {Path(output_path).name}")
            resp = requests.get(url, stream=True, timeout=600)
            if resp.status_code == 200:
                with open(output_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                size_mb = os.path.getsize(output_path) / 1024 / 1024
                logger.info(f"✅ 下载成功: {output_path} ({size_mb:.2f} MB)")
                return True
            logger.error(f"下载失败，状态码: {resp.status_code}")
        except Exception as e:
            logger.error(f"下载异常: {e}")
        return False

    # ─────────────────── 辅助：获取音频时长 ───────────────────

    @staticmethod
    def get_audio_duration(audio_path: str) -> int:
        """用 ffprobe 获取音频时长（秒，向上取整）"""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    audio_path,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            dur = float(result.stdout.strip())
            import math
            return math.ceil(dur)
        except Exception as e:
            logger.warning(f"无法获取音频时长，使用默认值: {e}")
            return 15  # fallback

    # ─────────────────── 主流程 ───────────────────

    def process(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        width: int = 576,
        height: int = 1024,
        instance_type: str = "plus",
    ) -> Dict[str, Any]:
        logger.info("\n" + "=" * 60)
        logger.info("🎬 InfiniteTalkV2V 视频对口型")
        logger.info("=" * 60)

        try:
            # 1. 上传视频
            logger.info("\n【步骤 1/4】上传视频")
            video_file_name = self.upload_file(video_path)
            if not video_file_name:
                return {"status": "error", "error": "视频上传失败"}

            # 2. 上传音频
            logger.info("\n【步骤 2/4】上传音频")
            audio_file_name = self.upload_file(audio_path)
            if not audio_file_name:
                return {"status": "error", "error": "音频上传失败"}

            # 3. 获取时长 & 提交任务
            logger.info("\n【步骤 3/4】提交任务")
            duration_sec = self.get_audio_duration(audio_path)
            logger.info(f"   音频时长: {duration_sec}s")
            task_id = self.submit_task(
                video_file_name=video_file_name,
                audio_file_name=audio_file_name,
                duration_seconds=duration_sec,
                width=width,
                height=height,
                instance_type=instance_type,
            )
            if not task_id:
                return {"status": "error", "error": "任务提交失败"}

            # 4. 轮询 & 下载
            logger.info("\n【步骤 4/4】等待生成并下载结果")
            results = self.poll_task(task_id)
            if not results:
                return {"status": "error", "error": "任务未成功或无结果"}

            for item in results:
                url = item.get("url") or item.get("fileUrl")
                output_type = item.get("outputType") or item.get("fileType", "")
                if url and output_type in ("mp4", "mov", ""):
                    if self.download(url, output_path):
                        return {
                            "status": "success",
                            "output_path": output_path,
                            "task_id": task_id,
                            "message": "对口型视频已下载到本地路径，远程结果URL已脱敏",
                        }

            return {"status": "error", "error": "结果中无可下载的视频"}

        except Exception as e:
            logger.error(f"处理失败: {e}")
            return {"status": "error", "error": str(e)}
