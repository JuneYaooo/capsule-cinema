#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini视频质量分析工具
使用Gemini Vision API分析视频内容，检测异常情况（如动物缺胳膊少腿、多腿等不符合常理的内容）

支持两种分析模式:
- 原始模式: 使用 VIDEO_ANALYSIS_* API (默认)
- Gemini3 模式: 使用 Gemini 3 OpenAI 格式 API (设置 USE_GEMINI3_VIDEO_ANALYZER=true 启用)
"""

import os
import base64
import requests
import json
from typing import Dict, Any, Type, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from pathlib import Path

from src.logger import get_logger

# 加载环境变量
load_dotenv()
logger = get_logger('gemini_video_analyzer')


class GeminiVideoAnalyzerSchema(BaseModel):
    """Gemini视频分析工具的输入参数"""
    video_path: str = Field(
        ...,
        description="要分析的视频文件路径"
    )
    analysis_focus: str = Field(
        default="quality",
        description="分析重点：'quality'（质量检测）或 'content'（内容分析）"
    )


class GeminiVideoAnalyzerTool(BaseTool):
    name: str = "Gemini视频质量分析工具"
    description: str = (
        "使用Gemini Vision模型分析视频内容的工具。"
        "可以检测视频中的异常情况，如：动物缺胳膊少腿、多腿、不符合常理的形态等。"
        "返回分析结果和是否需要重新生成的建议。"
    )
    args_schema: Type[BaseModel] = GeminiVideoAnalyzerSchema

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _run(
        self,
        video_path: str,
        analysis_focus: str = "quality"
    ) -> Dict[str, Any]:
        """
        执行Gemini视频分析

        Args:
            video_path: 视频文件路径
            analysis_focus: 分析重点

        Returns:
            分析结果字典
        """
        try:
            # 检查是否使用 Gemini3 分析器
            from custom_tools.quality_check.gemini3_video_analyzer import use_gemini3_analyzer, Gemini3VideoAnalyzer
            if use_gemini3_analyzer():
                logger.info("🔄 使用 Gemini3 视频分析器 (USE_GEMINI3_VIDEO_ANALYZER=true)")
                try:
                    analyzer = Gemini3VideoAnalyzer()
                    result = analyzer.analyze_video(
                        video_path=video_path,
                        analysis_focus=analysis_focus
                    )
                    return result
                except Exception as e:
                    logger.warning(f"⚠️ Gemini3 分析失败，回退到原始方式: {str(e)}")
                    # 如果 Gemini3 失败，回退到原始方式

            # 原始方式：初始化原始 Gemini 视频分析器
            logger.info("🔄 使用原始 Gemini 视频分析器")
            analyzer = GeminiVideoAnalyzer()

            # 执行分析
            result = analyzer.analyze_video(
                video_path=video_path,
                analysis_focus=analysis_focus
            )

            return result

        except Exception as e:
            logger.error(f"❌ Gemini视频分析失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "needs_regeneration": False,
                "quality_score": 0,
                "issues": []
            }


class GeminiVideoAnalyzer:
    """使用Gemini Vision模型分析视频的分析器"""

    def __init__(self):
        """初始化Gemini视频分析器"""
        self.base_url = os.getenv("VIDEO_ANALYSIS_BASE_URL")
        self.api_key = os.getenv("VIDEO_ANALYSIS_API_KEY")
        self.model_name = os.getenv("VIDEO_ANALYSIS_MODEL_NAME", "gemini-1.5-pro")

        if not self.base_url or not self.api_key:
            raise ValueError("请设置环境变量 VIDEO_ANALYSIS_BASE_URL 和 VIDEO_ANALYSIS_API_KEY")

        logger.info(f"🔍 初始化Gemini视频分析器 (模型: {self.model_name})")

    def _encode_video_to_base64(self, video_path: str) -> str:
        """将视频文件编码为base64格式"""
        try:
            with open(video_path, "rb") as video_file:
                return base64.b64encode(video_file.read()).decode('utf-8')
        except Exception as e:
            raise Exception(f"编码视频失败: {str(e)}")

    def _get_video_mime_type(self, video_path: str) -> str:
        """获取视频的MIME类型"""
        video_ext = Path(video_path).suffix.lower()
        mime_type_map = {
            '.mp4': 'video/mp4',
            '.mov': 'video/quicktime',
            '.avi': 'video/x-msvideo',
            '.webm': 'video/webm'
        }
        return mime_type_map.get(video_ext, 'video/mp4')

    def _build_analysis_prompt(self, analysis_focus: str) -> str:
        """构建视频分析的提示词"""
        if analysis_focus == "quality":
            return """请仔细分析这个视频，重点检查以下质量问题：

1. **生物形态异常**：
   - 人物或动物是否缺少身体部位（如缺胳膊、少腿、缺手指等）
   - 人物或动物是否有多余的身体部位（如多腿、多手臂等）
   - 身体比例是否严重失调或扭曲
   - 五官是否异常或位置错误

2. **物理规律违反**：
   - 物体是否违反重力或物理规律
   - 运动是否不自然或突兀
   - 物体是否穿模或重叠

3. **视觉质量问题**：
   - 画面是否模糊或扭曲
   - 是否有明显的瑕疵或伪影
   - 色彩是否异常

请按照以下JSON格式返回分析结果：
{
  "has_issues": true/false,
  "needs_regeneration": true/false,
  "quality_score": 1-10,
  "issues": [
    {
      "type": "形态异常/物理违反/视觉质量",
      "severity": "严重/中等/轻微",
      "description": "具体描述问题",
      "timestamp": "问题出现的时间点（如果可以识别）"
    }
  ],
  "summary": "整体质量评价"
}

注意：
- 如果有**严重**的形态异常（如缺胳膊少腿、多余肢体等），needs_regeneration应该为true
- quality_score: 10分最高，1分最低
- 如果视频质量良好，无明显问题，has_issues为false，needs_regeneration为false"""
        else:  # content analysis
            return """请分析这个视频的内容，包括：
1. 主要内容和主题
2. 场景描述
3. 人物或物体描述
4. 动作和运动
5. 整体氛围和风格

请以JSON格式返回分析结果。"""

    def _send_request(self, video_base64: str, mime_type: str, prompt: str) -> Dict[str, Any]:
        """发送请求到Gemini API进行视频分析"""
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }

            # 构建请求数据
            data = {
                "model": self.model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "video_url",
                                "video_url": {
                                    "url": f"data:{mime_type};base64,{video_base64}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 2000,
                "temperature": 0.3  # 使用较低的温度以获得更稳定的分析结果
            }

            # 确保URL正确
            url = f"{self.base_url.rstrip('/')}/v1/chat/completions"
            if "/v1/v1/" in url:
                url = url.replace("/v1/v1/", "/v1/")

            logger.info(f"🔗 发送视频分析请求到Gemini API: {url}")

            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=300  # 5分钟超时
            )

            logger.info(f"📥 收到响应，状态码: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"API请求失败，状态码: {response.status_code}")
                logger.error(f"响应内容: {response.text}")
                response.raise_for_status()

            result = response.json()

            # 提取响应内容
            if 'choices' in result and result['choices']:
                content = result['choices'][0]['message']['content']
                logger.info(f"📝 Gemini API 响应内容: {content[:200]}...")

                # 尝试解析JSON格式的响应
                try:
                    # 提取JSON部分
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', content)
                    if json_match:
                        analysis_result = json.loads(json_match.group())
                        return analysis_result
                    else:
                        # 如果没有找到JSON，返回原始文本
                        return {
                            "success": True,
                            "has_issues": False,
                            "needs_regeneration": False,
                            "quality_score": 7,
                            "issues": [],
                            "summary": content,
                            "raw_response": content
                        }
                except json.JSONDecodeError:
                    logger.warning("无法解析JSON响应，返回原始文本")
                    return {
                        "success": True,
                        "has_issues": False,
                        "needs_regeneration": False,
                        "quality_score": 7,
                        "issues": [],
                        "summary": content,
                        "raw_response": content
                    }
            else:
                logger.error(f"❌ Gemini API 响应格式异常: {result}")
                raise ValueError("Gemini API 响应格式异常")

        except requests.RequestException as e:
            logger.error(f"Gemini API 请求失败: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Gemini API 处理失败: {str(e)}")
            raise

    def analyze_video(self, video_path: str, analysis_focus: str = "quality") -> Dict[str, Any]:
        """
        分析视频质量和内容

        Args:
            video_path: 视频文件路径
            analysis_focus: 分析重点

        Returns:
            分析结果字典
        """
        if not os.path.exists(video_path):
            raise ValueError(f"视频文件不存在: {video_path}")

        try:
            logger.info(f"🎥 开始分析视频: {os.path.basename(video_path)}")

            # 编码视频
            logger.info("📦 编码视频文件...")
            video_base64 = self._encode_video_to_base64(video_path)
            mime_type = self._get_video_mime_type(video_path)

            # 构建提示词
            prompt = self._build_analysis_prompt(analysis_focus)

            # 发送请求
            logger.info("🔍 发送分析请求...")
            result = self._send_request(video_base64, mime_type, prompt)

            # 确保结果包含必要字段
            result['success'] = True
            result['video_path'] = video_path

            # 输出分析结果
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

            return result

        except Exception as e:
            logger.error(f"❌ 视频分析失败: {str(e)}")
            raise
