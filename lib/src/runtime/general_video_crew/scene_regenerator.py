"""Reusable runtime service for regenerating one storyboard scene."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

from src.contracts import (
    find_scene_by_id,
    get_scene_prompt,
    get_storyboard_scenes,
    scene_display_id,
    set_storyboard_scenes,
)
from src.utils.output_paths import PROJECT_ROOT, require_under_output


ProgressCallback = Callable[[str], None]


def _emit(progress: ProgressCallback | None, message: str) -> None:
    if progress:
        progress(message)


def find_next_version(directory: Path, scene_id: int, ext: str) -> int:
    """Return the next scene_NN_vX.ext version in a directory."""
    clean_ext = ext.lstrip(".")
    pattern = re.compile(rf"scene_{scene_id:02d}_v(\d+)\.{re.escape(clean_ext)}$")
    max_version = 0
    if directory.exists():
        for item in directory.iterdir():
            match = pattern.match(item.name)
            if match:
                max_version = max(max_version, int(match.group(1)))
    return max_version + 1


def load_storyboard(workspace_dir: Path) -> dict:
    storyboard_path = workspace_dir / "storyboard.json"
    if not storyboard_path.exists():
        raise FileNotFoundError(f"找不到 storyboard.json: {storyboard_path}")
    with storyboard_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_storyboard(workspace_dir: Path, data: dict) -> None:
    storyboard_path = workspace_dir / "storyboard.json"
    with storyboard_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def image_extension_for_engine(engine: str) -> str:
    normalized = (engine or "seedream5").strip()
    if normalized in {"gemini3_pro", "gpt-image-2"}:
        return "png"
    return "jpg"


def _artifact_subroot(workspace_dir: Path) -> Path:
    """Use the standard work/ artifact layout."""
    return workspace_dir / "work"


def _resolve_existing_path(value: str, workspace_dir: Path) -> str | None:
    if not value:
        return None

    path = Path(value).expanduser()
    candidates = [path] if path.is_absolute() else [workspace_dir / path, PROJECT_ROOT / path, path]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())
    return None


def generate_image(
    *,
    prompt: str,
    output_path: str,
    aspect_ratio: str,
    reference_image: str | None = None,
    image_engine: str = "seedream5",
    scene_id: int = 0,
) -> str:
    from custom_tools.image_generation import GenerateSceneImageTool

    result = GenerateSceneImageTool()._run(
        scene={"index": scene_id, "image_prompt": prompt},
        output_dir=str(Path(output_path).parent),
        output_path=output_path,
        engine=image_engine,
        aspect_ratio=aspect_ratio,
        reference_image_path=reference_image,
    )
    if isinstance(result, dict) and result.get("status") == "success" and result.get("output_path"):
        return str(result["output_path"])
    error = result.get("error") if isinstance(result, dict) else str(result)
    raise RuntimeError(f"图片生成失败（engine={image_engine}）: {error}")


def generate_video(
    *,
    prompt: str,
    image_path: str | None,
    output_dir: str,
    engine: str,
    aspect_ratio: str,
) -> str:
    from custom_tools.video_generation import UniversalVideoGenerationTool

    kwargs = {
        "prompt": prompt,
        "output_dir": output_dir,
        "engine": engine,
        "aspect_ratio": aspect_ratio,
    }
    if image_path and Path(image_path).exists():
        kwargs["generation_type"] = "image_to_video"
        kwargs["image_path"] = image_path
    else:
        kwargs["generation_type"] = "text_to_video"

    result = UniversalVideoGenerationTool()._run(**kwargs)
    if isinstance(result, dict) and result.get("output_path"):
        return str(result["output_path"])
    if isinstance(result, str) and result:
        return result
    error = result.get("error") if isinstance(result, dict) else str(result)
    raise RuntimeError(f"视频生成失败（engine={engine}）: {error}")


def regenerate_scene(
    *,
    workspace_dir: str | Path,
    scene_id: int,
    image_prompt: str | None = None,
    video_prompt: str | None = None,
    image_engine: str = "seedream5",
    video_engine: str = "seedance-fast",
    aspect_ratio: str = "9:16",
    skip_image: bool = False,
    reference_image: str | None = None,
    progress: ProgressCallback | None = None,
) -> dict:
    """Regenerate a single scene image and/or video and update storyboard.json."""
    if scene_id < 1:
        raise ValueError("scene_id 必须从 1 开始")

    workspace = require_under_output(workspace_dir, "workspace_dir")
    if not workspace.exists():
        raise FileNotFoundError(f"workspace 不存在: {workspace}")

    storyboard = load_storyboard(workspace)
    scenes = get_storyboard_scenes(storyboard)
    target_idx, target = find_scene_by_id(scenes, scene_id)
    if target is None:
        available = [scene_display_id(scene, index + 1) for index, scene in enumerate(scenes)]
        raise ValueError(f"找不到分镜 {scene_id}，可用分镜: {available}")

    img_prompt = image_prompt or get_scene_prompt(target, "image")
    vid_prompt = video_prompt or get_scene_prompt(target, "video")
    if not skip_image and not img_prompt:
        raise ValueError(f"分镜 {scene_id} 缺少图片 prompt，请传入 --image_prompt")
    if not vid_prompt:
        raise ValueError(f"分镜 {scene_id} 缺少视频 prompt，请传入 --video_prompt")

    subroot = _artifact_subroot(workspace)
    images_dir = subroot / "images"
    videos_dir = subroot / "videos"
    images_dir.mkdir(parents=True, exist_ok=True)
    videos_dir.mkdir(parents=True, exist_ok=True)

    result: dict = {"scene_id": scene_id, "status": "success"}
    new_image_path: str | None = None

    if not skip_image:
        image_ext = image_extension_for_engine(image_engine)
        image_version = find_next_version(images_dir, scene_id, image_ext)
        image_filename = f"scene_{scene_id:02d}_v{image_version}.{image_ext}"
        image_output = str(images_dir / image_filename)
        _emit(progress, f"[1/2] 生成图片: {image_filename} (engine={image_engine}) ...")
        new_image_path = generate_image(
            prompt=img_prompt,
            output_path=image_output,
            aspect_ratio=aspect_ratio,
            reference_image=reference_image,
            image_engine=image_engine,
            scene_id=scene_id,
        )
        result["image_path"] = new_image_path
        result["image_prompt"] = img_prompt
        result["image_engine"] = image_engine
        result["image_version"] = image_version
        _emit(progress, f"  -> 图片已保存: {new_image_path}")
    else:
        existing = target.get("image_path", "")
        new_image_path = _resolve_existing_path(existing, workspace) if isinstance(existing, str) else None
        _emit(progress, "[1/2] 跳过图片生成")

    video_version = find_next_version(videos_dir, scene_id, "mp4")
    video_filename = f"scene_{scene_id:02d}_v{video_version}.mp4"
    _emit(progress, f"[2/2] 生成视频: {video_filename} (engine={video_engine}) ...")
    video_path = generate_video(
        prompt=vid_prompt,
        image_path=new_image_path,
        output_dir=str(videos_dir),
        engine=video_engine,
        aspect_ratio=aspect_ratio,
    )

    video_source = Path(video_path)
    if not video_source.exists():
        raise RuntimeError(f"视频生成未返回有效本地文件: {video_path}")

    target_video_path = videos_dir / video_filename
    if video_source.resolve() != target_video_path.resolve():
        video_source.replace(target_video_path)
        video_path = str(target_video_path)
    result["video_path"] = video_path
    result["video_prompt"] = vid_prompt
    result["video_version"] = video_version
    _emit(progress, f"  -> 视频已保存: {video_path}")

    scene = scenes[target_idx]
    if image_prompt:
        scene["image_prompt"] = image_prompt
    if video_prompt:
        scene["video_prompt"] = video_prompt
    if new_image_path and not skip_image:
        scene["image_path"] = new_image_path
    if video_path:
        scene["video_path"] = video_path
    scene["regen_version"] = video_version
    scene["regen_image_engine"] = image_engine
    scene["regen_engine"] = video_engine

    set_storyboard_scenes(storyboard, scenes)
    save_storyboard(workspace, storyboard)
    result["storyboard_updated"] = True
    return result
