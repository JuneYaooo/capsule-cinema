#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable



_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPT_DIR.parent
_LIB_DIR = _SKILL_DIR / "lib"
sys.path.insert(0, str(_LIB_DIR))
sys.path.insert(0, str(_SCRIPT_DIR))

from env_loader import load_video_agent_env  # noqa: E402
from src.video_to_capsule import (  # noqa: E402
    VideoToCapsuleError,
    _parse_jsonish,
    build_analysis_prompt,
    materialize_capsule_from_draft,
    normalize_video_analysis,
    write_artifact_manifest,
    write_json,
)
from src.config_registry import load_tool_registry as load_registry_records  # noqa: E402
from src import video_package  # noqa: E402


load_video_agent_env(_SKILL_DIR)

DEFAULT_ANALYZER_TOOL = ""


def _json_default(value: Any) -> str:
    return str(value)


def _safe_segment(value: str, default: str = "video") -> str:
    import re

    text = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip()).strip("_")
    return text or default


def load_tool_registry() -> dict[str, str]:
    tools = load_registry_records()
    return {
        name: config["module"]
        for name, config in tools.items()
        if isinstance(config, dict) and config.get("module")
    }


def instantiate_tool(tool_name: str):
    if not tool_name:
        raise SystemExit(
            "video analysis requires an explicitly configured local tool; "
            "add it to local-channels/tool_registry.yaml"
        )
    registry = load_tool_registry()
    if tool_name not in registry:
        raise SystemExit(f"unknown video analysis tool: {tool_name}")
    module = importlib.import_module(registry[tool_name])
    tool_class = getattr(module, tool_name)
    tool = tool_class()
    if not hasattr(tool, "_run"):
        raise SystemExit(f"video analysis tool does not expose _run: {tool_name}")
    return tool


def create_workspace_dir(output_base_dir: str | Path | None, source_video_path: Path) -> Path:
    base = Path(
        output_base_dir
        or os.getenv("OPENCLAW_OUTPUT_DIR")
        or (_SKILL_DIR / "output")
    ).expanduser()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    workspace = base / f"video_to_capsule_{timestamp}_{_safe_segment(source_video_path.stem)}"
    workspace.mkdir(parents=True, exist_ok=False)
    (workspace / "analysis").mkdir(parents=True, exist_ok=True)
    return workspace


def _source_metadata(source: Path) -> dict[str, Any]:
    stat = source.stat()
    return {
        "path": str(source),
        "filename": source.name,
        "size_bytes": stat.st_size,
        "suffix": source.suffix.lower(),
    }


def _merge_package_analysis(raw_result: Any, package_analysis: dict[str, Any]) -> dict[str, Any]:
    """Analyzer output wins; the VIDEO.md package fills what the analyzer left out (summary, profile, segments)."""
    try:
        raw = _parse_jsonish(raw_result)  # unwrap raw_response / fenced JSON before deciding what is missing
    except VideoToCapsuleError:
        return raw_result  # let normalize_video_analysis report the bad response
    if raw.get("success") is False:
        return raw
    merged = dict(raw)
    for key in ("summary", "segments"):
        if not merged.get(key) and not (key == "segments" and merged.get("scene_breakdown")):
            merged[key] = package_analysis.get(key)
    profile = dict(package_analysis.get("source_profile") or {})
    profile.update(merged.get("source_profile") or {})
    merged["source_profile"] = profile
    merged["warnings"] = list(merged.get("warnings") or []) + list(package_analysis.get("warnings") or [])
    return merged


def run_video_to_capsule(
    *,
    source_video_path: str = "",
    videomd_package: str | Path | None = None,
    lookup_videomd: bool = True,
    video_analysis_tool: str = DEFAULT_ANALYZER_TOOL,
    output_base_dir: str | Path | None = None,
    capsule_output_root: str | Path | None = None,
    capsule_name: str = "",
    capsule_display_name: str = "",
    capsule_summary: str = "",
    analysis_prompt: str = "",
    target_platform: str = "",
    write_capsule: bool = False,
    include_source_video: bool = False,
    local_script_source: str | Path | None = None,
    local_script_entry: str = "",
    script_evidence: dict[str, Any] | str | Path | None = None,
    overwrite_capsule: bool = False,
    tool_factory: Callable[[str], Any] = instantiate_tool,
) -> dict[str, Any]:
    tool_name = video_analysis_tool or DEFAULT_ANALYZER_TOOL
    pkg: dict[str, Any] | None = None
    if not videomd_package and source_video_path and lookup_videomd and Path(source_video_path).expanduser().is_file():
        found = video_package.locate(source_video_path)
        if found["exact"]:
            videomd_package = found["exact"][0]
            print(f"using the VIDEO.md breakdown of the source video: {videomd_package}", file=sys.stderr)
    if videomd_package:
        try:
            pkg = video_package.load(videomd_package)
        except video_package.VideoPackageError as exc:
            raise SystemExit(str(exc)) from exc
    if source_video_path:
        source = Path(source_video_path).expanduser()
    elif pkg is not None:
        found = video_package.source_video(pkg)
        source = found or Path(pkg["root"]) / str(((pkg["card"].get("source") or {}).get("file")) or "source_video")
    else:
        raise SystemExit("pass --source-video-path, --videomd-package, or both")
    has_source = source.is_file()
    if not has_source and (pkg is None or tool_name):
        hint = " (the VIDEO.md package does not hold the video; pass --source-video-path)" if pkg is not None and not source_video_path else ""
        raise SystemExit(f"source video not found: {source}{hint}")
    if include_source_video and not has_source:
        raise SystemExit(f"include_source_video needs the source video file: {source}")
    if write_capsule and not str(capsule_name or "").strip():
        raise SystemExit("capsule_name is required when write_capsule=true")

    workspace = create_workspace_dir(output_base_dir, source)
    analysis_dir = workspace / "analysis"
    warnings: list[str] = []
    artifacts: list[dict[str, Any]] = []

    if has_source:
        source_metadata_path = write_json(analysis_dir / "source_video_metadata.json", _source_metadata(source))
        artifacts.append({"category": "source_video_metadata", "path": str(source_metadata_path), "title": "Source video metadata"})
    package_analysis: dict[str, Any] | None = None
    if pkg is not None:
        package_analysis = video_package.to_analysis(pkg)
        package_path = write_json(analysis_dir / "videomd_package.json", {**video_package.reference(pkg), "analysis": package_analysis})
        artifacts.append({"category": "videomd_package", "path": str(package_path), "title": "VIDEO.md package read"})

    prompt = build_analysis_prompt(analysis_prompt=analysis_prompt, target_platform=target_platform)
    if pkg is not None:
        prompt += (
            "\nA VIDEO.md breakdown of this video is attached below. Use it as evidence for segments and production "
            "methods, but check it against the video itself.\n\n"
            + video_package.context(pkg, topics=("content", "remake", "sound", "packaging"))
        )
    raw_path: Path | None = None
    if tool_name or pkg is None:
        tool = tool_factory(tool_name)
        raw_result = tool._run(video_path=str(source), prompt=prompt, analysis_focus="content")
        raw_path = analysis_dir / "analyzer_raw_response.json"
        raw_path.write_text(json.dumps(raw_result, ensure_ascii=False, indent=2, default=_json_default) + "\n", encoding="utf-8")
        if package_analysis is not None:
            raw_result = _merge_package_analysis(raw_result, package_analysis)
    else:
        # Only reachable with a package: no analyzer, so the draft carries no recipe or content scope and stays a preview.
        raw_result = package_analysis
        tool_name = "videomd"
        warnings.append("No analyzer tool ran; the draft comes from VIDEO.md alone and cannot be written as a capsule until an analyzer declares content_scope.")

    breakdown, draft = normalize_video_analysis(
        raw_result,
        source_video_path=str(source),
        analysis_tool=tool_name,
        capsule_name=capsule_name,
        capsule_display_name=capsule_display_name,
        capsule_summary=capsule_summary,
        target_platform=target_platform,
        require_source_file=has_source or pkg is None,
        video_package=video_package.reference(pkg) if pkg is not None else None,
    )
    warnings.extend(breakdown.get("warnings") or [])

    breakdown_path = write_json(analysis_dir / "video_breakdown.json", breakdown)
    draft_path = write_json(analysis_dir / "capsule_draft.json", draft)
    capsule_dir: Path | None = None
    if write_capsule:
        capsule_dir = materialize_capsule_from_draft(
            draft,
            source_video_path=str(source),
            output_root=capsule_output_root or (_SKILL_DIR / "capsules"),
            include_source_video=include_source_video,
            local_script_source=local_script_source,
            local_script_entry=local_script_entry,
            script_evidence=script_evidence,
            overwrite=overwrite_capsule,
        )
    else:
        if include_source_video:
            warnings.append("include_source_video ignored because write_capsule is false")
        if local_script_source:
            warnings.append("local_script_source ignored because write_capsule is false")

    artifacts += [
        {"category": "video_analysis", "path": str(breakdown_path), "title": "Video breakdown"},
        {"category": "capsule_draft", "path": str(draft_path), "title": "Capsule draft"},
    ]
    if raw_path is not None:
        artifacts.append({"category": "analyzer_raw_response", "path": str(raw_path), "title": "Analyzer raw response"})
    artifact_manifest_path = write_artifact_manifest(workspace, artifacts)

    return {
        "success": True,
        "workspace_dir": str(workspace),
        "video_analysis_path": str(breakdown_path),
        "capsule_draft_path": str(draft_path),
        "capsule_dir": str(capsule_dir) if capsule_dir else None,
        "capsule_name": draft["name"],
        "execution_strategy": draft.get("execution_strategy"),
        "analysis_tool_used": tool_name,
        "videomd_package": video_package.reference(pkg) if pkg is not None else None,
        "write_capsule": bool(write_capsule),
        "include_source_video": bool(include_source_video),
        "artifact_manifest_path": str(artifact_manifest_path),
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a local video and infer a reusable capsule draft.")
    parser.add_argument("--source-video-path", default="", help="Local source video. Optional with --videomd-package when the package holds it.")
    parser.add_argument(
        "--videomd-package",
        default="",
        help="VIDEO.md package (directory or its VIDEO.md, e.g. a rea-video output dir). Grounds the analyzer; "
        "without --video-analysis-tool it yields a preview draft from the package alone.",
    )
    parser.add_argument("--video-analysis-tool", default=DEFAULT_ANALYZER_TOOL)
    parser.add_argument("--capsule-name", default="")
    parser.add_argument("--capsule-display-name", default="")
    parser.add_argument("--capsule-summary", default="")
    parser.add_argument("--analysis-prompt", default="")
    parser.add_argument("--target-platform", default="")
    parser.add_argument("--no-videomd-lookup", action="store_true",
                        help="Do not look for an existing VIDEO.md breakdown of --source-video-path (by sha256).")
    parser.add_argument("--write-capsule", action="store_true")
    parser.add_argument("--include-source-video", action="store_true")
    parser.add_argument("--local-script-source", default="")
    parser.add_argument("--local-script-entry", default="")
    parser.add_argument(
        "--script-evidence",
        default="",
        help="JSON object or path proving the supplied local script is reusable.",
    )
    parser.add_argument("--overwrite-capsule", action="store_true")
    parser.add_argument("--output-base-dir", default="")
    parser.add_argument("--capsule-output-root", default="")
    args = parser.parse_args()

    result = run_video_to_capsule(
        source_video_path=args.source_video_path,
        videomd_package=args.videomd_package or None,
        lookup_videomd=not args.no_videomd_lookup,
        video_analysis_tool=args.video_analysis_tool,
        output_base_dir=args.output_base_dir or None,
        capsule_output_root=args.capsule_output_root or None,
        capsule_name=args.capsule_name,
        capsule_display_name=args.capsule_display_name,
        capsule_summary=args.capsule_summary,
        analysis_prompt=args.analysis_prompt,
        target_platform=args.target_platform,
        write_capsule=args.write_capsule,
        include_source_video=args.include_source_video,
        local_script_source=args.local_script_source or None,
        local_script_entry=args.local_script_entry,
        script_evidence=args.script_evidence or None,
        overwrite_capsule=args.overwrite_capsule,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
