#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini 3 视频分析工具
使用 Gemini 3 (OpenAI 格式) 分析视频内容，检测异常情况
支持通过环境变量 USE_GEMINI3_VIDEO_ANALYZER 切换使用新的 Gemini3 分析方式
"""

import os
import base64
import json
from typing import Dict, Any, Type, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from pathlib import Path
from openai import OpenAI

from src.logger import get_logger

# 加载环境变量
load_dotenv()
logger = get_logger('gemini3_video_analyzer')


def _video_analysis_timeout_seconds() -> float:
    raw = os.getenv("VIDEO_ANALYSIS_TIMEOUT_SECONDS", "180")
    try:
        timeout = float(raw)
    except (TypeError, ValueError):
        logger.warning(f"⚠️ VIDEO_ANALYSIS_TIMEOUT_SECONDS 无效: {raw!r}，使用默认 180 秒")
        return 180.0
    if timeout <= 0:
        logger.warning(f"⚠️ VIDEO_ANALYSIS_TIMEOUT_SECONDS 必须大于 0: {raw!r}，使用默认 180 秒")
        return 180.0
    return timeout


def _analysis_failure_result(error: Exception | str, video_path: str) -> Dict[str, Any]:
    error_text = str(error)
    return {
        "success": False,
        "error": error_text,
        "has_issues": True,
        "needs_regeneration": False,
        "needs_review": True,
        "quality_score": 0,
        "issues": [
            {
                "id": "video_analysis_unavailable",
                "type": "分析失败",
                "severity": "blocker",
                "description": error_text,
            }
        ],
        "summary": "分析失败，不能默认判定视频质量良好，需要人工或备用多模态复核",
        "video_path": video_path,
    }


class Gemini3VideoAnalyzerSchema(BaseModel):
    """Gemini3 视频分析工具的输入参数"""
    video_path: str = Field(
        ...,
        description="要分析的视频文件路径"
    )
    prompt: str = Field(
        default="请详细描述这个视频的内容",
        description="分析提示词"
    )
    analysis_focus: str = Field(
        default="quality",
        description="分析重点：'quality'（质量检测）或 'content'（内容分析）"
    )


class Gemini3VideoAnalyzer:
    """使用 Gemini 3 (OpenAI 格式) 分析视频的分析器"""

    def __init__(self):
        """初始化 Gemini3 视频分析器"""
        # 从环境变量读取配置
        self.api_key = os.getenv('GEMINI3_API_KEY')
        self.base_url = os.getenv('GEMINI3_BASE_URL', 'https://liu-api.fun/v1')
        model_name_raw = os.getenv('GEMINI3_MODEL_NAME', 'gemini-3-pro-preview-pc')
        # 支持逗号分隔的多模型名，按顺序尝试
        self.model_names = [m.strip() for m in model_name_raw.split(',') if m.strip()]
        self.timeout_seconds = _video_analysis_timeout_seconds()

        if not self.api_key:
            raise ValueError("请设置环境变量 GEMINI3_API_KEY")

        logger.info(f"🔍 初始化 Gemini3 视频分析器")
        logger.info(f"   API URL: {self.base_url}")
        logger.info(f"   模型列表: {self.model_names}")
        logger.info(f"   请求超时: {self.timeout_seconds:g} 秒")

    def _encode_video_to_base64(self, video_path: str) -> str:
        """将视频文件编码为 base64"""
        try:
            with open(video_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            raise Exception(f"编码视频失败: {str(e)}")

    def _get_video_mime_type(self, video_path: str) -> str:
        """获取视频的 MIME 类型"""
        video_ext = Path(video_path).suffix.lower()
        mime_type_map = {
            '.mp4': 'video/mp4',
            '.mov': 'video/quicktime',
            '.avi': 'video/x-msvideo',
            '.webm': 'video/webm',
            '.mkv': 'video/x-matroska'
        }
        return mime_type_map.get(video_ext, 'video/mp4')

    def _build_quality_check_prompt(self) -> str:
        """构建质量检测提示词"""
        return """请快速检查这个视频，只关注**非常明显**的畸形问题:

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

    def _build_content_analysis_prompt(self) -> str:
        """构建内容分析提示词"""
        return """请分析这个视频的内容,包括:
1. 主要内容和主题
2. 场景描述
3. 人物或物体描述
4. 动作和运动
5. 整体氛围和风格

请以JSON格式返回分析结果。"""

    def analyze_video(
        self,
        video_path: str,
        prompt: Optional[str] = None,
        analysis_focus: str = "quality"
    ) -> Dict[str, Any]:
        """
        分析视频质量和内容

        Args:
            video_path: 视频文件路径
            prompt: 自定义提示词（可选）
            analysis_focus: 分析重点 'quality' 或 'content'

        Returns:
            分析结果字典
        """
        if not os.path.exists(video_path):
            raise ValueError(f"视频文件不存在: {video_path}")

        try:
            logger.info(f"🎥 开始使用 Gemini3 分析视频: {os.path.basename(video_path)}")

            # 编码视频
            file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
            logger.info(f"📦 正在编码视频文件... (大小: {file_size_mb:.2f} MB)")
            video_base64 = self._encode_video_to_base64(video_path)
            logger.info(f"✅ 视频编码完成，base64 大小: {len(video_base64) / 1024 / 1024:.2f} MB")

            # 确定使用的提示词
            if prompt:
                analysis_prompt = prompt
            elif analysis_focus == "quality":
                analysis_prompt = self._build_quality_check_prompt()
            else:
                analysis_prompt = self._build_content_analysis_prompt()

            # 创建 OpenAI 客户端
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout_seconds,
            )

            # 获取 MIME 类型
            mime_type = self._get_video_mime_type(video_path)

            # 按顺序尝试每个模型
            last_error = None
            for i, model_name in enumerate(self.model_names):
                try:
                    logger.info(f"🚀 尝试模型 [{i+1}/{len(self.model_names)}]: {model_name}")

                    # 调用 API
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:{mime_type};base64,{video_base64}"
                                        }
                                    },
                                    {
                                        "type": "text",
                                        "text": analysis_prompt
                                    }
                                ]
                            }
                        ],
                        max_tokens=4096
                    )

                    response_text = response.choices[0].message.content
                    logger.info(f"✅ 模型 {model_name} 分析完成，响应长度: {len(response_text)} 字符")

                    # 尝试解析 JSON 响应
                    result = self._parse_response(response_text, video_path)

                    # 输出分析结果
                    self._log_analysis_result(result)

                    return result

                except Exception as e:
                    last_error = e
                    logger.warning(f"⚠️ 模型 {model_name} 失败: {str(e)}")
                    if i < len(self.model_names) - 1:
                        logger.info(f"🔄 尝试下一个模型...")
                    continue

            # 所有模型都失败了
            raise last_error or Exception("所有模型均失败")

        except Exception as e:
            logger.error(f"❌ Gemini3 视频分析失败: {str(e)}")
            return _analysis_failure_result(e, video_path)

    def _parse_response(self, response_text: str, video_path: str) -> Dict[str, Any]:
        """解析 API 响应"""
        import re
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                cleaned_text = json_match.group(0)
                parsed_result = json.loads(cleaned_text)
                logger.info(f"🎯 成功解析 Gemini3 分析结果")

                # 添加成功标记和视频路径
                parsed_result['success'] = True
                parsed_result['video_path'] = video_path

                return parsed_result
            else:
                logger.warning("未找到 JSON 格式的响应，返回原始文本")
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
            logger.error(f"解析 JSON 响应失败: {str(e)}")
            return {
                "success": False,
                "has_issues": False,
                "needs_regeneration": False,
                "quality_score": 7,
                "issues": [],
                "summary": response_text,
                "raw_response": response_text,
                "parse_error": str(e),
                "video_path": video_path
            }

    def _log_analysis_result(self, result: Dict[str, Any]) -> None:
        """输出分析结果日志"""
        if result.get('has_issues', False):
            logger.warning(f"⚠️ 视频存在质量问题:")
            for issue in result.get('issues', []):
                logger.warning(f"  - [{issue.get('severity', '未知')}] {issue.get('type', '未知类型')}: {issue.get('description', '')}")

            if result.get('needs_regeneration', False):
                logger.error(f"❌ 建议重新生成视频 (质量分数: {result.get('quality_score', 0)}/10)")
            else:
                logger.info(f"✅ 问题较轻微，可以接受 (质量分数: {result.get('quality_score', 7)}/10)")
        else:
            logger.info(f"✅ 视频质量良好 (质量分数: {result.get('quality_score', 8)}/10)")

        logger.info(f"📊 分析总结: {result.get('summary', '无')}")


class Gemini3VideoAnalyzerTool(BaseTool):
    """Gemini3 视频分析工具"""
    name: str = "Gemini3视频分析工具"
    description: str = (
        "使用 Gemini 3 模型分析视频内容的工具。"
        "可以检测视频中的异常情况，如：动物缺胳膊少腿、多腿、不符合常理的形态等。"
        "返回分析结果和是否需要重新生成的建议。"
    )
    args_schema: Type[BaseModel] = Gemini3VideoAnalyzerSchema

    def _run(
        self,
        video_path: str,
        prompt: str = "请详细描述这个视频的内容",
        analysis_focus: str = "quality"
    ) -> Dict[str, Any]:
        """
        执行 Gemini3 视频分析

        Args:
            video_path: 视频文件路径
            prompt: 自定义提示词
            analysis_focus: 分析重点

        Returns:
            分析结果字典
        """
        try:
            # 初始化 Gemini3 视频分析器
            analyzer = Gemini3VideoAnalyzer()

            # 执行分析
            result = analyzer.analyze_video(
                video_path=video_path,
                prompt=prompt if prompt != "请详细描述这个视频的内容" else None,
                analysis_focus=analysis_focus
            )

            return result

        except Exception as e:
            logger.error(f"❌ Gemini3 视频分析失败: {str(e)}")
            return _analysis_failure_result(e, video_path)


def use_gemini3_analyzer() -> bool:
    """检查是否应该使用 Gemini3 视频分析器"""
    env_value = os.getenv('USE_GEMINI3_VIDEO_ANALYZER', 'false').lower()
    return env_value in ('true', '1', 'yes', 'on')
