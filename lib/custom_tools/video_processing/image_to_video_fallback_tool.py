#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片转视频备用工具
当视频生成失败时，使用静态图片生成带有简单动画效果的视频
支持多种动画效果：Ken Burns、推镜、拉镜、平移等
"""

import subprocess
import random
from pathlib import Path
from typing import Dict, Optional, Literal, ClassVar
from crewai.tools import BaseTool
from src.logger import get_logger

logger = get_logger('image_to_video_fallback')


class ImageToVideoFallbackTool(BaseTool):
    """
    图片转视频备用工具

    当视频生成引擎失败时，使用这个工具将静态图片转换为带有简单动画效果的视频。
    支持的动画效果：
    - ken_burns: 肯伯恩斯效果（缓慢推镜+平移）
    - zoom_in: 推镜（从远到近）
    - zoom_out: 拉镜（从近到远）
    - pan_left: 向左平移
    - pan_right: 向右平移
    - pan_up: 向上平移
    - pan_down: 向下平移
    - static: 静态（无动画，仅展示）
    """

    name: str = "Image to Video Fallback Tool"
    description: str = "将静态图片转换为带有简单动画效果的视频，用作视频生成失败的备用方案"

    # 动画效果的FFmpeg滤镜配置
    ANIMATION_FILTERS: ClassVar[Dict[str, str]] = {
        'ken_burns': "zoompan=z='min(zoom+0.0015,1.5)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={width}x{height}:fps={fps}",
        'zoom_in': "zoompan=z='min(zoom+0.002,1.5)':d={frames}:s={width}x{height}:fps={fps}",
        'zoom_out': "zoompan=z='if(lte(zoom,1.0),1.5,max(1.0,zoom-0.002))':d={frames}:s={width}x{height}:fps={fps}",
        'pan_left': "zoompan=z='1.2':x='iw*0.1':y='ih*0.1':d={frames}:s={width}x{height}:fps={fps}",
        'pan_right': "zoompan=z='1.2':x='iw*-0.1':y='ih*0.1':d={frames}:s={width}x{height}:fps={fps}",
        'pan_up': "zoompan=z='1.2':x='0':y='ih*0.1':d={frames}:s={width}x{height}:fps={fps}",
        'pan_down': "zoompan=z='1.2':x='0':y='ih*-0.1':d={frames}:s={width}x{height}:fps={fps}",
        'static': "scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    }

    def _run(
        self,
        image_path: str,
        output_path: str,
        duration: float = 5.0,
        animation_type: Optional[Literal['ken_burns', 'zoom_in', 'zoom_out', 'pan_left', 'pan_right', 'pan_up', 'pan_down', 'static', 'auto']] = 'auto',
        width: int = 1080,
        height: int = 1920,
        fps: int = 30
    ) -> Dict:
        """
        将图片转换为带动画效果的视频

        Args:
            image_path: 输入图片路径
            output_path: 输出视频路径
            duration: 视频时长（秒）
            animation_type: 动画类型，'auto'表示随机选择
            width: 视频宽度
            height: 视频高度
            fps: 帧率

        Returns:
            结果字典，包含status和output_path或error
        """
        try:
            # 检查输入文件
            image_path_obj = Path(image_path)
            if not image_path_obj.exists():
                return {
                    'status': 'failed',
                    'error': f'输入图片不存在: {image_path}'
                }

            # 创建输出目录
            output_path_obj = Path(output_path)
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)

            # 如果是auto，随机选择一个动画效果（偏向使用ken_burns和zoom效果）
            if animation_type == 'auto':
                # 权重分配：ken_burns和zoom效果更常用
                weighted_choices = [
                    'ken_burns', 'ken_burns', 'ken_burns',  # 3次权重
                    'zoom_in', 'zoom_in',  # 2次权重
                    'zoom_out', 'zoom_out',  # 2次权重
                    'pan_left', 'pan_right', 'pan_up', 'pan_down',  # 各1次权重
                    'static'  # 1次权重
                ]
                animation_type = random.choice(weighted_choices)
                logger.info(f"🎲 自动选择动画效果: {animation_type}")

            # 获取滤镜配置
            filter_template = self.ANIMATION_FILTERS.get(animation_type)
            if not filter_template:
                return {
                    'status': 'failed',
                    'error': f'不支持的动画类型: {animation_type}'
                }

            # 计算总帧数
            frames = int(duration * fps)

            # 构建FFmpeg滤镜
            if animation_type == 'static':
                vf_filter = filter_template.format(width=width, height=height)
            else:
                vf_filter = filter_template.format(
                    frames=frames,
                    width=width,
                    height=height,
                    fps=fps
                )

            # 构建FFmpeg命令
            cmd = [
                'ffmpeg',
                '-loop', '1',
                '-i', str(image_path),
                '-f', 'lavfi',
                '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
                '-vf', vf_filter,
                '-t', str(duration),
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-pix_fmt', 'yuv420p',
                '-shortest',
                '-y',
                str(output_path)
            ]

            # 执行FFmpeg
            logger.info(f"🎬 使用{animation_type}效果将图片转换为视频...")
            logger.debug(f"FFmpeg命令: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                logger.error(f"FFmpeg错误: {result.stderr}")
                return {
                    'status': 'failed',
                    'error': f'FFmpeg执行失败: {result.stderr}'
                }

            # 验证输出文件
            if not output_path_obj.exists():
                return {
                    'status': 'failed',
                    'error': '输出视频文件未生成'
                }

            logger.info(f"✅ 图片转视频成功: {output_path}")

            return {
                'status': 'success',
                'output_path': str(output_path),
                'animation_type': animation_type,
                'duration': duration
            }

        except subprocess.TimeoutExpired:
            logger.error(f"❌ FFmpeg执行超时")
            return {
                'status': 'failed',
                'error': 'FFmpeg执行超时'
            }
        except Exception as e:
            logger.error(f"❌ 图片转视频失败: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e)
            }

    def create_video_from_image(
        self,
        image_path: str,
        output_path: str,
        duration: float = 5.0,
        scene_id: int = 0,
        animation_type: str = 'auto'
    ) -> Dict:
        """
        简化的图片转视频接口，自动选择合适的动画效果

        Args:
            image_path: 输入图片路径
            output_path: 输出视频路径
            duration: 视频时长
            scene_id: 分镜ID（用于生成不同的随机效果）
            animation_type: 动画类型，默认 auto

        Returns:
            结果字典
        """
        # 设置随机种子，让相同scene_id生成相同的动画效果
        random.seed(scene_id)

        result = self._run(
            image_path=image_path,
            output_path=output_path,
            duration=duration,
            animation_type=animation_type
        )

        # 重置随机种子
        random.seed()

        return result


def create_video_from_image_simple(
    image_path: str,
    output_path: str,
    duration: float = 5.0,
    animation_type: str = 'auto'
) -> Dict:
    """
    简单的函数式接口，用于快速将图片转换为视频

    Args:
        image_path: 输入图片路径
        output_path: 输出视频路径
        duration: 视频时长（秒）
        animation_type: 动画类型

    Returns:
        结果字典
    """
    tool = ImageToVideoFallbackTool()
    return tool._run(
        image_path=image_path,
        output_path=output_path,
        duration=duration,
        animation_type=animation_type
    )


if __name__ == "__main__":
    # 测试代码
    tool = ImageToVideoFallbackTool()

    # 测试各种动画效果
    test_image = "/path/to/test/image.jpg"
    test_output_dir = Path("/tmp/test_animations")
    test_output_dir.mkdir(parents=True, exist_ok=True)

    for effect in ['ken_burns', 'zoom_in', 'zoom_out', 'pan_left', 'static']:
        output_path = test_output_dir / f"test_{effect}.mp4"
        result = tool._run(
            image_path=test_image,
            output_path=str(output_path),
            duration=5.0,
            animation_type=effect
        )
        print(f"{effect}: {result}")
