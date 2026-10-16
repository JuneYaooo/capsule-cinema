"""逐帧把标注锚点投影成 1080x1920 像素坐标（只搭场景、不渲染，几秒一个镜头）。

$BLENDER -b --factory-startup -P project_labels.py
输出 ../labels_px.json：{shot: {label_id: [[x, y], ...每帧]}}；overlay.py 读它让标签跟着物体走。
改了 shots.py 里有标签的镜头（位置、相机、shift_y），要重跑这个。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import bpy  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402

import lib3d as L  # noqa: E402
import shots as S  # noqa: E402
from episode import LABELS  # noqa: E402

WORK = HERE.parent
W, H = 1080, 1920

tl = json.loads((WORK / "timeline.json").read_text())
fps = tl["fps"]
out = {}
for shot in tl["shots"]:
    sid = shot["id"]
    if sid not in LABELS:
        continue
    L.reset_scene()
    S.FONT = str(WORK.parent / "fonts" / "ZCOOLKuaiLe-Regular.ttf")
    state = S.SHOTS[sid]()
    sc = bpy.context.scene
    sc.camera.data.shift_y = S.SHIFT_Y.get(sid, 0.0)
    L.setup_render(res=(W, H), samples=1, fps=fps)
    tracks = {lb["id"]: [] for lb in LABELS[sid]}
    for f in range(shot["f1"] - shot["f0"] + 1):
        state(f / fps, shot["events"])
        bpy.context.view_layer.update()
        for lb in LABELS[sid]:
            ob = bpy.data.objects.get(lb["obj"])
            if ob is None:
                sys.exit(f"{sid} 的标签 {lb['id']}：shots.py 里没有叫 {lb['obj']} 的物体（物体名要和 build 里起的名字一致）")
            p = ob.matrix_world.translation + Vector(lb.get("off", (0, 0, 0)))
            v = world_to_camera_view(sc, sc.camera, p)
            tracks[lb["id"]].append([round(v.x * W, 1), round((1 - v.y) * H, 1)])
    out[sid] = tracks
    print("PROJ", sid, {k: v[len(v) // 2] for k, v in tracks.items()}, flush=True)
(WORK / "labels_px.json").write_text(json.dumps(out))
print("PROJ DONE", flush=True)
