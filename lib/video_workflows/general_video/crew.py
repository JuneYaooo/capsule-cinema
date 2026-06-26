#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agno 通用视频生成 Crew 编排模块
使用 Agno Team 协调多个 Agent 完成视频生成任务
"""

import os
import json
import math
import re
import copy
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from agno.agent import Agent
from agno.team import Team
from agno.models.openai import OpenAIChat

from .agents import AgnoVideoAgents, get_default_model
from .tasks import AgnoVideoTasks
from .config import CONFIG, MODE

from src.logger import get_logger, clear_project_log_dir
from src.contracts import normalize_storyboard_document
from src.utils.output_paths import get_output_base_dir

logger = get_logger('general_video_workflow')


def _list_text(value: Any) -> str:
    if isinstance(value, list):
        return "、".join(str(item) for item in value if item)
    if isinstance(value, str):
        return value
    return ""


def should_apply_realistic_fallback(user_requirements: str) -> bool:
    """Return whether missing style data should fall back to realistic style."""
    text = (user_requirements or "").lower()
    if not text:
        return False

    negated_patterns = [
        r"(不要|不能|禁止|拒绝|避免|不是|不要.*?)(真实|写实|真人|古装剧)",
        r"(not|no|avoid|reject|without)\s+(real|realistic|photorealistic|live[- ]?action)",
    ]
    if any(re.search(pattern, text) for pattern in negated_patterns):
        return False

    realistic_keywords = ['真实', '写实', '真实世界', 'realistic', 'photorealistic', 'real']
    return any(keyword in text for keyword in realistic_keywords)


def capsule_visual_style_from_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Build runtime visual_style from a capsule's local style contract."""
    if not isinstance(config, dict):
        return {}

    configured_style = config.get("visual_style")
    if isinstance(configured_style, dict) and configured_style:
        return configured_style

    contract = config.get("style_contract") if isinstance(config.get("style_contract"), dict) else {}
    required = contract.get("required") or []
    forbidden = contract.get("forbidden") or []
    style_markers = " ".join(
        str(config.get(key) or "")
        for key in ("visual_style", "default_style", "quality_profile", "motion_style")
    ).lower()
    contract_text = _list_text(required) + _list_text(forbidden)

    is_strong_shuimo = (
        "shuimo" in style_markers
        or "ink" in style_markers
        or "水墨" in contract_text
        or "宣纸" in contract_text
    )
    if not is_strong_shuimo:
        return {}

    required_text = _list_text(required) or "宣纸留白、湿墨晕染、断笔边缘、黑灰分层墨色、克制矿物色点缀"
    forbidden_text = _list_text(forbidden)
    forbidden_clause = f"绝无{forbidden_text}。" if forbidden_text else "绝无真人风、真实古装剧、过度真实电影光或光泽3D质感。"

    return {
        "颜色": {
            "主色调": ["黑色", "深灰色", "浅灰色", "象牙白宣纸底色"],
            "辅助色": ["暗红色", "暖金色", "克制矿物色"],
            "氛围特征": f"强水墨国漫，黑灰分层墨色为主，{required_text}，拒绝高饱和霓虹和写实摄影色彩。",
        },
        "排版": {
            "元素布局": f"大面积宣纸留白，疏密有致，焦点明确；必须体现{required_text}。",
            "层次关系": "纸剧场层次：近景焦墨剪影，中景主体人物，远景淡墨晕染。",
        },
        "构图": {
            "类型": "强水墨国漫纸剧场构图",
            "特征": "传统水墨留白结合现代分层纸剧场，强调视差、卷轴展开和墨痕成景。",
            "视角": "按叙事变化年龄、服装、表情、姿态和机位，避免同角度肖像复用。",
        },
        "特效": {
            "元素": ["宣纸留白", "湿墨晕染", "断笔边缘", "枯笔纹理", "墨痕转场", "克制矿物色点缀"],
            "质感": f"纯粹2D强水墨国漫质感，{forbidden_clause}",
        },
    }


def felt_asmr_visual_style_result() -> Dict[str, Any]:
    """Return the capsule-scoped wool-felt ASMR visual style."""
    return {
        "style_code": "felt_asmr_wool_felt_macro",
        "style_name": "Wool-Felt Macro ASMR",
        "visual_style": {
            "颜色": {
                "主色调": ["低饱和粉彩色", "奶油白", "浅抹茶绿或主题强调色"],
                "辅助色": ["浅木色", "柔和暖光", "银色工具高光"],
                "氛围特征": "治愈系微距手作厨房氛围，避免真实食物油光、湿润奶油和高饱和商业甜品色。",
            },
            "排版": {
                "元素布局": "主体占画面65%-85%，背景干净虚化，工具和手只服务于接触动作。",
                "层次关系": "前景工具接触点清晰，中景羊毛毡主体纤维清晰，背景柔和浅景深。",
            },
            "构图": {
                "类型": "极近微距 ASMR 构图",
                "特征": "每个镜头有明确触觉事件：压下、切开、回弹、露出棉花内馅或纤维拉扯。",
                "视角": "ECU/CU 为主，围绕工具与羊毛毡主体的真实接触关系取景。",
            },
            "特效": {
                "元素": ["可见羊毛纤维", "针毡缝合痕迹", "蓬松棉花内馅", "软体压痕回弹", "低音量 ASMR 氛围"],
                "质感": "干燥蓬松的羊毛纤维和棉花填料质感，拒绝真实奶油、液体流动、玻璃穿透、工具悬空和手/容器/主体互穿。",
            },
        },
        "reason": "capsule_scoped_felt_asmr_style",
    }


def capsule_art_style_result_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve deterministic capsule-owned art style, if the capsule defines one."""
    config = state.get('capsule_config') or {}
    configured_style = capsule_visual_style_from_config(config)
    if configured_style:
        return {
            "style_code": "capsule_visual_style",
            "style_name": "Capsule Visual Style",
            "visual_style": configured_style,
            "reason": "capsule_visual_style_from_config",
        }

    if state.get('capsule_name') == 'felt_asmr':
        return felt_asmr_visual_style_result()

    return {}


def ensure_storyboard_has_scenes(storyboard: List[Dict[str, Any]], planning_results: Dict[str, Any]) -> None:
    """Fail the run when planning produced no usable scenes."""
    if storyboard:
        return
    raw_output = ""
    storyboard_result = planning_results.get("storyboard_result") if isinstance(planning_results, dict) else {}
    if isinstance(storyboard_result, dict):
        raw_output = str(storyboard_result.get("raw_output") or "")
    detail = f"；规划响应: {raw_output[:160]}" if raw_output else ""
    raise ValueError(f"分镜为空，无法继续生成视频{detail}")


def ensure_required_planning_result(
    result: Dict[str, Any],
    task_name: str,
    *,
    allow_empty: bool = False,
) -> None:
    """Fail fast when a required planning Agent did not return valid structured data."""
    if not isinstance(result, dict):
        raise ValueError(f"规划任务 {task_name} 未返回有效结构化结果")
    raw_output = str(result.get('raw_output') or '').strip()
    if raw_output:
        raise ValueError(f"规划任务 {task_name} 未返回有效JSON；原始响应: {raw_output[:160]}")
    if not allow_empty and not result:
        raise ValueError(f"规划任务 {task_name} 返回空结果")


def _valid_scene_count_range(config: Dict[str, Any]) -> tuple[int, int] | None:
    raw_range = config.get("generated_scene_count_range") if isinstance(config, dict) else None
    if not isinstance(raw_range, list) or len(raw_range) != 2:
        return None
    try:
        minimum = int(raw_range[0])
        maximum = int(raw_range[1])
    except (TypeError, ValueError):
        return None
    if minimum <= 0 or maximum < minimum:
        return None
    return minimum, maximum


def _scene_groups(total: int, target: int) -> List[tuple[int, int]]:
    groups: List[tuple[int, int]] = []
    for index in range(target):
        start = round(index * total / target)
        end = round((index + 1) * total / target)
        if end > start:
            groups.append((start, end))
    return groups


def _merge_text(group: List[Dict[str, Any]], key: str, *, label: str = "") -> str:
    parts = []
    for scene in group:
        text = str(scene.get(key) or "").strip()
        if not text:
            continue
        if label:
            parts.append(f"{label}{scene.get('scene_id', len(parts))}: {text}")
        else:
            parts.append(text)
    return "\n".join(parts)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _merge_storyboard_group(group: List[Dict[str, Any]], new_index: int) -> Dict[str, Any]:
    merged = copy.deepcopy(group[0])
    merged["scene_id"] = new_index
    merged["description"] = _merge_text(group, "description", label="微镜头")
    merged["duration"] = round(sum(_to_float(scene.get("duration"), CONFIG.DEFAULT_SCENE_DURATION) for scene in group), 3)
    merged["merged_from_scene_ids"] = [scene.get("scene_id", idx) for idx, scene in enumerate(group)]

    character_ids: List[Any] = []
    for scene in group:
        for character_id in scene.get("character_ids", []) or []:
            if character_id not in character_ids:
                character_ids.append(character_id)
    if character_ids:
        merged["character_ids"] = character_ids

    for key in (
        "image_prompt_chinese",
        "image_prompt_english",
        "video_prompt_chinese",
        "video_prompt_english",
        "continuity_notes",
    ):
        text = _merge_text(group, key)
        if text:
            merged[key] = text

    return merged


def _merge_narration_group(group: List[Dict[str, Any]]) -> Dict[str, Any]:
    merged = copy.deepcopy(group[0]) if group else {}
    narration = " ".join(str(item.get("narration") or "").strip() for item in group if str(item.get("narration") or "").strip())
    if narration:
        merged["narration"] = narration
    return merged


def _merge_subtitle_group(group: List[Dict[str, Any]]) -> Dict[str, Any]:
    merged = copy.deepcopy(group[0]) if group else {"subtitles": []}
    subtitles: List[Any] = []
    for item in group:
        value = item.get("subtitles", [])
        if isinstance(value, list):
            subtitles.extend(value)
        elif value:
            subtitles.append(value)
    merged["subtitles"] = subtitles
    return merged


def _merge_optional_sequence(items: Any, groups: List[tuple[int, int]], merge_fn) -> Any:
    if not isinstance(items, list) or len(items) <= 1:
        return items
    merged = []
    for start, end in groups:
        group = items[start:min(end, len(items))]
        if group:
            merged.append(merge_fn(group))
    return merged


def enforce_capsule_storyboard_scene_range(
    planning_results: Dict[str, Any],
    capsule_config: Dict[str, Any],
) -> None:
    """Merge LLM micro-shot storyboards into the capsule's generated-scene range."""
    scene_range = _valid_scene_count_range(capsule_config)
    if scene_range is None:
        return
    _minimum, maximum = scene_range
    storyboard_result = planning_results.get("storyboard_result") if isinstance(planning_results, dict) else None
    if not isinstance(storyboard_result, dict):
        return
    scenes = storyboard_result.get("scenes")
    if not isinstance(scenes, list) or len(scenes) <= maximum:
        return

    groups = _scene_groups(len(scenes), maximum)
    merged_scenes = [
        _merge_storyboard_group(scenes[start:end], new_index)
        for new_index, (start, end) in enumerate(groups)
        if scenes[start:end]
    ]
    storyboard_result["scenes"] = merged_scenes
    storyboard_result["capsule_scene_count_normalized"] = {
        "original_count": len(scenes),
        "target_count": len(merged_scenes),
    }
    logger.info(
        "🔧 胶囊生成场景数硬约束: %s -> %s",
        len(scenes),
        len(merged_scenes),
    )

    narration_result = planning_results.get("narration_result")
    if isinstance(narration_result, dict):
        narration_result["narrations"] = _merge_optional_sequence(
            narration_result.get("narrations"),
            groups,
            _merge_narration_group,
        )

    subtitles_result = planning_results.get("subtitles_result")
    if isinstance(subtitles_result, dict):
        subtitles_result["scene_subtitles"] = _merge_optional_sequence(
            subtitles_result.get("scene_subtitles"),
            groups,
            _merge_subtitle_group,
        )


class AgnoGeneralVideoCrew:
    """
    Agno 通用视频生成 Crew
    使用 Agno 框架协调多个 Agent 完成视频生成任务
    """

    def __init__(self, model: Optional[OpenAIChat] = None):
        """
        初始化 Agno 通用视频生成 Crew

        Args:
            model: 可选的 LLM 模型，如果不提供则使用环境变量配置的默认模型
        """
        self.model = model or get_default_model()
        self.agents_manager = AgnoVideoAgents(self.model)
        self.tasks_manager = AgnoVideoTasks(self.agents_manager)

        self.workspace_dir = None
        self.output_paths = {
            'images': None,
            'audios': None,
            'videos': None,
            'final': None,
            'temp': None,
            'reference_images': None
        }

        logger.info("AgnoGeneralVideoCrew 初始化完成")

    def setup_workspace(self, video_name: str, base_dir: Optional[str] = None) -> Dict[str, str]:
        """
        设置视频工作空间目录

        Args:
            video_name: 视频名称
            base_dir: 基础目录

        Returns:
            各类文件的输出路径字典
        """
        from src.logger import set_project_log_dir

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        workspace_base = Path(base_dir).expanduser() if base_dir else get_output_base_dir()
        self.workspace_dir = workspace_base / f"general_video_{timestamp}"

        # 创建 run 目录结构：release/work/qa/logs，中间产物在 work/ 下
        work_dir = self.workspace_dir / 'work'
        dir_paths = {
            'release': self.workspace_dir / 'release',
            'qa': self.workspace_dir / 'qa',
            'logs': self.workspace_dir / 'logs',
            'work': work_dir,
            'images': work_dir / 'images',
            'audios': work_dir / 'audios',
            'videos': work_dir / 'videos',
            'temp': work_dir / 'temp',
            'reference_images': work_dir / 'reference_images',
        }
        for dir_name, dir_path in dir_paths.items():
            dir_path.mkdir(parents=True, exist_ok=True)
            self.output_paths[dir_name] = str(dir_path)
        self.output_paths['final'] = self.output_paths['release']

        # 启用项目级日志：所有模块的日志都会同时写入项目的 logs 目录
        set_project_log_dir(self.output_paths['logs'])
        logger.info(f"📝 项目日志已启用: {self.output_paths['logs']}/project.log")

        logger.info(f"✅ Agno 通用视频工作空间设置完成: {self.workspace_dir}")
        return self.output_paths

    def run_planning_phase(self, user_requirements: str, target_duration: int, state: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        执行规划阶段的所有任务

        Args:
            user_requirements: 用户要求
            target_duration: 目标时长（秒）

        Returns:
            规划阶段的所有结果
        """
        logger.info("🎬 开始规划阶段...")

        # 1. 规划视频制作元素
        logger.info("📋 步骤1: 规划视频制作元素...")
        plan_result = self.tasks_manager.plan_video_production(user_requirements, target_duration)
        ensure_required_planning_result(plan_result, 'plan_video_production')
        video_generation_mode = plan_result.get('video_generation_mode', MODE.PURE_IMAGE_TO_VIDEO)
        state = state or {}
        video_elements = plan_result.get('video_elements', {})
        self._apply_state_video_element_overrides(video_elements, state)

        needs_audio = video_elements.get('needs_audio', True)
        needs_subtitles = video_elements.get('needs_subtitles', True)
        needs_bgm = video_elements.get('needs_bgm', True)

        logger.info(f"   视频生成模式: {video_generation_mode}")
        logger.info(f"   需要音频: {needs_audio}, 需要字幕: {needs_subtitles}, 需要BGM: {needs_bgm}")

        # 2. 创作故事剧本
        logger.info("📖 步骤2: 创作故事剧本...")
        story_result = self.tasks_manager.create_story(user_requirements, target_duration, plan_result)
        ensure_required_planning_result(story_result, 'create_story')

        # 3. 生成分镜剧本
        logger.info("🎬 步骤3: 生成分镜剧本...")
        storyboard_result = self.tasks_manager.create_storyboard(
            user_requirements, target_duration, story_result, video_generation_mode
        )
        ensure_required_planning_result(storyboard_result, 'create_storyboard')
        storyboard_scenes = storyboard_result.get('scenes', []) if isinstance(storyboard_result, dict) else []
        if not isinstance(storyboard_scenes, list):
            storyboard_scenes = []
        ensure_storyboard_has_scenes(
            storyboard_scenes,
            {
                'storyboard_result': storyboard_result
                if isinstance(storyboard_result, dict)
                else {'raw_output': str(storyboard_result)},
            },
        )

        # 4. 选择音色
        logger.info("🎙️ 步骤4: 选择音色...")
        voice_result = self.tasks_manager.select_voice(user_requirements, storyboard_result, needs_audio)
        if needs_audio:
            ensure_required_planning_result(voice_result, 'select_voice')

        # 5. 生成配音文本
        logger.info("💬 步骤5: 生成配音文本...")
        narration_result = self.tasks_manager.generate_narration(user_requirements, storyboard_result, needs_audio)
        if needs_audio:
            ensure_required_planning_result(narration_result, 'generate_narration')

        # 6. 生成字幕文本
        logger.info("📝 步骤6: 生成字幕文本...")
        subtitles_result = self.tasks_manager.generate_subtitles(
            user_requirements, storyboard_result, narration_result, needs_subtitles
        )
        if needs_subtitles:
            ensure_required_planning_result(subtitles_result, 'generate_subtitles')

        # 7. 选择背景音乐
        logger.info("🎵 步骤7: 选择背景音乐...")
        music_result = self.tasks_manager.select_music(
            user_requirements,
            storyboard_result,
            needs_bgm=needs_bgm,
            music_defaults=state.get('capsule_config') or {},
        )
        if needs_bgm:
            ensure_required_planning_result(music_result, 'select_music')
        # 记录背景音乐选择结果
        music_source = music_result.get('music_source', 'online')
        music_filename = music_result.get('music_filename', '')
        music_style_id = music_result.get('music_style_id', '')
        if music_source == 'online':
            logger.info(f"   背景音乐: 在线生成 style={music_style_id or 'auto'} (音量: {music_result.get('music_volume', 0.4)})")
        elif music_filename:
            logger.info(f"   背景音乐: {music_filename} (音量: {music_result.get('music_volume', 0.4)})")
        else:
            logger.info(f"   背景音乐: 未选择 - {music_result.get('reason', '未说明原因')}")

        # 8. 选择音效
        logger.info("🔊 步骤8: 选择音效...")
        sound_effects_result = self.tasks_manager.select_sound_effects(
            user_requirements, storyboard_result, narration_result
        )
        ensure_required_planning_result(sound_effects_result, 'select_sound_effects')
        # 记录音效选择结果
        if sound_effects_result.get('needs_sound_effects'):
            effects = sound_effects_result.get('sound_effects', {})
            logger.info(f"   音效选择: 需要音效, 共 {len(effects)} 个分镜配置了音效")
            for idx, effect in effects.items():
                logger.info(f"     分镜{idx}: {effect}")
        else:
            logger.info(f"   音效选择: 不需要音效 - {sound_effects_result.get('reason', '未说明原因')}")

        # 9. 选择视频引擎
        logger.info("🎥 步骤9: 选择视频引擎...")
        engine_result = self.tasks_manager.select_video_engine(
            user_requirements,
            storyboard_result,
            video_generation_mode,
            forced_engine=state.get('manual_video_engine') or None,
        )
        ensure_required_planning_result(engine_result, 'select_video_engine')

        # 10. 选择艺术风格
        logger.info("🎨 步骤10: 选择艺术风格...")
        art_style_result = capsule_art_style_result_from_state(state)
        if art_style_result:
            logger.info(
                "🎨 使用胶囊确定性艺术风格，跳过艺术风格 Agent: %s",
                art_style_result.get('style_code', 'capsule_visual_style'),
            )
        else:
            art_style_result = self.tasks_manager.select_art_style(
                user_requirements, story_result, storyboard_result
            )
            ensure_required_planning_result(art_style_result, 'select_art_style')
        # 记录艺术风格选择结果
        if art_style_result.get('visual_style'):
            logger.info(f"   艺术风格: {art_style_result.get('style_name', 'N/A')}")
            logger.info(f"   风格代码: {art_style_result.get('style_code', 'N/A')}")
        else:
            logger.warning(f"   ⚠️ 艺术风格返回无效: {art_style_result}")

        # 11. 设计参考元素
        logger.info("📸 步骤11: 设计参考元素...")
        reference_result = self.tasks_manager.design_reference(
            user_requirements, storyboard_result, art_style_result
        )
        ensure_required_planning_result(reference_result, 'design_reference', allow_empty=True)

        logger.info("✅ 规划阶段完成")

        return {
            'plan_result': plan_result,
            'story_result': story_result,
            'storyboard_result': storyboard_result,
            'voice_result': voice_result,
            'narration_result': narration_result,
            'subtitles_result': subtitles_result,
            'music_result': music_result,
            'sound_effects_result': sound_effects_result,
            'engine_result': engine_result,
            'art_style_result': art_style_result,
            'reference_result': reference_result,
            'video_generation_mode': video_generation_mode,
            'video_elements': video_elements
        }

    @staticmethod
    def _apply_state_video_element_overrides(video_elements: Dict[str, Any], state: Dict[str, Any]) -> None:
        """Apply CLI/capsule output contract before optional planning tasks run."""
        config = state.get('capsule_config') or {}
        output_contract = config.get('output_contract') if isinstance(config.get('output_contract'), dict) else {}

        if config.get('has_narration') is False or output_contract.get('voice') == 'none':
            video_elements['needs_audio'] = False
        elif config.get('has_narration') is True or output_contract.get('voice') == 'unified_tts':
            video_elements['needs_audio'] = True

        if state.get('add_subtitles') is not None:
            video_elements['needs_subtitles'] = bool(state.get('add_subtitles'))
        if output_contract.get('subtitle') == 'none':
            video_elements['needs_subtitles'] = False
        elif output_contract.get('subtitle') in ('overlay', 'burned'):
            video_elements['needs_subtitles'] = True

        if state.get('add_background_music') is not None:
            video_elements['needs_bgm'] = bool(state.get('add_background_music'))
        if output_contract.get('bgm') == 'none':
            video_elements['needs_bgm'] = False
        elif output_contract.get('bgm') == 'external':
            video_elements['needs_bgm'] = True

    def run_visual_design_phase(self, user_requirements: str, planning_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行视觉设计阶段的任务（分批处理分镜）

        Args:
            user_requirements: 用户要求
            planning_results: 规划阶段的结果

        Returns:
            视觉设计阶段的结果
        """
        logger.info("🎨 开始视觉设计阶段...")

        storyboard_result = planning_results['storyboard_result']
        reference_result = planning_results['reference_result']
        art_style_result = planning_results['art_style_result']

        # 调试日志：检查 art_style_result 中的 visual_style
        art_style_visual_style = art_style_result.get('visual_style', {})
        if art_style_visual_style:
            logger.info(f"🎨 艺术风格 visual_style 已获取: {list(art_style_visual_style.keys())}")
        else:
            logger.warning(f"⚠️ 艺术风格 visual_style 为空！将尝试从用户需求中检测写实风格...")
            # 备用方案：如果 visual_style 为空，检查用户需求中是否有写实关键词
            if should_apply_realistic_fallback(user_requirements):
                logger.info("🎨 检测到写实风格关键词，使用默认写实风格配置")
                art_style_visual_style = {
                    "颜色": {
                        "主色调": ["真实自然色彩"],
                        "辅助色": ["符合现实场景的色彩还原"],
                        "氛围特征": "真实自然，光影效果准确，色调和谐统一"
                    },
                    "排版": {
                        "元素布局": "符合现实物理规律，透视准确",
                        "层次关系": "立体感突出，景深自然"
                    },
                    "构图": {
                        "类型": "照片级写实构图",
                        "特征": "比例协调，细节丰富，透视准确",
                        "视角": "符合现实视角"
                    },
                    "特效": {
                        "元素": ["真实光影效果", "清晰材质纹理", "准确的明暗对比"],
                        "质感": "照片级真实感，材质纹理清晰逼真"
                    }
                }
                # 更新 art_style_result 以便后续使用
                art_style_result['visual_style'] = art_style_visual_style
            else:
                logger.info("🎨 未触发写实 fallback，继续使用提示词中的风格描述")

        storyboard_scenes = storyboard_result.get('scenes', [])
        total_scenes = len(storyboard_scenes)
        batch_size = 10  # 每批处理10个分镜

        logger.info(f"📋 共有 {total_scenes} 个分镜，将分 {(total_scenes + batch_size - 1) // batch_size} 批处理")

        all_visual_scenes = []
        all_video_directions = []

        # 提取角色信息
        characters = reference_result.get('characters', [])
        character_ids = [char.get('character_id') for char in characters if 'character_id' in char]
        characters_detail = []
        for char in characters:
            characters_detail.append({
                'character_id': char.get('character_id'),
                'character_name': char.get('character_name', '未命名'),
                'character_description': char.get('character_description', ''),
                'identity_anchor': char.get('identity_anchor', ''),
                'fixed_traits': char.get('fixed_traits', []),
                'allowed_variations': char.get('allowed_variations', []),
                'image_prompt_chinese': char.get('image_prompt_chinese', ''),
                'image_prompt_english': char.get('image_prompt_english', '')
            })

        character_info = json.dumps({
            'character_count': len(characters),
            'character_ids': character_ids,
            'characters': characters_detail
        }, ensure_ascii=False)

        for batch_start in range(0, total_scenes, batch_size):
            batch_end = min(batch_start + batch_size, total_scenes)
            batch_scenes = storyboard_scenes[batch_start:batch_end]
            batch_num = (batch_start // batch_size) + 1
            total_batches = (total_scenes + batch_size - 1) // batch_size

            logger.info(f"\n{'=' * 60}")
            logger.info(f"📸 处理第 {batch_num}/{total_batches} 批分镜 (分镜{batch_start}至{batch_end - 1})")
            logger.info(f"{'=' * 60}\n")

            # 设计视觉场景
            logger.info(f"🎨 设计第{batch_start}-{batch_end - 1}个分镜的视觉场景...")
            visual_result = self.tasks_manager.design_visual_scenes(
                user_requirements=user_requirements,
                character_info=character_info,
                batch_start_index=batch_start,
                batch_end_index=batch_end,
                batch_size=len(batch_scenes),
                total_scenes=total_scenes,
                batch_scenes=json.dumps(batch_scenes, ensure_ascii=False),
                previous_scenes_summary=self._get_scenes_summary(all_visual_scenes)
            )

            batch_visual_scenes = visual_result.get('visual_scenes', [])

            # 添加艺术风格配置（胶囊风格是硬约束，必须覆盖 LLM 的普通默认值）
            if art_style_visual_style:
                for scene in batch_visual_scenes:
                    if art_style_result.get('capsule_override') or 'visual_style' not in scene or not scene['visual_style']:
                        scene['visual_style'] = art_style_visual_style
                        logger.debug(f"   场景 {scene.get('scene_id', '?')} 已应用 visual_style")

            all_visual_scenes.extend(batch_visual_scenes)
            logger.info(f"✅ 本批次生成了 {len(batch_visual_scenes)} 个视觉场景")

            # 创建视频指导
            logger.info(f"🎬 生成第{batch_start}-{batch_end - 1}个分镜的视频指导...")
            directions_result = self.tasks_manager.create_video_directions(
                user_requirements=user_requirements,
                batch_start_index=batch_start,
                batch_end_index=batch_end,
                batch_size=len(batch_scenes),
                total_scenes=total_scenes,
                batch_scenes=json.dumps(batch_scenes, ensure_ascii=False),
                batch_visual_scenes=json.dumps(batch_visual_scenes, ensure_ascii=False),
                previous_directions_summary=self._get_directions_summary(all_video_directions)
            )

            batch_video_directions = directions_result.get('video_directions', [])
            all_video_directions.extend(batch_video_directions)
            logger.info(f"✅ 本批次生成了 {len(batch_video_directions)} 个视频指导")

        logger.info(f"\n🎉 视觉设计阶段完成! 共生成 {len(all_visual_scenes)} 个视觉场景和 {len(all_video_directions)} 个视频指导\n")

        return {
            'visual_scenes': all_visual_scenes,
            'video_directions': all_video_directions
        }

    def build_storyboard(self, planning_results: Dict[str, Any],
                         visual_design_results: Dict[str, Any],
                         sound_effects_selection: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        构建最终分镜

        Args:
            planning_results: 规划阶段的结果
            visual_design_results: 视觉设计阶段的结果
            sound_effects_selection: 音效选择结果（可选）

        Returns:
            完整的分镜列表
        """
        logger.info("🔨 构建最终分镜...")

        storyboard_result = planning_results['storyboard_result']
        narration_result = planning_results['narration_result']
        subtitles_result = planning_results['subtitles_result']

        visual_scenes = visual_design_results['visual_scenes']
        video_directions = visual_design_results['video_directions']

        scenes = storyboard_result.get('scenes', [])
        narrations = narration_result.get('narrations', [])
        scene_subtitles = subtitles_result.get('scene_subtitles', [])

        storyboard = []

        for i, scene in enumerate(scenes):
            # 基础分镜信息
            storyboard_item = {
                'scene_id': i,
                'description': scene.get('description', ''),
                'duration': scene.get('duration', CONFIG.DEFAULT_SCENE_DURATION),
                'video_generation_type': scene.get('video_generation_type', 'image_to_video'),
                'chapter_id': scene.get('chapter_id', 'chapter_01'),
                'continuity_group': scene.get('continuity_group', f"scene_{i:02d}"),
                'character_ids': scene.get('character_ids', []),
                'style_anchor': scene.get('style_anchor', 'main_style'),
                'continuity_notes': scene.get('continuity_notes', ''),
            }

            # 添加配音信息
            if i < len(narrations):
                narration = narrations[i]
                storyboard_item['narration'] = narration.get('narration', '')
                storyboard_item['voice_character_tag'] = narration.get('voice_character_tag', 'main')
                storyboard_item['speed_ratio'] = narration.get('speed_ratio', 1.0)

            # 添加字幕信息
            if i < len(scene_subtitles):
                subtitle_data = scene_subtitles[i]
                storyboard_item['subtitles'] = subtitle_data.get('subtitles', [])

            # 添加视觉场景信息
            if i < len(visual_scenes):
                visual = visual_scenes[i]
                storyboard_item['needs_reference'] = visual.get('needs_reference', False)
                storyboard_item['reference_type'] = visual.get('reference_type', 'none')
                storyboard_item['reference_ids'] = visual.get('reference_ids', [])
                storyboard_item['use_style_reference'] = visual.get('use_style_reference', True)
                storyboard_item['style_anchor'] = visual.get('style_anchor', storyboard_item.get('style_anchor', 'main_style'))
                storyboard_item['continuity_group'] = visual.get('continuity_group', storyboard_item.get('continuity_group'))
                storyboard_item['continuity_notes'] = visual.get('continuity_notes', storyboard_item.get('continuity_notes', ''))
                storyboard_item['image_prompt_chinese'] = visual.get('image_prompt_chinese', '')
                storyboard_item['image_prompt_english'] = visual.get('image_prompt_english', '')
                storyboard_item['visual_style'] = visual.get('visual_style', {})

            # 添加视频指导信息
            if i < len(video_directions):
                direction = video_directions[i]
                storyboard_item['video_prompt_chinese'] = direction.get('video_prompt_chinese', '')
                storyboard_item['video_prompt_english'] = direction.get('video_prompt_english', '')

            storyboard.append(storyboard_item)

        # 自动拆分配音过长的分镜
        storyboard = self._split_long_narration_scenes(storyboard)
        # 重新编号 scene_id
        for i, scene in enumerate(storyboard):
            scene['scene_id'] = i

        # 将音效信息添加到每个分镜中（带文件存在性验证）
        if sound_effects_selection and sound_effects_selection.get('needs_sound_effects'):
            sound_effects_dict = sound_effects_selection.get('sound_effects', {})
            if sound_effects_dict:
                logger.info(f"🔊 ========== 音效验证开始 ==========")
                logger.info(f"🔊 Agent 选择了 {len(sound_effects_dict)} 个音效")
                logger.info(f"   Agent 选择列表: {list(sound_effects_dict.values())}")

                # 导入音效管理器进行验证
                from src.utils.sound_effects_utils import SoundEffectsManager

                # 获取实际存在的音效文件列表
                available_sounds = SoundEffectsManager.get_available_sound_effects()
                logger.info(f"   ✅ 音效库实际存在 {len(available_sounds)} 个文件")

                valid_count = 0
                invalid_count = 0
                invalid_files = []

                for scene_idx_str, sound_file in sound_effects_dict.items():
                    try:
                        scene_idx = int(scene_idx_str)
                        if scene_idx >= len(storyboard):
                            logger.warning(f"   ⚠️ 分镜索引 {scene_idx} 超出范围")
                            continue

                        # 验证音效文件是否真实存在
                        if sound_file in available_sounds:
                            storyboard[scene_idx]['sound_effect'] = sound_file
                            logger.info(f"   ✅ 分镜 {scene_idx}: {sound_file} - 验证通过")
                            valid_count += 1
                        else:
                            logger.error(f"   ❌ 分镜 {scene_idx}: {sound_file} - 文件不存在！")
                            invalid_files.append(sound_file)
                            invalid_count += 1

                    except (ValueError, IndexError) as e:
                        logger.warning(f"   ⚠️ 无法为分镜 {scene_idx_str} 添加音效: {e}")

                logger.info(f"🔊 ========== 音效验证结束 ==========")
                logger.info(f"   ✅ 有效: {valid_count} 个")
                logger.info(f"   ❌ 无效: {invalid_count} 个（已过滤）")

                if invalid_count > 0:
                    logger.warning(f"⚠️ Agent 选择了 {invalid_count} 个不存在的音效文件")
                    for invalid_file in invalid_files:
                        logger.warning(f"   - {invalid_file} ❌ 不存在")

        logger.info(f"✅ 分镜构建完成: {len(storyboard)} 个场景")
        return storyboard

    def save_storyboard_json(self, storyboard: List[Dict[str, Any]],
                             reference_design: Dict[str, Any],
                             delivery_promise: Dict[str, Any] | None = None) -> str:
        """
        保存分镜 JSON 文件

        Args:
            storyboard: 分镜列表
            reference_design: 参考设计

        Returns:
            保存的文件路径
        """
        if not self.workspace_dir:
            raise ValueError("工作空间未初始化，请先调用 setup_workspace")

        storyboard_data = normalize_storyboard_document({
            'reference_design': reference_design,
            'storyboard': storyboard,
            'created_at': datetime.now().isoformat()
        }).model_dump(mode='json')
        if delivery_promise:
            storyboard_data['delivery_promise'] = delivery_promise

        storyboard_path = self.workspace_dir / 'storyboard.json'
        with open(storyboard_path, 'w', encoding='utf-8') as f:
            json.dump(storyboard_data, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ 分镜已保存: {storyboard_path}")
        return str(storyboard_path)

    def kickoff(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行 Agno 通用视频生成流程

        Args:
            state: 输入状态，包含 user_requirements, target_duration 等

        Returns:
            包含生成结果的状态字典
        """
        try:
            logger.info("🎬 开始 Agno 通用视频生成流程")

            # 提取输入参数
            user_requirements = state.get('user_requirements', '')
            target_duration = state.get('target_duration', 30)
            aspect_ratio = state.get('aspect_ratio', CONFIG.DEFAULT_ASPECT_RATIO)
            platform = state.get('platform', CONFIG.DEFAULT_PLATFORM)

            if not user_requirements:
                raise ValueError("请提供视频要求 (user_requirements)")

            # 限制最大时长
            if target_duration > CONFIG.MAX_DURATION:
                logger.warning(f"⚠️ 目标时长{target_duration}秒超过最大限制{CONFIG.MAX_DURATION}秒，已调整")
                target_duration = CONFIG.MAX_DURATION

            logger.info(f"📋 用户要求: {user_requirements}")
            logger.info(f"⏱️  视频时长: {target_duration}秒")
            logger.info(f"📐 画面比例: {aspect_ratio}")
            logger.info(f"📱 目标平台: {platform}")

            # 设置工作空间
            video_name = user_requirements[:20].replace(' ', '_')
            self.setup_workspace(video_name)

            # 执行规划阶段
            planning_results = self.run_planning_phase(user_requirements, target_duration, state=state)
            capsule_config = state.get('capsule_config') or {}
            enforce_capsule_storyboard_scene_range(planning_results, capsule_config)
            capsule_visual_style = capsule_visual_style_from_config(capsule_config)
            if capsule_visual_style:
                art_style_result = planning_results.setdefault('art_style_result', {})
                art_style_result['visual_style'] = capsule_visual_style
                art_style_result['style_name'] = art_style_result.get('style_name') or 'capsule_style_contract'
                art_style_result['style_code'] = art_style_result.get('style_code') or capsule_config.get('visual_style', 'capsule_style_contract')
                art_style_result['capsule_override'] = True
                logger.info("🎨 已应用胶囊 style_contract 作为硬性 visual_style")

            # 执行视觉设计阶段
            visual_design_results = self.run_visual_design_phase(user_requirements, planning_results)

            # 构建最终分镜（传入音效选择结果）
            storyboard = self.build_storyboard(
                planning_results,
                visual_design_results,
                sound_effects_selection=planning_results.get('sound_effects_result')
            )
            ensure_storyboard_has_scenes(storyboard, planning_results)

            # 保存分镜
            storyboard_path = self.save_storyboard_json(
                storyboard,
                planning_results['reference_result'],
                state.get('delivery_promise')
            )

            # 构建结果
            result = {
                **state,
                'workspace_dir': str(self.workspace_dir),
                'output_paths': self.output_paths,
                'storyboard': storyboard,
                'storyboard_path': storyboard_path,
                'planning_results': planning_results,
                'visual_design_results': visual_design_results,
                'video_title': planning_results['story_result'].get('title', '通用视频'),
                'success': True,
                'video_type': 'general_video'
            }

            logger.info("🎉 Agno 通用视频生成流程完成")

            # 清理项目日志配置，确保后续运行不会混淆日志
            clear_project_log_dir()
            logger.info("📝 项目日志已清理")

            return result

        except Exception as e:
            error_msg = f"Agno 通用视频生成失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            import traceback
            logger.error(traceback.format_exc())

            # 即使出错也要清理项目日志配置
            clear_project_log_dir()

            return {
                **state,
                'error': error_msg,
                'workspace_dir': str(self.workspace_dir) if self.workspace_dir else None,
                'success': False,
                'video_type': 'general_video'
            }

    def _split_long_narration_scenes(self, storyboard, max_clip_duration=3.0):
        """当配音文本预估超过 max_clip_duration 时，拆分为多个子分镜"""
        new_storyboard = []
        for scene in storyboard:
            narration = scene.get('narration', '')
            if not narration:
                new_storyboard.append(scene)
                continue

            est_duration = self._estimate_narration_duration(narration, scene.get('speed_ratio', 1.0))
            if est_duration <= max_clip_duration + 0.5:
                new_storyboard.append(scene)
                continue

            # 需要拆分
            num_clips = math.ceil(est_duration / max_clip_duration)
            sub_narrations = self._split_narration_text(narration, num_clips)
            logger.info(f"   ✂️ 分镜 {scene.get('scene_id')} 配音预估 {est_duration:.1f}s，拆分为 {len(sub_narrations)} 个子分镜")

            for j, sub_text in enumerate(sub_narrations):
                sub_scene = scene.copy()
                sub_scene['scene_id'] = len(new_storyboard)
                sub_scene['narration'] = sub_text
                sub_scene['is_sub_scene'] = True
                sub_scene['sub_scene_index'] = j
                sub_scene['parent_description'] = scene.get('description', '')
                # 子分镜生成变化的视频提示词和图片提示词
                if j > 0:
                    sub_scene['video_prompt_chinese'] = self._generate_continuation_prompt(
                        scene.get('video_prompt_chinese', ''), j, len(sub_narrations)
                    )
                    sub_scene['video_prompt_english'] = self._generate_continuation_prompt(
                        scene.get('video_prompt_english', ''), j, len(sub_narrations)
                    )
                    # 为每个子分镜生成独立的 image_prompt，确保画面有变化
                    sub_scene['image_prompt_english'] = self._generate_image_variation_prompt(
                        scene.get('image_prompt_english', ''), j, len(sub_narrations)
                    )
                    sub_scene['image_prompt_chinese'] = self._generate_image_variation_prompt(
                        scene.get('image_prompt_chinese', ''), j, len(sub_narrations)
                    )
                new_storyboard.append(sub_scene)

        return new_storyboard

    def _estimate_narration_duration(self, text, speed_ratio=1.0):
        """估算配音时长，中文约 4 字/秒"""
        # 去除标点和空格，只计算实际字符
        clean = re.sub(r'[|，。！？、；：\u201c\u201d\u2018\u2019（）\s]', '', text)
        chars = len(clean)
        # 基础速率：4字/秒，speed_ratio 越大语速越快
        base_rate = 4.0
        return chars / (base_rate * speed_ratio)

    def _split_narration_text(self, text, num_clips):
        """按 "|" 标记或语义断点拆分配音文本"""
        # 优先按 "|" 拆分
        if '|' in text:
            parts = [p.strip() for p in text.split('|') if p.strip()]
            if len(parts) >= num_clips:
                # 将 parts 均匀分配到 num_clips 组
                return self._merge_parts_into_groups(parts, num_clips)
            elif len(parts) > 1:
                return parts

        # 按句号、感叹号、问号拆分
        sentences = re.split(r'(?<=[。！？])', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if len(sentences) >= num_clips:
            return self._merge_parts_into_groups(sentences, num_clips)

        # 按逗号拆分
        clauses = re.split(r'(?<=[，,])', text)
        clauses = [c.strip() for c in clauses if c.strip()]
        if len(clauses) >= num_clips:
            return self._merge_parts_into_groups(clauses, num_clips)

        # 无法拆分，返回原文
        return [text]

    def _merge_parts_into_groups(self, parts, num_groups):
        """将多个文本片段均匀合并为 num_groups 组"""
        if len(parts) <= num_groups:
            return parts
        result = []
        per_group = len(parts) / num_groups
        idx = 0.0
        for _ in range(num_groups):
            end = idx + per_group
            group_parts = parts[int(idx):int(end)]
            result.append(''.join(group_parts))
            idx = end
        # 把剩余的追加到最后一组
        if int(idx) < len(parts):
            result[-1] += ''.join(parts[int(idx):])
        return result

    def _generate_continuation_prompt(self, original_prompt, index, total):
        """为子分镜生成变化的视频提示词"""
        if not original_prompt:
            return original_prompt
        variations = [
            '（特写镜头，不同角度）',
            '（中景，反应镜头）',
            '（远景，环境展现）',
            '（侧面角度，动作延续）',
        ]
        variation_en = [
            ' (close-up shot, different angle)',
            ' (medium shot, reaction shot)',
            ' (wide shot, environment reveal)',
            ' (side angle, action continuation)',
        ]
        # 判断是中文还是英文 prompt
        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in original_prompt)
        if has_chinese:
            suffix = variations[(index - 1) % len(variations)]
        else:
            suffix = variation_en[(index - 1) % len(variation_en)]
        return original_prompt + suffix

    def _generate_image_variation_prompt(self, original_prompt, index, total):
        """为子分镜生成视觉差异化的图片提示词，确保每个子分镜画面不同"""
        if not original_prompt:
            return original_prompt

        variations_cn = [
            '，特写镜头，聚焦面部表情和细节',
            '，中景构图，展现人物动作和姿态变化',
            '，反应镜头，捕捉周围角色或环境的反应',
            '，环境全景，展现场景氛围和空间关系',
            '，低角度仰拍视角，增强气势和张力',
            '，俯瞰视角，展现全局布局',
        ]
        variations_en = [
            ', close-up shot focusing on facial expression and details',
            ', medium shot showing character action and posture change',
            ', reaction shot capturing surrounding characters or environment response',
            ', wide establishing shot showing scene atmosphere and spatial layout',
            ', low angle upward perspective enhancing power and tension',
            ', overhead perspective showing overall layout',
        ]

        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in original_prompt)
        if has_chinese:
            suffix = variations_cn[(index - 1) % len(variations_cn)]
        else:
            suffix = variations_en[(index - 1) % len(variations_en)]
        return original_prompt + suffix

    def _get_scenes_summary(self, previous_scenes: List[Dict]) -> str:
        """获取之前场景的简要总结"""
        if not previous_scenes:
            return "这是第一批分镜，请根据完整剧本和参考设计开始场景设计。"

        last_scenes = previous_scenes[-3:] if len(previous_scenes) >= 3 else previous_scenes

        summary = f"前面已生成 {len(previous_scenes)} 个场景。最后几个场景的关键信息:\n"
        for scene in last_scenes:
            scene_id = scene.get('scene_id', '?')
            ref_type = scene.get('reference_type', 'none')
            image_prompt = scene.get('image_prompt_chinese', '')[:80]
            summary += f"- 场景{scene_id} ({ref_type}参考): {image_prompt}...\n"

        summary += "\n【连贯性要求】请确保本批次场景与上述场景保持:\n"
        summary += "1. 视觉风格一致（画风、色调、氛围）\n"
        summary += "2. 人物形象一致（如有重复出现的角色）\n"
        summary += "3. 场景过渡自然流畅\n"

        return summary

    def _get_directions_summary(self, previous_directions: List[Dict]) -> str:
        """获取之前视频指导的简要总结"""
        if not previous_directions:
            return "这是第一批视频指导，请根据场景设计和整体故事节奏设计运镜方案。"

        last_directions = previous_directions[-3:] if len(previous_directions) >= 3 else previous_directions

        summary = f"前面已生成 {len(previous_directions)} 个视频指导。最后几个的运镜风格:\n"
        for direction in last_directions:
            scene_id = direction.get('scene_id', '?')
            video_prompt = direction.get('video_prompt_chinese', '')[:80]
            summary += f"- 场景{scene_id}: {video_prompt}...\n"

        summary += "\n【连贯性要求】请确保本批次运镜方案与上述保持:\n"
        summary += "1. 运镜风格一致\n"
        summary += "2. 节奏流畅自然\n"
        summary += "3. 整体视频节奏协调\n"

        return summary
