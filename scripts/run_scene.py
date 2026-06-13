#!/usr/bin/env python3
"""单分镜重生成脚本 — 在已有 workspace 中重新生成指定分镜的图片和/或视频。

用法：
    python scripts/run_scene.py \
      --workspace_dir /path/to/workspace \
      --scene_id 2 \
      --image_prompt "新的图片 prompt" \
      --video_prompt "New video prompt in English" \
      --video_engine veo3
"""

import argparse
import json
import os
import re
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

from src.contracts import (  # noqa: E402
    find_scene_by_id,
    get_scene_prompt,
    get_storyboard_scenes,
    scene_display_id,
    set_storyboard_scenes,
)
# ─────────────────────────────────────────────────────────


def find_next_version(directory: Path, scene_id: int, ext: str) -> int:
    """扫描目录中 scene_{id}_v{n}.{ext} 文件，返回下一个版本号。"""
    pattern = re.compile(rf"scene_{scene_id:02d}_v(\d+)\.{ext}$")
    max_v = 0
    if directory.exists():
        for f in directory.iterdir():
            m = pattern.match(f.name)
            if m:
                max_v = max(max_v, int(m.group(1)))
    return max_v + 1


def load_storyboard(workspace_dir: Path) -> dict:
    sb_path = workspace_dir / "storyboard.json"
    if not sb_path.exists():
        print(f"错误：找不到 storyboard.json: {sb_path}")
        sys.exit(1)
    with open(sb_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_storyboard(workspace_dir: Path, data: dict):
    sb_path = workspace_dir / "storyboard.json"
    with open(sb_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def generate_image(prompt: str, output_path: str, aspect_ratio: str, reference_image: str = None):
    from custom_tools.image_generation.gemini3_pro_image_tool import Gemini3ProImageGeneratorTool

    tool = Gemini3ProImageGeneratorTool()
    kwargs = {"prompt": prompt, "output_path": output_path, "aspect_ratio": aspect_ratio}
    if reference_image:
        kwargs["reference_image_paths"] = [reference_image]
    result = tool._run(**kwargs)
    # Gemini3Pro 返回消息字符串，确认文件存在即可
    if Path(output_path).exists():
        return output_path
    # 尝试从返回消息中解析路径
    if isinstance(result, str) and "保存到" in result:
        parts = result.split("保存到")
        if len(parts) > 1:
            parsed = parts[-1].strip().rstrip("。").strip()
            if Path(parsed).exists():
                return parsed
    print(f"警告：图片生成结果不确定，返回值: {result}")
    return output_path


def generate_video(prompt: str, image_path: str, output_dir: str, engine: str, aspect_ratio: str):
    if engine == "veo3":
        from custom_tools.video_generation.veo3_video_generator_tool import Veo3VideoGeneratorTool
        tool = Veo3VideoGeneratorTool()
    else:
        from custom_tools.video_generation.jimeng35pro_video_generator_tool import Jimeng35ProVideoGeneratorTool
        tool = Jimeng35ProVideoGeneratorTool()

    kwargs = {
        "prompt": prompt,
        "output_dir": output_dir,
        "aspect_ratio": aspect_ratio,
    }
    if image_path and Path(image_path).exists():
        kwargs["generation_type"] = "image_to_video"
        kwargs["image_path"] = image_path
    else:
        kwargs["generation_type"] = "text_to_video"

    result = tool._run(**kwargs)
    if isinstance(result, dict):
        return result.get("output_path", "")
    return str(result)


def main():
    parser = argparse.ArgumentParser(description="单分镜重生成")
    parser.add_argument("--workspace_dir", required=True, help="已有工作目录")
    parser.add_argument("--scene_id", type=int, required=True, help="要重生成的分镜编号（从 1 开始）")
    parser.add_argument("--image_prompt", default=None, help="新的图片 prompt（不传则保留原 prompt）")
    parser.add_argument("--video_prompt", default=None, help="新的视频 prompt（不传则保留原 prompt）")
    parser.add_argument("--video_engine", default="jimeng35pro", help="视频引擎：jimeng35pro / veo3（默认 jimeng35pro）")
    parser.add_argument("--aspect_ratio", default="9:16", help="画面比例（默认 9:16）")
    parser.add_argument("--skip_image", action="store_true", help="跳过图片生成，只重生成视频")
    parser.add_argument("--reference_image", default=None, help="角色参考图路径（可选）")
    args = parser.parse_args()

    workspace = Path(args.workspace_dir)
    if not workspace.exists():
        print(f"错误：workspace 不存在: {workspace}")
        sys.exit(1)

    # 加载 storyboard
    storyboard = load_storyboard(workspace)
    scenes = get_storyboard_scenes(storyboard)
    target_idx, target = find_scene_by_id(scenes, args.scene_id)

    if target is None:
        available = [scene_display_id(s, i + 1) for i, s in enumerate(scenes)]
        print(f"错误：找不到分镜 {args.scene_id}，可用分镜: {available}")
        sys.exit(1)

    # 确定 prompt
    img_prompt = args.image_prompt or get_scene_prompt(target, "image")
    vid_prompt = args.video_prompt or get_scene_prompt(target, "video")

    # 新布局中间产物在 work/ 下；旧 workspace 直接在根目录
    subroot = workspace / "work" if (workspace / "work").is_dir() or not (workspace / "images").is_dir() else workspace
    images_dir = subroot / "images"
    videos_dir = subroot / "videos"
    images_dir.mkdir(parents=True, exist_ok=True)
    videos_dir.mkdir(parents=True, exist_ok=True)

    result = {"scene_id": args.scene_id, "status": "success"}
    new_image_path = None

    # Step 1: 生成图片
    if not args.skip_image:
        version = find_next_version(images_dir, args.scene_id, "png")
        img_filename = f"scene_{args.scene_id:02d}_v{version}.png"
        img_output = str(images_dir / img_filename)
        print(f"[1/2] 生成图片: {img_filename} ...")
        new_image_path = generate_image(
            prompt=img_prompt,
            output_path=img_output,
            aspect_ratio=args.aspect_ratio,
            reference_image=args.reference_image,
        )
        result["image_path"] = new_image_path
        result["image_prompt"] = img_prompt
        print(f"  → 图片已保存: {new_image_path}")
    else:
        # 跳过图片，使用已有图片
        existing = target.get("image_path", "")
        if existing and Path(existing).exists():
            new_image_path = existing
        print("[1/2] 跳过图片生成")

    # Step 2: 生成视频
    version = find_next_version(videos_dir, args.scene_id, "mp4")
    vid_filename = f"scene_{args.scene_id:02d}_v{version}.mp4"
    vid_output_dir = str(videos_dir)
    print(f"[2/2] 生成视频: {vid_filename} (engine={args.video_engine}) ...")
    video_path = generate_video(
        prompt=vid_prompt,
        image_path=new_image_path,
        output_dir=vid_output_dir,
        engine=args.video_engine,
        aspect_ratio=args.aspect_ratio,
    )
    # 如果输出文件名不匹配，重命名
    if video_path and Path(video_path).exists():
        target_vid_path = videos_dir / vid_filename
        if Path(video_path) != target_vid_path:
            os.rename(video_path, target_vid_path)
            video_path = str(target_vid_path)
    result["video_path"] = video_path
    result["video_prompt"] = vid_prompt
    print(f"  → 视频已保存: {video_path}")

    # Step 3: 更新 storyboard
    if args.image_prompt:
        scenes[target_idx]["image_prompt"] = args.image_prompt
    if args.video_prompt:
        scenes[target_idx]["video_prompt"] = args.video_prompt
    if new_image_path and not args.skip_image:
        scenes[target_idx]["image_path"] = new_image_path
    if video_path:
        scenes[target_idx]["video_path"] = video_path
    scenes[target_idx]["regen_version"] = version
    scenes[target_idx]["regen_engine"] = args.video_engine

    set_storyboard_scenes(storyboard, scenes)
    save_storyboard(workspace, storyboard)
    result["storyboard_updated"] = True

    print("\n" + json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
