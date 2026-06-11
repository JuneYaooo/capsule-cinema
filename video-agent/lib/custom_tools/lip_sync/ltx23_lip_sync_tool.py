#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LTX2.3 数字人说话唱歌对口型工具（RunningHub AI App）

输入：人物图（9:16比例更佳）+ 语音/歌曲 → 输出：对口型视频
工作流 App ID: 2031016553440878594
来源：B站艾橘溪
"""

import os
import time
import math
import subprocess
import requests
from typing import Dict, Any, Type, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pathlib import Path

from custom_tools.base_tool import BaseTool
from src.logger import get_logger

load_dotenv()
logger = get_logger("ltx23_lip_sync")

APP_ID = "2031016553440878594"
BASE_URL = "https://www.runninghub.ai"


class LTX23LipSyncSchema(BaseModel):
    image_path: str = Field(
        ..., description="人物图片路径（正面照，9:16 比例效果更佳，jpg/png）"
    )
    audio_path: str = Field(
        ..., description="语音或歌曲文件路径（mp3/wav 等）"
    )
    output_path: str = Field(
        ..., description="输出视频路径（.mp4）"
    )
    action_prompt: str = Field(
        default="一位年轻的中国女人面向镜头深情的说话，环绕推拉运镜。",
        description="动作提示词，描述人物的表情和镜头运动",
    )
    duration_seconds: Optional[int] = Field(
        default=None,
        description="生成时长（秒），建议不超过 35 秒。不填则自动从音频时长推断",
    )
    resolution: int = Field(
        default=1280,
        description="输出分辨率（不超过 1600，越大越慢）",
    )
    frame_rate: int = Field(
        default=30,
        description="帧率",
    )
    instance_type: str = Field(
        default="plus",
        description='实例类型：default（24G 显存）/ plus（48G 显存）',
    )


class LTX23LipSyncTool(BaseTool):
    name: str = "LTX23数字人对口型工具"
    description: str = (
        "使用 LTX2.3 模型让静态人物图片根据音频内容对口型说话/唱歌。"
        "输入一张人物正面照和一段音频，输出人物口型与音频同步的视频。"
        "适用于：数字人播报、虚拟角色说话、AI 角色唱歌、静态图转说话视频等场景。"
        "相比 InfiniteTalkV2V（需要视频输入），本工具只需一张图片即可驱动。"
    )
    args_schema: Type[BaseModel] = LTX23LipSyncSchema

    def _run(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        action_prompt: str = "一位年轻的中国女人面向镜头深情的说话，环绕推拉运镜。",
        duration_seconds: Optional[int] = None,
        resolution: int = 1280,
        frame_rate: int = 30,
        instance_type: str = "plus",
    ) -> Dict[str, Any]:
        api = LTX23LipSyncAPI()
        return api.process(
            image_path=image_path,
            audio_path=audio_path,
            output_path=output_path,
            action_prompt=action_prompt,
            duration_seconds=duration_seconds,
            resolution=resolution,
            frame_rate=frame_rate,
            instance_type=instance_type,
        )


class LTX23LipSyncAPI:
    """LTX2.3 RunningHub API 客户端"""

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
                if data.get("code") == 0:
                    file_name = data["data"]["fileName"]
                    logger.info(f"✅ 上传成功: {file_name}")
                    return file_name
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
        image_file_name: str,
        audio_file_name: str,
        duration_seconds: int,
        action_prompt: str,
        resolution: int,
        frame_rate: int,
        instance_type: str = "plus",
    ) -> Optional[str]:
        """提交 LTX2.3 AI App 任务，返回 taskId"""
        url = f"{BASE_URL}/openapi/v2/run/ai-app/{APP_ID}"
        payload = {
            "nodeInfoList": [
                {
                    "nodeId": "444",
                    "fieldName": "image",
                    "fieldValue": image_file_name,
                    "description": "Character image (front view, 9:16 ratio is better)",
                },
                {
                    "nodeId": "1594",
                    "fieldName": "audio",
                    "fieldValue": audio_file_name,
                    "description": "Upload song or voice",
                },
                {
                    "nodeId": "1583",
                    "fieldName": "value",
                    "fieldValue": str(duration_seconds),
                    "description": "Generate seconds (better effect within 35 seconds)",
                },
                {
                    "nodeId": "1624",
                    "fieldName": "value",
                    "fieldValue": action_prompt,
                    "description": "Action prompt words",
                },
                {
                    "nodeId": "1606",
                    "fieldName": "value",
                    "fieldValue": str(resolution),
                    "description": "Maximum resolution (less than 1600, the larger the slower)",
                },
                {
                    "nodeId": "1586",
                    "fieldName": "value",
                    "fieldValue": str(frame_rate),
                    "description": "Frame rate",
                },
            ],
            "instanceType": instance_type,
            "usePersonalQueue": "false",
        }
        try:
            logger.info(f"🚀 提交 LTX2.3 数字人对口型任务...")
            logger.info(f"   图片: {image_file_name}")
            logger.info(f"   音频: {audio_file_name}")
            logger.info(f"   时长: {duration_seconds}s  分辨率: {resolution}  帧率: {frame_rate}")
            logger.info(f"   动作: {action_prompt[:50]}...")
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
            return math.ceil(dur)
        except Exception as e:
            logger.warning(f"无法获取音频时长，使用默认值: {e}")
            return 10

    # ─────────────────── 主流程 ───────────────────

    def process(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        action_prompt: str = "一位年轻的中国女人面向镜头深情的说话，环绕推拉运镜。",
        duration_seconds: Optional[int] = None,
        resolution: int = 1280,
        frame_rate: int = 30,
        instance_type: str = "plus",
    ) -> Dict[str, Any]:
        logger.info("\n" + "=" * 60)
        logger.info("🎬 LTX2.3 数字人对口型")
        logger.info("=" * 60)

        try:
            # 1. 上传图片
            logger.info("\n【步骤 1/4】上传人物图片")
            image_file_name = self.upload_file(image_path)
            if not image_file_name:
                return {"status": "error", "error": "图片上传失败"}

            # 2. 上传音频
            logger.info("\n【步骤 2/4】上传音频")
            audio_file_name = self.upload_file(audio_path)
            if not audio_file_name:
                return {"status": "error", "error": "音频上传失败"}

            # 3. 获取时长 & 提交任务
            logger.info("\n【步骤 3/4】提交任务")
            if duration_seconds is None:
                duration_seconds = self.get_audio_duration(audio_path)
                logger.info(f"   自动检测音频时长: {duration_seconds}s")
            else:
                logger.info(f"   指定生成时长: {duration_seconds}s")

            task_id = self.submit_task(
                image_file_name=image_file_name,
                audio_file_name=audio_file_name,
                duration_seconds=duration_seconds,
                action_prompt=action_prompt,
                resolution=resolution,
                frame_rate=frame_rate,
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
