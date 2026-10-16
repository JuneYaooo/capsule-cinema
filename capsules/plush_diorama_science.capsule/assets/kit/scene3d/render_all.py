"""并行渲染全部镜头（每个 Blender 进程一个镜头，已存在的帧跳过）。

python3.12 render_all.py [--jobs 2] [--only sh03,sh07] [--samples 24] [--preview] [--force]
Blender 路径：环境变量 BLENDER，否则找 PATH 里的 blender，再试 macOS 默认安装位置。
1080x1920、24 采样带毛发约 2 s/帧（单进程），2 个进程并行约 3.7 s/帧/进程；再多进程不会更快。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
MAC_DEFAULT = "/Applications/Blender.app/Contents/MacOS/Blender"
BLENDER = os.environ.get("BLENDER") or shutil.which("blender") or (MAC_DEFAULT if os.path.exists(MAC_DEFAULT) else "")
if not BLENDER:
    sys.exit("找不到 Blender：设置环境变量 BLENDER（需要 Blender 5.x）")

ap = argparse.ArgumentParser()
ap.add_argument("--jobs", type=int, default=2)
ap.add_argument("--only", default="")
ap.add_argument("--samples", type=int, default=24)
ap.add_argument("--force", action="store_true")
ap.add_argument("--preview", action="store_true", help="每个镜头只出首/中/尾 3 帧小图")
args = ap.parse_args()

tl = json.loads((WORK / "timeline.json").read_text())
shots = [s["id"] for s in tl["shots"]]
if args.only:
    want = set(args.only.split(","))
    shots = [s for s in shots if s in want]


def run(shot):
    t0 = time.time()
    cmd = [BLENDER, "-b", "--factory-startup", "-P", str(HERE / "render_shot.py"), "--", shot,
           "--samples", str(8 if args.preview else args.samples)] + (["--force"] if args.force else []) \
        + (["--preview"] if args.preview else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    tail = [l for l in r.stdout.splitlines() + r.stderr.splitlines()
            if l.startswith("SHOT") or "Error" in l or "Traceback" in l]
    return f"{shot} rc={r.returncode} {time.time() - t0:.0f}s {' | '.join(tail[-3:])}"


t_all = time.time()
with ThreadPoolExecutor(args.jobs) as ex:
    for msg in ex.map(run, shots):
        print(msg, flush=True)
print(f"ALL DONE {time.time() - t_all:.0f}s", flush=True)
