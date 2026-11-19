#!/usr/bin/env python3
"""Garment-detail crops: the same torso region from a reference image and from each candidate video at given seconds.

Product details (buttons, knit pattern, collar shape, fur length) drift once a video model starts moving the subject;
whole-frame sheets are too small to see it. This finds the person with segmentation, crops the torso band
(where the garments are), enlarges it, and lays the reference next to every candidate at each time.
Output is capped at --max-width (default 1280) to keep vision review cheap.

Usage: python scripts/remake_detail_crops.py --ref keyframe.png --video A=a.mp4 --video B=b.mp4 \
         --times 2,6,10 --out qa/detail.jpg [--band 0.12,0.62] [--max-width 1280]
Needs: pip install mediapipe, and ~/.cache/capsule-cinema/selfie_multiclass.tflite (mediapipe selfie_multiclass_256x256):
  curl -L -o ~/.cache/capsule-cinema/selfie_multiclass.tflite \\
    https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from PIL import Image, ImageDraw

MODEL = Path.home() / ".cache/capsule-cinema/selfie_multiclass.tflite"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite"

def ensure_model(path: Path, url: str) -> Path:
    """download the MediaPipe model on first use (~/.cache gets cleaned; a missing model must not break QA)"""
    if not path.exists():
        import urllib.request
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(path)
    return path



def torso(rgb, seg, band):
    m = (1 - seg.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
         .confidence_masks[0].numpy_view()).squeeze()
    ys, xs = np.where(m > 0.5)
    H, W = rgb.shape[:2]
    if len(ys) == 0:
        return Image.fromarray(rgb)
    top, bot = ys.min(), min(ys.max(), H - 1)
    h = bot - top
    y0, y1 = int(top + band[0] * h), int(top + band[1] * h)
    rows = m[y0:y1] > 0.5
    cols = np.where(rows.any(0))[0]
    x0, x1 = (cols.min(), cols.max()) if len(cols) else (0, W)
    pad = int(0.05 * (x1 - x0))
    return Image.fromarray(rgb[y0:y1, max(x0 - pad, 0):min(x1 + pad, W)])


def frame(path, t):
    cap = cv2.VideoCapture(str(path))
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, f = cap.read()
    return cv2.cvtColor(f, cv2.COLOR_BGR2RGB) if ok else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ref", required=True, help="reference image (e.g. the product-checked keyframe)")
    ap.add_argument("--video", action="append", required=True, help="LABEL=path, repeatable")
    ap.add_argument("--times", required=True, help="comma-separated seconds")
    ap.add_argument("--out", required=True)
    ap.add_argument("--band", default="0.12,0.62", help="torso band as share of person height (top,bottom)")
    ap.add_argument("--max-width", type=int, default=1280)
    a = ap.parse_args()
    band = tuple(float(x) for x in a.band.split(","))
    times = [float(t) for t in a.times.split(",")]
    vids = [v.split("=", 1) for v in a.video]
    opts = mp.tasks.vision.ImageSegmenterOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(ensure_model(MODEL, MODEL_URL))),
                                                 output_confidence_masks=True)
    cols = 1 + len(times)
    cw = a.max_width // cols
    ch = int(cw * 1.1)
    sheet = Image.new("RGB", (cols * cw, len(vids) * (ch + 18)), "white")
    d = ImageDraw.Draw(sheet)
    with mp.tasks.vision.ImageSegmenter.create_from_options(opts) as seg:
        ref = torso(np.array(Image.open(a.ref).convert("RGB")), seg, band)
        for r, (label, path) in enumerate(vids):
            y = r * (ch + 18)
            cells = [ref] + [torso(f, seg, band) if (f := frame(path, t)) is not None else Image.new("RGB", (10, 10), "gray")
                             for t in times]
            for c, im in enumerate(cells):
                im = im.copy(); im.thumbnail((cw - 4, ch))
                sheet.paste(im, (c * cw + (cw - im.width) // 2, y + 16))
            d.text((4, y + 1), f"{label}: reference | " + " | ".join(f"{t:g}s" for t in times), fill="black")
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=85)
    print(out, sheet.size)


if __name__ == "__main__":
    main()
