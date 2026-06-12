#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用音乐生成CrewAI工具
支持多个音乐生成供应商的统一接口
"""

from typing import Any, Type, Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from src.logger import get_logger

# 导入具体的音乐生成工具
from .suno_music_tool import SunoMusicClient

logger = get_logger("universal_music_generation_tool")


class UniversalMusicGenerationSchema(BaseModel):
    """通用音乐生成工具的输入参数"""
    description: str = Field(
        ...,
        description="音乐描述或歌词内容"
    )
    provider: str = Field(
        default="suno",
        description="音乐生成提供商，目前仅支持 suno"
    )
    mode: str = Field(
        default="inspiration",
        description="生成模式：inspiration（灵感模式）或 custom（专业模式）"
    )
    title: Optional[str] = Field(
        default=None,
        description="歌曲标题（专业模式需要）"
    )
    tags: Optional[str] = Field(
        default=None,
        description="风格标签（专业模式需要），如 'pop, rock, energetic'"
    )
    output_dir: Optional[str] = Field(
        default=None,
        description="音乐文件下载保存目录"
    )
    make_instrumental: bool = Field(
        default=False,
        description="是否生成纯音乐（无人声）"
    )
    wait_for_completion: bool = Field(
        default=True,
        description="是否等待任务完成"
    )


class UniversalLyricsGenerationSchema(BaseModel):
    """通用歌词生成工具的输入参数"""
    prompt: str = Field(
        ...,
        description="歌词生成提示词"
    )
    provider: str = Field(
        default="suno",
        description="歌词生成提供商，目前仅支持 suno"
    )
    wait_for_completion: bool = Field(
        default=True,
        description="是否等待任务完成"
    )


class UniversalMusicGenerationTool(BaseTool):
    """通用音乐生成工具"""
    name: str = "Universal Music Generation Tool"
    description: str = (
        "通用AI音乐生成工具，目前支持Suno。"
        "可以根据描述自动创作音乐（灵感模式），或者提供详细参数创作音乐（专业模式）。"
        "未来可扩展支持更多供应商。"
    )
    args_schema: Type[BaseModel] = UniversalMusicGenerationSchema

    def _run(
        self,
        description: str,
        provider: str = "suno",
        mode: str = "inspiration",
        title: Optional[str] = None,
        tags: Optional[str] = None,
        output_dir: Optional[str] = None,
        make_instrumental: bool = False,
        wait_for_completion: bool = True
    ) -> Any:
        """
        执行音乐生成

        Args:
            description: 音乐描述或歌词
            provider: 提供商
            mode: 生成模式
            title: 标题
            tags: 风格标签
            output_dir: 输出目录
            make_instrumental: 是否纯音乐
            wait_for_completion: 是否等待完成

        Returns:
            生成结果字典
        """
        try:
            logger.info(f"🎵 开始音乐生成 - 提供商: {provider}, 模式: {mode}")

            # 目前只支持Suno
            if provider == "suno":
                return self._generate_with_suno(
                    description=description,
                    mode=mode,
                    title=title,
                    tags=tags,
                    output_dir=output_dir,
                    make_instrumental=make_instrumental,
                    wait_for_completion=wait_for_completion
                )
            else:
                error_msg = f"不支持的音乐生成提供商: {provider}，目前仅支持 suno"
                logger.error(f"❌ {error_msg}")
                return {"success": False, "error": error_msg}

        except Exception as e:
            error_msg = f"音乐生成失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}

    def _generate_with_suno(
        self,
        description: str,
        mode: str,
        title: Optional[str],
        tags: Optional[str],
        output_dir: Optional[str],
        make_instrumental: bool,
        wait_for_completion: bool
    ) -> dict:
        """使用Suno进行音乐生成"""
        try:
            client = SunoMusicClient()

            if mode == "inspiration":
                # 灵感模式
                result = client.generate_music_inspiration(
                    gpt_description_prompt=description,
                    wait_for_completion=wait_for_completion,
                    output_dir=output_dir
                )
            elif mode == "custom":
                # 专业模式
                if not title or not tags:
                    return {
                        "success": False,
                        "error": "专业模式需要提供 title 和 tags 参数"
                    }

                result = client.generate_music_custom(
                    prompt=description,
                    tags=tags,
                    title=title,
                    make_instrumental=make_instrumental,
                    wait_for_completion=wait_for_completion,
                    output_dir=output_dir
                )
            else:
                return {
                    "success": False,
                    "error": f"不支持的生成模式: {mode}，支持: inspiration, custom"
                }

            if result.get("success"):
                songs = result.get("songs", [])
                return {
                    "success": True,
                    "provider": "suno",
                    "mode": mode,
                    "songs": songs,
                    "count": len(songs),
                    "message": f"Suno音乐生成成功 ({mode}模式)，共生成 {len(songs)} 首歌曲"
                }
            else:
                return {
                    "success": False,
                    "provider": "suno",
                    "error": result.get("error", "未知错误")
                }

        except Exception as e:
            return {
                "success": False,
                "provider": "suno",
                "error": f"Suno音乐生成异常: {str(e)}"
            }


class UniversalLyricsGenerationTool(BaseTool):
    """通用歌词生成工具"""
    name: str = "Universal Lyrics Generation Tool"
    description: str = (
        "通用AI歌词生成工具，目前支持Suno。"
        "可以根据提示词自动创作歌词，生成的歌词可用于音乐创作。"
        "未来可扩展支持更多供应商。"
    )
    args_schema: Type[BaseModel] = UniversalLyricsGenerationSchema

    def _run(
        self,
        prompt: str,
        provider: str = "suno",
        wait_for_completion: bool = True
    ) -> Any:
        """
        执行歌词生成

        Args:
            prompt: 歌词生成提示词
            provider: 提供商
            wait_for_completion: 是否等待完成

        Returns:
            生成结果字典
        """
        try:
            logger.info(f"✍️ 开始歌词生成 - 提供商: {provider}")

            # 目前只支持Suno
            if provider == "suno":
                return self._generate_with_suno(prompt, wait_for_completion)
            else:
                error_msg = f"不支持的歌词生成提供商: {provider}，目前仅支持 suno"
                logger.error(f"❌ {error_msg}")
                return {"success": False, "error": error_msg}

        except Exception as e:
            error_msg = f"歌词生成失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}

    def _generate_with_suno(self, prompt: str, wait_for_completion: bool) -> dict:
        """使用Suno进行歌词生成"""
        try:
            client = SunoMusicClient()

            result = client.generate_lyrics(
                prompt=prompt,
                wait_for_completion=wait_for_completion
            )

            if result.get("success"):
                lyrics_data = result.get("lyrics", {})
                return {
                    "success": True,
                    "provider": "suno",
                    "lyrics": lyrics_data,
                    "title": lyrics_data.get("title", ""),
                    "text": lyrics_data.get("text", ""),
                    "message": "Suno歌词生成成功"
                }
            else:
                return {
                    "success": False,
                    "provider": "suno",
                    "error": result.get("error", "未知错误")
                }

        except Exception as e:
            return {
                "success": False,
                "provider": "suno",
                "error": f"Suno歌词生成异常: {str(e)}"
            }


# 提供商注册表，便于管理和扩展
MUSIC_GENERATION_PROVIDERS = {
    "suno": {
        "name": "Suno",
        "description": "Suno AI音乐生成服务",
        "supported": True,
        "modes": ["inspiration", "custom"],
        "features": ["lyrics", "music", "instrumental"]
    }
}


def get_supported_providers() -> dict:
    """获取支持的音乐生成提供商列表"""
    return MUSIC_GENERATION_PROVIDERS


def is_provider_supported(provider: str) -> bool:
    """检查提供商是否支持"""
    return provider in MUSIC_GENERATION_PROVIDERS and MUSIC_GENERATION_PROVIDERS[provider]["supported"]
