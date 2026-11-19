#!/usr/bin/env python3
"""Match a remake's overall color (brightness, warm/cool, saturation) to a reference video, one fixed transform for all frames.

Generated keyframes often over-cook the relighting (a "warm sunlight" prompt turns everything orange; a "bright window"
prompt washes it out), and the video model then carries that cast through every frame. This measures LAB mean/std of the
reference and of the remake over sampled frames, builds ONE affine transform per LAB channel (Reinhard transfer), blends
it with --strength, and applies it to every frame, so relative colors (skin vs garments) stay intact and there is no flicker.
Audio is copied. Works on images too (--image).

Usage: python scripts/remake_color_match.py --ref source.mp4 --in remake.mp4 --out graded.mp4 [--strength 0.8]
       python scripts/remake_color_match.py --ref source.mp4 --image keyframe.png --out keyframe_graded.png
Prints the LAB stats before / after so the change is measurable.
"""
from __future__ import annotations

import argparse
import subprocess

import cv2
import numpy as np


def sample(path, n=12):
    cap = cv2.VideoCapture(str(path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    frames = []
    for i in np.linspace(0, total - 1, n).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, f = cap.read()
        if ok:
            frames.append(cv2.resize(f, (270, 480)))
    return frames


def lab_stats(bgr_frames):
    lab = np.concatenate([cv2.cvtColor(f, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32) for f in bgr_frames])
    return lab.mean(0), lab.std(0) + 1e-6


def describe(bgr_frames):
    m, _ = lab_stats(bgr_frames)
    sat = np.mean([cv2.cvtColor(f, cv2.COLOR_BGR2HSV)[..., 1].mean() for f in bgr_frames])
    return f"L {m[0] * 100 / 255:.0f}  a {m[1] - 128:+.1f}  b(warm) {m[2] - 128:+.1f}  sat {sat:.0f}"


def transform(ref_frames, in_frames, strength):
    rm, rs = lab_stats(ref_frames)
    im, is_ = lab_stats(in_frames)
    scale = 1 + strength * (rs / is_ - 1)
    target = im + strength * (rm - im)
    return lambda lab: (lab - im) * scale + target


def apply(bgr, fn):
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    return cv2.cvtColor(np.clip(fn(lab), 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ref", required=True, help="reference video or image (the look to match)")
    ap.add_argument("--in", dest="inp", help="remake video")
    ap.add_argument("--image", help="remake image instead of a video")
    ap.add_argument("--out", required=True)
    ap.add_argument("--strength", type=float, default=0.8, help="0 = unchanged, 1 = full match")
    a = ap.parse_args()

    ref = [cv2.imread(a.ref)] if a.ref.lower().endswith((".png", ".jpg", ".jpeg")) else sample(a.ref)
    if a.image:
        img = cv2.imread(a.image)
        fn = transform(ref, [cv2.resize(img, (270, 480))], a.strength)
        out = apply(img, fn)
        cv2.imwrite(a.out, out)
        print("ref   ", describe(ref)); print("before", describe([img])); print("after ", describe([out]))
        return
    inp = sample(a.inp)
    fn = transform(ref, inp, a.strength)
    cap = cv2.VideoCapture(a.inp)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", f"{fps}",
                            "-i", "-", "-i", a.inp, "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-crf", "17",
                            "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                            "-color_range", "tv", "-c:a", "copy", "-shortest", a.out], stdin=subprocess.PIPE)
    while True:
        ok, f = cap.read()
        if not ok:
            break
        enc.stdin.write(apply(f, fn).tobytes())
    enc.stdin.close(); enc.wait()
    print("ref   ", describe(ref)); print("before", describe(inp)); print("after ", describe(sample(a.out)))


if __name__ == "__main__":
    main()
