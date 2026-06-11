#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文案生成工具
根据参考文案和视频storyboard内容，生成新的社交媒体文案
"""

import os
import json
import requests
from pathlib import Path
from typing import Dict, Any, List
from src.logger import get_logger

logger = get_logger("copywriting_generator")


class CopywritingGeneratorTool:
    """文案生成工具
    
    根据参考文案和视频分镜内容，使用大模型生成新的社交媒体文案
    不需要分析视频，只基于文本内容生成
    """
    
    def __init__(self):
        logger.info("初始化CopywritingGeneratorTool")
    
    def generate_copywriting(
        self,
        reference_title: str,
        storyboard_path: str,
        platform: str = "douyin"
    ) -> Dict[str, Any]:
        """
        生成社交媒体文案
        
        Args:
            reference_title: 参考的原始文案标题
            storyboard_path: storyboard.json文件路径
            platform: 平台名称（douyin/kuaishou）
        
        Returns:
            生成结果字典
        """
        logger.info(f"🤖 开始生成{platform}文案")
        logger.info(f"📝 参考标题: {reference_title[:50]}...")
        
        try:
            # 1. 读取storyboard内容
            storyboard_content = self._load_storyboard(storyboard_path)
            
            # 2. 构建prompt
            prompt = self._build_prompt(reference_title, storyboard_content, platform)
            
            # 3. 调用大模型生成
            result = self._call_llm(prompt)
            
            logger.info("✅ 文案生成成功")
            return result
            
        except Exception as e:
            logger.error(f"❌ 文案生成失败: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'title': reference_title,  # 失败时返回原标题
                'tags': '#萌宠 #视频 #推荐'
            }
    
    def _load_storyboard(self, storyboard_path: str) -> Dict[str, Any]:
        """读取storyboard.json文件"""
        try:
            with open(storyboard_path, 'r', encoding='utf-8') as f:
                storyboard = json.load(f)
            
            logger.info(f"📖 读取storyboard成功，场景数: {len(storyboard)}")
            return storyboard
            
        except Exception as e:
            logger.error(f"❌ 读取storyboard失败: {str(e)}")
            return []
    
    def _build_prompt(
        self,
        reference_title: str,
        storyboard: List[Dict],
        platform: str
    ) -> str:
        """构建生成文案的prompt"""
        
        platform_name = "抖音" if platform == "douyin" else "快手"
        
        # 提取storyboard中的关键信息
        scene_descriptions = []
        voiceovers = []
        
        for idx, scene in enumerate(storyboard, 1):
            scene_desc = scene.get('scene_description', '')
            voiceover = scene.get('voiceover_text', '')
            
            if scene_desc:
                scene_descriptions.append(f"场景{idx}: {scene_desc}")
            if voiceover:
                voiceovers.append(voiceover)
        
        # 合并所有配音文本
        full_voiceover = " ".join(voiceovers)
        
        # 构建prompt
        prompt = f"""你是一个专业的社交媒体文案策划师，擅长为{platform_name}平台创作吸引人的文案。

**任务：**
请根据以下信息，为一个视频生成新的{platform_name}文案（标题+标签）。注意不要和参考文案一样，要尽可能做比较大的修改，考虑重复度的问题。

**参考文案（对标）：**
{reference_title}

**视频内容概要：**
配音文案：{full_voiceover[:500]}...

画面描述：
{chr(10).join(scene_descriptions[:5])}

**要求：**
1. 参考对标文案的风格和调性，但要有创新
2. 结合视频实际内容，确保文案与画面相符
3. 文案要有吸引力，能引发用户互动
4. 融入当前流行的话题和表达方式
5. 生成1条主文案和3-5个相关标签

**返回格式（JSON）：**
{{
  "title": "主文案内容，要简洁有力，吸引眼球",
  "tags": ["标签1", "标签2", "标签3", "标签4", "标签5"],
  "full_copywriting": "完整文案（标题+标签组合）"
}}

请直接返回JSON格式，不要有其他文字。"""
        
        return prompt
    
    def _call_llm(self, prompt: str) -> Dict[str, Any]:
        """调用大模型API生成文案"""
        
        try:
            # 使用项目中的CREW配置
            api_key = os.getenv("CREW_API_KEY")
            api_base = os.getenv("CREW_BASE_URL")
            model = os.getenv("CREW_MODEL_NAME")
            
            if not api_key or not api_base or not model:
                raise ValueError("缺少必要的环境变量: CREW_API_KEY, CREW_BASE_URL, CREW_MODEL_NAME")
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            data = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的社交媒体文案策划师，擅长创作吸引人的文案。请只返回JSON格式的结果。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.8,
                "response_format": {"type": "json_object"}  # 强制返回JSON
            }
            
            logger.info(f"🚀 调用LLM API生成文案...")
            logger.info(f"   API Base: {api_base}")
            logger.info(f"   模型: {model}")
            
            response = requests.post(
                f"{api_base}/chat/completions",
                headers=headers,
                json=data,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            
            # 解析返回结果
            content = result['choices'][0]['message']['content']
            logger.debug(f"LLM返回: {content}")
            
            # 解析JSON
            parsed_result = json.loads(content)
            
            # 格式化返回结果
            title = parsed_result.get('title', '')
            tags = parsed_result.get('tags', [])
            
            # 组合成完整文案
            tags_str = '  '.join([f"#{tag}" if not tag.startswith('#') else tag for tag in tags])
            full_copywriting = f"{title}\n\n{tags_str}"
            
            logger.info(f"✅ LLM生成成功")
            logger.info(f"   标题: {title}")
            logger.info(f"   标签: {tags_str}")
            
            return {
                'success': True,
                'title': title,
                'tags': tags_str,
                'full_copywriting': full_copywriting,
                'raw_response': parsed_result
            }
            
        except Exception as e:
            logger.error(f"❌ 调用LLM失败: {str(e)}")
            raise


def generate_copywriting_from_storyboard(
    reference_title: str,
    storyboard_path: str,
    platform: str = "douyin"
) -> Dict[str, Any]:
    """
    便捷函数：根据参考文案和storyboard生成新文案
    
    Args:
        reference_title: 参考的原始文案标题
        storyboard_path: storyboard.json文件路径
        platform: 平台名称（douyin/kuaishou）
    
    Returns:
        生成结果字典，包含 title, tags, full_copywriting
    """
    tool = CopywritingGeneratorTool()
    return tool.generate_copywriting(reference_title, storyboard_path, platform)


if __name__ == "__main__":
    # 测试示例
    reference_title = "⚠️冬天猫咪蕞害怕的6件事🥶 哈#猫咪冬天 #冬天养猫 #猫咪迷惑行为"
    storyboard_path = "output/animation_copywriting/20251221_013331_71ce/storyboard.json"
    
    result = generate_copywriting_from_storyboard(reference_title, storyboard_path)
    
    print("\n生成结果：")
    print(f"标题: {result.get('title')}")
    print(f"标签: {result.get('tags')}")
    print(f"\n完整文案:\n{result.get('full_copywriting')}")

