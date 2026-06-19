from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from src.logger import get_logger
from src.video_generation_config import normalize_video_engine_name
from .jimeng35pro_video_generator_tool import Jimeng35ProVideoGeneratorTool
from .veo3_video_generator_tool import Veo3VideoGeneratorTool
from .veo31_video_generator_tool import Veo31VideoGeneratorTool

logger = get_logger("video_generation_tool")

SUPPORTED_VIDEO_ENGINES = {"seedance-fast", "seedance", "jimeng35pro", "veo3", "veo3.1"}
CHINESE_PROMPT_ENGINES = {"seedance-fast", "seedance", "jimeng35pro", "veo3", "veo3.1"}
ENGLISH_PROMPT_ENGINES = set()


def normalize_video_engine(engine: str) -> str:
    return normalize_video_engine_name(engine or "seedance-fast")


def seedance_tier_for_engine(engine: str) -> Optional[str]:
    engine = normalize_video_engine(engine)
    if engine == "seedance-fast":
        return "fast"
    if engine == "seedance":
        return "pro"
    return None


def select_video_prompt_by_engine(scene: Dict[str, Any], engine: str) -> str:
    chinese_prompt = scene.get("video_prompt_chinese") or scene.get("video_prompt") or scene.get("description") or ""
    english_prompt = scene.get("video_prompt_english") or scene.get("video_prompt") or scene.get("description") or ""
    engine = normalize_video_engine(engine)
    if engine in ENGLISH_PROMPT_ENGINES:
        return english_prompt or chinese_prompt
    return chinese_prompt or english_prompt


class GenerateVideoFromTextSchema(BaseModel):
    prompt: str = Field(..., description="Video prompt")
    output_dir: str = Field(..., description="Output directory")
    engine: str = Field("seedance-fast", description="Video engine: seedance-fast | seedance | jimeng35pro | veo3 | veo3.1")
    aspect_ratio: str = Field("9:16", description="Aspect ratio")


class GenerateVideoFromImageSchema(BaseModel):
    image_path: str = Field(..., description="Input image path")
    scene: Dict[str, Any] = Field(..., description="Scene object")
    output_dir: str = Field(..., description="Output directory")
    engine: str = Field("seedance-fast", description="Video engine: seedance-fast | seedance | jimeng35pro | veo3 | veo3.1")
    aspect_ratio: str = Field("9:16", description="Aspect ratio")


class GenerateAllVideosSchema(BaseModel):
    image_paths: Dict[int, str] = Field(..., description="Scene index to image path map")
    scenes: List[Dict[str, Any]] = Field(..., description="Scene list")
    output_dir: str = Field(..., description="Output directory")
    engine: str = Field("seedance-fast", description="Video engine: seedance-fast | seedance | jimeng35pro | veo3 | veo3.1")
    aspect_ratio: str = Field("9:16", description="Aspect ratio")
    is_transition_frame: bool = Field(False, description="Ignored in core runtime")


class UniversalVideoGenerationSchema(BaseModel):
    prompt: str = Field(..., description="Video prompt")
    output_dir: str = Field(..., description="Output directory")
    generation_type: str = Field("text_to_video", description="text_to_video | image_to_video | first_last_frame")
    engine: str = Field("seedance-fast", description="Video engine: seedance-fast | seedance | jimeng35pro | veo3 | veo3.1")
    image_path: Optional[str] = Field(None, description="Input image path")
    start_image_path: Optional[str] = Field(None, description="Start frame path/URL for first_last_frame")
    end_image_path: Optional[str] = Field(None, description="End frame path/URL for first_last_frame")
    images: Optional[List[str]] = Field(None, description="Image list for first_last_frame")
    aspect_ratio: str = Field("9:16", description="Aspect ratio")


def _tool_for_engine(engine: str) -> BaseTool:
    engine = normalize_video_engine(engine)
    if engine == "jimeng35pro":
        return Jimeng35ProVideoGeneratorTool()
    if engine == "veo3":
        return Veo3VideoGeneratorTool()
    if engine == "veo3.1":
        return Veo31VideoGeneratorTool()
    if engine in ("seedance", "seedance-fast"):
        from .seedance_video_generator_tool import SeedanceVideoGeneratorTool
        return SeedanceVideoGeneratorTool()
    raise ValueError(
        f"Unsupported video engine: {engine}. Supported: seedance-fast, seedance, jimeng35pro, veo3, veo3.1"
    )


def _video_path_from_result(result: Any) -> Optional[str]:
    if isinstance(result, dict):
        return result.get("output_path") or result.get("video_path")
    if isinstance(result, str) and Path(result).exists():
        return result
    return None


class GenerateVideoFromTextTool(BaseTool):
    name: str = "Generate video from text prompt"
    description: str = "Generate a video from text with seedance-fast, seedance, jimeng35pro, veo3 or veo3.1."
    args_schema: Type[BaseModel] = GenerateVideoFromTextSchema

    def _run(self, prompt: str, output_dir: str, engine: str = "seedance-fast", aspect_ratio: str = "9:16", **kwargs: Any) -> Dict[str, Any]:
        engine = normalize_video_engine(engine)
        try:
            result = _tool_for_engine(engine)._run(
                prompt=prompt,
                generation_type="text_to_video",
                output_dir=output_dir,
                aspect_ratio=aspect_ratio,
                seedance_tier=seedance_tier_for_engine(engine),
                duration=kwargs.get("duration"),
            )
            video_path = _video_path_from_result(result)
            if video_path:
                return {"engine": engine, "generation_type": "text_to_video", "result": result, "output_path": video_path}
            return {"error": str(result), "engine": engine}
        except Exception as exc:
            return {"error": str(exc), "engine": engine}


class GenerateVideoFromImageTool(BaseTool):
    name: str = "Generate video from single image"
    description: str = "Generate a video from one image with seedance-fast, seedance, jimeng35pro, veo3 or veo3.1."
    args_schema: Type[BaseModel] = GenerateVideoFromImageSchema

    def _run(
        self,
        image_path: str,
        scene: Dict[str, Any],
        output_dir: str,
        engine: str = "seedance-fast",
        aspect_ratio: str = "9:16",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        engine = normalize_video_engine(engine)
        prompt = select_video_prompt_by_engine(scene, engine)
        try:
            result = _tool_for_engine(engine)._run(
                prompt=prompt,
                generation_type="image_to_video",
                output_dir=output_dir,
                image_path=image_path,
                aspect_ratio=aspect_ratio,
                seedance_tier=seedance_tier_for_engine(engine),
                duration=kwargs.get("duration"),
            )
            video_path = _video_path_from_result(result)
            if video_path:
                return {"engine": engine, "generation_type": "image_to_video", "result": result, "output_path": video_path}
            return {"error": str(result), "engine": engine}
        except Exception as exc:
            return {"error": str(exc), "engine": engine}


class GenerateAllVideosTool(BaseTool):
    name: str = "Generate multiple scene videos"
    description: str = "Generate storyboard scene videos with the minimal supported video engines."
    args_schema: Type[BaseModel] = GenerateAllVideosSchema

    def _run(
        self,
        image_paths: Dict[int, str],
        scenes: List[Dict[str, Any]],
        output_dir: str,
        is_transition_frame: bool = False,
        engine: str = "seedance-fast",
        aspect_ratio: str = "9:16",
        max_workers: int = 2,
        **_: Any,
    ) -> Dict[str, Any]:
        del is_transition_frame
        engine = normalize_video_engine(engine)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        single_tool = GenerateVideoFromImageTool()
        outputs: Dict[int, str] = {}
        details: List[Dict[str, Any]] = []

        def generate(i: int, scene: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
            scene_index = scene.get("index", i)
            image_path = image_paths.get(scene_index) or image_paths.get(i)
            if not image_path:
                return i, {"error": f"Missing image for scene {scene_index}", "engine": engine}
            return i, single_tool._run(
                image_path=image_path,
                scene=scene,
                output_dir=output_dir,
                engine=engine,
                aspect_ratio=aspect_ratio,
            )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(generate, i, scene) for i, scene in enumerate(scenes)]
            for future in as_completed(futures):
                i, result = future.result()
                details.append({"index": i, **result})
                video_path = result.get("output_path")
                if video_path:
                    outputs[i] = video_path

        return {
            "outputs": outputs,
            "details": sorted(details, key=lambda item: item.get("index", 0)),
            "summary": {
                "total": len(scenes),
                "successful": len(outputs),
                "failed": len(scenes) - len(outputs),
                "engine": engine,
            },
        }


class UniversalVideoGenerationTool(BaseTool):
    name: str = "Universal video generation tool"
    description: str = "Unified text/image-to-video wrapper for the core runtime."
    args_schema: Type[BaseModel] = UniversalVideoGenerationSchema

    def _run(
        self,
        prompt: str,
        output_dir: str,
        generation_type: str = "text_to_video",
        engine: str = "seedance-fast",
        image_path: Optional[str] = None,
        start_image_path: Optional[str] = None,
        end_image_path: Optional[str] = None,
        images: Optional[List[str]] = None,
        aspect_ratio: str = "9:16",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        engine = normalize_video_engine(engine)
        if generation_type == "first_last_frame":
            result = _tool_for_engine(engine)._run(
                prompt=prompt,
                generation_type="first_last_frame",
                output_dir=output_dir,
                start_image_path=start_image_path,
                end_image_path=end_image_path,
                images=images,
                aspect_ratio=aspect_ratio,
                **kwargs,
            )
            video_path = _video_path_from_result(result)
            if video_path:
                return {
                    "engine": engine,
                    "generation_type": "first_last_frame",
                    "result": result,
                    "output_path": video_path,
                }
            return {"error": str(result), "engine": engine}

        if generation_type == "image_to_video":
            if not image_path:
                return {"error": "image_path is required for image_to_video"}
            return GenerateVideoFromImageTool()._run(
                image_path=image_path,
                scene={"video_prompt": prompt},
                output_dir=output_dir,
                engine=engine,
                aspect_ratio=aspect_ratio,
                **kwargs,
            )
        return GenerateVideoFromTextTool()._run(
            prompt=prompt,
            output_dir=output_dir,
            engine=engine,
            aspect_ratio=aspect_ratio,
            **kwargs,
        )
