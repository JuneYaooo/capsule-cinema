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

import yaml


_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPT_DIR.parent
_LIB_DIR = _SKILL_DIR / "lib"
sys.path.insert(0, str(_LIB_DIR))
sys.path.insert(0, str(_SCRIPT_DIR))

from env_loader import load_video_agent_env  # noqa: E402
from src.video_to_capsule import (  # noqa: E402
    build_analysis_prompt,
    materialize_capsule_from_draft,
    normalize_video_analysis,
    write_artifact_manifest,
    write_json,
)


load_video_agent_env(_SKILL_DIR)

DEFAULT_ANALYZER_TOOL = "Gemini3VideoAnalyzerTool"


def _json_default(value: Any) -> str:
    return str(value)


def _safe_segment(value: str, default: str = "video") -> str:
    import re

    text = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip()).strip("_")
    return text or default


def load_tool_registry() -> dict[str, str]:
    registry_path = _LIB_DIR / "config" / "tool_registry.yaml"
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    tools = data.get("tools") or {}
    return {
        name: config["module"]
        for name, config in tools.items()
        if isinstance(config, dict) and config.get("module")
    }


def instantiate_tool(tool_name: str):
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


def run_video_to_capsule(
    *,
    source_video_path: str,
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
    overwrite_capsule: bool = False,
    tool_factory: Callable[[str], Any] = instantiate_tool,
) -> dict[str, Any]:
    source = Path(source_video_path).expanduser()
    if not source.is_file():
        raise SystemExit(f"source video not found: {source}")
    if write_capsule and not str(capsule_name or "").strip():
        raise SystemExit("capsule_name is required when write_capsule=true")

    tool_name = video_analysis_tool or DEFAULT_ANALYZER_TOOL
    workspace = create_workspace_dir(output_base_dir, source)
    analysis_dir = workspace / "analysis"
    warnings: list[str] = []

    source_metadata_path = write_json(analysis_dir / "source_video_metadata.json", _source_metadata(source))
    prompt = build_analysis_prompt(analysis_prompt=analysis_prompt, target_platform=target_platform)
    tool = tool_factory(tool_name)
    raw_result = tool._run(video_path=str(source), prompt=prompt, analysis_focus="content")
    raw_path = analysis_dir / "analyzer_raw_response.json"
    raw_path.write_text(json.dumps(raw_result, ensure_ascii=False, indent=2, default=_json_default) + "\n", encoding="utf-8")

    breakdown, draft = normalize_video_analysis(
        raw_result,
        source_video_path=str(source),
        analysis_tool=tool_name,
        capsule_name=capsule_name,
        capsule_display_name=capsule_display_name,
        capsule_summary=capsule_summary,
        target_platform=target_platform,
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
            overwrite=overwrite_capsule,
        )
    elif include_source_video:
        warnings.append("include_source_video ignored because write_capsule is false")

    artifact_manifest_path = write_artifact_manifest(
        workspace,
        [
            {"category": "source_video_metadata", "path": str(source_metadata_path), "title": "Source video metadata"},
            {"category": "video_analysis", "path": str(breakdown_path), "title": "Video breakdown"},
            {"category": "capsule_draft", "path": str(draft_path), "title": "Capsule draft"},
            {"category": "analyzer_raw_response", "path": str(raw_path), "title": "Analyzer raw response"},
        ],
    )

    return {
        "success": True,
        "workspace_dir": str(workspace),
        "video_analysis_path": str(breakdown_path),
        "capsule_draft_path": str(draft_path),
        "capsule_dir": str(capsule_dir) if capsule_dir else None,
        "capsule_name": draft["name"],
        "analysis_tool_used": tool_name,
        "write_capsule": bool(write_capsule),
        "include_source_video": bool(include_source_video),
        "artifact_manifest_path": str(artifact_manifest_path),
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a local video and infer a reusable capsule draft.")
    parser.add_argument("--source-video-path", required=True)
    parser.add_argument("--video-analysis-tool", default=DEFAULT_ANALYZER_TOOL)
    parser.add_argument("--capsule-name", default="")
    parser.add_argument("--capsule-display-name", default="")
    parser.add_argument("--capsule-summary", default="")
    parser.add_argument("--analysis-prompt", default="")
    parser.add_argument("--target-platform", default="")
    parser.add_argument("--write-capsule", action="store_true")
    parser.add_argument("--include-source-video", action="store_true")
    parser.add_argument("--overwrite-capsule", action="store_true")
    parser.add_argument("--output-base-dir", default="")
    parser.add_argument("--capsule-output-root", default="")
    args = parser.parse_args()

    result = run_video_to_capsule(
        source_video_path=args.source_video_path,
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
        overwrite_capsule=args.overwrite_capsule,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
