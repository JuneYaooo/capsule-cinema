#!/usr/bin/env python3
"""Run a segmented motion-transfer remake (e.g. Kling motion control) from one JSON spec, then assemble.

Why: one-take reference videos are longer than a motion-transfer call allows (Kling: <=13 s per segment), so the
take is split; a later segment starts from a frame of the previous output so the joint is continuous.
Ad-hoc batch scripts lost hours: a whole batch had to finish before retries / chained segments started.
Here every segment is submitted as soon as its dependency is done, failures retry on their own, and a task id
saved next to each output means a re-run resumes polling instead of paying again.

Spec (JSON):
{
  "tool": "<a video tool from the tool registry that takes first_frame + video_paths (+ dry_run)>",
  "params": {"model": "kling-v2.6-motion-control", "aspect_ratio": "9:16", "duration": 0, "resolution": null,
             "options": {"keep_sound": false, "orientation": "FULL"}, "max_wait": 5400},
  "prompt": "...",                       # shared prompt; a segment may override with "prompt"
  "out_dir": "output/xxx/segments",
  "segments": [
    {"id": "A1", "ref": "clips/a1.mp4", "first_frame": "kf/a1.png"},
    {"id": "A2", "ref": "clips/a2.mp4", "first_frame": {"from": "A1", "at": 12.4}}   # or "at": "last"
  ],
  "videos": [{"name": "A", "parts": ["A1", "A2"], "source": "src/a.mp4", "out": "output/xxx/final/A.mp4"}],
  "concurrency": 4, "retries": 2
}
A part that hands over at a time inside it ("at": t) is trimmed to t seconds when assembling.
Paths are relative to the spec file. Rules that keep motion transfer clean (see the remake capsule recipe):
drive with the REAL footage (a clay/blank-head ref makes the model invent talking mouths and confuses light
garments), keep segments >= ~4 s, and hand over at a frame that shows the full outfit.

Usage: python scripts/motion_segments.py spec.json [--dry-run] [--only A1,A2] [--assemble-only]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *map(str, args)], check=True)


def dur(p) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True, check=True).stdout.strip())


class Runner:
    def __init__(self, spec_path: Path, dry: bool):
        self.base = spec_path.parent
        self.spec = json.loads(spec_path.read_text())
        self.out = self.p(self.spec["out_dir"])
        self.out.mkdir(parents=True, exist_ok=True)
        self.segs = {s["id"]: s for s in self.spec["segments"]}
        self.dry = dry
        self.lock = threading.Lock()

    def p(self, rel) -> Path:
        q = Path(rel)
        return q if q.is_absolute() else (self.base / q).resolve()

    def raw(self, sid) -> Path:
        return self.out / f"{sid}.mp4"

    def dep(self, sid):
        f = self.segs[sid]["first_frame"]
        return f["from"] if isinstance(f, dict) else None

    def first_frame(self, sid) -> Path:
        f = self.segs[sid]["first_frame"]
        if not isinstance(f, dict):
            return self.p(f)
        src, at = self.raw(f["from"]), f.get("at", "last")
        img = self.out / f"{f['from']}_at{at}.png"
        if not self.dry:
            if at == "last":
                ff("-sseof", "-0.1", "-i", src, "-frames:v", 1, img)
            else:
                ff("-ss", at, "-i", src, "-frames:v", 1, img)
        return img

    def run_one(self, sid) -> tuple[str, bool, str]:
        s, raw = self.segs[sid], self.raw(sid)
        if raw.exists():
            return sid, True, "exists"
        params = dict(self.spec.get("params", {}))
        params.update(prompt=s.get("prompt", self.spec.get("prompt", "")), output_path=str(raw),
                      first_frame=str(self.first_frame(sid)), video_paths=[str(self.p(s["ref"]))])
        if self.dry:
            params["dry_run"] = True
            if self.dep(sid):  # chained frame does not exist yet in a dry run; validate with the dependency's input
                params["first_frame"] = str(self.p(self.segs[self.dep(sid)]["first_frame"])) \
                    if not isinstance(self.segs[self.dep(sid)]["first_frame"], dict) else params["first_frame"]
        task = raw.with_suffix(".task.json")
        tries = 1 + int(self.spec.get("retries", 2))
        msg = ""
        for attempt in range(tries):
            if task.exists() and not self.dry:
                params["task_id"] = json.loads(task.read_text())["task_id"]
            r = subprocess.run([str(ROOT / ".venv/bin/python"), "scripts/run_tool.py", "--tool", self.spec["tool"],
                                "--params", json.dumps(params, ensure_ascii=False)], cwd=ROOT, capture_output=True, text=True)
            if self.dry:
                ok = '"dry_run": true' in r.stdout
                return sid, ok, "dry-run ok" if ok else (r.stdout[-300:] + r.stderr[-200:])
            if raw.exists():
                return sid, True, f"ok (try {attempt + 1})"
            msg = (r.stdout[-300:] + r.stderr[-200:]).replace("\n", " ")
            if "task failed" in msg:  # the provider rejected this task: drop the id so the retry submits fresh
                task.unlink(missing_ok=True)
            time.sleep(20 * (attempt + 1))
        return sid, False, msg

    def run(self, only=None):
        todo = [s for s in self.segs if not only or s in only]
        done, failed, running = set(), {}, {}
        n = int(self.spec.get("concurrency", 4))
        with ThreadPoolExecutor(n) as ex:
            while todo or running:
                for sid in list(todo):
                    d = self.dep(sid)
                    if d in failed:
                        failed[sid] = f"blocked by {d}"; todo.remove(sid)
                    elif (d is None or d in done or self.raw(d).exists() or (self.dry and d not in todo + list(running))) \
                            and len(running) < n:
                        running[ex.submit(self.run_one, sid)] = sid; todo.remove(sid)
                if not running:
                    break
                fin, _ = wait(list(running), return_when=FIRST_COMPLETED)
                for fut in fin:
                    sid, ok, msg = fut.result(); running.pop(fut)
                    (done.add(sid) if ok else failed.__setitem__(sid, msg))
                    print(f"[{time.strftime('%H:%M:%S')}] {sid}: {'OK' if ok else 'FAILED'} {msg[:160]}", flush=True)
        return done, failed

    def assemble(self):
        for v in self.spec.get("videos", []):
            parts = v["parts"]
            files = [self.raw(p) for p in parts]
            if not all(f.exists() for f in files):
                print("assemble skipped (missing parts):", v["name"]); continue
            src = self.p(v["source"])
            cut = {}  # a part that hands over at t (not 'last') is used only up to t
            for p in parts:
                f = self.segs[p]["first_frame"]
                if isinstance(f, dict) and f.get("at", "last") != "last":
                    cut[f["from"]] = float(f["at"])
            ins, fc = [], []
            for i, f in enumerate(files):
                ins += ["-i", f]
                trim = ("trim=start_frame=1," if i else "") + (f"trim=duration={cut[parts[i]]}," if parts[i] in cut else "")
                fc.append(f"[{i}:v]{trim}setpts=PTS-STARTPTS,fps=30,scale=1080:1920:force_original_aspect_ratio=decrease,"
                          f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]")
            fc.append("".join(f"[v{i}]" for i in range(len(files))) +
                      f"concat=n={len(files)}:v=1:a=0,tpad=stop_mode=clone:stop_duration=1[v]")
            out = self.p(v["out"]); out.parent.mkdir(parents=True, exist_ok=True)
            ff(*ins, "-i", src, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", f"{len(files)}:a?", "-t", dur(src),
               "-c:v", "libx264", "-crf", 17, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", out)
            print("final:", out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--dry-run", action="store_true", help="validate every request without submitting (no cost)")
    ap.add_argument("--only", help="comma-separated segment ids")
    ap.add_argument("--assemble-only", action="store_true")
    a = ap.parse_args()
    r = Runner(Path(a.spec).resolve(), a.dry_run)
    if not a.assemble_only:
        done, failed = r.run(set(a.only.split(",")) if a.only else None)
        if failed:
            print("FAILED:", json.dumps(failed, ensure_ascii=False, indent=1)); sys.exit(1 if not a.dry_run else 0)
    if not a.dry_run:
        r.assemble()


if __name__ == "__main__":
    main()
