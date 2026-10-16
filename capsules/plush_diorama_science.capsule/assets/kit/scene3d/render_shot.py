"""渲染一个镜头的帧序列。

$BLENDER -b --factory-startup -P render_shot.py -- <shot_id> [--preview] [--frames a,b,c] [--samples N] [--force]
--preview：540x960、8 采样，只出指定帧（默认首/中/尾）到 ../../frames/<shot>_preview/，用于检查构图。
正式：1080x1920、24 采样，输出 ../../frames/<shot>/f_%04d.jpg（帧号从 0 开始，相对镜头起点）；
已存在的帧跳过（中断后接着渲），--force 重渲。每个镜头多渲 1 帧，剪辑时丢掉。
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bpy  # noqa: E402
import lib3d as L  # noqa: E402
import shots as S  # noqa: E402

WORK = HERE.parent
OUT = WORK.parent / "frames"
FONT_PATH = str(WORK.parent / "fonts" / "ZCOOLKuaiLe-Regular.ttf")   # 3D 字（罐签之类）用

argv = sys.argv[sys.argv.index("--") + 1:]
shot_id = argv[0]
preview = "--preview" in argv
samples = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else (8 if preview else 24)
tl = json.loads((WORK / "timeline.json").read_text())
shot = next(s for s in tl["shots"] if s["id"] == shot_id)
fps = tl["fps"]
n = shot["f1"] - shot["f0"] + 1   # 多渲染 1 帧，剪辑时可裁

if "--frames" in argv:
    frames = [int(x) for x in argv[argv.index("--frames") + 1].split(",")]
elif preview:
    frames = [0, n // 2, n - 2]
else:
    frames = list(range(n))

t0 = time.time()
L.reset_scene()
S.FONT = FONT_PATH
state = S.SHOTS[shot_id]()
bpy.context.scene.camera.data.shift_y = S.SHIFT_Y.get(shot_id, 0.0)
L.setup_render(res=(540, 960) if preview else (1080, 1920), samples=samples, fps=fps)
sc = bpy.context.scene
odir = OUT / (shot_id + ("_preview" if preview else ""))
odir.mkdir(parents=True, exist_ok=True)
t_build = time.time() - t0
for f in frames:
    path = odir / f"f_{f:04d}.jpg"
    if path.exists() and not preview and "--force" not in argv:
        continue
    state(f / fps, shot["events"])
    bpy.context.view_layer.update()
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
print(f"SHOT {shot_id} frames={len(frames)} build={t_build:.1f}s total={time.time() - t0:.1f}s", flush=True)
