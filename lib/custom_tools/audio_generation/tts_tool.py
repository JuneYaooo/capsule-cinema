import os
import asyncio
import contextlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, List, Optional, Type

from pydantic import BaseModel, Field

from .base_tool_compat import BaseTool
from src.logger import get_logger

from .minimax_tts_tool import synthesize_with_minimax

logger = get_logger("universal_tts_tool")


def _default_provider() -> str:
    """默认 TTS 提供商。

    优先读取环境变量 TTS_PROVIDER；未设置时按本地可用凭证选择 MiniMax
    或豆包；都不可用时使用本机后期 TTS，避免胶囊因为缺外部 voice key
    而无法完成统一旁白。
    """
    explicit = os.getenv("TTS_PROVIDER")
    if explicit:
        return explicit.strip().lower()
    if os.getenv("DOUBAO_TTS_API_KEY"):
        return "doubao"
    if os.getenv("MINIMAX_API_KEY"):
        return "minimax"
    return "local_system"


class UniversalTTSSchema(BaseModel):
    text: str = Field(..., description="要合成的文本")
    output_path: Optional[str] = Field(None, description="输出文件路径")
    provider: str = Field(
        default_factory=_default_provider,
        description="TTS提供商：minimax、doubao 或 local_system；可通过 TTS_PROVIDER 环境变量覆盖",
    )
    voice_type: str = Field("science_female", description="音色类型，参见豆包TTS预设")
    speed: float = Field(1.0, description="语速比例")
    encoding: str = Field("mp3", description="音频编码格式")


class UniversalTTSBatchSchema(BaseModel):
    texts: List[str] = Field(..., description="要批量合成的文本列表")
    output_dir: str = Field(..., description="输出目录")
    filename_template: str = Field("audio_{:02d}.mp3", description="输出文件名模板")
    provider: str = Field(
        default_factory=_default_provider,
        description="TTS提供商：minimax、doubao 或 local_system",
    )
    voice_type: str = Field("science_female", description="音色类型")
    speed: float = Field(1.0, description="语速比例")
    encoding: str = Field("mp3", description="音频编码格式")


class UniversalTTSTool(BaseTool):
    name: str = "Universal TTS Synthesizer"
    description: str = (
        "通用TTS语音合成工具，支持 MiniMax T2A v2、豆包语音和本机后期 TTS。"
        "可通过 TTS_PROVIDER 环境变量切换默认提供商；远程提供商不可用时可回退到本机。"
    )
    args_schema: Type[BaseModel] = UniversalTTSSchema

    def _run(self, text: str, output_path: Optional[str] = None,
             provider: Optional[str] = None,
             voice_type: str = "science_female", speed: float = 1.0,
             encoding: str = "mp3") -> Any:
        """执行 TTS 合成；按 provider 选择主路径，失败时自动回退到另一方。"""
        provider = (provider or _default_provider()).lower()
        try:
            logger.info(
                f"🎙️ 开始TTS合成 - 提供商: {provider}, 音色: {voice_type}, 语速: {speed}x"
            )

            if provider == "minimax":
                return self._synthesize_with_minimax(
                    text, output_path, voice_type, speed,
                    fallback_to_doubao=True, encoding=encoding,
                )
            if provider == "doubao":
                return self._synthesize_with_doubao(
                    text, output_path, voice_type, speed, encoding,
                )
            if provider in {"local", "local_system", "system", "post_production"}:
                return self._synthesize_with_local_system(
                    text, output_path, voice_type, speed, encoding,
                )

            error_msg = f"不支持的TTS提供商: {provider}（仅支持 minimax / doubao / local_system）"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}

        except Exception as e:
            error_msg = f"TTS合成失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}

    def _synthesize_with_minimax(self, text: str, output_path: Optional[str],
                                 voice_type: str, speed: float,
                                 fallback_to_doubao: bool = True,
                                 encoding: str = "mp3") -> dict:
        """主路径：MiniMax T2A v2。失败可回退到豆包。"""
        if not output_path:
            return {
                "success": False,
                "provider": "minimax",
                "error": "MiniMax 合成需要 output_path",
            }

        result = synthesize_with_minimax(
            text=text, output_path=output_path,
            voice_type=voice_type, speed=speed,
        )
        if result.get("success"):
            return result

        if not fallback_to_doubao:
            return result

        logger.warning(
            f"⚠️ MiniMax TTS 失败，自动回退到豆包。原因: {result.get('error')}"
        )
        doubao_result = self._synthesize_with_doubao(
            text, output_path, voice_type, speed, encoding,
        )
        if doubao_result.get("success"):
            doubao_result["fallback_from"] = "minimax"
            doubao_result["minimax_error"] = result.get("error")
            return doubao_result

        local_result = self._synthesize_with_local_system(
            text, output_path, voice_type, speed, encoding,
        )
        if local_result.get("success"):
            local_result["fallback_from"] = "minimax"
            local_result["minimax_error"] = result.get("error")
            local_result["doubao_error"] = doubao_result.get("error")
            return local_result
        return doubao_result

    def _synthesize_with_local_system(self, text: str, output_path: Optional[str],
                                      voice_type: str, speed: float,
                                      encoding: str = "mp3") -> dict:
        """使用本机 TTS 做后期旁白，不依赖外部 voice key。"""
        if not output_path:
            return {
                "success": False,
                "provider": "local_system",
                "error": "本机 TTS 合成需要 output_path",
            }
        if not text.strip():
            return {
                "success": False,
                "provider": "local_system",
                "error": "本机 TTS 合成需要非空文本",
            }

        if os.getenv("LOCAL_TTS_FORCE_EDGE", "").strip().lower() in {"1", "true", "yes", "on"}:
            return self._synthesize_with_edge_tts(
                text, output_path, voice_type, speed,
                reason="LOCAL_TTS_FORCE_EDGE enabled",
            )

        say_bin = shutil.which("say")
        if not say_bin:
            return self._synthesize_with_edge_tts(
                text, output_path, voice_type, speed,
                reason="未找到 macOS say 命令",
            )

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        system_voice = self._select_local_system_voice(voice_type)
        words_per_minute = max(110, min(260, int(175 * max(speed, 0.5))))

        with tempfile.TemporaryDirectory(prefix="capsule_tts_") as tmp:
            raw_path = Path(tmp) / "voice.aiff"
            say_cmd = [say_bin, "-r", str(words_per_minute), "-o", str(raw_path)]
            if system_voice:
                say_cmd[1:1] = ["-v", system_voice]
            say_cmd.append(text)
            completed = subprocess.run(
                say_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=180,
                check=False,
            )
            if completed.returncode != 0:
                return {
                    "success": False,
                    "provider": "local_system",
                    "error": completed.stderr.strip() or "macOS say 合成失败",
                }

            if out.suffix.lower() in {".aif", ".aiff"}:
                shutil.copyfile(raw_path, out)
            else:
                ffmpeg_bin = self._ffmpeg_executable()
                if not ffmpeg_bin:
                    return {
                        "success": False,
                        "provider": "local_system",
                        "error": "未找到 ffmpeg，无法把本机 TTS 音频转成目标格式",
                    }
                converted = subprocess.run(
                    [
                        ffmpeg_bin,
                        "-y",
                        "-loglevel",
                        "error",
                        "-i",
                        str(raw_path),
                        str(out),
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=180,
                    check=False,
                )
                if converted.returncode != 0:
                    return self._synthesize_with_edge_tts(
                        text, output_path, voice_type, speed,
                        reason=converted.stderr.strip() or "ffmpeg 音频转码失败",
                    )

        if not self._audio_file_has_duration(out):
            with contextlib.suppress(Exception):
                out.unlink()
            return self._synthesize_with_edge_tts(
                text, output_path, voice_type, speed,
                reason="macOS say 生成了空音频",
            )

        logger.info(f"🎙️ 本机后期 TTS 成功: voice={system_voice or 'system-default'} -> {out}")
        return {
            "success": True,
            "provider": "local_system",
            "output_path": str(out),
            "audio_path": str(out),
            "voice_type": voice_type,
            "system_voice": system_voice or "system-default",
        }

    def _synthesize_with_edge_tts(self, text: str, output_path: Optional[str],
                                  voice_type: str, speed: float,
                                  reason: str = "") -> dict:
        """无 key 的后期 TTS 兜底；需要 edge-tts 包和网络可达。"""
        if not output_path:
            return {
                "success": False,
                "provider": "local_system",
                "error": "Edge TTS 兜底需要 output_path",
            }
        try:
            import edge_tts
        except ModuleNotFoundError:
            return {
                "success": False,
                "provider": "local_system",
                "error": (
                    f"{reason}；edge-tts 未安装，无法使用无 key 后期 TTS 兜底"
                    if reason else "edge-tts 未安装，无法使用无 key 后期 TTS 兜底"
                ),
            }

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        voice = os.getenv("EDGE_TTS_VOICE") or self._edge_voice_for(voice_type)
        rate_percent = max(-50, min(100, int((speed - 1.0) * 100)))
        rate = f"{rate_percent:+d}%"

        async def save_audio() -> None:
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            await communicate.save(str(out))

        try:
            asyncio.run(asyncio.wait_for(save_audio(), timeout=180))
        except Exception as exc:
            return {
                "success": False,
                "provider": "local_system",
                "error": f"{reason}；Edge TTS 兜底失败: {exc}" if reason else f"Edge TTS 兜底失败: {exc}",
            }

        if not self._audio_file_has_duration(out):
            return {
                "success": False,
                "provider": "local_system",
                "error": f"{reason}；Edge TTS 生成了无效音频" if reason else "Edge TTS 生成了无效音频",
            }

        logger.info(f"🎙️ Edge 后期 TTS 成功: voice={voice} -> {out}")
        return {
            "success": True,
            "provider": "local_system",
            "output_path": str(out),
            "audio_path": str(out),
            "voice_type": voice_type,
            "system_voice": voice,
            "fallback_reason": reason,
        }

    @staticmethod
    def _edge_voice_for(voice_type: str) -> str:
        if UniversalTTSTool._voice_type_prefers_male(voice_type):
            return "zh-CN-YunxiNeural"
        return "zh-CN-XiaoxiaoNeural"

    @staticmethod
    def _voice_type_prefers_male(voice_type: str) -> bool:
        lower_voice_type = (voice_type or "").lower()
        if "female" in lower_voice_type or "女" in lower_voice_type:
            return False
        return "male" in lower_voice_type or "男" in lower_voice_type

    def _select_local_system_voice(self, voice_type: str) -> Optional[str]:
        env_voice = os.getenv("LOCAL_TTS_VOICE")
        if env_voice:
            return env_voice

        available = self._available_macos_voices()
        preferred = [
            "Ting-Ting",
            "Mei-Jia",
            "Sin-ji",
            "Yu-shu",
            "Li-mu",
        ]
        if self._voice_type_prefers_male(voice_type):
            preferred.extend(["Yunjian", "Eddy"])
        preferred.extend(["Samantha", "Ava"])

        if not available:
            return None
        for voice in preferred:
            if voice in available:
                return voice
        return None

    @staticmethod
    def _available_macos_voices() -> set[str]:
        say_bin = shutil.which("say")
        if not say_bin:
            return set()
        try:
            result = subprocess.run(
                [say_bin, "-v", "?"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=20,
                check=False,
            )
        except Exception:
            return set()
        voices = set()
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            voices.add(line.split()[0])
        return voices

    @staticmethod
    def _ffmpeg_executable() -> Optional[str]:
        try:
            import imageio_ffmpeg

            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return shutil.which("ffmpeg")

    @staticmethod
    def _audio_file_has_duration(path: Path) -> bool:
        if not path.exists() or path.stat().st_size < 1024:
            return False

        ffprobe_bin = shutil.which("ffprobe")
        if not ffprobe_bin:
            return path.stat().st_size > 4096

        try:
            result = subprocess.run(
                [
                    ffprobe_bin,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "json",
                    str(path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=20,
                check=False,
            )
            if result.returncode != 0:
                return False
            data = json.loads(result.stdout or "{}")
            return float(data.get("format", {}).get("duration") or 0) > 0.25
        except Exception:
            return False

    def _synthesize_with_doubao(self, text: str, output_path: Optional[str],
                               voice_type: str, speed: float, encoding: str) -> dict:
        """Use the API-Key authenticated Doubao bidirectional WebSocket route."""
        try:
            from .doubao_tts_tool import DoubaoTTSTool

            result = DoubaoTTSTool()._run(
                text=text,
                output_path=output_path,
                voice_type=voice_type,
                speed_ratio=speed,
                encoding=encoding,
            )
            if result.get("success"):
                return result
            return self._fallback_to_minimax(
                text, output_path, voice_type, speed,
                doubao_error=result.get("error") or "豆包语音合成失败",
            )
        except Exception as exc:
            return self._fallback_to_minimax(
                text, output_path, voice_type, speed,
                doubao_error=f"豆包语音合成调用异常: {exc}",
            )

    def _fallback_to_minimax(self, text: str, output_path: Optional[str],
                             voice_type: str, speed: float,
                             doubao_error: str) -> dict:
        """豆包失败时使用已批准的 MiniMax 或本机后期 TTS 兜底。"""
        if not output_path:
            return {
                "success": False,
                "provider": "doubao",
                "error": doubao_error or "豆包TTS失败，且缺少 output_path 无法回退",
            }

        logger.warning(f"⚠️ 豆包TTS失败，自动回退到 MiniMax。原因: {doubao_error}")
        result = synthesize_with_minimax(
            text=text,
            output_path=output_path,
            voice_type=voice_type,
            speed=speed,
        )
        if result.get("success"):
            result["fallback_from"] = "doubao"
            result["doubao_error"] = doubao_error
            return result

        local_result = self._synthesize_with_local_system(
            text, output_path, voice_type, speed,
        )
        if local_result.get("success"):
            local_result["fallback_from"] = "doubao"
            local_result["doubao_error"] = doubao_error
            local_result["minimax_error"] = result.get("error")
            return local_result

        return {
            "success": False,
            "provider": "doubao",
            "error": doubao_error,
            "fallback_attempt": result,
        }


class UniversalTTSBatchTool(BaseTool):
    name: str = "Universal TTS Batch Synthesizer"
    description: str = (
        "通用TTS批量语音合成工具，目前支持豆包TTS。"
        "可以批量处理多个文本，生成对应的音频文件。支持自动重试和结果验证。"
    )
    args_schema: Type[BaseModel] = UniversalTTSBatchSchema

    def _run(self, texts: List[str], output_dir: str, filename_template: str = "audio_{:02d}.mp3",
             provider: Optional[str] = None, voice_type: str = "science_female",
             speed: float = 1.0, encoding: str = "mp3") -> Any:
        """
        批量执行TTS语音合成

        Args:
            texts: 要合成的文本列表
            output_dir: 输出目录
            filename_template: 文件名模板
            provider: TTS提供商
            voice_type: 音色类型
            speed: 语速比例
            encoding: 音频编码格式

        Returns:
            批量合成结果字典
        """
        try:
            provider = (provider or _default_provider()).lower()
            logger.info(f"🎙️ 开始批量TTS合成 - 提供商: {provider}, 数量: {len(texts)}")
            import os
            import time
            start_time = time.time()

            if provider in (
                "minimax", "doubao",
                "local", "local_system", "system", "post_production",
            ):
                # 批量路径未直接支持 minimax；逐条走 UniversalTTSTool._run，
                # 由它内部完成 minimax/doubao 的选择和回退。
                from pathlib import Path
                Path(output_dir).mkdir(parents=True, exist_ok=True)
                results = []
                single = UniversalTTSTool()
                for i, text in enumerate(texts):
                    out = str(Path(output_dir) / filename_template.format(i))
                    results.append(single._run(
                        text=text, output_path=out, provider=provider,
                        voice_type=voice_type, speed=speed, encoding=encoding,
                    ))
                return {
                    "success": all(r.get("success") for r in results),
                    "provider": provider,
                    "results": results,
                    "elapsed_seconds": time.time() - start_time,
                }

            error_msg = f"不支持的TTS提供商: {provider}（仅支持 minimax / doubao / local_system）"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}

        except Exception as e:
            error_msg = f"批量TTS合成失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}

    def _batch_synthesize_with_doubao_enhanced(self, texts: List[str], output_dir: str,
                                    filename_template: str, voice_type: str,
                                    speed: float, encoding: str) -> dict:
        """使用豆包TTS批量合成（增强版，带重试和验证）"""
        try:
            import os
            import time
            from .doubao_tts_tool import DoubaoTTSTool

            start_time = time.time()

            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)

            doubao_tool = DoubaoTTSTool()
            outputs = []
            results = []
            generated_count = 0
            failed_count = 0

            for i, text in enumerate(texts):
                max_retries = 3
                retry_delay = 5.0
                success = False
                last_error = None

                output_filename = filename_template.format(i) if "{" in filename_template else f"{filename_template}_{i}.mp3"
                output_path = os.path.join(output_dir, output_filename)

                for attempt in range(max_retries):
                    try:
                        if attempt > 0:
                            logger.info(f"🔄 文本 {i} TTS合成重试 (第{attempt + 1}次尝试)")
                            time.sleep(retry_delay)

                        result = doubao_tool._run(
                            text=text,
                            output_path=output_path,
                            voice_type=voice_type,
                            speed_ratio=speed,
                            encoding=encoding
                        )

                        # 检查结果
                        if isinstance(result, dict) and result.get("success") and os.path.exists(output_path):
                            file_size = os.path.getsize(output_path)
                            if file_size < 1024:  # 至少1KB
                                raise Exception(f"生成的音频文件过小 ({file_size} 字节)，可能损坏")

                            logger.info(f"✅ 文本 {i} TTS合成成功: {output_path} ({file_size} 字节)")
                            outputs.append(output_path)
                            results.append({"index": i, "status": "success", "path": output_path})
                            generated_count += 1
                            success = True
                            break
                        elif isinstance(result, dict) and result.get("error"):
                            raise Exception(result["error"])
                        else:
                            raise Exception("TTS合成返回格式异常")

                    except Exception as e:
                        last_error = str(e)
                        logger.warning(f"⚠️ 文本 {i} TTS合成失败 (尝试 {attempt + 1}/{max_retries}): {last_error}")

                if not success:
                    outputs.append(None)
                    results.append({"index": i, "status": "failed", "error": last_error})
                    failed_count += 1
                    logger.error(f"❌ 文本 {i} TTS合成最终失败 (已达到最大重试次数)")

                # API 限流延迟
                if i < len(texts) - 1:
                    time.sleep(1)

            end_time = time.time()
            summary = {
                "success": generated_count > 0,
                "provider": "doubao",
                "outputs": outputs,
                "summary": {
                    "total": len(texts),
                    "generated": generated_count,
                    "failed": failed_count,
                    "success_rate": f"{(generated_count/len(texts)*100):.1f}%" if len(texts) > 0 else "0%",
                    "processing_time": f"{end_time - start_time:.2f}秒"
                },
                "results": results,
                "message": f"豆包TTS批量合成完成: {generated_count}/{len(texts)} 成功"
            }

            logger.info(f"🎙️ 批量TTS合成完成 - 成功: {generated_count}/{len(texts)} ({summary['summary']['success_rate']}), 耗时: {summary['summary']['processing_time']}")
            return summary

        except Exception as e:
            return {
                "success": False,
                "provider": "doubao",
                "error": f"豆包TTS批量合成异常: {str(e)}"
            }

    def _batch_synthesize_with_doubao(self, texts: List[str], output_dir: str,
                                    filename_template: str, voice_type: str,
                                    speed: float, encoding: str) -> dict:
        """Compatibility wrapper around the current Doubao batch route."""
        return self._batch_synthesize_with_doubao_enhanced(
            texts, output_dir, filename_template, voice_type, speed, encoding,
        )


# 提供商注册表，便于管理和扩展
TTS_PROVIDERS = {
    "minimax": {
        "name": "MiniMax T2A",
        "description": "MiniMax T2A v2 服务",
        "supported": True,
        "batch_supported": True
    },
    "doubao": {
        "name": "豆包TTS",
        "description": "字节跳动豆包TTS服务",
        "supported": True,
        "batch_supported": True
    },
    "local_system": {
        "name": "本机后期TTS",
        "description": "使用 macOS say 和 ffmpeg 在后期生成旁白，不需要外部 voice key",
        "supported": True,
        "batch_supported": True
    }
}


def get_supported_providers() -> dict:
    """获取支持的TTS提供商列表"""
    return TTS_PROVIDERS


def is_provider_supported(provider: str) -> bool:
    """检查提供商是否支持"""
    return provider in TTS_PROVIDERS and TTS_PROVIDERS[provider]["supported"]
