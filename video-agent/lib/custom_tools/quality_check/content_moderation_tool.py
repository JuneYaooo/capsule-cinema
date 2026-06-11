from typing import Any, Type, Optional, Dict, ClassVar
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
import os
import json
import re
from openai import OpenAI

from src.logger import get_logger

logger = get_logger("content_moderation_tool")

# 延迟初始化 OpenAI 客户端（避免模块导入时报错）
_moderation_client = None
moderation_temperature = 0.3


def get_moderation_client():
    """延迟获取 OpenAI 客户端"""
    global _moderation_client
    if _moderation_client is None:
        _moderation_client = OpenAI(
            api_key=os.getenv('MODERATION_API_KEY', os.getenv('CREW_API_KEY')),
            base_url=os.getenv('MODERATION_BASE_URL', os.getenv('CREW_BASE_URL'))
        )
    return _moderation_client


def get_moderation_model():
    """获取审核模型名称"""
    return os.getenv('MODERATION_MODEL_NAME', os.getenv('CREW_MODEL_NAME'))


def get_moderation_max_tokens():
    """获取最大 token 数"""
    return int(os.getenv('MODERATION_MAX_TOKEN', '4000'))



class ContentModerationSchema(BaseModel):
    """Input for ContentModerationTool."""
    prompt: str = Field(..., description="需要检测和可能重写的提示词内容")
    error_message: Optional[str] = Field(None, description="来自API的错误消息(如果有)，用于辅助判断违规类型")
    content_type: str = Field("video", description="内容类型: image | video | text")


class ContentModerationTool(BaseTool):
    name: str = "AI content moderation and prompt rewriting"
    description: str = (
        "使用大模型检测提示词中的违规内容，并智能重写以符合内容政策。"
        "适用于处理图片生成、视频生成等场景中的违规提示词问题。"
        "完全由AI驱动，不使用任何规则。"
    )
    args_schema: Type[BaseModel] = ContentModerationSchema

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info("初始化ContentModerationTool - 纯AI驱动模式")
    
    def _parse_json_response(self, response: str) -> dict:
        """
        解析大模型返回的JSON响应（支持多种格式）
        
        Args:
            response: 大模型返回的响应文本
            
        Returns:
            解析后的字典对象
        """
        # 如果已经是字典，直接返回
        if isinstance(response, dict):
            return response
        
        # 转换为字符串
        response_str = str(response).strip()
        
        try:
            # 尝试直接解析JSON
            return json.loads(response_str)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 ```json ... ``` 代码块
        json_code_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_str)
        if json_code_match:
            try:
                return json.loads(json_code_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # 尝试提取 {...} JSON对象
        json_obj_match = re.search(r'\{[\s\S]*\}', response_str)
        if json_obj_match:
            try:
                return json.loads(json_obj_match.group(0))
            except json.JSONDecodeError:
                pass
        
        # 如果所有尝试都失败，记录错误并返回默认值
        logger.error(f"JSON解析失败，原始响应: {response_str[:200]}...")
        return {
            "is_violation": False,
            "violation_reasons": [],
            "rewritten_prompt": ""
        }

    def _run(
        self,
        prompt: str,
        error_message: Optional[str] = None,
        content_type: str = "video"
    ) -> Any:
        """
        使用AI检测并重写违规提示词（纯AI驱动，无规则）

        Args:
            prompt: 原始提示词
            error_message: API返回的错误消息
            content_type: 内容类型

        Returns:
            Dict包含:
                - is_violation: 是否违规
                - original_prompt: 原始提示词
                - rewritten_prompt: 重写后的提示词
                - violation_reasons: 违规原因列表
                - success: 是否成功
        """
        logger.info(f"🤖 AI内容审核 - 内容类型: {content_type}")
        
        # 显示原始提示词
        logger.info("=" * 60)
        logger.info("📝 原始提示词:")
        logger.info(f"   {prompt[:200]}{'...' if len(prompt) > 200 else ''}")
        logger.info("=" * 60)
        
        if error_message:
            # 直接显示错误信息（已经是清理过的）
            logger.info(f"⚠️  API错误: {error_message[:500]}{'...' if len(error_message) > 500 else ''}")

        try:
            # 构建简洁的系统提示词 - 让AI自己判断
            system_prompt = f"""你是内容安全专家。请检查并重写AI生成{content_type}的提示词，确保符合OpenAI内容政策。

**主要违规类型**:
1. 品牌推广：任何具体品牌名、logo、商标、公司名（如蜜雪冰城、Mixue、Starbucks等）
2. 暴力内容：血腥、暴力、武器、死亡等描述
3. 中英文混合：中文和英文单词混在一起（如"focuses on两人"）
4. 其他：色情、恐怖、敏感政治等

**重写原则**:
- 品牌名 → 通用名词（"蜜雪冰城" → "奶茶店"，"Mixue logo" → "shop decoration"）
- 暴力词 → 温和表达（"血" → "泪"，"杀" → "离开"）
- 中英混合 → 纯英文或纯中文
- 保留故事核心和情感，只改违规内容

请返回JSON格式:
{{
    "is_violation": true/false,
    "violation_reasons": "具体违规类型和词汇",
    "rewritten_prompt": "安全优化后的提示词"
}}

重要提示：
1. 无论是否检测到违规，rewritten_prompt字段必须始终返回一个优化后的安全提示词
2. 如果没有违规，也要对提示词进行优化，确保描述更安全、更符合政策
3. 避开一切可能引起争议的描述，即使它们看起来不明显违规"""

            user_content = f"提示词: {prompt}"
            if error_message:
                user_content += f"\n\n错误信息: {error_message}\n\n这个提示词导致API失败，请仔细检查并重写。"

            # 调用AI大模型
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]

            logger.info("📡 调用AI大模型检测...")

            completion = get_moderation_client().chat.completions.create(
                model=get_moderation_model(),
                messages=messages,
                temperature=moderation_temperature,
                max_tokens=get_moderation_max_tokens(),
                response_format={"type": "json_object"}
            )
            
            response_content = completion.choices[0].message.content
            result = self._parse_json_response(response_content)

            is_violation = result.get("is_violation", False)
            violation_reasons = result.get("violation_reasons", [])
            rewritten_prompt = result.get("rewritten_prompt", prompt).strip()

            # 移除可能的引号包裹
            if rewritten_prompt.startswith('"') and rewritten_prompt.endswith('"'):
                rewritten_prompt = rewritten_prompt[1:-1]
            elif rewritten_prompt.startswith("'") and rewritten_prompt.endswith("'"):
                rewritten_prompt = rewritten_prompt[1:-1]

            # 显示对比结果
            if is_violation:
                logger.warning(f"⚠️  AI检测到违规: {', '.join(violation_reasons)}")
                logger.info("=" * 60)
                logger.info("✅ AI重写后的提示词:")
                logger.info(f"   {rewritten_prompt}")
                logger.info("=" * 60)
                logger.info("📊 对比:")
                logger.info(f"   原始长度: {len(prompt)} 字符")
                logger.info(f"   重写长度: {len(rewritten_prompt)} 字符")
                logger.info("=" * 60)
                
                return {
                    "is_violation": True,
                    "original_prompt": prompt,
                    "rewritten_prompt": rewritten_prompt,
                    "violation_reasons": violation_reasons,
                    "success": True
                }
            else:
                # 即使没有检测到明显违规，也使用AI优化后的提示词
                logger.info("✅ AI检测通过，使用优化后的提示词")
                logger.info("=" * 60)
                logger.info("✅ AI优化后的提示词:")
                logger.info(f"   {rewritten_prompt}")
                logger.info("=" * 60)
                logger.info("📊 对比:")
                logger.info(f"   原始长度: {len(prompt)} 字符")
                logger.info(f"   优化长度: {len(rewritten_prompt)} 字符")
                logger.info("=" * 60)
                
                return {
                    "is_violation": False,
                    "original_prompt": prompt,
                    "rewritten_prompt": rewritten_prompt,  # 使用AI重写后的版本
                    "violation_reasons": [],
                    "success": True
                }

        except Exception as e:
            logger.error(f"❌ AI审核失败: {str(e)}")
            return {
                "is_violation": False,
                "original_prompt": prompt,
                "rewritten_prompt": prompt,
                "violation_reasons": [],
                "success": False,
                "error": str(e)
            }


class BatchContentModerationSchema(BaseModel):
    """Input for BatchContentModerationTool."""
    prompts: list = Field(..., description="需要批量检测的提示词列表，每项可以是字符串或包含prompt字段的字典")
    content_type: str = Field("video", description="内容类型: image | video | text")


class BatchContentModerationTool(BaseTool):
    name: str = "Batch AI content moderation and prompt rewriting"
    description: str = (
        "批量检测和重写多个提示词的违规内容，提高处理效率。"
        "返回每个提示词的检测和重写结果。"
    )
    args_schema: Type[BaseModel] = BatchContentModerationSchema

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info("初始化BatchContentModerationTool")

    def _run(
        self,
        prompts: list,
        content_type: str = "video"
    ) -> Any:
        """
        批量检测并重写违规提示词

        Returns:
            Dict包含:
                - results: List[Dict] 每个提示词的处理结果
                - summary: Dict 统计摘要
        """
        logger.info(f"📋 开始批量违规检测 - 提示词数量: {len(prompts)}")

        results = []
        violation_count = 0
        rewrite_success_count = 0
        rewrite_failed_count = 0

        single_tool = ContentModerationTool()

        for i, item in enumerate(prompts):
            # 支持字符串或字典格式
            if isinstance(item, str):
                prompt = item
                index = i
            elif isinstance(item, dict):
                prompt = item.get("prompt", item.get("video_prompt", item.get("image_prompt", "")))
                index = item.get("index", i)
            else:
                logger.warning(f"跳过无效的提示词项: {item}")
                continue

            if not prompt:
                logger.warning(f"跳过空提示词 (索引: {index})")
                continue

            logger.info(f"🔍 处理提示词 {index + 1}/{len(prompts)}")

            result = single_tool._run(
                prompt=prompt,
                content_type=content_type
            )

            result["index"] = index
            results.append(result)

            if result.get("is_violation", False):
                violation_count += 1
                if result.get("success", False):
                    rewrite_success_count += 1
                else:
                    rewrite_failed_count += 1

        summary = {
            "total": len(prompts),
            "violations": violation_count,
            "clean": len(prompts) - violation_count,
            "rewrite_success": rewrite_success_count,
            "rewrite_failed": rewrite_failed_count
        }

        logger.info(f"✅ 批量检测完成 - 违规: {violation_count}/{len(prompts)}, "
                   f"重写成功: {rewrite_success_count}, 重写失败: {rewrite_failed_count}")

        return {
            "results": results,
            "summary": summary
        }
