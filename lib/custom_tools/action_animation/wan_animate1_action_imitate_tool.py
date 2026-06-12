#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WanAnimate1动作模仿CrewAI工具
使用RunningHub API上传参考图片和视频，生成动作模仿视频
"""

import os
import re
import time
import requests
from typing import Dict, Any, Type, Optional
from urllib.parse import urlparse
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from custom_tools.base_tool import BaseTool
from pathlib import Path

from src.logger import get_logger

# 加载环境变量
load_dotenv()

# 初始化日志
logger = get_logger("wan_animate1_action_imitate")


class WanAnimate1ActionImitateSchema(BaseModel):
    """WanAnimate1动作模仿工具的输入参数"""
    image_path: str = Field(
        ...,
        description="要替换的角色/人物图片路径"
    )
    video_path: str = Field(
        ...,
        description="参考视频路径（动作来源）"
    )
    output_dir: str = Field(
        default="output/videos",
        description="生成视频的保存目录（当output_path未提供时使用）"
    )
    output_path: Optional[str] = Field(
        default=None,
        description="完整的输出文件路径（优先使用，如果提供则忽略output_dir）"
    )
    frame_rate: int = Field(
        default=25,
        description="帧率（选16或25）"
    )
    duration: int = Field(
        default=4,
        description="总时长（秒）"
    )
    skip: int = Field(
        default=0,
        description="跳过（秒）"
    )
    width: int = Field(
        default=1080,
        description="视频宽度"
    )
    height: int = Field(
        default=1920,
        description="视频高度"
    )


class WanAnimate1ActionImitateTool(BaseTool):
    name: str = "WanAnimate1动作模仿工具"
    description: str = (
        "使用WanAnimate1 API生成动作模仿视频的工具。"
        "上传参考图片和视频，将图片中的角色替换到视频的动作中。"
        "适合生成人物动作迁移、舞蹈模仿等创意视频内容。"
    )
    args_schema: Type[BaseModel] = WanAnimate1ActionImitateSchema

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _run(
        self,
        image_path: str,
        video_path: str,
        output_dir: str = "output/videos",
        output_path: Optional[str] = None,
        frame_rate: int = 25,
        duration: int = 4,
        skip: int = 0,
        width: int = 1080,
        height: int = 1920
    ) -> Dict[str, Any]:
        """
        执行WanAnimate1动作模仿

        Args:
            image_path: 角色图片路径
            video_path: 参考视频路径
            output_dir: 输出目录（当output_path未提供时使用）
            output_path: 完整的输出文件路径（优先使用）
            frame_rate: 帧率
            duration: 总时长
            skip: 跳过秒数
            width: 视频宽度
            height: 视频高度

        Returns:
            生成结果的字典
        """
        try:
            # 初始化API客户端
            client = WanAnimate1ApiClient(output_dir=output_dir)

            # 执行动作模仿
            video_output_path = client.action_imitate(
                image_path=image_path,
                video_path=video_path,
                output_path=output_path,
                frame_rate=frame_rate,
                duration=duration,
                skip=skip,
                width=width,
                height=height
            )

            if video_output_path:
                return {
                    "output_path": video_output_path,
                    "status": "success",
                    "message": f"✅ WanAnimate1动作模仿成功！视频已保存到: {video_output_path}"
                }
            else:
                return {
                    "status": "failed",
                    "message": "❌ WanAnimate1动作模仿失败"
                }

        except Exception as e:
            logger.error(f"WanAnimate1动作模仿失败: {str(e)}")
            return {
                "status": "failed",
                "message": f"❌ WanAnimate1动作模仿失败: {str(e)}"
            }


class WanAnimate1ApiClient:
    """WanAnimate1 API客户端"""

    def __init__(self, output_dir: str = "output/videos"):
        """初始化API客户端"""
        self.api_key = os.getenv('WANANIMATE1_API_KEY') or os.getenv('RUNNINGHUB_API_KEY')
        if not self.api_key:
            raise ValueError("请设置环境变量 WANANIMATE1_API_KEY 或 RUNNINGHUB_API_KEY")
        self.webapp_id = os.getenv('WANANIMATE1_WEBAPP_ID', '1971504342157213697')
        self.base_url = "https://www.runninghub.cn"
        self.headers = {
            "Host": "www.runninghub.cn",
            "Content-Type": "application/json"
        }

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def upload_file(self, file_path: str) -> Optional[str]:
        """
        上传文件（图片或视频）

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
                data = {'apiKey': self.api_key}
                upload_headers = {"Host": "www.runninghub.cn"}

                logger.info(f"📤 正在上传: {os.path.basename(file_path)} ({file_size / 1024:.2f}KB)")
                response = requests.post(url, files=files, data=data, headers=upload_headers, timeout=120)

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

    def create_task(
        self,
        image_file_name: str,
        video_file_name: str,
        frame_rate: int = 25,
        duration: int = 4,
        skip: int = 0,
        width: int = 1080,
        height: int = 1920
    ) -> Optional[str]:
        """
        创建动作模仿任务

        Args:
            image_file_name: 上传后的图片文件名
            video_file_name: 上传后的视频文件名
            frame_rate: 帧率（16或25）
            duration: 总时长（秒）
            skip: 跳过（秒）
            width: 宽度
            height: 高度

        Returns:
            任务ID，如果失败返回 None
        """
        url = f"{self.base_url}/task/openapi/ai-app/run"

        payload = {
            "webappId": self.webapp_id,
            "apiKey": self.api_key,
            "nodeInfoList": [
                {
                    "nodeId": "257",
                    "fieldName": "value",
                    "fieldValue": str(frame_rate),
                    "description": "帧率（选16或25）"
                },
                {
                    "nodeId": "255",
                    "fieldName": "value",
                    "fieldValue": str(duration),
                    "description": "总时长（秒）"
                },
                {
                    "nodeId": "254",
                    "fieldName": "value",
                    "fieldValue": str(skip),
                    "description": "跳过（秒）"
                },
                {
                    "nodeId": "52",
                    "fieldName": "video",
                    "fieldValue": video_file_name,
                    "description": "参考视频"
                },
                {
                    "nodeId": "167",
                    "fieldName": "image",
                    "fieldValue": image_file_name,
                    "description": "要替换的角色/人物"
                },
                {
                    "nodeId": "264",
                    "fieldName": "value",
                    "fieldValue": str(width),
                    "description": "宽度"
                },
                {
                    "nodeId": "265",
                    "fieldName": "value",
                    "fieldValue": str(height),
                    "description": "高度"
                }
            ]
        }

        try:
            logger.info("🚀 正在创建任务...")
            logger.info(
                f"📋 API请求参数: webappId={self.webapp_id}, "
                f"nodes={len(payload['nodeInfoList'])}, instance=default"
            )

            response = requests.post(url, json=payload, headers=self.headers, timeout=30)

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

    def check_task_status(self, task_id: str) -> Optional[str]:
        """
        查询任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务状态字符串
        """
        url = f"{self.base_url}/task/openapi/status"

        payload = {
            "apiKey": self.api_key,
            "taskId": str(task_id)
        }

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)

            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    return result.get('data')

        except Exception as e:
            logger.warning(f"查询状态异常（将在下次轮询重试）: {str(e)}")

        return None

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
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)

            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    return result.get('data', [])
                else:
                    logger.error(f"获取结果失败: {result.get('msg')}")

        except Exception as e:
            logger.error(f"获取结果异常: {str(e)}")

        return None

    def wait_for_completion(
        self,
        task_id: str,
        max_wait_time: int = 7200,
        check_interval: int = 5
    ) -> bool:
        """
        等待任务完成

        Args:
            task_id: 任务ID
            max_wait_time: 最大等待时间（秒），默认2小时
            check_interval: 检查间隔（秒）

        Returns:
            任务是否成功完成
        """
        start_time = time.time()
        last_status = None

        logger.info(f"⏳ 等待任务完成...")

        while time.time() - start_time < max_wait_time:
            status = self.check_task_status(task_id)

            if status != last_status:
                logger.info(f"   当前状态: {status}")
                last_status = status

            if status == "SUCCESS":
                elapsed_time = int(time.time() - start_time)
                logger.info(f"✅ 任务完成！耗时: {elapsed_time}秒")
                return True
            elif status == "FAILED":
                logger.error(f"任务失败")
                return False

            time.sleep(check_interval)

        logger.warning(f"⏱️ 超时：等待时间超过 {max_wait_time} 秒")
        return False

    def download_file(self, url: str, output_path: str) -> bool:
        """
        下载文件到指定路径

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

                file_size = os.path.getsize(output_path)
                logger.info(f"✅ 下载成功: {output_path} ({file_size / (1024*1024):.2f} MB)")
                return True
            else:
                logger.error(f"下载失败，状态码: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"下载异常: {str(e)}")
            return False

    def action_imitate(
        self,
        image_path: str,
        video_path: str,
        output_path: Optional[str] = None,
        frame_rate: int = 25,
        duration: int = 4,
        skip: int = 0,
        width: int = 1080,
        height: int = 1920
    ) -> Optional[str]:
        """
        动作模仿功能

        Args:
            image_path: 角色图片路径
            video_path: 参考视频路径
            output_path: 自定义输出路径（可选）
            frame_rate: 帧率
            duration: 总时长
            skip: 跳过秒数
            width: 视频宽度
            height: 视频高度

        Returns:
            生成的视频文件路径，失败返回None
        """
        logger.info(f"\n{'='*60}")
        logger.info("🎬 WanAnimate1 动作模仿 (Action Imitate)")
        logger.info(f"{'='*60}")
        logger.info(f"🖼️  输入图片: {image_path}")
        logger.info(f"🎥 参考视频: {video_path}")

        start_time = time.time()
        try:
            # 1. 上传图片
            logger.info("\n【步骤 1/5】上传参考图片")
            image_file_name = self.upload_file(image_path)
            if not image_file_name:
                logger.error("图片上传失败")
                return None

            # 2. 上传视频
            logger.info("\n【步骤 2/5】上传参考视频")
            video_file_name = self.upload_file(video_path)
            if not video_file_name:
                logger.error("视频上传失败")
                return None

            # 3. 创建任务
            logger.info("\n【步骤 3/5】创建动作模仿任务")
            logger.info(f"   参数设置:")
            logger.info(f"   - 帧率: {frame_rate}")
            logger.info(f"   - 时长: {duration}秒")
            logger.info(f"   - 跳过: {skip}秒")
            logger.info(f"   - 分辨率: {width}x{height}")

            task_id = self.create_task(
                image_file_name=image_file_name,
                video_file_name=video_file_name,
                frame_rate=frame_rate,
                duration=duration,
                skip=skip,
                width=width,
                height=height
            )

            if not task_id:
                logger.error("任务创建失败")
                return None

            # 4. 等待任务完成
            logger.info("\n【步骤 4/5】等待任务完成")
            success = self.wait_for_completion(task_id, max_wait_time=7200, check_interval=10)

            if not success:
                logger.error("任务未成功完成")
                return None

            # 5. 获取结果
            logger.info("\n【步骤 5/5】获取结果并下载")
            outputs = self.get_task_outputs(task_id)

            if outputs and len(outputs) > 0:
                output = outputs[0]
                file_url = output.get('fileUrl')

                if file_url:
                    # 确定输出文件路径
                    if output_path:
                        output_file = output_path
                    else:
                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                        output_file = self.output_dir / f"action_imitate_{timestamp}.mp4"

                    # 下载视频
                    if self.download_file(file_url, str(output_file)):
                        elapsed_time = time.time() - start_time
                        logger.info(f"\n✅ 动作模仿成功！总耗时: {elapsed_time:.2f}秒")
                        return str(output_file)
                else:
                    logger.error("未获取到视频URL")
            else:
                logger.error("未获取到结果")

            return None

        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"\n❌ 动作模仿失败 (耗时: {elapsed_time:.2f} 秒): {e}")
            import traceback
            traceback.print_exc()
            return None
