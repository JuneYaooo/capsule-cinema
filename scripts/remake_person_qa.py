#!/usr/bin/env python3
"""Person QA for a remake vs its source: head size (head-to-body ratio) and mouth opening (invented talking).

Checks garments/hands/background miss two things viewers notice at once:
  * head too big / body too short  -> face height as a share of the frame, remake vs source (same seconds)
  * a silent subject that suddenly "talks" or grins -> mouth opening (inner-lip gap / face height) per second
Both are measured with MediaPipe face landmarks and compared second by second; outliers are flagged.
Also writes <out>.jpg: one row source, one row remake, a face crop per sampled second.

Usage: python scripts/remake_person_qa.py --source src.mp4 --remake remake.mp4 [--out qa/name] [--every 0.5]
       [--head-tol 0.10] [--mouth-tol 0.03]
Exit code 1 when a check fails (so it can gate a pipeline).
Needs: pip install mediapipe, and the face landmarker model at ~/.cache/capsule-cinema/face_landmarker.task:
  curl -L -o ~/.cache/capsule-cinema/face_landmarker.task \
    https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from PIL import Image, ImageDraw

MODEL = Path.home() / ".cache/capsule-cinema/face_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"

def ensure_model(path: Path, url: str) -> Path:
    """download the MediaPipe model on first use (~/.cache gets cleaned; a missing model must not break QA)"""
    if not path.exists():
        import urllib.request
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(path)
    return path

UP_LIP, LOW_LIP, TOP, CHIN = 13, 14, 10, 152  # inner lips, forehead top, chin (FaceMesh indices)


def measure(path, times, lm):
    cap = cv2.VideoCapture(str(path))
    rows = []
    for t in times:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, f = cap.read()
        if not ok:
            rows.append(None); continue
        rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
        H, W = rgb.shape[:2]
        found = None
        # full frame first; a full-body shot leaves the face too small for the landmarker, so retry on the
        # upper-middle region (where a standing subject's head is) and map back to frame coordinates
        for x0, y0, x1, y1 in ((0, 0, 1, 1), (0.15, 0, 0.85, 0.55), (0.25, 0.05, 0.75, 0.4)):
            sub = np.ascontiguousarray(rgb[int(y0 * H):int(y1 * H), int(x0 * W):int(x1 * W)])
            res = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=sub))
            if res.face_landmarks:
                found = [(x0 + p.x * (x1 - x0), y0 + p.y * (y1 - y0)) for p in res.face_landmarks[0]]
                break
        if not found:
            rows.append({"t": t, "crop": None}); continue
        face_h = abs(found[CHIN][1] - found[TOP][1])           # share of frame height
        mouth = abs(found[LOW_LIP][1] - found[UP_LIP][1]) / max(face_h, 1e-6)
        xs = [x * W for x, _ in found]; ys = [y * H for _, y in found]
        cx, cy, s = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (max(ys) - min(ys)) * 0.75
        crop = rgb[int(max(cy - s, 0)):int(cy + s), int(max(cx - s, 0)):int(cx + s)]
        rows.append({"t": t, "face": face_h, "mouth": mouth, "crop": Image.fromarray(crop).resize((120, 120))})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True)
    ap.add_argument("--remake", required=True)
    ap.add_argument("--out", help="output prefix (writes .jpg and .json)")
    ap.add_argument("--every", type=float, default=0.5)
    ap.add_argument("--max-width", type=int, default=1280, help="cap the review sheet width (vision-token cost)")
    ap.add_argument("--head-tol", type=float, default=0.10, help="allowed |remake/source - 1| of the median face size")
    ap.add_argument("--mouth-tol", type=float, default=0.03, help="allowed extra mouth opening (share of face height)")
    a = ap.parse_args()

    def length(p):
        c = cv2.VideoCapture(str(p)); return c.get(cv2.CAP_PROP_FRAME_COUNT) / max(c.get(cv2.CAP_PROP_FPS), 1)
    times = list(np.arange(0.25, min(length(a.source), length(a.remake)) - 0.1, a.every))
    opts = mp.tasks.vision.FaceLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(ensure_model(MODEL, MODEL_URL))), num_faces=1)
    with mp.tasks.vision.FaceLandmarker.create_from_options(opts) as lm:
        src, rem = measure(a.source, times, lm), measure(a.remake, times, lm)

    pairs = [(s, r) for s, r in zip(src, rem) if s and r and "face" in s and "face" in r]
    head = float(np.median([r["face"] / s["face"] for s, r in pairs])) if pairs else float("nan")
    mouth_extra = [(r["t"], r["mouth"] - s["mouth"]) for s, r in pairs]
    talking = [(round(t, 2), round(d, 3)) for t, d in mouth_extra if d > a.mouth_tol]
    report = {
        "head_ratio_median": round(head, 3),
        "head_ok": abs(head - 1) <= a.head_tol,
        "mouth_src_max": round(max((s["mouth"] for s, _ in pairs), default=0), 3),
        "mouth_remake_max": round(max((r["mouth"] for _, r in pairs), default=0), 3),
        "mouth_flags": talking,                     # seconds where the remake opens the mouth well beyond the source
        "mouth_ok": len(talking) <= 1,  # calibrated: clay-driven Kling (invented talking) 4 flags, real-footage drive 0
        "faces_compared": len(pairs), "no_face_in_remake": sum(1 for r in rem if r and "face" not in r),
    }
    print(json.dumps(report, ensure_ascii=False, indent=1))

    if a.out:
        out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
        per = max(1, a.max_width // 122)            # wrap into row-pairs instead of squashing faces
        groups = [list(range(k, min(k + per, len(times)))) for k in range(0, len(times), per)]
        sheet = Image.new("RGB", (per * 122, len(groups) * 262), "white")
        d = ImageDraw.Draw(sheet)
        flagged = {t for t, _ in talking}
        for g, idx in enumerate(groups):
            y0 = g * 262
            for col, i in enumerate(idx):
                s, r = src[i], rem[i]
                for j, row in enumerate((s, r)):
                    c = row.get("crop") if row else None
                    sheet.paste(c or Image.new("RGB", (120, 120), "gray"), (col * 122, y0 + j * 122))
                if r and round(r["t"], 2) in flagged:
                    d.rectangle([col * 122, y0 + 122, col * 122 + 119, y0 + 241], outline="red", width=4)
                d.text((col * 122 + 3, y0 + 246), f"{times[i]:.1f}s", fill="black")
        sheet.save(out.with_suffix(".jpg"), quality=85)
        out.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    sys.exit(0 if report["head_ok"] and report["mouth_ok"] else 1)


if __name__ == "__main__":
    main()
