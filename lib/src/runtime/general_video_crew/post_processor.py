#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
后期处理 runtime 模块
负责视频后期处理（字幕、拼接、背景音乐、社交媒体文案等）
"""

import re
import subprocess
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from custom_tools.video_processing import (
    ConcatenateVideosTool,
    AddBackgroundMusicTool,
    VideoTimeLengthManager,
    AdaptiveSubtitleProcessor,
    FlexibleSubtitleProcessor,
    SubtitleStyleParser
)
from custom_tools.utilities import SocialMediaCopywritingTool
from src.logger import get_logger
from src.utils.music_utils import MusicManager
from src.utils.sound_effects_utils import SoundEffectsManager
from .config import CONFIG, VIDEO_TYPE, SUBTITLE_LANG

logger = get_logger('post_processor')


class PostProcessor:
    """视频后期处理器"""

    def __init__(self):
        """初始化后期处理器"""
        self.concat_tool = ConcatenateVideosTool()
        self.bgm_tool = AddBackgroundMusicTool()
        self.social_media_tool = SocialMediaCopywritingTool()

    def add_subtitles(
        self,
        video_result: Dict,
        storyboard: List[Dict],
        user_requirements: str,
        output_dir: str,
        custom_font_path: str = None
    ) -> Dict:
        """
        为所有视频添加字幕

        Args:
            video_result: 视频生成结果
            storyboard: 分镜列表
            user_requirements: 用户需求
            output_dir: 输出目录
            custom_font_path: 自定义字体路径

        Returns:
            字幕添加结果
        """
        custom_font_path = custom_font_path or CONFIG.DEFAULT_FONT_PATH

        video_outputs = video_result.get('outputs', {})
        subtitled_outputs = {}

        # 解析用户样式配置
        style_config = SubtitleStyleParser.merge_user_style_to_scene(user_requirements, storyboard)
        use_flexible = style_config.get('use_flexible_subtitle', False)

        # 选择字幕处理器
        if use_flexible:
            subtitle_processor = FlexibleSubtitleProcessor()
            logger.info(f"💬 使用灵活字幕系统（支持多层字幕和自定义样式）")
        else:
            subtitle_processor = AdaptiveSubtitleProcessor()
            logger.info(f"💬 使用默认自适应字幕系统")

        # 检测字幕语言
        subtitle_language = self._detect_subtitle_language(storyboard, user_requirements)
        logger.info(f"💬 检测到字幕语言: {subtitle_language}")

        subtitled_dir = Path(output_dir) / 'subtitled'
        subtitled_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"💬 为 {len(storyboard)} 个视频添加字幕...")

        success_count = 0
        failed_count = 0

        for i, scene in enumerate(storyboard):
            video_path = video_outputs.get(i)

            if not video_path or (isinstance(video_path, str) and video_path.startswith("错误")):
                failed_count += 1
                continue

            try:
                if not Path(video_path).exists():
                    failed_count += 1
                    continue
            except (OSError, ValueError):
                failed_count += 1
                continue

            try:
                output_path = subtitled_dir / f"scene_{i:02d}_with_subtitles.mp4"

                if use_flexible:
                    subtitle_layers = SubtitleStyleParser.build_subtitle_layers_for_scene(
                        scene, style_config, scene.get('duration', CONFIG.DEFAULT_SCENE_DURATION)
                    )

                    if not subtitle_layers:
                        subtitled_outputs[i] = video_path
                        failed_count += 1
                        continue

                    result = subtitle_processor._run(
                        video_path=video_path,
                        subtitles=subtitle_layers,
                        output_path=str(output_path),
                        language=subtitle_language,
                        custom_font_path=custom_font_path
                    )
                else:
                    subtitle_text = scene.get('subtitle_text', '')
                    if not subtitle_text:
                        narration = scene.get('narration', '')
                        if narration:
                            subtitle_text = narration.strip()[:30]

                    if not subtitle_text:
                        subtitled_outputs[i] = video_path
                        failed_count += 1
                        continue

                    result = subtitle_processor._run(
                        video_path=video_path,
                        subtitle_text=subtitle_text,
                        output_path=str(output_path),
                        position=CONFIG.DEFAULT_SUBTITLE_POSITION,
                        language=subtitle_language,
                        font_color=CONFIG.DEFAULT_FONT_COLOR,
                        border_color=CONFIG.DEFAULT_BORDER_COLOR,
                        border_width=CONFIG.DEFAULT_BORDER_WIDTH,
                        background_color="",
                        display_start=0.0,
                        display_duration=0.0,
                        fade_in=CONFIG.DEFAULT_FADE_IN,
                        fade_out=CONFIG.DEFAULT_FADE_OUT,
                        custom_font_path=custom_font_path,
                        force_single_line=False
                    )

                if result.get('status') == 'success':
                    subtitled_outputs[i] = result['output_path']
                    success_count += 1
                else:
                    subtitled_outputs[i] = video_path
                    failed_count += 1

            except Exception as e:
                logger.error(f"❌ 场景{i}字幕添加异常: {str(e)[:100]}")
                subtitled_outputs[i] = video_path
                failed_count += 1

        logger.info(f"💬 字幕添加完成: 成功{success_count}, 失败{failed_count}")

        return {
            'outputs': subtitled_outputs,
            'summary': {
                'total': len(storyboard),
                'successful': success_count,
                'failed': failed_count
            }
        }

    def concatenate_videos(
        self,
        video_result: Dict,
        audio_result,
        storyboard: List[Dict],
        cover_image: str,
        output_path: str,
        temp_dir: Path,
        voice_volume: float = 1.5,
        sound_effects: Dict[int, str] = None,
        image_result: Dict = None,
        execution_directive: Dict | None = None
    ) -> str:
        """
        拼接所有视频片段并合并音频

        Args:
            video_result: 视频生成结果
            audio_result: 音频生成结果
            storyboard: 分镜列表
            cover_image: 封面图片路径
            output_path: 输出路径
            temp_dir: 临时目录
            voice_volume: 配音音量倍数，默认1.5（即150%）
            sound_effects: 音效配置字典 {分镜索引: 音效文件名}
            image_result: 图片生成结果，用于口型同步
            execution_directive: 胶囊输出契约翻译出的后处理指令

        Returns:
            拼接后的视频路径
        """
        temp_dir = Path(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        video_outputs = video_result.get('outputs', {})

        # 提取图片输出（用于口型同步）
        image_outputs = {}
        if image_result and isinstance(image_result, dict):
            image_outputs = image_result.get('outputs', {})

        # 兼容处理 audio_result 的不同格式
        if isinstance(audio_result, dict):
            audio_outputs = audio_result.get('outputs', [])
        elif isinstance(audio_result, list):
            audio_outputs = audio_result
        else:
            audio_outputs = []

        # 准备视频、音频和音效路径列表
        video_paths = []
        audio_paths = []
        sound_effect_paths = []

        # 初始化音效字典
        if sound_effects is None:
            sound_effects = {}

        for i in range(len(storyboard)):
            video_path = video_outputs.get(i)

            if not video_path or (isinstance(video_path, str) and video_path.startswith("错误")):
                continue

            try:
                if not Path(video_path).exists():
                    continue
            except (OSError, ValueError):
                continue

            # 获取对应的音频路径
            if isinstance(audio_outputs, list):
                audio_path = audio_outputs[i] if i < len(audio_outputs) else None
            else:
                audio_path = None

            video_gen_type = storyboard[i].get('video_generation_type', VIDEO_TYPE.IMAGE_TO_VIDEO)
            if video_gen_type not in (VIDEO_TYPE.IMAGE_TO_VIDEO, 'text_to_video'):
                logger.warning(f"  场景{i}: 不支持的 video_generation_type={video_gen_type}，按普通视频片段处理")

            # 常规模式：根据时长进行剪辑
            scene_duration = storyboard[i].get('duration', CONFIG.DEFAULT_SCENE_DURATION)
            actual_video_duration = VideoTimeLengthManager.get_video_duration(video_path)

            audio_duration = None
            if audio_path and Path(audio_path).exists():
                audio_duration = VideoTimeLengthManager.get_audio_duration(audio_path)

            # 计算最终时长
            final_duration = VideoTimeLengthManager.calculate_final_duration(
                scene_duration, actual_video_duration, audio_duration, i
            )

            # 如果需要剪辑视频
            if final_duration < actual_video_duration:
                logger.info(f"  场景{i}: 剪辑视频从 {actual_video_duration:.2f}秒 到 {final_duration:.2f}秒")
                trimmed_video_path = temp_dir / f'scene_{i:02d}_trimmed.mp4'
                success = VideoTimeLengthManager.trim_video(video_path, str(trimmed_video_path), final_duration)
                if success:
                    video_path = str(trimmed_video_path)
                    # 重要：更新actual_video_duration为剪辑后的时长
                    actual_video_duration = final_duration

            # 如果音频比视频长，不再截断音频，让 ConcatenateVideosTool 自动用最后一帧延长视频来补齐
            if audio_path and audio_duration and audio_duration > actual_video_duration:
                logger.info(f"  场景{i}: 音频{audio_duration:.2f}秒 > 视频{actual_video_duration:.2f}秒，保留完整音频，下游自动延长视频")

            # 处理音效：根据实际视频时长截断音效（使用更新后的actual_video_duration）
            sound_effect_path = self._process_sound_effect(i, sound_effects, video_path, actual_video_duration, temp_dir)

            video_path = self._apply_post_steps(video_path, temp_dir, i, execution_directive)

            video_paths.append(video_path)
            audio_paths.append(audio_path)
            sound_effect_paths.append(sound_effect_path)

        if not video_paths:
            raise ValueError("没有可用的视频文件进行拼接")

        logger.info(f"📊 拼接统计: {len(video_paths)} 个视频")

        # 先将封面图片转换为视频
        if cover_image and Path(cover_image).exists():
            logger.info("🖼️ 将封面图片转换为0.1秒视频...")
            cover_video_path = self._create_cover_video(cover_image, video_paths[0], temp_dir)
            if cover_video_path:
                video_paths.insert(0, cover_video_path)
                audio_paths.insert(0, None)
                sound_effect_paths.insert(0, None)  # 封面视频不添加音效

        # 使用拼接工具
        result = self.concat_tool._run(
            video_paths=video_paths,
            output_path=str(output_path),
            audio_paths=audio_paths if any(audio_paths) else None,
            voice_volume=voice_volume,
            sound_effect_paths=sound_effect_paths if any(sound_effect_paths) else None
        )

        if result.get('status') == 'failed':
            raise ValueError(result.get('error', '视频拼接失败'))

        return result['output_path']

    def _apply_post_steps(
        self,
        video_path: str,
        temp_dir: Path,
        scene_index: int,
        execution_directive: Dict | None
    ) -> str:
        """Apply capsule-directed per-scene video post steps before concat."""
        if not isinstance(execution_directive, dict):
            return video_path

        post_steps = {
            str(step).strip()
            for step in execution_directive.get('post_steps', [])
            if str(step).strip()
        }
        if not post_steps:
            return video_path

        if 'mute_audio' in post_steps or 'strip_voice' in post_steps:
            video_path = self._strip_audio_track(video_path, temp_dir, scene_index)

        if 'overlay_text' in post_steps:
            logger.warning("⚠️ capsule post_step=overlay_text 尚未接入具体文字源，保持原视频")

        return video_path

    def _strip_audio_track(self, video_path: str, temp_dir: Path, scene_index: int) -> str:
        """Return a copy of the scene video with its audio stream removed."""
        temp_dir = Path(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        output_path = temp_dir / f"scene_{scene_index:02d}_muted.mp4"

        cmd = [
            'ffmpeg',
            '-y',
            '-i', video_path,
            '-map', '0:v:0',
            '-c:v', 'copy',
            '-an',
            str(output_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"🔇 场景{scene_index}: 已按胶囊契约移除片段原生音轨")
            return str(output_path)
        except Exception as exc:
            logger.warning(f"⚠️ 场景{scene_index}: 移除片段原生音轨失败，保留原视频: {exc}")
            return video_path

    def add_background_music(
        self,
        video_path: str,
        music_selection: Dict,
        needs_bgm: bool,
        user_config_enabled: bool,
        manual_music_path: str = None,
        bgm_volume: float = None,
        generated_music_dir: str = None
    ) -> str:
        """
        添加背景音乐

        Args:
            video_path: 视频路径
            music_selection: 在线音乐风格与生成查询
            needs_bgm: AI判断是否需要BGM
            user_config_enabled: 用户配置是否启用BGM
            manual_music_path: 用户手动指定的音乐路径；默认流程不读取本地音乐库
            bgm_volume: 用户指定的背景音乐音量（如果为None，则使用music_selection中的音量或默认值）

        Returns:
            添加BGM后的视频路径（失败返回原视频路径）
        """
        if not isinstance(music_selection, dict):
            music_selection = {}

        should_add_music = MusicManager.should_add_music(
            music_selection=music_selection,
            needs_bgm=needs_bgm,
            user_config_enabled=user_config_enabled
        )

        if not should_add_music:
            logger.info("⏭️  跳过背景音乐添加（AI判断不需要或用户禁用）")
            return video_path

        logger.info("🎵 添加背景音乐...")
        music_path = MusicManager.get_music_path(
            music_selection=music_selection,
            manual_path=manual_music_path
        )
        if not music_path:
            music_path = MusicManager.resolve_online_music_path(
                music_selection=music_selection,
                output_dir=generated_music_dir,
                logger=logger,
            )

        if not music_path:
            music_path = self._generate_online_background_music(
                music_selection=music_selection,
                output_dir=generated_music_dir
            )

        if not music_path:
            logger.warning("⚠️ 未找到或生成有效的背景音乐，跳过添加")
            return video_path

        # 优先使用用户指定的音量，其次使用AI选择的音量，最后使用默认值
        if bgm_volume is not None:
            music_volume = bgm_volume
            logger.info(f"🎵 使用用户指定的背景音乐音量: {music_volume}")
        else:
            music_volume = music_selection.get('music_volume', CONFIG.DEFAULT_MUSIC_VOLUME)
            logger.info(f"🎵 使用AI选择的背景音乐音量: {music_volume}")

        video_file = Path(video_path)
        bgm_suffix = '_with_bgm'
        if video_file.stem.endswith(bgm_suffix):
            bgm_suffix = f"_bgm_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        bgm_output_path = video_file.with_name(f"{video_file.stem}{bgm_suffix}{video_file.suffix}")

        result = self.bgm_tool._run(
            video_path=video_path,
            music_path=music_path,
            output_path=str(bgm_output_path),
            music_volume=music_volume
        )

        if result.get('status') == 'success':
            logger.info(f"✅ 背景音乐添加成功")
            return result['output_path']
        else:
            logger.warning(f"⚠️ 背景音乐添加失败: {result.get('error', '未知错误')}")
            return video_path

    def _generate_online_background_music(self, music_selection: Dict, output_dir: str = None) -> Optional[str]:
        """Generate and download background music online when no manual audio path is supplied."""
        if not isinstance(music_selection, dict):
            return None
        if music_selection.get('music_source') not in (None, '', 'online'):
            return None

        output_dir = output_dir or str(Path.cwd() / 'generated_music')
        query = (
            music_selection.get('music_query')
            or music_selection.get('generation_prompt')
            or music_selection.get('reason')
            or 'short instrumental background music, no vocals'
        )
        style_id = (
            music_selection.get('music_style_id')
            or music_selection.get('style_id')
            or music_selection.get('style')
            or 'auto'
        )
        description = (
            f"{query}. Create short instrumental background music for a video. "
            "No vocals, no lyrics, clean mix, loop-friendly, suitable for voiceover."
        )
        tags = f"instrumental, background music, no vocals, {style_id}"

        try:
            from custom_tools.music_generation import UniversalMusicGenerationTool

            logger.info(f"🌐 在线生成背景音乐: style={style_id}")
            result = UniversalMusicGenerationTool()._run(
                description=description,
                provider='suno',
                mode='custom',
                title=f"bgm_{style_id}",
                tags=tags,
                output_dir=output_dir,
                make_instrumental=True,
                wait_for_completion=True,
            )
        except Exception as exc:
            logger.warning(f"⚠️ 在线背景音乐生成异常: {exc}")
            return None

        if not isinstance(result, dict) or not result.get('success'):
            logger.warning(f"⚠️ 在线背景音乐生成失败: {result}")
            return None

        for song in result.get('songs', []):
            local_path = song.get('local_path')
            if local_path and Path(local_path).exists():
                logger.info(f"✅ 在线背景音乐已下载: {local_path}")
                return local_path

        logger.warning("⚠️ 在线背景音乐生成完成但没有可用本地音频")
        return None

    def generate_social_media_copywriting(
        self,
        video_path: str,
        user_requirements: str,
        platform: str,
        workspace_dir: str
    ) -> Dict:
        """
        生成社交媒体文案

        Args:
            video_path: 视频路径
            user_requirements: 用户需求
            platform: 目标平台
            workspace_dir: 工作空间目录

        Returns:
            文案生成结果
        """
        logger.info("🤖 生成社交媒体文案...")

        video_info = {
            "user_requirements": user_requirements,
            "platform": platform
        }

        result = self.social_media_tool._run(
            video_path=video_path,
            video_info=video_info,
            platform=platform.lower() if platform else 'douyin',
            output_dir=workspace_dir
        )

        return result

    def _process_sound_effect(
        self,
        scene_index: int,
        sound_effects: Dict[int, str],
        video_path: str,
        video_duration: float,
        temp_dir: Path
    ) -> Optional[str]:
        """
        处理单个分镜的音效

        Args:
            scene_index: 分镜索引
            sound_effects: 音效配置字典 {分镜索引: 音效文件名}
            video_path: 视频文件路径
            video_duration: 视频时长(秒)
            temp_dir: 临时目录

        Returns:
            处理后的音效文件路径，如果没有音效则返回None
        """
        # 检查该分镜是否有音效配置
        if scene_index not in sound_effects:
            return None

        sound_effect_filename = sound_effects[scene_index]
        if not sound_effect_filename:
            return None

        # 获取音效文件路径
        sound_effect_path = SoundEffectsManager.get_sound_effect_path(sound_effect_filename)
        if not sound_effect_path:
            logger.warning(f"  场景{scene_index}: 音效文件不存在: {sound_effect_filename}")
            return None

        # 获取音效时长
        sound_effect_duration = VideoTimeLengthManager.get_audio_duration(sound_effect_path)
        if not sound_effect_duration:
            logger.warning(f"  场景{scene_index}: 无法获取音效时长: {sound_effect_filename}")
            return None

        # 只在音效超长时才截断，不要移除静音！
        # 原因：音效的静音部分可能是有意设计的（配合画面时间点）
        # 移除静音会导致音效提前播放，与画面不同步
        if sound_effect_duration > video_duration:
            logger.info(f"  场景{scene_index}: 音效过长，需要截断 (原始{sound_effect_duration:.2f}秒 → 目标{video_duration:.2f}秒)")
            trimmed_sound_effect_path = temp_dir / f'scene_{scene_index:02d}_sound_effect_trimmed.mp3'

            # 简单截断：保持音效原始时间点，只截断长度
            success = VideoTimeLengthManager.trim_audio(
                sound_effect_path,
                str(trimmed_sound_effect_path),
                video_duration
            )

            if success:
                # 验证截断后的时长
                trimmed_duration = VideoTimeLengthManager.get_audio_duration(str(trimmed_sound_effect_path))
                if trimmed_duration:
                    logger.info(f"  场景{scene_index}: ✅ 音效截断成功 {sound_effect_duration:.2f}s → {trimmed_duration:.3f}s")
                return str(trimmed_sound_effect_path)
            else:
                logger.warning(f"  场景{scene_index}: ⚠️ 音效截断失败，使用原音效")
                return sound_effect_path
        else:
            logger.info(f"  场景{scene_index}: 添加音效 {sound_effect_filename} (时长{sound_effect_duration:.2f}秒)")
            return sound_effect_path

    def _detect_subtitle_language(self, storyboard: List[Dict], user_requirements: str) -> str:
        """
        检测字幕语言

        优先级：
        1. 检查用户需求中的明确语言要求
        2. 检查分镜中的字幕文本语言
        3. 默认返回中文

        Args:
            storyboard: 分镜列表
            user_requirements: 用户需求

        Returns:
            语言代码: "en" 或 "zh"
        """
        # 1. 检查用户需求中的语言关键词
        user_req_lower = user_requirements.lower()

        # 英文关键词
        if re.search(r'(英文字幕|english subtitle|英语字幕|字幕.*英文|subtitle.*english)', user_req_lower, re.IGNORECASE):
            return SUBTITLE_LANG.ENGLISH

        # 中文关键词
        if re.search(r'(中文字幕|chinese subtitle|中文|字幕.*中文)', user_req_lower, re.IGNORECASE):
            return SUBTITLE_LANG.CHINESE

        # 2. 检查分镜中的字幕文本（采样前3个分镜）
        sample_texts = []
        for i, scene in enumerate(storyboard[:3]):
            subtitle_text = scene.get('subtitle_text', '') or scene.get('narration', '')
            if subtitle_text:
                sample_texts.append(subtitle_text)

        if sample_texts:
            # 统计英文字符和中文字符的比例
            combined_text = ''.join(sample_texts)
            english_chars = len(re.findall(r'[a-zA-Z]', combined_text))
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', combined_text))

            # 如果英文字符数 > 中文字符数的2倍，判定为英文
            if english_chars > chinese_chars * 2:
                return SUBTITLE_LANG.ENGLISH

        # 3. 默认返回中文
        return SUBTITLE_LANG.CHINESE

    def _create_cover_video(self, cover_image: str, reference_video: str, temp_dir: Path) -> str:
        """
        将封面图片转换为视频

        Args:
            cover_image: 封面图片路径
            reference_video: 参考视频（用于获取分辨率和帧率）
            temp_dir: 临时目录

        Returns:
            封面视频路径
        """
        cover_video_path = temp_dir / 'cover_video.mp4'

        probe_cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,r_frame_rate',
            '-of', 'json',
            reference_video
        ]

        try:
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            video_info = json.loads(probe_result.stdout)
            stream = video_info['streams'][0]
            width = stream['width']
            height = stream['height']
            fps_str = stream['r_frame_rate']
            fps_num, fps_den = map(int, fps_str.split('/'))
            fps = fps_num / fps_den

            cmd = [
                'ffmpeg', '-loop', '1',
                '-i', cover_image,
                '-f', 'lavfi',
                '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
                '-t', str(CONFIG.COVER_DURATION),
                '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2',
                '-r', str(fps),
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-pix_fmt', 'yuv420p',
                '-shortest',
                '-y', str(cover_video_path)
            ]

            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"✅ 封面视频生成成功")
            return str(cover_video_path)

        except Exception as e:
            logger.warning(f"⚠️ 封面视频生成失败: {str(e)}")
            return None
