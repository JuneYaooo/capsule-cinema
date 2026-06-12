#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视觉风格提取工具
使用多模态模型从参考图片中提取 visual_style 配置
"""

import os
import base64
import json
import yaml
from typing import Dict, List, Optional
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime

from src.logger import get_logger

load_dotenv()
logger = get_logger('style_extractor')


class StyleExtractor:
    """视觉风格提取器 - 从参考图片提取 visual_style 配置"""

    def __init__(self):
        """初始化多模态客户端"""
        self.api_key = os.getenv("MULTIMODAL_API_KEY")
        self.base_url = os.getenv("MULTIMODAL_BASE_URL")
        self.model_name = os.getenv("MULTIMODAL_MODEL_NAME")

        if not self.api_key or not self.base_url or not self.model_name:
            raise ValueError("请设置环境变量: MULTIMODAL_API_KEY, MULTIMODAL_BASE_URL, MULTIMODAL_MODEL_NAME")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

        logger.info(f"视觉风格提取器初始化成功 (模型: {self.model_name})")

    def extract_from_single_image(self, image_path: str) -> Dict:
        """
        从单张图片提取视觉风格

        Args:
            image_path: 图片路径

        Returns:
            风格提取结果字典，包含 visual_style 配置
        """
        if not Path(image_path).exists():
            logger.error(f"图片不存在: {image_path}")
            return {
                'status': 'error',
                'error': f'图片不存在: {image_path}'
            }

        try:
            # 读取图片并转为base64
            with open(image_path, 'rb') as f:
                image_data = f.read()
                image_base64 = base64.b64encode(image_data).decode('utf-8')

            # 根据文件扩展名确定MIME类型
            ext = Path(image_path).suffix.lower()
            mime_types = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.webp': 'image/webp'
            }
            mime_type = mime_types.get(ext, 'image/png')

            # 构建提示词
            prompt = self._build_extraction_prompt()

            logger.info(f"🎨 开始提取视觉风格: {Path(image_path).name}")

            # 调用多模态模型
            response = self.client.chat.completions.create(
                model=self.model_name,
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
                max_tokens=3000,
                response_format={"type": "json_object"}
            )

            # 解析响应
            response_content = response.choices[0].message.content
            result = json.loads(response_content)

            logger.info(f"✅ 风格提取完成: {Path(image_path).name}")
            if 'style_name' in result:
                logger.info(f"   风格名称: {result.get('style_name', '未知')}")

            return {
                'status': 'success',
                'image_path': image_path,
                'visual_style': result.get('visual_style', {}),
                'style_name': result.get('style_name', '提取的风格'),
                'style_description': result.get('style_description', '')
            }

        except Exception as e:
            logger.error(f"风格提取失败 {Path(image_path).name}: {str(e)}")
            return {
                'status': 'error',
                'image_path': image_path,
                'error': str(e)
            }

    def extract_from_multiple_images(self, image_paths: List[str]) -> Dict:
        """
        从多张图片提取并合成统一的视觉风格

        Args:
            image_paths: 图片路径列表

        Returns:
            合成的风格配置字典
        """
        if not image_paths:
            return {
                'status': 'error',
                'error': '未提供图片路径'
            }

        logger.info(f"🎨 开始从 {len(image_paths)} 张图片提取风格...")

        # 提取每张图片的风格
        individual_styles = []
        for image_path in image_paths:
            result = self.extract_from_single_image(image_path)
            if result.get('status') == 'success':
                individual_styles.append(result)

        if not individual_styles:
            return {
                'status': 'error',
                'error': '所有图片风格提取失败'
            }

        logger.info(f"✅ 成功提取 {len(individual_styles)}/{len(image_paths)} 张图片的风格")

        # 如果只有一张图片，直接返回
        if len(individual_styles) == 1:
            return individual_styles[0]

        # 合成多张图片的风格
        logger.info("🔄 合成统一风格配置...")
        merged_style = self._merge_styles(individual_styles)

        return {
            'status': 'success',
            'visual_style': merged_style,
            'style_name': '合成风格',
            'style_description': f'从 {len(individual_styles)} 张参考图合成的统一风格',
            'source_count': len(individual_styles)
        }

    def generate_clean_style_reference(
        self,
        user_style_image_path: str,
        output_path: str,
        image_engine: str = "seedream5"
    ) -> Dict:
        """
        根据用户风格图生成纯净的风格参考图（环境图，无具体主体）

        Args:
            user_style_image_path: 用户提供的风格参考图路径
            output_path: 输出图片路径
            image_engine: 图片生成引擎

        Returns:
            生成结果字典
        """
        logger.info(f"🎨 开始生成纯净风格参考图...")
        logger.info(f"   源图片: {Path(user_style_image_path).name}")

        try:
            # 1. 先提取风格特征
            style_result = self.extract_from_single_image(user_style_image_path)
            if style_result.get('status') != 'success':
                return {
                    'status': 'error',
                    'error': f'风格提取失败: {style_result.get("error")}'
                }

            visual_style = style_result['visual_style']

            # 2. 构建纯净环境图的prompt
            prompt = self._build_clean_environment_prompt(visual_style)

            logger.info(f"   生成prompt: {prompt[:100]}...")

            # 3. 调用图片生成引擎
            from custom_tools.image_generation.image_generator_factory import ImageGeneratorFactory

            generator = ImageGeneratorFactory.create_generator(image_engine)

            # 使用图生图模式，以用户风格图为参考
            generation_result = generator.generate(
                prompt=prompt,
                output_path=output_path,
                aspect_ratio="16:9",  # 环境图通常用横版
                reference_image=user_style_image_path,  # 使用用户图作为风格参考
                reference_weight=0.6  # 中等权重，保持风格但不复制内容
            )

            if generation_result.get('success'):
                logger.info(f"✅ 纯净风格参考图生成成功: {output_path}")
                return {
                    'status': 'success',
                    'image_path': output_path,
                    'visual_style': visual_style,
                    'prompt': prompt
                }
            else:
                error_msg = generation_result.get('error', '未知错误')
                logger.error(f"❌ 风格参考图生成失败: {error_msg}")
                return {
                    'status': 'error',
                    'error': error_msg
                }

        except Exception as e:
            logger.error(f"生成风格参考图时出错: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return {
                'status': 'error',
                'error': str(e)
            }

    def _build_clean_environment_prompt(self, visual_style: Dict) -> str:
        """
        根据提取的visual_style构建纯净环境图的prompt

        Args:
            visual_style: 提取的风格配置

        Returns:
            图片生成prompt
        """
        # 提取关键特征
        colors = visual_style.get('颜色', {})
        main_colors = colors.get('主色调', [])
        aux_colors = colors.get('辅助色', [])
        atmosphere = colors.get('氛围特征', '')

        composition = visual_style.get('构图', {})
        comp_type = composition.get('类型', '三分构图')
        perspective = composition.get('视角', '平视')

        effects = visual_style.get('特效', {})
        texture = effects.get('质感', '')
        effect_elements = effects.get('元素', [])

        # 构建prompt：纯净的环境场景，没有具体主体
        prompt_parts = []

        # 1. 场景类型（抽象的环境）
        prompt_parts.append("纯净的环境场景")

        # 2. 色彩描述
        if main_colors:
            colors_str = "、".join(main_colors[:3])
            prompt_parts.append(f"主要色调为{colors_str}")

        if aux_colors:
            aux_str = "、".join(aux_colors[:2])
            prompt_parts.append(f"辅以{aux_str}")

        # 3. 氛围
        if atmosphere:
            prompt_parts.append(f"{atmosphere}的氛围")

        # 4. 构图和视角
        prompt_parts.append(f"{comp_type}")
        if perspective:
            prompt_parts.append(f"{perspective}视角")

        # 5. 质感和特效
        if texture:
            prompt_parts.append(f"{texture}")

        if effect_elements:
            effects_str = "、".join(effect_elements[:3])
            prompt_parts.append(f"带有{effects_str}")

        # 6. 重要约束
        prompt_parts.append("画面干净简洁")
        prompt_parts.append("没有具体的人物或动物主体")
        prompt_parts.append("只有抽象的环境元素和氛围")

        prompt = "，".join(prompt_parts) + "。"

        return prompt

    def save_style_to_yaml(
        self,
        visual_style: Dict,
        output_path: str,
        style_name: str = "自定义风格",
        style_code: str = "custom_style"
    ) -> str:
        """
        将提取的风格保存为 YAML 文件

        Args:
            visual_style: 风格配置字典
            output_path: 输出文件路径
            style_name: 风格名称
            style_code: 风格代码

        Returns:
            保存的文件路径
        """
        try:
            style_data = {
                'style_name': style_name,
                'style_code': style_code,
                'visual_style': visual_style,
                'created_at': datetime.now().isoformat(),
                'source': 'extracted_from_images'
            }

            # 确保输出目录存在
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            # 保存为 YAML
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(style_data, f, allow_unicode=True, default_flow_style=False)

            logger.info(f"✅ 风格配置已保存: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"保存风格配置失败: {str(e)}")
            raise

    def _build_extraction_prompt(self) -> str:
        """构建风格提取提示词"""
        return """请分析这张图片的视觉风格，提取以下维度的特征，返回JSON格式。

🚨 **【核心原则】：只提取抽象的、可复用的风格特征，严禁包含具体的画面主体！**

❌ **禁止包含的内容**（这是最重要的规则！）：
- 画面中的具体主体（如"仓鼠"、"猫"、"人物"、"汽车"等任何具体物体）
- 具体的物体名称（如"自行车"、"树木"、"房子"、"建筑"等）
- 场景中的具体元素（如"草地"、"窗户"、"桌子"、"地面"等）
- **特别注意**：装饰性元素也要抽象化（如"云朵"→"浮动元素"、"树木"→"垂直元素"、"草地"→"底部铺陈"）

✅ **应该提取的内容**：
- 抽象的色彩运用（如"暖色调"、"高饱和度"）
- 通用的布局规律（如"三分构图"、"对称布局"）
- 可复用的视觉效果（如"柔和光影"、"手绘线条"）
- 艺术表现手法（如"水彩质感"、"3D立体感"）

【分析维度】：

1. **颜色** - 分析色彩使用
   - 主色调：主要使用的3-5种颜色（用中文色彩名称描述，如"天空蓝"、"森林绿"、"暖阳黄"）
   - 辅助色：辅助使用的2-3种颜色（如"珍珠白"、"草木青"、"柔和粉"）
   - 氛围特征：用一句话描述整体色彩氛围（如"清新自然"、"浓郁厚重"、"柔和温暖"）
   ⚠️ 注意：只描述颜色本身，不要提及具体物体
   ⚠️ 严禁：辅助色不要用具体物体命名（如避免"云朵白"，应用"珍珠白"、"纯白"、"乳白"）

2. **排版** - 分析元素布局的抽象规律
   - 元素布局：通用的布局方式（如"居中对称"、"自然和谐"、"左右平衡"）
   - 层次关系：通用的层次感描述（如"前景-中景-背景层次分明"、"扁平化设计"）
   ⚠️ 注意：不要提及具体物体，只描述布局规律。装饰元素要抽象化。
   例如：
   - ✅ "主体位于画面下方，上方留白分布轻盈装饰元素"
   - ❌ "小仓鼠位于画面下方，云朵分布在上半部分"
   - ✅ "上方区域有浮动的装饰性元素，形成空间层次"
   - ❌ "上方区域有白色云朵飘浮"

3. **构图** - 分析画面构图的抽象规律
   - 类型：构图类型（如"对称式构图"、"三角形构图"、"黄金分割"）
   - 特征：构图的抽象特点（不涉及具体物体）
   - 视角：观察视角（如"平视"、"俯视"、"仰视"、"鸟瞰"）
   ⚠️ 注意：用"主体"、"元素"等通用词汇，不要具体化

4. **特效** - 分析视觉效果
   - 元素：列出2-5个视觉特效元素（如"光影效果"、"粒子效果"、"手绘线条"、"柔和模糊"、"景深虚化"）
   - 质感：画面的质感描述（如"手绘水彩质感"、"3D立体质感"、"扁平插画质感"）
   ⚠️ 注意：只描述技术效果和质感，不要关联具体物体
   ⚠️ 严禁：不要描述具体元素的质感（如"云朵立体感"、"树木纹理"），应描述整体画面质感（如"柔和立体感"、"细腻纹理"）

【返回JSON格式】：
{
  "style_name": "风格名称（简短描述，如'宫崎骏'、'赛博朋克'、'水彩插画'）",
  "style_description": "风格整体描述（一句话概括，不提及具体物体）",
  "visual_style": {
    "颜色": {
      "主色调": ["色彩1", "色彩2", "色彩3"],
      "辅助色": ["色彩1", "色彩2"],
      "氛围特征": "色彩氛围描述（不提及具体物体）"
    },
    "排版": {
      "元素布局": "通用布局方式描述（用'主体'、'元素'等通用词）",
      "层次关系": "通用层次关系描述（不提及具体物体）"
    },
    "构图": {
      "类型": "构图类型",
      "特征": "构图抽象特征（不提及具体物体）",
      "视角": "视角描述"
    },
    "特效": {
      "元素": ["特效1", "特效2", "特效3"],
      "质感": "质感描述（技术手法，不关联物体）"
    }
  }
}

【重要说明】：
- 所有描述用中文
- 色彩名称要具体生动（如"天空蓝"而非"蓝色"）
- 特征描述要准确、客观、抽象化
- **重点关注可以被复现到任何主题的视觉特征**
- **想象这个风格要用到猫、狗、人、车等完全不同的主题，你的描述应该通用适配**

【正确示例】：
✅ "主体位于画面下方三分之一处，上方留白形成平衡感"
❌ "小仓鼠位于画面下方三分之一处，云朵分布在上半部分"

✅ "柔和的光影过渡，营造温暖氛围"
❌ "阳光照在仓鼠的毛发上，云朵周围有柔和光晕"
"""

    def _merge_styles(self, style_results: List[Dict]) -> Dict:
        """
        合并多个风格配置为统一的风格

        Args:
            style_results: 多个风格提取结果

        Returns:
            合成的 visual_style 配置
        """
        # 提取所有 visual_style
        styles = [result['visual_style'] for result in style_results]

        # 合并颜色
        merged_colors = self._merge_colors([s.get('颜色', {}) for s in styles])

        # 合并排版（取最常见的）
        merged_layout = self._merge_layouts([s.get('排版', {}) for s in styles])

        # 合并构图（取最常见的）
        merged_composition = self._merge_compositions([s.get('构图', {}) for s in styles])

        # 合并特效
        merged_effects = self._merge_effects([s.get('特效', {}) for s in styles])

        return {
            '颜色': merged_colors,
            '排版': merged_layout,
            '构图': merged_composition,
            '特效': merged_effects
        }

    def _merge_colors(self, color_configs: List[Dict]) -> Dict:
        """合并颜色配置"""
        all_main_colors = []
        all_aux_colors = []
        all_atmospheres = []

        for config in color_configs:
            if '主色调' in config:
                main = config['主色调']
                if isinstance(main, list):
                    all_main_colors.extend(main)
                else:
                    all_main_colors.append(main)

            if '辅助色' in config:
                aux = config['辅助色']
                if isinstance(aux, list):
                    all_aux_colors.extend(aux)
                else:
                    all_aux_colors.append(aux)

            if '氛围特征' in config:
                all_atmospheres.append(config['氛围特征'])

        # 去重并取前几个
        unique_main = list(dict.fromkeys(all_main_colors))[:5]
        unique_aux = list(dict.fromkeys(all_aux_colors))[:3]

        # 合并氛围描述
        merged_atmosphere = "、".join(all_atmospheres) if all_atmospheres else ""

        return {
            '主色调': unique_main,
            '辅助色': unique_aux,
            '氛围特征': merged_atmosphere
        }

    def _merge_layouts(self, layout_configs: List[Dict]) -> Dict:
        """合并排版配置（取第一个非空）"""
        merged = {}

        for config in layout_configs:
            if '元素布局' in config and not merged.get('元素布局'):
                merged['元素布局'] = config['元素布局']
            if '层次关系' in config and not merged.get('层次关系'):
                merged['层次关系'] = config['层次关系']

        return merged

    def _merge_compositions(self, composition_configs: List[Dict]) -> Dict:
        """合并构图配置（取第一个非空）"""
        merged = {}

        for config in composition_configs:
            if '类型' in config and not merged.get('类型'):
                merged['类型'] = config['类型']
            if '特征' in config and not merged.get('特征'):
                merged['特征'] = config['特征']
            if '视角' in config and not merged.get('视角'):
                merged['视角'] = config['视角']

        return merged

    def _merge_effects(self, effects_configs: List[Dict]) -> Dict:
        """合并特效配置"""
        all_elements = []
        all_textures = []

        for config in effects_configs:
            if '元素' in config:
                elements = config['元素']
                if isinstance(elements, list):
                    all_elements.extend(elements)
                else:
                    all_elements.append(elements)

            if '质感' in config:
                all_textures.append(config['质感'])

        # 去重
        unique_elements = list(dict.fromkeys(all_elements))[:5]
        merged_texture = "、".join(all_textures) if all_textures else ""

        return {
            '元素': unique_elements,
            '质感': merged_texture
        }


def extract_style_from_images(
    image_paths: List[str],
    save_to_file: Optional[str] = None,
    style_name: str = "自定义风格"
) -> Dict:
    """
    便捷函数：从图片提取视觉风格

    Args:
        image_paths: 图片路径列表
        save_to_file: 可选，保存为YAML文件的路径
        style_name: 风格名称

    Returns:
        风格提取结果
    """
    extractor = StyleExtractor()

    # 提取风格
    result = extractor.extract_from_multiple_images(image_paths)

    if result.get('status') != 'success':
        return result

    # 如果指定了保存路径，保存为YAML
    if save_to_file:
        style_code = style_name.lower().replace(' ', '_').replace('自定义', 'custom')
        extractor.save_style_to_yaml(
            visual_style=result['visual_style'],
            output_path=save_to_file,
            style_name=style_name,
            style_code=style_code
        )

    return result


# ========== 用于测试的主函数 ==========
if __name__ == "__main__":
    import sys

    # 测试单张图片
    if len(sys.argv) > 1:
        test_images = sys.argv[1:]
        print(f"测试提取 {len(test_images)} 张图片的风格...")

        result = extract_style_from_images(
            image_paths=test_images,
            style_name="测试风格"
        )

        if result.get('status') == 'success':
            print("\n✅ 风格提取成功！")
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"\n❌ 风格提取失败: {result.get('error')}")
    else:
        print("用法: python style_extractor_tool.py <图片1> [图片2] [图片3] ...")
