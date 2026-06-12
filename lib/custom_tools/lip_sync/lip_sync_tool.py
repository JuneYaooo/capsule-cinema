#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用对口型CrewAI工具
支持多个对口型模型供应商，目前支持：omnihuman, wan22
"""

from pathlib import Path
from typing import Type, Literal
from pydantic import BaseModel, Field
from custom_tools.base_tool import BaseTool

from .omnihuman_lip_sync_tool import OmniHumanLipSyncTool
from .wan22_lip_sync_tool import Wan22LipSyncTool


class LipSyncSchema(BaseModel):
    """对口型工具的输入参数"""
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
    provider: Literal["omnihuman", "wan22"] = Field(
        default="omnihuman",
        description="对口型模型供应商，目前支持：omnihuman, wan22"
    )


class LipSyncTool(BaseTool):
    name: str = "对口型工具"
    description: str = (
        "通用对口型生成工具，支持多个模型供应商。输入人物图片和音频文件，"
        "可以生成人物根据音频内容进行对口型说话的视频。"
        "目前支持的供应商：omnihuman（使用OmniHuman模型）、wan22（使用Wan2.2数字人模型）。"
        "适用于虚拟主播、教学视频、数字人等场景。"
    )
    args_schema: Type[BaseModel] = LipSyncSchema

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 初始化供应商工具映射
        self._providers = {
            "omnihuman": OmniHumanLipSyncTool(),
            "wan22": Wan22LipSyncTool()
        }
        
    def _run(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        provider: str = "omnihuman"
    ) -> str:
        """
        执行对口型生成
        
        Args:
            image_path: 输入图片路径
            audio_path: 输入音频路径
            output_path: 输出视频路径
            provider: 供应商名称，默认为 omnihuman
            
        Returns:
            生成结果的描述信息
        """
        try:
            # 验证供应商
            if provider not in self._providers:
                available_providers = ", ".join(self._providers.keys())
                return f"❌ 不支持的供应商: {provider}。可用供应商: {available_providers}"
            
            # 验证输入文件
            if not self._validate_input_files(image_path, audio_path):
                return "❌ 输入文件验证失败，请检查文件路径和格式"
            
            # 获取对应的供应商工具
            provider_tool = self._providers[provider]
            
            print(f"🎬 使用 {provider} 供应商生成对口型视频...")
            print(f"   图片: {image_path}")
            print(f"   音频: {audio_path}")
            print(f"   输出: {output_path}")
            
            # 调用供应商工具
            result = provider_tool._run(
                image_path=image_path,
                audio_path=audio_path,
                output_path=output_path
            )
            
            return f"[{provider}] {result}"
            
        except Exception as e:
            return f"❌ 对口型生成失败: {str(e)}"

    def _validate_input_files(self, image_path: str, audio_path: str) -> bool:
        """验证输入文件"""
        try:
            image_file = Path(image_path)
            audio_file = Path(audio_path)
            
            # 检查文件是否存在
            if not image_file.exists():
                print(f"❌ 图片文件不存在: {image_path}")
                return False
                
            if not audio_file.exists():
                print(f"❌ 音频文件不存在: {audio_path}")
                return False
            
            # 检查文件格式
            image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
            audio_extensions = {'.mp3', '.wav', '.m4a', '.aac'}
            
            if image_file.suffix.lower() not in image_extensions:
                print(f"❌ 不支持的图片格式: {image_file.suffix}")
                return False
                
            if audio_file.suffix.lower() not in audio_extensions:
                print(f"❌ 不支持的音频格式: {audio_file.suffix}")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ 文件验证失败: {str(e)}")
            return False
