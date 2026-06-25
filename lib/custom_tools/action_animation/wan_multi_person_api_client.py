#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RunningHub 多人动作模仿 API 客户端
封装 RunningHub Workflow API 的上传、运行、查询、下载功能
"""

import os
import re
import time
import requests
from typing import Dict, Any, Optional
from pathlib import Path

from src.logger import get_logger

logger = get_logger("wan_multi_person_api_client")


def _redact_sensitive(value: Any, max_len: int = 500) -> str:
    text = str(value)
    text = re.sub(r"https?://[^\s'\"<>]+", "<url redacted>", text)
    text = re.sub(r"(Bearer\s+)[^\s,;]+", r"\1<redacted>", text)
    text = re.sub(r"((?:api[_-]?key|token)[\"':=\s]+)[^,'\"\s}]+", r"\1<redacted>", text, flags=re.I)
    return text if len(text) <= max_len else f"{text[:max_len]}..."


class WanMultiPersonApiClient:
    """多人动作模仿 API客户端 (RunningHub Workflow API)"""

    # 多人动作模仿的工作流 ID (.ai 域名)
    WORKFLOW_ID = "2014675474420604929"

    # 正确的节点 ID（从工作流 JSON 中获取）
    IMAGE_NODE_ID = "106"  # LoadImage 节点
    VIDEO_NODE_ID = "130"  # VHS_LoadVideo 节点
    PROMPT_NODE_ID = "368"  # WanVideoTextEncodeCached 节点

    def __init__(self, output_dir: str = "output/videos"):
        """初始化API客户端"""
        self.api_key = os.getenv('RUNNINGHUB_API_KEY')
        if not self.api_key:
            raise ValueError("请设置环境变量 RUNNINGHUB_API_KEY")

        # 统一使用 .ai 域名
        self.base_url = "https://www.runninghub.ai"

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 尝试初始化七牛云客户端作为备用上传方案
        self.qiniu_client = None
        try:
            from custom_tools.utilities.qiniu_storage_tool import QiniuStorageClient
            self.qiniu_client = QiniuStorageClient()
        except Exception as e:
            logger.warning(f"七牛云客户端初始化失败，将不使用备用上传: {e}")

    def upload_file(self, file_path: str, max_retries: int = 3) -> Optional[str]:
        """
        上传文件（图片或视频）- 使用 .ai 域名的 /task/openapi/upload 接口

        Args:
            file_path: 文件路径
            max_retries: 最大重试次数

        Returns:
            上传后的文件名，如果失败返回 None
        """
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return None

        # 检查文件大小
        file_size = os.path.getsize(file_path)
        if file_size > 100 * 1024 * 1024:  # 100MB
            logger.error(f"文件大小超过100MB限制: {file_size / 1024 / 1024:.2f}MB")
            return None

        # 使用 .ai 域名的 /task/openapi/upload 接口
        url = f"{self.base_url}/task/openapi/upload"

        for attempt in range(max_retries):
            try:
                with open(file_path, 'rb') as f:
                    files = {'file': (os.path.basename(file_path), f)}
                    # 上传接口需要传递 apiKey 参数（表单方式）
                    data = {'apiKey': self.api_key}

                    retry_info = f" (重试 {attempt + 1}/{max_retries})" if attempt > 0 else ""
                    logger.info(f"📤 正在上传: {os.path.basename(file_path)} ({file_size / 1024:.2f}KB){retry_info}")
                    response = requests.post(url, files=files, data=data, timeout=120)

                    if response.status_code == 200:
                        result = response.json()

                        # 检查响应格式
                        if result.get('code') == 0:
                            file_name = result['data']['fileName']
                            logger.info(f"✅ 上传成功: {file_name}")
                            return file_name
                        else:
                            error_msg = result.get('msg', '未知错误')
                            logger.warning(f"API 返回错误: {error_msg}")
                            if attempt < max_retries - 1:
                                time.sleep(3)
                                continue
                            # 上传失败，尝试七牛云
                            break
                    else:
                        logger.warning(
                            f"上传请求失败，状态码: {response.status_code}, "
                            f"响应: {_redact_sensitive(response.text)}"
                        )
                        if attempt < max_retries - 1:
                            time.sleep(3)
                            continue
                        # 上传失败，尝试七牛云
                        break

            except Exception as e:
                logger.warning(f"上传异常: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
                # 上传失败，尝试七牛云
                break

        # RunningHub 上传失败，尝试使用七牛云作为备用方案
        if self.qiniu_client:
            logger.info("🔄 RunningHub 上传失败，尝试使用七牛云上传...")
            return self._upload_to_qiniu(file_path)
        else:
            logger.error("RunningHub 上传失败，且七牛云备用方案不可用")
            return None

    def _upload_to_qiniu(self, file_path: str) -> Optional[str]:
        """
        上传文件到七牛云

        Args:
            file_path: 文件路径

        Returns:
            文件的公开URL，如果失败返回 None
        """
        if not self.qiniu_client:
            return None

        try:
            # 确定文件类型
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                subdir = "images"
            elif ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
                subdir = "videos"
            else:
                subdir = "data"

            result = self.qiniu_client.upload_file(
                local_file_path=file_path,
                workflow_type="action_transfer",
                subdir=subdir
            )

            if result.get("success"):
                # 返回公开URL (七牛云的 public_url)
                public_url = result.get("public_url")
                logger.info("✅ 七牛云上传成功: <remote media url redacted>")
                return public_url
            else:
                error = result.get("error", "未知错误")
                if result.get("skipped"):
                    logger.warning(f"七牛云上传已禁用: {error}")
                else:
                    logger.error(f"七牛云上传失败: {error}")
                return None

        except Exception as e:
            logger.error(f"七牛云上传异常: {str(e)}")
            return None

    def run_workflow(
        self,
        image_file_name: str,
        video_file_name: str,
        instance_type: str = "plus",
        width: int = 576,
        height: int = 1024,
        positive_prompt: Optional[str] = None,
        add_metadata: bool = False,
    ) -> Optional[str]:
        """
        运行工作流 - 使用 .ai 域名的 v2 API

        Args:
            image_file_name: 上传后的图片文件名
            video_file_name: 上传后的视频文件名
            instance_type: 实例类型 (default: 24G显存, plus: 48G显存)
            width: 输出视频宽度（像素），默认 576
            height: 输出视频高度（像素），默认 1024
            positive_prompt: 覆盖工作流默认正向提示词，避免使用模板示例 prompt
            add_metadata: 是否让 RunningHub 写入完整 workflow metadata，默认关闭以避免落盘远端URL

        Returns:
            任务ID，如果失败返回 None
        """
        # 检查是否是URL（七牛云上传的结果）- 不支持外部URL
        is_url_input = image_file_name.startswith('http') or video_file_name.startswith('http')

        if is_url_input:
            logger.error("❌ 检测到外部URL输入，RunningHub工作流不支持外部URL")
            logger.error("❌ 请确保文件上传成功后再运行工作流")
            return None

        # 使用 .ai 域名的 v2 API 运行工作流
        url = f"{self.base_url}/openapi/v2/run/workflow/{self.WORKFLOW_ID}"

        # 使用正确的节点 ID，节点 203=width, 204=height
        node_info_list = [
            {"nodeId": self.IMAGE_NODE_ID, "fieldName": "image", "fieldValue": image_file_name},
            {"nodeId": self.VIDEO_NODE_ID, "fieldName": "video", "fieldValue": video_file_name},
            {"nodeId": "203", "fieldName": "value", "fieldValue": width},
            {"nodeId": "204", "fieldName": "value", "fieldValue": height},
        ]
        if positive_prompt:
            node_info_list.append(
                {
                    "nodeId": self.PROMPT_NODE_ID,
                    "fieldName": "positive_prompt",
                    "fieldValue": positive_prompt,
                }
            )

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "addMetadata": add_metadata,
            "nodeInfoList": node_info_list,
            "instanceType": instance_type,
            "usePersonalQueue": "false"
        }

        try:
            logger.info(f"🚀 运行多人动作模仿工作流...")
            logger.info(f"   图片节点 {self.IMAGE_NODE_ID}: {image_file_name}")
            logger.info(f"   视频节点 {self.VIDEO_NODE_ID}: {video_file_name}")
            logger.info(f"   分辨率: {width}x{height}")
            if positive_prompt:
                logger.info(f"   提示词节点 {self.PROMPT_NODE_ID}: 已覆盖")
            import json
            logger.debug(f"📋 API请求参数:\n{json.dumps(payload, ensure_ascii=False, indent=2)}")

            response = requests.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                result = response.json()
                task_id = result.get('taskId')
                status = result.get('status')
                error_message = result.get('errorMessage')
                prompt_tips = result.get('promptTips')

                logger.info(f"   Task ID: {task_id}")
                logger.info(f"   Status: {status}")
                if error_message:
                    logger.info(f"   Error Message: {error_message}")
                if prompt_tips:
                    logger.info(f"   Prompt Tips: {prompt_tips}")

                if task_id:
                    logger.info(f"✅ 工作流启动成功，任务ID: {task_id}")
                    return task_id
                else:
                    error_msg = error_message or result.get('msg', '未知错误')
                    logger.error(f"工作流启动失败: {error_msg}")
                    return None
            else:
                logger.error(
                    f"请求失败，状态码: {response.status_code}, 响应: {_redact_sensitive(response.text)}"
                )
                return None

        except Exception as e:
            logger.error(f"运行工作流异常: {str(e)}")
            return None

    def query_task(self, task_id: str) -> Dict[str, Any]:
        """
        查询任务状态 - 使用 .ai 域名的 v2 API

        Args:
            task_id: 任务ID

        Returns:
            任务状态和结果
        """
        url = f"{self.base_url}/openapi/v2/query"

        payload = {
            "taskId": task_id
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        try:
            response = requests.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"查询失败，状态码: {response.status_code}")
                return {}

        except Exception as e:
            logger.error(f"查询异常: {str(e)}")
            return {}

    def wait_for_completion(
        self,
        task_id: str,
        max_wait_time: int = 7200,
        check_interval: int = 10
    ) -> Optional[Dict[str, Any]]:
        """
        等待任务完成

        Args:
            task_id: 任务ID
            max_wait_time: 最大等待时间（秒），默认2小时
            check_interval: 检查间隔（秒）

        Returns:
            任务结果，如果失败返回 None
        """
        start_time = time.time()
        last_status = None

        logger.info(f"⏳ 等待任务完成 (Task ID: {task_id})...")

        while time.time() - start_time < max_wait_time:
            result = self.query_task(task_id)
            status = result.get('status')

            if status != last_status:
                elapsed = int(time.time() - start_time)
                logger.info(f"   [{elapsed}s] 状态: {status}")
                last_status = status

            if status == "SUCCESS":
                elapsed_time = int(time.time() - start_time)
                logger.info(f"✅ 任务完成！耗时: {elapsed_time}秒")
                return result
            elif status == "FAILED":
                error_msg = result.get('errorMessage', '未知错误')
                failed_reason = result.get('failedReason', {})
                logger.error(f"任务失败: {error_msg}")
                logger.error(f"失败原因: {failed_reason}")
                return None

            time.sleep(check_interval)

        logger.warning(f"⏱️ 超时：等待时间超过 {max_wait_time} 秒")
        return None

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
        instance_type: str = "plus",
        width: int = 576,
        height: int = 1024,
        positive_prompt: Optional[str] = None,
        add_metadata: bool = False,
    ) -> Optional[str]:
        """
        多人动作模仿功能

        Args:
            image_path: 角色图片路径
            video_path: 参考视频路径
            output_path: 自定义输出路径（可选）
            instance_type: 实例类型
            width: 输出视频宽度，默认 576（竖屏 9:16）
            height: 输出视频高度，默认 1024（竖屏 9:16）
            positive_prompt: 覆盖工作流默认正向提示词
            add_metadata: 是否写入完整 workflow metadata

        Returns:
            生成的视频文件路径，失败返回None
        """
        logger.info(f"\n{'='*60}")
        logger.info("🎬 多人动作模仿 (Multi-Person Action Imitate)")
        logger.info(f"{'='*60}")
        logger.info(f"🖼️  输入图片: {image_path}")
        logger.info(f"🎥 参考视频: {video_path}")
        logger.info(f"🔧 实例类型: {instance_type}")
        logger.info(f"📐 输出分辨率: {width}x{height}")

        start_time = time.time()
        try:
            # 1. 上传图片
            logger.info("\n【步骤 1/4】上传参考图片")
            image_file_name = self.upload_file(image_path)
            if not image_file_name:
                logger.error("图片上传失败")
                return None

            # 2. 上传视频
            logger.info("\n【步骤 2/4】上传参考视频")
            video_file_name = self.upload_file(video_path)
            if not video_file_name:
                logger.error("视频上传失败")
                return None

            # 3. 运行工作流
            logger.info("\n【步骤 3/4】运行多人动作模仿工作流")
            task_id = self.run_workflow(
                image_file_name=image_file_name,
                video_file_name=video_file_name,
                instance_type=instance_type,
                width=width,
                height=height,
                positive_prompt=positive_prompt,
                add_metadata=add_metadata,
            )

            if not task_id:
                logger.error("工作流启动失败")
                return None

            # 4. 等待任务完成并下载结果
            logger.info("\n【步骤 4/4】等待任务完成并下载结果")
            result = self.wait_for_completion(task_id, max_wait_time=7200, check_interval=10)

            if not result:
                logger.error("任务未成功完成")
                return None

            # 从 .ai 域名 v2 API 返回的 results 中获取输出
            outputs = result.get('results', [])
            logger.info(f"📋 工作流返回 {len(outputs) if outputs else 0} 个结果")

            if outputs and len(outputs) > 0:
                # 收集所有视频结果
                video_outputs = []
                for i, output in enumerate(outputs):
                    output_type = output.get('outputType', '')
                    node_id = output.get('nodeId', 'unknown')
                    file_url = output.get('url', '')
                    url_status = "present" if file_url else "missing"
                    logger.info(f"   结果 {i+1}: nodeId={node_id}, type={output_type}, url={url_status}")
                    if output_type in ['mp4', 'video', 'mov', 'avi'] and file_url:
                        video_outputs.append(output)

                if not video_outputs:
                    logger.warning("未找到视频类型结果，尝试使用第一个有URL的结果")
                    for output in outputs:
                        if output.get('url'):
                            video_outputs.append(output)
                            break

                if video_outputs:
                    # 下载所有视频，保留所有中间文件
                    downloaded_videos = []
                    timestamp = time.strftime("%Y%m%d_%H%M%S")

                    for i, video_output in enumerate(video_outputs):
                        file_url = video_output.get('url')
                        output_type = video_output.get('outputType', 'mp4')
                        node_id = video_output.get('nodeId', 'unknown')

                        # 使用序号命名，保留所有视频
                        temp_file = self.output_dir / f"output_{i+1}_node{node_id}_{timestamp}.{output_type}"

                        if self.download_file(file_url, str(temp_file)):
                            file_size = os.path.getsize(temp_file)
                            downloaded_videos.append({
                                'path': str(temp_file),
                                'size': file_size,
                                'node_id': node_id,
                                'index': i
                            })
                            logger.info(f"   ✅ 下载完成: {temp_file} ({file_size / (1024*1024):.2f} MB)")

                    if downloaded_videos:
                        # 选择倒数第二个视频作为最终输出（通常是带音频的最终渲染结果）
                        # 工作流输出顺序: 1.骨骼视频 2.最终视频(带音频) 3.对比视频
                        if len(downloaded_videos) >= 2:
                            final_video = downloaded_videos[-2]  # 倒数第二个
                            logger.info(f"   选择倒数第二个视频作为最终输出 (共{len(downloaded_videos)}个)")
                        else:
                            final_video = downloaded_videos[-1]  # 只有一个就用最后一个
                            logger.info(f"   只有{len(downloaded_videos)}个视频，选择最后一个作为最终输出")

                        final_path = final_video['path']

                        # 如果指定了output_path，复制最终视频（保留原文件）
                        if output_path:
                            import shutil
                            shutil.copy(final_path, output_path)
                            final_path = output_path

                        elapsed_time = time.time() - start_time
                        logger.info(f"\n✅ 多人动作模仿成功！总耗时: {elapsed_time:.2f}秒")
                        logger.info(f"   最终输出: {final_path}")
                        logger.info(f"   所有视频已保留在: {self.output_dir}")
                        return final_path
                    else:
                        logger.error("所有视频下载失败")
                else:
                    logger.error("未获取到视频URL")
            else:
                logger.error("未获取到结果")

            return None

        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"\n❌ 多人动作模仿失败 (耗时: {elapsed_time:.2f} 秒): {e}")
            import traceback
            traceback.print_exc()
            return None
