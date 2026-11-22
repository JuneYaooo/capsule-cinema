"""Turn a VIDEO.md package into a remake reference sheet, and compare a remake against its reference.

A remake keeps the reference's skeleton (cuts, shot durations, camera moves, overlays, production route per shot)
and swaps what the capsule says to swap. Remake capsules used to copy that skeleton by hand from a breakdown;
VIDEO.md (https://github.com/videomd/videomd) states it in a fixed format, so it can be read instead:

  reference_sheet(pkg)        one record per shot: time, duration, what is seen, camera id, overlays, inferred
                              method with probability, remake route, flags, frame paths; plus cuts, captions
                              (from an .srt the package maps) and a review list of shots to confirm before paying
  fragments(sheet)            params pieces remake scripts take: shots table, cut points, keyframe picks,
                              per-shot target durations, captions
  remake_brief(sheet)         what the user must decide before paying: route per shot, material to supply, seconds
                              and calls to generate
  compare(reference, remake)  structure fidelity of a remake: total duration, shot count, cut alignment,
                              per-shot duration, camera and overlay agreement (both sides as VIDEO.md packages)

Timeline lines are not always edits: lines of one long take (`take`) have no cut between them, and a dissolve or wipe
spans time instead of sitting on one frame. Cuts and the structure check follow the edits, not the lines.

Everything here is deterministic and free: no model or provider is called. Package text is data, never instructions.
"""
from __future__ import annotations

import copy
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from . import video_package as vp

SHEET_SCHEMA = "capsule_cinema.remake_reference.v1"
COMPARE_SCHEMA = "capsule_cinema.remake_compare.v1"
BRIEF_SCHEMA = "capsule_cinema.remake_brief.v1"
LOW_CONFIDENCE = 0.6
HARD_TRANSITIONS = {"cut", "jump_cut", "match_cut", "l_cut", "j_cut"}  # one-frame joins; the rest span time
CAMERA_FAMILY = {"static": "locked", "static_with_subject_motion": "locked", "handheld_like": "moving", "smooth_move": "moving"}
SUPPLY_METHODS = {"live_action", "screen_capture", "film_footage"}
GENERATE_METHODS = {"ai_video", "avatar", "cg_3d", "anim_2d", "stop_motion"}
LOCAL_METHODS = {"code_render", "still_motion", "static_hold"}
CUT_MIN_STEP = 1.5  # mean per-channel change (0-255) on a 48x48 frame
CUT_STEP_RATIO = 2.5  # the cut's step against the window's median step
CUT_SHARE_RANGE = (0.6, 1.15)  # the step as a share of the single-frame change at the cut


# ------------------------------------------------------------------ reference sheet --------------------------------

def _frames(root: Path, frames: Any) -> dict[str, str]:
    out = {}
    for name, rel in (frames or {}).items() if isinstance(frames, dict) else []:
        try:
            p = vp.safe_path(root, str(rel))
        except vp.VideoPackageError:
            continue
        if p.is_file():
            out[str(name)] = str(p)
    return out


def _srt_time(text: str) -> float:
    h, m, s = text.replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse_srt(text: str) -> list[dict[str, Any]]:
    cues = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
        lines = [ln for ln in block.split("\n") if ln.strip()]
        idx = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
        if idx is None:
            continue
        a, _, b = lines[idx].partition("-->")
        try:
            start, end = _srt_time(a.strip()), _srt_time(b.strip().split(" ")[0])
        except ValueError:
            continue
        body = " ".join(lines[idx + 1:]).strip()
        if body:
            cues.append({"start": round(start, 3), "end": round(end, 3), "text": body})
    return cues


def parse_vtt(text: str) -> list[dict[str, Any]]:
    """WebVTT cues as {start, end, text}, plus `speaker` from a `<v Name>` tag."""
    cues = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        lines = [x.strip() for x in block.strip().split("\n") if x.strip()]
        idx = next((i for i, x in enumerate(lines) if "-->" in x), None)
        if idx is None:
            continue
        a, _, b = lines[idx].partition("-->")
        try:
            start, end = _vtt_time(a.strip()), _vtt_time(b.strip().split()[0])
        except (ValueError, IndexError):
            continue
        raw = " ".join(lines[idx + 1:])
        voice = re.search(r"<v(?:\.[^ >]*)?\s+([^>]+)>", raw)
        body = re.sub(r"<[^>]+>", "", raw).strip()
        if body:
            cue = {"start": round(start, 3), "end": round(end, 3), "text": body}
            if voice:
                cue["speaker"] = voice.group(1).strip()
            cues.append(cue)
    return cues


def _vtt_time(text: str) -> float:
    parts = [float(x) for x in text.split(":")]
    if len(parts) not in (2, 3):
        raise ValueError(text)
    return sum(v * 60 ** i for i, v in enumerate(reversed(parts)))


def _transcript(pkg: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    rel = ((pkg.get("card") or {}).get("tracks") or {}).get("transcript")
    if not rel:
        return [], None
    try:
        p = vp.safe_path(Path(pkg["root"]), str(rel))
        return parse_vtt(p.read_text(encoding="utf-8", errors="replace")), str(rel)
    except (vp.VideoPackageError, OSError):
        return [], None


def camera_id(camera: Any) -> str:
    """One comparable id for a shot's camera: the id itself, or an object's first move, else its rig."""
    if isinstance(camera, dict):
        moves = [m for m in camera.get("moves") or [] if isinstance(m, dict)]
        return str((moves[0].get("type") if moves else None) or camera.get("rig") or "unknown")
    return str(camera or "unknown")


def _captions(pkg: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    """Subtitles from the first .srt the package's map points to (a file, or inside a mapped directory), else the
    card's transcript track."""
    root = Path(pkg["root"])
    for entry in pkg.get("map", []):
        rel = entry.get("path", "")
        if any(ch in rel for ch in "*?["):
            continue
        try:
            p = vp.safe_path(root, rel.rstrip("/"))
        except vp.VideoPackageError:
            continue
        cands = [p] if p.is_file() and p.suffix.lower() == ".srt" else sorted(p.glob("*.srt")) if p.is_dir() else []
        for c in cands:
            cues = parse_srt(c.read_text(encoding="utf-8", errors="replace"))
            if cues:
                return cues, str(c.relative_to(root))
    return _transcript(pkg)


def reference_sheet(pkg: dict[str, Any]) -> dict[str, Any]:
    root = Path(pkg["root"])
    card = pkg["card"]
    shots = []
    for line in pkg.get("timeline", []):
        n = line["shot"]
        fm = pkg.get("shots", {}).get(n) or {}
        t = fm.get("time") or [line["start"], line["end"]]
        start, end = float(t[0]), float(t[1])
        inf = fm.get("inferred") or {}
        flags = list(fm.get("flags") or [])
        if line.get("flag") and not flags:
            flags.append("x-timeline_flag")
        layers = [x for x in fm.get("layers") or [] if isinstance(x, dict)]
        shots.append({
            "shot": n,
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(end - start, 3),
            "story": line.get("story", ""),
            "seen": line.get("seen", ""),
            "act": line.get("act", ""),
            "camera": camera_id(fm.get("camera")),
            "camera_detail": fm.get("camera") if isinstance(fm.get("camera"), dict) else None,
            "camera_text": line.get("camera", ""),
            "scene": fm.get("scene"),
            "take": fm.get("take"),
            "beats": fm.get("beats") or [],
            "layers": layers,
            "transition_in": fm.get("transition_in"),
            "transition_text": line.get("transition", ""),
            "speed": fm.get("speed"),
            "lens": fm.get("lens") or [],
            "overlays": list(fm.get("overlays") or []),
            "made": inf.get("made"),
            "p": inf.get("p"),
            "alternatives": inf.get("alternatives") or {},
            "decided_by": inf.get("decided_by"),
            "real_material": inf.get("real_material") or any(x.get("real_material") for x in layers) or None,
            "made_text": line.get("made~", ""),
            "material_text": line.get("material~", ""),
            "remake_route": line.get("remake", ""),
            "flags": flags,
            "flag_text": line.get("flag", ""),
            "frames": _frames(root, fm.get("frames")),
        })
    review = []
    for s in shots:
        reasons = []
        if s["flags"]:
            reasons.append("flags: " + ", ".join(s["flags"]))
        if isinstance(s["p"], (int, float)) and s["p"] < LOW_CONFIDENCE and s["decided_by"] != "human":
            reasons.append(f"method {s['made']} at p={s['p']:.2f}")
        if s["real_material"]:
            reasons.append("needs real material (filmed / screen / product footage)")
        if reasons:
            review.append({"shot": s["shot"], "reasons": reasons, "frames": s["frames"].get("sheet") or s["frames"].get("first")})
    review_note = None
    if shots and len(review) == len(shots) and all(s["decided_by"] in (None, "tools") for s in shots):
        review_note = ("Every shot is flagged and no image reader or person judged any of them: the breakdown ran on "
                       "pixel statistics alone. Review it by eye first (rea-video review / apply-review), then rebuild "
                       "this sheet.")
    captions, captions_src = _captions(pkg)
    transcript, transcript_src = _transcript(pkg)
    src = card.get("source") or {}
    source_file = vp.source_video(pkg)
    return {
        "schema_version": SHEET_SCHEMA,
        "package": vp.reference(pkg),
        "source_video": str(source_file) if source_file else None,
        "duration": src.get("duration") or (shots[-1]["end"] if shots else 0),
        "size": src.get("size"),
        "fps": src.get("fps"),
        "aspect": src.get("aspect"),
        "made_mix": card.get("made_mix") or {},
        "confidence": card.get("confidence"),
        "open_questions": card.get("open_questions", 0),
        "shots": shots,
        "scenes": pkg.get("scenes") or [],
        "cuts": [s["start"] for s in _edit_shots(shots)[1:]],
        "captions": captions,
        "captions_source": captions_src,
        "transcript": transcript,
        "transcript_source": transcript_src,
        "review": review,
        "review_note": review_note,
        "notice": vp.DATA_NOTICE,
    }


# ------------------------------------------------------------------ params fragments -------------------------------

def _keyframe_time(s: dict[str, Any]) -> float:
    return round(s["start"] + min(0.5, s["duration"] / 2), 3)


def fragments(sheet: dict[str, Any], *, shots: list[int] | None = None) -> dict[str, Any]:
    """Params pieces in the shapes remake scripts take. `shots` limits keyframes to those shot numbers.

    The shots table's `text` is the reference's `seen` line as a seed: rewrite it for the new subject (and in the
    language the video model wants) before generating; it describes the reference, not the remake."""
    pick = set(shots or [])
    return {
        "shots": [
            {"start": s["start"], "end": s["end"], "text": s["seen"]} if s["seen"] else
            {"start": s["start"], "end": s["end"], "text": "", "write_from": s["frames"].get("sheet") or s["frames"].get("first")}
            for s in sheet["shots"]
        ],
        "cuts": sheet["cuts"],
        "keyframes": [
            {"id": f"s{s['shot']}", "shot": s["shot"], "t": _keyframe_time(s), "frame": s["frames"].get("first")}
            for s in sheet["shots"] if not pick or s["shot"] in pick
        ],
        "targets": [{"shot": s["shot"], "start": s["start"], "end": s["end"], "target": s["duration"]} for s in sheet["shots"]],
        "transitions": [{"shot": s["shot"], **s["transition_in"]} for s in sheet["shots"] if s.get("transition_in")],
        "captions": sheet["captions"],
    }


# ------------------------------------------------------------------ pre-production brief ----------------------------

def shot_route(s: dict[str, Any]) -> str:
    """`supply` needs real material, `generate` calls a paid model, `local` renders here, `decide` has no known method."""
    if s.get("real_material") or s.get("made") in SUPPLY_METHODS:
        return "supply"
    if s.get("made") in GENERATE_METHODS:
        return "generate"
    if s.get("made") in LOCAL_METHODS:
        return "local"
    return "decide"


def _calls(seconds: float, max_seconds: int | None) -> int:
    return max(1, math.ceil(seconds / max_seconds)) if max_seconds else 1


def remake_brief(sheet: dict[str, Any], *, engine: dict[str, Any] | None = None) -> dict[str, Any]:
    """Everything to confirm before paid generation. Calls nothing. Reports seconds and calls, never a price: the
    catalog has no unit prices, and a made-up figure is worse than none. `engine` is {"key", "max_seconds", "cost_tier"}."""
    max_seconds = (engine or {}).get("max_seconds")
    review = {r["shot"]: r["reasons"] for r in sheet["review"]}
    rows = []
    for s in sheet["shots"]:
        route = shot_route(s)
        rows.append({
            "shot": s["shot"], "start": s["start"], "end": s["end"], "duration": s["duration"], "route": route,
            "made": s.get("made"), "p": s.get("p"), "seen": s.get("seen", ""), "remake_route": s.get("remake_route", ""),
            "calls": _calls(s["duration"], max_seconds) if route == "generate" else 0,
            "calls_if_regenerated": _calls(s["duration"], max_seconds) if route in ("generate", "supply", "decide") else 0,
            "confirm": review.get(s["shot"], []),
        })

    def seconds(*routes: str) -> float:
        return round(sum(r["duration"] for r in rows if r["route"] in routes), 3)

    return {
        "schema_version": BRIEF_SCHEMA,
        "package": sheet["package"],
        "source_video": sheet.get("source_video"),
        "duration": sheet["duration"],
        "aspect": sheet.get("aspect"),
        "shots": len(rows),
        "edits": len(sheet["cuts"]) + 1 if rows else 0,
        "scenes": len(sheet.get("scenes") or []),
        "made_mix": sheet.get("made_mix") or {},
        "confidence": sheet.get("confidence"),
        "open_questions": sheet.get("open_questions", 0),
        "review_note": sheet.get("review_note"),
        "engine": engine,
        "seconds": {"supply": seconds("supply"), "generate": seconds("generate"), "local": seconds("local"),
                    "decide": seconds("decide")},
        "generation": {
            "as_planned": {"seconds": seconds("generate"), "calls": sum(r["calls"] for r in rows)},
            "if_filmed_shots_are_regenerated": {"seconds": seconds("generate", "supply", "decide"),
                                                "calls": sum(r["calls_if_regenerated"] for r in rows)},
        },
        "confirm_shots": [r["shot"] for r in rows if r["confirm"]],
        "rows": rows,
        "notice": sheet.get("notice"),
    }


def brief_markdown(brief: dict[str, Any]) -> str:
    zh = str(brief["package"].get("lang") or "").lower().startswith("zh")
    names = {"supply": "要你提供", "generate": "AI 生成", "local": "本地渲染", "decide": "待定"} if zh else \
        {"supply": "you supply", "generate": "AI generate", "local": "local render", "decide": "to decide"}
    sec, gen = brief["seconds"], brief["generation"]
    planned, regen = gen["as_planned"], gen["if_filmed_shots_are_regenerated"]
    engine = brief.get("engine") or {}
    engine_text = f"{engine.get('key')}（单次最长 {engine.get('max_seconds')} 秒，成本档 {engine.get('cost_tier') or '未标注'}）" if zh and engine else \
        f"{engine.get('key')} (up to {engine.get('max_seconds')}s per call, cost tier {engine.get('cost_tier') or 'not listed'})" if engine else ("未指定" if zh else "not chosen")
    if zh:
        lines = ["# 复刻简报（尚未调用任何付费模型）", "",
                 f"- 参考：{brief['duration']} 秒，{brief['shots']} 镜，{brief['edits']} 个剪辑段" + (f"，{brief['scenes']} 场" if brief["scenes"] else ""),
                 f"- 路线：{names['supply']} {sec['supply']} 秒 · {names['generate']} {sec['generate']} 秒 · {names['local']} {sec['local']} 秒 · {names['decide']} {sec['decide']} 秒",
                 f"- 视频模型：{engine_text}",
                 f"- 按当前路线生成：{planned['seconds']} 秒，约 {planned['calls']} 次调用",
                 f"- 如果实拍镜头也全部改用 AI 重做：{regen['seconds']} 秒，约 {regen['calls']} 次调用",
                 "- 费用：目录里没有单价，这里只给秒数和调用次数，请按所选渠道的价格换算",
                 f"- 开工前要确认的镜头：{brief['confirm_shots'] or '无'}"]
        head = "| 镜 | 时间 | 路线 | 判断 | 画面 | 要确认 |"
    else:
        lines = ["# Remake brief (no paid model has been called)", "",
                 f"- Reference: {brief['duration']}s, {brief['shots']} shots, {brief['edits']} edits" + (f", {brief['scenes']} scenes" if brief["scenes"] else ""),
                 f"- Routes: {names['supply']} {sec['supply']}s · {names['generate']} {sec['generate']}s · {names['local']} {sec['local']}s · {names['decide']} {sec['decide']}s",
                 f"- Video model: {engine_text}",
                 f"- Generation as planned: {planned['seconds']}s, about {planned['calls']} calls",
                 f"- If filmed shots are regenerated with AI too: {regen['seconds']}s, about {regen['calls']} calls",
                 "- Cost: the catalog has no unit prices, so this lists seconds and calls; apply your provider's price",
                 f"- Shots to confirm first: {brief['confirm_shots'] or 'none'}"]
        head = "| shot | time | route | method | seen | confirm |"
    if brief.get("review_note"):
        lines += ["", f"> {brief['review_note']}"]
    lines += ["", head, "|---|---|---|---|---|---|"]
    for r in brief["rows"]:
        made = f"{r['made']} {r['p']:.0%}" if isinstance(r.get("p"), (int, float)) else str(r.get("made") or "-")
        seen = str(r["seen"]).replace("|", "/").replace("\n", " ")[:48]
        confirm = "; ".join(r["confirm"]).replace("|", "/")
        lines.append(f"| {r['shot']} | {r['start']:.1f}-{r['end']:.1f} | {names[r['route']]} | {made} | {seen} | {confirm} |")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ remake vs reference -----------------------------

def _overlap(a: dict[str, Any], b: dict[str, Any]) -> float:
    return max(0.0, min(a["end"], b["end"]) - max(a["start"], b["start"]))


def _edit_shots(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Timeline lines joined into what the editor cut: consecutive lines of one `take` are one shot."""
    out: list[dict[str, Any]] = []
    for s in shots:
        take = s.get("take")
        if out and take is not None and out[-1].get("take") == take:
            last = out[-1]
            last["end"] = s["end"]
            last["duration"] = round(last["end"] - last["start"], 3)
            last["overlays"] = sorted({*last.get("overlays", []), *s.get("overlays", [])})
        else:
            out.append(dict(s))
    return out


def _same_camera(a: str, b: str) -> bool:
    """A locked camera stays locked whether or not the subject moves, and the handheld / smooth line is a threshold on
    measured jitter that re-encoding can cross, so each pair counts as one kind of camera."""
    return "unknown" in (a, b) or CAMERA_FAMILY.get(a, a) == CAMERA_FAMILY.get(b, b)


def _is_soft(s: dict[str, Any]) -> bool:
    t = s.get("transition_in")
    return isinstance(t, dict) and t.get("type") not in HARD_TRANSITIONS


def _cut_window(s: dict[str, Any], tolerance: float) -> tuple[float, float]:
    """Where the join into shot `s` may be detected: around its start, or across a transition's measured span."""
    low, high = s["start"], s["start"]
    t = s.get("transition_in")
    if _is_soft(s) and isinstance(t.get("time"), (list, tuple)) and len(t["time"]) == 2:
        low, high = min(low, float(t["time"][0])), max(high, float(t["time"][1]))
    return low - tolerance, high + tolerance


def missed_cuts(reference: dict[str, Any], remake: dict[str, Any], *, tolerance: float = 0.2) -> dict[str, list[float]]:
    """Reference joins with no remake cut near them. `hard` ones can be checked in the pixels, `soft` ones need eyes."""
    rem_cuts = [s["start"] for s in _edit_shots(remake["shots"])[1:]]
    out: dict[str, list[float]] = {"hard": [], "soft": []}
    for s in _edit_shots(reference["shots"])[1:]:
        low, high = _cut_window(s, tolerance)
        if not any(low <= r <= high for r in rem_cuts):
            out["soft" if _is_soft(s) else "hard"].append(s["start"])
    return out


def _frame_diff(a: bytes, b: bytes) -> float:
    return sum(abs(x - y) for x, y in zip(a, b)) / max(1, len(a))


def _mean_frame(frames: list[bytes]) -> bytes:
    return bytes(sum(values) // len(frames) for values in zip(*frames))


def find_cut_in_frames(frames: list[bytes], start: float, fps: float, target: float, tolerance: float) -> float | None:
    """The hard cut near `target`, or None.

    Compares the 3 frames before each position with the 3 after, which averages out grain so low-contrast cuts show.
    A cut stands well above the window's usual step and happens in one frame: motion builds up over several frames
    (step larger than the single-frame change) and a flash is gone again (step smaller than it)."""
    if len(frames) < 12:
        return None
    steps = {i: _frame_diff(_mean_frame(frames[i - 2:i + 1]), _mean_frame(frames[i + 1:i + 4]))
             for i in range(2, len(frames) - 3)}
    near = [i for i in steps if abs(start + (i + 1) / fps - target) <= tolerance]
    if not near:
        return None
    p = max(near, key=steps.get)
    rest = sorted(v for i, v in steps.items() if abs(i - p) > 3)
    if not rest or steps[p] < max(CUT_MIN_STEP, CUT_STEP_RATIO * rest[len(rest) // 2]):
        return None
    single = _frame_diff(frames[p], frames[p + 1])
    if not single or not CUT_SHARE_RANGE[0] <= steps[p] / single <= CUT_SHARE_RANGE[1]:
        return None
    return round(start + (p + 1) / fps, 3)


def probe_cuts(video: str | Path, times: list[float], *, tolerance: float = 0.2) -> list[float]:
    """Check the video's pixels at `times` for hard cuts a shot detector missed. Returns the cuts it confirms."""
    exe = shutil.which("ffmpeg")
    if not exe:
        return []
    w, h, fps = 48, 48, 30
    size = w * h * 3
    found = []
    for t in times:
        start = max(0.0, t - tolerance - 0.4)
        length = 2 * (tolerance + 0.4)
        r = subprocess.run([exe, "-v", "error", "-ss", f"{start:.3f}", "-i", str(video), "-t", f"{length:.3f}", "-an",
                            "-vf", f"fps={fps},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           capture_output=True)
        if r.returncode:
            continue
        frames = [r.stdout[i:i + size] for i in range(0, len(r.stdout) - size + 1, size)]
        cut = find_cut_in_frames(frames, start, fps, t, tolerance)
        if cut is not None:
            found.append(cut)
    return found


def with_probed_cuts(sheet: dict[str, Any], cuts: list[float]) -> dict[str, Any]:
    """A copy of `sheet` with the shots split at pixel-confirmed `cuts`."""
    out = copy.deepcopy(sheet)
    shots = out["shots"]
    applied = []
    for cut in sorted(cuts):
        i = next((i for i, s in enumerate(shots) if s["start"] < cut < s["end"]), None)
        if i is None:
            continue
        first, second = shots[i], copy.deepcopy(shots[i])
        first["take"] = second["take"] = None  # the pixels show a cut, so this is no longer one take
        first["end"] = second["start"] = cut
        first["duration"] = round(cut - first["start"], 3)
        second["duration"] = round(second["end"] - cut, 3)
        shots.insert(i + 1, second)
        applied.append(cut)
    for n, s in enumerate(shots, 1):
        s["shot"] = n
    out["cuts"] = [s["start"] for s in shots[1:]]
    out["probed_cuts"] = applied
    return out


def compare(reference: dict[str, Any], remake: dict[str, Any], *, cut_tolerance: float = 0.2,
            duration_tolerance: float = 0.25) -> dict[str, Any]:
    """Structure fidelity of `remake` against `reference`, both reference sheets.

    Shot detection differs a little run to run, so cuts match within `cut_tolerance` seconds and each reference shot
    is paired with the remake shot it overlaps most. `duration_tolerance` is the allowed relative error per shot.
    Cuts the detector missed but the pixels confirm arrive through `with_probed_cuts`."""
    ref, rem = _edit_shots(reference["shots"]), _edit_shots(remake["shots"])
    probed = remake.get("probed_cuts") or []
    total_ref, total_rem = float(reference["duration"] or 0), float(remake["duration"] or 0)
    checks: list[dict[str, Any]] = []

    def add(cid: str, ok: bool, detail: str, severity: str = "warning") -> None:
        checks.append({"id": cid, "pass": bool(ok), "severity": severity, "detail": detail})

    dur_err = abs(total_rem - total_ref) / total_ref if total_ref else 0.0
    add("total_duration", dur_err <= 0.05, f"reference {total_ref:.2f}s, remake {total_rem:.2f}s ({dur_err:.0%} off)", "blocker")
    count_note = f" ({len(rem) - len(probed)} detected + {len(probed)} confirmed in pixels at {probed})" if probed else ""
    add("shot_count", abs(len(rem) - len(ref)) <= len(ref) // 10,
        f"reference {len(ref)} shots, remake {len(rem)}{count_note}")

    rem_cuts = [s["start"] for s in rem[1:]]
    windows = [(s["start"], *_cut_window(s, cut_tolerance), _is_soft(s)) for s in ref[1:]]
    matched = [w[0] for w in windows if any(w[1] <= r <= w[2] for r in rem_cuts)]
    extra = [r for r in rem_cuts if not any(w[1] <= r <= w[2] for w in windows)]
    missing = [w[0] for w in windows if w[0] not in matched]
    soft_missing = [w[0] for w in windows if w[3] and w[0] not in matched]
    cut_ratio = len(matched) / len(windows) if windows else 1.0
    soft_note = f"; transitions to check by eye {soft_missing[:8]}" if soft_missing else ""
    add("cut_alignment", cut_ratio >= 0.8 and len(extra) <= len(windows) // 10,
        f"{len(matched)}/{len(windows)} reference cuts within ±{cut_tolerance}s; missing {missing[:8]}; extra {extra[:8]}{soft_note}")

    pairs = []
    for s in ref:
        best = max(rem, key=lambda r: _overlap(s, r), default=None)
        if best is None or _overlap(s, best) <= 0:
            pairs.append({"shot": s["shot"], "remake_shot": None})
            continue
        rel = abs(best["duration"] - s["duration"]) / s["duration"] if s["duration"] else 0.0
        pairs.append({
            "shot": s["shot"], "remake_shot": best["shot"],
            "duration": [s["duration"], best["duration"]], "duration_ok": rel <= duration_tolerance,
            "camera": [s["camera"], best["camera"]], "camera_ok": _same_camera(s["camera"], best["camera"]),
            "overlays": [s["overlays"], best["overlays"]], "overlays_ok": bool(s["overlays"]) == bool(best["overlays"]),
        })
    paired = [p for p in pairs if p["remake_shot"] is not None]

    def ratio(key: str) -> float:
        return sum(p[key] for p in paired) / len(paired) if paired else 0.0

    bad_dur = [p["shot"] for p in paired if not p["duration_ok"]]
    add("shot_durations", ratio("duration_ok") >= 0.8, f"{ratio('duration_ok'):.0%} of shots within ±{duration_tolerance:.0%}; off: {bad_dur[:12]}")
    bad_cam = [p["shot"] for p in paired if not p["camera_ok"]]
    add("camera_moves", ratio("camera_ok") >= 0.7, f"{ratio('camera_ok'):.0%} of shots keep the camera move; differ: {bad_cam[:12]}")
    bad_ov = [p["shot"] for p in paired if not p["overlays_ok"]]
    add("overlays", ratio("overlays_ok") >= 0.8, f"{ratio('overlays_ok'):.0%} of shots match overlay presence; differ: {bad_ov[:12]}")

    score = round(sum(c["pass"] for c in checks) / len(checks), 3)
    blocked = any(not c["pass"] and c["severity"] == "blocker" for c in checks)
    return {
        "schema_version": COMPARE_SCHEMA,
        "reference": reference["package"],
        "remake": remake["package"],
        "status": "blocked" if blocked else ("pass" if all(c["pass"] for c in checks) else "review_required"),
        "score": score,
        "checks_passed": sum(c["pass"] for c in checks),
        "checks_total": len(checks),
        "probed_cuts": probed,
        "unverified_transitions": soft_missing,
        "checks": checks,
        "pairs": pairs,
        "note": "Structure only: cuts, timing, camera, overlays. It does not judge identity, hands, props or look; "
                "check those frame by frame against the reference.",
    }


def compare_markdown(result: dict[str, Any]) -> str:
    lines = [f"# Remake vs reference: {result['status']} ({result['checks_passed']}/{result['checks_total']} checks passed)", "",
             f"- reference: `{result['reference']['root']}`", f"- remake: `{result['remake']['root']}`", "",
             "| check | result | detail |", "|---|---|---|"]
    for c in result["checks"]:
        lines.append(f"| {c['id']} | {'pass' if c['pass'] else ('BLOCKER' if c['severity'] == 'blocker' else 'review')} | {c['detail']} |")
    lines += ["", result["note"]]
    return "\n".join(lines) + "\n"
