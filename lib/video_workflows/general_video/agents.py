#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agno 通用视频生成 Agent 定义模块
使用 Agno 框架定义所有视频生成相关的 Agent
"""

import os
from typing import List, Optional, Any, Dict
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入 CrewAI 工具（需要包装后使用）
from custom_tools.image_generation import GenerateSceneImageTool
from custom_tools.video_generation import UniversalVideoGenerationTool
from custom_tools.audio_generation import UniversalTTSBatchTool
from custom_tools.video_processing import ConcatenateVideosTool, AddBackgroundMusicTool
from custom_tools.utilities import SocialMediaCopywritingTool
from custom_tools.utilities import ReadConfigYamlTool, ListSoundEffectsTool
from custom_tools.utilities import ArtStyleManagerTool

from src.logger import get_logger

logger = get_logger('general_video_agents')


# ============================================================
# CrewAI 工具适配器
# Agno 需要 callable 函数，但 CrewAI BaseTool 不是 callable
# 这里创建包装函数来适配
# ============================================================

def _wrap_crewai_tool(tool_instance):
    """
    将 CrewAI BaseTool 包装成 Agno 可用的 callable 函数

    Args:
        tool_instance: CrewAI BaseTool 实例

    Returns:
        包装后的函数
    """
    def wrapper(**kwargs):
        return tool_instance._run(**kwargs)

    # 复制工具的元信息
    wrapper.__name__ = tool_instance.name.replace(" ", "_").lower()
    wrapper.__doc__ = tool_instance.description
    return wrapper


# 创建工具实例的包装函数
_read_config_yaml_tool = ReadConfigYamlTool()
_list_sound_effects_tool = ListSoundEffectsTool()
_art_style_manager_tool = ArtStyleManagerTool()


def read_config_yaml(config_type: str = 'music', **_: Any) -> str:
    """
    读取音乐、音色或视频引擎配置文件。
    指定 'music' 读取背景音乐选项，'voice' 读取 TTS 音色选项，'video_engines' 读取视频引擎规格。
    使用此工具了解可用选项后再进行选择。

    Args:
        config_type: 配置类型，可选值为 music、voice、video_engines

    Returns:
        配置数据字典
    """
    return _read_config_yaml_tool._run(config_type=config_type)


def list_sound_effects(**_: Any) -> str:
    """
    列出音效库中所有可用的音效文件及其适用场景。
    音效文件存放在 video_resources/sounds/ 目录中。
    使用此工具可以获取最新的音效列表，然后根据分镜内容选择合适的音效。
    【重要】只能从返回列表中选择音效文件名，禁止编造不存在的文件名！

    Returns:
        包含音效列表的字典，包括 sound_effects（音效详情列表）和 files_list_readable（易读格式）
    """
    return _list_sound_effects_tool._run()


def art_style_manager(action: str = 'list',
                      style_code: str = None,
                      style_config: str = None,
                      temporary: bool = True,
                      **_: Any) -> str:
    """
    管理艺术风格配置。支持三种操作：
    - 'list': 列出所有可用的艺术风格
    - 'get': 获取指定风格的完整配置（需要 style_code 参数）
    - 'create': 创建新的艺术风格（需要 style_code 和 style_config 参数）

    Args:
        action: 操作类型，可选值为 list、get、create
        style_code: 风格代码（get/create 操作需要）
        style_config: 风格配置JSON字符串（create 操作需要）
        temporary: 是否写入临时目录，默认True

    Returns:
        操作结果字典
    """
    # 兼容 AI agent 传入 dict 格式，如 {'type': 'get'}
    if isinstance(action, dict):
        action = action.get('type', action.get('action', 'list'))
    kwargs = {'action': action}
    if style_code:
        kwargs['style_code'] = style_code
    if style_config:
        # 兼容传入字符串或dict
        if isinstance(style_config, str):
            import json
            try:
                style_config = json.loads(style_config)
            except (json.JSONDecodeError, TypeError):
                pass
        kwargs['style_config'] = style_config
    if action == 'create':
        kwargs['temporary'] = temporary
    return _art_style_manager_tool._run(**kwargs)


def get_default_model() -> OpenAIChat:
    """
    获取默认的 LLM 模型
    从环境变量读取配置，与 crewai 版本使用相同的模型

    The public runtime expects an OpenAI-compatible planning interface. Any
    provider-specific compatibility adapter belongs in the local overlay.
    """
    model_name = os.getenv('CREW_MODEL_NAME', 'gpt-4o')
    api_key = os.getenv('CREW_API_KEY')
    base_url = os.getenv('CREW_BASE_URL')

    logger.info(f"🤖 使用模型: {model_name}")

    return OpenAIChat(
        id=model_name,
        api_key=api_key,
        base_url=base_url
    )


def create_story_writer(model: Optional[OpenAIChat] = None) -> Agent:
    """
    故事剧本作家 - 负责创作完整的故事剧本
    """
    return Agent(
        name="故事剧本作家",
        role="故事剧本作家",
        model=model or get_default_model(),
        description="经验丰富的故事剧本作家和内容策划师",
        instructions=[
            "根据用户要求创作完整、连贯、引人入胜的故事剧本",
            "精准把握故事的主题和情感基调，构建清晰的故事结构",
            "输出格式为JSON数据，用文字描述完整的故事内容",
            "包括开头、发展、高潮、结尾等各个部分",
            "为后续的分镜剧本创作提供坚实的基础"
        ],
        markdown=True
    )


def create_script_writer(model: Optional[OpenAIChat] = None) -> Agent:
    """
    剧本编剧 - 负责创建视频剧本
    """
    return Agent(
        name="通用剧本编剧",
        role="剧本编剧",
        model=model or get_default_model(),
        description="经验丰富的视频剧本编剧，擅长根据各种主题创作引人入胜的视频剧本文字稿",
        instructions=[
            "准确把握视频节奏，合理分配时长",
            "创造流畅自然的叙事结构",
            "输出格式为JSON数据，用文字描述剧本内容",
            "包括旁白、场景描述等文本信息"
        ],
        markdown=True
    )


def create_content_requirements_analyzer(model: Optional[OpenAIChat] = None) -> Agent:
    """
    内容需求分析专家 - 负责判断是否需要音频、字幕、背景音乐
    """
    return Agent(
        name="视频内容需求分析专家",
        role="内容需求分析师",
        model=model or get_default_model(),
        description="专业的视频内容需求分析专家和媒体制作顾问",
        instructions=[
            "深入分析用户需求，准确判断视频的必要元素",
            "判断是否需要音频配音（TTS）",
            "判断是否需要字幕",
            "判断是否需要背景音乐",
            "决策优先级：用户明确要求 > 内容类型特点 > 默认推荐"
        ],
        markdown=True
    )


def create_reference_designer(model: Optional[OpenAIChat] = None) -> Agent:
    """
    视觉参考设计师 - 负责设计参考元素
    """
    return Agent(
        name="视觉参考设计师",
        role="视觉参考设计师",
        model=model or get_default_model(),
        description="专业的视觉参考设计师和风格定义专家",
        instructions=[
            "根据视频主题撰写合适的视觉参考元素的文字描述",
            "设计人物角色、画面风格和核心物体的视觉参考",
            "输出格式为JSON数据，用文字详细描述视觉元素的特征和风格"
        ],
        markdown=True
    )


def create_scene_designer(model: Optional[OpenAIChat] = None) -> Agent:
    """
    场景设计师 - 负责设计视觉场景
    """
    return Agent(
        name="场景设计师",
        role="场景设计师",
        model=model or get_default_model(),
        description="专业的场景设计师和视觉艺术家",
        instructions=[
            "将剧本中的文字描述转化为更具体的视觉场景文字说明",
            "撰写既美观又符合主题的场景构图文案",
            "生成的图片是每个分镜的第一帧（起始画面）",
            "像按下相机快门，捕捉单一时刻的静态画面",
            "输出格式为JSON prompt文案，用文字详细描述每个场景的视觉内容"
        ],
        markdown=True
    )


def create_video_director(model: Optional[OpenAIChat] = None) -> Agent:
    """
    视频导演 - 负责创建视频描述和运镜方案
    """
    return Agent(
        name="视频导演",
        role="视频导演",
        model=model or get_default_model(),
        description="专业的视频导演和运镜专家",
        instructions=[
            "深谙视频语言，擅长用文字描述富有表现力的镜头运动和场景调度",
            "撰写专业的运镜技巧说明文案",
            "为视频生成提供指导",
            "输出格式为JSON prompt文案，用文字描述镜头应该如何运动、场景如何变化"
        ],
        markdown=True
    )


def create_voice_selector(model: Optional[OpenAIChat] = None) -> Agent:
    """
    TTS音色选择专家 - 负责选择最适合的音色
    """
    return Agent(
        name="TTS音色选择专家",
        role="音色选择专家",
        model=model or get_default_model(),
        description="专业的TTS音色选择专家和声音设计师",
        instructions=[
            "深入了解豆包TTS音色库中各音色的特点",
            "根据内容场景（知识解说、情感故事、搞笑娱乐、美食吃播等）推荐音色",
            "考虑音色的性别、年龄感、情感表现力等因素",
            "确保音色与视频整体风格协调一致",
            "使用read_config_yaml工具（参数config_type='voice'）访问完整的豆包音色配置"
        ],
        tools=[read_config_yaml],  # 使用包装后的函数
        markdown=True
    )


def create_music_selector(model: Optional[OpenAIChat] = None) -> Agent:
    """
    背景音乐选择专家 - 负责选择最适合的背景音乐和音效
    """
    return Agent(
        name="背景音乐与音效选择专家",
        role="音乐选择专家",
        model=model or get_default_model(),
        description="专业的背景音乐与音效选择专家，同时也是音乐情感分析师",
        instructions=[
            "【最高优先级】必须使用 read_config_yaml 工具读取在线音乐风格配置，然后从中选择一个 style_id",
            "深谙不同音乐风格与视频内容的搭配艺术",
            "根据视频主题、情感基调、节奏特点等因素精准选择在线授权音乐搜索或生成背景音乐的风格和描述",
            "使用 read_config_yaml 工具（参数 config_type='music'）访问完整的在线音乐风格配置",
            "【强制要求】输出 music_source='online'、music_style_id 和 music_query，不要输出本地音乐文件名",
            "使用 list_sound_effects 工具获取音效库中所有实际存在的音效文件列表",
            "音效选择时必须先调用工具获取列表，只能从返回列表中选择",
            "严禁编造音效文件名"
        ],
        tools=[read_config_yaml, list_sound_effects],  # 使用包装后的函数
        markdown=True
    )


def create_video_engine_selector(model: Optional[OpenAIChat] = None) -> Agent:
    """
    视频引擎选择专家 - 负责选择最适合的视频生成引擎
    """
    return Agent(
        name="视频生成引擎选择专家",
        role="引擎选择专家",
        model=model or get_default_model(),
        description="专业的视频生成引擎选择专家和AI视频技术顾问",
        instructions=[
            "深入了解不同视频生成引擎的技术特点和适用场景",
            "根据视频内容的特性精准推荐最适合的生成工具",
            "理解video_generation_mode与引擎的兼容性要求",
            "使用 read_config_yaml 工具（参数 config_type='video_engines'）获取各引擎的详细技术参数",
            "决策优先级：用户明确指定的引擎 > video_generation_mode兼容性 > 场景匹配 > 默认推荐"
        ],
        tools=[read_config_yaml],  # 使用包装后的函数
        markdown=True
    )


def create_art_style_selector(model: Optional[OpenAIChat] = None) -> Agent:
    """
    艺术风格选择专家 - 负责选择或创建合适的艺术风格
    """
    return Agent(
        name="艺术风格选择专家",
        role="艺术风格顾问",
        model=model or get_default_model(),
        description="专业的艺术风格顾问和视觉设计专家",
        instructions=[
            "【最高优先级】检查用户需求中是否指定了特定风格",
            "如果用户要求'真实'、'写实'、'realistic'，必须选择或创建写实风格",
            "使用 art_style_manager 工具列出所有可用风格",
            "如果找到合适的现有风格，使用 get 操作获取完整配置",
            "如果没有合适的现有风格，使用 art_style_manager 的 create 操作手动创建",
            "创建新风格时，visual_style必须包含：颜色、排版、构图、特效四个部分",
            "严格遵循用户的风格需求，不要擅自更换风格类型"
        ],
        tools=[art_style_manager, read_config_yaml],  # 使用包装后的函数
        markdown=True
    )


def create_image_generator(model: Optional[OpenAIChat] = None) -> Agent:
    """
    AI图像生成专家 - 使用AI工具生成高质量的参考图和场景图片
    """
    return Agent(
        name="AI图像生成专家",
        role="图像生成专家",
        model=model or get_default_model(),
        description="专业的AI图像生成专家和视觉艺术家",
        instructions=[
            "熟练使用各种图像生成工具",
            "掌握文生图和图生图技术",
            "优化prompt以获得最佳效果",
            "确保图像风格的一致性",
            "生成适合视频制作的高质量图像"
        ],
        tools=[GenerateSceneImageTool()],
        markdown=True
    )


def create_audio_generator(model: Optional[OpenAIChat] = None) -> Agent:
    """
    TTS音频生成专家 - 为视频剧本生成专业清晰的TTS语音音频
    """
    return Agent(
        name="TTS音频生成专家",
        role="音频生成专家",
        model=model or get_default_model(),
        description="专业的TTS音频生成专家和声音设计师",
        instructions=[
            "熟练使用各种TTS工具和平台",
            "选择适合内容的音色和语速",
            "处理专业术语的准确发音",
            "确保音频质量和清晰度",
            "批量生成高质量音频文件"
        ],
        tools=[UniversalTTSBatchTool()],
        markdown=True
    )


def create_video_generator(model: Optional[OpenAIChat] = None) -> Agent:
    """
    AI视频生成专家 - 将静态图像转化为动态视频内容
    """
    return Agent(
        name="AI视频生成专家",
        role="视频生成专家",
        model=model or get_default_model(),
        description="专业的AI视频生成专家和影像制作师",
        instructions=[
            "熟练使用各种视频生成工具",
            "掌握图生视频的最佳实践",
            "设计适合的视频动作和运镜",
            "确保视频质量和流畅性",
            "优化视频生成参数和效果"
        ],
        tools=[UniversalVideoGenerationTool()],
        markdown=True
    )


def create_video_processor(model: Optional[OpenAIChat] = None) -> Agent:
    """
    视频后期处理专家 - 进行完整的视频后期制作和最终合成
    """
    return Agent(
        name="视频后期处理专家",
        role="后期处理专家",
        model=model or get_default_model(),
        description="专业的视频后期处理专家和视频合成师",
        instructions=[
            "精通专业视频制作工具",
            "熟练处理音视频同步和内容对齐",
            "专业的字幕和特效制作",
            "优化最终视频的质量和观感"
        ],
        tools=[ConcatenateVideosTool(), AddBackgroundMusicTool()],
        markdown=True
    )


def create_copywriter(model: Optional[OpenAIChat] = None) -> Agent:
    """
    自媒体文案专家 - 为生成的视频创作吸引人的自媒体发布文案
    """
    return Agent(
        name="自媒体文案专家",
        role="文案专家",
        model=model or get_default_model(),
        description="专业的自媒体文案专家和内容营销师",
        instructions=[
            "深谙各大社交媒体平台的内容传播规律",
            "创作既符合平台特点又能吸引目标受众的优质文案",
            "精准把握不同平台的文案风格",
            "创作吸引人的标题和开头",
            "合理使用话题标签和关键词",
            "激发用户互动和传播"
        ],
        tools=[SocialMediaCopywritingTool()],
        markdown=True
    )


class AgnoVideoAgents:
    """
    Agno 视频生成 Agent 管理器
    统一管理所有视频生成相关的 Agent
    """

    def __init__(self, model: Optional[OpenAIChat] = None):
        """
        初始化 Agent 管理器

        Args:
            model: 可选的 LLM 模型，如果不提供则使用默认模型
        """
        self.model = model or get_default_model()
        self._agents = {}
        logger.info("AgnoVideoAgents 初始化完成")

    def get_story_writer(self) -> Agent:
        """获取故事剧本作家 Agent"""
        if 'story_writer' not in self._agents:
            self._agents['story_writer'] = create_story_writer(self.model)
        return self._agents['story_writer']

    def get_script_writer(self) -> Agent:
        """获取剧本编剧 Agent"""
        if 'script_writer' not in self._agents:
            self._agents['script_writer'] = create_script_writer(self.model)
        return self._agents['script_writer']

    def get_content_requirements_analyzer(self) -> Agent:
        """获取内容需求分析专家 Agent"""
        if 'content_requirements_analyzer' not in self._agents:
            self._agents['content_requirements_analyzer'] = create_content_requirements_analyzer(self.model)
        return self._agents['content_requirements_analyzer']

    def get_reference_designer(self) -> Agent:
        """获取视觉参考设计师 Agent"""
        if 'reference_designer' not in self._agents:
            self._agents['reference_designer'] = create_reference_designer(self.model)
        return self._agents['reference_designer']

    def get_scene_designer(self) -> Agent:
        """获取场景设计师 Agent"""
        if 'scene_designer' not in self._agents:
            self._agents['scene_designer'] = create_scene_designer(self.model)
        return self._agents['scene_designer']

    def get_video_director(self) -> Agent:
        """获取视频导演 Agent"""
        if 'video_director' not in self._agents:
            self._agents['video_director'] = create_video_director(self.model)
        return self._agents['video_director']

    def get_voice_selector(self) -> Agent:
        """获取音色选择专家 Agent"""
        if 'voice_selector' not in self._agents:
            self._agents['voice_selector'] = create_voice_selector(self.model)
        return self._agents['voice_selector']

    def get_music_selector(self) -> Agent:
        """获取音乐选择专家 Agent"""
        if 'music_selector' not in self._agents:
            self._agents['music_selector'] = create_music_selector(self.model)
        return self._agents['music_selector']

    def get_video_engine_selector(self) -> Agent:
        """获取视频引擎选择专家 Agent"""
        if 'video_engine_selector' not in self._agents:
            self._agents['video_engine_selector'] = create_video_engine_selector(self.model)
        return self._agents['video_engine_selector']

    def get_art_style_selector(self) -> Agent:
        """获取艺术风格选择专家 Agent"""
        if 'art_style_selector' not in self._agents:
            self._agents['art_style_selector'] = create_art_style_selector(self.model)
        return self._agents['art_style_selector']

    def get_image_generator(self) -> Agent:
        """获取图像生成专家 Agent"""
        if 'image_generator' not in self._agents:
            self._agents['image_generator'] = create_image_generator(self.model)
        return self._agents['image_generator']

    def get_audio_generator(self) -> Agent:
        """获取音频生成专家 Agent"""
        if 'audio_generator' not in self._agents:
            self._agents['audio_generator'] = create_audio_generator(self.model)
        return self._agents['audio_generator']

    def get_video_generator(self) -> Agent:
        """获取视频生成专家 Agent"""
        if 'video_generator' not in self._agents:
            self._agents['video_generator'] = create_video_generator(self.model)
        return self._agents['video_generator']

    def get_video_processor(self) -> Agent:
        """获取视频后期处理专家 Agent"""
        if 'video_processor' not in self._agents:
            self._agents['video_processor'] = create_video_processor(self.model)
        return self._agents['video_processor']

    def get_copywriter(self) -> Agent:
        """获取自媒体文案专家 Agent"""
        if 'copywriter' not in self._agents:
            self._agents['copywriter'] = create_copywriter(self.model)
        return self._agents['copywriter']

    def get_all_agents(self) -> dict:
        """获取所有 Agent 的字典"""
        return {
            'story_writer': self.get_story_writer(),
            'script_writer': self.get_script_writer(),
            'content_requirements_analyzer': self.get_content_requirements_analyzer(),
            'reference_designer': self.get_reference_designer(),
            'scene_designer': self.get_scene_designer(),
            'video_director': self.get_video_director(),
            'voice_selector': self.get_voice_selector(),
            'music_selector': self.get_music_selector(),
            'video_engine_selector': self.get_video_engine_selector(),
            'art_style_selector': self.get_art_style_selector(),
            'image_generator': self.get_image_generator(),
            'audio_generator': self.get_audio_generator(),
            'video_generator': self.get_video_generator(),
            'video_processor': self.get_video_processor(),
            'copywriter': self.get_copywriter(),
        }
