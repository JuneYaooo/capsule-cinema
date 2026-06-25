#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
社交媒体视频文案生成工具
支持为视频生成抖音、快手等平台的文案、标签和神评论
"""

from typing import Any, Type, Dict, Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
import os
import json
import base64
import requests
import subprocess
from pathlib import Path
from src.logger import get_logger

# 初始化日志记录器
logger = get_logger("social_media_copywriting")


class SocialMediaCopywritingToolSchema(BaseModel):
    """Input for SocialMediaCopywritingTool."""
    video_path: str = Field(
        ..., description="视频文件路径"
    )
    video_info: Dict[str, Any] = Field(
        default_factory=dict,
        description="视频相关信息，如主题、风格、设计理念等"
    )
    platform: str = Field(
        default="douyin",
        description="社交媒体平台，可选: douyin(抖音), kuaishou(快手)"
    )
    output_dir: str = Field(
        ..., description="输出目录路径"
    )


class SocialMediaCopywritingTool(BaseTool):
    """社交媒体视频文案生成工具
    
    使用Gemini分析视频内容，为抖音、快手等平台生成：
    1. 5组文案（每组包含文案内容和标签）
    2. 10条神评论
    """
    
    name: str = "Generate social media copywriting for video"
    description: str = (
        "分析视频内容，为社交媒体平台（抖音、快手等）生成吸引人的文案、标签和神评论。"
    )
    args_schema: Type[BaseModel] = SocialMediaCopywritingToolSchema

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info("初始化SocialMediaCopywritingTool")

    def _run(
        self,
        video_path: str,
        video_info: Dict[str, Any] = None,
        platform: str = "douyin",
        output_dir: str = None
    ) -> Dict[str, Any]:
        """
        生成社交媒体文案
        
        Args:
            video_path: 视频文件路径
            video_info: 视频相关信息
            platform: 平台名称（douyin/kuaishou）
            output_dir: 输出目录
            
        Returns:
            生成结果字典
        """
        logger.info(f"🤖 开始为视频生成{platform}文案: {video_path}")
        
        if video_info is None:
            video_info = {}
        
        try:
            # 1. 压缩视频用于分析
            compressed_video = self._compress_video_for_analysis(video_path)
            
            # 2. 调用Gemini分析视频
            analysis_result = self._analyze_video_with_gemini(
                compressed_video,
                video_info,
                platform
            )
            
            # 3. 保存结果
            if output_dir:
                saved_path = self._save_copywriting_result(
                    analysis_result,
                    output_dir,
                    platform
                )
                analysis_result['saved_path'] = saved_path
            
            # 4. 清理临时文件
            self._cleanup_temp_files(compressed_video, video_path)
            
            logger.info(f"✅ {platform}文案生成完成")
            return analysis_result
            
        except Exception as e:
            error_msg = f"文案生成失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "copywriting": [],
                "comments": []
            }

    def _compress_video_for_analysis(self, video_path: str, target_size_mb: int = 10) -> str:
        """压缩视频到指定大小以下，用于Gemini分析"""
        logger.info(f"🗜️ 开始压缩视频用于分析: {video_path}")
        
        try:
            # 创建临时压缩文件路径
            video_dir = os.path.dirname(video_path)
            compressed_path = os.path.join(video_dir, "compressed_for_analysis.mp4")
            
            # 获取原视频文件大小
            original_size = os.path.getsize(video_path) / (1024 * 1024)  # MB
            logger.info(f"📊 原视频大小: {original_size:.2f} MB")
            
            if original_size <= target_size_mb:
                # 如果原视频已经小于目标大小，直接复制
                import shutil
                shutil.copy2(video_path, compressed_path)
                logger.info(f"✅ 原视频已小于 {target_size_mb}MB，无需压缩")
                return compressed_path
            
            # 获取视频时长
            duration_cmd = [
                "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", video_path
            ]
            duration_result = subprocess.run(duration_cmd, capture_output=True, text=True, check=True)
            duration = float(duration_result.stdout.strip())
            
            # 计算目标比特率 (kbps)，预留20%余量
            target_bitrate = int((target_size_mb * 8 * 1024 * 0.8) / duration)
            # 设置最小比特率为200kbps，避免压缩后文件为0kb
            MIN_BITRATE = 200
            if target_bitrate < MIN_BITRATE:
                logger.warning(f"⚠️ 计算的比特率 {target_bitrate} kbps 过低，调整为最小值 {MIN_BITRATE} kbps")
                target_bitrate = MIN_BITRATE
            
            logger.info(f"🎯 目标比特率: {target_bitrate} kbps")
            
            # 压缩视频（移除crf参数，只使用比特率控制）
            # 使用两步scale确保宽度和高度都是偶数（H.264要求）
            # 1. 先限制最大尺寸并保持宽高比
            # 2. 然后使用第二个scale确保宽高都是偶数
            compress_cmd = [
                "ffmpeg", "-i", video_path,
                "-c:v", "libx264", "-b:v", f"{target_bitrate}k",
                "-maxrate", f"{int(target_bitrate * 1.5)}k",  # 最大比特率
                "-bufsize", f"{int(target_bitrate * 2)}k",     # 缓冲区大小
                "-c:a", "aac", "-b:a", "64k",
                "-preset", "medium",
                # 两步scale：先限制尺寸保持比例，再确保偶数
                "-vf", "scale='min(1280,iw)':'min(720,ih)':force_original_aspect_ratio=decrease,scale='trunc(iw/2)*2':'trunc(ih/2)*2'",
                "-movflags", "+faststart",
                "-y", compressed_path
            ]
            
            logger.info(f"🔧 执行压缩命令...")
            logger.debug(f"压缩命令: {' '.join(compress_cmd)}")
            result = subprocess.run(compress_cmd, capture_output=True, text=True)
            
            # 检查ffmpeg是否执行成功
            if result.returncode != 0:
                logger.error(f"❌ ffmpeg执行失败 (退出码: {result.returncode})")
                logger.error(f"📋 完整命令: {' '.join(compress_cmd)}")
                if result.stderr:
                    logger.error(f"🔴 错误输出:\n{result.stderr}")
                if result.stdout:
                    logger.error(f"📄 标准输出:\n{result.stdout}")
                raise Exception(f"ffmpeg返回错误代码: {result.returncode}, 错误: {result.stderr[:200]}")
            
            # 检查压缩后的文件是否存在且有效
            if not os.path.exists(compressed_path):
                raise Exception("压缩后的文件不存在")
                
            compressed_size = os.path.getsize(compressed_path) / (1024 * 1024)
            
            # 检查文件大小是否有效（至少100KB）
            if compressed_size < 0.1:
                logger.error(f"❌ 压缩后文件过小: {compressed_size:.2f} MB")
                raise Exception("压缩后文件大小异常")
            
            compression_ratio = (1 - compressed_size / original_size) * 100
            
            logger.info(f"✅ 视频压缩完成")
            logger.info(f"📊 压缩后大小: {compressed_size:.2f} MB")
            logger.info(f"📉 压缩率: {compression_ratio:.1f}%")
            
            if compressed_size > target_size_mb:
                logger.warning(f"⚠️ 压缩后大小 {compressed_size:.2f}MB 仍超过目标 {target_size_mb}MB，但文件有效，继续使用")
            
            return compressed_path
            
        except Exception as e:
            logger.error(f"❌ 视频压缩失败: {str(e)}")
            # 压缩失败时，尝试直接使用原视频
            logger.warning("🔄 压缩失败，将直接使用原视频进行分析")
            return video_path

    def _build_analysis_prompt(
        self,
        video_info: Dict[str, Any],
        platform: str
    ) -> str:
        """构建分析提示词"""
        platform_name = "抖音" if platform == "douyin" else "快手"

        # 从video_info中提取相关信息
        topic_name = video_info.get('topic_name', video_info.get('figure_name', ''))
        style = video_info.get('house_style', video_info.get('art_style', video_info.get('style_name', '')))
        concept = video_info.get('design_concept', video_info.get('video_feeling', ''))
        building_type = video_info.get('building_type', '')

        # 构建视频信息描述
        video_info_text = f"""**视频信息：**
- 主题：{topic_name if topic_name else '未知'}
- 风格：{style if style else '未知'}"""

        if building_type:
            video_info_text += f"\n- 类型：{building_type}"
        if concept:
            video_info_text += f"\n- 理念：{concept}"

        prompt = f"""请分析这个视频，并为{platform_name}平台生成相关内容：

{video_info_text}

**任务要求：**
请基于视频内容生成以下内容，要求符合{platform_name}平台特点，吸引用户关注和互动：

1. **{platform_name}文案（5组）**：
   - 每组包含文案内容和对应标签
   - 要有吸引力，能引发用户互动
   - 融入当前流行的话题和表达方式
   - 突出视频的亮点和美感
   - 每组提供不超过5个相关标签

2. **神评论（10组）**：
   - 模拟用户可能的精彩评论
   - 包含赞美、提问、互动等不同类型
   - 要真实自然，符合用户表达习惯
   - 可以包含一些有趣的观点或幽默元素

**返回格式（JSON）：**
{{
  "copywriting": [
    {{
      "content_tags": "文案内容，要有吸引力和互动性  #标签1 #标签2 #标签3 #标签4 #标签5",
    }},
    ...共5组
  ],
  "comments": [
    "这个太美了，我也想要！",
    "请问怎么做到的？好喜欢",
    ...共10条评论
  ]
}}

请确保生成的内容：
- 符合{platform_name}平台调性
- 具有传播价值和互动性
- 突出视频的专业性和美感
- 能够吸引目标用户群体"""
        return prompt

    def _analyze_video_with_gemini(
        self,
        video_path: str,
        video_info: Dict[str, Any],
        platform: str
    ) -> Dict[str, Any]:
        """使用Gemini原生API分析视频，生成社交媒体文案"""

        prompt = self._build_analysis_prompt(video_info, platform)
        return self._call_gemini_native_api(video_path, prompt, platform)

    def _call_gemini_native_api(
        self,
        video_path: str,
        prompt: str,
        platform: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """使用Gemini原生API分析视频"""

        api_base = os.getenv("VIDEO_ANALYSIS_BASE_URL")
        api_key = os.getenv("VIDEO_ANALYSIS_API_KEY")
        model_name = os.getenv("VIDEO_ANALYSIS_MODEL_NAME", "gemini-2.0-flash")

        if not api_base or not api_key:
            logger.warning("⚠️ 未配置视频分析 API (VIDEO_ANALYSIS_BASE_URL/VIDEO_ANALYSIS_API_KEY)")
            return {"success": False, "error": "未配置视频分析 API", "platform": platform}

        try:
            # 读取视频并编码为base64
            with open(video_path, "rb") as f:
                video_base64 = base64.b64encode(f.read()).decode('utf-8')

            # 获取视频MIME类型
            video_ext = Path(video_path).suffix.lower()
            mime_type_map = {
                '.mp4': 'video/mp4',
                '.mov': 'video/quicktime',
                '.avi': 'video/x-msvideo',
                '.webm': 'video/webm'
            }
            mime_type = mime_type_map.get(video_ext, 'video/mp4')

            # 构建API URL（处理base_url可能已经包含/v1的情况）
            base = api_base.rstrip('/')
            if base.endswith('/v1'):
                base = base[:-3]
            api_url = f"{base}/v1beta/models/{model_name}:generateContent?key={api_key}"

            # 打印调试信息（隐藏key）
            debug_url = api_url.split('?')[0] + "?key=***"
            key_preview = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 10 else "***"
            file_size_mb = os.path.getsize(video_path) / 1024 / 1024
            logger.info(f"🚀 Gemini请求URL: {debug_url}")
            logger.info(f"🔑 API Key: {key_preview}")
            logger.info(f"🎬 模型: {model_name}, 视频大小: {file_size_mb:.2f} MB")

            # 构建请求数据
            data = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": mime_type, "data": video_base64}}
                    ]
                }],
                "generationConfig": {
                    "maxOutputTokens": 4000,
                    "temperature": 0.5
                }
            }

            headers = {'Content-Type': 'application/json'}

            for attempt in range(1, max_retries + 1):
                try:
                    if attempt > 1:
                        logger.info(f"🔄 重试分析 ({attempt}/{max_retries})...")
                        import time
                        time.sleep(3)

                    logger.info(f"📤 调用Gemini API分析视频...")
                    response = requests.post(api_url, headers=headers, json=data, timeout=300)

                    if response.status_code == 200:
                        result = response.json()

                        # Gemini API响应格式
                        if 'candidates' in result and result['candidates']:
                            candidate = result['candidates'][0]
                            if 'content' in candidate and 'parts' in candidate['content']:
                                parts_text = [p.get('text', '') for p in candidate['content']['parts'] if 'text' in p]
                                response_text = '\n'.join(parts_text)

                                if response_text:
                                    logger.info(f"✅ Gemini视频分析成功，响应长度: {len(response_text)} 字符")
                                    return self._parse_gemini_response(response_text, platform)
                                else:
                                    logger.warning(f"⚠️ 响应内容为空")
                            else:
                                logger.error(f"❌ 响应格式异常: 缺少content.parts")
                        else:
                            logger.error(f"❌ 响应格式异常: 缺少candidates")
                            logger.error(f"响应内容: {json.dumps(result, ensure_ascii=False)[:500]}")
                    else:
                        logger.error(f"❌ HTTP错误: {response.status_code}")
                        logger.error(f"响应内容: {response.text[:500]}")

                except Exception as e:
                    logger.error(f"❌ 请求失败 ({attempt}/{max_retries}): {e}")

            return {"success": False, "error": "Gemini API调用失败", "platform": platform}

        except Exception as e:
            logger.error(f"❌ 视频分析异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e), "platform": platform}

    def _parse_gemini_response(
        self,
        response_text: str,
        platform: str
    ) -> Dict[str, Any]:
        """解析Gemini响应，提取JSON格式的文案数据"""
        import re

        try:
            # 尝试提取JSON
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                cleaned_text = json_match.group(0)
                parsed_result = json.loads(cleaned_text)
                logger.info(f"🎯 成功解析Gemini分析结果")
                parsed_result['success'] = True
                parsed_result['platform'] = platform
                return parsed_result
            else:
                logger.warning("未找到JSON格式的响应，返回原始文本")
                return {
                    "success": False,
                    "analysis_summary": response_text,
                    "copywriting": [],
                    "comments": [],
                    "raw_response": response_text,
                    "platform": platform
                }
        except json.JSONDecodeError as e:
            logger.error(f"解析Gemini响应JSON失败: {str(e)}")
            return {
                "success": False,
                "analysis_summary": response_text,
                "copywriting": [],
                "comments": [],
                "raw_response": response_text,
                "parse_error": str(e),
                "platform": platform
            }

    def _save_copywriting_result(
        self,
        result: Dict[str, Any],
        output_dir: str,
        platform: str
    ) -> str:
        """保存文案生成结果到指定目录"""
        try:
            # 创建social_media_copywriting子目录
            copywriting_dir = Path(output_dir) / 'social_media_copywriting'
            copywriting_dir.mkdir(parents=True, exist_ok=True)
            
            # 根据平台确定文件名
            filename = f"{platform}_text.json"
            output_path = copywriting_dir / filename
            
            # 保存结果
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            logger.info(f"💾 文案结果已保存: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"❌ 保存文案结果失败: {str(e)}")
            return ""

    def _cleanup_temp_files(self, compressed_video: str, original_video: str):
        """清理临时文件"""
        try:
            if compressed_video != original_video and os.path.exists(compressed_video):
                os.unlink(compressed_video)
                logger.info(f"🗑️ 清理压缩临时文件: {compressed_video}")
        except Exception as e:
            logger.warning(f"⚠️ 清理压缩临时文件失败: {str(e)}")
