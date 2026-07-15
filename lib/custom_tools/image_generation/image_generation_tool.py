"""Registry-driven scene image generation.

The public default is the official Volcengine Ark adapter. Extra runtime engine
names can be declared in the Git-ignored local registry.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field

from custom_tools.audio_generation.base_tool_compat import BaseTool
from src.config_registry import load_tool_registry


PUBLIC_IMAGE_ENGINE = "volcengine-seedream"
SUPPORTED_IMAGE_ENGINES = {PUBLIC_IMAGE_ENGINE}


class GenerateSceneImageSchema(BaseModel):
    scene: Dict[str, Any] = Field(..., description="Scene with an image prompt")
    output_dir: str
    output_path: Optional[str] = None
    engine: str = PUBLIC_IMAGE_ENGINE
    aspect_ratio: str = "9:16"
    quality: str = "high"
    reference_image_path: Optional[str] = None


class GenerateAllImagesSchema(BaseModel):
    scenes: List[Dict[str, Any]]
    output_dir: str
    engine: str = PUBLIC_IMAGE_ENGINE
    aspect_ratio: str = "9:16"


def _prompt(scene: Dict[str, Any]) -> str:
    return str(
        scene.get("image_prompt")
        or scene.get("image_prompt_chinese")
        or scene.get("image_prompt_english")
        or scene.get("description")
        or scene.get("scene_description")
        or ""
    )


def _tool_for_engine(engine: str):
    records = load_tool_registry()
    for class_name, record in records.items():
        if not isinstance(record, dict) or record.get("category") != "image_generation":
            continue
        if record.get("runtime_engine") == engine:
            module = import_module(record["module"])
            return getattr(module, class_name)()
    available = sorted(
        str(record.get("runtime_engine"))
        for record in records.values()
        if isinstance(record, dict) and record.get("category") == "image_generation" and record.get("runtime_engine")
    )
    raise ValueError(f"Unsupported image engine: {engine}. Available: {', '.join(available)}")


class GenerateSceneImageTool(BaseTool):
    name: str = "Generate single scene image"
    description: str = "Generate one scene image through an approved public or local-overlay engine."
    args_schema: Type[BaseModel] = GenerateSceneImageSchema

    def _run(
        self,
        scene: Dict[str, Any],
        output_dir: str,
        output_path: Optional[str] = None,
        engine: str = PUBLIC_IMAGE_ENGINE,
        aspect_ratio: str = "9:16",
        quality: str = "high",
        reference_image_path: Optional[str] = None,
        reference_prompt_prefix: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        prompt = _prompt(scene)
        if reference_prompt_prefix:
            prompt = f"{reference_prompt_prefix}\n{prompt}".strip()
        if not prompt:
            return {"status": "failed", "error": "Scene is missing image prompt", "engine": engine}
        index = scene.get("index", scene.get("scene_id", 0))
        destination = Path(output_path) if output_path else Path(output_dir) / f"scene_{int(index):02d}.png"
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = _tool_for_engine(engine)._run(
                prompt=prompt,
                output_path=str(destination),
                aspect_ratio=aspect_ratio,
                quality=quality,
                reference_image_path=reference_image_path,
                **kwargs,
            )
        except Exception as exc:  # noqa: BLE001
            return {"status": "failed", "error": str(exc), "engine": engine}
        path = result.get("output_path") if isinstance(result, dict) else None
        if destination.exists() or (path and Path(path).exists()):
            return {"status": "success", "output_path": path or str(destination), "engine": engine, "result": result}
        return {"status": "failed", "error": str(result), "engine": engine}


class GenerateAllImagesTool(BaseTool):
    name: str = "Generate all scene images"
    description: str = "Generate storyboard scene images."
    args_schema: Type[BaseModel] = GenerateAllImagesSchema

    def _run(self, scenes: List[Dict[str, Any]], output_dir: str, engine: str = PUBLIC_IMAGE_ENGINE, aspect_ratio: str = "9:16", max_workers: int = 4, **kwargs: Any) -> Dict[str, Any]:
        outputs: Dict[int, str] = {}
        details: List[Dict[str, Any]] = []
        tool = GenerateSceneImageTool()
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(tool._run, scene={**scene, "index": scene.get("index", index)}, output_dir=output_dir, engine=engine, aspect_ratio=aspect_ratio, **kwargs): index
                for index, scene in enumerate(scenes)
            }
            for future in as_completed(futures):
                index = futures[future]
                result = future.result()
                details.append({"index": index, **result})
                if result.get("status") == "success":
                    outputs[index] = result["output_path"]
        return {"outputs": outputs, "details": sorted(details, key=lambda item: item["index"]), "summary": {"total": len(scenes), "successful": len(outputs), "failed": len(scenes) - len(outputs), "engine": engine}}
