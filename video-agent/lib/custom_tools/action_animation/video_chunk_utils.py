#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频分块处理工具
用于将长视频切分成多个片段，提取最后一帧，以及拼接视频
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from src.logger import get_logger

logger = get_logger("video_chunk_utils")


def get_video_duration(video_path: str) -> float:
    """
    获取视频时长（秒）

    Args:
        video_path: 视频文件路径

    Returns:
        视频时长（秒）
    """
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        logger.info(f"📊 视频时长: {duration:.2f}秒 - {video_path}")
        return duration
    except Exception as e:
        logger.error(f"获取视频时长失败: {e}")
        raise


def split_video_into_chunks(
    video_path: str,
    chunk_duration: float = 8.0,
    min_chunk_duration: float = 4.0,
    output_dir: Optional[str] = None
) -> List[str]:
    """
    将视频按指定时长切分成多个片段

    Args:
        video_path: 输入视频路径
        chunk_duration: 每个片段的时长（秒），默认10秒
        min_chunk_duration: 最小片段时长（秒），默认5秒。
                           如果最后一段小于此值，会合并到前一段
        output_dir: 输出目录，默认为临时目录

    Returns:
        切分后的视频片段路径列表
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"视频文件不存在: {video_path}")

    # 获取视频总时长
    total_duration = get_video_duration(video_path)

    # 如果视频时长小于等于chunk_duration，不需要切分
    if total_duration <= chunk_duration:
        logger.info(f"📹 视频时长 {total_duration:.2f}秒 <= {chunk_duration}秒，无需切分")
        return [video_path]

    # 计算切分点，处理最后一段过短的情况
    chunk_times = _calculate_chunk_times(total_duration, chunk_duration, min_chunk_duration)

    # 创建输出目录
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="video_chunks_")
    else:
        os.makedirs(output_dir, exist_ok=True)

    chunk_paths = []
    video_name = Path(video_path).stem

    logger.info(f"🔪 开始切分视频: {video_path}")
    logger.info(f"   总时长: {total_duration:.2f}秒, 目标每段: {chunk_duration}秒, 最小: {min_chunk_duration}秒")

    for chunk_index, (start_time, end_time) in enumerate(chunk_times):
        current_chunk_duration = end_time - start_time

        # 输出文件路径
        chunk_path = os.path.join(output_dir, f"{video_name}_chunk_{chunk_index:03d}.mp4")

        # 使用 ffmpeg 切分
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start_time),
            '-i', video_path,
            '-t', str(current_chunk_duration),
            '-c', 'copy',  # 无损复制，速度快
            '-avoid_negative_ts', 'make_zero',
            chunk_path
        ]

        try:
            subprocess.run(cmd, capture_output=True, check=True)
            chunk_paths.append(chunk_path)
            logger.info(f"   ✅ 片段 {chunk_index}: {start_time:.2f}s - {end_time:.2f}s ({current_chunk_duration:.2f}秒)")
        except subprocess.CalledProcessError as e:
            logger.error(f"切分视频片段失败: {e.stderr.decode()}")
            raise

    logger.info(f"✅ 视频切分完成，共 {len(chunk_paths)} 个片段")
    return chunk_paths


def _calculate_chunk_times(
    total_duration: float,
    chunk_duration: float,
    min_chunk_duration: float
) -> List[Tuple[float, float]]:
    """
    计算切分时间点，处理最后一段过短的情况

    Args:
        total_duration: 视频总时长
        chunk_duration: 目标片段时长
        min_chunk_duration: 最小片段时长

    Returns:
        切分时间点列表 [(start, end), ...]
    """
    chunks = []
    start_time = 0.0

    while start_time < total_duration:
        remaining = total_duration - start_time

        if remaining <= chunk_duration:
            # 这是最后一段
            chunks.append((start_time, total_duration))
            break
        elif remaining - chunk_duration < min_chunk_duration:
            # 如果切完这段后，剩余不足 min_chunk_duration，就把剩余全部合并到这一段
            # 例如：22秒，chunk=10，min=5 -> 剩余12秒，切10秒后剩2秒 < 5秒
            # 所以这一段取 12秒（10 + 2）
            chunks.append((start_time, total_duration))
            logger.info(f"   📎 合并最后短片段: {start_time:.2f}s - {total_duration:.2f}s ({remaining:.2f}秒)")
            break
        else:
            # 正常切分
            chunks.append((start_time, start_time + chunk_duration))
            start_time += chunk_duration

    return chunks


def extract_last_frame(video_path: str, output_path: Optional[str] = None) -> str:
    """
    提取视频的最后一帧作为图片

    Args:
        video_path: 视频文件路径
        output_path: 输出图片路径，默认为临时文件

    Returns:
        提取的图片路径
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"视频文件不存在: {video_path}")

    # 确定输出路径
    if output_path is None:
        video_name = Path(video_path).stem
        output_path = os.path.join(
            tempfile.gettempdir(),
            f"{video_name}_last_frame.png"
        )

    # 获取视频时长
    duration = get_video_duration(video_path)

    # 提取最后一帧（往前偏移0.1秒以确保能获取到帧）
    seek_time = max(0, duration - 0.1)

    cmd = [
        'ffmpeg', '-y',
        '-ss', str(seek_time),
        '-i', video_path,
        '-vframes', '1',
        '-q:v', '2',  # 高质量
        output_path
    ]

    try:
        subprocess.run(cmd, capture_output=True, check=True)
        logger.info(f"✅ 提取最后一帧成功: {output_path}")
        return output_path
    except subprocess.CalledProcessError as e:
        logger.error(f"提取最后一帧失败: {e.stderr.decode()}")
        raise


def concatenate_videos(video_paths: List[str], output_path: str) -> str:
    """
    将多个视频拼接成一个视频

    Args:
        video_paths: 视频文件路径列表（按顺序）
        output_path: 输出视频路径

    Returns:
        拼接后的视频路径
    """
    if not video_paths:
        raise ValueError("视频列表为空")

    if len(video_paths) == 1:
        # 只有一个视频，直接复制
        import shutil
        shutil.copy(video_paths[0], output_path)
        logger.info(f"✅ 只有一个视频，直接复制: {output_path}")
        return output_path

    # 在输出目录下创建临时列表文件（避免相对路径问题）
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        list_file_path = os.path.join(output_dir, "concat_list.txt")
    else:
        list_file_path = "concat_list.txt"

    try:
        # 写入文件列表
        with open(list_file_path, 'w') as list_file:
            for video_path in video_paths:
                if not os.path.exists(video_path):
                    raise FileNotFoundError(f"视频文件不存在: {video_path}")
                # 使用绝对路径确保可靠性
                abs_path = os.path.abspath(video_path)
                escaped_path = abs_path.replace("'", "'\\''")
                list_file.write(f"file '{escaped_path}'\n")

        logger.info(f"🔗 开始拼接 {len(video_paths)} 个视频...")

        # 使用 ffmpeg concat demuxer 拼接
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file_path,
            '-c', 'copy',  # 无损复制
            output_path
        ]

        subprocess.run(cmd, capture_output=True, check=True)
        logger.info(f"✅ 视频拼接完成: {output_path}")
        return output_path

    except subprocess.CalledProcessError as e:
        logger.error(f"视频拼接失败: {e.stderr.decode()}")
        raise
    finally:
        # 清理临时文件
        if os.path.exists(list_file_path):
            os.unlink(list_file_path)


def cleanup_temp_files(file_paths: List[str]) -> None:
    """
    清理临时文件

    Args:
        file_paths: 要删除的文件路径列表
    """
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.unlink(path)
                logger.debug(f"🗑️ 删除临时文件: {path}")
        except Exception as e:
            logger.warning(f"删除临时文件失败: {path}, 错误: {e}")
