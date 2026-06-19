#!/usr/bin/env python3
"""单分镜重生成脚本。

用法：
    python scripts/run_scene.py \
      --workspace_dir output/<run_id> \
      --scene_id 2 \
      --image_prompt "新的图片 prompt" \
      --video_prompt "New video prompt in English" \
      --image_engine seedream5 \
      --video_engine veo3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# scripts/this_script.py -> lib/ contains the runtime package.
_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPT_DIR.parent
_LIB_DIR = _SKILL_DIR / "lib"

sys.path.insert(0, str(_LIB_DIR))
sys.path.insert(0, str(_SCRIPT_DIR))

from env_loader import load_video_agent_env  # noqa: E402
from output_guard import require_workspace_under_output  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="单分镜重生成")
    parser.add_argument("--workspace_dir", required=True, help="已有工作目录")
    parser.add_argument("--scene_id", type=int, required=True, help="要重生成的分镜编号（从 1 开始）")
    parser.add_argument("--image_prompt", default=None, help="新的图片 prompt（不传则保留原 prompt）")
    parser.add_argument("--video_prompt", default=None, help="新的视频 prompt（不传则保留原 prompt）")
    parser.add_argument("--image_engine", default="seedream5", help="图片引擎：seedream5 / gpt-image-2 / gemini3_pro（默认 seedream5）")
    parser.add_argument("--video_engine", default="seedance-fast", help="视频引擎：seedance-fast / seedance / jimeng35pro / veo3 / veo3.1（默认 seedance-fast）")
    parser.add_argument("--aspect_ratio", default="9:16", help="画面比例（默认 9:16）")
    parser.add_argument("--skip_image", action="store_true", help="跳过图片生成，只重生成视频")
    parser.add_argument("--reference_image", default=None, help="角色参考图路径（可选）")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    load_video_agent_env(_SKILL_DIR)

    try:
        workspace = require_workspace_under_output(args.workspace_dir)
        from src.runtime.general_video_crew.scene_regenerator import regenerate_scene

        result = regenerate_scene(
            workspace_dir=workspace,
            scene_id=args.scene_id,
            image_prompt=args.image_prompt,
            video_prompt=args.video_prompt,
            image_engine=args.image_engine,
            video_engine=args.video_engine,
            aspect_ratio=args.aspect_ratio,
            skip_image=args.skip_image,
            reference_image=args.reference_image,
            progress=print,
        )
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        sys.exit(1)

    print("\n" + json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
