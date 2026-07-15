#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wan2.2数字人对口型CrewAI工具
使用RunningHub API上传图片和音频，生成Wan2.2数字人对口型视频
"""

import os
import time
import requests
from typing import Dict, Any, Type, Optional
from urllib.parse import urlparse
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from custom_tools.base_tool import BaseTool
from pathlib import Path
import subprocess
import json

from src.logger import get_logger

# 加载环境变量
load_dotenv()

# 初始化日志
logger = get_logger("wan22_lip_sync")


class Wan22LipSyncSchema(BaseModel):
    """Wan2.2数字人对口型工具的输入参数"""
    image_path: str = Field(
        ...,
        description="输入人物图片的路径，支持jpg、png等格式"
    )
    audio_path: str = Field(
        ...,
        description="输入音频文件的路径，支持mp3、wav等格式"
    )
    output_path: str = Field(
        ...,
        description="输出视频文件的保存路径"
    )
    max_edge: int = Field(
        default=832,
        description="视频最长边（像素）"
    )
    action_prompt: str = Field(
        default="说话",
        description="人物动作提示词（简单点）"
    )


class Wan22LipSyncTool(BaseTool):
    name: str = "Wan2.2数字人对口型工具"
    description: str = (
        "使用Wan2.2模型生成数字人对口型视频的工具。输入人物图片和音频文件，"
        "可以生成人物根据音频内容进行对口型说话的视频，并支持添加动作提示。"
        "适用于数字人视频、虚拟主播、教学视频等场景。"
    )
    args_schema: Type[BaseModel] = Wan22LipSyncSchema

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _run(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        max_edge: int = 832,
        action_prompt: str = "说话"
    ) -> str:
        """
        执行Wan2.2数字人对口型生成

        Args:
            image_path: 输入图片路径
            audio_path: 输入音频路径
            output_path: 输出视频路径
            max_edge: 视频最长边
            action_prompt: 人物动作提示词

        Returns:
            生成结果的描述信息
        """
        try:
            # 初始化API客户端
            api = Wan22LipSyncAPI()

            # 执行对口型生成
            result = api.process(
                image_path=image_path,
                audio_path=audio_path,
                output_path=output_path,
                max_edge=max_edge,
                action_prompt=action_prompt
            )

            if result['success']:
                return f"✅ Wan2.2数字人对口型生成成功！视频已保存到: {result['output_path']}"
            else:
                return f"❌ Wan2.2数字人对口型生成失败: {result['error']}"

        except Exception as e:
            logger.error(f"Wan2.2数字人对口型生成失败: {str(e)}")
            return f"❌ Wan2.2数字人对口型生成失败: {str(e)}"


class Wan22LipSyncAPI:
    """Wan2.2数字人对口型API调用类"""

    def __init__(self):
        self.api_key = os.getenv('WAN22_API_KEY') or os.getenv('RUNNINGHUB_API_KEY')
        if not self.api_key:
            raise ValueError("请设置环境变量 WAN22_API_KEY 或 RUNNINGHUB_API_KEY")
        self.webapp_id = os.getenv('WAN22_WEBAPP_ID', '1983409117538787329')
        self.base_url = "https://www.runninghub.cn"
        self.headers = {
            "Host": "www.runninghub.cn",
            "Content-Type": "application/json"
        }

    def get_audio_duration(self, audio_path: str) -> Optional[float]:
        """
        获取音频文件时长，最长支持5分钟

        Args:
            audio_path: 音频文件路径

        Returns:
            音频时长（秒），如果失败返回 None
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'json',
                audio_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                data = json.loads(result.stdout)
                duration = float(data['format']['duration'])

                # 最长支持5分钟（300秒）
                max_duration = 300.0
                if duration > max_duration:
                    logger.warning(f"⚠️ 音频时长 {duration:.2f} 秒超过最大限制 {max_duration:.2f} 秒，将自动截断")
                    duration = max_duration

                logger.info(f"✅ 音频时长: {duration:.2f} 秒")
                return duration
            else:
                logger.error(f"获取音频时长失败: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"获取音频时长异常: {str(e)}")
            return None

    def format_end_time(self, duration_seconds: float) -> str:
        """
        将秒数转换为 end_time 格式（0:20表示20秒）

        Args:
            duration_seconds: 时长（秒）

        Returns:
            格式化的时间字符串
        """
        import math
        # 向上取整，确保视频时长足够覆盖整个音频
        total_seconds = math.ceil(duration_seconds)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds}"

    def upload_file(self, file_path: str) -> Optional[str]:
        """
        上传文件（图片或音频）

        Args:
            file_path: 文件路径

        Returns:
            上传后的文件名，如果失败返回 None
        """
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return None

        # 检查文件大小
        file_size = os.path.getsize(file_path)
        if file_size > 30 * 1024 * 1024:  # 30MB
            logger.error(f"文件大小超过30MB限制: {file_size / 1024 / 1024:.2f}MB")
            return None

        url = f"{self.base_url}/task/openapi/upload"

        try:
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f)}
                # 上传接口需要传递 apiKey 参数
                data = {'apiKey': self.api_key}
                upload_headers = {"Host": "www.runninghub.cn"}

                logger.info(f"📤 正在上传: {os.path.basename(file_path)} ({file_size / 1024:.2f}KB)")
                response = requests.post(url, files=files, data=data, headers=upload_headers)

                if response.status_code == 200:
                    result = response.json()
                    if result.get('code') == 0:
                        file_name = result['data']['fileName']
                        logger.info(f"✅ 上传成功: {file_name}")
                        return file_name
                    else:
                        logger.error(f"上传失败: {result.get('msg')}")
                        return None
                else:
                    logger.error(f"上传请求失败，状态码: {response.status_code}")
                    return None

        except Exception as e:
            logger.error(f"上传异常: {str(e)}")
            return None

    def create_wan22_task(self, image_file_name: str, audio_file_name: str,
                         end_time: str, max_edge: int, action_prompt: str) -> Optional[str]:
        """
        创建Wan2.2数字人对口型任务

        Args:
            image_file_name: 上传后的图片文件名
            audio_file_name: 上传后的音频文件名
            end_time: 视频结束时间（格式：0:20表示20秒）
            max_edge: 视频最长边（像素）
            action_prompt: 人物动作提示词

        Returns:
            任务ID，如果失败返回 None
        """
        url = f"{self.base_url}/task/openapi/ai-app/run"

        payload = {
            "webappId": self.webapp_id,
            "apiKey": self.api_key,
            "nodeInfoList": [
                {
                    "nodeId": "221",
                    "fieldName": "end_time",
                    "fieldValue": end_time,
                    "description": "视频结束时间（按照格式填写）（0:20表示20s）"
                },
                {
                    "nodeId": "126",
                    "fieldName": "image",
                    "fieldValue": image_file_name,
                    "description": "加载图片"
                },
                {
                    "nodeId": "185",
                    "fieldName": "audio",
                    "fieldValue": audio_file_name,
                    "description": "加载音频"
                },
                {
                    "nodeId": "218",
                    "fieldName": "value",
                    "fieldValue": str(max_edge),
                    "description": "视频最长边"
                },
                {
                    "nodeId": "141",
                    "fieldName": "prompt",
                    "fieldValue": action_prompt,
                    "description": "输入人物动作提示词（简单点）"
                }
            ]
        }

        try:
            logger.info("🚀 正在创建Wan2.2任务...")
            response = requests.post(url, json=payload, headers=self.headers, timeout=60)

            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    task_id = result['data']['taskId']
                    logger.info(f"✅ 任务创建成功，任务ID: {task_id}")
                    logger.info(f"   状态: {result['data'].get('taskStatus')}")
                    return task_id
                else:
                    logger.error(f"任务创建失败: {result.get('msg')}")
                    return None
            else:
                logger.error(f"请求失败，状态码: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"创建任务异常: {str(e)}")
            return None

    def check_task_status(self, task_id: str) -> tuple[Optional[str], Optional[dict]]:
        """
        查询任务状态

        Args:
            task_id: 任务ID

        Returns:
            tuple: (状态字符串, 完整响应数据)
        """
        url = f"{self.base_url}/task/openapi/status"

        payload = {
            "apiKey": self.api_key,
            "taskId": str(task_id)
        }

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=60)

            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    return result.get('data'), result

        except Exception as e:
            logger.error(f"查询状态异常: {str(e)}")

        return None, None

    def get_task_outputs(self, task_id: str) -> Optional[list]:
        """
        获取任务生成结果

        Args:
            task_id: 任务ID

        Returns:
            输出结果列表
        """
        url = f"{self.base_url}/task/openapi/outputs"

        payload = {
            "apiKey": self.api_key,
            "taskId": str(task_id)
        }

        try:
            response = requests.post(url, json=payload, headers=self.headers)

            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    return result.get('data', [])
                else:
                    logger.error(f"获取结果失败: {result.get('msg')}")

        except Exception as e:
            logger.error(f"获取结果异常: {str(e)}")

        return None

    def wait_for_completion(self, task_id: str, max_wait_time: int =3600,
                           check_interval: int = 5) -> bool:
        """
        等待任务完成

        Args:
            task_id: 任务ID
            max_wait_time: 最大等待时间（秒）
            check_interval: 检查间隔（秒）

        Returns:
            任务是否成功完成
        """
        start_time = time.time()
        last_status = None

        logger.info(f"⏳ 等待任务完成...")

        while time.time() - start_time < max_wait_time:
            status, _full_response = self.check_task_status(task_id)

            if status != last_status:
                logger.info(f"   当前状态: {status}")
                last_status = status

            if status == "SUCCESS":
                elapsed_time = int(time.time() - start_time)
                logger.info(f"✅ 任务完成！耗时: {elapsed_time}秒")
                return True
            elif status == "FAILED":
                logger.error("任务失败（远程响应已脱敏；仅保留任务状态）")
                return False

            time.sleep(check_interval)

        logger.warning(f"⏱️ 超时：等待时间超过 {max_wait_time} 秒")
        return False

    def download_file(self, url: str, output_path: str) -> bool:
        """
        下载文件到指定目录

        Args:
            url: 文件URL
            output_path: 输出路径

        Returns:
            是否下载成功
        """
        try:
            # 确保输出目录存在
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            logger.info(f"📥 正在下载: {os.path.basename(output_path)}")

            # 下载文件
            response = requests.get(url, stream=True, timeout=300)
            if response.status_code == 200:
                total_size = int(response.headers.get('content-length', 0))

                with open(output_path, 'wb') as f:
                    if total_size == 0:
                        f.write(response.content)
                    else:
                        downloaded = 0
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                # 显示进度
                                percent = (downloaded / total_size) * 100
                                logger.info(f"\r   进度: {percent:.1f}% ({downloaded / 1024 / 1024:.2f}MB / {total_size / 1024 / 1024:.2f}MB)")

                logger.info(f"✅ 下载成功: {output_path}")
                return True
            else:
                logger.error(f"下载失败，状态码: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"下载异常: {str(e)}")
            return False

    def process(self, image_path: str, audio_path: str, output_path: str,
                max_edge: int = 832, action_prompt: str = "说话") -> Dict[str, Any]:
        """
        完整的处理流程

        Args:
            image_path: 输入图片路径
            audio_path: 输入音频路径
            output_path: 输出视频路径
            max_edge: 视频最长边
            action_prompt: 人物动作提示词

        Returns:
            处理结果字典
        """
        logger.info(f"\n{'='*60}")
        logger.info("🎬 Wan2.2数字人对口型视频生成")
        logger.info(f"{'='*60}")

        try:
            # 0. 获取音频时长并计算 end_time
            logger.info("\n【步骤 0/4】获取音频时长")
            duration = self.get_audio_duration(audio_path)
            if not duration:
                return {'success': False, 'error': '无法获取音频时长'}

            # 格式化为 end_time
            end_time = self.format_end_time(duration)
            logger.info(f"✅ 自动设置视频时长: {end_time} ({duration:.2f}秒)")

            # 1. 上传图片
            logger.info("\n【步骤 1/4】上传图片")
            image_file_name = self.upload_file(image_path)
            if not image_file_name:
                return {'success': False, 'error': '图片上传失败'}

            # 2. 上传音频
            logger.info("\n【步骤 2/4】上传音频")
            audio_file_name = self.upload_file(audio_path)
            if not audio_file_name:
                return {'success': False, 'error': '音频上传失败'}

            # 3. 创建任务
            logger.info("\n【步骤 3/4】创建Wan2.2数字人对口型任务")
            logger.info(f"   参数设置:")
            logger.info(f"   - 视频结束时间: {end_time}")
            logger.info(f"   - 视频最长边: {max_edge}px")
            logger.info(f"   - 动作提示词: {action_prompt}")

            task_id = self.create_wan22_task(
                image_file_name=image_file_name,
                audio_file_name=audio_file_name,
                end_time=end_time,
                max_edge=max_edge,
                action_prompt=action_prompt
            )

            if not task_id:
                return {'success': False, 'error': '任务创建失败'}

            # 4. 等待任务完成
            logger.info("\n【步骤 4/4】等待任务完成")
            success = self.wait_for_completion(task_id, max_wait_time=3600, check_interval=5)

            if not success:
                return {'success': False, 'error': '任务未成功完成'}

            # 5. 获取结果
            logger.info("\n【获取结果】")
            outputs = self.get_task_outputs(task_id)

            if outputs:
                logger.info(f"✅ 生成了 {len(outputs)} 个文件")

                for i, output in enumerate(outputs, 1):
                    logger.info(f"\n文件 {i}:")
                    logger.info(f"  类型: {output.get('fileType')}")
                    logger.info(f"  远程结果: {'present' if output.get('fileUrl') else 'missing'}")
                    logger.info(f"  耗时: {output.get('taskCostTime')}秒")

                    # 下载文件
                    file_url = output.get('fileUrl')
                    if file_url:
                        if self.download_file(file_url, output_path):
                            return {
                                'success': True,
                                'output_path': output_path,
                                'duration': duration
                            }

            return {'success': False, 'error': '未获取到结果'}

        except Exception as e:
            logger.error(f"处理失败: {str(e)}")
            return {'success': False, 'error': str(e)}
