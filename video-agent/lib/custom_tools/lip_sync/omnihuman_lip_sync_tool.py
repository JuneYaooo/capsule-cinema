#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OmniHuman对口型CrewAI工具
使用fal-ai/bytedance/omnihuman模型从图片和音频生成对口型视频
"""

import os
import time
from pathlib import Path
from typing import Type
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from custom_tools.base_tool import BaseTool
import requests

# 加载环境变量
load_dotenv()

# 尝试导入fal_client
try:
    import fal_client
    FAL_CLIENT_AVAILABLE = True
except ImportError:
    FAL_CLIENT_AVAILABLE = False


class OmniHumanLipSyncSchema(BaseModel):
    """OmniHuman对口型工具的输入参数"""
    image_path: str = Field(
        ..., 
        description="输入人物图片的路径，支持jpg、png等格式"
    )
    audio_path: str = Field(
        ...,
        description="输入音频文件的路径，支持mp3、wav等格式"
    )
    output_path: str = Field(
        ...,
        description="输出视频文件的保存路径"
    )


class OmniHumanLipSyncTool(BaseTool):
    name: str = "OmniHuman对口型工具"
    description: str = (
        "使用OmniHuman模型生成对口型视频的工具。输入人物图片和音频文件，"
        "可以生成人物根据音频内容进行对口型说话的视频。适用于虚拟主播、教学视频等场景。"
    )
    args_schema: Type[BaseModel] = OmniHumanLipSyncSchema

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
    def _run(
        self,
        image_path: str,
        audio_path: str,
        output_path: str
    ) -> str:
        """
        执行OmniHuman对口型生成
        
        Args:
            image_path: 输入图片路径
            audio_path: 输入音频路径
            output_path: 输出视频路径
            
        Returns:
            生成结果的描述信息
        """
        try:
            if not FAL_CLIENT_AVAILABLE:
                return "❌ fal_client未安装，请运行: pip install fal-client"
            
            # 初始化OmniHuman生成器
            generator = OmniHumanGenerator()
            
            # 执行完整的处理流程
            result = generator.process(image_path, audio_path, output_path)
            
            if result['success']:
                return f"✅ OmniHuman对口型生成成功！视频已保存到: {result['output_path']}\n视频时长: {result.get('duration', 0):.2f}秒"
            else:
                return f"❌ OmniHuman对口型生成失败: {result['error']}"
            
        except Exception as e:
            return f"❌ OmniHuman对口型生成失败: {str(e)}"


class OmniHumanGenerator:
    def __init__(self):
        """初始化生成器"""
        self.api_key = os.getenv('FAL_AI_API_KEY')
        if not self.api_key:
            raise ValueError("未找到 FAL_AI_API_KEY 环境变量，请检查 .env 文件")
        
        # 设置 fal_client 的 API key
        os.environ['FAL_KEY'] = self.api_key
        
        print("✅ OmniHuman 生成器初始化成功")

    def validate_files(self, image_path: str, audio_path: str):
        """验证输入文件是否存在且格式正确"""
        image_path = Path(image_path)
        audio_path = Path(audio_path)
        
        # 检查文件是否存在
        if not image_path.exists():
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
        if not audio_path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        # 检查文件格式
        image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
        audio_extensions = {'.mp3', '.wav', '.m4a', '.aac'}
        
        if image_path.suffix.lower() not in image_extensions:
            raise ValueError(f"不支持的图片格式: {image_path.suffix}")
        if audio_path.suffix.lower() not in audio_extensions:
            raise ValueError(f"不支持的音频格式: {audio_path.suffix}")
        
        print(f"✅ 文件验证通过")
        print(f"   图片: {image_path}")
        print(f"   音频: {audio_path}")

    def upload_files(self, image_path: str, audio_path: str):
        """上传文件到 fal.ai 并获取 URL"""
        print("📤 上传文件到 fal.ai...")
        
        try:
            # 上传图片
            print("   上传图片...")
            with open(image_path, "rb") as image_file:
                image_url = fal_client.upload(image_file, "image/jpeg")
            print(f"   ✅ 图片上传成功: {image_url}")
            
            # 上传音频
            print("   上传音频...")
            with open(audio_path, "rb") as audio_file:
                audio_url = fal_client.upload(audio_file, "audio/mpeg")
            print(f"   ✅ 音频上传成功: {audio_url}")
            
            return image_url, audio_url
            
        except Exception as e:
            raise Exception(f"文件上传失败: {str(e)}")

    def generate_video(self, image_url: str, audio_url: str):
        """使用 OmniHuman 模型生成视频"""
        print("🎬 开始生成视频...")
        
        def on_queue_update(update):
            if isinstance(update, fal_client.InProgress):
                print(f"   队列状态: {update.logs[-1] if update.logs else '处理中...'}")

        try:
            # 调用 OmniHuman 模型
            result = fal_client.subscribe(
                "fal-ai/bytedance/omnihuman",
                arguments={
                    "image_url": image_url,
                    "audio_url": audio_url
                },
                with_logs=True,
                on_queue_update=on_queue_update,
            )
            
            print("✅ 视频生成完成!")
            return result
            
        except Exception as e:
            raise Exception(f"视频生成失败: {str(e)}")

    def download_video(self, video_url: str, output_path: str):
        """下载生成的视频"""
        print(f"📥 下载视频到: {output_path}")
        
        try:
            # 确保输出目录存在
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 下载视频
            response = requests.get(video_url, stream=True, timeout=300)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(output_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # 显示下载进度
                        if total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            print(f"\r   下载进度: {progress:.1f}%", end='', flush=True)
            
            print(f"\n✅ 视频下载完成: {output_file}")
            
        except Exception as e:
            raise Exception(f"视频下载失败: {str(e)}")

    def process(self, image_path: str, audio_path: str, output_path: str):
        """完整的处理流程"""
        try:
            # 验证输入文件
            self.validate_files(image_path, audio_path)
            
            # 上传文件
            image_url, audio_url = self.upload_files(image_path, audio_path)
            
            # 生成视频
            result = self.generate_video(image_url, audio_url)
            
            # 获取视频 URL
            video_url = result['video']['url']
            duration = result.get('duration', 0)
            
            print(f"📊 视频信息:")
            print(f"   时长: {duration:.2f} 秒")
            print(f"   URL: {video_url}")
            
            # 下载视频
            self.download_video(video_url, output_path)
            
            return {
                'success': True,
                'output_path': output_path,
                'video_url': video_url,
                'duration': duration
            }
            
        except Exception as e:
            print(f"❌ 处理失败: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            } 