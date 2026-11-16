"""Unified video-generation entry points.

Engine names, aliases and prompt language come from the engine catalog
(``lib/config/video_engines.yaml`` via :mod:`src.video_engines`); the tool class
for an engine comes from ``tool_registry.yaml`` (``runtime_engine``). This module
keeps no engine list of its own.

Result contract (every entry point):

* success → ``{"success": True, "engine", "generation_type", "output_path", "result"}``
* failure → ``{"success": False, "engine", "error", ...}`` keeping the adapter's
  ``task_id`` / ``provider_error_code`` so callers can log or resume.
* an engine with no registered tool raises :class:`UnsupportedVideoEngineError`
  (``Unsupported video engine: x. Available: ...``) — never a silent fallback.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from src.logger import get_logger
from src.video_engines import get_engine_spec, normalize_engine_name, registered_video_engines
from src.config_registry import load_tool_registry

logger = get_logger("video_generation_tool")

DEFAULT_ENGINE = "seedance2.0"
GENERATION_TYPES = ("text_to_video", "image_to_video", "first_last_frame", "multimodal")
_RESULT_PATH_KEYS = ("output_path", "video_path", "local_path", "path", "file_path")
_RESULT_NESTED_KEYS = ("result", "data", "video")


class UnsupportedVideoEngineError(ValueError):
    """The requested engine has no registered, active tool."""


def normalize_video_engine(engine: str) -> str:
    return normalize_engine_name(engine or DEFAULT_ENGINE)


def select_video_prompt_by_engine(scene: Dict[str, Any], engine: str) -> str:
    chinese_prompt = scene.get("video_prompt_chinese") or scene.get("video_prompt") or scene.get("description") or ""
    english_prompt = scene.get("video_prompt_english") or scene.get("video_prompt") or scene.get("description") or ""
    spec = get_engine_spec(normalize_video_engine(engine))
    if spec is not None and spec.prompt_language == "en":
        return english_prompt or chinese_prompt
    return chinese_prompt or english_prompt


class GenerateVideoFromTextSchema(BaseModel):
    prompt: str = Field(..., description="Video prompt")
    output_dir: str = Field(..., description="Output directory")
    engine: str = Field(DEFAULT_ENGINE, description="Video engine key or alias from video_engines.yaml")
    aspect_ratio: str = Field("9:16", description="Aspect ratio")


class GenerateVideoFromImageSchema(BaseModel):
    image_path: str = Field(..., description="Input image path")
    scene: Dict[str, Any] = Field(..., description="Scene object")
    output_dir: str = Field(..., description="Output directory")
    engine: str = Field(DEFAULT_ENGINE, description="Video engine key or alias from video_engines.yaml")
    aspect_ratio: str = Field("9:16", description="Aspect ratio")


class GenerateAllVideosSchema(BaseModel):
    image_paths: Dict[int, str] = Field(..., description="Scene index to image path map")
    scenes: List[Dict[str, Any]] = Field(..., description="Scene list")
    output_dir: str = Field(..., description="Output directory")
    engine: str = Field(DEFAULT_ENGINE, description="Video engine key or alias from video_engines.yaml")
    aspect_ratio: str = Field("9:16", description="Aspect ratio")
    is_transition_frame: bool = Field(False, description="Ignored in core runtime")


class UniversalVideoGenerationSchema(BaseModel):
    prompt: str = Field(..., description="Video prompt; in multimodal refer to references as 图片N/视频N/音频N in list order")
    output_dir: str = Field(..., description="Output directory")
    generation_type: str = Field(
        "text_to_video", description="text_to_video | image_to_video | first_last_frame | multimodal"
    )
    engine: str = Field(DEFAULT_ENGINE, description="Video engine key or alias, e.g. seedance-2.0, seedance-2.5, minimax-h3")
    image_path: Optional[str] = Field(None, description="Input image for image_to_video")
    start_image_path: Optional[str] = Field(None, description="Start frame path/URL for first_last_frame")
    end_image_path: Optional[str] = Field(None, description="End frame path/URL for first_last_frame")
    images: Optional[List[str]] = Field(None, description="Image list for first_last_frame")
    image_paths: Optional[List[str]] = Field(None, description="multimodal reference images, in 图片N order")
    video_paths: Optional[List[str]] = Field(None, description="multimodal reference videos, in 视频N order")
    audio_paths: Optional[List[str]] = Field(None, description="multimodal reference audios, in 音频N order")
    duration: Optional[int] = Field(None, description="Seconds; must fit the engine's duration_range")
    aspect_ratio: str = Field("9:16", description="Aspect ratio")


def resolve_video_tool(engine: str) -> BaseTool:
    """Instantiate the registered tool for an engine, or raise UnsupportedVideoEngineError."""
    engine = normalize_video_engine(engine)
    engines = registered_video_engines()
    class_name = engines.get(engine)
    if class_name is None:
        raise UnsupportedVideoEngineError(
            f"Unsupported video engine: {engine}. Available: {', '.join(sorted(engines))}"
        )
    record = load_tool_registry()[class_name]
    return getattr(import_module(record["module"]), class_name)()


# Backward-compatible private name (rea-video's run_remake.py imports it).
_tool_for_engine = resolve_video_tool


def video_path_from_result(result: Any) -> Optional[str]:
    """Find the produced local video path in an adapter result (one nesting level)."""
    if isinstance(result, str):
        return result if Path(result).exists() else None
    if not isinstance(result, dict) or result.get("success") is False or result.get("error"):
        return None
    for key in _RESULT_PATH_KEYS:
        value = result.get(key)
        if isinstance(value, str) and value:
            return value
    for key in _RESULT_NESTED_KEYS:
        nested = result.get(key)
        if isinstance(nested, dict):
            for path_key in _RESULT_PATH_KEYS:
                value = nested.get(path_key)
                if isinstance(value, str) and value:
                    return value
    return None


_video_path_from_result = video_path_from_result


def wrap_video_result(engine: str, generation_type: str, result: Any) -> Dict[str, Any]:
    """Normalize an adapter result to the module's result contract."""
    video_path = video_path_from_result(result)
    if video_path:
        return {
            "success": True,
            "engine": engine,
            "generation_type": generation_type,
            "result": result,
            "output_path": video_path,
        }
    if isinstance(result, dict):
        failure = {key: value for key, value in result.items() if key not in {"success", "engine"}}
        failure.setdefault("error", "Video tool returned no video path")
        return {"success": False, "engine": engine, "generation_type": generation_type, **failure}
    return {"success": False, "engine": engine, "generation_type": generation_type, "error": str(result)}


def run_video_engine(engine: str, generation_type: str, **tool_kwargs: Any) -> Dict[str, Any]:
    """Dispatch one generation to an engine's tool and normalize the result.

    Raises UnsupportedVideoEngineError for unknown engines; adapter failures and
    exceptions come back as ``success: False`` dicts.
    """
    engine = normalize_video_engine(engine)
    tool = resolve_video_tool(engine)
    kwargs = {key: value for key, value in tool_kwargs.items() if value is not None}
    try:
        result = tool._run(generation_type=generation_type, **kwargs)
    except Exception as exc:  # adapters are third-party shaped; keep the batch alive
        logger.exception("video engine %s failed", engine)
        return {"success": False, "engine": engine, "generation_type": generation_type, "error": str(exc)}
    return wrap_video_result(engine, generation_type, result)


class GenerateVideoFromTextTool(BaseTool):
    name: str = "Generate video from text prompt"
    description: str = "Generate a video from text with an approved public or local-overlay engine."
    args_schema: Type[BaseModel] = GenerateVideoFromTextSchema

    def _run(self, prompt: str, output_dir: str, engine: str = DEFAULT_ENGINE, aspect_ratio: str = "9:16", **kwargs: Any) -> Dict[str, Any]:
        engine = normalize_video_engine(engine)
        try:
            return run_video_engine(
                engine, "text_to_video", **{**kwargs, "prompt": prompt, "output_dir": output_dir, "aspect_ratio": aspect_ratio}
            )
        except UnsupportedVideoEngineError as exc:
            return {"success": False, "error": str(exc), "engine": engine}


class GenerateVideoFromImageTool(BaseTool):
    name: str = "Generate video from single image"
    description: str = "Generate a video from one image with an approved public or local-overlay engine."
    args_schema: Type[BaseModel] = GenerateVideoFromImageSchema

    def _run(
        self,
        image_path: str,
        scene: Dict[str, Any],
        output_dir: str,
        engine: str = DEFAULT_ENGINE,
        aspect_ratio: str = "9:16",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        engine = normalize_video_engine(engine)
        prompt = select_video_prompt_by_engine(scene, engine)
        try:
            return run_video_engine(
                engine,
                "image_to_video",
                **{**kwargs, "prompt": prompt, "output_dir": output_dir, "image_path": image_path, "aspect_ratio": aspect_ratio},
            )
        except UnsupportedVideoEngineError as exc:
            return {"success": False, "error": str(exc), "engine": engine}


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
        engine: str = DEFAULT_ENGINE,
        aspect_ratio: str = "9:16",
        max_workers: int = 2,
        **kwargs: Any,
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
                **kwargs,
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
    description: str = "Unified text / image / first-last-frame / multimodal-reference video entry point."
    args_schema: Type[BaseModel] = UniversalVideoGenerationSchema

    def _run(
        self,
        prompt: str,
        output_dir: str,
        generation_type: str = "text_to_video",
        engine: str = DEFAULT_ENGINE,
        image_path: Optional[str] = None,
        start_image_path: Optional[str] = None,
        end_image_path: Optional[str] = None,
        images: Optional[List[str]] = None,
        image_paths: Optional[List[str]] = None,
        video_paths: Optional[List[str]] = None,
        audio_paths: Optional[List[str]] = None,
        aspect_ratio: str = "9:16",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        engine = normalize_video_engine(engine)
        generation_type = str(generation_type or "text_to_video").strip().lower()
        if generation_type not in GENERATION_TYPES:
            return {
                "success": False,
                "engine": engine,
                "error": f"Unsupported generation_type: {generation_type}. Use one of {', '.join(GENERATION_TYPES)}",
            }
        common = {**kwargs, "prompt": prompt, "output_dir": output_dir, "aspect_ratio": aspect_ratio}

        if generation_type == "first_last_frame":
            return run_video_engine(
                engine,
                generation_type,
                **common,
                start_image_path=start_image_path,
                end_image_path=end_image_path,
                images=images,
            )
        if generation_type == "image_to_video":
            if not image_path:
                return {"success": False, "engine": engine, "error": "image_path is required for image_to_video"}
            prompt = select_video_prompt_by_engine({"video_prompt": prompt}, engine)
            return run_video_engine(engine, generation_type, **{**common, "prompt": prompt}, image_path=image_path)
        if generation_type == "multimodal":
            if not (image_paths or video_paths or audio_paths or image_path):
                return {
                    "success": False,
                    "engine": engine,
                    "error": "multimodal requires image_paths, video_paths or audio_paths",
                }
            return run_video_engine(
                engine,
                generation_type,
                **common,
                image_path=image_path,
                image_paths=image_paths,
                video_paths=video_paths,
                audio_paths=audio_paths,
            )
        return run_video_engine(engine, generation_type, **common)
