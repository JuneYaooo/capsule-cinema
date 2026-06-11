#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Suno音乐生成CrewAI工具
使用Suno API进行AI音乐创作
"""

import os
import time
import json
import requests
from typing import Type, Optional, Dict, Any, List
from dotenv import load_dotenv
from pathlib import Path
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from src.logger import get_logger

# 加载环境变量
load_dotenv()

logger = get_logger("suno_music_tool")


class SunoMusicSchema(BaseModel):
    """Suno音乐生成工具的输入参数"""
    gpt_description_prompt: str = Field(
        ...,
        description="灵感模式提示词，描述你想要生成的音乐风格和内容"
    )
    mv: str = Field(
        default="chirp-crow",
        description="模型版本，默认为 chirp-crow"
    )
    output_dir: Optional[str] = Field(
        default=None,
        description="音乐文件下载保存目录，如果不指定则不下载"
    )
    wait_for_completion: bool = Field(
        default=True,
        description="是否等待任务完成"
    )
    max_wait_time: int = Field(
        default=600,
        description="最大等待时间（秒），默认600秒"
    )


class SunoMusicCustomSchema(BaseModel):
    """Suno专业模式音乐生成工具的输入参数"""
    prompt: str = Field(
        ...,
        description="歌词内容"
    )
    tags: str = Field(
        ...,
        description="风格标签，如 'Chinese Hip Hop, Rap, funny, comedy'"
    )
    title: str = Field(
        ...,
        description="歌曲标题"
    )
    mv: str = Field(
        default="chirp-crow",
        description="模型版本，默认为 chirp-crow"
    )
    negative_tags: str = Field(
        default="",
        description="禁用的风格标签"
    )
    make_instrumental: bool = Field(
        default=False,
        description="是否生成纯音乐（无人声）"
    )
    output_dir: Optional[str] = Field(
        default=None,
        description="音乐文件下载保存目录"
    )
    wait_for_completion: bool = Field(
        default=True,
        description="是否等待任务完成"
    )
    max_wait_time: int = Field(
        default=600,
        description="最大等待时间（秒）"
    )


class SunoLyricsSchema(BaseModel):
    """Suno歌词生成工具的输入参数"""
    prompt: str = Field(
        ...,
        description="歌词生成提示词"
    )
    wait_for_completion: bool = Field(
        default=True,
        description="是否等待任务完成"
    )
    max_wait_time: int = Field(
        default=300,
        description="最大等待时间（秒）"
    )
    max_retries: int = Field(
        default=3,
        description="最大重试次数"
    )


class SunoMusicTool(BaseTool):
    """Suno灵感模式音乐生成工具"""
    name: str = "Suno音乐生成工具（灵感模式）"
    description: str = (
        "使用Suno API生成AI音乐的工具（灵感模式）。"
        "只需提供音乐描述，AI会自动创作完整的音乐作品，包括旋律、歌词和编曲。"
        "适合快速创作各种风格的音乐。"
    )
    args_schema: Type[BaseModel] = SunoMusicSchema

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _run(
        self,
        gpt_description_prompt: str,
        mv: str = "chirp-crow",
        output_dir: Optional[str] = None,
        wait_for_completion: bool = True,
        max_wait_time: int = 600
    ) -> str:
        """
        执行Suno音乐生成（灵感模式）

        Args:
            gpt_description_prompt: 灵感模式提示词
            mv: 模型版本
            output_dir: 输出目录
            wait_for_completion: 是否等待完成
            max_wait_time: 最大等待时间

        Returns:
            生成结果的描述信息
        """
        try:
            # 初始化Suno客户端
            client = SunoMusicClient()

            # 生成音乐
            result = client.generate_music_inspiration(
                gpt_description_prompt=gpt_description_prompt,
                mv=mv,
                wait_for_completion=wait_for_completion,
                max_wait_time=max_wait_time,
                output_dir=output_dir
            )

            if result.get("success"):
                songs = result.get("songs", [])
                if songs:
                    # 检查歌曲数据是否有效（至少要有audio_url或local_path）
                    valid_songs = []
                    for song in songs:
                        if song.get('audio_url') or song.get('local_path'):
                            valid_songs.append(song)
                        else:
                            logger.warning(f"⚠️ 歌曲数据不完整: {song}")

                    if valid_songs:
                        response = f"✅ Suno音乐生成成功！共生成 {len(valid_songs)} 首歌曲：\n"
                        for i, song in enumerate(valid_songs, 1):
                            response += f"\n歌曲 {i}:\n"
                            response += f"  - 标题: {song.get('title', 'N/A')}\n"
                            response += f"  - ID: {song.get('id', 'N/A')}\n"
                            response += f"  - 标签: {song.get('tags', 'N/A')}\n"
                            response += f"  - 音频URL: {song.get('audio_url', 'N/A')}\n"
                            if song.get('local_path'):
                                response += f"  - 本地路径: {song['local_path']}\n"
                        return response
                    else:
                        logger.error("❌ Suno返回的歌曲数据均无效（缺少音频URL和本地路径）")
                        return "❌ Suno音乐生成失败: 返回的歌曲数据无效"
                else:
                    logger.error("❌ Suno音乐生成完成，但没有返回歌曲数据")
                    return "❌ Suno音乐生成失败: 没有返回歌曲数据"
            else:
                error = result.get("error", "未知错误")
                return f"❌ Suno音乐生成失败: {error}"

        except Exception as e:
            logger.error(f"Suno音乐生成异常: {str(e)}")
            return f"❌ Suno音乐生成失败: {str(e)}"


class SunoMusicCustomTool(BaseTool):
    """Suno专业模式音乐生成工具"""
    name: str = "Suno音乐生成工具（专业模式）"
    description: str = (
        "使用Suno API生成AI音乐的工具（专业模式）。"
        "可以自定义歌词、风格标签、标题等，实现更精细的音乐创作控制。"
        "适合需要精确控制音乐内容和风格的场景。"
    )
    args_schema: Type[BaseModel] = SunoMusicCustomSchema

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _run(
        self,
        prompt: str,
        tags: str,
        title: str,
        mv: str = "chirp-crow",
        negative_tags: str = "",
        make_instrumental: bool = False,
        output_dir: Optional[str] = None,
        wait_for_completion: bool = True,
        max_wait_time: int = 600
    ) -> str:
        """
        执行Suno音乐生成（专业模式）

        Args:
            prompt: 歌词
            tags: 风格标签
            title: 标题
            mv: 模型版本
            negative_tags: 禁用的风格标签
            make_instrumental: 是否纯音乐
            output_dir: 输出目录
            wait_for_completion: 是否等待完成
            max_wait_time: 最大等待时间

        Returns:
            生成结果的描述信息
        """
        try:
            # 初始化Suno客户端
            client = SunoMusicClient()

            # 生成音乐
            result = client.generate_music_custom(
                prompt=prompt,
                tags=tags,
                title=title,
                mv=mv,
                negative_tags=negative_tags,
                make_instrumental=make_instrumental,
                wait_for_completion=wait_for_completion,
                max_wait_time=max_wait_time,
                output_dir=output_dir
            )

            if result.get("success"):
                songs = result.get("songs", [])
                if songs:
                    # 检查歌曲数据是否有效（至少要有audio_url或local_path）
                    valid_songs = []
                    for song in songs:
                        if song.get('audio_url') or song.get('local_path'):
                            valid_songs.append(song)
                        else:
                            logger.warning(f"⚠️ 歌曲数据不完整: {song}")

                    if valid_songs:
                        response = f"✅ Suno音乐生成成功（专业模式）！共生成 {len(valid_songs)} 首歌曲：\n"
                        for i, song in enumerate(valid_songs, 1):
                            response += f"\n歌曲 {i}:\n"
                            response += f"  - 标题: {song.get('title', 'N/A')}\n"
                            response += f"  - ID: {song.get('id', 'N/A')}\n"
                            response += f"  - 标签: {song.get('tags', 'N/A')}\n"
                            response += f"  - 音频URL: {song.get('audio_url', 'N/A')}\n"
                            if song.get('local_path'):
                                response += f"  - 本地路径: {song['local_path']}\n"
                        return response
                    else:
                        logger.error("❌ Suno返回的歌曲数据均无效（缺少音频URL和本地路径）")
                        return "❌ Suno音乐生成失败: 返回的歌曲数据无效"
                else:
                    logger.error("❌ Suno音乐生成完成，但没有返回歌曲数据")
                    return "❌ Suno音乐生成失败: 没有返回歌曲数据"
            else:
                error = result.get("error", "未知错误")
                return f"❌ Suno音乐生成失败: {error}"

        except Exception as e:
            logger.error(f"Suno音乐生成异常: {str(e)}")
            return f"❌ Suno音乐生成失败: {str(e)}"


class SunoLyricsTool(BaseTool):
    """Suno歌词生成工具"""
    name: str = "Suno歌词生成工具"
    description: str = (
        "使用Suno API生成歌词的工具。"
        "根据提示词自动创作歌词，可用于后续音乐生成。"
    )
    args_schema: Type[BaseModel] = SunoLyricsSchema

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _run(
        self,
        prompt: str,
        wait_for_completion: bool = True,
        max_wait_time: int = 300,
        max_retries: int = 3
    ) -> str:
        """
        执行Suno歌词生成（带重试机制）

        Args:
            prompt: 歌词生成提示词
            wait_for_completion: 是否等待完成
            max_wait_time: 最大等待时间
            max_retries: 最大重试次数

        Returns:
            生成的歌词
        """
        # 初始化Suno客户端
        client = SunoMusicClient()
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"🔄 歌词生成尝试 {attempt}/{max_retries}")

                # 生成歌词
                result = client.generate_lyrics(
                    prompt=prompt,
                    wait_for_completion=wait_for_completion,
                    max_wait_time=max_wait_time
                )

                if result.get("success"):
                    lyrics_data = result.get("lyrics", {})
                    title = lyrics_data.get("title", "无标题")
                    text = lyrics_data.get("text", "")

                    # 验证歌词有效性
                    if text and len(text.strip()) > 20:
                        logger.info(f"✅ 第{attempt}次尝试成功，歌词长度: {len(text)} 字符")
                        response = f"✅ Suno歌词生成成功！\n\n"
                        response += f"标题: {title}\n\n"
                        response += f"歌词:\n{text}"
                        return response
                    else:
                        logger.warning(f"⚠️ 第{attempt}次尝试: 歌词内容无效或过短 (长度: {len(text.strip()) if text else 0})")
                        last_error = "歌词内容无效或过短"
                else:
                    error = result.get("error", "未知错误")
                    logger.warning(f"⚠️ 第{attempt}次尝试失败: {error}")
                    last_error = error

                # 如果不是最后一次尝试，等待后重试
                if attempt < max_retries:
                    retry_wait = 5
                    logger.info(f"   等待 {retry_wait} 秒后重试...")
                    time.sleep(retry_wait)

            except Exception as e:
                logger.error(f"❌ 第{attempt}次尝试异常: {str(e)}")
                last_error = str(e)
                if attempt < max_retries:
                    retry_wait = 5
                    logger.info(f"   等待 {retry_wait} 秒后重试...")
                    time.sleep(retry_wait)

        # 所有重试均失败
        error_msg = f"❌ Suno歌词生成失败（已重试{max_retries}次）: {last_error}"
        logger.error(error_msg)
        return error_msg


class SunoMusicClient:
    """Suno音乐生成客户端"""

    def __init__(self):
        """初始化Suno客户端"""
        # 获取环境变量
        self.base_url = os.getenv('SUNO_BASE_URL')
        self.api_key = os.getenv('SUNO_API_KEY')

        if not self.base_url:
            raise ValueError("缺少环境变量: SUNO_BASE_URL")
        if not self.api_key:
            raise ValueError("缺少环境变量: SUNO_API_KEY")

        self.base_url = self.base_url.rstrip('/')
        self.headers = {
            'Authorization': self.api_key,
            'Content-Type': 'application/json'
        }

        logger.info(f"Suno客户端初始化成功，API地址: {self.base_url}")

    def generate_lyrics(
        self,
        prompt: str,
        wait_for_completion: bool = True,
        max_wait_time: int = 300
    ) -> Dict[str, Any]:
        """
        生成歌词

        Args:
            prompt: 提示词
            wait_for_completion: 是否等待完成
            max_wait_time: 最大等待时间

        Returns:
            生成结果
        """
        try:
            url = f"{self.base_url}/suno/submit/lyrics"
            payload = {"prompt": prompt}

            logger.info(f"🎵 开始生成歌词...")
            logger.info(f"   提示词: {prompt}")

            response = requests.post(url, json=payload, headers=self.headers)

            if response.status_code != 200:
                logger.error(f"API请求失败: {response.status_code}")
                return {"success": False, "error": f"HTTP {response.status_code}"}

            result = response.json()

            if result.get('code') == 'success':
                task_id = result.get('data')
                logger.info(f"   任务已提交: {task_id}")

                if wait_for_completion:
                    final_result = self._wait_for_task(task_id, max_wait_time)

                    if final_result.get('code') == 'success':
                        data = final_result.get('data', {})
                        lyrics_data = data.get('data', {})
                        logger.info(f"✅ 歌词生成成功")

                        return {
                            "success": True,
                            "task_id": task_id,
                            "lyrics": lyrics_data
                        }
                    else:
                        return {"success": False, "error": "任务执行失败"}
                else:
                    return {"success": True, "task_id": task_id, "status": "pending"}
            else:
                error_msg = result.get('message', '未知错误')
                logger.error(f"❌ 歌词生成失败: {error_msg}")
                return {"success": False, "error": error_msg}

        except Exception as e:
            logger.error(f"❌ 歌词生成异常: {str(e)}")
            return {"success": False, "error": str(e)}

    def generate_music_inspiration(
        self,
        gpt_description_prompt: str,
        mv: str = "chirp-crow",
        wait_for_completion: bool = True,
        max_wait_time: int = 600,
        output_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成音乐（灵感模式）

        Args:
            gpt_description_prompt: 灵感模式提示词
            mv: 模型版本
            wait_for_completion: 是否等待完成
            max_wait_time: 最大等待时间
            output_dir: 输出目录

        Returns:
            生成结果
        """
        try:
            url = f"{self.base_url}/suno/submit/music"
            payload = {
                "gpt_description_prompt": gpt_description_prompt,
                "mv": mv
            }

            logger.info(f"🎵 开始生成音乐（灵感模式）...")
            logger.info(f"   提示词: {gpt_description_prompt}")
            logger.info(f"   模型: {mv}")

            response = requests.post(url, json=payload, headers=self.headers)

            if response.status_code != 200:
                logger.error(f"API请求失败: {response.status_code}")
                return {"success": False, "error": f"HTTP {response.status_code}"}

            result = response.json()

            if result.get('code') == 'success':
                task_id = result.get('data')
                logger.info(f"   任务已提交: {task_id}")

                if wait_for_completion:
                    final_result = self._wait_for_task(task_id, max_wait_time)

                    if final_result.get('code') == 'success':
                        data = final_result.get('data', {})
                        songs = data.get('data', [])

                        # 下载音乐文件（如果指定了输出目录）
                        if output_dir and songs:
                            songs = self._download_songs(songs, output_dir)

                        logger.info(f"✅ 音乐生成成功，共 {len(songs)} 首")

                        return {
                            "success": True,
                            "task_id": task_id,
                            "songs": songs
                        }
                    else:
                        return {"success": False, "error": "任务执行失败"}
                else:
                    return {"success": True, "task_id": task_id, "status": "pending"}
            else:
                error_msg = result.get('message', '未知错误')
                logger.error(f"❌ 音乐生成失败: {error_msg}")
                return {"success": False, "error": error_msg}

        except Exception as e:
            logger.error(f"❌ 音乐生成异常: {str(e)}")
            return {"success": False, "error": str(e)}

    def generate_music_custom(
        self,
        prompt: str,
        tags: str,
        title: str,
        mv: str = "chirp-crow",
        negative_tags: str = "",
        make_instrumental: bool = False,
        wait_for_completion: bool = True,
        max_wait_time: int = 600,
        output_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成音乐（专业模式）

        Args:
            prompt: 歌词
            tags: 风格标签
            title: 标题
            mv: 模型版本
            negative_tags: 禁用的风格
            make_instrumental: 是否纯音乐
            wait_for_completion: 是否等待完成
            max_wait_time: 最大等待时间
            output_dir: 输出目录

        Returns:
            生成结果
        """
        try:
            url = f"{self.base_url}/suno/submit/music"
            payload = {
                "prompt": prompt,
                "tags": tags,
                "title": title,
                "mv": mv,
                "negative_tags": negative_tags,
                "make_instrumental": make_instrumental
            }

            logger.info(f"🎵 开始生成音乐（专业模式）...")
            logger.info(f"   标题: {title}")
            logger.info(f"   标签: {tags}")
            logger.info(f"   模型: {mv}")

            response = requests.post(url, json=payload, headers=self.headers)

            if response.status_code != 200:
                logger.error(f"API请求失败: {response.status_code}")
                return {"success": False, "error": f"HTTP {response.status_code}"}

            result = response.json()

            if result.get('code') == 'success':
                task_id = result.get('data')
                logger.info(f"   任务已提交: {task_id}")

                if wait_for_completion:
                    final_result = self._wait_for_task(task_id, max_wait_time)

                    if final_result.get('code') == 'success':
                        data = final_result.get('data', {})
                        songs = data.get('data', [])

                        # 下载音乐文件（如果指定了输出目录）
                        if output_dir and songs:
                            songs = self._download_songs(songs, output_dir)

                        logger.info(f"✅ 音乐生成成功，共 {len(songs)} 首")

                        return {
                            "success": True,
                            "task_id": task_id,
                            "songs": songs
                        }
                    else:
                        return {"success": False, "error": "任务执行失败"}
                else:
                    return {"success": True, "task_id": task_id, "status": "pending"}
            else:
                error_msg = result.get('message', '未知错误')
                logger.error(f"❌ 音乐生成失败: {error_msg}")
                return {"success": False, "error": error_msg}

        except Exception as e:
            logger.error(f"❌ 音乐生成异常: {str(e)}")
            return {"success": False, "error": str(e)}

    def fetch_task(self, task_id: str) -> Dict[str, Any]:
        """
        查询任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务数据
        """
        try:
            url = f"{self.base_url}/suno/fetch/{task_id}"
            response = requests.get(url, headers=self.headers)

            if response.status_code != 200:
                return {"code": "error", "message": f"HTTP {response.status_code}"}

            return response.json()

        except Exception as e:
            return {"code": "error", "message": str(e)}

    def _wait_for_task(
        self,
        task_id: str,
        max_wait_time: int = 600,
        poll_interval: int = 5
    ) -> Dict[str, Any]:
        """
        等待任务完成

        Args:
            task_id: 任务ID
            max_wait_time: 最大等待时间（秒）
            poll_interval: 轮询间隔（秒）

        Returns:
            最终任务数据
        """
        logger.info(f"⏳ 等待任务 {task_id} 完成...")
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            result = self.fetch_task(task_id)

            if result.get('code') == 'success':
                data = result.get('data', {})
                status = data.get('status')
                progress = data.get('progress', '0%')

                logger.info(f"   任务状态: {status}, 进度: {progress}")

                if status == 'SUCCESS':
                    logger.info("✅ 任务完成!")
                    return result
                elif status == 'FAILURE':
                    logger.error(f"❌ 任务失败: {data.get('failReason')}")
                    return result

            time.sleep(poll_interval)

        logger.warning(f"⏰ 任务等待超时({max_wait_time}秒)")
        return self.fetch_task(task_id)

    def _download_songs(self, songs: List[Dict], output_dir: str) -> List[Dict]:
        """
        下载歌曲文件

        Args:
            songs: 歌曲列表
            output_dir: 输出目录

        Returns:
            更新后的歌曲列表（包含本地路径）
        """
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            logger.info(f"📥 开始下载音乐文件到: {output_dir}")

            for i, song in enumerate(songs):
                audio_url = song.get('audio_url')
                if not audio_url:
                    continue

                # 生成文件名
                song_id = song.get('id', f'song_{i}')
                title = song.get('title', 'untitled')
                # 清理文件名中的非法字符
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
                filename = f"{safe_title}_{song_id}.mp3"
                filepath = output_path / filename

                try:
                    logger.info(f"   下载第 {i+1}/{len(songs)} 首: {safe_title}")
                    response = requests.get(audio_url, timeout=60)

                    if response.status_code == 200:
                        with open(filepath, 'wb') as f:
                            f.write(response.content)

                        song['local_path'] = str(filepath.absolute())
                        logger.info(f"   ✅ 下载成功: {filepath}")
                    else:
                        logger.warning(f"   ⚠️ 下载失败: HTTP {response.status_code}")

                except Exception as e:
                    logger.error(f"   ❌ 下载异常: {str(e)}")

            return songs

        except Exception as e:
            logger.error(f"❌ 下载音乐文件失败: {str(e)}")
            return songs

    @classmethod
    def validate_config(cls) -> Dict[str, bool]:
        """验证配置"""
        checks = {
            'env_SUNO_BASE_URL': bool(os.getenv('SUNO_BASE_URL')),
            'env_SUNO_API_KEY': bool(os.getenv('SUNO_API_KEY'))
        }
        return checks
