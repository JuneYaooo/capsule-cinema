#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能风格创建工具
整合Web图片搜索、多模态理解、风格生成功能
当用户指定的风格不存在时，自动创建新风格YAML
"""

import os
import json
import base64
import requests
import tempfile
from typing import Any, Type, Dict, List, Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

from src.logger import get_logger
from custom_tools.utilities.searxng_web_search_tool import SearxngWebSearchListTool
from custom_tools.utilities.style_extractor_tool import StyleExtractor
from custom_tools.utilities.art_style_manager_tool import ArtStyleManagerTool

load_dotenv()
logger = get_logger('intelligent_style_creator')


class IntelligentStyleCreatorToolSchema(BaseModel):
    """Input for IntelligentStyleCreatorTool."""
    style_name: str = Field(
        description="风格名称（中文或英文），例如：'末日废土'、'赛博朋克'、'宫崎骏'、'水墨画'"
    )
    user_reference_images: List[str] = Field(
        default_factory=list,
        description="用户提供的参考图片路径列表（可选）。如果提供，将从这些图片中提取风格"
    )
    skip_web_search: bool = Field(
        default=False,
        description="是否跳过网络搜索。True表示直接生成风格（适用于常见风格），False表示先搜索参考图（适用于不确定的风格）"
    )


class IntelligentStyleCreatorTool(BaseTool):
    name: str = "Intelligent style creator - create art style with web search or direct generation"
    description: str = (
        "智能创建艺术风格配置的工具。支持三种模式：\n"
        "1. 从用户提供的参考图片提取风格（user_reference_images不为空）\n"
        "2. 通过网络搜索参考图片后提取风格（skip_web_search=False）\n"
        "3. 直接生成风格配置（skip_web_search=True，适用于常见风格）\n"
        "\n"
        "使用场景：\n"
        "- 用户指定的风格名称（如'末日废土'、'赛博朋克'）在现有风格库中不存在\n"
        "- 需要基于参考图片创建新风格\n"
        "- 需要智能判断是搜索参考图还是直接生成\n"
        "\n"
        "返回：包含 style_code, visual_style 等的完整风格配置"
    )
    args_schema: Type[BaseModel] = IntelligentStyleCreatorToolSchema

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 初始化多模态客户端
        self.api_key = os.getenv("MULTIMODAL_API_KEY")
        self.base_url = os.getenv("MULTIMODAL_BASE_URL")
        self.model_name = os.getenv("MULTIMODAL_MODEL_NAME")

        if not all([self.api_key, self.base_url, self.model_name]):
            logger.warning("多模态配置不完整，将仅使用直接生成模式")
            self.multimodal_available = False
        else:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            self.multimodal_available = True
            logger.info(f"多模态客户端初始化成功 (模型: {self.model_name})")

        # 初始化工具
        self.search_tool = SearxngWebSearchListTool()
        self.style_extractor = StyleExtractor() if self.multimodal_available else None
        self.art_style_manager = ArtStyleManagerTool()

        logger.info("智能风格创建工具初始化完成")

    def _run(
        self,
        style_name: str,
        user_reference_images: List[str] = None,
        skip_web_search: bool = False
    ) -> Dict[str, Any]:
        """
        智能创建艺术风格

        Args:
            style_name: 风格名称
            user_reference_images: 用户提供的参考图片路径列表
            skip_web_search: 是否跳过网络搜索

        Returns:
            风格配置字典
        """
        if not user_reference_images:
            user_reference_images = []

        logger.info(f"🎨 开始智能创建风格: {style_name}")
        logger.info(f"   用户参考图: {len(user_reference_images)} 张")
        logger.info(f"   跳过搜索: {skip_web_search}")

        try:
            # 模式1: 用户提供了参考图片 - 优先级最高
            if user_reference_images:
                logger.info("📸 模式1: 从用户提供的参考图片提取风格")
                return self._create_from_user_images(style_name, user_reference_images)

            # 模式2: 网络搜索参考图片
            if not skip_web_search and self.multimodal_available:
                logger.info("🔍 模式2: 通过网络搜索参考图片后提取风格")
                return self._create_from_web_search(style_name)

            # 模式3: 直接生成风格配置
            logger.info("🤖 模式3: 直接生成风格配置（LLM理解）")
            return self._create_directly(style_name)

        except Exception as e:
            logger.error(f"创建风格失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': f"创建风格失败: {str(e)}"
            }

    def _create_from_user_images(self, style_name: str, image_paths: List[str]) -> Dict:
        """
        从用户提供的参考图片提取风格

        Args:
            style_name: 风格名称
            image_paths: 图片路径列表

        Returns:
            风格配置字典
        """
        if not self.multimodal_available:
            logger.error("多模态功能不可用，无法从图片提取风格")
            return {
                'success': False,
                'error': '多模态功能不可用，请配置 MULTIMODAL_API_KEY 等环境变量'
            }

        try:
            # 使用 StyleExtractor 提取风格
            extraction_result = self.style_extractor.extract_from_multiple_images(image_paths)

            if extraction_result.get('status') != 'success':
                logger.error(f"风格提取失败: {extraction_result.get('error')}")
                return {
                    'success': False,
                    'error': f"风格提取失败: {extraction_result.get('error')}"
                }

            visual_style = extraction_result['visual_style']
            style_description = extraction_result.get('style_description', f'{style_name}风格')

            # 生成 style_code
            style_code = self._generate_style_code(style_name)

            # 使用 ArtStyleManagerTool 创建 YAML 文件
            create_result = self.art_style_manager._run(
                action='create',
                style_code=style_code,
                style_config={
                    'style_name': style_name,
                    'style_description': style_description,
                    'visual_style': visual_style
                }
            )

            if not create_result.get('success'):
                return create_result

            logger.info(f"✅ 成功从用户图片创建风格: {style_name}")
            return {
                'success': True,
                'style_code': style_code,
                'style_name': style_name,
                'visual_style': visual_style,
                'style_description': style_description,
                'creation_mode': 'user_images',
                'file_path': create_result.get('file_path')
            }

        except Exception as e:
            logger.error(f"从用户图片创建风格失败: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _create_from_web_search(self, style_name: str) -> Dict:
        """
        通过网络搜索参考图片后提取风格

        Args:
            style_name: 风格名称

        Returns:
            风格配置字典
        """
        try:
            # 构建搜索查询（中英文双语）
            search_query = f"{style_name} 风格 艺术 art style visual"
            logger.info(f"🔍 搜索关键词: {search_query}")

            # 搜索图片
            image_results = self.search_tool.search_image(
                query=search_query,
                max_results=10
            )

            if not image_results:
                logger.warning("未搜索到参考图片，切换到直接生成模式")
                return self._create_directly(style_name)

            logger.info(f"✅ 搜索到 {len(image_results)} 张参考图片")

            # 下载图片（最多5张）
            downloaded_images = []
            temp_dir = tempfile.mkdtemp(prefix='style_ref_')

            for i, img_result in enumerate(image_results[:5]):
                try:
                    img_url = img_result.get('img_src')
                    if not img_url:
                        continue

                    logger.info(f"   下载图片 {i+1}: {img_result.get('title', 'untitled')}")

                    response = requests.get(img_url, timeout=10)
                    if response.status_code == 200:
                        # 保存到临时文件
                        temp_img_path = Path(temp_dir) / f"ref_{i}.jpg"
                        with open(temp_img_path, 'wb') as f:
                            f.write(response.content)

                        downloaded_images.append(str(temp_img_path))
                        logger.info(f"   ✅ 下载成功: {temp_img_path}")

                except Exception as e:
                    logger.warning(f"   下载图片失败: {str(e)}")
                    continue

            if not downloaded_images:
                logger.warning("所有图片下载失败，切换到直接生成模式")
                return self._create_directly(style_name)

            logger.info(f"✅ 成功下载 {len(downloaded_images)} 张参考图片")

            # 使用下载的图片提取风格
            result = self._create_from_user_images(style_name, downloaded_images)

            # 更新创建模式标识
            if result.get('success'):
                result['creation_mode'] = 'web_search'

            # 清理临时文件
            try:
                import shutil
                shutil.rmtree(temp_dir)
                logger.info(f"✅ 清理临时目录: {temp_dir}")
            except Exception as e:
                logger.warning(f"清理临时目录失败: {str(e)}")

            return result

        except Exception as e:
            logger.error(f"从网络搜索创建风格失败: {str(e)}")
            logger.warning("切换到直接生成模式")
            return self._create_directly(style_name)

    def _create_directly(self, style_name: str) -> Dict:
        """
        直接生成风格配置（基于LLM的风格知识）

        Args:
            style_name: 风格名称

        Returns:
            风格配置字典
        """
        try:
            logger.info(f"🤖 直接生成风格: {style_name}")

            # 构建风格生成提示词
            prompt = self._build_direct_generation_prompt(style_name)

            if self.multimodal_available:
                # 使用多模态模型（文本模式）
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    max_tokens=2000,
                    response_format={"type": "json_object"}
                )

                response_content = response.choices[0].message.content
                result = json.loads(response_content)

            else:
                # 降级：使用预定义的风格模板
                logger.warning("多模态不可用，使用预定义模板")
                result = self._get_fallback_template(style_name)

            visual_style = result.get('visual_style', {})
            style_description = result.get('style_description', f'{style_name}风格')

            # 生成 style_code
            style_code = self._generate_style_code(style_name)

            # 使用 ArtStyleManagerTool 创建 YAML 文件
            create_result = self.art_style_manager._run(
                action='create',
                style_code=style_code,
                style_config={
                    'style_name': style_name,
                    'style_description': style_description,
                    'visual_style': visual_style
                }
            )

            if not create_result.get('success'):
                return create_result

            logger.info(f"✅ 成功直接生成风格: {style_name}")
            return {
                'success': True,
                'style_code': style_code,
                'style_name': style_name,
                'visual_style': visual_style,
                'style_description': style_description,
                'creation_mode': 'direct_generation',
                'file_path': create_result.get('file_path')
            }

        except Exception as e:
            logger.error(f"直接生成风格失败: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _build_direct_generation_prompt(self, style_name: str) -> str:
        """构建直接生成风格的提示词"""
        return f"""请根据风格名称「{style_name}」，生成对应的视觉风格配置。

【任务说明】：
你需要基于对「{style_name}」风格的理解，生成一套完整的视觉风格配置。这套配置将用于指导AI图片和视频的生成。

【风格维度】：

1. **颜色** - 这个风格典型的色彩使用
   - 主色调：3-5种主要颜色（用中文色彩名称，如"深灰色"、"锈红色"、"暗黄色"）
   - 辅助色：2-3种辅助颜色
   - 氛围特征：一句话描述色彩氛围（如"灰暗压抑"、"明亮活泼"、"柔和温馨"）

2. **排版** - 元素布局特点
   - 元素布局：这个风格典型的布局方式
   - 层次关系：画面的层次感特点

3. **构图** - 构图特点
   - 类型：典型的构图类型
   - 特征：构图的主要特征
   - 视角：常用的观察视角

4. **特效** - 视觉效果特点
   - 元素：2-5个典型的视觉特效元素（如"粗糙的质感纹理"、"强烈的明暗对比"）
   - 质感：画面的质感描述（如"粗糙、破败"、"光滑、精致"）

【返回JSON格式】：
{{
  "style_description": "对{style_name}风格的整体描述（一句话概括特点和氛围）",
  "visual_style": {{
    "颜色": {{
      "主色调": ["色彩1", "色彩2", "色彩3", "色彩4"],
      "辅助色": ["色彩1", "色彩2", "色彩3"],
      "氛围特征": "色彩氛围描述"
    }},
    "排版": {{
      "元素布局": "布局方式描述",
      "层次关系": "层次关系描述"
    }},
    "构图": {{
      "类型": "构图类型",
      "特征": "构图特征描述",
      "视角": "视角描述"
    }},
    "特效": {{
      "元素": ["特效1", "特效2", "特效3", "特效4"],
      "质感": "质感描述"
    }}
  }}
}}

【重要说明】：
- 所有描述用中文
- 色彩名称要具体生动（如"锈红色"而非"红色"）
- 特征描述要准确反映{style_name}风格的特点
- 重点关注可以被AI复现的视觉特征
- 如果不确定某个风格，可以基于常见认知进行合理推断
"""

    def _get_fallback_template(self, style_name: str) -> Dict:
        """获取降级模板（当多模态不可用时）"""
        # 预定义一些常见风格的模板
        templates = {
            "末日废土": {
                "style_description": "末日废土风格，荒凉破败的世界观，充满绝望与希望并存的氛围",
                "visual_style": {
                    "颜色": {
                        "主色调": ["灰褐色", "锈红色", "暗黄色", "钢铁灰"],
                        "辅助色": ["破败绿", "沙尘黄", "血污红"],
                        "氛围特征": "灰暗压抑，色彩饱和度低，充满末日感"
                    },
                    "排版": {
                        "元素布局": "破败感的非对称布局，残缺与完整对比",
                        "层次关系": "荒凉的远景-破败的中景-细节化的前景"
                    },
                    "构图": {
                        "类型": "末日废墟构图",
                        "特征": "广角展现荒凉景观，强调破败与孤独",
                        "视角": "略带俯视或平视，展现世界的残酷"
                    },
                    "特效": {
                        "元素": ["粗糙的质感纹理", "强烈的明暗对比", "灰尘与雾霾效果", "锈蚀与风化痕迹"],
                        "质感": "粗糙、破败、充满岁月痕迹"
                    }
                }
            },
            "赛博朋克": {
                "style_description": "赛博朋克风格，高科技与低生活的反差，霓虹灯光与黑暗街道的对比",
                "visual_style": {
                    "颜色": {
                        "主色调": ["霓虹粉", "电光蓝", "紫色", "深黑色"],
                        "辅助色": ["荧光绿", "橙红色", "冷白色"],
                        "氛围特征": "高饱和霓虹色彩与暗黑色调强烈对比"
                    },
                    "排版": {
                        "元素布局": "密集、混乱的城市布局，充满科技感",
                        "层次关系": "多层次的城市景观，上下纵深感强"
                    },
                    "构图": {
                        "类型": "未来都市构图",
                        "特征": "仰视角度展现高耸建筑，俯视展现拥挤街道",
                        "视角": "极端视角（仰视或俯视）"
                    },
                    "特效": {
                        "元素": ["霓虹灯光效果", "全息投影", "雨水反光", "数字扫描线"],
                        "质感": "光滑金属与粗糙混凝土对比，湿润反光"
                    }
                }
            }
        }

        # 如果有匹配的模板，返回；否则返回通用模板
        if style_name in templates:
            return templates[style_name]

        # 通用模板
        return {
            "style_description": f"{style_name}风格，独特的视觉表现",
            "visual_style": {
                "颜色": {
                    "主色调": ["色彩1", "色彩2", "色彩3"],
                    "辅助色": ["色彩4", "色彩5"],
                    "氛围特征": "整体色彩氛围"
                },
                "排版": {
                    "元素布局": "元素布局方式",
                    "层次关系": "层次关系描述"
                },
                "构图": {
                    "类型": "构图类型",
                    "特征": "构图特征",
                    "视角": "视角描述"
                },
                "特效": {
                    "元素": ["特效1", "特效2", "特效3"],
                    "质感": "质感描述"
                }
            }
        }

    def _generate_style_code(self, style_name: str) -> str:
        """
        生成风格代码（英文小写+下划线）

        Args:
            style_name: 风格名称

        Returns:
            风格代码
        """
        # 中文风格名称翻译映射
        translations = {
            "末日废土": "post_apocalyptic",
            "赛博朋克": "cyberpunk",
            "宫崎骏": "miyazaki",
            "水墨画": "ink_painting",
            "油画": "oil_painting",
            "水彩": "watercolor",
            "素描": "sketch",
            "卡通": "cartoon",
            "写实": "realistic",
            "抽象": "abstract",
            "极简": "minimalist",
            "复古": "retro",
            "未来": "futuristic",
            "哥特": "gothic",
            "蒸汽朋克": "steampunk",
        }

        # 如果有现成的翻译，使用翻译
        for cn, en in translations.items():
            if cn in style_name:
                return f"{en}_style"

        # 否则，转换为拼音或保留英文
        import re
        # 移除特殊字符，保留字母数字和空格
        cleaned = re.sub(r'[^\w\s]', '', style_name)
        # 转为小写，空格替换为下划线
        style_code = cleaned.lower().replace(' ', '_').replace('风格', '').strip('_')

        return f"{style_code}_style" if style_code else "custom_style"


# ========== 便捷函数 ==========

def create_style_intelligently(
    style_name: str,
    user_reference_images: List[str] = None,
    skip_web_search: bool = False
) -> Dict:
    """
    便捷函数：智能创建艺术风格

    Args:
        style_name: 风格名称
        user_reference_images: 用户提供的参考图片路径列表
        skip_web_search: 是否跳过网络搜索

    Returns:
        风格配置字典
    """
    tool = IntelligentStyleCreatorTool()
    return tool._run(
        style_name=style_name,
        user_reference_images=user_reference_images or [],
        skip_web_search=skip_web_search
    )


# ========== 测试代码 ==========
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python intelligent_style_creator_tool.py <风格名称> [--skip-search] [--images <图片1> <图片2> ...]")
        print("\n示例:")
        print("  # 网络搜索模式")
        print("  python intelligent_style_creator_tool.py 末日废土")
        print("\n  # 直接生成模式")
        print("  python intelligent_style_creator_tool.py 赛博朋克 --skip-search")
        print("\n  # 用户图片模式")
        print("  python intelligent_style_creator_tool.py 自定义风格 --images ref1.jpg ref2.jpg")
        sys.exit(1)

    style_name = sys.argv[1]
    skip_search = '--skip-search' in sys.argv

    # 解析图片参数
    user_images = []
    if '--images' in sys.argv:
        images_idx = sys.argv.index('--images') + 1
        user_images = [arg for arg in sys.argv[images_idx:] if not arg.startswith('--')]

    print(f"\n🎨 测试智能风格创建工具")
    print(f"   风格名称: {style_name}")
    print(f"   跳过搜索: {skip_search}")
    print(f"   用户图片: {len(user_images)} 张")
    print()

    result = create_style_intelligently(
        style_name=style_name,
        user_reference_images=user_images,
        skip_web_search=skip_search
    )

    if result.get('success'):
        print("\n✅ 风格创建成功！")
        print(f"   风格代码: {result.get('style_code')}")
        print(f"   创建模式: {result.get('creation_mode')}")
        print(f"   文件路径: {result.get('file_path')}")
        print(f"\n风格配置:")
        print(json.dumps(result.get('visual_style'), ensure_ascii=False, indent=2))
    else:
        print(f"\n❌ 风格创建失败: {result.get('error')}")
