#!/usr/bin/env python3
"""重新拼接脚本 — 用 workspace 中的视频文件重新拼接最终视频。

用法：
    python scripts/run_concat.py \
      --workspace_dir /path/to/workspace \
      --video_files '["/path/to/scene_01.mp4", "/path/to/scene_02_v2.mp4", "/path/to/scene_03.mp4"]'

也可以不传 --video_files，脚本会自动从 storyboard.json 中读取每个分镜的最新视频路径。
"""

import argparse
import json
import os
import sys
from pathlib import Path

# ── boilerplate ──────────────────────────────────────────
# Skill 目录结构: scripts/this_script.py → lib/ 是工具库
_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPT_DIR.parent
_LIB_DIR = _SKILL_DIR / "lib"

# project_root 指向 lib/ 目录（包含 custom_tools/, agents/, agno_agents/）
project_root = _LIB_DIR
sys.path.insert(0, str(_LIB_DIR))
sys.path.insert(0, str(_SCRIPT_DIR))

from env_loader import load_video_agent_env  # noqa: E402

load_video_agent_env(_SKILL_DIR)

from src.contracts import get_storyboard_scenes, scene_display_id, scene_order  # noqa: E402
# ─────────────────────────────────────────────────────────


def collect_videos_from_storyboard(workspace_dir: Path) -> list[str]:
    """从 storyboard.json 中按分镜顺序收集最新的视频路径。"""
    sb_path = workspace_dir / "storyboard.json"
    if not sb_path.exists():
        print(f"错误：找不到 storyboard.json: {sb_path}")
        sys.exit(1)

    with open(sb_path, "r", encoding="utf-8") as f:
        storyboard = json.load(f)

    scenes = sorted(
        enumerate(get_storyboard_scenes(storyboard), start=1),
        key=lambda item: scene_order(item[1], item[0]),
    )
    video_paths = []
    for fallback, scene in scenes:
        vp = scene.get("video_path", "")
        if vp and Path(vp).exists():
            video_paths.append(vp)
        else:
            print(f"警告：分镜 {scene_display_id(scene, fallback)} 没有有效的视频路径: {vp}")
    return video_paths


def collect_audios_from_storyboard(workspace_dir: Path) -> list[str]:
    """从 storyboard.json 中按分镜顺序收集配音路径。"""
    sb_path = workspace_dir / "storyboard.json"
    with open(sb_path, "r", encoding="utf-8") as f:
        storyboard = json.load(f)

    scenes = sorted(
        enumerate(get_storyboard_scenes(storyboard), start=1),
        key=lambda item: scene_order(item[1], item[0]),
    )
    audio_paths = []
    for _, scene in scenes:
        ap = scene.get("audio_path", "")
        if ap and Path(ap).exists():
            audio_paths.append(ap)
    return audio_paths


def main():
    parser = argparse.ArgumentParser(description="重新拼接视频")
    parser.add_argument("--workspace_dir", required=True, help="工作目录")
    parser.add_argument("--video_files", default=None, help="JSON 列表，指定视频文件路径（按顺序）。不传则自动从 storyboard 读取")
    parser.add_argument("--voice_volume", type=float, default=1.5, help="配音音量（默认 1.5）")
    args = parser.parse_args()

    workspace = Path(args.workspace_dir)
    if not workspace.exists():
        print(f"错误：workspace 不存在: {workspace}")
        sys.exit(1)

    # 收集视频路径
    if args.video_files:
        video_paths = json.loads(args.video_files)
    else:
        video_paths = collect_videos_from_storyboard(workspace)

    if not video_paths:
        print("错误：没有找到可拼接的视频文件")
        sys.exit(1)

    # 收集配音路径
    audio_paths = collect_audios_from_storyboard(workspace)

    # 输出目录：新布局用 release/，旧 workspace 已有 final/ 时沿用
    final_dir = workspace / "final" if (workspace / "final").is_dir() else workspace / "release"
    final_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(final_dir / "final_video.mp4")

    print(f"拼接 {len(video_paths)} 个视频片段 ...")
    for i, vp in enumerate(video_paths, 1):
        print(f"  [{i}] {vp}")

    from custom_tools.video_processing.video_concatenate_tool import ConcatenateVideosTool

    tool = ConcatenateVideosTool()
    kwargs = {
        "video_paths": video_paths,
        "output_path": output_path,
        "voice_volume": args.voice_volume,
    }
    if audio_paths:
        kwargs["audio_paths"] = audio_paths
        print(f"配音文件: {len(audio_paths)} 个")

    result = tool._run(**kwargs)

    if isinstance(result, dict):
        final_path = result.get("output_path", output_path)
        print(f"\n拼接完成: {final_path}")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"\n拼接结果: {result}")


if __name__ == "__main__":
    main()
