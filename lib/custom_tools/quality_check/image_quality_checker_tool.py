#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片质量检测工具
使用GLM-4.5V模型分析图片内容,检测异常情况(如动物缺胳膊少腿、多腿等不符合常理的内容)
"""

import os
import base64
from typing import Dict, Any, Type
from pathlib import Path
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from dotenv import load_dotenv
from openai import OpenAI
import json

from src.logger import get_logger

# 加载环境变量
load_dotenv()
logger = get_logger('image_quality_checker')


class ImageQualityCheckerSchema(BaseModel):
    """图片质量检测工具的输入参数"""
    image_path: str = Field(
        ...,
        description="要检测的图片文件路径"
    )
    original_prompt: str = Field(
        default="",
        description="生成图片时使用的原始prompt，用于检测图片是否符合要求"
    )
    check_focus: str = Field(
        default="quality",
        description="检测重点:'quality'(质量检测,默认) 或 'content'(内容分析)"
    )


class ImageQualityCheckerTool(BaseTool):
    """图片质量检测工具

    使用多模态大模型（如 GLM-4.5V 或 Qwen-VL）分析图片内容,检测图片中的异常情况:
    - 生物形态异常(缺胳膊少腿、多余肢体等)
    - 严重的躯干扭曲
    - 内容是否符合原始prompt要求
    """

    name: str = "Image Quality Checker"
    description: str = (
        "使用多模态大模型分析图片质量的工具。"
        "可以检测图片中的异常情况,如:动物缺胳膊少腿、多腿、严重躯干扭曲等。"
        "同时可以结合原始prompt检测图片内容是否符合要求。"
        "返回分析结果和是否需要重新生成的建议。"
    )
    args_schema: Type[BaseModel] = ImageQualityCheckerSchema

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info("🔍 初始化ImageQualityCheckerTool")

    def _run(
        self,
        image_path: str,
        original_prompt: str = "",
        check_focus: str = "quality"
    ) -> Dict[str, Any]:
        """
        执行图片质量检测

        Args:
            image_path: 图片文件路径
            original_prompt: 生成图片时使用的原始prompt
            check_focus: 检测重点

        Returns:
            检测结果字典
        """
        try:
            logger.info(f"🖼️ 开始检测图片质量: {os.path.basename(image_path)}")
            if original_prompt:
                logger.info(f"📝 原始prompt: {original_prompt[:100]}...")

            # 检查文件是否存在
            if not os.path.exists(image_path):
                raise ValueError(f"图片文件不存在: {image_path}")

            # 使用GLM-4.5V分析图片质量
            analysis_result = self._analyze_image_quality(
                image_path,
                original_prompt,
                check_focus
            )

            logger.info(f"✅ 图片质量检测完成")
            return analysis_result

        except Exception as e:
            error_msg = f"图片质量检测失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "has_issues": False,
                "needs_regeneration": False,
                "quality_score": 0,
                "issues": []
            }

    def _analyze_image_quality(
        self,
        image_path: str,
        original_prompt: str,
        check_focus: str
    ) -> Dict[str, Any]:
        """使用GLM-4.5V分析图片质量"""

        # 构建质量检测提示词
        if check_focus == "quality":
            # 如果提供了原始prompt，增强检测逻辑
            if original_prompt:
                prompt = f"""请检查这张图片的质量，原始生成要求是：
"{original_prompt}"

**检查项目**（按优先级排序）：

1. **内容符合性**: 图片内容是否符合原始prompt的要求
   - **重要**: 如果prompt要求"拟人化"动物（anthropomorphic/拟人化的狗/猫等），这些角色应该保持动物外形（如狗的头部、尾巴、毛发），但可以有人类行为（站立、穿衣服、使用手等）。这是正常的，不算内容不符。
   - **真正的内容不符**: 如果prompt要求生成"拟人化的狗"，但图片中出现了完全的真人脸部或人类身体（没有动物特征），这才是严重问题
   - 如果prompt要求的主要元素缺失或被完全替换成其他事物，这是严重问题

2. **数量检测**: 检查图片中角色/物体的数量是否符合prompt要求
   - 如果prompt明确要求"一只狗"、"两个人"、"三只猫"等，检查图片中的数量是否匹配
   - 如果prompt要求"一只金毛犬"但图片中出现了两只或更多狗，这是严重问题
   - 如果prompt要求"妈妈和儿子（两个角色）"但图片中出现了三个或更多人物，这是严重问题
   - 注意区分主角和背景角色：如果prompt明确要求某些角色，只统计这些主角的数量
   - 数量不匹配是严重问题，必须重新生成

3. **形态检测**: 仅检查**非常明显**的畸形问题
   - **多余肢体**: 人物或动物是否有明显多余的腿、手臂等(如3条腿、4只手等)
   - **缺失肢体**: 人物或动物是否明显缺少腿、手臂等主要肢体
   - **严重扭曲**: 躯干或身体是否有非常明显的扭曲变形

**重要提示**:
- **拟人化动物的理解**: 如果prompt要求"拟人化"角色，动物有人类行为（站立、穿衣、使用手）是正常的，不算内容不符。只有当动物特征完全消失、变成真人时才算不符。
- **内容不符和数量不符是最严重的问题**: 如果图片内容与prompt要求不符，或数量不匹配，必须标记为需要重新生成
- **数量检测要准确**: 仔细数清楚图片中符合prompt描述的主要角色/物体数量
- 形态检测标准应该很宽松：只有非常明显、一眼就能看出的畸形才算问题
- 轻微的画面模糊、小的比例问题、轻微的不自然都**不算**问题
- 如果内容符合、数量正确且形态基本正常，就应该判定为无问题
- **默认应该是无问题**，只有看到明显不符、数量错误或畸形才报告

请按照以下JSON格式返回分析结果:
{{
  "has_issues": true/false,
  "needs_regeneration": true/false,
  "quality_score": 1-10,
  "issues": [
    {{
      "type": "内容不符/数量不符/多余肢体/缺失肢体/严重扭曲",
      "severity": "严重/轻微",
      "description": "具体描述问题，如果是数量问题，请说明要求数量和实际数量"
    }}
  ],
  "summary": "检测结果说明"
}}

注意:
- **拟人化角色**: 如果prompt要求"拟人化"角色，保持动物外形但有人类行为（站立/穿衣/使用手）是正常的
- **内容不符和数量不符是最优先判断的问题**，如果发现这些问题，needs_regeneration必须为true
- 只有发现明显的多腿、少腿或严重躯干扭曲时，needs_regeneration才为true
- 如果内容符合、数量正确且没有发现明显畸形，has_issues为false，needs_regeneration为false
- quality_score默认应该给8分以上，除非有明显问题

**请直接返回JSON，不要有任何其他文字说明**"""
            else:
                # 没有prompt时，只检测形态问题
                prompt = """请快速检查这张图片，只关注**非常明显**的畸形问题:

**仅检查以下严重缺陷**:
1. **多余肢体**: 人物或动物是否有明显多余的腿、手臂等(如3条腿、4只手等)
2. **缺失肢体**: 人物或动物是否明显缺少腿、手臂等主要肢体
3. **严重扭曲**: 躯干或身体是否有非常明显的扭曲变形(如身体折成奇怪的角度)

**重要提示**:
- **标准应该很宽松**: 只有非常明显、一眼就能看出的畸形才算问题
- 轻微的画面模糊、小的比例问题、轻微的不自然都**不算**问题
- 如果看起来基本正常，就应该判定为无问题
- 不需要检查画面质量、色彩、光影等
- **默认应该是无问题**，只有看到明显畸形才报告

请按照以下JSON格式返回分析结果:
{
  "has_issues": true/false,
  "needs_regeneration": true/false,
  "quality_score": 1-10,
  "issues": [
    {
      "type": "多余肢体/缺失肢体/严重扭曲",
      "severity": "严重",
      "description": "具体描述问题"
    }
  ],
  "summary": "检测结果说明"
}

注意:
- **只有发现明显的多腿、少腿或严重躯干扭曲时**,needs_regeneration才为true
- 如果没有发现明显畸形,has_issues为false,needs_regeneration为false
- quality_score默认应该给8分以上,除非有明显畸形

**请直接返回JSON，不要有任何其他文字说明**"""
        else:  # content
            prompt = """请分析这张图片的内容,包括:
1. 主要内容和主题
2. 场景描述
3. 人物或物体描述
4. 整体氛围和风格

请以JSON格式返回分析结果。"""

        try:
            # 读取图片并转换为base64
            with open(image_path, "rb") as image_file:
                image_base64 = base64.b64encode(image_file.read()).decode('utf-8')

            # 初始化OpenAI客户端 - 优先使用 GLM_4V 配置，如果没有则使用 MULTIMODAL 配置
            api_key = os.getenv('GLM_4V_API_KEY') or os.getenv('MULTIMODAL_API_KEY')
            base_url = os.getenv('GLM_4V_BASE_URL') or os.getenv('MULTIMODAL_BASE_URL', 'https://api.siliconflow.cn/v1')
            model_name = os.getenv('GLM_4V_MODEL_NAME') or os.getenv('MULTIMODAL_MODEL_NAME', 'Qwen/Qwen2-VL-72B-Instruct')

            if not api_key:
                raise ValueError("请设置环境变量 GLM_4V_API_KEY 或 MULTIMODAL_API_KEY")

            client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )

            logger.info(f"🚀 发送多模态图片质量检测请求...")
            logger.info(f"📁 检测图片路径: {image_path}")
            logger.info(f"🤖 使用模型: {model_name}")

            # 检测图片格式
            image_ext = Path(image_path).suffix.lower()
            mime_type_map = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp',
                '.bmp': 'image/bmp'
            }
            mime_type = mime_type_map.get(image_ext, 'image/jpeg')

            # 调用GLM-4.5V API
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0.3  # 使用较低的温度以获得更稳定的分析结果
            )

            response_text = response.choices[0].message.content
            logger.info(f"✅ 多模态图片质量分析成功,响应长度: {len(response_text)} 字符")

            # 尝试解析JSON响应
            try:
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    cleaned_text = json_match.group(0)
                    parsed_result = json.loads(cleaned_text)
                    logger.info(f"🎯 成功解析多模态分析结果")

                    # 添加成功标记和图片路径
                    parsed_result['success'] = True
                    parsed_result['image_path'] = image_path

                    # 输出分析结果摘要
                    logger.info("="*60)
                    logger.info("📊 图片质量检测结果详情")
                    logger.info("="*60)

                    if parsed_result.get('has_issues', False):
                        logger.warning(f"⚠️ 检测状态: 发现质量问题")
                        logger.warning(f"🔄 需要重新生成: {'是' if parsed_result.get('needs_regeneration', False) else '否'}")
                        logger.warning(f"⭐ 质量分数: {parsed_result.get('quality_score', 0)}/10")

                        issues = parsed_result.get('issues', [])
                        if issues:
                            logger.warning(f"\n📋 问题列表 (共{len(issues)}个):")
                            for idx, issue in enumerate(issues, 1):
                                issue_type = issue.get('type', '未知类型')
                                severity = issue.get('severity', '未知')
                                description = issue.get('description', '')
                                logger.warning(f"  {idx}. [{severity}] {issue_type}")
                                logger.warning(f"     详情: {description}")

                        logger.info(f"\n💬 AI分析总结:")
                        logger.info(f"   {parsed_result.get('summary', '无')}")

                        if parsed_result.get('needs_regeneration', False):
                            logger.error(f"\n❌ 最终判定: 图片质量不合格，建议重新生成")
                        else:
                            logger.info(f"\n✅ 最终判定: 问题较轻微，可以接受")
                    else:
                        logger.info(f"✅ 检测状态: 图片质量良好")
                        logger.info(f"⭐ 质量分数: {parsed_result.get('quality_score', 8)}/10")
                        logger.info(f"💬 AI分析总结: {parsed_result.get('summary', '无问题')}")
                        logger.info(f"✅ 最终判定: 通过质量检查")

                    logger.info("="*60)

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
                        "image_path": image_path
                    }
            except json.JSONDecodeError as e:
                logger.error(f"解析多模态响应JSON失败: {str(e)}")
                return {
                    "success": False,
                    "has_issues": False,
                    "needs_regeneration": False,
                    "quality_score": 0,
                    "issues": [],
                    "summary": response_text,
                    "raw_response": response_text,
                    "parse_error": str(e),
                    "image_path": image_path
                }

        except Exception as e:
            logger.error(f"❌ 多模态图片质量分析请求失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "has_issues": False,
                "needs_regeneration": False,
                "quality_score": 0,
                "issues": [],
                "image_path": image_path
            }
