"""Check generated clips before they are assembled: does the speech match the scripted lines, and a frame sheet to look at.

Scripted lines are the `<d>[Language] words</d>` tags of a job's prompt. Speech recognition comes from rea-video when it
is installed; without it the speech check reports `not_checked` instead of passing.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

MATCH = 0.72  # recognisers swap homophones, so a line counts when most of it is heard
EXTRA_CHARS = 4  # a stray word or two of recogniser noise is not an extra line
LANGS = {"chinese": "zh", "mandarin": "zh", "english": "en", "japanese": "ja", "korean": "ko"}
_LINE = re.compile(r"<d>\s*(?:\[([^\]]*)\])?\s*(.*?)\s*</d>", re.S)


def scripted_lines(prompt: str) -> tuple[list[str], str | None]:
    found = _LINE.findall(prompt or "")
    lang = next((LANGS[x.strip().lower()] for x, _ in found if x.strip().lower() in LANGS), None)
    return [t for _, t in found if norm(t)], lang


def norm(text: str) -> str:
    return re.sub(r"[\W_]+", "", str(text or "")).lower()


def _spans(line: str, heard: str) -> list[tuple[float, int, int]]:
    n = len(line)
    out = []
    for size in {max(1, n - 1), n, n + 1}:
        for i in range(0, max(0, len(heard) - size) + 1):
            r = SequenceMatcher(None, line, heard[i:i + size], autojunk=False).ratio()
            if r >= MATCH:
                out.append((r, i, i + size))
    return out


def compare_speech(lines: list[str], heard: list[str]) -> dict[str, Any]:
    """Which scripted lines were heard, how often, and what was said beyond them."""
    text = "".join(norm(x) for x in heard)
    wanted = [norm(x) for x in lines]
    used = [False] * len(text)
    counts = {w: 0 for w in wanted}
    spans = sorted(((r, s, e, w) for w in set(wanted) for r, s, e in _spans(w, text)), key=lambda x: (-x[0], x[1]))
    for _, s, e, w in spans:
        if not any(used[s:e]):
            used[s:e] = [True] * (e - s)
            counts[w] += 1
    planned = {w: wanted.count(w) for w in wanted}
    missing = [x for x in dict.fromkeys(lines) if counts[norm(x)] < planned[norm(x)]]
    repeated = [x for x in dict.fromkeys(lines) if counts[norm(x)] > planned[norm(x)]]
    extra = "".join(c for c, u in zip(text, used) if not u)
    problems = bool(missing or repeated or len(extra) > EXTRA_CHARS)
    return {"status": "fail" if problems else "pass", "missing": missing, "repeated": repeated,
            "extra": extra if len(extra) > EXTRA_CHARS else "", "heard": heard}


def _heard(video: Path, seconds: float | None, language: str | None) -> list[str] | None:
    try:
        from rea_video import speech
    except ImportError:
        return None
    if not speech.available():
        return None
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "speech.wav"
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(video), *(["-t", str(seconds)] if seconds else []), "-vn", "-ac", "1", "-ar", "16000", str(wav)]
        if subprocess.run(cmd, capture_output=True).returncode or not wav.is_file():
            return []
        result = speech.transcribe(wav, language=language)
    if not result.get("ok"):
        return [] if result.get("reason") == "no audio" else None
    return [str(x.get("text") or "") for x in result.get("lines") or []]


def frame_sheet(video: Path, out: Path, seconds: float | None = None, count: int = 8, width: int = 240) -> Path | None:
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if seconds:
        total = min(total, int(seconds * fps))
    tiles = []
    for i in range(count):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int((i + 0.5) * total / count))
        ok, frame = cap.read()
        if ok:
            tiles.append(cv2.resize(frame, (width, round(frame.shape[0] * width / frame.shape[1])), interpolation=cv2.INTER_AREA))
    cap.release()
    if not tiles:
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), np.hstack(tiles))
    return out


def check_jobs(jobs_path: str | Path, only: set[str] | None = None) -> dict[str, Any]:
    """Check every generated clip of a jobs file; writes clip_check.json and clip_check/<id>.jpg beside it."""
    path = Path(jobs_path).expanduser().resolve()
    spec = json.loads(path.read_text(encoding="utf-8"))
    results_path = path.with_name("results.json")
    results = json.loads(results_path.read_text(encoding="utf-8")).get("results", {}) if results_path.is_file() else {}
    report: dict[str, Any] = {}
    for job in spec.get("jobs") or []:
        key = job["id"] if job.get("unit") else str(job.get("shot"))
        video = (results.get(key) or {}).get("video")
        if job.get("executor") != "capsule_cinema" or not video or not Path(video).is_file() or (only and key not in only):
            continue
        seconds = job.get("trim_to")
        lines, language = scripted_lines((job.get("params") or {}).get("prompt") or "")
        heard = _heard(Path(video), seconds, language) if lines else None
        speech = compare_speech(lines, heard) if lines and heard is not None else {"status": "not_checked" if lines else "no_lines"}
        sheet = frame_sheet(Path(video), path.parent / "clip_check" / f"{key}.jpg", seconds)
        report[key] = {"video": video, "speech": speech, "frames": str(sheet) if sheet else None}
    out = {"clips": report, "status": "fail" if any(x["speech"]["status"] == "fail" for x in report.values()) else "pass"}
    path.with_name("clip_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def summary(report: dict[str, Any]) -> str:
    rows = []
    for key, clip in report["clips"].items():
        s = clip["speech"]
        detail = "; ".join(f"{name}: {' / '.join(s[name]) if isinstance(s[name], list) else s[name]}"
                           for name in ("missing", "repeated", "extra") if s.get(name))
        rows.append(f"{key}: speech {s['status']}" + (f" ({detail})" if detail else "") + (f"; frames {clip['frames']}" if clip.get("frames") else ""))
    return "\n".join(rows)
