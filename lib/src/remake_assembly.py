"""Put a remake together on the reference's timeline, from a rea-video handoff (`remake/handoff.json`).

rea-video measures the reference and writes the plan. This module does the assembling:

- generated or supplied clips are retimed to the reference shot, frame-exact: the clip's moves are warped onto the
  reference's (where they start, peak and stop), within the speed limits
- still shots are rebuilt from one image with the measured zoom and pan, with no model call
- every other shot keeps the reference footage as a stand-in, and the status file says what it still needs
- the measured subtitles and styled text go back on over replaced shots only

Writes remake.mp4 (reference audio), compare.mp4 (side by side), assemble_log.json, status.md and status.json.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any, Iterator

import cv2
import numpy as np

from . import video_package as vp

HANDOFF_SCHEMA = "rea_video.remake_handoff.v1"
MAX_SPEEDUP = 3.0  # a generated clip is retimed to the shot length, up to this much faster
MAX_SLOWDOWN = 1.25  # and up to this much slower; past that the remainder is trimmed or held
WARP_W = 96  # width the motion of a clip is measured at
WARP_STEP_COST = 0.04  # how much a step away from the clip's mean speed costs against matching the motion better


class AssemblyError(Exception):
    pass


def _ff(args: list[str], cwd: Path | None = None) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True, cwd=cwd)


def load_handoff(root: Path) -> dict[str, Any]:
    path = root / "remake" / "handoff.json"
    if not path.is_file():
        raise AssemblyError(f"no remake handoff in {root}: run `scripts/remake_reference.py prepare {root}` first")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != HANDOFF_SCHEMA:
        raise AssemblyError(f"{path}: unknown handoff schema {data.get('schema')!r}; update rea-video and Capsule Cinema")
    return data


def frame_bounds(shots: list[dict], fps: float) -> dict[int, tuple[int, int]]:
    """{shot: (first frame, frame count)} on the reference's frame grid, so lengths never add up to a drift."""
    starts = [int(round(s["start"] * fps)) for s in shots]
    ends = starts[1:] + [int(round(shots[-1]["end"] * fps))] if shots else []
    return {s["index"]: (a, max(1, z - a)) for s, a, z in zip(shots, starts, ends)}


def fit_speed(clip_s: float, duration: float) -> float:
    """Playback speed that fits a clip into a shot. Models have a minimum length, so a 1.2 s shot often comes back as
    4 s of the same action: speed the whole clip up instead of cutting the action off."""
    if clip_s <= 0 or duration <= 0:
        return 1.0
    return max(1 / MAX_SLOWDOWN, min(MAX_SPEEDUP, clip_s / duration))


def _probe(src: Path) -> tuple[int, int, float]:
    """Display width, height and duration."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height:stream_side_data=rotation:format=duration", "-of", "json", str(src)],
                       capture_output=True, text=True, check=True)
    data = json.loads(r.stdout)
    stream = (data.get("streams") or [{}])[0]
    w, h = int(stream.get("width") or 0), int(stream.get("height") or 0)
    rotation = next((abs(int(x["rotation"])) for x in stream.get("side_data_list") or [] if "rotation" in x), 0)
    if rotation in (90, 270):
        w, h = h, w
    return w, h, float((data.get("format") or {}).get("duration") or 0)


def _clip_seconds(src: Path) -> float:
    try:
        return _probe(src)[2]
    except (subprocess.CalledProcessError, ValueError, OSError):
        return 0.0


def _exact(fps: float, frames: int) -> tuple[str, list[str]]:
    """Filter tail and flags for exactly `frames` frames: the last one held when the source runs short."""
    return f"fps={fps},tpad=stop_mode=clone:stop_duration={frames / fps + 1:.3f}", ["-frames:v", str(frames), "-r", f"{fps}"]


def motion_curve(frames) -> np.ndarray:
    """How much the picture moves at each frame, 0-1: the change in the most-changed block of a 12 x 8 grid, held 3
    frames and smoothed. All zero when nothing moves."""
    out, prev = [], None
    for f in frames:
        g = (f if f.ndim == 2 else cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)).astype(np.float32)
        out.append(0.0 if prev is None else float(cv2.resize(np.abs(g - prev), (12, 8), interpolation=cv2.INTER_AREA).max()) / 255.0)
        prev = g
    c = np.array(out)
    if len(c) >= 3:
        c = np.array([c[max(0, i - 2):i + 1].max() for i in range(len(c))])
        c = np.convolve(c, np.ones(3) / 3, mode="same")
    top = float(c.max()) if len(c) else 0.0
    return c / top if top >= 0.03 else np.zeros_like(c)


def warp_map(ref: np.ndarray, gen: np.ndarray) -> list[int] | None:
    """For each reference frame, the clip frame to show: a monotonic path lining the clip's moves up with the
    reference's (dynamic time warping), each step 0-3 clip frames. None when either side has no motion to line up."""
    n, m = len(ref), len(gen)
    if n < 4 or m < 2 or not ref.any() or not gen.any():
        return None
    r = max(1 / MAX_SLOWDOWN, min(MAX_SPEEDUP, m / n))
    end = min(m - 1, int(round((n - 1) * r)))
    steps = (0, 1, 2, 3)
    pen = {k: WARP_STEP_COST * (k - r) ** 2 for k in steps}
    inf = 1e18
    cost = np.full((n, m), inf)
    back = np.zeros((n, m), np.int8)
    cost[0, 0] = abs(ref[0] - gen[0])
    for i in range(1, n):
        best = np.full(m, inf)
        arg = np.zeros(m, np.int8)
        for k in steps:
            prev = np.full(m, inf)
            prev[k:] = cost[i - 1, :m - k] if k else cost[i - 1]
            cand = prev + pen[k]
            better = cand < best
            best[better], arg[better] = cand[better], k
        cost[i] = best + np.abs(ref[i] - gen)
        back[i] = arg
    if cost[n - 1, end] >= inf:
        return None
    path, j = [end], end
    for i in range(n - 1, 0, -1):
        j -= int(back[i, j])
        path.append(j)
    return path[::-1]


def _frames_at(src: Path, fps: float, width: int, start_frame: int = 0, count: int | None = None,
               gray: bool = False) -> Iterator[np.ndarray]:
    """Frames of src resampled to fps, streamed through ffmpeg."""
    sw, sh, _ = _probe(src)
    if not sw or not sh:
        return
    w = width - width % 2
    h = max(2, int(round(w * sh / sw / 2)) * 2)
    channels = 1 if gray else 3
    args = ["ffmpeg", "-v", "error"]
    if start_frame:
        args += ["-ss", f"{max(0.0, (start_frame - 0.5) / fps):.6f}"]
    args += ["-i", str(src), "-an", "-vf", f"setpts=PTS-STARTPTS,fps={fps},scale={w}:{h}"]
    if count is not None:
        args += ["-frames:v", str(count)]
    args += ["-f", "rawvideo", "-pix_fmt", "gray" if gray else "bgr24", "-"]
    proc = subprocess.Popen(args, stdout=subprocess.PIPE)
    assert proc.stdout is not None
    size = w * h * channels
    shape = (h, w) if gray else (h, w, 3)
    try:
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            yield np.frombuffer(buf, np.uint8).reshape(shape)
    finally:
        proc.stdout.close()
        proc.terminate()
        proc.wait()


def _warp_clip(src: Path, out: Path, path: list[int], size: tuple[int, int], fps: float) -> Path:
    """Write the clip's frames in the order `path` gives: exactly len(path) frames, never the whole clip in memory."""
    w, h = size
    need: dict[int, int] = {}
    for j in path:
        need[j] = need.get(j, 0) + 1
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", f"{fps}",
                             "-i", "-", "-frames:v", str(len(path)), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(out)],
                            stdin=subprocess.PIPE)
    assert proc.stdin is not None
    written, last = 0, None
    for j, f in enumerate(_frames_at(src, fps, max(w, int(round(h * 16 / 9))))):
        if j > path[-1]:
            break
        fh, fw = f.shape[:2]
        s = max(w / fw, h / fh)  # cover, then centre crop
        f = cv2.resize(f, (max(w, int(round(fw * s))), max(h, int(round(fh * s)))), interpolation=cv2.INTER_AREA)
        y0, x0 = (f.shape[0] - h) // 2, (f.shape[1] - w) // 2
        last = np.ascontiguousarray(f[y0:y0 + h, x0:x0 + w])
        for _ in range(need.get(j, 0)):
            proc.stdin.write(last.tobytes())
            written += 1
    while last is not None and written < len(path):  # the clip decoded shorter than measured
        proc.stdin.write(last.tobytes())
        written += 1
    proc.stdin.close()
    if proc.wait() != 0 or written == 0:
        raise RuntimeError(f"warp failed for {src}")
    return out


def _fit_clip(src: Path, out: Path, frames: int, size: tuple[int, int], fps: float) -> Path:
    w, h = size
    speed = fit_speed(_clip_seconds(src), frames / fps)
    tail, flags = _exact(fps, frames)
    vf = f"setpts=PTS/{speed:.4f},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},{tail}"
    _ff(["-i", str(src), "-an", "-vf", vf, *flags, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(out)])
    return out


def fit_to_original(src: Path, out: Path, original: Path, first: int, frames: int, size: tuple[int, int], fps: float) -> str:
    """A clip into the reference shot's frames: warped onto its moves, else evenly retimed. Returns which."""
    try:
        ref = motion_curve(_frames_at(original, fps, WARP_W, first, frames, gray=True))
        gen = motion_curve(_frames_at(src, fps, WARP_W, gray=True))
        path = warp_map(ref[:frames], gen) if len(ref) >= frames - 1 else None
        if path:
            _warp_clip(src, out, path + [path[-1]] * (frames - len(path)), size, fps)
            return "warped"
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError):
        pass
    _fit_clip(src, out, frames, size, fps)
    return "even"


def _segment(src: Path, out: Path, first: int, frames: int, size: tuple[int, int], fps: float) -> Path:
    """Frames first .. first + frames - 1 of src, seeking half a frame early so the first one is never skipped."""
    w, h = size
    tail, flags = _exact(fps, frames)
    _ff(["-ss", f"{max(0.0, (first - 0.5) / fps):.6f}", "-i", str(src), "-an",
         "-vf", f"setpts=PTS-STARTPTS,scale={w}:{h},{tail}", *flags, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(out)])
    return out


def render_still_motion(image: Path, out: Path, duration: float, size: tuple[int, int], fps: float,
                        zoom_per_s: float = 0.0, pan_px_per_s: float = 0.0, pan_dir_deg: float = 0.0,
                        analysis_width: int = 480) -> Path:
    """Re-create a zoom and pan on one image with the measured rates."""
    img = cv2.imdecode(np.fromfile(str(image), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(image)
    w, h = size
    img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    n = max(1, int(round(duration * fps)))
    px_scale = w / float(analysis_width)
    vx = math.cos(math.radians(pan_dir_deg)) * pan_px_per_s * px_scale
    vy = math.sin(math.radians(pan_dir_deg)) * pan_px_per_s * px_scale
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", f"{fps}",
                             "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(out)], stdin=subprocess.PIPE)
    assert proc.stdin is not None
    base = 1.0 + max(0.0, -zoom_per_s * duration) + 0.02 + (abs(vx) + abs(vy)) * duration / max(w, h)
    for i in range(n):
        t = i / fps
        s = base * (1.0 + zoom_per_s * t)
        m = cv2.getRotationMatrix2D((w / 2, h / 2), 0, s)
        m[0, 2] += vx * t - vx * duration / 2
        m[1, 2] += vy * t - vy * duration / 2
        proc.stdin.write(cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT).tobytes())
    proc.stdin.close()
    if proc.wait():
        raise RuntimeError(f"still render failed for {image}")
    return out


def unit_shots(shots: list[dict], results: dict, udir: Path, size: tuple[int, int], fps: float,
               bounds: dict[int, tuple[int, int]]) -> dict[str, dict]:
    """Clips of one generation unit (results keyed "G2", or "G4-1", "G4-2") -> one clip per shot, cut at the
    reference's cut points. A unit is used only when every part of it came back."""
    by_unit: dict[str, list[dict]] = {}
    for v in results.values():
        if isinstance(v, dict) and v.get("unit"):
            by_unit.setdefault(str(v["unit"]), []).append(v)
    if not by_unit:
        return {}
    known = {s["index"] for s in shots}
    udir.mkdir(parents=True, exist_ok=True)
    out: dict[str, dict] = {}
    for n, (uid, got) in enumerate(by_unit.items(), 1):
        got.sort(key=lambda v: v.get("part", 1))
        if len(got) < int(got[0].get("parts") or 1) or not all(v.get("video") and Path(v["video"]).is_file() for v in got):
            continue
        fitted = []
        for k, v in enumerate(got, 1):
            f = udir / f"unit{n}_p{k}.mp4"  # never a file name taken from the JSON
            _fit_clip(Path(v["video"]), f, max(1, int(round(float(v["trim_to"]) * fps))), size, fps)
            fitted.append(f)
        whole = fitted[0]
        if len(fitted) > 1:
            lst = udir / f"unit{n}.txt"
            lst.write_text("".join("file '" + str(f.resolve()).replace("'", "'\\''") + "'\n" for f in fitted), encoding="utf-8")
            whole = udir / f"unit{n}.mp4"
            _ff(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(whole)])
        at = 0
        for i in got[0].get("shots") or []:
            if i not in known:
                continue
            clip = udir / f"shot_{int(i):03d}.mp4"
            count = bounds[i][1]
            _segment(whole, clip, at, count, size, fps)
            out[str(i)] = {"video": str(clip), "unit": uid, "fitted": True}
            at += count
    return out


def replaced_spans(shots: list[dict], legend: list[tuple[int, str]]) -> list[tuple[float, float]]:
    """Time spans no longer showing the reference picture, adjacent ones merged."""
    by = {s["index"]: s for s in shots}
    spans: list[list[float]] = []
    for i, how in legend:
        if how in ("original", "code"):  # both already carry their text
            continue
        a, z = by[i]["start"], by[i]["end"]
        if spans and abs(spans[-1][1] - a) < 1e-3:
            spans[-1][1] = z
        else:
            spans.append([a, z])
    return [(a, z) for a, z in spans]


def _ass_time(text: str) -> float:
    h, m, s = text.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _ass_clock(t: float) -> str:
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def clip_ass(text: str, spans: list[tuple[float, float]]) -> tuple[str, int]:
    """Keep the dialogue lines inside `spans`. A line cut by a span edge loses its fade on that side, so it does not
    pop in again mid-line. Returns (text, lines kept)."""
    out, kept = [], 0
    for line in text.splitlines():
        if not line.startswith("Dialogue:"):
            out.append(line)
            continue
        head, rest = line.split(":", 1)
        parts = rest.split(",", 9)
        if len(parts) < 10:
            continue
        t0, t1 = _ass_time(parts[1].strip()), _ass_time(parts[2].strip())
        for a, z in spans:
            lo, hi = max(t0, a), min(t1, z)
            if hi - lo < 0.1:
                continue
            body = parts[9]
            if lo > t0 + 1e-3 or hi < t1 - 1e-3:
                body = re.sub(r"\\fade?\([^)]*\)", "", body)
            out.append(f"{head}:" + ",".join([parts[0], _ass_clock(lo), _ass_clock(hi), *parts[3:9], body]))
            kept += 1
    return "\n".join(out) + "\n", kept


def _compare_video(src: Path, final: Path, out: Path, height: int) -> None:
    ch = 720 if height >= 720 else height - height % 2
    label = ",drawtext=text='{t}':x=10:y=10:fontcolor=white:box=1:boxcolor=black@0.5"
    for with_text in (True, False):  # drawtext needs libfreetype
        la, lb = (label.format(t="original"), label.format(t="remake")) if with_text else ("", "")
        try:
            _ff(["-i", str(src), "-i", str(final), "-filter_complex",
                 f"[0:v]scale=-2:{ch}{la}[a];[1:v]scale=-2:{ch}{lb}[b];[a][b]hstack=inputs=2[v]",
                 "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p", "-shortest", str(out)])
            return
        except subprocess.CalledProcessError:
            if not with_text:
                raise


def _results(path: Path) -> dict:
    return (json.loads(path.read_text(encoding="utf-8")).get("results") or {}) if path.is_file() else {}


HOW = {"zh": {"generated": "生成 / 你的素材", "code": "代码重画", "local_still": "静图按测得的运动重建", "original": "原片占位"},
       "en": {"generated": "generated / your footage", "code": "redrawn in code", "local_still": "still rebuilt with the measured move",
              "original": "original as stand-in"}}


def write_status(out_dir: Path, shots: list[dict], legend: list[tuple[int, str]], final: Path, lang: str) -> dict[str, Any]:
    zh = str(lang or "").lower().startswith("zh")
    how = dict(legend)
    words = HOW["zh" if zh else "en"]
    rows = [{"shot": s["index"], "start": s["start"], "end": s["end"], "label": s.get("label"), "now": how.get(s["index"], "original"),
             "next": s.get("next") or "" if how.get(s["index"], "original") == "original" else ""} for s in shots]
    total = sum(r["end"] - r["start"] for r in rows) or 1.0
    done = sum(r["end"] - r["start"] for r in rows if r["now"] != "original")
    groups: dict[str, list[int]] = {}
    for r in rows:
        if r["next"]:
            groups.setdefault(r["next"], []).append(r["shot"])
    lines = ["# 复刻进度" if zh else "# Remake status", "",
             (f"已经做好 {done / total:.0%} 时长；成片 `{final.name}`，左右对比 `compare.mp4`（没做的镜头先用原片占位）。" if zh else
              f"{done / total:.0%} of the running time is done; video `{final.name}`, side by side `compare.mp4` (shots not done yet show the original)."), ""]
    if groups:
        lines += ["## 还要做" if zh else "## Still to do", ""]
        for k, (what, ids) in enumerate(groups.items(), 1):
            secs = sum(r["end"] - r["start"] for r in rows if r["shot"] in ids)
            lines.append(f"{k}. {what}（镜头 {ids}，共 {secs:.1f}s）" if zh else f"{k}. {what} (shots {ids}, {secs:.1f}s)")
        lines.append("")
    lines += ["拿到新镜头就写进 `remake/mine.json`：`{\"results\": {\"镜头号\": {\"video\": \"绝对路径\"}}}`，再运行一次 assemble。" if zh else
              "When a clip comes in, add it to `remake/mine.json`: `{\"results\": {\"<shot>\": {\"video\": \"<absolute path>\"}}}`, then run assemble again.",
              "", "## 逐镜" if zh else "## Shot by shot", "",
              "| 镜头 | 时间 | 画面类型 | 现在 |" if zh else "| Shot | Time | Picture | Now |", "|---|---|---|---|"]
    lines += [f"| #{r['shot']} | {r['start']:.1f}–{r['end']:.1f}s | {r['label']} | {words[r['now']]} |" for r in rows]
    (out_dir / "status.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    status = {"replaced_share": round(done / total, 3), "shots": rows}
    (out_dir / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return status


def assemble(pkg_path: str | Path, *, results_path: str | Path | None = None, mine_path: str | Path | None = None,
             out_dir: str | Path | None = None, overlays: bool = True) -> dict[str, Any]:
    """Build the remake from the package's handoff, generated results and the user's own clips (which win)."""
    pkg = vp.load(pkg_path, validate=False)
    root = Path(pkg["root"])
    hand = load_handoff(root)
    src = vp.source_video(pkg)
    if src is None:
        raise AssemblyError("the reference video was not found (same sha256): put it next to the package")
    rdir = root / "remake"
    results_file = Path(results_path).expanduser() if results_path else rdir / "results.json"
    mine_file = Path(mine_path).expanduser() if mine_path else rdir / "mine.json"
    out = Path(out_dir).expanduser() if out_dir else rdir
    seg_dir = out / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    shots = hand["shots"]
    size = (int(hand["width"]), int(hand["height"]))
    raw_fps = float(hand.get("fps") or 0)
    fps = raw_fps if 0 < raw_fps <= 60 else 30.0
    bounds = frame_bounds(shots, fps)
    results = {**_results(results_file), **{str(k): v for k, v in _results(mine_file).items()}}
    per_shot = {**unit_shots(shots, results, seg_dir / "units", size, fps, bounds),
                **{k: v for k, v in results.items() if not (isinstance(v, dict) and v.get("unit"))}}
    code_rel = hand.get("code_video")
    code_video = vp.safe_path(root, code_rel) if code_rel else None
    parts, legend, timing = [], [], {}
    for s in shots:
        i = s["index"]
        first, n = bounds[i]
        seg = seg_dir / f"shot_{int(i):03d}.mp4"
        res = per_shot.get(str(i)) or {}
        if res.get("video") and Path(res["video"]).is_file():
            timing[str(i)] = fit_to_original(Path(res["video"]), seg, src, first, n, size, fps)
            legend.append((i, "generated"))
        elif code_video and s.get("label") == "code_render" and code_video.is_file():
            _segment(code_video, seg, first, n, size, fps)
            legend.append((i, "code"))
        elif s.get("label") in ("still_motion", "static_hold") and s.get("first_frame"):
            m = s.get("local") or {}
            render_still_motion(vp.safe_path(root, s["first_frame"]), seg, n / fps, size, fps, m.get("zoom_per_s", 0.0),
                                m.get("pan_px_per_s", 0.0), m.get("pan_dir_deg", 0.0), m.get("analysis_width", 480))
            legend.append((i, "local_still"))
        else:
            _segment(src, seg, first, n, size, fps)
            legend.append((i, "original"))
        parts.append(seg)
    lst = seg_dir / "concat.txt"
    lst.write_text("".join("file '" + str(p.resolve()).replace("'", "'\\''") + "'\n" for p in parts), encoding="utf-8")
    picture = out / "remake_silent.mp4"
    _ff(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(picture)])
    overlay_log: dict[str, Any] = {}
    if overlays:
        spans = replaced_spans(shots, legend)
        info = hand.get("overlays") or {}
        overlay_log["stickers_to_add"] = [st for st in info.get("stickers") or []
                                          if any(min(st["t1"], z) - max(st["t0"], a) >= 0.1 for a, z in spans)]
        if info.get("ass") and spans:
            text, kept = clip_ass(vp.safe_path(root, info["ass"]).read_text(encoding="utf-8"), spans)
            overlay_log["text"] = kept
            if kept:
                (out / "overlays_remake.ass").write_text(text, encoding="utf-8")
                try:  # relative name + cwd: no filter-string escaping of the path
                    _ff(["-i", picture.name, "-vf", "ass=overlays_remake.ass", "-c:v", "libx264", "-crf", "18",
                         "-pix_fmt", "yuv420p", "remake_overlaid.mp4"], cwd=out)
                    picture = out / "remake_overlaid.mp4"
                except subprocess.CalledProcessError as exc:
                    overlay_log["error"] = f"ffmpeg ass filter failed ({exc.returncode}); burn overlays_remake.ass in another editor"
    final = out / "remake.mp4"
    if hand.get("has_audio"):
        _ff(["-i", str(picture), "-i", str(src), "-map", "0:v", "-map", "1:a?", "-c:v", "copy", "-c:a", "aac", "-shortest", str(final)])
    else:
        _ff(["-i", str(picture), "-c", "copy", str(final)])
    compare = out / "compare.mp4"
    _compare_video(src, final, compare, size[1])
    status = write_status(out, shots, legend, final, str(pkg["card"].get("lang") or "zh"))
    log = {"legend": legend, "remake": str(final), "compare": str(compare), "status": str(out / "status.md"),
           "replaced_share": status["replaced_share"], "to_do": [r["shot"] for r in status["shots"] if r["next"]],
           **({"timing": timing} if timing else {}), **({"overlays": overlay_log} if overlays else {})}
    (out / "assemble_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return log
