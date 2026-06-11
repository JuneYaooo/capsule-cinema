#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prompt优化工具
根据图片质量检测的失败原因，智能优化图片生成prompt
"""

import os
from typing import Dict, List
from openai import OpenAI
from dotenv import load_dotenv
from src.logger import get_logger

load_dotenv()
logger = get_logger('prompt_optimizer')


class PromptOptimizer:
    """Prompt优化器"""

    def __init__(self):
        """初始化优化器"""
        # 使用与质量检测相同的API配置
        self.api_key = os.getenv('MULTIMODAL_API_KEY') or os.getenv('GLM_4V_API_KEY')
        self.base_url = os.getenv('MULTIMODAL_BASE_URL') or os.getenv('GLM_4V_BASE_URL', 'https://api.siliconflow.cn/v1')
        self.model_name = os.getenv('MULTIMODAL_MODEL_NAME') or os.getenv('GLM_4V_MODEL_NAME', 'Qwen/Qwen2-VL-72B-Instruct')

        if not self.api_key:
            raise ValueError("请设置环境变量 MULTIMODAL_API_KEY 或 GLM_4V_API_KEY")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

        logger.info(f"🧠 初始化PromptOptimizer，使用模型: {self.model_name}")

    def optimize_prompt(
        self,
        original_prompt: str,
        quality_issues: List[Dict],
        attempt_number: int
    ) -> str:
        """
        根据质量问题优化prompt

        Args:
            original_prompt: 原始prompt
            quality_issues: 质量问题列表，每个问题包含 type 和 description
            attempt_number: 当前是第几次重试（1, 2, ...）

        Returns:
            优化后的prompt
        """
        try:
            # 构建问题描述
            issues_text = "\n".join([
                f"- {issue.get('type', '未知')}: {issue.get('description', '')}"
                for issue in quality_issues
            ])

            # 构建优化请求
            optimization_prompt = f"""你是一个专业的AI图片生成prompt优化专家。

**原始Prompt**：
"{original_prompt}"

**第{attempt_number}次生成失败，检测到以下质量问题**：
{issues_text}

**你的任务**：
请优化这个prompt，使其能够生成符合要求的高质量图片。优化时请注意：

1. **数量问题**: 如果检测到数量不符（如要求1只却生成2只），在prompt中明确强调数量
   - 例如："一只金毛犬" → "只有一只金毛犬，画面中只能出现这一只狗"
   - 例如："两个人" → "恰好两个人，画面中只有这两个角色"

2. **内容不符问题**: 如果生成内容与要求不符，加强关键词和描述
   - 例如：如果要求狗却生成人，强调 "拟人化的狗（保持狗的外形特征，如狗头、狗耳朵、狗尾巴）"
   - 明确排除不想要的元素："不要出现人类"

3. **形态问题**: 如果出现多余或缺失肢体，强调正确的身体结构
   - 例如："四只腿，两只前腿和两只后腿"
   - 例如："两只手臂，一左一右"

4. **保持原意**: 不要改变原prompt的核心内容和风格要求
5. **简洁明确**: 优化后的prompt应该更具体、更明确，但不要过于冗长

**请直接返回优化后的prompt，不要有任何额外说明**。
"""

            logger.info(f"🧠 开始优化prompt（第{attempt_number}次重试）...")
            logger.debug(f"原始prompt: {original_prompt}")
            logger.debug(f"质量问题: {issues_text}")

            # 调用LLM优化
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": optimization_prompt
                    }
                ],
                max_tokens=1000,
                temperature=0.7
            )

            optimized_prompt = response.choices[0].message.content.strip()

            # 移除可能的引号包裹
            if optimized_prompt.startswith('"') and optimized_prompt.endswith('"'):
                optimized_prompt = optimized_prompt[1:-1]
            elif optimized_prompt.startswith("'") and optimized_prompt.endswith("'"):
                optimized_prompt = optimized_prompt[1:-1]

            logger.info(f"✅ Prompt优化完成")
            logger.info(f"📝 优化后prompt: {optimized_prompt}")

            return optimized_prompt

        except Exception as e:
            logger.error(f"❌ Prompt优化失败: {str(e)}")
            logger.warning(f"⚠️ 将使用原始prompt重试")
            return original_prompt
