#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
参考图生成工具
实现优化的参考图生成策略：先生成风格图和物体图，再生成角色图
"""

import re
from typing import Dict, List, Optional
from pathlib import Path
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from src.logger import get_logger

logger = get_logger('reference_image_tool')


class ReferenceImageInput(BaseModel):
    """参考图生成输入模型"""
    reference_design: Dict = Field(..., description="参考设计数据")
    output_dir: str = Field(..., description="输出目录")
    aspect_ratio: str = Field(default='9:16', description="宽高比")
    engine: str = Field(default='seedream5', description="图片生成引擎")


class ReferenceImageGenerator:
    """参考图生成器

    优化的生成顺序：
    1. 先生成风格参考图（文生图）
    2. 生成物体参考图（文生图，可基于风格图）
    3. 生成第一个角色图（文生图 + visual_style prompt 控制风格）
    4. 生成剩余角色图（基于角色1图生图 + visual_style prompt 控制风格）

    角色图不使用风格参考图作为图生图输入，而是通过 visual_style YAML 配置
    在 prompt 中添加风格关键词前缀来控制风格，与场景图生成保持一致。
    """

    # 定义需要使用中文提示词的引擎
    CHINESE_PROMPT_ENGINES = {'seedream5', 'gemini3_pro'}
    # 定义需要使用英文提示词的引擎
    ENGLISH_PROMPT_ENGINES = set()

    def __init__(self):
        """初始化参考图生成器"""
        # 延迟导入，避免循环依赖
        from custom_tools.image_generation import GenerateSceneImageTool
        self.image_tool = GenerateSceneImageTool()

    def _add_style_guidance(self, image_prompt: str, engine: str, guidance_type: str = 'simple') -> str:
        """为提示词添加风格指导

        Args:
            image_prompt: 原始提示词
            engine: 图片生成引擎
            guidance_type: 指导类型，'simple'(第一个角色) 或 'strict'(后续角色)

        Returns:
            添加了风格指导的提示词
        """
        engine_lower = engine.lower()

        # 根据引擎选择语言
        if engine_lower in self.CHINESE_PROMPT_ENGINES:
            # 中文风格指导
            if guidance_type == 'simple':
                style_guidance = (
                    "【重要提示】参考图用于统一画风和艺术风格，"
                    "必须保持与参考图相同的画风、色调、质感和艺术表现手法。"
                )
            else:  # strict
                style_guidance = (
                    "【重要提示】参考图仅用于统一画风和艺术风格，"
                    "严格禁止复制参考图中的角色形象、五官、发型、服装。"
                    "必须创建一个全新的、完全不同的角色，"
                    "但保持与参考图相同的画风、色调、质感和艺术表现手法。"
                )
            # 中文提示词添加
            if not image_prompt.endswith('。'):
                return f"{image_prompt}。{style_guidance}"
            else:
                return f"{image_prompt}{style_guidance}"

        else:
            # 英文风格指导
            if guidance_type == 'simple':
                style_guidance = (
                    "[IMPORTANT] Use the reference image to maintain consistent art style, "
                    "color tone, texture, and artistic expression."
                )
            else:  # strict
                style_guidance = (
                    "[IMPORTANT] Use reference images ONLY for art style consistency. "
                    "DO NOT copy character appearance, facial features, hairstyle, or clothing. "
                    "Create a completely NEW and DIFFERENT character, "
                    "but maintain the same art style, color tone, texture, and artistic expression as the reference."
                )
            # 英文提示词添加
            if not image_prompt.endswith('.'):
                return f"{image_prompt}. {style_guidance}"
            else:
                return f"{image_prompt} {style_guidance}"

    def _build_visual_style_prefix(self, visual_style: Dict, engine: str) -> str:
        """根据 visual_style 配置构建风格关键词前缀

        Args:
            visual_style: 视觉风格配置，包含颜色、构图、特效等信息
            engine: 图片生成引擎

        Returns:
            风格关键词前缀字符串
        """
        if not visual_style:
            return ""

        engine_lower = engine.lower()

        # 检测是否是写实风格
        is_realistic = False
        style_keywords = []

        def has_positive_realistic_keyword(text: str) -> bool:
            if not text:
                return False
            cleaned = str(text).lower()
            negated_patterns = [
                r"(不要|不能|禁止|拒绝|避免|绝无|非|不是|无)[^。；;，,]*?(照片级|真实|写实|真人|古装剧)[^。；;，,]*",
                r"(not|no|avoid|reject|without|non[- ]?)[^.;,]*?(realistic|photorealistic|live[- ]?action|real)[^.;,]*",
            ]
            for pattern in negated_patterns:
                cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
            realistic_keywords = ['照片级', '真实', '写实', 'photorealistic', 'realistic']
            return any(kw in cleaned for kw in realistic_keywords)

        # 检查特效配置中的质感描述
        effects = visual_style.get('特效', {})
        quality = effects.get('质感', '')
        if has_positive_realistic_keyword(quality):
            is_realistic = True

        # 检查颜色配置中的氛围特征
        color = visual_style.get('颜色', {})
        atmosphere = color.get('氛围特征', '')
        if has_positive_realistic_keyword(atmosphere):
            is_realistic = True

        # 检查构图配置
        composition = visual_style.get('构图', {})
        comp_type = composition.get('类型', '')
        if has_positive_realistic_keyword(comp_type) or 'photo' in str(comp_type).lower():
            is_realistic = True

        # 根据引擎和风格类型构建前缀
        if engine_lower in self.CHINESE_PROMPT_ENGINES:
            # 中文引擎
            if is_realistic:
                return "照片级真实感，自然光影，真实材质纹理，真实世界场景。"
            else:
                # 提取风格特征
                elements = effects.get('元素', [])
                if elements:
                    style_keywords = elements[:3] if len(elements) > 3 else elements
                    return f"{', '.join(style_keywords)}。"
                return ""
        else:
            # 英文引擎
            if is_realistic:
                return "Photorealistic, natural lighting, realistic textures, real-world scene. "
            else:
                # 提取风格特征
                elements = effects.get('元素', [])
                if elements:
                    style_keywords = elements[:3] if len(elements) > 3 else elements
                    return f"{', '.join(style_keywords)}. "
                return ""

    def _select_prompt_by_engine(self, prompt_data: Dict, engine: str) -> str:
        """根据引擎类型选择合适的提示词语言

        Args:
            prompt_data: 包含 image_prompt_chinese 和 image_prompt_english 的字典
            engine: 图片生成引擎名称

        Returns:
            选择的提示词文本
        """
        chinese_prompt = prompt_data.get('image_prompt_chinese', '')
        english_prompt = prompt_data.get('image_prompt_english', '')

        # 规范化引擎名称（转小写）
        engine_lower = engine.lower()

        # 根据引擎类型选择提示词
        if engine_lower in self.CHINESE_PROMPT_ENGINES:
            # 中文引擎：seedream5, gemini3_pro
            selected_prompt = chinese_prompt or english_prompt
            if chinese_prompt:
                logger.debug(f"  🇨🇳 引擎 {engine} 使用中文提示词")
            else:
                logger.warning(f"  ⚠️ 引擎 {engine} 应使用中文提示词，但未找到 image_prompt_chinese，使用英文提示词")
        elif engine_lower in self.ENGLISH_PROMPT_ENGINES:
            # 当前核心图片引擎优先中文提示词
            selected_prompt = english_prompt or chinese_prompt
            if english_prompt:
                logger.debug(f"  🇬🇧 引擎 {engine} 使用英文提示词")
            else:
                logger.warning(f"  ⚠️ 引擎 {engine} 应使用英文提示词，但未找到 image_prompt_english，使用中文提示词")
        else:
            # 未知引擎，默认优先英文
            selected_prompt = english_prompt or chinese_prompt
            logger.warning(f"  ⚠️ 未知引擎 {engine}，默认优先使用英文提示词")

        return selected_prompt

    def generate_all_references(
        self,
        reference_design: Dict,
        output_dir: str,
        aspect_ratio: str = '9:16',
        engine: str = 'seedream5',
        max_retries: int = 3,
        user_reference_images: List[str] = None,
        reference_analysis_results: List[Dict] = None,
        style_reference_variants: List[Dict] = None,
        visual_style: Dict = None
    ) -> Dict:
        """生成所有参考图

        Args:
            reference_design: 参考设计数据
            output_dir: 输出目录
            aspect_ratio: 宽高比
            engine: 图片生成引擎
            max_retries: 最大重试次数
            user_reference_images: 用户提供的参考图片路径列表
            reference_analysis_results: 参考图分析结果列表
            style_reference_variants: 风格参考图变体列表（可选），将用于角色参考图生成
            visual_style: 视觉风格配置（可选），包含颜色、构图、特效等信息，用于在角色prompt中添加风格关键词

        Returns:
            参考图生成结果字典
        """
        reference_type = reference_design.get('reference_type', 'style')
        user_reference_images = user_reference_images or []
        reference_analysis_results = reference_analysis_results or []
        style_reference_variants = style_reference_variants or []
        visual_style = visual_style or {}

        # 构建用户参考图索引映射
        user_image_map = {i: img_path for i, img_path in enumerate(user_reference_images)}

        logger.info(f"🔍 主要参考类型: {reference_type}")
        if user_image_map:
            logger.info(f"📷 用户提供了 {len(user_image_map)} 张参考图片")
        if style_reference_variants:
            logger.info(f"🎨 提供了 {len(style_reference_variants)} 张风格参考图变体，将用于角色生成")
        logger.info(f"📋 参考图生成策略：先风格/物体图 → 角色图1（文生图+visual_style）→ 其他角色（基于角色1+visual_style）")

        reference_images = []

        # 用于存储已生成的参考图路径
        first_character_path = None
        style_reference_path = None  # AI生成的风格参考图（用于object_reference）

        # 步骤1: 先生成风格参考图（如果存在style_reference定义）
        style_ref = reference_design.get('style_reference', {})
        if style_ref:
            result = self._generate_style_reference(
                style_ref, output_dir, aspect_ratio, engine, max_retries, user_image_map
            )
            reference_images.append(result)
            if result.get('generation_status') == 'success':
                style_reference_path = result.get('image_path')
                logger.info(f"  🎨 风格参考图生成成功")

        # 步骤2: 生成物体参考图（如果存在object_reference定义）
        object_ref = reference_design.get('object_reference', {})
        if object_ref:
            result = self._generate_object_reference(
                object_ref, output_dir, aspect_ratio, engine, max_retries,
                style_reference_path, user_image_map
            )
            reference_images.append(result)

        # 步骤3: 生成角色参考图（如果存在characters定义）
        characters = reference_design.get('characters', [])
        if characters:
            logger.info(f"🎨 [步骤3/4] 发现 {len(characters)} 个角色定义，开始按顺序生成...")

            for idx, char in enumerate(characters):
                result = self._generate_character_reference(
                    char, idx, len(characters), output_dir, aspect_ratio, engine,
                    max_retries, first_character_path, user_image_map, visual_style
                )
                reference_images.append(result)

                # 保存第一个角色的路径供后续使用
                if idx == 0 and result.get('generation_status') == 'success':
                    first_character_path = result.get('image_path')
                    logger.info(f"  ✅ 角色1生成成功，将用于后续角色生成")

        # 统计结果
        total_refs = len(reference_images)
        successful = sum(1 for img in reference_images if img.get('generation_status') == 'success')
        failed = total_refs - successful

        logger.info(f"✅ [步骤4/4] 参考图生成完成: 成功{successful}/{total_refs}, 失败{failed}")
        if visual_style:
            logger.info(f"  📌 风格统一策略：角色图通过 visual_style prompt 前缀控制风格")

        return {
            "reference_type": reference_type,
            "total_references": total_refs,
            "reference_images": reference_images,
            "successful": successful,
            "failed": failed,
            "style_reference_path": style_reference_path,
            "first_character_path": first_character_path
        }

    def _generate_style_reference(
        self,
        style_ref: Dict,
        output_dir: str,
        aspect_ratio: str,
        engine: str,
        max_retries: int,
        user_image_map: Dict[int, str]
    ) -> Dict:
        """生成风格参考图"""
        import shutil

        style_name = style_ref.get('style_name', '风格参考')
        # 根据引擎选择合适的提示词
        image_prompt = self._select_prompt_by_engine(style_ref, engine)

        # 检查是否使用用户提供的图片
        use_user_provided = style_ref.get('use_user_provided', False)
        user_provided_index = style_ref.get('user_provided_image_index')
        based_on_user_index = style_ref.get('based_on_user_image_index')

        logger.info(f"🎨 [步骤1/4] 生成风格参考图: {style_name}")

        try:
            # 模式1: 直接使用用户图片
            if use_user_provided and user_provided_index is not None and user_provided_index in user_image_map:
                user_image_path = user_image_map[user_provided_index]
                logger.info(f"  📌 直接使用用户参考图{user_provided_index}: {user_image_path}")

                # 复制用户图片到输出目录
                output_path = Path(output_dir) / f"style_reference_from_user_{user_provided_index}.jpg"
                shutil.copy2(user_image_path, output_path)

                return {
                    'reference_id': 'style_reference',
                    'reference_name': style_name,
                    'reference_type': 'style',
                    'image_path': str(output_path),
                    'generation_status': 'success',
                    'prompt_used': image_prompt,
                    'source': 'user_provided',
                    'user_image_index': user_provided_index
                }

            # 模式2: 基于用户图片生成新图
            reference_image = None
            if based_on_user_index is not None and based_on_user_index in user_image_map:
                reference_image = user_image_map[based_on_user_index]
                logger.info(f"  🎨 基于用户参考图{based_on_user_index}生成新图: {reference_image}")
            elif use_user_provided:
                # 如果设置了use_user_provided但index无效，给出警告
                logger.warning(f"  ⚠️ 风格图设置了use_user_provided=true，但user_provided_image_index={user_provided_index}无效，降级为AI生成")

            # 模式3: 标准AI生成（或模式2的执行）
            result = self.image_tool._run(
                scene={'index': 'style_reference', 'image_prompt': image_prompt},
                output_dir=output_dir,
                engine=engine,
                aspect_ratio=aspect_ratio,
                reference_image_path=reference_image,
                max_retries=max_retries,
                enable_moderation=True
            )

            success = result.get('status') == 'success'
            output_path = result.get('output_path', '') if success else ''

            if success:
                if reference_image:
                    logger.info(f"  ✅ 基于用户图{based_on_user_index}生成风格图成功")
                else:
                    logger.info(f"  ✅ 风格图生成成功，将用于后续角色生成")

            return {
                'reference_id': 'style_reference',
                'reference_name': style_name,
                'reference_type': 'style',
                'image_path': output_path,
                'generation_status': 'success' if success else 'failed',
                'prompt_used': image_prompt,
                'result': result,
                'source': 'based_on_user' if reference_image else 'ai_generated',
                'user_image_index': based_on_user_index if reference_image else None
            }
        except Exception as e:
            logger.error(f"  ❌ 生成风格参考图失败: {str(e)}")
            return {
                'reference_id': 'style_reference',
                'reference_name': style_name,
                'reference_type': 'style',
                'image_path': '',
                'generation_status': 'failed',
                'error': str(e)
            }

    def _generate_object_reference(
        self,
        object_ref: Dict,
        output_dir: str,
        aspect_ratio: str,
        engine: str,
        max_retries: int,
        style_reference_path: Optional[str],
        user_image_map: Dict[int, str]
    ) -> Dict:
        """生成物体参考图"""
        import shutil

        object_name = object_ref.get('object_name', '物体参考')
        # 根据引擎选择合适的提示词
        image_prompt = self._select_prompt_by_engine(object_ref, engine)

        # 检查是否使用用户提供的图片
        use_user_provided = object_ref.get('use_user_provided', False)
        user_provided_index = object_ref.get('user_provided_image_index')
        based_on_user_index = object_ref.get('based_on_user_image_index')

        logger.info(f"🎨 [步骤2/4] 生成物体参考图: {object_name}")

        try:
            # 模式1: 直接使用用户图片
            if use_user_provided and user_provided_index is not None and user_provided_index in user_image_map:
                user_image_path = user_image_map[user_provided_index]
                logger.info(f"  📌 直接使用用户参考图{user_provided_index}: {user_image_path}")

                # 复制用户图片到输出目录
                output_path = Path(output_dir) / f"object_reference_from_user_{user_provided_index}.jpg"
                shutil.copy2(user_image_path, output_path)

                return {
                    'reference_id': 'object_reference',
                    'reference_name': object_name,
                    'reference_type': 'object',
                    'image_path': str(output_path),
                    'generation_status': 'success',
                    'prompt_used': image_prompt,
                    'source': 'user_provided',
                    'user_image_index': user_provided_index
                }

            # 模式2: 基于用户图片生成新图
            reference_image = None
            generation_strategy = 'text_to_image'

            if based_on_user_index is not None and based_on_user_index in user_image_map:
                reference_image = user_image_map[based_on_user_index]
                generation_strategy = 'based_on_user'
                logger.info(f"  🎨 基于用户参考图{based_on_user_index}生成新图")
            elif style_reference_path:
                reference_image = style_reference_path
                generation_strategy = 'style_based'
                logger.info(f"  🎨 基于风格图生成")
            else:
                logger.info(f"  🎨 文生图")

            # 模式3: 标准AI生成（或模式2的执行）
            result = self.image_tool._run(
                scene={'index': 'object_reference', 'image_prompt': image_prompt},
                output_dir=output_dir,
                engine=engine,
                aspect_ratio=aspect_ratio,
                reference_image_path=reference_image,
                max_retries=max_retries,
                enable_moderation=True
            )

            success = result.get('status') == 'success'
            output_path = result.get('output_path', '') if success else ''

            return {
                'reference_id': 'object_reference',
                'reference_name': object_name,
                'reference_type': 'object',
                'image_path': output_path,
                'generation_status': 'success' if success else 'failed',
                'prompt_used': image_prompt,
                'result': result,
                'generation_strategy': generation_strategy,
                'source': 'based_on_user' if based_on_user_index is not None else ('ai_generated'),
                'user_image_index': based_on_user_index
            }
        except Exception as e:
            logger.error(f"  ❌ 生成物体参考图失败: {str(e)}")
            return {
                'reference_id': 'object_reference',
                'reference_name': object_name,
                'reference_type': 'object',
                'image_path': '',
                'generation_status': 'failed',
                'error': str(e)
            }

    def _generate_character_reference(
        self,
        char: Dict,
        idx: int,
        total_chars: int,
        output_dir: str,
        aspect_ratio: str,
        engine: str,
        max_retries: int,
        first_character_path: Optional[str],
        user_image_map: Dict[int, str],
        visual_style: Dict = None
    ) -> Dict:
        """生成角色参考图

        Args:
            char: 角色配置数据
            idx: 角色索引
            total_chars: 总角色数
            output_dir: 输出目录
            aspect_ratio: 宽高比
            engine: 图片生成引擎
            max_retries: 最大重试次数
            first_character_path: 第一个角色参考图路径（用于后续角色保持一致性）
            user_image_map: 用户图片索引映射
            visual_style: 视觉风格配置（用于在 prompt 中添加风格关键词前缀）

        Returns:
            角色参考图生成结果
        """
        import shutil

        visual_style = visual_style or {}
        char_id = char.get('character_id', idx)
        char_name = char.get('character_name', f'角色{char_id}')
        # 根据引擎选择合适的提示词
        image_prompt = self._select_prompt_by_engine(char, engine)

        # 🎨 根据 visual_style 添加风格关键词前缀
        if visual_style:
            style_prefix = self._build_visual_style_prefix(visual_style, engine)
            if style_prefix:
                image_prompt = style_prefix + image_prompt
                logger.info(f"  🎨 角色{idx+1}: 已添加风格关键词前缀")

        # 检查是否使用用户提供的图片
        use_user_provided = char.get('use_user_provided', False)
        user_provided_index = char.get('user_provided_image_index')
        based_on_user_index = char.get('based_on_user_image_index')

        try:
            # 模式1: 直接使用用户图片
            if use_user_provided and user_provided_index is not None and user_provided_index in user_image_map:
                user_image_path = user_image_map[user_provided_index]
                logger.info(f"  📌 角色{idx+1}/{total_chars}: {char_name} (ID:{char_id}) - 直接使用用户参考图{user_provided_index}")

                # 复制用户图片到输出目录
                output_path = Path(output_dir) / f"character_{char_id}_from_user_{user_provided_index}.jpg"
                shutil.copy2(user_image_path, output_path)

                return {
                    'reference_id': f'character_{char_id}',
                    'reference_name': char_name,
                    'reference_type': 'character',
                    'image_path': str(output_path),
                    'generation_status': 'success',
                    'prompt_used': image_prompt,
                    'source': 'user_provided',
                    'user_image_index': user_provided_index
                }

            # 模式2或3: 基于用户图片生成，或独立生成（使用 visual_style 控制风格）
            # 注意：不使用风格参考图作为图生图输入，而是通过 visual_style prompt 前缀控制风格
            reference_image_param = None
            generation_strategy = 'text_to_image'

            # 优先检查是否基于用户图生成
            if based_on_user_index is not None and based_on_user_index in user_image_map:
                reference_image_param = user_image_map[based_on_user_index]
                generation_strategy = 'based_on_user'
                logger.info(f"  🎨 角色{idx+1}/{total_chars}: {char_name} (ID:{char_id}) - 基于用户参考图{based_on_user_index}生成")

            elif idx == 0:
                # 第一个角色：使用文生图 + visual_style 控制风格
                if visual_style:
                    logger.info(f"  🎨 角色{idx+1}/{total_chars}: {char_name} (ID:{char_id}) - 文生图（使用 visual_style 控制风格）")
                else:
                    logger.info(f"  🎨 角色{idx+1}/{total_chars}: {char_name} (ID:{char_id}) - 文生图（无风格配置）")
                generation_strategy = 'text_to_image_with_style' if visual_style else 'text_to_image'
            else:
                # 后续角色：参考第一个角色图保持一致性 + visual_style 控制风格
                if first_character_path:
                    logger.info(f"  🎨 角色{idx+1}/{total_chars}: {char_name} (ID:{char_id}) - 基于角色1生成（使用 visual_style 控制风格）")
                    reference_image_param = first_character_path
                    generation_strategy = 'character_reference'
                    # 为后续角色添加严格的风格指导（仅参考角色，不复制）
                    image_prompt = self._add_style_guidance(image_prompt, engine, 'strict')
                else:
                    if visual_style:
                        logger.info(f"  🎨 角色{idx+1}/{total_chars}: {char_name} (ID:{char_id}) - 文生图（使用 visual_style 控制风格）")
                    else:
                        logger.info(f"  🎨 角色{idx+1}/{total_chars}: {char_name} (ID:{char_id}) - 文生图（无参考图）")
                    generation_strategy = 'text_to_image_with_style' if visual_style else 'text_to_image'

            result = self.image_tool._run(
                scene={'index': f'character_{char_id}', 'image_prompt': image_prompt},
                output_dir=output_dir,
                engine=engine,
                aspect_ratio=aspect_ratio,
                reference_image_path=reference_image_param,
                max_retries=max_retries,
                enable_moderation=True
            )

            success = result.get('status') == 'success'
            output_path = result.get('output_path', '') if success else ''

            return {
                'reference_id': f'character_{char_id}',
                'reference_name': char_name,
                'reference_type': 'character',
                'image_path': output_path,
                'generation_status': 'success' if success else 'failed',
                'prompt_used': image_prompt,
                'result': result,
                'generation_strategy': generation_strategy,
                'source': 'based_on_user' if based_on_user_index is not None else 'ai_generated',
                'user_image_index': based_on_user_index
            }
        except Exception as e:
            logger.error(f"  ❌ 生成角色{char_name}失败: {str(e)}")
            return {
                'reference_id': f'character_{char_id}',
                'reference_name': char_name,
                'reference_type': 'character',
                'image_path': '',
                'generation_status': 'failed',
                'error': str(e)
            }


class ReferenceImageTool(BaseTool):
    """参考图生成工具"""
    name: str = "Generate Reference Images"
    description: str = "生成参考图（风格图、物体图、角色图），使用优化的生成策略确保风格统一"
    args_schema: type[BaseModel] = ReferenceImageInput

    def _run(
        self,
        reference_design: Dict,
        output_dir: str,
        aspect_ratio: str = '9:16',
        engine: str = 'seedream5'
    ) -> Dict:
        """执行工具"""
        generator = ReferenceImageGenerator()
        return generator.generate_all_references(
            reference_design=reference_design,
            output_dir=output_dir,
            aspect_ratio=aspect_ratio,
            engine=engine
        )
