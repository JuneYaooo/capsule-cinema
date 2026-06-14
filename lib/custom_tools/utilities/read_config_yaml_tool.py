from typing import Any, Type, Literal
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
import yaml
import os
from src.logger import get_logger

# 初始化日志记录器
logger = get_logger("read_config_yaml")

class ReadConfigYamlToolSchema(BaseModel):
    """Input for ReadConfigYamlTool."""
    config_type: Literal['music', 'voice', 'video_engines'] = Field(
        description="配置类型：'music' 读取在线音乐风格配置，'voice' 读取音色库配置，'video_engines' 读取视频引擎配置"
    )

class ReadConfigYamlTool(BaseTool):
    name: str = "Read music, voice or video engine configuration from yaml file"
    description: str = (
        "A tool that reads configuration files for online music styles, voice library, or video engines. "
        "Specify 'music' to read online background music style options from music_scenes.yaml, "
        "'voice' to read TTS voice options from doubao_voices.yaml, "
        "or 'video_engines' to read video generation engine specifications from video_engines.yaml. "
        "Use this tool to understand what options are available before making a selection."
    )
    args_schema: Type[BaseModel] = ReadConfigYamlToolSchema

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info("初始化ReadConfigYamlTool")

    def _run(self, config_type: str = 'music') -> Any:
        """读取音乐、音色或视频引擎配置YAML文件

        Args:
            config_type: 配置类型，'music'、'voice' 或 'video_engines'
        """
        try:
            # 修复路径：从 custom_tools/utilities 向上3级到项目根目录，再进入 config
            # __file__ -> custom_tools/utilities/read_config_yaml_tool.py
            # dirname -> custom_tools/utilities
            # dirname -> custom_tools
            # dirname -> video-agent/lib
            config_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'config'
            )

            if config_type == 'music':
                return self._read_music_config(config_dir)
            elif config_type == 'voice':
                return self._read_voice_config(config_dir)
            elif config_type == 'video_engines':
                return self._read_video_engines_config(config_dir)
            else:
                logger.error(f"不支持的配置类型: {config_type}")
                return {
                    "error": f"不支持的配置类型: {config_type}，请使用 'music'、'voice' 或 'video_engines'",
                    "success": False
                }

        except Exception as e:
            logger.error(f"读取配置文件失败: {str(e)}")
            return {
                "error": f"读取失败: {str(e)}",
                "success": False
            }
    
    def _read_music_config(self, config_dir: str) -> dict:
        """读取在线音乐风格配置"""
        music_yaml_path = os.path.join(config_dir, 'music_scenes.yaml')
        
        logger.info(f"读取音乐配置文件: {music_yaml_path}")
        
        if not os.path.exists(music_yaml_path):
            logger.error(f"音乐配置文件不存在: {music_yaml_path}")
            return {
                "error": "音乐配置文件不存在",
                "path": music_yaml_path,
                "success": False
            }
        
        # 读取YAML文件
        with open(music_yaml_path, 'r', encoding='utf-8') as f:
            music_config = yaml.safe_load(f)
        
        if not music_config:
            logger.error("音乐配置文件格式错误")
            return {
                "error": "音乐配置文件格式错误",
                "success": False
            }

        online_music_styles = music_config.get('online_music_styles')
        if not online_music_styles:
            logger.error("音乐配置文件缺少 online_music_styles")
            return {
                "error": "音乐配置文件缺少 online_music_styles",
                "success": False
            }

        # 格式化输出，便于AI理解
        formatted_music_list = []
        for style_id, info in online_music_styles.items():
            formatted_music_list.append({
                "style_id": style_id,
                "tag": info.get('标签', ''),
                "scene_description": info.get('场景描述', ''),
                "generation_prompt": info.get('生成提示', ''),
            })

        result = {
            "success": True,
            "config_type": "music",
            "mode": "online_generation",
            "total_count": len(formatted_music_list),
            "online_music_styles": formatted_music_list,
            "config_path": music_yaml_path
        }

        logger.info(f"成功读取 {len(formatted_music_list)} 个在线音乐风格配置")
        return result
    
    def _read_voice_config(self, config_dir: str) -> dict:
        """读取音色库配置"""
        voice_yaml_path = os.path.join(config_dir, 'doubao_voices.yaml')
        
        logger.info(f"读取音色配置文件: {voice_yaml_path}")
        
        if not os.path.exists(voice_yaml_path):
            logger.error(f"音色配置文件不存在: {voice_yaml_path}")
            return {
                "error": "音色配置文件不存在",
                "path": voice_yaml_path,
                "success": False
            }
        
        # 读取YAML文件
        with open(voice_yaml_path, 'r', encoding='utf-8') as f:
            voice_config = yaml.safe_load(f)
        
        if not voice_config or 'voices' not in voice_config:
            logger.error("音色配置文件格式错误")
            return {
                "error": "音色配置文件格式错误",
                "success": False
            }
        
        # 格式化输出，便于AI理解
        formatted_voice_list = []
        voice_categories = voice_config.get('voices', {})
        
        for category, voices in voice_categories.items():
            for voice in voices:
                formatted_voice_list.append({
                    "category": category,
                    "name": voice.get('name', ''),
                    "voice_type": voice.get('voice_type', ''),
                    "gender": voice.get('gender', ''),
                    "language": voice.get('language', ''),
                    "description": voice.get('description', ''),
                    "recommended_for": voice.get('recommended_for', []),
                    "support_mix": voice.get('support_mix', False),
                    "emotions": voice.get('emotions', [])
                })
        
        # 获取推荐音色配置
        recommended_voices = voice_config.get('recommended_voices', {})
        
        result = {
            "success": True,
            "config_type": "voice",
            "total_count": len(formatted_voice_list),
            "voice_library": formatted_voice_list,
            "recommended_voices": recommended_voices,
            "config_path": voice_yaml_path
        }
        
        logger.info(f"成功读取 {len(formatted_voice_list)} 个音色配置")
        return result

    def _read_video_engines_config(self, config_dir: str) -> dict:
        """读取视频引擎配置"""
        video_engines_yaml_path = os.path.join(config_dir, 'video_engines.yaml')

        logger.info(f"读取视频引擎配置文件: {video_engines_yaml_path}")

        if not os.path.exists(video_engines_yaml_path):
            logger.error(f"视频引擎配置文件不存在: {video_engines_yaml_path}")
            return {
                "error": "视频引擎配置文件不存在",
                "path": video_engines_yaml_path,
                "success": False
            }

        # 读取YAML文件
        with open(video_engines_yaml_path, 'r', encoding='utf-8') as f:
            engines_config = yaml.safe_load(f)

        if not engines_config or 'engines' not in engines_config:
            logger.error("视频引擎配置文件格式错误")
            return {
                "error": "视频引擎配置文件格式错误",
                "success": False
            }

        # 格式化输出，便于AI理解
        formatted_engines_list = []
        engines = engines_config.get('engines', {})

        for engine_id, engine_info in engines.items():
            capabilities = engine_info.get('capabilities', {})
            features = engine_info.get('features', {})

            formatted_engines_list.append({
                "engine_id": engine_id,
                "name": engine_info.get('name', engine_id),
                "provider": engine_info.get('provider', ''),
                "duration_options": capabilities.get('duration_options', []),
                "default_duration": capabilities.get('default_duration', 5),
                "aspect_ratios": capabilities.get('aspect_ratios', []),
                "supports_text_to_video": features.get('text_to_video', False),
                "supports_image_to_video": features.get('image_to_video', False),
                "supports_transition_frames": features.get('transition_frames', False),
                "best_for": engine_info.get('best_for', []),
                "strengths": engine_info.get('strengths', []),
                "weaknesses": engine_info.get('weaknesses', []),
                "cost_tier": engine_info.get('cost_tier', 'medium')
            })

        # 获取选择规则和兼容性信息（如果存在）
        selection_rules = engines_config.get('selection_rules', {})
        compatibility = engines_config.get('compatibility', {})

        result = {
            "success": True,
            "config_type": "video_engines",
            "total_count": len(formatted_engines_list),
            "engines": formatted_engines_list,
            "selection_rules": selection_rules,
            "compatibility": compatibility,
            "config_path": video_engines_yaml_path
        }

        logger.info(f"成功读取 {len(formatted_engines_list)} 个视频引擎配置")
        return result
