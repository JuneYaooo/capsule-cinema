#!/usr/bin/env python3
"""Source-over-remake contact sheet for review, sized for cheap vision review.

One column per sampled second, source on top, remake below (garments, hands, joints, background at a glance).
The sheet is capped at --max-width (default 1280) and split into several images if needed, because a vision
model bills ~1 token per 28x28 px (a 1280x720 image ~1.2k tokens; a full-res portrait frame up to ~4.8k) and
every image left in an agent's context is re-read on every later turn.
Review rule: run the numeric checks first (remake_person_qa.py etc.) and look at sheets only for what failed
or what numbers cannot judge; hand the looking to a sub-agent that answers in text.

Usage: python scripts/remake_frame_sheet.py --source src.mp4 --remake remake.mp4 --out qa/name.jpg
       [--every 1.0] [--max-width 1280] [--cols 10]
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image


def frames(path, times, w):
    import cv2
    cap = cv2.VideoCapture(str(path)); out = []
    for t in times:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, f = cap.read()
        if not ok:
            out.append(None); continue
        h = round(f.shape[0] * w / f.shape[1])
        out.append(Image.fromarray(cv2.cvtColor(cv2.resize(f, (w, h)), cv2.COLOR_BGR2RGB)))
    return out


def length(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True)
    ap.add_argument("--remake", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--every", type=float, default=1.0)
    ap.add_argument("--max-width", type=int, default=1280)
    ap.add_argument("--cols", type=int, default=10, help="seconds per sheet row-pair")
    a = ap.parse_args()

    times = list(np.arange(0.5, min(length(a.source), length(a.remake)) - 0.05, a.every))
    cw = a.max_width // a.cols
    src, rem = frames(a.source, times, cw), frames(a.remake, times, cw)
    ch = max((im.height for im in src + rem if im), default=cw * 16 // 9)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    written = []
    for k in range(0, len(times), a.cols):
        sheet = Image.new("RGB", (a.max_width, 2 * ch + 4), "white")
        for i, (s, r) in enumerate(zip(src[k:k + a.cols], rem[k:k + a.cols])):
            for j, im in enumerate((s, r)):
                if im:
                    sheet.paste(im, (i * cw, j * (ch + 4)))
        p = out if k == 0 else out.with_name(f"{out.stem}_{k // a.cols + 1}{out.suffix}")
        sheet.save(p, quality=82)
        written.append(str(p))
    print("\n".join(written))


if __name__ == "__main__":
    main()
