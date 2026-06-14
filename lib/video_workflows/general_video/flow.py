#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agno 通用视频生成 Flow 模块
整合 Agents 和增强的生成工具，实现完整的通用视频制作流程
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from tqdm import tqdm

from .crew import AgnoGeneralVideoCrew
from .config import CONFIG, MODE, validate_video_engine, get_recommended_engine, normalize_video_engine_name

from src.logger import get_logger
from src.base.video_flow_base import BaseVideoFlow

# Agno 负责规划，canonical runtime generators 负责实际生成和后处理。
from src.runtime.general_video_crew.audio_generator import AudioGenerator
from src.runtime.general_video_crew.image_generator import ImageGenerator
from src.runtime.general_video_crew.video_generator import VideoGenerator
from src.runtime.general_video_crew.post_processor import PostProcessor

logger = get_logger('general_video_flow')


class AgnoGeneralVideoFlow(BaseVideoFlow):
    """
    Agno 通用视频生成 Flow
    使用 Agno 框架的 Agent 进行规划，然后使用工具生成视频
    """

    def __init__(self):
        """初始化 Agno 通用视频生成 Flow"""
        super().__init__()
        self.crew = AgnoGeneralVideoCrew()

        # 初始化 runtime generator 模块。
        self.audio_generator = AudioGenerator()
        self.image_generator = ImageGenerator()
        self.video_generator = VideoGenerator()
        self.post_processor = PostProcessor()

        logger.info("AgnoGeneralVideoFlow 初始化完成（使用 Agno 框架）")

    def run(self, user_requirements: str, target_duration: int = 30, **kwargs) -> Dict[str, Any]:
        """
        运行 Agno 通用视频生成流程

        Args:
            user_requirements: 用户要求
            target_duration: 目标视频时长（秒）
            **kwargs: 其他可选参数

        Returns:
            生成结果字典
        """
        try:
            logger.info("🎬 [Agno] 开始通用视频生成流程")
            start_time = time.time()  # 记录开始时间

            # 初始化状态
            self.state = {
                'user_requirements': user_requirements,
                'target_duration': target_duration,
                'aspect_ratio': kwargs.get('aspect_ratio', CONFIG.DEFAULT_ASPECT_RATIO),
                'platform': kwargs.get('platform', CONFIG.DEFAULT_PLATFORM),
                'add_subtitles': kwargs.get('add_subtitles', CONFIG.ENABLE_SUBTITLES),
                'add_background_music': kwargs.get('add_background_music', CONFIG.ENABLE_BACKGROUND_MUSIC),
                'generate_social_media_copywriting': kwargs.get('generate_social_media_copywriting', CONFIG.ENABLE_SOCIAL_MEDIA_COPYWRITING),
                'background_music_path': kwargs.get('background_music_path', None),
                'bgm_volume': kwargs.get('bgm_volume'),
                'voice_volume': kwargs.get('voice_volume', 1.5),
                'manual_video_engine': normalize_video_engine_name(kwargs.get('video_engine')) if kwargs.get('video_engine') else None,
                'enable_image_quality_check': kwargs.get('enable_image_quality_check', CONFIG.ENABLE_IMAGE_QUALITY_CHECK),
                'enable_video_quality_check': kwargs.get('enable_video_quality_check', CONFIG.ENABLE_VIDEO_QUALITY_CHECK),
                'audio_concurrency': kwargs.get('audio_concurrency', CONFIG.AUDIO_CONCURRENCY),
                'user_reference_images': kwargs.get('user_reference_images', []),
                'douyin_text': kwargs.get('douyin_text', ''),
                'capsule_name': kwargs.get('capsule_name'),
                'capsule_category': kwargs.get('capsule_category'),
                'capsule_config': kwargs.get('capsule_config', {}) or {},
            }

            # 处理抖音参考视频内容提取
            douyin_text = self.state.get('douyin_text', '')
            if douyin_text:
                logger.info("🎬 [Agno] 检测到抖音参考视频，正在提取内容...")
                try:
                    from src.utils.douyin_utils import extract_douyin_reference

                    douyin_reference = extract_douyin_reference(
                        douyin_text,
                        enable_transcript=True,
                        enable_video_analysis=True,
                        save_video=False  # agno 版本暂不保存视频
                    )
                    if douyin_reference:
                        # 将抖音视频内容追加到用户要求中
                        original_requirements = self.state['user_requirements']
                        enhanced_requirements = original_requirements + "\n\n【参考视频内容】\n" + douyin_reference
                        self.state['user_requirements'] = enhanced_requirements
                        self.state['douyin_reference'] = douyin_reference
                        logger.info("✅ [Agno] 已将抖音视频内容追加到用户要求中")
                        logger.info(f"📝 提取的内容长度: {len(douyin_reference)} 字符")
                    else:
                        logger.warning("⚠️ [Agno] 抖音视频内容提取失败，将使用原始用户要求")
                except Exception as e:
                    logger.warning(f"⚠️ [Agno] 抖音视频内容提取出错: {str(e)}，将使用原始用户要求")

            # 步骤1: 执行 Agent 规划任务
            logger.info("🔬 [Agno] 步骤1: 执行 Agent 规划任务")
            crew_result = self.crew.kickoff(self.state)

            if not crew_result.get('success'):
                error_msg = crew_result.get('error', '未知错误')
                logger.error(f"❌ Agent 规划任务失败: {error_msg}")
                return crew_result

            # 更新状态
            self._apply_capsule_overrides(crew_result)
            self.state.update({
                'workspace_dir': crew_result['workspace_dir'],
                'output_dirs': crew_result['output_paths'],
                'storyboard': crew_result['storyboard'],
                'storyboard_path': crew_result['storyboard_path'],
                'video_title': crew_result['video_title'],
                'planning_results': crew_result['planning_results'],
            })

            # storyboard_only 模式：只返回分镜数据，不执行生成
            if kwargs.get('storyboard_only'):
                logger.info("📋 [Agno] storyboard_only 模式，跳过生成阶段")
                return {
                    'success': True,
                    'storyboard': crew_result['storyboard'],
                    'storyboard_path': crew_result['storyboard_path'],
                    'workspace_dir': crew_result['workspace_dir'],
                    'video_title': crew_result['video_title'],
                    'planning_results': crew_result['planning_results'],
                    'video_type': 'general_video',
                    'storyboard_only': True,
                }

            # 提取规划结果
            planning_results = crew_result['planning_results']
            content_requirements = planning_results['plan_result']
            voice_selection = planning_results['voice_result']
            music_selection = planning_results['music_result']
            sound_effects_selection = planning_results['sound_effects_result']
            engine_selection = planning_results['engine_result']
            reference_design = planning_results['reference_result']
            art_style_selection = planning_results['art_style_result']

            self.state.update({
                'content_requirements': content_requirements,
                'voice_selection': voice_selection,
                'music_selection': music_selection,
                'sound_effects_selection': sound_effects_selection,
                'engine_selection': engine_selection,
                'reference_design': reference_design,
                'art_style_selection': art_style_selection,
            })

            # 检查用户是否手动指定了视频引擎（覆盖AI选择）
            self._check_manual_engine_override()

            # 步骤2: 直接使用工具批量生成
            logger.info("🎨 [Agno] 步骤2: 使用工具批量生成")
            result = self._execute_generation_phase()

            # 计算总耗时
            total_time = time.time() - start_time
            minutes = int(total_time // 60)
            seconds = int(total_time % 60)
            total_time_formatted = f"{minutes}分{seconds}秒"

            # 更新结果中的时间信息
            result['total_time_seconds'] = total_time
            result['total_time_formatted'] = total_time_formatted
            result['generation_summary']['total_time'] = total_time_formatted

            # 保存抖音参考内容到工作目录
            douyin_reference = self.state.get('douyin_reference')
            if douyin_reference and self.state.get('workspace_dir'):
                try:
                    douyin_ref_path = Path(self.state['workspace_dir']) / 'douyin_reference.txt'
                    with open(douyin_ref_path, 'w', encoding='utf-8') as f:
                        f.write(douyin_reference)
                    logger.info(f"📝 已保存抖音参考内容: {douyin_ref_path}")
                    result['douyin_reference_path'] = str(douyin_ref_path)
                except Exception as e:
                    logger.warning(f"⚠️ 保存抖音参考内容失败: {e}")

            logger.info(f"🎉 [Agno] 通用视频生成流程完成，总耗时: {total_time_formatted}")
            return result

        except Exception as e:
            error_msg = f"Agno 通用视频生成失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                **self.state,
                'error': error_msg,
                'success': False,
                'video_type': 'general_video'
            }

    def _check_manual_engine_override(self) -> None:
        """若用户在入参中显式指定 video_engine，则覆盖 AI 自动选择的引擎。"""
        manual_engine = normalize_video_engine_name(self.state.get('manual_video_engine'))
        if not manual_engine:
            return

        engine_selection = self.state.get('engine_selection') or {}
        ai_engine = engine_selection.get('video_engine')
        video_mode = engine_selection.get('compatibility_check', {}).get(
            'video_generation_mode', MODE.PURE_IMAGE_TO_VIDEO
        )

        if not validate_video_engine(manual_engine, video_mode):
            logger.warning(
                f"⚠️ 用户指定的视频引擎 '{manual_engine}' 不在受支持的引擎列表中，"
                f"继续保留 AI 选择的 '{ai_engine}'"
            )
            return

        if ai_engine == manual_engine:
            logger.info(f"🔧 用户指定的视频引擎与 AI 选择一致：{manual_engine}")
        else:
            logger.info(f"🔧 用户手动指定视频引擎：{manual_engine}（覆盖 AI 选择 '{ai_engine}'）")
            engine_selection['video_engine'] = manual_engine
            engine_selection['user_specified'] = True
            engine_selection['override_reason'] = (
                f"用户通过 video_engine 参数显式指定为 {manual_engine}"
            )
            self.state['engine_selection'] = engine_selection

    def _apply_capsule_overrides(self, crew_result: Dict[str, Any]) -> None:
        """Apply hard capsule defaults after LLM planning.

        The planning model may return safe defaults when a subtask response is
        empty. Capsule config is a local contract, so it must win over those
        defaults before storyboard_only results or generation state are used.
        """
        config = self.state.get('capsule_config') or {}
        if not config:
            return

        planning = crew_result.get('planning_results') or {}
        plan_result = planning.get('plan_result') or {}
        video_elements = plan_result.setdefault('video_elements', {})
        has_narration = config.get('has_narration')
        add_subtitles = config.get('add_subtitles')
        add_background_music = config.get('add_background_music')

        if has_narration is not None:
            video_elements['needs_audio'] = bool(has_narration)
        if add_subtitles is not None:
            video_elements['needs_subtitles'] = bool(add_subtitles)
        if add_background_music is not None:
            video_elements['needs_bgm'] = bool(add_background_music)

        tts_voice = config.get('tts_voice') or 'science_female'
        tts_speed = config.get('tts_speed') or CONFIG.DEFAULT_VOICE_SPEED
        tts_provider = config.get('tts_provider')
        if has_narration is False:
            planning['voice_result'] = {
                'voice_mode': 'none',
                'main_voice': {},
                'character_voices': [],
                'selection_reason': 'capsule_override: no narration',
            }
        elif has_narration is True:
            planning['voice_result'] = {
                'voice_mode': 'single',
                'main_voice': {
                    'voice_type': tts_voice,
                    'voice_name': tts_voice,
                    'speed': tts_speed,
                    'usage': 'capsule_override',
                    'provider': tts_provider,
                    'tts_provider': tts_provider,
                },
                'character_voices': [],
                'selection_reason': 'capsule_override',
            }

        bgm_volume = config.get('bgm_volume')
        if add_background_music is False:
            planning['music_result'] = {
                'needs_bgm': False,
                'music_filename': '',
                'music_volume': 0,
                'reason': 'capsule_override: no background music',
            }
        elif add_background_music is True:
            music_result = planning.get('music_result')
            if not isinstance(music_result, dict):
                music_result = {}
            music_result.update({
                'needs_bgm': True,
                'music_filename': '',
                'music_volume': bgm_volume if bgm_volume is not None else CONFIG.DEFAULT_MUSIC_VOLUME,
            })
            music_result.setdefault('reason', 'capsule_override: use capsule BGM strategy or supplied local BGM')
            planning['music_result'] = music_result

        manual_engine = self.state.get('manual_video_engine')
        if manual_engine:
            engine_result = planning.setdefault('engine_result', {})
            engine_result['video_engine'] = manual_engine
            engine_result['user_specified'] = True
            engine_result['override_reason'] = f'capsule/runtime specified video_engine={manual_engine}'

        storyboard = crew_result.get('storyboard') or []
        for scene in storyboard:
            if not isinstance(scene, dict):
                continue
            if has_narration is False:
                scene['narration'] = ''
                scene['voice_character_tag'] = ''
            elif has_narration is True:
                scene['speed_ratio'] = tts_speed
                scene.setdefault('voice_character_tag', '旁白')
            if add_subtitles is False:
                scene['subtitles'] = []

        crew_result['planning_results'] = planning

    def _execute_generation_phase(self) -> Dict[str, Any]:
        """
        执行生成阶段的所有任务

        Returns:
            生成结果
        """
        storyboard = self.state['storyboard']
        reference_design = self.state.get('reference_design', {})
        content_requirements = self.state.get('content_requirements', {})
        video_elements = content_requirements.get('video_elements', {})

        needs_audio = video_elements.get('needs_audio', True)
        needs_subtitles = video_elements.get('needs_subtitles', True)
        needs_bgm = video_elements.get('needs_bgm', True)

        total_steps = 9
        with tqdm(total=total_steps, desc="视频生成进度", unit="步骤") as pbar:

            # 2.1 批量生成音频
            if needs_audio:
                logger.info("🎙️ 步骤2.1: 生成音频...")
                audio_result = self.audio_generator.generate_audios(
                    storyboard=storyboard,
                    voice_selection=self.state.get('voice_selection', {}),
                    audios_dir=self.state['output_dirs']['audios'],
                    max_retries=CONFIG.MAX_RETRIES
                )
                self.state['audio_generation_result'] = audio_result
                logger.info(f"✅ 音频生成完成")
            else:
                logger.info("⏭️  步骤2.1: 跳过音频生成")
                self.state['audio_generation_result'] = []
            pbar.update(1)

            # 2.2 生成参考图片
            logger.info("📸 步骤2.2: 生成参考图片...")
            # 获取 visual_style 配置，用于在角色prompt中添加风格关键词
            art_style_selection = self.state.get('art_style_selection', {})
            visual_style = art_style_selection.get('visual_style', {})
            if visual_style:
                logger.info(f"  🎨 使用 visual_style 配置: {list(visual_style.keys())}")

            references_result = self.image_generator.generate_reference_images(
                reference_design=reference_design,
                output_dir=self.state['output_dirs']['reference_images'],
                aspect_ratio=self.state.get('aspect_ratio', CONFIG.DEFAULT_ASPECT_RATIO),
                user_reference_images=self.state.get('user_reference_images', []),
                reference_analysis_results=self.state.get('reference_analysis_results', []),
                visual_style=visual_style
            )
            self.state['references_result'] = references_result
            logger.info(f"✅ 参考图片生成完成")
            pbar.update(1)

            # 2.2.5 保留为占位步骤，避免进度含义变化
            logger.info("⏭️  步骤2.2.5: 跳过可选扩展能力")
            pbar.update(1)

            # 2.3 批量生成场景图片
            logger.info("📸 步骤2.3: 生成场景图片...")
            image_result = self.image_generator.generate_scene_images(
                storyboard=storyboard,
                references_result=references_result,
                output_dir=self.state['output_dirs']['images'],
                aspect_ratio=self.state.get('aspect_ratio', CONFIG.DEFAULT_ASPECT_RATIO),
                enable_quality_check=self.state.get('enable_image_quality_check', CONFIG.ENABLE_IMAGE_QUALITY_CHECK)
            )
            self.state['image_generation_result'] = image_result
            logger.info(f"✅ 场景图片生成完成")
            pbar.update(1)

            # 2.4 批量生成视频
            logger.info("🎥 步骤2.4: 生成视频...")

            audio_result = self.state.get('audio_generation_result', {})
            audio_outputs = audio_result.get('outputs', []) if isinstance(audio_result, dict) else []

            video_result = self.video_generator.generate_videos(
                storyboard=storyboard,
                image_result=image_result,
                output_dir=self.state['output_dirs']['videos'],
                engine=self.state['engine_selection'].get('video_engine', CONFIG.DEFAULT_VIDEO_ENGINE),
                enable_quality_check=self.state.get('enable_video_quality_check', CONFIG.ENABLE_VIDEO_QUALITY_CHECK),
                aspect_ratio=self.state.get('aspect_ratio', CONFIG.DEFAULT_ASPECT_RATIO)
            )
            self.state['video_generation_result'] = video_result
            logger.info(f"✅ 视频生成完成")
            pbar.update(1)

            # 2.5 添加字幕
            should_add_subtitles = self.state.get('add_subtitles', True) and needs_subtitles

            if should_add_subtitles:
                logger.info("💬 步骤2.5: 添加字幕...")
                subtitled_result = self.post_processor.add_subtitles(
                    video_result=video_result,
                    storyboard=storyboard,
                    user_requirements=self.state.get('user_requirements', ''),
                    output_dir=self.state['output_dirs']['videos']
                )
                self.state['subtitled_video_result'] = subtitled_result
                video_to_concat = subtitled_result
                logger.info(f"✅ 字幕添加完成")
            else:
                logger.info("⏭️  跳过字幕添加")
                video_to_concat = video_result
            pbar.update(1)

            # 2.6 生成视频封面
            logger.info("🖼️ 步骤2.6: 生成视频封面...")
            cover_path = Path(self.state['output_dirs']['final']) / 'cover.jpg'
            cover_image = self.image_generator.generate_cover_image(
                image_result=image_result,
                title_text=self.state.get('video_title', '精彩视频'),
                output_path=str(cover_path),
                aspect_ratio=self.state.get('aspect_ratio', CONFIG.DEFAULT_ASPECT_RATIO)
            )
            self.state['cover_image'] = cover_image
            logger.info(f"✅ 封面生成完成")
            pbar.update(1)

            # 2.7 拼接视频
            logger.info("🔗 步骤2.7: 拼接视频...")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_title = self.state.get('video_title', '通用视频').replace(' ', '_')
            final_video_path = Path(self.state['output_dirs']['final']) / f"{video_title}_{timestamp}.mp4"

            # 从分镜中提取音效配置（音效已在 crew.py 的 build_storyboard 中验证并添加到分镜）
            sound_effects_dict = {}
            for i, scene in enumerate(storyboard):
                if 'sound_effect' in scene and scene['sound_effect']:
                    sound_effects_dict[i] = scene['sound_effect']
                    logger.info(f"   🔊 分镜 {i} 配置音效: {scene['sound_effect']}")

            if sound_effects_dict:
                logger.info(f"🔊 将应用 {len(sound_effects_dict)} 个音效到视频")
            else:
                logger.info(f"🔊 跳过音效（未配置或验证失败）")

            final_video = self.post_processor.concatenate_videos(
                video_result=video_to_concat,
                audio_result=self.state.get('audio_generation_result', []),
                storyboard=storyboard,
                cover_image=cover_image,
                output_path=str(final_video_path),
                temp_dir=Path(self.state['output_dirs']['temp']),
                voice_volume=self.state.get('voice_volume', 1.5),
                sound_effects=sound_effects_dict if sound_effects_dict else None,
                image_result=self.state.get('image_generation_result', {})
            )
            self.state['final_video'] = final_video
            logger.info(f"✅ 视频拼接完成")
            pbar.update(1)

            # 2.8 添加背景音乐
            video_before_bgm = final_video
            final_video = self.post_processor.add_background_music(
                video_path=final_video,
                music_selection=self.state.get('music_selection', {}),
                needs_bgm=needs_bgm,
                user_config_enabled=self.state.get('add_background_music', True),
                manual_music_path=self.state.get('background_music_path'),
                bgm_volume=self.state.get('bgm_volume'),
                generated_music_dir=str(Path(self.state['output_dirs']['work']) / 'music')
            )
            self.state['final_video'] = final_video
            self.state['bgm_added_result'] = bool(final_video and final_video != video_before_bgm)
            logger.info(f"✅ 背景音乐添加完成")
            pbar.update(1)

            # 2.9 生成社交媒体文案
            if self.state.get('generate_social_media_copywriting', True):
                logger.info("🤖 步骤2.9: 生成社交媒体文案...")
                copywriting_result = self.post_processor.generate_social_media_copywriting(
                    video_path=final_video,
                    user_requirements=self.state.get('user_requirements', ''),
                    platform=self.state.get('platform', CONFIG.DEFAULT_PLATFORM),
                    workspace_dir=self.state['workspace_dir']
                )
                self.state['social_media_copywriting'] = copywriting_result
                logger.info(f"✅ 文案生成完成")

        self.state['artifact_manifest_path'] = self._write_artifact_manifest()
        return self._build_final_result()

    def _write_artifact_manifest(self) -> str:
        """Write a local artifact manifest for QA and delivery tooling."""
        workspace_dir = self.state.get('workspace_dir')
        if not workspace_dir:
            return ''

        manifest_path = Path(workspace_dir) / 'artifact_manifest.json'
        artifacts = []

        def add_artifact(category: str, path_value: str, **extra: Any) -> None:
            if not path_value:
                return
            path = Path(path_value)
            if not path.exists():
                return
            artifacts.append({
                'category': category,
                'path': str(path),
                'size_bytes': path.stat().st_size,
                **extra,
            })

        add_artifact('final_video', self.state.get('final_video'), bgm_added=bool(self.state.get('bgm_added_result')))
        add_artifact('cover_image', self.state.get('cover_image'))
        add_artifact('storyboard', self.state.get('storyboard_path'))

        copywriting = self.state.get('social_media_copywriting') or {}
        if isinstance(copywriting, dict):
            add_artifact('copywriting', copywriting.get('saved_path'), platform=copywriting.get('platform'))

        manifest = {
            'schema_version': 1,
            'created_at': datetime.now().isoformat(),
            'workflow': 'general_video',
            'workspace_dir': str(workspace_dir),
            'video_title': self.state.get('video_title'),
            'generation_summary': {
                'total_scenes': len(self.state.get('storyboard', [])),
                'video_engine': self.state.get('engine_selection', {}).get('video_engine', CONFIG.DEFAULT_VIDEO_ENGINE),
                'audio_generated': bool(self.state.get('audio_generation_result')),
                'subtitles_added': bool(self.state.get('subtitled_video_result')),
                'bgm_added': bool(self.state.get('bgm_added_result')),
            },
            'artifacts': artifacts,
        }

        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        logger.info(f"📦 artifact manifest 已保存: {manifest_path}")
        return str(manifest_path)

    def _build_final_result(self) -> Dict[str, Any]:
        """构建最终结果"""
        return {
            'success': True,
            'video_type': 'general_video',
            'workspace_dir': self.state.get('workspace_dir'),
            'output_paths': self.state.get('output_dirs'),
            'final_video': self.state.get('final_video'),
            'cover_image': self.state.get('cover_image'),
            'storyboard': self.state.get('storyboard', []),
            'storyboard_path': self.state.get('storyboard_path'),
            'artifact_manifest_path': self.state.get('artifact_manifest_path'),
            'video_title': self.state.get('video_title'),
            'social_media_copywriting': self.state.get('social_media_copywriting'),
            'total_time_seconds': self.state.get('total_time_seconds'),
            'total_time_formatted': self.state.get('total_time_formatted'),
            'generation_summary': {
                'total_scenes': len(self.state.get('storyboard', [])),
                'video_engine': self.state.get('engine_selection', {}).get('video_engine', CONFIG.DEFAULT_VIDEO_ENGINE),
                'audio_generated': bool(self.state.get('audio_generation_result')),
                'subtitles_added': self.state.get('add_subtitles', True),
                'bgm_added': bool(self.state.get('bgm_added_result')),
                'total_time': self.state.get('total_time_formatted'),
            }
        }


# ============================================================
# 便捷函数
# ============================================================

def run_general_video_flow(user_requirements: str, target_duration: int = 30, **kwargs) -> Dict[str, Any]:
    """
    运行通用视频生成流程的便捷函数

    Args:
        user_requirements: 用户要求
        target_duration: 目标视频时长（秒），最长180秒
        **kwargs: 其他可选参数
            - aspect_ratio: 视频宽高比，默认 '9:16'
            - platform: 目标平台，默认 '抖音'
            - add_subtitles: 是否添加字幕，默认 True
            - add_background_music: 是否添加背景音乐，默认 True
            - generate_social_media_copywriting: 是否生成社交媒体文案，默认 True
            - background_music_path: 自定义背景音乐路径
            - bgm_volume: 可选背景音乐音量；不传则使用 AI 音乐选择结果
            - voice_volume: 配音音量，默认 1.5
            - video_engine: 手动指定视频生成引擎
            - enable_image_quality_check: 是否启用图片质量检查，默认 True
            - enable_video_quality_check: 是否启用视频质量检查，默认 True
            - audio_concurrency: 音频生成并发数，默认 3
            - user_reference_images: 用户提供的参考图片路径列表
            - douyin_text: 抖音参考视频文本

    Returns:
        生成结果字典
    """
    # 限制最大时长
    if target_duration > CONFIG.MAX_DURATION:
        logger.warning(f"目标时长{target_duration}秒超过最大限制{CONFIG.MAX_DURATION}秒，已调整为{CONFIG.MAX_DURATION}秒")
        target_duration = CONFIG.MAX_DURATION

    logger.info("🚀 使用 Agno 框架: Agent 任务 + 工具直接生成")

    flow = AgnoGeneralVideoFlow()
    result = flow.run(user_requirements, target_duration, **kwargs)

    return result


# Backward-compatible framework-specific alias.
run_agno_general_video_flow = run_general_video_flow
