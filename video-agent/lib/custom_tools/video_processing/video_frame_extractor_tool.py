#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频帧提取工具
用于从视频中提取指定帧（首帧、尾帧等）
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field

from src.logger import get_logger

logger = get_logger("video_frame_extractor_tool")


class VideoFrameExtractor:
    """视频帧提取器"""

    def __init__(self):
        """初始化视频帧提取器"""
        pass

    def extract_frame(
        self,
        video_path: str,
        output_path: str,
        frame_position: Literal['first', 'last', 'middle'] = 'last',
        time_offset: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        从视频中提取指定位置的帧

        Args:
            video_path: 视频文件路径
            output_path: 输出图片路径
            frame_position: 帧位置 ('first', 'last', 'middle')
            time_offset: 自定义时间偏移（秒），如果指定则忽略 frame_position

        Returns:
            提取结果字典
        """
        try:
            if not os.path.exists(video_path):
                return {
                    "status": "failed",
                    "error": f"视频文件不存在: {video_path}"
                }

            # 确保输出目录存在
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)

            # 获取视频时长
            duration = self._get_video_duration(video_path)
            if duration is None or duration <= 0:
                return {
                    "status": "failed",
                    "error": f"无法获取视频时长: {video_path}"
                }

            # 确定提取时间点
            if time_offset is not None:
                extract_time = min(time_offset, duration - 0.1)
            elif frame_position == 'first':
                extract_time = 0.0
            elif frame_position == 'last':
                # 提取最后一帧，使用视频时长减去一个小偏移
                extract_time = max(0, duration - 0.1)
            elif frame_position == 'middle':
                extract_time = duration / 2
            else:
                extract_time = max(0, duration - 0.1)

            logger.info(f"📸 提取视频帧: {video_path}")
            logger.info(f"   位置: {frame_position}, 时间点: {extract_time:.2f}秒 (总时长: {duration:.2f}秒)")

            # 使用 ffmpeg 提取帧，尾帧失败时自动回退重试
            attempts = [extract_time]
            if frame_position == 'last' and duration > 1.0:
                # 尾帧可能遇到损坏数据，准备回退时间点
                for offset in [1.0, 2.0, duration / 2]:
                    t = max(0, duration - offset)
                    if t not in attempts:
                        attempts.append(t)

            last_error = None
            for attempt_time in attempts:
                cmd = [
                    'ffmpeg',
                    '-y',
                    '-ss', str(attempt_time),
                    '-i', video_path,
                    '-vframes', '1',
                    '-pix_fmt', 'yuvj420p',
                    '-q:v', '2',
                    output_path
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    extract_time = attempt_time
                    break
                else:
                    last_error = result.stderr
                    if attempt_time != attempts[0]:
                        logger.warning(f"⚠️ 回退到 {attempt_time:.2f}s 仍失败，继续尝试...")
            else:
                logger.error(f"❌ ffmpeg 提取帧失败（已尝试 {len(attempts)} 个时间点）")
                return {
                    "status": "failed",
                    "error": f"ffmpeg 错误: {last_error}"
                }

            # 验证输出文件
            if not os.path.exists(output_path):
                return {
                    "status": "failed",
                    "error": "输出文件未生成"
                }

            file_size = os.path.getsize(output_path)
            logger.info(f"✅ 帧提取成功: {output_path} ({file_size / 1024:.1f} KB)")

            return {
                "status": "success",
                "output_path": output_path,
                "frame_position": frame_position,
                "extract_time": extract_time,
                "video_duration": duration,
                "file_size": file_size
            }

        except subprocess.TimeoutExpired:
            return {
                "status": "failed",
                "error": "ffmpeg 执行超时"
            }
        except Exception as e:
            logger.error(f"❌ 帧提取异常: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }

    def extract_last_frame(self, video_path: str, output_path: str) -> Dict[str, Any]:
        """
        提取视频的最后一帧（便捷方法）

        Args:
            video_path: 视频文件路径
            output_path: 输出图片路径

        Returns:
            提取结果字典
        """
        return self.extract_frame(video_path, output_path, frame_position='last')

    def extract_first_frame(self, video_path: str, output_path: str) -> Dict[str, Any]:
        """
        提取视频的第一帧（便捷方法）

        Args:
            video_path: 视频文件路径
            output_path: 输出图片路径

        Returns:
            提取结果字典
        """
        return self.extract_frame(video_path, output_path, frame_position='first')

    def _get_video_duration(self, video_path: str) -> Optional[float]:
        """
        获取视频时长

        Args:
            video_path: 视频文件路径

        Returns:
            视频时长（秒），失败返回 None
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
            return None

        except Exception as e:
            logger.error(f"获取视频时长失败: {e}")
            return None


# 便捷函数
def extract_video_last_frame(video_path: str, output_path: str) -> Dict[str, Any]:
    """
    提取视频最后一帧的便捷函数

    Args:
        video_path: 视频文件路径
        output_path: 输出图片路径

    Returns:
        提取结果字典
    """
    extractor = VideoFrameExtractor()
    return extractor.extract_last_frame(video_path, output_path)


def extract_video_first_frame(video_path: str, output_path: str) -> Dict[str, Any]:
    """
    提取视频第一帧的便捷函数

    Args:
        video_path: 视频文件路径
        output_path: 输出图片路径

    Returns:
        提取结果字典
    """
    extractor = VideoFrameExtractor()
    return extractor.extract_first_frame(video_path, output_path)
