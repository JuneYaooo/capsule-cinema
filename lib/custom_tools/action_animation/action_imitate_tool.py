#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用动作模仿CrewAI工具
支持多种动作模仿引擎，包含WanAnimate1和WanAnimate2
支持自动fallback机制：当一个引擎失败时自动尝试下一个
"""

from typing import Any, Dict, Type, Optional, List
from pydantic import BaseModel, Field
from custom_tools.base_tool import BaseTool

from src.logger import get_logger

# 导入动作模仿工具
from .wan_animate1_action_imitate_tool import WanAnimate1ActionImitateTool
from .wan_animate2_action_imitate_tool import WanAnimate2ActionImitateTool
from .wan22_animate3_action_imitate_tool import Wan22Animate3ActionImitateTool
from .wan_animate4_action_imitate_tool import WanAnimate4ActionImitateTool
from .wan_multi_person_action_imitate_tool import WanMultiPersonActionImitateTool
from .video_chunk_utils import (
    get_video_duration,
    split_video_into_chunks,
    extract_last_frame,
    concatenate_videos,
    cleanup_temp_files
)

logger = get_logger("action_imitate_tool")

# 默认引擎优先级列表（按优先级排序）
DEFAULT_ENGINE_PRIORITY = ["animate4", "animate2", "wan2.2animate3", "animate1"]


class ActionImitateSchema(BaseModel):
    """通用动作模仿工具的输入参数"""
    image_path: str = Field(
        ...,
        description="要替换的角色/人物图片路径"
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
    engine: str = Field(
        default="animate2",
        description="动作模仿引擎：animate2（默认，动作迁移2）, wan2.2animate3, animate4（3piao版本）, animate1, multi_person（多人动作模仿）"
    )
    enable_fallback: bool = Field(
        default=True,
        description="是否启用自动fallback机制：当指定引擎失败时自动尝试其他引擎"
    )
    engine_priority: Optional[List[str]] = Field(
        default=None,
        description="引擎优先级列表，用于fallback时的尝试顺序。默认为 ['animate2', 'wan2.2animate3', 'animate1']"
    )
    chunk_duration: float = Field(
        default=8.0,
        description="视频分块时长（秒）。当视频超过此时长时，会自动分块处理以避免OOM。设为0禁用分块。"
    )
    # WanAnimate1 参数
    frame_rate: int = Field(
        default=25,
        description="帧率（选16或25）"
    )
    duration: int = Field(
        default=5,
        description="总时长（秒）"
    )
    skip: int = Field(
        default=0,
        description="跳过（秒）"
    )
    width: int = Field(
        default=1080,
        description="视频宽度"
    )
    height: int = Field(
        default=1920,
        description="视频高度"
    )
    # 多人动作模仿参数
    num_people: int = Field(
        default=1,
        description="视频中的人数（1-10），仅在 engine='multi_person' 时生效"
    )
    prompt: str = Field(
        default="",
        description="提示词，描述视频内容（如：三个人在跳舞），仅在 engine='multi_person' 时生效"
    )
    instance_type: str = Field(
        default="default",
        description="运行实例类型：default (24G显存), plus (48G显存)，仅在 engine='multi_person' 时生效"
    )


class ActionImitateTool(BaseTool):
    name: str = "Universal action imitation tool"
    description: str = (
        "通用动作模仿工具，上传参考图片和视频，将图片中的角色替换到视频的动作中。"
        "支持多种引擎（animate2, wan2.2animate3, animate4, animate1, multi_person），默认使用animate2。"
        "支持自动fallback机制：当一个引擎失败时自动尝试下一个引擎。"
        "multi_person引擎支持多人动作模仿。"
    )
    args_schema: Type[BaseModel] = ActionImitateSchema

    def _run(
        self,
        image_path: str,
        video_path: str,
        output_dir: str = "output/videos",
        output_path: Optional[str] = None,
        engine: str = "animate2",
        enable_fallback: bool = True,
        engine_priority: Optional[List[str]] = None,
        chunk_duration: float = 8.0,
        frame_rate: int = 25,
        duration: int = 4,
        skip: int = 0,
        width: int = 1080,
        height: int = 1920,
        num_people: int = 1,
        prompt: str = "",
        instance_type: str = "default"
    ) -> Dict[str, Any]:
        """
        执行动作模仿

        Args:
            image_path: 角色图片路径
            video_path: 参考视频路径
            output_dir: 输出目录
            output_path: 完整的输出文件路径
            engine: 动作模仿引擎（默认 wananimate2）
            enable_fallback: 是否启用自动fallback（默认 True）
            engine_priority: 引擎优先级列表
            chunk_duration: 视频分块时长（秒），0表示禁用分块
            frame_rate: 帧率
            duration: 总时长
            skip: 跳过秒数
            width: 视频宽度
            height: 视频高度
            num_people: 视频中的人数（多人模式）
            prompt: 提示词（多人模式）
            instance_type: 实例类型（多人模式）

        Returns:
            生成结果的字典
        """
        import time
        import os
        import tempfile

        # 多人动作模仿模式 - 直接调用多人工具，不走分块和fallback逻辑
        if engine == "multi_person":
            logger.info(f"🎭 使用多人动作模仿引擎")
            tool = WanMultiPersonActionImitateTool()
            return tool._run(
                image_path=image_path,
                video_path=video_path,
                output_dir=output_dir,
                output_path=output_path,
                instance_type=instance_type
            )

        # 检查是否需要分块处理
        if chunk_duration > 0:
            try:
                video_duration = get_video_duration(video_path)
                if video_duration > chunk_duration:
                    logger.info(f"🎬 视频时长 {video_duration:.2f}秒 > {chunk_duration}秒，启用分块处理")
                    return self._run_chunked(
                        image_path=image_path,
                        video_path=video_path,
                        output_dir=output_dir,
                        output_path=output_path,
                        engine=engine,
                        enable_fallback=enable_fallback,
                        engine_priority=engine_priority,
                        chunk_duration=chunk_duration,
                        frame_rate=frame_rate,
                        width=width,
                        height=height
                    )
            except Exception as e:
                logger.warning(f"获取视频时长失败，将使用普通模式处理: {e}")

        # 普通模式（不分块）
        return self._run_single(
            image_path=image_path,
            video_path=video_path,
            output_dir=output_dir,
            output_path=output_path,
            engine=engine,
            enable_fallback=enable_fallback,
            engine_priority=engine_priority,
            frame_rate=frame_rate,
            duration=duration,
            skip=skip,
            width=width,
            height=height
        )

    def _run_chunked(
        self,
        image_path: str,
        video_path: str,
        output_dir: str,
        output_path: Optional[str],
        engine: str,
        enable_fallback: bool,
        engine_priority: Optional[List[str]],
        chunk_duration: float,
        frame_rate: int,
        width: int,
        height: int
    ) -> Dict[str, Any]:
        """
        分块处理长视频

        流程：
        1. 将参考视频按 chunk_duration 切分成多个片段
        2. 第一个片段使用原始参考图 + 第一段视频
        3. 后续片段使用上一个生成视频的最后一帧 + 对应的视频片段
        4. 最后将所有生成的视频拼接成一个完整视频
        """
        import time
        import os

        logger.info(f"\n{'='*60}")
        logger.info("🎬 分块动作模仿模式")
        logger.info(f"{'='*60}")

        start_time = time.time()
        generated_videos = []

        try:
            # 1. 在 output_dir 下创建 chunks 子目录，保存所有分块文件
            os.makedirs(output_dir, exist_ok=True)
            chunk_output_dir = os.path.join(output_dir, "chunks")
            os.makedirs(chunk_output_dir, exist_ok=True)
            logger.info(f"📁 分块文件目录: {chunk_output_dir}")

            video_chunks = split_video_into_chunks(
                video_path=video_path,
                chunk_duration=chunk_duration,
                output_dir=chunk_output_dir
            )

            logger.info(f"📊 共 {len(video_chunks)} 个视频片段需要处理")

            # 2. 依次处理每个片段
            current_image = image_path

            for i, chunk_path in enumerate(video_chunks):
                logger.info(f"\n{'─'*40}")
                logger.info(f"🔄 处理片段 {i+1}/{len(video_chunks)}")
                logger.info(f"   参考图: {current_image}")
                logger.info(f"   视频片段: {chunk_path}")

                # 为每个片段生成临时输出路径
                chunk_output = os.path.join(
                    chunk_output_dir,
                    f"generated_chunk_{i:03d}.mp4"
                )

                # 调用单次处理
                result = self._run_single(
                    image_path=current_image,
                    video_path=chunk_path,
                    output_dir=output_dir,
                    output_path=chunk_output,
                    engine=engine,
                    enable_fallback=enable_fallback,
                    engine_priority=engine_priority,
                    frame_rate=frame_rate,
                    duration=int(chunk_duration),
                    skip=0,
                    width=width,
                    height=height
                )

                if result.get('status') != 'success':
                    logger.error(f"❌ 片段 {i+1} 生成失败: {result.get('error')}")
                    return {
                        "status": "failed",
                        "error": f"片段 {i+1}/{len(video_chunks)} 生成失败: {result.get('error')}",
                        "partial_results": generated_videos
                    }

                generated_video = result.get('output_path')
                generated_videos.append(generated_video)
                logger.info(f"   ✅ 片段 {i+1} 生成成功: {generated_video}")

                # 3. 提取最后一帧作为下一个片段的参考图
                if i < len(video_chunks) - 1:
                    last_frame_path = os.path.join(
                        chunk_output_dir,
                        f"last_frame_{i:03d}.png"
                    )
                    current_image = extract_last_frame(generated_video, last_frame_path)
                    logger.info(f"   📸 提取最后一帧: {current_image}")

            # 4. 拼接所有生成的视频
            logger.info(f"\n{'─'*40}")
            logger.info(f"🔗 开始拼接 {len(generated_videos)} 个视频片段...")

            # 确定最终输出路径
            if output_path:
                final_output = output_path
            else:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                os.makedirs(output_dir, exist_ok=True)
                final_output = os.path.join(output_dir, f"action_imitate_{timestamp}.mp4")

            concatenate_videos(generated_videos, final_output)

            elapsed_time = time.time() - start_time
            logger.info(f"\n✅ 分块动作模仿完成！")
            logger.info(f"   总耗时: {elapsed_time:.2f}秒")
            logger.info(f"   输出文件: {final_output}")

            return {
                "status": "success",
                "output_path": final_output,
                "engine": engine,
                "message": f"分块处理完成，共处理 {len(video_chunks)} 个片段",
                "chunks_count": len(video_chunks),
                "chunks_dir": chunk_output_dir,
                "total_time": f"{elapsed_time:.2f}秒"
            }

        except Exception as e:
            logger.error(f"❌ 分块处理失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "failed",
                "error": str(e),
                "partial_results": generated_videos,
                "chunks_dir": chunk_output_dir if 'chunk_output_dir' in dir() else None
            }

    def _run_single(
        self,
        image_path: str,
        video_path: str,
        output_dir: str = "output/videos",
        output_path: Optional[str] = None,
        engine: str = "animate2",
        enable_fallback: bool = True,
        engine_priority: Optional[List[str]] = None,
        frame_rate: int = 25,
        duration: int = 4,
        skip: int = 0,
        width: int = 1080,
        height: int = 1920
    ) -> Dict[str, Any]:
        """
        执行单次动作模仿（不分块）
        """
        import time
        import os

        # 构建引擎尝试列表
        if engine_priority:
            engines_to_try = engine_priority.copy()
        else:
            engines_to_try = DEFAULT_ENGINE_PRIORITY.copy()

        # 确保指定的引擎在列表最前面
        if engine in engines_to_try:
            engines_to_try.remove(engine)
        engines_to_try.insert(0, engine)

        # 如果不启用fallback，只尝试指定的引擎
        if not enable_fallback:
            engines_to_try = [engine]

        logger.info(f"🎭 开始动作模仿 - 引擎: {engine}")
        logger.info(f"   图片: {image_path}")
        logger.info(f"   视频: {video_path}")
        if enable_fallback and len(engines_to_try) > 1:
            logger.info(f"   Fallback顺序: {' -> '.join(engines_to_try)}")

        all_errors = {}

        for engine_name in engines_to_try:
            logger.info(f"🔧 尝试引擎: {engine_name}")

            result = self._try_engine(
                engine_name=engine_name,
                image_path=image_path,
                video_path=video_path,
                output_dir=output_dir,
                output_path=output_path,
                frame_rate=frame_rate,
                duration=duration,
                skip=skip,
                width=width,
                height=height
            )

            if result.get('status') == 'success':
                if engine_name != engine:
                    logger.info(f"✅ 动作模仿成功（通过fallback引擎: {engine_name}）")
                return result

            # 记录失败原因
            all_errors[engine_name] = result.get('error', '未知错误')
            logger.warning(f"⚠️ 引擎 {engine_name} 失败: {all_errors[engine_name]}")

        # 所有引擎都失败
        error_details = "; ".join([f"{k}: {v}" for k, v in all_errors.items()])
        logger.error(f"❌ 所有引擎都失败: {error_details}")
        return {
            "status": "failed",
            "error": f"所有引擎都失败: {error_details}",
            "engine_errors": all_errors
        }

    def _try_engine(
        self,
        engine_name: str,
        image_path: str,
        video_path: str,
        output_dir: str,
        output_path: Optional[str],
        frame_rate: int,
        duration: int,
        skip: int,
        width: int,
        height: int
    ) -> Dict[str, Any]:
        """尝试使用指定引擎执行动作模仿"""
        import time
        import os

        max_retries = 3
        retry_delay = 5.0
        last_error = None

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logger.info(f"🔄 引擎 {engine_name} 重试 (尝试 {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)

                if engine_name == "animate1":
                    tool = WanAnimate1ActionImitateTool()
                    result = tool._run(
                        image_path=image_path,
                        video_path=video_path,
                        output_dir=output_dir,
                        output_path=output_path,
                        frame_rate=frame_rate,
                        duration=duration,
                        skip=skip,
                        width=width,
                        height=height
                    )
                elif engine_name == "animate2":
                    tool = WanAnimate2ActionImitateTool()
                    result = tool._run(
                        image_path=image_path,
                        video_path=video_path,
                        output_dir=output_dir,
                        output_path=output_path,
                        duration=duration,
                        width=width
                    )
                elif engine_name == "wan2.2animate3":
                    tool = Wan22Animate3ActionImitateTool()
                    result = tool._run(
                        image_path=image_path,
                        video_path=video_path,
                        output_dir=output_dir,
                        output_path=output_path,
                        width=width,
                        height=height,
                        frame_rate=frame_rate
                    )
                elif engine_name == "animate4":
                    # animate4 引擎只支持 720x1280 固定分辨率，强制覆盖用户传入的宽高
                    animate4_width = 720
                    animate4_height = 1280
                    if width != animate4_width or height != animate4_height:
                        logger.info(f"⚠️ animate4 引擎仅支持 720x1280，已自动调整 (原: {width}x{height})")
                    tool = WanAnimate4ActionImitateTool()
                    result = tool._run(
                        image_path=image_path,
                        video_path=video_path,
                        output_dir=output_dir,
                        output_path=output_path,
                        frame_rate=frame_rate,
                        width=animate4_width,
                        height=animate4_height
                    )
                else:
                    return {
                        "status": "failed",
                        "error": f"不支持的引擎: {engine_name}，目前支持 animate1, animate2, wan2.2animate3, animate4"
                    }

                # 验证结果
                if isinstance(result, dict):
                    if result.get('status') == 'failed':
                        error_msg = result.get('message') or result.get('error', '未知错误')
                        raise Exception(error_msg)
                    video_path_result = result.get("output_path")
                else:
                    raise Exception(f"意外的返回类型: {type(result)}")

                if video_path_result and os.path.exists(video_path_result):
                    file_size = os.path.getsize(video_path_result)
                    if file_size < 10240:  # 至少10KB
                        raise Exception(f"生成的视频文件过小 ({file_size} 字节)，可能损坏")

                    logger.info(f"✅ 动作模仿成功: {video_path_result} ({file_size / (1024*1024):.2f} MB)")
                    return {
                        "engine": engine_name,
                        "output_path": video_path_result,
                        "status": "success",
                        "message": result.get('message', '生成成功')
                    }
                else:
                    raise Exception(f"无法获取有效的视频路径")

            except Exception as e:
                last_error = str(e)
                logger.warning(f"⚠️ 引擎 {engine_name} 失败 (尝试 {attempt + 1}/{max_retries}): {last_error}")

        # 该引擎所有重试都失败
        return {
            "status": "failed",
            "error": last_error
        }


class BatchActionImitateTool(BaseTool):
    name: str = "Batch action imitation tool"
    description: str = (
        "批量动作模仿工具，为多个场景生成动作模仿视频。"
        "支持并发处理，自动重试和结果验证。"
    )
    args_schema: Type[BaseModel] = None  # 使用动态参数

    def _run(
        self,
        tasks: list,
        engine: str = "animate2",
        enable_fallback: bool = True,
        max_workers: int = 5,
        output_dir: str = "output/videos"
    ) -> Dict[str, Any]:
        """
        批量执行动作模仿

        Args:
            tasks: 任务列表，每个任务包含 image_path, video_path 等参数
            engine: 动作模仿引擎（默认 wananimate2）
            enable_fallback: 是否启用自动fallback（默认 True）
            max_workers: 最大并发数
            output_dir: 输出目录

        Returns:
            批量生成结果的字典
        """
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed

        logger.info(f"🎭 开始批量动作模仿 - 引擎: {engine}, 任务数: {len(tasks)}")

        start_time = time.time()
        outputs = {}
        results = []
        generated_count = 0
        failed_count = 0

        action_tool = ActionImitateTool()

        def generate_single_task(task_index, task):
            """生成单个动作模仿任务"""
            try:
                logger.info(f"🎬 任务 {task_index}: 开始处理")
                result = action_tool._run(
                    image_path=task.get('image_path'),
                    video_path=task.get('video_path'),
                    output_dir=output_dir,
                    output_path=task.get('output_path'),
                    engine=engine,
                    enable_fallback=enable_fallback,
                    frame_rate=task.get('frame_rate', 25),
                    duration=task.get('duration', 4),
                    skip=task.get('skip', 0),
                    width=task.get('width', 480),
                    height=task.get('height', 832)
                )

                if result.get('status') == 'success':
                    logger.info(f"✅ 任务 {task_index}: 成功")
                    return {
                        "task_index": task_index,
                        "status": "success",
                        "output_path": result.get('output_path')
                    }
                else:
                    logger.error(f"❌ 任务 {task_index}: 失败 - {result.get('error')}")
                    return {
                        "task_index": task_index,
                        "status": "failed",
                        "error": result.get('error')
                    }

            except Exception as e:
                logger.error(f"❌ 任务 {task_index}: 异常 - {str(e)}")
                return {
                    "task_index": task_index,
                    "status": "failed",
                    "error": str(e)
                }

        # 使用线程池并发处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {
                executor.submit(generate_single_task, i, task): i
                for i, task in enumerate(tasks)
            }

            for future in as_completed(future_to_task):
                task_idx = future_to_task[future]
                try:
                    result = future.result()
                    task_index = result["task_index"]

                    if result["status"] == "success":
                        outputs[task_index] = result["output_path"]
                        results.append(result)
                        generated_count += 1
                    else:
                        outputs[task_index] = f"错误: {result['error']}"
                        results.append(result)
                        failed_count += 1

                except Exception as e:
                    logger.error(f"❌ 任务 {task_idx} 处理异常: {str(e)}")
                    failed_count += 1

        end_time = time.time()
        summary = {
            "engine": engine,
            "outputs": outputs,
            "summary": {
                "total": len(tasks),
                "generated": generated_count,
                "failed": failed_count,
                "success_rate": f"{(generated_count/len(tasks)*100):.1f}%" if len(tasks) > 0 else "0%",
                "processing_time": f"{end_time - start_time:.2f}秒"
            },
            "results": results
        }

        logger.info(
            f"🎭 批量动作模仿完成 - "
            f"成功: {generated_count}/{len(tasks)} ({summary['summary']['success_rate']}), "
            f"耗时: {summary['summary']['processing_time']}"
        )

        return summary
