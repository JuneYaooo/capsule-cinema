#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频拼接工具
支持视频片段拼接、音频合并、背景音乐添加
"""

import subprocess
from pathlib import Path
from typing import Any, Type, List, Dict, Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from src.logger import get_logger

logger = get_logger("video_concatenate")


class ConcatenateVideosSchema(BaseModel):
    """视频拼接工具的输入参数"""
    video_paths: List[str] = Field(
        ...,
        description="视频片段路径列表，按顺序拼接"
    )
    output_path: str = Field(
        ...,
        description="拼接后的输出视频路径"
    )
    audio_paths: Optional[List[str]] = Field(
        default=None,
        description="音频文件路径列表（可选），与video_paths一一对应。如果提供，会先将音频合并到对应视频"
    )
    voice_volume: float = Field(
        default=1.5,
        description="配音音量倍数，默认1.5（即150%）"
    )
    sound_effect_paths: Optional[List[str]] = Field(
        default=None,
        description="音效文件路径列表（可选），与video_paths一一对应。如果提供，会将音效合并到对应视频"
    )


class AddBackgroundMusicSchema(BaseModel):
    """添加背景音乐工具的输入参数"""
    video_path: str = Field(
        ...,
        description="视频文件路径"
    )
    music_path: str = Field(
        ...,
        description="背景音乐文件路径"
    )
    output_path: Optional[str] = Field(
        default=None,
        description="输出视频路径（可选）。如果不提供，将覆盖原视频"
    )
    music_volume: float = Field(
        default=0.15,
        description="背景音乐音量（0.0-1.0），默认0.15"
    )


class ConcatenateVideosTool(BaseTool):
    name: str = "拼接视频片段"
    description: str = (
        "将多个视频片段按顺序拼接成一个完整视频。支持同时合并音频到各个视频片段。"
    )
    args_schema: Type[BaseModel] = ConcatenateVideosSchema

    def _run(
        self,
        video_paths: List[str],
        output_path: str,
        audio_paths: Optional[List[str]] = None,
        voice_volume: float = 1.5,
        sound_effect_paths: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        拼接视频片段

        Args:
            video_paths: 视频片段路径列表
            output_path: 输出视频路径
            audio_paths: 音频路径列表（可选）
            voice_volume: 配音音量倍数，默认1.5（即150%）
            sound_effect_paths: 音效路径列表（可选）

        Returns:
            包含拼接结果的字典
        """
        try:
            logger.info(f"🔗 开始拼接 {len(video_paths)} 个视频片段")

            # 准备视频片段列表
            video_segments = []
            temp_dir = Path(output_path).parent / "temp_concat"
            temp_dir.mkdir(exist_ok=True)

            # 检查并转换视频格式（如果需要）
            converted_videos = []
            for i, video_path in enumerate(video_paths):
                if not Path(video_path).exists():
                    logger.warning(f"⚠️ 视频文件不存在: {video_path}")
                    continue

                # 检查文件格式
                converted_path = self._ensure_mp4_format(video_path, temp_dir, i)
                converted_videos.append(converted_path)

            # 处理音频和音效，确保所有视频都有音频流（避免拼接时音频时间戳偏移）
            logger.info("🔊 处理音频和音效...")
            if audio_paths or sound_effect_paths:
                logger.info(f"   配音音量: {voice_volume}x ({voice_volume*100:.0f}%)")

            # 确保列表长度一致
            audio_list = audio_paths if audio_paths else [None] * len(converted_videos)
            sound_effect_list = sound_effect_paths if sound_effect_paths else [None] * len(converted_videos)

            for i, video_path in enumerate(converted_videos):
                audio_path = audio_list[i] if i < len(audio_list) else None
                sound_effect_path = sound_effect_list[i] if i < len(sound_effect_list) else None

                # 如果有音频或音效需要合并
                if (audio_path and Path(audio_path).exists()) or (sound_effect_path and Path(sound_effect_path).exists()):
                    merged_path = str(temp_dir / f"video_{i:02d}_with_audio.mp4")
                    self._merge_audio_to_video(
                        video_path,
                        audio_path,
                        merged_path,
                        voice_volume,
                        sound_effect_path
                    )
                    # 合并后再次检查格式（因为可能生成了 WebP）
                    final_path = self._ensure_mp4_format(merged_path, temp_dir, i + 1000)
                    video_segments.append(final_path)
                else:
                    # 没有音频/音效的视频也需要添加静音音轨，确保拼接时音频时间戳正确
                    # 否则后续有音效的分镜会出现音频延迟的问题
                    silent_video_path = str(temp_dir / f"video_{i:02d}_with_silent.mp4")
                    self._add_silent_audio_track(video_path, silent_video_path)
                    video_segments.append(silent_video_path)

            if not video_segments:
                return {
                    'status': 'failed',
                    'error': '没有可用的视频片段',
                    'message': '❌ 没有可用的视频片段进行拼接'
                }

            # 统一视频分辨率（使用第一个视频的分辨率作为目标分辨率）
            logger.info("📐 检查并统一视频分辨率...")
            video_segments = self._normalize_video_resolutions(video_segments, temp_dir)

            logger.info(f"📋 准备拼接 {len(video_segments)} 个视频片段")

            # 创建拼接列表文件
            concat_list_path = temp_dir / "concat_list.txt"
            with open(concat_list_path, 'w', encoding='utf-8') as f:
                for video_path in video_segments:
                    abs_path = Path(video_path).resolve()
                    f.write(f"file '{abs_path}'\n")

            # 拼接视频
            # 使用重编码模式确保时间戳连续和音视频同步（关键修复）
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_list_path),
                '-map', '0:v:0',          # 只映射视频流
                '-map', '0:a:0',          # 只映射音频流
                '-dn',                    # 禁用数据流（字幕元数据等），避免时长显示不正确
                '-c:v', 'libx264',        # 重编码视频，修复时间戳
                '-preset', 'medium',      # 平衡速度和质量
                '-crf', '23',             # 质量控制（18-28，越小质量越好）
                '-c:a', 'aac',            # 音频重新编码
                '-b:a', '192k',           # 音频码率192kbps（高质量）
                '-ar', '48000',           # 统一音频采样率为48000Hz（更高质量，减少卡顿）
                '-ac', '2',               # 强制双声道，确保一致性
                '-af', 'aresample=async=1:first_pts=0',  # 音频重采样，确保音视频同步
                '-avoid_negative_ts', 'make_zero',  # 修复时间戳问题
                '-fflags', '+genpts',     # 生成正确的PTS
                '-vsync', 'cfr',          # 恒定帧率，避免帧跳跃
                '-max_muxing_queue_size', '1024',  # 增加复用队列，防止音频丢帧
                str(output_path)
            ]

            logger.info("🎬 执行视频拼接（重编码音频以确保连贯）...")
            result = subprocess.run(cmd, check=True, capture_output=True)

            logger.info(f"✅ 视频拼接完成: {output_path}")

            return {
                'status': 'success',
                'output_path': str(output_path),
                'total_segments': len(video_segments),
                'message': f'✅ 成功拼接 {len(video_segments)} 个视频片段'
            }

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"❌ 视频拼接失败: {error_msg}")
            return {
                'status': 'failed',
                'error': error_msg,
                'message': f'❌ 视频拼接失败: {error_msg}'
            }
        except Exception as e:
            logger.error(f"❌ 视频拼接失败: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e),
                'message': f'❌ 视频拼接失败: {str(e)}'
            }

    def _ensure_mp4_format(self, video_path: str, temp_dir: Path, index: int) -> str:
        """确保视频是MP4格式，如果是WebP则转换"""
        try:
            # 读取文件头检测格式
            with open(video_path, 'rb') as f:
                header = f.read(12)

            is_webp = header[:4] == b'RIFF' and header[8:12] == b'WEBP'

            if is_webp:
                logger.warning(f"⚠️ 检测到WebP格式: {Path(video_path).name}，转换为MP4...")
                converted_path = str(temp_dir / f"converted_{index:02d}.mp4")

                # WebP 动画需要特殊处理
                cmd = [
                    'ffmpeg', '-y',
                    '-i', video_path,  # WebP 动画会自动识别帧率
                    '-c:v', 'libx264',
                    '-preset', 'ultrafast',  # 使用最快预设
                    '-crf', '23',  # 质量控制
                    '-pix_fmt', 'yuv420p',
                    '-vf', 'fps=25',  # 统一帧率为 25fps
                    '-movflags', '+faststart',
                    converted_path
                ]

                subprocess.run(cmd, check=True, capture_output=True)
                logger.info(f"   ✅ 转换完成: {Path(converted_path).name}")
                return converted_path
            else:
                # 已经是MP4或其他视频格式
                return video_path

        except Exception as e:
            logger.error(f"❌ 格式检测/转换失败: {str(e)}")
            return video_path  # 返回原路径，让ffmpeg尝试处理

    def _normalize_video_resolutions(self, video_paths: List[str], temp_dir: Path) -> List[str]:
        """
        统一所有视频的分辨率，以第一个视频的分辨率为基准

        Args:
            video_paths: 视频路径列表
            temp_dir: 临时目录

        Returns:
            统一分辨率后的视频路径列表
        """
        if not video_paths:
            return video_paths

        try:
            # 获取第一个视频的分辨率作为目标分辨率
            target_width, target_height = self._get_video_resolution(video_paths[0])
            if target_width is None or target_height is None:
                logger.warning("⚠️ 无法获取第一个视频的分辨率，跳过分辨率统一")
                return video_paths

            logger.info(f"   目标分辨率: {target_width}x{target_height}")

            normalized_paths = []
            for i, video_path in enumerate(video_paths):
                width, height = self._get_video_resolution(video_path)

                if width is None or height is None:
                    logger.warning(f"   ⚠️ 无法获取视频 {i} 的分辨率，保持原样")
                    normalized_paths.append(video_path)
                    continue

                # 打印每个视频的分辨率（用于调试）
                logger.info(f"   视频 {i}: {width}x{height} ({Path(video_path).name})")

                # 检查分辨率是否需要调整
                if width != target_width or height != target_height:
                    logger.info(f"      → 调整为 {target_width}x{target_height}")

                    # 转换分辨率
                    normalized_path = str(temp_dir / f"normalized_{i:02d}.mp4")
                    success = self._resize_video(video_path, normalized_path, target_width, target_height)

                    if success:
                        normalized_paths.append(normalized_path)
                    else:
                        logger.warning(f"   ⚠️ 视频 {i} 分辨率调整失败，使用原视频")
                        normalized_paths.append(video_path)
                else:
                    # 分辨率一致，无需调整
                    normalized_paths.append(video_path)

            return normalized_paths

        except Exception as e:
            logger.error(f"❌ 分辨率统一失败: {str(e)}")
            return video_paths

    def _get_video_resolution(self, video_path: str) -> tuple:
        """
        获取视频的分辨率

        Args:
            video_path: 视频路径

        Returns:
            (width, height) 元组，失败返回 (None, None)
        """
        try:
            cmd = [
                'ffprobe', '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height',
                '-of', 'csv=p=0:s=x',
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            width_str, height_str = result.stdout.strip().split('x')
            return int(width_str), int(height_str)
        except Exception as e:
            logger.warning(f"⚠️ 获取视频分辨率失败: {str(e)}")
            return None, None

    def _resize_video(self, input_path: str, output_path: str, width: int, height: int) -> bool:
        """
        调整视频分辨率

        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径
            width: 目标宽度
            height: 目标高度

        Returns:
            是否成功
        """
        try:
            # 使用 scale + pad 确保正确的宽高比
            # force_original_aspect_ratio=decrease 会缩小视频以适应目标尺寸
            # pad 会在周围添加黑边以填充到目标尺寸
            cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black',
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '23',
                '-c:a', 'copy',
                '-pix_fmt', 'yuv420p',
                output_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except Exception as e:
            logger.error(f"❌ 视频分辨率调整失败: {str(e)}")
            return False

    def _add_silent_audio_track(self, video_path: str, output_path: str):
        """
        为没有音频流的视频添加静音音轨

        这是为了解决 ffmpeg concat 拼接时，如果前面的视频没有音频流，
        后面有音效的视频的音频会出现时间戳偏移（延迟播放）的问题。

        Args:
            video_path: 输入视频路径
            output_path: 输出视频路径
        """
        try:
            # 先检查视频是否已经有音频流
            probe_cmd = [
                'ffprobe', '-v', 'error',
                '-select_streams', 'a',
                '-show_entries', 'stream=codec_type',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            result = subprocess.run(probe_cmd, capture_output=True, text=True)

            if result.stdout.strip() == 'audio':
                # 已有音频流，直接复制
                import shutil
                shutil.copy2(video_path, output_path)
                return

            # 获取视频时长
            dur_cmd = [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            dur_result = subprocess.run(dur_cmd, capture_output=True, text=True, check=True)
            video_duration = float(dur_result.stdout.strip())

            # 添加静音音轨
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-f', 'lavfi',
                '-i', 'anullsrc=channel_layout=stereo:sample_rate=48000',
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-ar', '48000',
                '-ac', '2',
                '-t', str(video_duration),
                '-shortest',
                output_path
            ]

            subprocess.run(cmd, check=True, capture_output=True)
            logger.debug(f"   🔇 已为视频添加静音音轨: {Path(output_path).name}")

        except Exception as e:
            logger.warning(f"   ⚠️ 添加静音音轨失败: {str(e)}，使用原视频")
            import shutil
            shutil.copy2(video_path, output_path)

    def _merge_audio_to_video(
        self,
        video_path: str,
        audio_path: Optional[str],
        output_path: str,
        voice_volume: float = 1.5,
        sound_effect_path: Optional[str] = None
    ):
        """将音频和音效合并到视频"""
        try:
            # 检查是否有音频或音效需要合并
            has_audio = audio_path and Path(audio_path).exists()
            has_sound_effect = sound_effect_path and Path(sound_effect_path).exists()

            if not has_audio and not has_sound_effect:
                logger.warning(f"   ⚠️ 没有音频或音效需要合并")
                import shutil
                shutil.copy2(video_path, output_path)
                return

            # 获取视频时长
            try:
                probe_cmd = [
                    'ffprobe', '-v', 'error',
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    video_path
                ]
                result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
                video_duration = float(result.stdout.strip())
                logger.info(f"   📏 视频时长: {video_duration:.3f}秒")
            except Exception as e:
                logger.warning(f"   ⚠️ 无法获取视频时长: {e}")
                video_duration = None

            # 获取音频时长（配音）
            audio_duration = None
            if has_audio:
                try:
                    a_probe_cmd = [
                        'ffprobe', '-v', 'error',
                        '-show_entries', 'format=duration',
                        '-of', 'default=noprint_wrappers=1:nokey=1',
                        audio_path
                    ]
                    a_result = subprocess.run(a_probe_cmd, capture_output=True, text=True, check=True)
                    audio_duration = float(a_result.stdout.strip())
                    logger.info(f"   📏 音频时长: {audio_duration:.3f}秒")
                except Exception as e:
                    logger.warning(f"   ⚠️ 无法获取音频时长: {e}")

            # 计算目标时长：取视频和音频中较长的那个
            if video_duration and audio_duration:
                target_duration = max(video_duration, audio_duration)
                need_extend_video = audio_duration > video_duration + 0.1  # 音频比视频长超过0.1秒
                need_pad_audio = video_duration > audio_duration + 0.1    # 视频比音频长超过0.1秒
                logger.info(f"   📏 目标时长: {target_duration:.3f}秒 (延长视频: {need_extend_video}, 填充音频: {need_pad_audio})")
            else:
                target_duration = video_duration or audio_duration
                need_extend_video = False
                need_pad_audio = False

            # 检测输入视频是否是 WebP
            with open(video_path, 'rb') as f:
                header = f.read(12)
            is_webp = header[:4] == b'RIFF' and header[8:12] == b'WEBP'

            # 构建ffmpeg命令
            cmd = ['ffmpeg', '-y', '-i', video_path]
            input_index = 1

            # 添加音频输入
            if has_audio:
                cmd.extend(['-i', audio_path])
                audio_index = input_index
                input_index += 1

            # 添加音效输入
            if has_sound_effect:
                cmd.extend(['-i', sound_effect_path])
                sound_effect_index = input_index
                input_index += 1

            # 构建音频滤镜（添加输出标签[aout]以便后续映射）
            # 关键修复：使用 atrim 强制截断音效，确保不溢出到下一个分镜
            # 重要：AAC 编码器会将音频对齐到帧边界（约 21-23ms），导致音频略长于视频
            # 解决方案：在滤镜链末尾再次使用 atrim 精确截断，确保音频时长 <= 视频时长
            if has_audio and has_sound_effect:
                # 同时有配音和音效
                if target_duration:
                    audio_filter = (
                        f'[{audio_index}:a]asetpts=PTS-STARTPTS,volume={voice_volume},'
                        f'apad=whole_dur={target_duration:.3f}[voice];'
                        f'[{sound_effect_index}:a]atrim=0:{target_duration:.3f},asetpts=PTS-STARTPTS,'
                        f'volume=0.8,apad=whole_dur={target_duration:.3f}[se];'
                        f'[voice][se]amix=inputs=2:duration=first:dropout_transition=2,'
                        f'aresample=async=1,aformat=sample_rates=48000:channel_layouts=stereo,'
                        f'atrim=0:{target_duration:.3f},asetpts=PTS-STARTPTS[aout]'
                    )
                    logger.info(f"   🎵 合并配音和音效（目标时长{target_duration:.3f}秒）")
                else:
                    audio_filter = f'[{audio_index}:a]volume={voice_volume}[voice];[{sound_effect_index}:a]volume=0.8[se];[voice][se]amix=inputs=2:duration=first:dropout_transition=2,aresample=async=1,aformat=sample_rates=48000:channel_layouts=stereo[aout]'
                    logger.info(f"   🎵 合并配音和音效")
            elif has_audio:
                # 只有配音：保留完整音频，用 apad 填充到目标时长
                if target_duration:
                    audio_filter = (
                        f'[{audio_index}:a]asetpts=PTS-STARTPTS,'
                        f'volume={voice_volume},apad=whole_dur={target_duration:.3f},'
                        f'aresample=async=1,aformat=sample_rates=48000:channel_layouts=stereo,'
                        f'atrim=0:{target_duration:.3f},asetpts=PTS-STARTPTS[aout]'
                    )
                else:
                    audio_filter = f'[{audio_index}:a]volume={voice_volume},aresample=async=1,aformat=sample_rates=48000:channel_layouts=stereo[aout]'
                logger.info(f"   🎵 合并配音（目标时长{target_duration:.3f}秒）")
            else:
                # 只有音效：截断/填充到目标时长
                if target_duration:
                    audio_filter = (
                        f'[{sound_effect_index}:a]atrim=0:{target_duration:.3f},asetpts=PTS-STARTPTS,'
                        f'volume=0.8,apad=whole_dur={target_duration:.3f},'
                        f'aresample=async=1,aformat=sample_rates=48000:channel_layouts=stereo,'
                        f'atrim=0:{target_duration:.3f},asetpts=PTS-STARTPTS[aout]'
                    )
                    logger.info(f"   🔊 合并音效（目标时长{target_duration:.3f}秒）")
                else:
                    audio_filter = f'[{sound_effect_index}:a]volume=0.8,aresample=async=1,aformat=sample_rates=48000:channel_layouts=stereo[aout]'
                    logger.info(f"   🔊 合并音效")

            # 构建视频滤镜：如果音频比视频长，根据差值决定策略
            # tpad 冻结帧仅用于 ≤1秒 的微小差异，超过1秒则裁剪音频（上游分镜拆分应处理）
            if need_extend_video and target_duration:
                extend_dur = target_duration - video_duration
                if extend_dur <= 1.0:
                    # 微小差异：用 tpad 冻结最后一帧（可接受）
                    video_filter = f'[0:v]tpad=stop_mode=clone:stop_duration={extend_dur:.3f}[vout]'
                    video_map = '[vout]'
                    logger.info(f"   🎬 延长视频 {extend_dur:.3f}秒（冻结最后一帧，≤1秒可接受）")
                else:
                    # 超过1秒：不延长视频，改为裁剪音频到视频时长
                    logger.warning(f"   ⚠️ 音频超出视频 {extend_dur:.3f}秒（>1秒），裁剪音频到视频时长。建议上游分镜拆分处理。")
                    target_duration = video_duration
                    need_extend_video = False
                    video_filter = None
                    video_map = '0:v:0'
            else:
                video_filter = None
                video_map = '0:v:0'

            # 始终使用重编码模式，copy 模式在有 filter_complex 时不可靠
            force_reencode = True

            # 合并视频滤镜和音频滤镜到 filter_complex
            if video_filter:
                full_filter = f'{video_filter};{audio_filter}'
            else:
                full_filter = audio_filter

            # 输出时长限制
            t_args = ['-t', f'{target_duration:.3f}'] if target_duration else []

            # 如果是 WebP 或需要延长视频，必须重编码
            if is_webp or force_reencode:
                if is_webp:
                    logger.info(f"   ⚠️ 检测到 WebP 格式，使用重编码模式...")
                cmd.extend([
                    '-c:v', 'libx264',
                    '-preset', 'ultrafast',
                    '-crf', '23',
                    '-pix_fmt', 'yuv420p',
                    '-filter_complex', full_filter,
                    '-c:a', 'aac',
                    '-b:a', '192k',
                    '-ar', '48000',
                    '-ac', '2',
                    '-map', video_map,
                    '-map', '[aout]',
                    *t_args,
                    '-avoid_negative_ts', 'make_zero',
                    '-fflags', '+genpts',
                    output_path
                ])
                subprocess.run(cmd, check=True, capture_output=True)
            else:
                # 尝试使用 copy 模式（视频不重编码，快速）
                cmd_copy = cmd + [
                    '-c:v', 'copy',
                    '-filter_complex', full_filter,
                    '-c:a', 'aac',
                    '-b:a', '192k',
                    '-ar', '48000',
                    '-ac', '2',
                    '-map', video_map,
                    '-map', '[aout]',
                    *t_args,
                    '-avoid_negative_ts', 'make_zero',
                    '-fflags', '+genpts',
                    '-async', '1',
                    output_path
                ]
                result = subprocess.run(cmd_copy, capture_output=True)

                # 如果 copy 失败，使用重编码模式
                if result.returncode != 0:
                    logger.warning(f"   ⚠️ copy模式失败，尝试重编码模式...")
                    cmd_reencode = cmd + [
                        '-c:v', 'libx264',
                        '-preset', 'fast',
                        '-filter_complex', full_filter,
                        '-c:a', 'aac',
                        '-b:a', '192k',
                        '-ar', '48000',
                        '-ac', '2',
                        '-map', video_map,
                        '-map', '[aout]',
                        *t_args,
                        '-avoid_negative_ts', 'make_zero',
                        '-fflags', '+genpts',
                        '-async', '1',
                        output_path
                    ]
                    subprocess.run(cmd_reencode, check=True, capture_output=True)

            logger.info(f"   ✅ 音频/音效合并成功: {Path(output_path).name}")

            # 验证：分别检查视频流和音频流时长，确保音频不超过视频
            # 这是关键修复：AAC 编码器会对齐帧边界（约 21-23ms），可能导致音频略长于视频
            try:
                # 获取视频流时长
                v_probe_cmd = [
                    'ffprobe', '-v', 'error',
                    '-select_streams', 'v:0',
                    '-show_entries', 'stream=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    output_path
                ]
                v_result = subprocess.run(v_probe_cmd, capture_output=True, text=True, check=True)
                output_video_duration = float(v_result.stdout.strip())

                # 获取音频流时长
                a_probe_cmd = [
                    'ffprobe', '-v', 'error',
                    '-select_streams', 'a:0',
                    '-show_entries', 'stream=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    output_path
                ]
                a_result = subprocess.run(a_probe_cmd, capture_output=True, text=True, check=True)
                output_audio_duration = float(a_result.stdout.strip())

                # 计算音视频时长差异（容忍 5ms 的误差）
                av_diff = output_audio_duration - output_video_duration
                tolerance_ms = 5  # 5ms 容忍度

                if av_diff > tolerance_ms / 1000:
                    logger.warning(f"   ⚠️ 音频({output_audio_duration:.3f}s) > 视频({output_video_duration:.3f}s)，差异 {av_diff*1000:.1f}ms")
                    # 重新编码音频以精确截断到视频时长
                    temp_output = str(Path(output_path).parent / f"temp_fix_{Path(output_path).name}")

                    # 使用 PCM 中间格式避免 AAC 帧对齐问题，然后再编码为 AAC
                    # 更精确的方法：直接重新合成，使用视频时长作为严格限制
                    fix_cmd = [
                        'ffmpeg', '-y',
                        '-i', output_path,
                        '-c:v', 'copy',
                        '-af', f'atrim=0:{output_video_duration:.6f},asetpts=PTS-STARTPTS',
                        '-c:a', 'aac',
                        '-b:a', '192k',
                        '-ar', '48000',
                        '-ac', '2',
                        temp_output
                    ]
                    subprocess.run(fix_cmd, check=True, capture_output=True)

                    # 验证修复后的时长
                    # 注意：需要完整的 ffprobe 命令，不能使用切片（之前 a_probe_cmd[:5] 会丢失 -show_entries 和 -of 参数）
                    a_check_cmd = [
                        'ffprobe', '-v', 'error',
                        '-select_streams', 'a:0',
                        '-show_entries', 'stream=duration',
                        '-of', 'default=noprint_wrappers=1:nokey=1',
                        temp_output
                    ]
                    a_check = subprocess.run(a_check_cmd, capture_output=True, text=True)
                    if a_check.returncode == 0:
                        fixed_audio_dur = float(a_check.stdout.strip())
                        fixed_diff = fixed_audio_dur - output_video_duration
                        if fixed_diff <= tolerance_ms / 1000:
                            import shutil
                            shutil.move(temp_output, output_path)
                            logger.info(f"   ✅ 已修复音频时长: {output_audio_duration:.3f}s → {fixed_audio_dur:.3f}s (差异 {fixed_diff*1000:.1f}ms)")
                        else:
                            # 修复失败，删除临时文件
                            Path(temp_output).unlink(missing_ok=True)
                            logger.warning(f"   ⚠️ 音频时长修复效果有限: {fixed_audio_dur:.3f}s (仍差 {fixed_diff*1000:.1f}ms)")
                    else:
                        Path(temp_output).unlink(missing_ok=True)
                        logger.warning(f"   ⚠️ 无法验证修复结果")
                else:
                    logger.info(f"   ✅ 验证通过：视频={output_video_duration:.3f}s 音频={output_audio_duration:.3f}s (差异 {av_diff*1000:.1f}ms)")
            except Exception as e:
                logger.warning(f"   ⚠️ 无法验证输出时长: {e}")
                
        except subprocess.CalledProcessError as e:
            logger.error(f"   ❌ 音频合并失败: {e.stderr.decode() if e.stderr else str(e)}")
            # 如果合并失败，复制原视频
            import shutil
            shutil.copy2(video_path, output_path)


class AddBackgroundMusicTool(BaseTool):
    name: str = "添加背景音乐"
    description: str = (
        "为视频添加背景音乐，支持音量调节和音乐循环。"
    )
    args_schema: Type[BaseModel] = AddBackgroundMusicSchema

    def _remove_data_tracks(self, video_path: str) -> str:
        """
        移除视频中的 data 轨道（如字幕元数据），避免播放器显示错误时长

        Args:
            video_path: 视频文件路径

        Returns:
            处理后的视频路径（如果有 data 轨道则返回新路径，否则返回原路径）
        """
        try:
            # 检测是否有 data 轨道
            probe_cmd = [
                'ffprobe', '-v', 'error',
                '-select_streams', 'd',
                '-show_entries', 'stream=index,codec_type',
                '-of', 'csv=p=0',
                video_path
            ]
            result = subprocess.run(probe_cmd, capture_output=True, text=True)

            if not result.stdout.strip():
                # 没有 data 轨道，直接返回原路径
                return video_path

            logger.info(f"🔧 检测到 data 轨道，正在移除以修复时长显示问题...")

            # 创建临时输出路径
            video_p = Path(video_path)
            temp_output = str(video_p.with_name(f"{video_p.stem}_no_data{video_p.suffix}"))

            # 使用 ffmpeg 移除 data 轨道，只保留视频和音频
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-map', '0:v:0',  # 只映射第一个视频流
                '-map', '0:a:0',  # 只映射第一个音频流
                '-map_chapters', '-1',  # 移除章节元数据，避免播放器显示错误时长
                '-c', 'copy',     # 复制编码，不重新编码
                temp_output
            ]

            subprocess.run(cmd, check=True, capture_output=True)

            # 替换原文件
            import os
            os.replace(temp_output, video_path)
            logger.info(f"   ✅ data 轨道已移除")

            return video_path

        except Exception as e:
            logger.warning(f"⚠️ 移除 data 轨道失败: {e}，使用原视频")
            return video_path

    def _check_video_has_audio(self, video_path: str) -> bool:
        """检测视频是否包含音频流，并且音频时长是否有意义（>1秒）"""
        try:
            # 检查是否有音频流
            cmd = [
                'ffprobe', '-v', 'error',
                '-select_streams', 'a:0',
                '-show_entries', 'stream=codec_type',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            has_audio = result.stdout.strip() == 'audio'

            if not has_audio:
                logger.info(f"🔍 视频音频检测: 无音频流")
                return False

            # 检查音频时长
            cmd_duration = [
                'ffprobe', '-v', 'error',
                '-select_streams', 'a:0',
                '-show_entries', 'stream=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            result_duration = subprocess.run(cmd_duration, capture_output=True, text=True)
            try:
                audio_duration = float(result_duration.stdout.strip())
                # 如果音频时长小于1秒，认为是无意义的音频（比如封面视频的静音）
                if audio_duration < 1.0:
                    logger.info(f"🔍 视频音频检测: 有音频流但时长很短({audio_duration:.2f}秒)，视为无音频")
                    return False
                else:
                    logger.info(f"🔍 视频音频检测: 有音频流，时长{audio_duration:.2f}秒")
                    return True
            except (ValueError, AttributeError):
                logger.info(f"🔍 视频音频检测: 有音频流但无法获取时长，视为有音频")
                return True

        except Exception as e:
            logger.warning(f"⚠️ 音频流检测失败: {str(e)}，假定视频无音频")
            return False

    def _run(
        self,
        video_path: str,
        music_path: str,
        output_path: Optional[str] = None,
        music_volume: float = 0.15
    ) -> Dict[str, Any]:
        """
        为视频添加背景音乐

        Args:
            video_path: 视频文件路径
            music_path: 背景音乐文件路径
            output_path: 输出视频路径（可选）
            music_volume: 背景音乐音量（0.0-1.0）

        Returns:
            包含处理结果的字典
        """
        try:
            if not Path(music_path).exists():
                logger.warning(f"⚠️ 背景音乐文件不存在: {music_path}")
                return {
                    'status': 'failed',
                    'error': '背景音乐文件不存在',
                    'output_path': video_path,
                    'message': '⚠️ 背景音乐文件不存在，跳过添加'
                }

            # 如果没有指定输出路径，使用临时文件后覆盖原文件
            if not output_path:
                video_p = Path(video_path)
                output_path = str(video_p.with_name(f"{video_p.stem}_temp_with_music{video_p.suffix}"))
                replace_original = True
            else:
                replace_original = False

            logger.info("🎵 添加背景音乐...")
            logger.info(f"   视频: {video_path}")
            logger.info(f"   音乐: {music_path}")
            logger.info(f"   音量: {music_volume}")

            # 检测视频是否有音频流
            has_audio = self._check_video_has_audio(video_path)

            # 根据视频是否有音频流，使用不同的 ffmpeg 命令
            if has_audio:
                # 视频有音频：混合原视频音频和背景音乐
                logger.info("🎵 视频有音频流，将混合原音频和背景音乐")
                logger.info(f"   原视频音量: 1.0x (保持原音量)，背景音乐音量: {music_volume}")
                # 修复：只循环音乐，不循环视频！这样-shortest才能正确工作
                cmd = [
                    'ffmpeg', '-y',
                    '-loglevel', 'error',
                    '-i', video_path,  # 视频不循环
                    '-stream_loop', '-1',  # 只循环背景音乐
                    '-i', music_path,
                    '-filter_complex',
                    f'[0:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=1.0[voice];'
                    f'[1:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={music_volume}[music];'
                    '[voice][music]amix=inputs=2:duration=shortest:dropout_transition=0.2[aout]',
                    '-map', '0:v:0',  # 只映射第一个视频流
                    '-map', '[aout]',
                    '-dn',  # 禁用数据流（字幕等），避免时长不一致问题
                    '-map_chapters', '-1',  # 禁止复制章节元数据，避免播放器显示错误时长
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    '-b:a', '192k',
                    '-ar', '48000',
                    '-ac', '2',
                    '-shortest',  # 让输出与视频同长
                    output_path
                ]
            else:
                # 视频无音频：直接添加背景音乐作为音频流
                logger.info("🎵 视频无音频流，将添加背景音乐作为音频")
                # 简化方案：不使用aloop，直接使用-stream_loop让音乐循环
                cmd = [
                    'ffmpeg', '-y',
                    '-loglevel', 'error',
                    '-i', video_path,
                    '-stream_loop', '-1',  # 循环音乐
                    '-i', music_path,
                    '-filter_complex',
                    f'[1:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={music_volume}[aout]',
                    '-map', '0:v:0',  # 只映射第一个视频流
                    '-map', '[aout]',
                    '-dn',  # 禁用数据流（字幕等），避免时长不一致问题
                    '-map_chapters', '-1',  # 禁止复制章节元数据，避免播放器显示错误时长
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    '-b:a', '192k',
                    '-ar', '48000',
                    '-ac', '2',
                    '-shortest',  # 让输出与视频同长
                    output_path
                ]

            # 使用 capture_output=True 来捕获输出，避免 DEVNULL 可能导致的问题
            # 这样即使 ffmpeg 产生输出，也会被 Python 进程正确处理
            logger.info("⏳ 正在添加背景音乐，请稍候（这可能需要一些时间）...")
            logger.info(f"   提示: 正在处理视频，视频越长耗时越久")
            result = subprocess.run(cmd, check=True,
                                   capture_output=True,
                                   text=True)

            # 如果需要覆盖原文件
            if replace_original:
                import os
                os.replace(output_path, video_path)
                output_path = video_path

            # 清理 data 轨道（如果存在），避免播放器显示错误时长
            output_path = self._remove_data_tracks(output_path)

            logger.info(f"✅ 背景音乐添加完成: {output_path}")

            return {
                'status': 'success',
                'output_path': output_path,
                'message': '✅ 背景音乐添加成功'
            }

        except subprocess.CalledProcessError as e:
            error_msg = f"ffmpeg 执行失败，返回码: {e.returncode}"
            logger.error(f"❌ 背景音乐添加失败: {error_msg}")
            logger.error(f"   命令: {' '.join(cmd)}")
            
            # 输出 ffmpeg 的错误信息
            if e.stderr:
                logger.error(f"   FFmpeg 错误输出:")
                for line in e.stderr.split('\n')[:20]:  # 只显示前20行
                    if line.strip():
                        logger.error(f"     {line}")
            
            if e.stdout:
                logger.error(f"   FFmpeg 标准输出:")
                for line in e.stdout.split('\n')[:10]:  # 只显示前10行
                    if line.strip():
                        logger.error(f"     {line}")

            # 清理临时文件
            if replace_original and Path(output_path).exists():
                Path(output_path).unlink()

            return {
                'status': 'failed',
                'error': error_msg,
                'stderr': e.stderr if e.stderr else '',
                'output_path': video_path,
                'message': f'❌ 背景音乐添加失败: {error_msg}'
            }
        except Exception as e:
            logger.error(f"❌ 背景音乐添加失败: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e),
                'output_path': video_path,
                'message': f'❌ 背景音乐添加失败: {str(e)}'
            }
