from typing import Any, List, Optional, Type
import os

from pydantic import BaseModel, Field

from .base_tool_compat import BaseTool
from src.logger import get_logger

from .minimax_tts_tool import synthesize_with_minimax

logger = get_logger("universal_tts_tool")


def _default_provider() -> str:
    """默认 TTS 提供商。

    优先读取环境变量 TTS_PROVIDER；未设置时默认 minimax，因为豆包 _moon_bigtts
    系列大模型音色需要单独申请，未开通账号会全部 403。
    """
    return (os.getenv("TTS_PROVIDER") or "minimax").strip().lower()


class UniversalTTSSchema(BaseModel):
    text: str = Field(..., description="要合成的文本")
    output_path: Optional[str] = Field(None, description="输出文件路径")
    provider: str = Field(
        default_factory=_default_provider,
        description="TTS提供商：minimax（默认）或 doubao；可通过 TTS_PROVIDER 环境变量覆盖",
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
        description="TTS提供商：minimax（默认）或 doubao",
    )
    voice_type: str = Field("science_female", description="音色类型")
    speed: float = Field(1.0, description="语速比例")
    encoding: str = Field("mp3", description="音频编码格式")


class UniversalTTSTool(BaseTool):
    name: str = "Universal TTS Synthesizer"
    description: str = (
        "通用TTS语音合成工具，支持 MiniMax T2A v2（默认）和豆包 TTS。"
        "可通过 TTS_PROVIDER 环境变量切换默认提供商；任一提供商失败时自动回退到另一方。"
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

            error_msg = f"不支持的TTS提供商: {provider}（仅支持 minimax / doubao）"
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

    
    def _synthesize_with_doubao(self, text: str, output_path: Optional[str],
                               voice_type: str, speed: float, encoding: str) -> dict:
        """使用豆包TTS进行合成"""
        try:
            from .doubao_tts_tool import DoubaoTTSTool

            doubao_tool = DoubaoTTSTool()
            result = doubao_tool._run(
                text=text,
                output_path=output_path,
                voice_type=voice_type,
                speed_ratio=speed,  # 豆包使用speed_ratio参数
                encoding=encoding
            )

            # 解析豆包工具的返回结果
            if isinstance(result, str):
                if "成功" in result and "音频已保存到:" in result:
                    # 提取文件路径
                    output_file = result.split("音频已保存到: ")[-1]
                    return {
                        "success": True,
                        "output_path": output_file,
                        "provider": "doubao",
                        "message": result
                    }
                else:
                    return self._fallback_to_minimax(
                        text, output_path, voice_type, speed,
                        doubao_error=result,
                    )
            else:
                return self._fallback_to_minimax(
                    text, output_path, voice_type, speed,
                    doubao_error="豆包TTS返回格式异常",
                )

        except Exception as e:
            return self._fallback_to_minimax(
                text, output_path, voice_type, speed,
                doubao_error=f"豆包TTS调用异常: {str(e)}",
            )

    def _fallback_to_minimax(self, text: str, output_path: Optional[str],
                             voice_type: str, speed: float,
                             doubao_error: str) -> dict:
        """豆包失败时的兜底：使用 MiniMax T2A v2 出音频。

        如果豆包账号没开通某个 _moon_bigtts 大模型音色，会一直 403。
        与其让整支视频缺音频，不如降级到 MiniMax，保证流程能跑完。
        """
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

            if provider in ("minimax", "doubao"):
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

            error_msg = f"不支持的TTS提供商: {provider}（仅支持 minimax / doubao）"
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
                        if isinstance(result, str) and "成功" in result and os.path.exists(output_path):
                            file_size = os.path.getsize(output_path)
                            if file_size < 1024:  # 至少1KB
                                raise Exception(f"生成的音频文件过小 ({file_size} 字节)，可能损坏")

                            logger.info(f"✅ 文本 {i} TTS合成成功: {output_path} ({file_size} 字节)")
                            outputs.append(output_path)
                            results.append({"index": i, "status": "success", "path": output_path})
                            generated_count += 1
                            success = True
                            break
                        elif isinstance(result, str) and "失败" in result:
                            raise Exception(result)
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
        """使用豆包TTS批量合成（原版，保持兼容性）"""
        try:
            from .doubao_tts_tool import DoubaoTTSClient

            # 使用豆包客户端的批量合成功能
            client = DoubaoTTSClient(voice_type=voice_type)
            outputs = client.batch_synthesize(
                text_list=texts,
                output_dir=output_dir,
                filename_template=filename_template,
                speed_ratio=speed,
                encoding=encoding
            )

            successful_count = len([f for f in outputs if f is not None])

            return {
                "success": successful_count > 0,
                "provider": "doubao",
                "outputs": outputs,
                "successful_count": successful_count,
                "total_count": len(texts),
                "message": f"豆包TTS批量合成完成: {successful_count}/{len(texts)} 成功"
            }

        except Exception as e:
            return {
                "success": False,
                "provider": "doubao",
                "error": f"豆包TTS批量合成异常: {str(e)}"
            }


# 提供商注册表，便于管理和扩展
TTS_PROVIDERS = {
    "doubao": {
        "name": "豆包TTS",
        "description": "字节跳动豆包TTS服务",
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

