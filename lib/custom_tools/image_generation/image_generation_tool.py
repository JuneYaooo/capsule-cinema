from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from src.logger import get_logger
from .gemini3_pro_image_tool import Gemini3ProImageGeneratorTool
from .seedream5_image_generator_tool import Seedream5ImageGeneratorTool, GptImage2Tool

logger = get_logger("image_generation_tool")


SUPPORTED_IMAGE_ENGINES = {"seedream5", "gpt-image-2", "gemini3_pro"}


class GenerateSceneImageSchema(BaseModel):
    scene: Dict[str, Any] = Field(..., description="Scene object containing index and image prompt")
    output_dir: str = Field(..., description="Output directory")
    output_path: Optional[str] = Field(None, description="Optional exact output image path")
    engine: str = Field("seedream5", description="Image engine: seedream5 | gpt-image-2 | gemini3_pro")
    aspect_ratio: str = Field("9:16", description="Aspect ratio: 9:16, 16:9, or 1:1")
    quality: str = Field("hd", description="Image quality hint passed to engines that support it")
    reference_image_path: Optional[str] = Field(None, description="Optional reference image path")
    reference_prompt_prefix: str = Field("", description="Optional prefix when reference image is used")


class GenerateAllImagesSchema(BaseModel):
    scenes: List[Dict[str, Any]] = Field(..., description="Scene list")
    output_dir: str = Field(..., description="Output directory")
    engine: str = Field("seedream5", description="Image engine: seedream5 | gpt-image-2 | gemini3_pro")
    aspect_ratio: str = Field("9:16", description="Aspect ratio: 9:16, 16:9, or 1:1")


def _scene_prompt(scene: Dict[str, Any]) -> str:
    return (
        scene.get("image_prompt")
        or scene.get("image_prompt_chinese")
        or scene.get("image_prompt_english")
        or scene.get("description")
        or scene.get("scene_description")
        or ""
    )


def resolve_reference_engine(engine: str, reference_image_path: Optional[str]) -> tuple[str, bool]:
    """Choose an image engine that can handle the requested reference inputs."""
    normalized_engine = (engine or "seedream5").lower()
    return normalized_engine, False


class GenerateSceneImageTool(BaseTool):
    name: str = "Generate single scene image"
    description: str = "Generate one scene image with seedream5, gpt-image-2 or gemini3_pro."
    args_schema: Type[BaseModel] = GenerateSceneImageSchema

    def _run(
        self,
        scene: Dict[str, Any],
        output_dir: str,
        output_path: Optional[str] = None,
        engine: str = "seedream5",
        aspect_ratio: str = "9:16",
        quality: str = "hd",
        reference_image_path: Optional[str] = None,
        reference_prompt_prefix: str = "",
        **_: Any,
    ) -> Dict[str, Any]:
        requested_engine = (engine or "seedream5").lower()
        engine, used_reference_fallback = resolve_reference_engine(requested_engine, reference_image_path)
        if engine == "gpt-image-2":
            quality = os.getenv("GPT_IMAGE2_DEFAULT_QUALITY", quality)
        if engine not in SUPPORTED_IMAGE_ENGINES:
            return {
                "status": "failed",
                "error": f"Unsupported image engine: {engine}. Supported: {', '.join(sorted(SUPPORTED_IMAGE_ENGINES))}",
            }

        prompt = _scene_prompt(scene)
        if reference_prompt_prefix:
            prompt = f"{reference_prompt_prefix}\n{prompt}".strip()
        if not prompt:
            return {"status": "failed", "error": "Scene is missing image prompt"}

        if used_reference_fallback:
            logger.info(
                "⚠️ Reference image provided but requested image engine cannot consume reference inputs; "
                f"using {engine} for this scene."
            )

        scene_index = scene.get("index", scene.get("scene_id", 0))
        suffix = "png" if engine in {"gemini3_pro", "gpt-image-2"} else "jpg"
        output_path = output_path or (
            str(Path(output_dir) / f"scene_{int(scene_index):02d}.{suffix}")
            if isinstance(scene_index, int)
            else str(Path(output_dir) / f"scene_{scene_index}.{suffix}")
        )
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if engine == "gemini3_pro":
            tool = Gemini3ProImageGeneratorTool()
        elif engine == "gpt-image-2":
            tool = GptImage2Tool()
        else:
            tool = Seedream5ImageGeneratorTool()

        try:
            reference_paths = None
            if reference_image_path:
                reference_paths = (
                    reference_image_path
                    if isinstance(reference_image_path, list)
                    else [reference_image_path]
                )
            result = tool._run(
                prompt=prompt,
                output_path=output_path,
                aspect_ratio=aspect_ratio,
                quality=quality,
                reference_image_paths=reference_paths,
                reference_image_path=reference_image_path,
            )
        except TypeError:
            result = tool._run(prompt=prompt, output_path=output_path, aspect_ratio=aspect_ratio)

        if Path(output_path).exists():
            return {
                "status": "success",
                "output_path": output_path,
                "engine": engine,
                "requested_engine": requested_engine,
                "reference_engine_fallback": used_reference_fallback,
                "result": result,
            }
        if isinstance(result, dict) and (result.get("output_path") or result.get("image_path")):
            return {
                "status": "success",
                "output_path": result.get("output_path") or result.get("image_path"),
                "engine": engine,
                "requested_engine": requested_engine,
                "reference_engine_fallback": used_reference_fallback,
                "result": result,
            }
        return {
            "status": "failed",
            "error": str(result),
            "engine": engine,
            "requested_engine": requested_engine,
            "reference_engine_fallback": used_reference_fallback,
        }


class GenerateAllImagesTool(BaseTool):
    name: str = "Generate all scene images"
    description: str = "Generate scene images for a storyboard with seedream5, gpt-image-2 or gemini3_pro."
    args_schema: Type[BaseModel] = GenerateAllImagesSchema

    def _run(
        self,
        scenes: List[Dict[str, Any]],
        output_dir: str,
        engine: str = "seedream5",
        aspect_ratio: str = "9:16",
        max_workers: int = 4,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        single_tool = GenerateSceneImageTool()
        outputs: Dict[int, str] = {}
        details: List[Dict[str, Any]] = []

        def generate(i: int, scene: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
            return i, single_tool._run(
                scene={**scene, "index": scene.get("index", i)},
                output_dir=output_dir,
                engine=engine,
                aspect_ratio=aspect_ratio,
                **kwargs,
            )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(generate, i, scene) for i, scene in enumerate(scenes)]
            for future in as_completed(futures):
                i, result = future.result()
                details.append({"index": i, **result})
                if result.get("status") == "success" and result.get("output_path"):
                    outputs[i] = result["output_path"]

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
