#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片生成 runtime 模块
负责处理所有与图片生成相关的逻辑（参考图、场景图、封面图）
"""

from pathlib import Path
import math
import os
import time
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed

from custom_tools.image_generation import (
    ReferenceImageGenerator,
    GenerateSceneImageTool,
    CoverImageGenerator
)
from src.logger import get_logger
from .config import CONFIG, REF_TYPE, GEN_MODE

logger = get_logger('image_generator')


class ImageGenerator:
    """图片生成器"""

    # 定义需要使用中文提示词的引擎
    CHINESE_PROMPT_ENGINES = {'seedream5', 'gemini3_pro'}
    # 定义需要使用英文提示词的引擎
    ENGLISH_PROMPT_ENGINES = {'gpt-image-2'}

    def __init__(self, default_engine: str = None):
        """
        初始化图片生成器

        Args:
            default_engine: 默认图片生成引擎（如果不指定则使用CONFIG.DEFAULT_IMAGE_ENGINE）
        """
        self.scene_image_tool = GenerateSceneImageTool()
        self.default_engine = default_engine or CONFIG.DEFAULT_IMAGE_ENGINE

    def generate_reference_images(
        self,
        reference_design: Dict,
        output_dir: str,
        aspect_ratio: str = None,
        engine: str = None,
        user_reference_images: List[str] = None,
        reference_analysis_results: List[Dict] = None,
        style_reference_variants: List[Dict] = None,
        visual_style: Dict = None
    ) -> Dict:
        """
        生成参考图片

        Args:
            reference_design: 参考设计数据
            output_dir: 输出目录
            aspect_ratio: 宽高比
            engine: 图片生成引擎（如果不指定则使用self.default_engine）
            user_reference_images: 用户提供的参考图片路径列表
            reference_analysis_results: 参考图分析结果列表
            style_reference_variants: 风格参考图变体列表（可选）
            visual_style: 视觉风格配置（可选），用于在角色prompt中添加风格关键词

        Returns:
            参考图生成结果
        """
        aspect_ratio = aspect_ratio or CONFIG.DEFAULT_ASPECT_RATIO
        engine = engine or self.default_engine  # 使用实例的default_engine而不是CONFIG
        user_reference_images = user_reference_images or []
        reference_analysis_results = reference_analysis_results or []
        style_reference_variants = style_reference_variants or []
        visual_style = visual_style or {}

        generator = ReferenceImageGenerator()
        return generator.generate_all_references(
            reference_design=reference_design,
            output_dir=output_dir,
            aspect_ratio=aspect_ratio,
            engine=engine,
            user_reference_images=user_reference_images,
            reference_analysis_results=reference_analysis_results,
            style_reference_variants=style_reference_variants,
            visual_style=visual_style
        )

    def generate_scene_images(
        self,
        storyboard: List[Dict],
        references_result: Dict,
        output_dir: str,
        aspect_ratio: str = None,
        max_workers: int = None,
        max_retries: int = None,
        enable_moderation: bool = None,
        enable_quality_check: bool = None,
        style_reference_variants: List[Dict] = None,
        engine: str = None,
        scene_timeout_seconds: float = None,
        user_reference_images: List[str] = None,
        capsule_category: str = None
    ) -> Dict:
        """
        批量生成场景图片（支持并发，智能选择文生图/图生图）

        Args:
            storyboard: 分镜列表
            references_result: 参考图生成结果
            output_dir: 输出目录
            aspect_ratio: 宽高比
            max_workers: 最大并发数
            max_retries: 最大重试次数
            enable_moderation: 是否启用内容审核
            enable_quality_check: 是否启用图片质量检查
            style_reference_variants: 风格参考图变体列表（可选）
            engine: 图片生成引擎（如果不指定则使用self.default_engine）
            scene_timeout_seconds: 单个场景生成允许的最大秒数，默认读取配置/环境变量
            user_reference_images: 用户提供的参考图片路径列表（电商商品锚定用）
            capsule_category: 胶囊类型，用于启用电商商品锚定逻辑

        Returns:
            场景图生成结果
        """
        aspect_ratio = aspect_ratio or CONFIG.DEFAULT_ASPECT_RATIO
        max_workers = max_workers or CONFIG.IMAGE_CONCURRENCY
        max_retries = max_retries or CONFIG.MAX_RETRIES
        enable_moderation = enable_moderation if enable_moderation is not None else CONFIG.ENABLE_MODERATION
        enable_quality_check = enable_quality_check if enable_quality_check is not None else CONFIG.ENABLE_IMAGE_QUALITY_CHECK
        style_reference_variants = style_reference_variants or []
        engine = engine or self.default_engine
        scene_timeout_seconds = self._resolve_scene_timeout_seconds(scene_timeout_seconds)
        user_reference_images = user_reference_images or []

        # 构建参考图映射
        ref_mapping = self._build_reference_mapping(references_result)
        self._attach_user_product_reference(
            ref_mapping=ref_mapping,
            user_reference_images=user_reference_images,
            capsule_category=capsule_category,
        )
        if engine == 'gpt-image-2' and ref_mapping.get('force_product_reference_for_scenes'):
            max_workers = min(max_workers, int(os.getenv('GPT_IMAGE2_IMAGE_CONCURRENCY', '1')))
            logger.info(f"🐢 电商商品图使用 gpt-image-2 edits，限制图片并发为 {max_workers}")
        batch_timeout_seconds = scene_timeout_seconds * max(1, math.ceil(len(storyboard) / max(1, max_workers)))

        # 并发生成场景图片
        generated_images = []

        logger.info(f"📸 开始并发生成 {len(storyboard)} 个场景图片（最大{max_workers}并发）...")
        if enable_quality_check:
            logger.info(f"🔍 图片质量检查已启用，不合格图片将自动重新生成（最多{CONFIG.MAX_IMAGE_REGENERATION_ATTEMPTS}次）")

        # 🎨 如果提供了风格参考图变体，记录日志
        if style_reference_variants:
            logger.info(f"🎨 使用 {len(style_reference_variants)} 张风格参考图变体:")
            for variant in style_reference_variants:
                logger.info(f"   - {variant['type']}: {Path(variant['path']).name}")
            logger.info(f"   💡 这些图将作为风格参考，仅学习风格不复制内容")

        executor = ThreadPoolExecutor(max_workers=max_workers)
        futures = {}
        pending = set()
        try:
            futures = {
                executor.submit(
                    self._generate_single_scene,
                    i, scene, ref_mapping, output_dir, aspect_ratio, max_retries, enable_moderation, enable_quality_check, style_reference_variants, engine
                ): i
                for i, scene in enumerate(storyboard)
            }
            pending = set(futures)

            for future in as_completed(futures, timeout=batch_timeout_seconds):
                pending.discard(future)
                try:
                    result = future.result()
                    generated_images.append(result)
                except Exception as e:
                    i = futures[future]
                    logger.error(f"❌ 场景{i}生成异常: {str(e)}")
                    generated_images.append({
                        'scene_id': storyboard[i].get('scene_id', i),
                        'image_path': '',
                        'generation_mode': GEN_MODE.FAILED,
                        'status': 'failed',
                        'index': i,
                        'error': str(e)
                    })
        except FuturesTimeoutError:
            timeout_message = (
                f"场景图片批处理超时: {len(pending)} 个场景在 "
                f"{batch_timeout_seconds:g}s 内未完成"
            )
            logger.error(f"❌ {timeout_message}")
            for future in pending:
                i = futures[future]
                future.cancel()
                generated_images.append(
                    self._build_failed_scene_result(
                        storyboard[i],
                        i,
                        error='scene_image_generation_timeout',
                        extra={
                            'timeout_seconds': scene_timeout_seconds,
                            'batch_timeout_seconds': batch_timeout_seconds,
                        },
                    )
                )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        # 按照原始顺序排序
        generated_images.sort(key=lambda x: x.get('index', 0))

        summary = {
            'total_scenes': len(storyboard),
            'successful': sum(1 for img in generated_images if img['status'] == 'success'),
            'failed': sum(1 for img in generated_images if img['status'] == 'failed'),
            'timed_out': sum(1 for img in generated_images if img.get('error') == 'scene_image_generation_timeout'),
        }

        if enable_quality_check:
            summary['quality_checked'] = sum(1 for img in generated_images if img.get('quality_checked', False))
            summary['regenerated'] = sum(1 for img in generated_images if img.get('regeneration_count', 0) > 0)

        logger.info(f"📊 场景图片生成完成: 成功{summary['successful']}/{summary['total_scenes']}, 失败{summary['failed']}")
        if enable_quality_check:
            logger.info(f"   质量检查: {summary.get('quality_checked', 0)}张, 重新生成: {summary.get('regenerated', 0)}张")

        # 如果启用了质量检查，保存检测报告到文件
        if enable_quality_check:
            try:
                import json
                from datetime import datetime

                report_path = Path(output_dir).parent / 'image_quality_report.json'
                report_data = {
                    'timestamp': datetime.now().isoformat(),
                    'summary': summary,
                    'details': [
                        {
                            'scene_id': img.get('scene_id'),
                            'index': img.get('index'),
                            'status': img.get('status'),
                            'quality_checked': img.get('quality_checked', False),
                            'regeneration_count': img.get('regeneration_count', 0),
                            'quality_score': img.get('quality_score', 0),
                            'quality_check_error': img.get('quality_check_error', ''),
                            'image_path': img.get('image_path', ''),
                            'prompt_optimization_history': img.get('prompt_optimization_history', []),
                            'final_prompt': img.get('final_prompt', '')
                        }
                        for img in generated_images
                    ]
                }

                with open(report_path, 'w', encoding='utf-8') as f:
                    json.dump(report_data, f, ensure_ascii=False, indent=2)

                logger.info(f"📄 图片质量检测报告已保存: {report_path}")
            except Exception as e:
                logger.warning(f"⚠️ 保存质量检测报告失败: {str(e)}")

        return {
            'summary': summary,
            'outputs': {i: img['image_path'] for i, img in enumerate(generated_images)},
            'details': generated_images
        }

    def _resolve_scene_timeout_seconds(self, explicit_timeout: float = None) -> float:
        if explicit_timeout is not None:
            raw_timeout = explicit_timeout
        else:
            raw_timeout = os.getenv(
                "IMAGE_SCENE_TIMEOUT_SECONDS",
                str(getattr(CONFIG, "IMAGE_SCENE_TIMEOUT_SECONDS", 300.0)),
            )
        try:
            timeout_seconds = float(raw_timeout)
        except (TypeError, ValueError):
            timeout_seconds = float(getattr(CONFIG, "IMAGE_SCENE_TIMEOUT_SECONDS", 300.0))
        return max(0.01, timeout_seconds)

    def _build_failed_scene_result(
        self,
        scene: Dict,
        index: int,
        error: str,
        extra: Dict = None,
    ) -> Dict:
        result = {
            'scene_id': scene.get('scene_id', index),
            'image_path': '',
            'generation_mode': GEN_MODE.FAILED,
            'status': 'failed',
            'index': index,
            'error': error,
        }
        if extra:
            result.update(extra)
        return result

    def generate_cover_image(
        self,
        image_result: Dict,
        title_text: str,
        output_path: str,
        aspect_ratio: str = None
    ) -> str:
        """
        生成视频封面（使用第一个场景图片+标题文字）

        Args:
            image_result: 场景图生成结果
            title_text: 标题文字
            output_path: 输出路径
            aspect_ratio: 宽高比

        Returns:
            封面图片路径
        """
        aspect_ratio = aspect_ratio or CONFIG.DEFAULT_ASPECT_RATIO

        first_image = CoverImageGenerator.get_first_scene_image(image_result)
        if not first_image:
            logger.warning("⚠️ 未找到第一个场景图片，无法生成封面")
            return ''

        cover_image = CoverImageGenerator.create_cover_with_text(
            base_image_path=first_image,
            title_text=title_text,
            output_path=output_path,
            aspect_ratio=aspect_ratio
        )

        if cover_image:
            logger.info(f"✅ 视频封面生成成功: {cover_image}")
        else:
            logger.warning("⚠️ 视频封面生成失败")

        return cover_image

    def _select_prompt_by_engine(self, scene: Dict, engine: str) -> str:
        """
        根据图片生成引擎智能选择提示词语言

        Args:
            scene: 场景数据，包含中英文提示词
            engine: 图片生成引擎

        Returns:
            选择的提示词
        """
        chinese_prompt = scene.get('image_prompt_chinese', '')
        english_prompt = scene.get('image_prompt_english', '')

        engine_lower = engine.lower()

        # 根据引擎类型选择提示词
        if engine_lower in self.CHINESE_PROMPT_ENGINES:
            # 中文引擎：seedream5, gemini3_pro
            selected_prompt = chinese_prompt or english_prompt
            if chinese_prompt:
                logger.debug(f"🇨🇳 引擎 {engine} 使用中文提示词")
            else:
                logger.warning(f"⚠️ 引擎 {engine} 需要中文提示词，但未提供，使用英文提示词")
        elif engine_lower in self.ENGLISH_PROMPT_ENGINES:
            # 当前核心图片引擎优先中文提示词
            selected_prompt = english_prompt or chinese_prompt
            if english_prompt:
                logger.debug(f"🇺🇸 引擎 {engine} 使用英文提示词")
            else:
                logger.warning(f"⚠️ 引擎 {engine} 需要英文提示词，但未提供，使用中文提示词")
        else:
            # 未知引擎，优先使用中文（因为大多数国内引擎使用中文）
            selected_prompt = chinese_prompt or english_prompt
            logger.warning(f"⚠️ 未知引擎 {engine}，默认使用中文提示词")

        return selected_prompt

    def _build_style_guidance_prompt(self, style_reference_variants: List[Dict], engine: str) -> str:
        """
        构建风格引导prompt，明确说明仅参考风格不复制内容

        Args:
            style_reference_variants: 风格参考图变体列表
            engine: 图片生成引擎

        Returns:
            风格引导prompt
        """
        if not style_reference_variants:
            return ""

        engine_lower = engine.lower()

        # 根据引擎选择语言
        if engine_lower in self.CHINESE_PROMPT_ENGINES:
            # 中文引擎
            variant_names = []
            for idx, variant in enumerate(style_reference_variants, 1):
                vtype = variant.get('type', 'unknown')
                type_map = {
                    'original': '原始风格图',
                    'clean_background': '干净背景版',
                    'grid_4': '4宫格版',
                    'grid_9': '9宫格版'
                }
                variant_names.append(f"第{idx}张({type_map.get(vtype, vtype)})")

            guidance = f"""【重要风格说明】参考图中的前{len(style_reference_variants)}张({', '.join(variant_names)})仅用于风格参考。
严格要求：
1. 只学习这些图的艺术风格、色调、画风、质感
2. 不要复制这些图中的具体内容、主体、场景、物体
3. 根据文本prompt生成全新的内容，但使用参考图的风格表现
4. 其余参考图（如有）用于角色/物体一致性"""

        else:
            # 英文引擎
            variant_names = []
            for idx, variant in enumerate(style_reference_variants, 1):
                vtype = variant.get('type', 'unknown')
                type_map = {
                    'original': 'original style',
                    'clean_background': 'clean background',
                    'grid_4': '4-grid',
                    'grid_9': '9-grid'
                }
                variant_names.append(f"#{idx} ({type_map.get(vtype, vtype)})")

            guidance = f"""[IMPORTANT STYLE GUIDANCE] The first {len(style_reference_variants)} reference images ({', '.join(variant_names)}) are for style reference ONLY.
Strict requirements:
1. ONLY learn the artistic style, color tone, art style, and texture from these images
2. DO NOT copy the specific content, subjects, scenes, or objects from these images
3. Generate completely NEW content based on the text prompt, but render it in the reference style
4. Other reference images (if any) are for character/object consistency"""

        return guidance

    def _build_visual_style_prompt(self, visual_style: Dict) -> str:
        """
        将 visual_style 配置转换为图片生成的前缀 prompt

        Args:
            visual_style: 视觉风格配置，包含颜色、构图、排版、特效等信息

        Returns:
            格式化的风格 prompt 字符串
        """
        if not visual_style:
            return ""

        import json

        # 将 visual_style 转换为结构化的 prompt
        prompt_parts = []

        # 处理颜色配置
        if '颜色' in visual_style:
            color_config = visual_style['颜色']
            if '主色调' in color_config:
                main_colors = color_config['主色调']
                if isinstance(main_colors, list):
                    prompt_parts.append(f"主色调: {', '.join(main_colors)}")
                else:
                    prompt_parts.append(f"主色调: {main_colors}")
            if '辅助色' in color_config:
                aux_colors = color_config['辅助色']
                if isinstance(aux_colors, list):
                    prompt_parts.append(f"辅助色: {', '.join(aux_colors)}")
                else:
                    prompt_parts.append(f"辅助色: {aux_colors}")
            if '氛围特征' in color_config:
                prompt_parts.append(f"色彩氛围: {color_config['氛围特征']}")

        # 处理排版配置
        if '排版' in visual_style:
            layout_config = visual_style['排版']
            if '元素布局' in layout_config:
                prompt_parts.append(f"元素布局: {layout_config['元素布局']}")
            if '层次关系' in layout_config:
                prompt_parts.append(f"层次关系: {layout_config['层次关系']}")

        # 处理构图配置
        if '构图' in visual_style:
            composition_config = visual_style['构图']
            if '类型' in composition_config:
                prompt_parts.append(f"构图类型: {composition_config['类型']}")
            if '特征' in composition_config:
                prompt_parts.append(f"构图特征: {composition_config['特征']}")
            if '视角' in composition_config:
                prompt_parts.append(f"视角: {composition_config['视角']}")

        # 处理特效配置
        if '特效' in visual_style:
            effects_config = visual_style['特效']
            if '元素' in effects_config:
                effects = effects_config['元素']
                if isinstance(effects, list):
                    prompt_parts.append(f"特效元素: {', '.join(effects)}")
                else:
                    prompt_parts.append(f"特效元素: {effects}")
            if '质感' in effects_config:
                prompt_parts.append(f"画面质感: {effects_config['质感']}")

        # 将所有部分组合成一个 prompt，用句号分隔
        if prompt_parts:
            # 添加前缀说明这是风格配置
            style_prompt = "【风格配置】" + "。".join(prompt_parts) + "。\n"
            return style_prompt

        return ""

    def _build_reference_mapping(self, references_result: Dict) -> Dict:
        """
        构建参考图的映射关系（仅处理角色参考图）

        Args:
            references_result: 参考图生成结果

        Returns:
            参考图映射字典
        """
        reference_images = references_result.get('reference_images', [])

        char_id_to_image = {}
        object_id_to_image = {}

        for ref in reference_images:
            if ref.get('generation_status') != 'success' or not ref.get('image_path'):
                continue

            ref_type = ref.get('reference_type')
            ref_id = ref.get('reference_id', '')
            image_path = ref.get('image_path')

            if ref_type == REF_TYPE.CHARACTER:
                # 支持多种角色ID格式。参考图生成器会输出
                # "character_<原ID>"，分镜通常引用 "<原ID>"。
                aliases = [ref_id]
                if ref_id.startswith('character_'):
                    aliases.append(ref_id.replace('character_', '', 1))

                for char_id in dict.fromkeys(alias for alias in aliases if alias):
                    char_id_to_image[char_id] = image_path
                    logger.info(f"📋 角色 {char_id} 参考图: {image_path}")
            elif ref_type == REF_TYPE.OBJECT:
                aliases = [ref_id, 'object_reference', 'product', 'product_reference']
                if ref_id.startswith('object_'):
                    aliases.append(ref_id.replace('object_', '', 1))
                for object_id in dict.fromkeys(alias for alias in aliases if alias):
                    object_id_to_image[object_id] = image_path
                    logger.info(f"📋 物体 {object_id} 参考图: {image_path}")

        return {
            'char_id_to_image': char_id_to_image,
            'object_id_to_image': object_id_to_image,
        }

    def _attach_user_product_reference(
        self,
        ref_mapping: Dict,
        user_reference_images: List[str],
        capsule_category: str = None,
    ) -> None:
        """Use the first user reference image as the ecommerce product anchor."""
        if capsule_category != 'ecommerce_product_showcase' or not user_reference_images:
            return

        product_image = ''
        for image_path in user_reference_images:
            path = Path(str(image_path)).expanduser()
            if path.is_file():
                product_image = str(path)
                break

        if not product_image:
            logger.warning("⚠️ 电商胶囊提供了用户参考图，但未找到可用的商品图文件")
            return

        object_id_to_image = ref_mapping.setdefault('object_id_to_image', {})
        aliases = [
            'object_reference',
            'product_reference',
            'product',
            'obj_product',
            'obj_headphone',
            'obj_headset',
            '黑色办公通话耳机',
        ]
        for alias in aliases:
            object_id_to_image.setdefault(alias, product_image)

        ref_mapping['fallback_product_image'] = product_image
        ref_mapping['force_product_reference_for_scenes'] = True
        logger.info(f"📌 电商商品主图参考: {product_image}")

    def _generate_single_scene(
        self,
        i: int,
        scene: Dict,
        ref_mapping: Dict,
        output_dir: str,
        aspect_ratio: str,
        max_retries: int,
        enable_moderation: bool,
        enable_quality_check: bool,
        style_reference_variants: List[Dict] = None,
        engine: str = None
    ) -> Dict:
        """
        生成单个场景图片（支持质量检查和重新生成）

        Args:
            i: 场景索引
            scene: 场景数据
            ref_mapping: 参考图映射
            output_dir: 输出目录
            aspect_ratio: 宽高比
            max_retries: 最大重试次数
            enable_moderation: 是否启用审核
            enable_quality_check: 是否启用质量检查
            style_reference_variants: 风格参考图变体列表（可选）
            engine: 图片生成引擎

        Returns:
            生成结果
        """
        style_reference_variants = style_reference_variants or []
        engine = engine or self.default_engine

        # 🎯 根据引擎智能选择提示词语言（中文引擎用中文，英文引擎用英文）
        image_prompt = self._select_prompt_by_engine(scene, engine)
        needs_reference = scene.get('needs_reference', False)
        scene_ref_type = scene.get('reference_type', REF_TYPE.NONE)
        reference_ids = scene.get('reference_ids', [])
        if ref_mapping.get('force_product_reference_for_scenes'):
            needs_reference = True
            if scene_ref_type in (REF_TYPE.NONE, REF_TYPE.STYLE):
                scene_ref_type = REF_TYPE.OBJECT
            elif scene_ref_type == REF_TYPE.CHARACTER:
                scene_ref_type = REF_TYPE.MIXED

            if not isinstance(reference_ids, list):
                reference_ids = [reference_ids] if reference_ids else []
            if 'object_reference' not in [str(item) for item in reference_ids]:
                reference_ids = [*reference_ids, 'object_reference']

        # 🎨 获取 visual_style 配置并转换为 reference_prompt_prefix
        visual_style = scene.get('visual_style', {})
        reference_prompt_prefix = self._build_visual_style_prompt(visual_style)

        # 🎨 检查该分镜是否使用风格参考（Agent决策）
        use_style_reference = scene.get('use_style_reference', True)  # 默认为True以保持向后兼容

        # 🎨 如果有风格参考图变体且该分镜决定使用，添加风格说明到 prompt prefix
        if style_reference_variants and use_style_reference:
            style_guidance = self._build_style_guidance_prompt(style_reference_variants, engine)
            reference_prompt_prefix = style_guidance + "\n" + reference_prompt_prefix if reference_prompt_prefix else style_guidance

        scene_data = {
            'index': i,
            'image_prompt': image_prompt
        }

        # 根据分镜的参考需求选择生成模式
        ref_images, generation_mode = self._determine_generation_mode(
            needs_reference, scene_ref_type, reference_ids, ref_mapping, i
        )
        if engine == 'gpt-image-2' and ref_mapping.get('force_product_reference_for_scenes'):
            product_image = ref_mapping.get('fallback_product_image')
            if product_image:
                ref_images = [product_image]
                generation_mode = GEN_MODE.IMAGE_TO_IMAGE
                logger.info(f"📌 场景{i}: 使用商品主图作为唯一 gpt-image-2 reference，降低资源池压力")

        # 🎨 获取风格参考决策原因（Agent提供）
        use_style_reference_reason = scene.get('use_style_reference_reason', '')

        # 🎨 合并风格参考图变体：将所有风格图添加到参考图列表
        if style_reference_variants and use_style_reference:
            style_images = [v['path'] for v in style_reference_variants]
            if ref_images:
                # 已有角色参考图，将风格参考图添加到列表前面（优先级：风格 > 角色）
                ref_images = style_images + ref_images
                generation_mode = GEN_MODE.MULTI_IMAGE_FUSION
                logger.info(f"🎨 场景{i}: {generation_mode} ({len(style_images)}张风格参考 + {len(ref_images)-len(style_images)}张角色参考)")
            else:
                # 没有角色参考图，仅使用风格参考图
                ref_images = style_images
                generation_mode = GEN_MODE.MULTI_IMAGE_FUSION if len(style_images) > 1 else GEN_MODE.IMAGE_TO_IMAGE
                logger.info(f"🎨 场景{i}: {generation_mode} (仅{len(style_images)}张风格参考)")
            if use_style_reference_reason:
                logger.info(f"   💡 使用风格参考原因: {use_style_reference_reason}")
        elif style_reference_variants and not use_style_reference:
            # Agent决定不使用风格参考
            logger.info(f"🎨 场景{i}: {generation_mode} (Agent决定不使用风格参考)")
            if use_style_reference_reason:
                logger.info(f"   💡 不使用原因: {use_style_reference_reason}")
        else:
            logger.info(f"🎨 场景{i}: {generation_mode}")

        if ref_images:
            logger.info(f"   参考图: {len(ref_images)}张")
        if reference_prompt_prefix:
            logger.info(f"   🎨 应用视觉风格配置和风格引导")

        # 调用生成工具
        reference_image_param = ref_images if len(ref_images) > 1 else (ref_images[0] if ref_images else None)

        regeneration_count = 0
        quality_checked = False
        final_result = None
        current_prompt = image_prompt  # 当前使用的prompt
        prompt_optimization_history = []  # 记录prompt优化历史

        # 最多尝试生成 (1 + MAX_IMAGE_REGENERATION_ATTEMPTS) 次
        transient_extra_retries = (
            int(os.getenv('GPT_IMAGE2_TRANSIENT_RETRIES', '4'))
            if engine == 'gpt-image-2' and ref_mapping.get('force_product_reference_for_scenes')
            else 0
        )
        total_generation_attempts = 1 + CONFIG.MAX_IMAGE_REGENERATION_ATTEMPTS + transient_extra_retries
        image_quality = (
            os.getenv('GPT_IMAGE2_ECOMMERCE_QUALITY', 'low')
            if engine == 'gpt-image-2' and ref_mapping.get('force_product_reference_for_scenes')
            else 'hd'
        )

        for attempt in range(total_generation_attempts):
            # 更新scene_data中的prompt
            scene_data['image_prompt'] = current_prompt

            result = self.scene_image_tool._run(
                scene=scene_data,
                output_dir=output_dir,
                engine=engine,
                aspect_ratio=aspect_ratio,
                reference_image_path=reference_image_param,
                reference_prompt_prefix=reference_prompt_prefix,
                max_retries=max_retries,
                enable_moderation=enable_moderation,
                quality=image_quality,
            )

            if result.get('status') != 'success':
                error_text = result.get('error', '未知错误')
                is_transient = any(token in str(error_text) for token in ('429', '资源池', 'rate limit', 'timeout'))
                if is_transient and attempt < total_generation_attempts - 1:
                    sleep_seconds = min(8 * (attempt + 1), 40)
                    logger.warning(
                        f"   ⚠️ 场景{i}生成遇到临时错误，{sleep_seconds}s 后重试 "
                        f"({attempt + 1}/{total_generation_attempts}): {error_text}"
                    )
                    time.sleep(sleep_seconds)
                    continue

                logger.error(f"   ❌ 场景{i}生成失败: {error_text}")
                final_result = {
                    'scene_id': scene.get('scene_id', i),
                    'image_path': '',
                    'generation_mode': GEN_MODE.FAILED,
                    'status': 'failed',
                    'index': i,
                    'error': error_text,
                    'quality_checked': False,
                    'regeneration_count': regeneration_count
                }
                break

            image_path = result['output_path']

            # 如果启用质量检查，检查生成的图片
            if enable_quality_check and attempt < CONFIG.MAX_IMAGE_REGENERATION_ATTEMPTS:
                logger.info(f"🔍 场景{i}: 开始质量检查（第{attempt+1}次生成）...")
                quality_checked = True

                from custom_tools.quality_check import ImageQualityCheckerTool
                quality_checker = ImageQualityCheckerTool()

                quality_result = quality_checker._run(
                    image_path=image_path,
                    original_prompt=image_prompt,
                    check_focus="quality"
                )

                if not quality_result.get('success', False):
                    logger.warning(
                        f"⚠️ 场景{i}: 图片质量检查不可用，标记为失败以避免未审核图片进入后续生成: "
                        f"{quality_result.get('error', 'unknown error')}"
                    )
                    final_result = {
                        'scene_id': scene.get('scene_id', i),
                        'image_path': '',
                        'generation_mode': GEN_MODE.FAILED,
                        'status': 'failed',
                        'index': i,
                        'error': 'image_quality_check_unavailable',
                        'quality_checked': False,
                        'quality_check_error': quality_result.get('error', 'unknown error'),
                        'regeneration_count': regeneration_count,
                        'prompt_optimization_history': prompt_optimization_history,
                        'final_prompt': current_prompt
                    }
                    break

                if quality_result.get('needs_regeneration', False):
                    regeneration_count += 1
                    logger.warning(f"")
                    logger.warning(f"{'='*60}")
                    logger.warning(f"⚠️ 场景{i}: 图片质量不合格！开始第{regeneration_count}次重新生成")
                    logger.warning(f"{'='*60}")

                    issues = quality_result.get('issues', [])
                    if issues:
                        logger.warning(f"🔍 不合格原因:")
                        for idx, issue in enumerate(issues, 1):
                            logger.warning(f"  {idx}. {issue.get('type', '未知')}: {issue.get('description', '')}")

                    logger.warning(f"⭐ 当前质量分数: {quality_result.get('quality_score', 0)}/10")
                    logger.warning(f"💡 期望分数: 8/10 以上")
                    logger.warning(f"🔄 剩余重试机会: {CONFIG.MAX_IMAGE_REGENERATION_ATTEMPTS - regeneration_count}")

                    # 🧠 智能优化prompt（如果还有重试机会）
                    if regeneration_count < CONFIG.MAX_IMAGE_REGENERATION_ATTEMPTS and issues:
                        logger.info(f"🧠 开始智能优化prompt...")
                        try:
                            from custom_tools.quality_check.prompt_optimizer_tool import PromptOptimizer
                            optimizer = PromptOptimizer()
                            optimized_prompt = optimizer.optimize_prompt(
                                original_prompt=current_prompt,
                                quality_issues=issues,
                                attempt_number=regeneration_count
                            )

                            if optimized_prompt != current_prompt:
                                # 记录优化历史
                                prompt_optimization_history.append({
                                    'attempt': regeneration_count,
                                    'original': current_prompt,
                                    'optimized': optimized_prompt,
                                    'issues': issues
                                })
                                current_prompt = optimized_prompt
                                logger.info(f"✅ Prompt已优化，将使用新prompt重新生成")
                            else:
                                logger.warning(f"⚠️ Prompt优化未生效，将使用原prompt重试")
                        except Exception as e:
                            logger.error(f"❌ Prompt优化失败: {str(e)}")
                            logger.warning(f"⚠️ 将使用原prompt重试")

                    logger.warning(f"{'='*60}")
                    logger.warning(f"")

                    # 删除不合格的图片
                    if os.path.exists(image_path):
                        os.remove(image_path)
                        logger.info(f"   🗑️  已删除不合格图片: {os.path.basename(image_path)}")

                    continue  # 重新生成
                else:
                    logger.info(f"")
                    logger.info(f"{'='*60}")
                    logger.info(f"✅ 场景{i}: 图片质量检查通过！")
                    logger.info(f"{'='*60}")
                    logger.info(f"⭐ 质量分数: {quality_result.get('quality_score', 8)}/10")
                    if regeneration_count > 0:
                        logger.info(f"🔄 重新生成次数: {regeneration_count}")
                        if prompt_optimization_history:
                            logger.info(f"🧠 Prompt优化次数: {len(prompt_optimization_history)}")
                    logger.info(f"💬 评价: {quality_result.get('summary', '图片质量良好')}")
                    logger.info(f"{'='*60}")
                    logger.info(f"")
                    final_result = {
                        'scene_id': scene.get('scene_id', i),
                        'image_path': image_path,
                        'generation_mode': generation_mode,
                        'status': 'success',
                        'index': i,
                        'quality_checked': True,
                        'regeneration_count': regeneration_count,
                        'quality_score': quality_result.get('quality_score', 8),
                        'prompt_optimization_history': prompt_optimization_history,  # 记录优化历史
                        'final_prompt': current_prompt  # 记录最终使用的prompt
                    }
                    break
            else:
                # 不启用质量检查或已达到最大重试次数
                final_result = {
                    'scene_id': scene.get('scene_id', i),
                    'image_path': image_path,
                    'generation_mode': generation_mode,
                    'status': 'success',
                    'index': i,
                    'quality_checked': quality_checked,
                    'regeneration_count': regeneration_count
                }
                break

        # 如果所有尝试都失败了
        if final_result is None:
            final_result = {
                'scene_id': scene.get('scene_id', i),
                'image_path': '',
                'generation_mode': GEN_MODE.FAILED,
                'status': 'failed',
                'index': i,
                'error': f'经过{CONFIG.MAX_IMAGE_REGENERATION_ATTEMPTS}次重新生成，图片质量仍不合格',
                'quality_checked': True,
                'regeneration_count': regeneration_count
            }

        return final_result

    def _determine_generation_mode(
        self,
        needs_reference: bool,
        scene_ref_type: str,
        reference_ids: List[str],
        ref_mapping: Dict,
        scene_index: int
    ) -> tuple:
        """
        确定场景的生成模式和参考图。

        风格/物体参考会通过 visual_style、style_reference_variants 和 prompt
        约束生效；这里仅把可用的角色参考图升级为 image-to-image。

        Args:
            needs_reference: 是否需要参考图
            scene_ref_type: 参考类型
            reference_ids: 参考ID列表（字符串格式，如 ["char_001"]）
            ref_mapping: 参考图映射
            scene_index: 场景索引

        Returns:
            (参考图列表, 生成模式)
        """
        ref_images = []
        generation_mode = GEN_MODE.TEXT_TO_IMAGE

        if not needs_reference or scene_ref_type == REF_TYPE.NONE:
            return ref_images, generation_mode

        char_id_to_image = ref_mapping['char_id_to_image']
        object_id_to_image = ref_mapping.get('object_id_to_image', {})

        normalized_ids = []
        for item in reference_ids or []:
            if isinstance(item, dict):
                value = (
                    item.get('id')
                    or item.get('object_id')
                    or item.get('character_id')
                    or item.get('reference_id')
                )
            else:
                value = item
            if value:
                normalized_ids.append(str(value))

        def append_ref(image_path: str) -> None:
            if image_path and image_path not in ref_images:
                ref_images.append(image_path)

        if scene_ref_type in (REF_TYPE.CHARACTER, REF_TYPE.MIXED):
            for char_id in normalized_ids:
                if char_id in char_id_to_image:
                    append_ref(char_id_to_image[char_id])
            if scene_ref_type == REF_TYPE.CHARACTER:
                if ref_images:
                    generation_mode = GEN_MODE.MULTI_IMAGE_FUSION if len(ref_images) > 1 else GEN_MODE.IMAGE_TO_IMAGE
                else:
                    logger.warning(f"⚠️ 场景{scene_index}需要角色{normalized_ids}的参考图，但未找到，降级为文生图")
                return ref_images, generation_mode

        if scene_ref_type in (REF_TYPE.OBJECT, REF_TYPE.MIXED):
            object_ids = normalized_ids or ['object_reference']
            if scene_ref_type == REF_TYPE.MIXED and 'object_reference' not in object_ids:
                object_ids.append('object_reference')
            for object_id in object_ids:
                if object_id in object_id_to_image:
                    append_ref(object_id_to_image[object_id])
            fallback_product = ref_mapping.get('fallback_product_image')
            if scene_ref_type == REF_TYPE.MIXED and fallback_product:
                append_ref(fallback_product)
            if ref_images:
                generation_mode = GEN_MODE.MULTI_IMAGE_FUSION if len(ref_images) > 1 else GEN_MODE.IMAGE_TO_IMAGE
            else:
                logger.warning(f"⚠️ 场景{scene_index}需要物体参考图{object_ids}，但未找到，降级为文生图")
            return ref_images, generation_mode

        if scene_ref_type == REF_TYPE.STYLE:
            return ref_images, generation_mode

        if scene_ref_type == REF_TYPE.CHARACTER:
            logger.warning(f"⚠️ 场景{scene_index}需要角色参考图但未配置reference_ids，降级为文生图")
        else:
            logger.warning(f"⚠️ 场景{scene_index}参考类型{scene_ref_type}不支持或未配置参考图，使用文生图")

        return ref_images, generation_mode
