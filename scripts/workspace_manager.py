#!/usr/bin/env python3
"""Workspace 管理工具 — 统一所有工作流的输出目录。

所有工作流的输出统一存放在 OUTPUT_BASE_DIR 下，每次运行一个 run 目录：

    <OUTPUT_BASE_DIR>/
    ├── full-video_20260227_143000/          ← run_id = <workflow>_<timestamp>[_<project>]
    │   ├── release/                          ← 最终成片 + manifest
    │   │   └── 猫咪做饭_20260227_143000.mp4
    │   ├── work/                             ← 中间产物
    │   │   ├── images/
    │   │   ├── audios/
    │   │   ├── videos/
    │   │   ├── reference_images/
    │   │   └── temp/
    │   ├── qa/                               ← 质检报告
    │   ├── logs/
    │   │   └── project.log
    │   └── storyboard.json
    ├── action-transfer_20260227_160000/
    │   └── ...
    └── latest -> full-video_20260227_143000/  ← 最近一次生成

OUTPUT_BASE_DIR 可通过以下方式配置（优先级从高到低）：
1. 命令行参数 --output_base_dir
2. 环境变量 OPENCLAW_OUTPUT_DIR
3. 默认值: 当前项目根目录下的 output/

显式配置也必须解析到当前项目 output/ 或其子目录，避免最终产物散落到仓库外。

用户可以在任何时候查看 latest/ 符号链接找到最近的生成结果。
"""
import time
from pathlib import Path
from typing import Optional

from output_guard import get_output_base_dir  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_BASE_DIR = PROJECT_ROOT / "output"


def create_workspace(
    workflow: str,
    output_base_dir: Optional[str] = None,
    project_name: Optional[str] = None,
) -> dict:
    """创建标准化的 workspace 目录结构。

    Args:
        workflow: 工作流类型 (full-video, novel-manga, action-transfer, digital-human, feedback)
        output_base_dir: 输出根目录（可选）
        project_name: 项目名称后缀（可选）

    Returns:
        {
            "workspace_dir": "/path/to/<base>/<run_id>",
            "output_dirs": {
                "release": ..., "work": ..., "qa": ..., "logs": ...,
                "images": ..., "audios": ..., "videos": ...,
                "reference_images": ..., "temp": ...,
            }
        }
    """
    base = get_output_base_dir(output_base_dir)
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    run_id = f"{workflow}_{timestamp}_{project_name}" if project_name else f"{workflow}_{timestamp}"
    workspace = base / run_id

    work = workspace / "work"
    output_dirs = {
        "release": workspace / "release",
        "work": work,
        "qa": workspace / "qa",
        "logs": workspace / "logs",
        "images": work / "images",
        "audios": work / "audios",
        "videos": work / "videos",
        "reference_images": work / "reference_images",
        "temp": work / "temp",
    }
    for p in output_dirs.values():
        p.mkdir(parents=True, exist_ok=True)
    output_dirs = {key: str(value) for key, value in output_dirs.items()}

    # 更新 latest 符号链接
    latest_link = base / "latest"
    try:
        if latest_link.is_symlink() or latest_link.exists():
            latest_link.unlink()
        latest_link.symlink_to(workspace)
    except OSError:
        pass  # Windows 或权限问题，不影响主流程

    return {
        "workspace_dir": str(workspace),
        "output_dirs": output_dirs,
    }


def list_workspaces(
    output_base_dir: Optional[str] = None,
    workflow: Optional[str] = None,
    limit: int = 10,
) -> list:
    """列出最近的 workspace。

    Returns:
        [{"workflow": "full-video", "workspace": "...", "name": "...", "has_final": True}, ...]
    """
    base = get_output_base_dir(output_base_dir)
    results = []

    def final_video_exists(ws: Path) -> bool:
        for sub in ("release", "final"):
            d = ws / sub
            if d.exists() and any(d.glob("*.mp4")):
                return True
        return False

    for entry in base.iterdir():
        if not entry.is_dir() or entry.name == "latest":
            continue
        if (entry / "release").exists() or (entry / "work").exists():
            wf = entry.name.rsplit("_", 2)[0] if "_" in entry.name else entry.name
            if workflow and wf != workflow:
                continue
            results.append({
                "workflow": wf,
                "workspace": str(entry),
                "name": entry.name,
                "has_final": final_video_exists(entry),
            })

    # 按目录名（时间戳）倒序，取最近 N 个
    results.sort(key=lambda x: x["name"], reverse=True)
    return results[:limit]


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Workspace 管理")
    sub = parser.add_subparsers(dest="command")

    create_p = sub.add_parser("create", help="创建新 workspace")
    create_p.add_argument("--workflow", required=True)
    create_p.add_argument("--output_base_dir", default=None)
    create_p.add_argument("--project_name", default=None)

    list_p = sub.add_parser("list", help="列出最近的 workspace")
    list_p.add_argument("--output_base_dir", default=None)
    list_p.add_argument("--workflow", default=None)
    list_p.add_argument("--limit", type=int, default=10)

    args = parser.parse_args()

    try:
        if args.command == "create":
            result = create_workspace(args.workflow, args.output_base_dir, args.project_name)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "list":
            results = list_workspaces(args.output_base_dir, args.workflow, args.limit)
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            parser.print_help()
    except ValueError as exc:
        print(f"错误：{exc}")
        raise SystemExit(1) from exc
