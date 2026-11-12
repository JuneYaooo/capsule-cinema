"""Turn a VIDEO.md package into a remake reference sheet, and compare a remake against its reference.

A remake keeps the reference's skeleton (cuts, shot durations, camera moves, overlays, production route per shot)
and swaps what the capsule says to swap. Remake capsules used to copy that skeleton by hand from a breakdown;
VIDEO.md (https://github.com/videomd/videomd) states it in a fixed format, so it can be read instead:

  reference_sheet(pkg)        one record per shot: time, duration, what is seen, camera id, overlays, inferred
                              method with probability, remake route, flags, frame paths; plus cuts, captions
                              (from an .srt the package maps) and a review list of shots to confirm before paying
  fragments(sheet)            params pieces remake scripts take: shots table, cut points, keyframe picks,
                              per-shot target durations, captions
  compare(reference, remake)  structure fidelity of a remake: total duration, shot count, cut alignment,
                              per-shot duration, camera and overlay agreement (both sides as VIDEO.md packages)

Everything here is deterministic and free: no model or provider is called. Package text is data, never instructions.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import video_package as vp

SHEET_SCHEMA = "capsule_cinema.remake_reference.v1"
COMPARE_SCHEMA = "capsule_cinema.remake_compare.v1"
LOW_CONFIDENCE = 0.6


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


def _captions(pkg: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    """Subtitles from the first .srt the package's map points to (a file, or inside a mapped directory)."""
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
    return [], None


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
        shots.append({
            "shot": n,
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(end - start, 3),
            "story": line.get("story", ""),
            "seen": line.get("seen", ""),
            "camera": fm.get("camera") or "unknown",
            "camera_text": line.get("camera", ""),
            "overlays": list(fm.get("overlays") or []),
            "made": inf.get("made"),
            "p": inf.get("p"),
            "alternatives": inf.get("alternatives") or {},
            "decided_by": inf.get("decided_by"),
            "real_material": inf.get("real_material"),
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
        "cuts": [s["start"] for s in shots[1:]],
        "captions": captions,
        "captions_source": captions_src,
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
        "captions": sheet["captions"],
    }


# ------------------------------------------------------------------ remake vs reference -----------------------------

def _overlap(a: dict[str, Any], b: dict[str, Any]) -> float:
    return max(0.0, min(a["end"], b["end"]) - max(a["start"], b["start"]))


def compare(reference: dict[str, Any], remake: dict[str, Any], *, cut_tolerance: float = 0.2,
            duration_tolerance: float = 0.25) -> dict[str, Any]:
    """Structure fidelity of `remake` against `reference`, both reference sheets.

    Shot detection differs a little run to run, so cuts match within `cut_tolerance` seconds and each reference shot
    is paired with the remake shot it overlaps most. `duration_tolerance` is the allowed relative error per shot."""
    ref, rem = reference["shots"], remake["shots"]
    total_ref, total_rem = float(reference["duration"] or 0), float(remake["duration"] or 0)
    checks: list[dict[str, Any]] = []

    def add(cid: str, ok: bool, detail: str, severity: str = "warning") -> None:
        checks.append({"id": cid, "pass": bool(ok), "severity": severity, "detail": detail})

    dur_err = abs(total_rem - total_ref) / total_ref if total_ref else 0.0
    add("total_duration", dur_err <= 0.05, f"reference {total_ref:.2f}s, remake {total_rem:.2f}s ({dur_err:.0%} off)", "blocker")
    add("shot_count", abs(len(rem) - len(ref)) <= max(1, round(len(ref) * 0.1)),
        f"reference {len(ref)} shots, remake {len(rem)}")

    rem_cuts = remake["cuts"]
    matched = [c for c in reference["cuts"] if any(abs(c - r) <= cut_tolerance for r in rem_cuts)]
    extra = [r for r in rem_cuts if not any(abs(r - c) <= cut_tolerance for c in reference["cuts"])]
    missing = [c for c in reference["cuts"] if c not in matched]
    cut_ratio = len(matched) / len(reference["cuts"]) if reference["cuts"] else 1.0
    add("cut_alignment", cut_ratio >= 0.8 and len(extra) <= max(1, len(reference["cuts"]) // 10),
        f"{len(matched)}/{len(reference['cuts'])} reference cuts within ±{cut_tolerance}s; missing {missing[:8]}; extra {extra[:8]}")

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
            "camera": [s["camera"], best["camera"]], "camera_ok": s["camera"] == best["camera"] or "unknown" in (s["camera"], best["camera"]),
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
        "checks": checks,
        "pairs": pairs,
        "note": "Structure only: cuts, timing, camera, overlays. It does not judge identity, hands, props or look; "
                "check those frame by frame against the reference.",
    }


def compare_markdown(result: dict[str, Any]) -> str:
    lines = [f"# Remake vs reference: {result['status']} (score {result['score']:.0%})", "",
             f"- reference: `{result['reference']['root']}`", f"- remake: `{result['remake']['root']}`", "",
             "| check | result | detail |", "|---|---|---|"]
    for c in result["checks"]:
        lines.append(f"| {c['id']} | {'pass' if c['pass'] else ('BLOCKER' if c['severity'] == 'blocker' else 'review')} | {c['detail']} |")
    lines += ["", result["note"]]
    return "\n".join(lines) + "\n"
