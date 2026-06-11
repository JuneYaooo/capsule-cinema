from pathlib import Path
from typing import Dict, List

from custom_tools.quality_check import VideoQualityCheckerTool
from custom_tools.video_generation import GenerateAllVideosTool
from custom_tools.video_generation.video_generation_tool import select_video_prompt_by_engine
from custom_tools.video_processing import ImageToVideoFallbackTool
from src.logger import get_logger
from .config import CONFIG

logger = get_logger("video_generator")


class VideoGenerator:
    """Core storyboard video generator."""

    def __init__(self):
        self.video_batch_tool = GenerateAllVideosTool()
        self.quality_checker = VideoQualityCheckerTool()
        self.image_fallback_tool = ImageToVideoFallbackTool()

    def generate_videos(
        self,
        storyboard: List[Dict],
        image_result: Dict,
        output_dir: str,
        engine: str = None,
        enable_quality_check: bool = None,
        max_regeneration_attempts: int = None,
        aspect_ratio: str = None,
    ) -> Dict:
        engine = engine or CONFIG.DEFAULT_VIDEO_ENGINE
        enable_quality_check = (
            enable_quality_check
            if enable_quality_check is not None
            else CONFIG.ENABLE_VIDEO_QUALITY_CHECK
        )
        max_regeneration_attempts = max_regeneration_attempts or CONFIG.MAX_VIDEO_REGENERATION_ATTEMPTS
        aspect_ratio = aspect_ratio or CONFIG.DEFAULT_ASPECT_RATIO
        image_outputs = image_result.get("outputs", {})

        fallback_engines = self._fallback_engines(engine)
        all_outputs = {}
        last_error = None

        for current_engine in fallback_engines:
            logger.info(f"🎬 使用视频生成引擎: {current_engine}")
            try:
                scene_list = list(enumerate(storyboard))
                all_outputs = self._generate_video_batch(
                    scene_list=scene_list,
                    image_outputs=image_outputs,
                    output_dir=output_dir,
                    engine=current_engine,
                    aspect_ratio=aspect_ratio,
                )

                if enable_quality_check and all_outputs:
                    all_outputs = self._analyze_and_regenerate_videos(
                        video_outputs=all_outputs,
                        scene_list=scene_list,
                        image_outputs=image_outputs,
                        output_dir=output_dir,
                        engine=current_engine,
                        max_regeneration_attempts=max_regeneration_attempts,
                    )

                success_rate = self._success_rate(all_outputs, len(storyboard))
                if success_rate >= 0.7:
                    break
                logger.warning(f"⚠️ 视频生成成功率不达标: {success_rate:.1%}")
                all_outputs = {}
            except Exception as exc:
                last_error = str(exc)
                logger.error(f"❌ 视频引擎 {current_engine} 失败: {last_error}")
                all_outputs = {}

        if not all_outputs:
            logger.warning(f"🔄 启用图片备用视频方案，最后错误: {last_error}")
            all_outputs = self._fallback_to_image_videos(storyboard, image_outputs, output_dir)

        generated_count = sum(
            1 for value in all_outputs.values()
            if value and isinstance(value, str) and not value.startswith("错误")
        )
        failed_count = len(storyboard) - generated_count
        logger.info(f"🎥 视频生成完成: 总计{generated_count}/{len(storyboard)}, 失败{failed_count}个")

        return {
            "outputs": all_outputs,
            "summary": {
                "total": len(storyboard),
                "generated": generated_count,
                "failed": failed_count,
                "regular_count": generated_count,
            },
        }

    def _fallback_engines(self, engine: str) -> List[str]:
        engines = CONFIG.VIDEO_ENGINE_FALLBACK_ORDER.copy()
        if engine in engines:
            return engines[engines.index(engine):]
        return [engine] + engines

    def _generate_video_batch(
        self,
        scene_list: List[tuple],
        image_outputs: Dict,
        output_dir: str,
        engine: str,
        aspect_ratio: str = "9:16",
    ) -> Dict:
        temp_image_outputs = {}
        scenes_for_tool = []

        for temp_index, (original_index, scene) in enumerate(scene_list):
            image_path = image_outputs.get(original_index)
            if not image_path or (isinstance(image_path, str) and image_path.startswith("错误")):
                logger.warning(f"⚠️ 场景{original_index}图片不可用，跳过视频生成")
                continue
            if not Path(image_path).exists():
                logger.warning(f"⚠️ 场景{original_index}图片不存在: {image_path}")
                continue

            temp_image_outputs[temp_index] = image_path
            video_prompt = select_video_prompt_by_engine(scene, engine)
            scenes_for_tool.append({
                "index": temp_index,
                "video_prompt": video_prompt,
                "video_prompt_chinese": scene.get("video_prompt_chinese", ""),
                "video_prompt_english": scene.get("video_prompt_english", ""),
                "original_index": original_index,
            })

        if not scenes_for_tool:
            return {}

        video_result = self.video_batch_tool._run(
            image_paths=temp_image_outputs,
            scenes=scenes_for_tool,
            output_dir=output_dir,
            engine=engine,
            aspect_ratio=aspect_ratio,
        )

        mapped_outputs = {}
        for temp_index, scene_data in enumerate(scenes_for_tool):
            original_index = scene_data["original_index"]
            if temp_index in video_result.get("outputs", {}):
                mapped_outputs[original_index] = video_result["outputs"][temp_index]
        return mapped_outputs

    def _analyze_and_regenerate_videos(
        self,
        video_outputs: Dict,
        scene_list: List[tuple],
        image_outputs: Dict,
        output_dir: str,
        engine: str,
        max_regeneration_attempts: int,
    ) -> Dict:
        original_to_temp = {original_idx: temp_idx for temp_idx, (original_idx, _) in enumerate(scene_list)}
        scene_map = {original_idx: scene for original_idx, scene in scene_list}

        for original_index, video_path in list(video_outputs.items()):
            if not video_path or not Path(str(video_path)).exists():
                continue

            attempts = 0
            while attempts < max_regeneration_attempts:
                try:
                    analysis = self.quality_checker._run(video_path=video_path, check_focus="quality")
                    if not analysis.get("needs_regeneration", False):
                        break

                    scene = scene_map.get(original_index)
                    temp_index = original_to_temp.get(original_index)
                    regenerated = self.video_batch_tool._run(
                        image_paths={temp_index: image_outputs.get(original_index)},
                        scenes=[{
                            "index": temp_index,
                            "video_prompt": select_video_prompt_by_engine(scene, engine),
                            "original_index": original_index,
                        }],
                        output_dir=output_dir,
                        engine=engine,
                    )
                    new_path = regenerated.get("outputs", {}).get(temp_index)
                    if not new_path:
                        break
                    video_outputs[original_index] = new_path
                    video_path = new_path
                    attempts += 1
                except Exception as exc:
                    logger.warning(f"⚠️ 场景{original_index}视频质量检测失败: {exc}")
                    break
        return video_outputs

    def _fallback_to_image_videos(self, storyboard: List[Dict], image_outputs: Dict, output_dir: str) -> Dict:
        fallback_dir = Path(output_dir) / "fallback_videos"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        video_outputs = {}

        for i, scene in enumerate(storyboard):
            image_path = image_outputs.get(i)
            if not image_path or not Path(str(image_path)).exists():
                video_outputs[i] = "错误: 图片不可用"
                continue

            output_path = fallback_dir / f"scene_{i:02d}_fallback.mp4"
            result = self.image_fallback_tool.create_video_from_image(
                image_path=image_path,
                output_path=str(output_path),
                duration=scene.get("duration", CONFIG.DEFAULT_SCENE_DURATION),
                scene_id=i,
            )
            if result.get("status") == "success":
                video_outputs[i] = result["output_path"]
            else:
                video_outputs[i] = f"错误: {result.get('error', '未知错误')}"
        return video_outputs

    @staticmethod
    def _success_rate(outputs: Dict, total: int) -> float:
        if total <= 0:
            return 0.0
        generated = sum(
            1 for value in outputs.values()
            if value and isinstance(value, str) and not value.startswith("错误")
        )
        return generated / total
