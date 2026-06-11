#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Whisper歌词提取工具
使用OpenAI Whisper从音频中提取带时间戳的歌词
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from .base_tool_compat import BaseTool
from src.logger import get_logger

logger = get_logger('whisper_lyrics_extractor')


class WhisperLyricsExtractorInput(BaseModel):
    """Whisper歌词提取工具的输入参数"""
    audio_path: str = Field(..., description="音频文件路径（.mp3, .wav等）")
    language: str = Field(default="zh", description="歌词语言（zh: 中文, en: 英文, auto: 自动检测）")
    model_size: str = Field(default="medium", description="Whisper模型大小（tiny, base, small, medium, large）")
    output_format: str = Field(default="lrc", description="输出格式（lrc: LRC歌词格式, json: JSON格式）")
    original_lyrics: Optional[str] = Field(default=None, description="原始歌词（用于对齐修正，可选）")


class WhisperLyricsExtractorTool(BaseTool):
    """
    使用Whisper从音频中提取带时间戳的歌词

    功能：
    1. 从音频文件中识别演唱内容
    2. 输出带时间戳的歌词（LRC或JSON格式）
    3. 如果提供原始歌词，可以进行对齐修正
    """

    name: str = "Whisper歌词提取工具"
    description: str = (
        "使用Whisper从音频中提取带时间戳的歌词。"
        "支持中文、英文等多语言，输出LRC或JSON格式。"
    )
    args_schema: type[BaseModel] = WhisperLyricsExtractorInput

    def _run(
        self,
        audio_path: str,
        language: str = "zh",
        model_size: str = "medium",
        output_format: str = "lrc",
        original_lyrics: Optional[str] = None
    ) -> str:
        """
        执行歌词提取

        Args:
            audio_path: 音频文件路径
            language: 语言代码（zh/en/auto）
            model_size: Whisper模型大小
            output_format: 输出格式（lrc/json）
            original_lyrics: 原始歌词（可选，用于对齐修正）

        Returns:
            处理结果描述字符串
        """
        try:
            logger.info(f"🎵 开始提取歌词: {audio_path}")
            logger.info(f"   语言: {language}, 模型: {model_size}")

            # 检查音频文件
            if not Path(audio_path).exists():
                error_msg = f"音频文件不存在: {audio_path}"
                logger.error(f"❌ {error_msg}")
                return f"❌ 提取失败: {error_msg}"

            # 检查是否安装了whisper
            try:
                import whisper
            except ImportError:
                error_msg = "未安装whisper库，请运行: pip install openai-whisper"
                logger.error(f"❌ {error_msg}")
                return f"❌ 提取失败: {error_msg}"

            # 加载Whisper模型
            logger.info(f"⏳ 加载Whisper模型: {model_size}...")
            model = whisper.load_model(model_size)

            # 转录音频（启用词级时间戳）
            logger.info(f"⏳ 正在转录音频（这可能需要几分钟）...")
            transcribe_options = {
                "word_timestamps": True,
                "verbose": False
            }

            # 只有非auto模式才指定语言
            if language != "auto":
                transcribe_options["language"] = language

            result = model.transcribe(audio_path, **transcribe_options)

            # 提取带时间戳的歌词段落
            lyrics_segments = []
            for segment in result["segments"]:
                lyrics_segments.append({
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": segment["text"].strip()
                })

            logger.info(f"✅ 成功提取 {len(lyrics_segments)} 个歌词段落")

            # 如果提供了原始歌词，进行对齐修正
            if original_lyrics:
                logger.info("🔄 正在对齐原始歌词...")
                lyrics_segments = self._align_with_original_lyrics(
                    lyrics_segments,
                    original_lyrics
                )

            # 生成输出文件
            audio_dir = Path(audio_path).parent
            audio_name = Path(audio_path).stem

            if output_format == "lrc":
                output_path = audio_dir / f"{audio_name}_lyrics.lrc"
                lrc_content = self._generate_lrc(lyrics_segments)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(lrc_content)
                logger.info(f"💾 LRC歌词已保存: {output_path}")
            else:  # json
                output_path = audio_dir / f"{audio_name}_lyrics.json"
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        "audio_path": audio_path,
                        "language": result.get("language", language),
                        "duration": result["segments"][-1]["end"] if result["segments"] else 0,
                        "lyrics_segments": lyrics_segments
                    }, f, ensure_ascii=False, indent=2)
                logger.info(f"💾 JSON歌词已保存: {output_path}")

            # 构建返回信息
            result_msg = f"✅ 歌词提取成功\n"
            result_msg += f"- 音频文件: {audio_path}\n"
            result_msg += f"- 歌词段落数: {len(lyrics_segments)}\n"
            result_msg += f"- 音频时长: {lyrics_segments[-1]['end']:.2f}秒\n"
            result_msg += f"- 输出文件: {output_path}\n"
            result_msg += f"\n歌词预览（前3段）:\n"
            for i, seg in enumerate(lyrics_segments[:3]):
                result_msg += f"  [{self._format_time(seg['start'])} - {self._format_time(seg['end'])}] {seg['text']}\n"

            return result_msg

        except Exception as e:
            error_msg = f"歌词提取失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            import traceback
            logger.error(traceback.format_exc())
            return f"❌ {error_msg}"

    def _align_with_original_lyrics(
        self,
        extracted_segments: List[Dict],
        original_lyrics: str
    ) -> List[Dict]:
        """
        使用原始歌词对齐修正提取的歌词

        这个方法可以修正Whisper识别错误的地方，保留时间戳
        """
        try:
            from difflib import SequenceMatcher

            # 将原始歌词按行分割
            original_lines = [line.strip() for line in original_lyrics.split('\n') if line.strip()]

            # 提取的文本
            extracted_texts = [seg['text'] for seg in extracted_segments]

            # 使用序列匹配算法对齐
            # 这里简化处理：如果段落数量相同，直接替换文本，保留时间戳
            if len(original_lines) == len(extracted_segments):
                logger.info(f"✅ 段落数量匹配，直接对齐")
                for i, line in enumerate(original_lines):
                    extracted_segments[i]['text'] = line
                    extracted_segments[i]['aligned'] = True
            else:
                logger.warning(f"⚠️ 段落数量不匹配（原始:{len(original_lines)}, 提取:{len(extracted_segments)}），使用智能对齐")
                # 这里可以实现更复杂的对齐算法
                # 简化版：使用相似度匹配
                aligned_segments = []
                used_lines = set()

                for seg in extracted_segments:
                    best_match_idx = -1
                    best_ratio = 0.0

                    for i, orig_line in enumerate(original_lines):
                        if i in used_lines:
                            continue
                        ratio = SequenceMatcher(None, seg['text'], orig_line).ratio()
                        if ratio > best_ratio:
                            best_ratio = ratio
                            best_match_idx = i

                    if best_ratio > 0.5 and best_match_idx != -1:
                        seg['text'] = original_lines[best_match_idx]
                        seg['aligned'] = True
                        used_lines.add(best_match_idx)
                    else:
                        seg['aligned'] = False

                    aligned_segments.append(seg)

                extracted_segments = aligned_segments

            return extracted_segments

        except Exception as e:
            logger.warning(f"⚠️ 歌词对齐失败: {str(e)}，使用提取的原始文本")
            return extracted_segments

    def _generate_lrc(self, lyrics_segments: List[Dict]) -> str:
        """生成LRC格式的歌词文件"""
        lrc_lines = []
        lrc_lines.append("[ti:]")
        lrc_lines.append("[ar:]")
        lrc_lines.append("[al:]")
        lrc_lines.append("[by:Whisper Auto-Generated]")
        lrc_lines.append("")

        for seg in lyrics_segments:
            timestamp = self._format_lrc_time(seg['start'])
            lrc_lines.append(f"[{timestamp}]{seg['text']}")

        return '\n'.join(lrc_lines)

    def _format_lrc_time(self, seconds: float) -> str:
        """格式化为LRC时间格式 [mm:ss.xx]"""
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes:02d}:{remaining_seconds:05.2f}"

    def _format_time(self, seconds: float) -> str:
        """格式化时间为可读格式"""
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes:02d}:{remaining_seconds:04.1f}"


# 便捷函数
def extract_lyrics_from_audio(
    audio_path: str,
    language: str = "zh",
    model_size: str = "medium",
    output_format: str = "lrc",
    original_lyrics: Optional[str] = None
) -> Dict[str, Any]:
    """
    从音频中提取带时间戳的歌词（便捷函数）

    Args:
        audio_path: 音频文件路径
        language: 语言代码（zh/en/auto）
        model_size: Whisper模型大小（tiny/base/small/medium/large）
        output_format: 输出格式（lrc/json）
        original_lyrics: 原始歌词文本（可选）

    Returns:
        包含提取结果的字典
    """
    tool = WhisperLyricsExtractorTool()
    result = tool._run(
        audio_path=audio_path,
        language=language,
        model_size=model_size,
        output_format=output_format,
        original_lyrics=original_lyrics
    )

    # 读取生成的JSON文件（如果是json格式）
    if output_format == "json":
        audio_dir = Path(audio_path).parent
        audio_name = Path(audio_path).stem
        json_path = audio_dir / f"{audio_name}_lyrics.json"

        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)

    return {"status": "success", "message": result}
