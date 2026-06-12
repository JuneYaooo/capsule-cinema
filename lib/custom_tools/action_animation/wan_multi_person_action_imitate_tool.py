#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多人动作模仿CrewAI工具
使用RunningHub Workflow API上传参考图片和视频，生成多人动作模仿视频
工作流: https://www.runninghub.ai/workflow-new/2014675474420604929
"""

from pathlib import Path
from typing import Dict, Any, Type, Optional
from pydantic import BaseModel, Field
from custom_tools.base_tool import BaseTool

from src.logger import get_logger
from custom_tools.action_animation.wan_multi_person_api_client import WanMultiPersonApiClient

# 初始化日志
logger = get_logger("wan_multi_person_action_imitate")


class WanMultiPersonActionImitateSchema(BaseModel):
    """多人动作模仿工具的输入参数"""
    image_path: str = Field(
        ...,
        description="要替换的角色/人物图片路径（尽量与视频第一帧对齐）"
    )
    video_path: str = Field(
        ...,
        description="参考视频路径（动作来源）"
    )
    output_dir: str = Field(
        default="output/videos",
        description="生成视频的保存目录（当output_path未提供时使用）"
    )
    output_path: Optional[str] = Field(
        default=None,
        description="完整的输出文件路径（优先使用，如果提供则忽略output_dir）"
    )
    instance_type: str = Field(
        default="plus",
        description="运行实例类型：default (24G显存), plus (48G显存，推荐)"
    )
    width: int = Field(
        default=576,
        description="输出视频宽度（像素），默认 576（竖屏 9:16）"
    )
    height: int = Field(
        default=1024,
        description="输出视频高度（像素），默认 1024（竖屏 9:16）"
    )


class WanMultiPersonActionImitateTool(BaseTool):
    """多人动作模仿工具"""
    name: str = "多人动作模仿工具"
    description: str = (
        "使用RunningHub Workflow API生成多人动作模仿视频的工具。"
        "上传参考图片和视频，将图片中的多个角色替换到视频的动作中。"
        "适合生成多人舞蹈、群体动作迁移等创意视频内容。"
        "使用工作流2014675474420604929。"
    )
    args_schema: Type[BaseModel] = WanMultiPersonActionImitateSchema

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _run(
        self,
        image_path: str,
        video_path: str,
        output_dir: str = "output/videos",
        output_path: Optional[str] = None,
        instance_type: str = "plus",
        width: int = 576,
        height: int = 1024,
    ) -> Dict[str, Any]:
        """
        执行多人动作模仿

        Args:
            image_path: 角色图片路径
            video_path: 参考视频路径
            output_dir: 输出目录（当output_path未提供时使用）
            output_path: 完整的输出文件路径（优先使用）
            instance_type: 实例类型
            width: 输出视频宽度（像素），默认 576
            height: 输出视频高度（像素），默认 1024

        Returns:
            生成结果的字典
        """
        try:
            if output_path and output_dir == "output/videos":
                output_parent = Path(output_path).expanduser().resolve().parent
                run_root = output_parent.parent if output_parent.name in {"videos", "final"} else output_parent
                output_dir = str(run_root / "intermediates" / "action_transfer")

            # 初始化API客户端
            client = WanMultiPersonApiClient(output_dir=output_dir)

            # 执行动作模仿
            video_output_path = client.action_imitate(
                image_path=image_path,
                video_path=video_path,
                output_path=output_path,
                instance_type=instance_type,
                width=width,
                height=height,
            )

            if video_output_path:
                return {
                    "output_path": video_output_path,
                    "status": "success",
                    "message": f"✅ 多人动作模仿成功！视频已保存到: {video_output_path}"
                }
            else:
                return {
                    "status": "failed",
                    "message": "❌ 多人动作模仿失败"
                }

        except Exception as e:
            logger.error(f"多人动作模仿失败: {str(e)}")
            return {
                "status": "failed",
                "message": f"❌ 多人动作模仿失败: {str(e)}"
            }
