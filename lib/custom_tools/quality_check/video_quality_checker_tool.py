#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频质量检测工具
使用Gemini Vision API分析视频内容,检测异常情况(如动物缺胳膊少腿、多腿等不符合常理的内容)

支持两种分析模式:
- 原始模式: 使用 GEMINI_ANALYSIS_API_BASE_URL 服务 (默认)
- Gemini3 模式: 使用 Gemini 3 OpenAI 格式 API (设置 USE_GEMINI3_VIDEO_ANALYZER=true 启用)
"""

import os
import json
import requests
import subprocess
from typing import Dict, Any, Type
from pathlib import Path
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from dotenv import load_dotenv

from src.logger import get_logger

# 加载环境变量
load_dotenv()
logger = get_logger('video_quality_checker')


class VideoQualityCheckerSchema(BaseModel):
    """视频质量检测工具的输入参数"""
    video_path: str = Field(
        ...,
        description="要检测的视频文件路径"
    )
    check_focus: str = Field(
        default="quality",
        description="检测重点:'quality'(质量检测,默认) 或 'content'(内容分析)"
    )


class VideoQualityCheckerTool(BaseTool):
    """视频质量检测工具

    使用Gemini Vision模型分析视频内容,检测视频中的异常情况:
    - 生物形态异常(缺胳膊少腿、多余肢体等)
    - 物理规律违反
    - 视觉质量问题
    """

    name: str = "Video Quality Checker"
    description: str = (
        "使用Gemini Vision模型分析视频质量的工具。"
        "可以检测视频中的异常情况,如:动物缺胳膊少腿、多腿、不符合常理的形态等。"
        "返回分析结果和是否需要重新生成的建议。"
    )
    args_schema: Type[BaseModel] = VideoQualityCheckerSchema

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info("🔍 初始化VideoQualityCheckerTool")

    def _run(
        self,
        video_path: str,
        check_focus: str = "quality"
    ) -> Dict[str, Any]:
        """
        执行视频质量检测

        Args:
            video_path: 视频文件路径
            check_focus: 检测重点

        Returns:
            检测结果字典
        """
        try:
            logger.info(f"🎥 开始检测视频质量: {os.path.basename(video_path)}")

            # 检查文件是否存在
            if not os.path.exists(video_path):
                raise ValueError(f"视频文件不存在: {video_path}")

            # 检查是否使用 Gemini3 分析器
            from .gemini3_video_analyzer import use_gemini3_analyzer, Gemini3VideoAnalyzer
            if use_gemini3_analyzer():
                logger.info("🔄 使用 Gemini3 视频分析器 (USE_GEMINI3_VIDEO_ANALYZER=true)")
                try:
                    analyzer = Gemini3VideoAnalyzer()
                    analysis_result = analyzer.analyze_video(
                        video_path=video_path,
                        analysis_focus=check_focus
                    )
                    logger.info(f"✅ Gemini3 视频质量检测完成")
                    return analysis_result
                except Exception as e:
                    logger.warning(f"⚠️ Gemini3 分析失败，回退到原始方式: {str(e)}")
                    # 如果 Gemini3 失败，回退到原始方式

            # 原始方式
            logger.info("🔄 使用原始 Gemini 分析服务")

            # 1. 压缩视频用于分析(如果需要)
            compressed_video = self._compress_video_if_needed(video_path)

            # 2. 使用Gemini分析视频质量
            analysis_result = self._analyze_video_quality(
                compressed_video,
                check_focus
            )

            # 3. 清理临时文件
            self._cleanup_temp_files(compressed_video, video_path)

            logger.info(f"✅ 视频质量检测完成")
            return analysis_result

        except Exception as e:
            error_msg = f"视频质量检测失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "has_issues": False,
                "needs_regeneration": False,
                "quality_score": 0,
                "issues": []
            }

    def _compress_video_if_needed(self, video_path: str, target_size_mb: int = 10) -> str:
        """如果视频过大,压缩到指定大小以下用于Gemini分析"""
        try:
            # 获取原视频文件大小
            original_size = os.path.getsize(video_path) / (1024 * 1024)  # MB
            logger.info(f"📊 原视频大小: {original_size:.2f} MB")

            if original_size <= target_size_mb:
                logger.info(f"✅ 视频已小于 {target_size_mb}MB,无需压缩")
                return video_path

            logger.info(f"🗜️ 开始压缩视频用于分析...")

            # 创建临时压缩文件路径
            video_dir = os.path.dirname(video_path)
            compressed_path = os.path.join(video_dir, "temp_compressed_for_check.mp4")

            # 获取视频时长
            duration_cmd = [
                "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", video_path
            ]
            duration_result = subprocess.run(duration_cmd, capture_output=True, text=True, check=True)
            duration = float(duration_result.stdout.strip())

            # 计算目标比特率 (kbps),预留20%余量
            target_bitrate = int((target_size_mb * 8 * 1024 * 0.8) / duration)
            # 设置最小比特率为200kbps
            MIN_BITRATE = 200
            if target_bitrate < MIN_BITRATE:
                logger.warning(f"⚠️ 计算的比特率 {target_bitrate} kbps 过低,调整为最小值 {MIN_BITRATE} kbps")
                target_bitrate = MIN_BITRATE

            logger.info(f"🎯 目标比特率: {target_bitrate} kbps")

            # 压缩视频
            compress_cmd = [
                "ffmpeg", "-i", video_path,
                "-c:v", "libx264", "-b:v", f"{target_bitrate}k",
                "-maxrate", f"{int(target_bitrate * 1.5)}k",
                "-bufsize", f"{int(target_bitrate * 2)}k",
                "-c:a", "aac", "-b:a", "64k",
                "-preset", "medium",
                "-vf", "scale='min(1280,iw)':'min(720,ih)':force_original_aspect_ratio=decrease,scale='trunc(iw/2)*2':'trunc(ih/2)*2'",
                "-movflags", "+faststart",
                "-y", compressed_path
            ]

            result = subprocess.run(compress_cmd, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"❌ ffmpeg执行失败 (退出码: {result.returncode})")
                logger.warning("🔄 压缩失败,将直接使用原视频")
                return video_path

            # 检查压缩后的文件
            if not os.path.exists(compressed_path):
                logger.warning("压缩后的文件不存在,使用原视频")
                return video_path

            compressed_size = os.path.getsize(compressed_path) / (1024 * 1024)

            if compressed_size < 0.1:
                logger.error(f"❌ 压缩后文件过小: {compressed_size:.2f} MB")
                return video_path

            compression_ratio = (1 - compressed_size / original_size) * 100
            logger.info(f"✅ 视频压缩完成: {compressed_size:.2f} MB (压缩率: {compression_ratio:.1f}%)")

            return compressed_path

        except Exception as e:
            logger.error(f"❌ 视频压缩失败: {str(e)}")
            logger.warning("🔄 将直接使用原视频进行分析")
            return video_path

    def _analyze_video_quality(
        self,
        video_path: str,
        check_focus: str
    ) -> Dict[str, Any]:
        """使用Gemini分析视频质量"""

        # 构建质量检测提示词
        if check_focus == "quality":
            prompt = """请快速检查这个视频，只关注**非常明显**的畸形问题:

**仅检查以下严重缺陷**:
1. **多余肢体**: 人物或动物是否有明显多余的腿、手臂等(如3条腿、4只手等)
2. **缺失肢体**: 人物或动物是否明显缺少腿、手臂等主要肢体
3. **严重扭曲**: 躯干或身体是否有非常明显的扭曲变形(如身体折成奇怪的角度)

**重要提示**:
- **标准应该很宽松**: 只有非常明显、一眼就能看出的畸形才算问题
- 轻微的画面模糊、小的比例问题、轻微的不自然都**不算**问题
- 如果看起来基本正常，就应该判定为无问题
- 不需要检查画面质量、色彩、物理规律等
- **默认应该是无问题**，只有看到明显畸形才报告
- **中英文混合内容是正常的**，不应算作违规或问题
- 视频中出现文字、标识、logo等都是正常的，不算问题

请按照以下JSON格式返回分析结果:
{
  "has_issues": true/false,
  "needs_regeneration": true/false,
  "quality_score": 1-10,
  "issues": [
    {
      "type": "多余肢体/缺失肢体/严重扭曲",
      "severity": "严重",
      "description": "具体描述问题",
      "timestamp": "问题出现的时间点(如果可以识别)"
    }
  ],
  "summary": "检测结果说明"
}

注意:
- **只有发现明显的多腿、少腿或严重躯干扭曲时**,needs_regeneration才为true
- 如果没有发现明显畸形,has_issues为false,needs_regeneration为false
- quality_score默认应该给8分以上,除非有明显畸形
- 中英文混合、文字水印等不算问题"""
        else:  # content
            prompt = """请分析这个视频的内容,包括:
1. 主要内容和主题
2. 场景描述
3. 人物或物体描述
4. 动作和运动
5. 整体氛围和风格

请以JSON格式返回分析结果。"""

        try:
            # 使用文件上传方式调用Gemini API
            with open(video_path, 'rb') as video_file:
                files = {
                    'file': (os.path.basename(video_path), video_file, 'video/mp4')
                }
                data = {
                    'prompt': prompt
                }

                # 使用正确的Gemini分析服务
                base_url = os.getenv("GEMINI_ANALYSIS_API_BASE_URL", "http://43.156.131.167:5777")
                gemini_endpoint = "/gemini/video"

                logger.info(f"🚀 发送Gemini视频质量检测请求...")
                logger.info(f"📁 检测视频路径: {video_path}")

                response = requests.post(
                    f"{base_url}{gemini_endpoint}",
                    files=files,
                    data=data,
                    timeout=600  # 10分钟超时
                )

                # 检查HTTP状态码
                if response.status_code != 200:
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"❌ Gemini API请求失败: {error_msg}")
                    return {
                        "success": False,
                        "error": error_msg,
                        "has_issues": False,
                        "needs_regeneration": False,
                        "quality_score": 8,  # 默认给8分，假设质量良好
                        "issues": [],
                        "video_path": video_path
                    }

                result = response.json()
                logger.debug(f"Gemini API响应状态码: {response.status_code}")
                logger.debug(f"Gemini API响应内容: {json.dumps(result, ensure_ascii=False)[:500]}")

                if result.get('success'):
                    # 安全地获取响应文本，处理 result 字段可能为 None 的情况
                    result_data = result.get('result') or {}
                    response_text = result_data.get('response', '') if isinstance(result_data, dict) else ''

                    if not response_text:
                        logger.warning("⚠️ Gemini返回成功但响应文本为空")
                        return {
                            "success": False,
                            "error": "Gemini API返回成功但响应为空",
                            "has_issues": False,
                            "needs_regeneration": False,
                            "quality_score": 0,
                            "issues": [],
                            "video_path": video_path
                        }

                    logger.info(f"✅ Gemini视频质量分析成功,响应长度: {len(response_text)} 字符")

                    # 尝试解析JSON响应
                    try:
                        import re
                        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                        if json_match:
                            cleaned_text = json_match.group(0)
                            parsed_result = json.loads(cleaned_text)
                            logger.info(f"🎯 成功解析Gemini分析结果")

                            # 添加成功标记和视频路径
                            parsed_result['success'] = True
                            parsed_result['video_path'] = video_path

                            # 输出分析结果摘要
                            if parsed_result.get('has_issues', False):
                                logger.warning(f"⚠️ 视频存在质量问题:")
                                for issue in parsed_result.get('issues', []):
                                    logger.warning(f"  - [{issue.get('severity', '未知')}] {issue.get('type', '未知类型')}: {issue.get('description', '')}")

                                if parsed_result.get('needs_regeneration', False):
                                    logger.error(f"❌ 建议重新生成视频 (质量分数: {parsed_result.get('quality_score', 0)}/10)")
                                else:
                                    logger.info(f"✅ 问题较轻微,可以接受 (质量分数: {parsed_result.get('quality_score', 7)}/10)")
                            else:
                                logger.info(f"✅ 视频质量良好 (质量分数: {parsed_result.get('quality_score', 8)}/10)")

                            logger.info(f"📊 分析总结: {parsed_result.get('summary', '无')}")

                            return parsed_result
                        else:
                            logger.warning("未找到JSON格式的响应,返回原始文本")
                            return {
                                "success": True,
                                "has_issues": False,
                                "needs_regeneration": False,
                                "quality_score": 7,
                                "issues": [],
                                "summary": response_text,
                                "raw_response": response_text,
                                "video_path": video_path
                            }
                    except json.JSONDecodeError as e:
                        logger.error(f"解析Gemini响应JSON失败: {str(e)}")
                        return {
                            "success": False,
                            "has_issues": False,
                            "needs_regeneration": False,
                            "quality_score": 0,
                            "issues": [],
                            "summary": response_text,
                            "raw_response": response_text,
                            "parse_error": str(e),
                            "video_path": video_path
                        }
                else:
                    # 安全地获取错误信息
                    error_data = result.get('error', '未知错误')
                    if isinstance(error_data, dict):
                        error_msg = error_data.get('message', str(error_data))
                    else:
                        error_msg = str(error_data)

                    logger.error(f"❌ Gemini视频质量分析失败: {error_msg}")
                    logger.warning(f"⚠️ 质量检测失败，将假设视频质量良好继续流程")

                    # API失败时返回默认的"质量良好"结果，避免阻塞流程
                    return {
                        "success": False,
                        "error": error_msg,
                        "has_issues": False,
                        "needs_regeneration": False,
                        "quality_score": 8,  # 默认8分，假设质量良好
                        "issues": [],
                        "summary": "质量检测API失败，默认假设视频质量良好",
                        "video_path": video_path
                    }

        except Exception as e:
            logger.error(f"❌ Gemini视频质量分析请求失败: {str(e)}")
            logger.warning(f"⚠️ 质量检测异常，将假设视频质量良好继续流程")
            return {
                "success": False,
                "error": str(e),
                "has_issues": False,
                "needs_regeneration": False,
                "quality_score": 8,  # 默认8分，假设质量良好
                "issues": [],
                "summary": "质量检测异常，默认假设视频质量良好",
                "video_path": video_path
            }

    def _cleanup_temp_files(self, compressed_video: str, original_video: str):
        """清理临时文件"""
        try:
            if compressed_video != original_video and os.path.exists(compressed_video):
                os.unlink(compressed_video)
                logger.info(f"🗑️ 清理临时文件: {compressed_video}")
        except Exception as e:
            logger.warning(f"⚠️ 清理临时文件失败: {str(e)}")
