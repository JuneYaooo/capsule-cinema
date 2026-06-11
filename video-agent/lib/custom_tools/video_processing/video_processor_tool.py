#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频处理工具集
包含获取视频信息、切割视频等功能
"""

import os
import subprocess
import json
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from src.logger import get_logger

logger = get_logger("video_processor_tool")


class GetVideoInfoSchema(BaseModel):
    """获取视频信息工具的输入参数"""
    video_path: str = Field(
        ...,
        description="视频文件路径"
    )


class GetVideoInfoTool(BaseTool):
    name: str = "Get video information tool"
    description: str = (
        "获取视频的详细信息，包括时长、分辨率、帧率、编码格式等。"
    )
    args_schema: type[BaseModel] = GetVideoInfoSchema

    def _run(self, video_path: str) -> Dict[str, Any]:
        """
        获取视频信息

        Args:
            video_path: 视频文件路径

        Returns:
            视频信息字典
        """
        try:
            if not os.path.exists(video_path):
                return {
                    "status": "failed",
                    "error": f"视频文件不存在: {video_path}"
                }

            logger.info(f"📊 获取视频信息: {video_path}")

            # 使用ffprobe获取视频信息
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height,r_frame_rate,codec_name,duration',
                '-show_entries', 'format=duration,size,bit_rate',
                '-of', 'json',
                video_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            probe_data = json.loads(result.stdout)

            # 提取视频流信息
            video_stream = probe_data.get('streams', [{}])[0]
            format_info = probe_data.get('format', {})

            # 解析帧率
            fps_str = video_stream.get('r_frame_rate', '0/1')
            fps_num, fps_den = map(int, fps_str.split('/'))
            fps = fps_num / fps_den if fps_den != 0 else 0

            # 获取时长（优先使用stream的duration，其次使用format的duration）
            duration = float(video_stream.get('duration', format_info.get('duration', 0)))

            video_info = {
                "status": "success",
                "video_path": video_path,
                "width": int(video_stream.get('width', 0)),
                "height": int(video_stream.get('height', 0)),
                "fps": round(fps, 2),
                "duration": round(duration, 2),
                "codec": video_stream.get('codec_name', 'unknown'),
                "file_size": int(format_info.get('size', 0)),
                "bit_rate": int(format_info.get('bit_rate', 0)),
            }

            logger.info(f"✅ 视频信息获取成功:")
            logger.info(f"   分辨率: {video_info['width']}x{video_info['height']}")
            logger.info(f"   时长: {video_info['duration']}秒")
            logger.info(f"   帧率: {video_info['fps']} fps")
            logger.info(f"   编码: {video_info['codec']}")
            logger.info(f"   大小: {video_info['file_size'] / (1024*1024):.2f} MB")

            return video_info

        except subprocess.CalledProcessError as e:
            error_msg = f"ffprobe执行失败: {e.stderr}"
            logger.error(f"❌ {error_msg}")
            return {
                "status": "failed",
                "error": error_msg
            }
        except Exception as e:
            error_msg = f"获取视频信息失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "status": "failed",
                "error": error_msg
            }


class CutVideoSchema(BaseModel):
    """切割视频工具的输入参数"""
    video_path: str = Field(
        ...,
        description="源视频文件路径"
    )
    start_time: float = Field(
        ...,
        description="开始时间（秒）"
    )
    end_time: float = Field(
        ...,
        description="结束时间（秒）"
    )
    output_path: str = Field(
        ...,
        description="输出视频文件路径"
    )
    re_encode: bool = Field(
        default=False,
        description="是否重新编码（False=快速复制流，True=重新编码）"
    )


class CutVideoTool(BaseTool):
    name: str = "Cut video tool"
    description: str = (
        "切割视频，提取指定时间段的视频片段。"
    )
    args_schema: type[BaseModel] = CutVideoSchema

    def _run(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        output_path: str,
        re_encode: bool = False
    ) -> Dict[str, Any]:
        """
        切割视频

        Args:
            video_path: 源视频文件路径
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            output_path: 输出视频文件路径
            re_encode: 是否重新编码

        Returns:
            切割结果字典
        """
        try:
            if not os.path.exists(video_path):
                return {
                    "status": "failed",
                    "error": f"源视频文件不存在: {video_path}"
                }

            if start_time >= end_time:
                return {
                    "status": "failed",
                    "error": f"开始时间({start_time})必须小于结束时间({end_time})"
                }

            duration = end_time - start_time

            logger.info(f"✂️ 切割视频: {os.path.basename(video_path)}")
            logger.info(f"   时间段: {start_time}s - {end_time}s (时长: {duration}s)")
            logger.info(f"   输出: {output_path}")

            # 创建输出目录
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            if re_encode:
                # 重新编码模式（较慢，但更精确）
                cmd = [
                    'ffmpeg',
                    '-i', video_path,
                    '-ss', str(start_time),
                    '-t', str(duration),
                    '-c:v', 'libx264',
                    '-c:a', 'aac',
                    '-y',
                    output_path
                ]
            else:
                # 快速复制流模式（较快，但可能不够精确）
                cmd = [
                    'ffmpeg',
                    '-ss', str(start_time),
                    '-i', video_path,
                    '-t', str(duration),
                    '-c', 'copy',
                    '-y',
                    output_path
                ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                logger.info(f"✅ 视频切割成功: {output_path} ({file_size / (1024*1024):.2f} MB)")

                return {
                    "status": "success",
                    "output_path": output_path,
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": duration,
                    "file_size": file_size
                }
            else:
                return {
                    "status": "failed",
                    "error": "视频切割完成但输出文件不存在"
                }

        except subprocess.CalledProcessError as e:
            error_msg = f"ffmpeg执行失败: {e.stderr}"
            logger.error(f"❌ {error_msg}")
            return {
                "status": "failed",
                "error": error_msg
            }
        except Exception as e:
            error_msg = f"视频切割失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "status": "failed",
                "error": error_msg
            }


class BatchCutVideoSchema(BaseModel):
    """批量切割视频工具的输入参数"""
    video_path: str = Field(
        ...,
        description="源视频文件路径"
    )
    segments: List[Dict[str, Any]] = Field(
        ...,
        description="切割片段列表，每个包含start_time, end_time, output_path"
    )
    re_encode: bool = Field(
        default=False,
        description="是否重新编码"
    )


class BatchCutVideoTool(BaseTool):
    name: str = "Batch cut video tool"
    description: str = (
        "批量切割视频，一次性提取多个时间段的视频片段。"
    )
    args_schema: type[BaseModel] = BatchCutVideoSchema

    def _run(
        self,
        video_path: str,
        segments: List[Dict[str, Any]],
        re_encode: bool = False
    ) -> Dict[str, Any]:
        """
        批量切割视频

        Args:
            video_path: 源视频文件路径
            segments: 切割片段列表，每个包含:
                - start_time: 开始时间（秒）
                - end_time: 结束时间（秒）
                - output_path: 输出路径
                - scene_id: 可选，场景ID
            re_encode: 是否重新编码

        Returns:
            批量切割结果字典
        """
        try:
            if not os.path.exists(video_path):
                return {
                    "status": "failed",
                    "error": f"源视频文件不存在: {video_path}"
                }

            logger.info(f"✂️ 批量切割视频: {os.path.basename(video_path)}")
            logger.info(f"   片段数量: {len(segments)}")

            cut_tool = CutVideoTool()
            results = []
            outputs = {}
            success_count = 0
            failed_count = 0

            for i, segment in enumerate(segments):
                start_time = segment.get('start_time')
                end_time = segment.get('end_time')
                output_path = segment.get('output_path')
                scene_id = segment.get('scene_id', i)

                if start_time is None or end_time is None or not output_path:
                    logger.warning(f"⚠️ 片段{i}缺少必要参数，跳过")
                    failed_count += 1
                    continue

                logger.info(f"📹 切割片段{i+1}/{len(segments)}: {start_time}s - {end_time}s")

                result = cut_tool._run(
                    video_path=video_path,
                    start_time=start_time,
                    end_time=end_time,
                    output_path=output_path,
                    re_encode=re_encode
                )

                if result.get('status') == 'success':
                    outputs[scene_id] = result['output_path']
                    success_count += 1
                    logger.info(f"✅ 片段{i+1}切割成功")
                else:
                    outputs[scene_id] = f"错误: {result.get('error')}"
                    failed_count += 1
                    logger.error(f"❌ 片段{i+1}切割失败: {result.get('error')}")

                results.append({
                    "scene_id": scene_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "status": result.get('status'),
                    "output_path": result.get('output_path', ''),
                    "error": result.get('error', '')
                })

            summary = {
                "total": len(segments),
                "success": success_count,
                "failed": failed_count,
                "success_rate": f"{(success_count/len(segments)*100):.1f}%" if len(segments) > 0 else "0%"
            }

            logger.info(f"✂️ 批量切割完成: 成功{success_count}/{len(segments)}, 失败{failed_count}")

            return {
                "status": "success",
                "outputs": outputs,
                "summary": summary,
                "results": results
            }

        except Exception as e:
            error_msg = f"批量切割视频失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "status": "failed",
                "error": error_msg
            }
