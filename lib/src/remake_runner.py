"""Run the generation jobs of a remake plan (`remake/jobs.json`, written by `rea-video remake-plan`).

Paid: every job calls a video model. `dry_run` lists the jobs and calls nothing. jobs.json may come from someone else,
so it never chooses the code that runs, and its output directories must stay under this repo's output/.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import os
import re
import time
from pathlib import Path
from typing import Any


class JobsError(Exception):
    pass


def video_path(res: Any) -> str | None:
    """The generated file, in the result shapes the video tools return."""
    if isinstance(res, str):
        return res if res.lower().endswith((".mp4", ".mov", ".webm")) and Path(res).is_file() else None
    if not isinstance(res, dict):
        return None
    for key in ("output_path", "video_path", "local_path", "path", "file_path"):
        v = res.get(key)
        if isinstance(v, str) and Path(v).is_file():
            return v
    for key in ("result", "data", "video"):
        v = video_path(res.get(key)) if res.get(key) is not None else None
        if v:
            return v
    return None


def parse_only(text: str) -> tuple[set[int], set[str]]:
    shots: set[int] = set()
    units: set[str] = set()
    for x in (y.strip() for y in str(text or "").split(",")):
        if not x:
            continue
        if re.fullmatch(r"G\d+", x, re.I):
            units.add(x.upper())
            continue
        m = re.fullmatch(r"(?:shot_?)?0*(\d+)", x, re.I)
        if not m:
            raise JobsError(f"--only: cannot read {x!r}; use a shot number (3), a shot id (shot_003) or a unit (G2)")
        shots.add(int(m.group(1)))
    return shots, units


def select_jobs(spec: dict[str, Any], root: Path, only: str = "") -> list[dict[str, Any]]:
    """The generation jobs to run, after checking every one of them writes inside this repo's output/."""
    root = root.resolve()
    planned = Path(str(spec.get("capsule_root") or "")).expanduser().resolve()
    if planned != root:
        raise JobsError(f"jobs.json was planned for {planned}, not this repo ({root}); re-run prepare")
    out_root = root / "output"
    for j in spec["jobs"]:
        od = Path(str((j.get("params") or {}).get("output_dir") or "")).expanduser().resolve()
        if j.get("executor") == "capsule_cinema" and not od.is_relative_to(out_root):
            raise JobsError(f"shot {j.get('shot')}: output_dir is outside {out_root}; refusing to run")
    shots, units = parse_only(only)
    generation = [j for j in spec["jobs"] if j.get("executor") == "capsule_cinema"]
    if not (shots or units):
        return generation
    todo = [j for j in generation if j.get("unit") in units or shots & set(j.get("shots") or [j["shot"]])]
    if not todo:
        raise JobsError(f"--only {only}: nothing to generate there; shots that can be generated: {sorted(j['shot'] for j in generation)}")
    return todo


def engine_routes() -> dict[str, str]:
    """Deployment routes from the environment (`plan-engine=run-engine,...`). Plans and reports keep the planned model;
    jobs.json can never set a route."""
    pairs = (x.split("=", 1) for x in os.getenv("REA_VIDEO_ENGINE_ROUTES", "").split(",") if "=" in x)
    return {a.strip(): b.strip() for a, b in pairs if a.strip() and b.strip()}


def task_fingerprint(engine: str, params: dict[str, Any]) -> str:
    """A saved task is resumed only for the same engine and the same request."""
    data = json.dumps({"engine": engine, **{k: v for k, v in params.items() if k != "output_dir"}}, sort_keys=True, default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _height(resolution: Any) -> int:
    text = str(resolution or "").lower()
    if "2k" in text:
        return 1440
    if "4k" in text:
        return 2160
    m = re.search(r"(\d{3,4})p", text)
    return int(m.group(1)) if m else 0


def channel_notes(todo: list[dict[str, Any]], vgt: Any) -> list[str]:
    """Where the channel that will run a job falls short of the planned model. Advisory, and nothing is sent."""
    from src.video_engines import get_engine_spec

    routes = {vgt.normalize_video_engine(a): vgt.normalize_video_engine(b) for a, b in engine_routes().items()}
    notes = []
    for j in todo:
        if not j.get("unit"):
            continue
        planned = vgt.normalize_video_engine(j["params"]["engine"])
        try:
            tool = vgt._tool_for_engine(routes.get(planned, planned))
            check = getattr(tool, "preflight", None)
            if not check:
                continue
            got = check({k: v for k, v in j["params"].items() if k not in ("engine", "output_dir")})
        except Exception as exc:  # the run would fail the same way: say so before it is paid for
            notes.append(f"{j['id']}: the current channel cannot run this job as planned: {exc}")
            continue
        spec = get_engine_spec(planned)
        best = max((spec.capabilities.get("resolutions") or []) if spec else [], key=_height, default=None)
        if best and _height(got.get("resolution")) and _height(got["resolution"]) < _height(best):
            notes.append(f"{j['id']}: {planned} can reach {best}; the current channel runs it at {got['resolution']}")
    return notes


def run_jobs(jobs_path: str | Path, root: str | Path, *, only: str = "", dry_run: bool = False) -> int:
    """Returns the number of jobs that produced no video. Results are saved after every job."""
    path = Path(jobs_path).expanduser().resolve()
    root = Path(root).resolve()
    spec = json.loads(path.read_text(encoding="utf-8"))
    todo = select_jobs(spec, root, only)
    print(f"{len(todo)} generation job(s); run dir {spec.get('run_dir')}")
    if dry_run:
        for j in todo:
            p = dict(j["params"])
            p["prompt"] = p["prompt"][:120] + ("…" if len(p["prompt"]) > 120 else "")
            print(json.dumps({"job": j.get("id", j["shot"]), "shots": j.get("shots") or [j["shot"]], "label": j.get("label"), **p}, ensure_ascii=False))
            if j.get("warning"):
                print(f"  ! {j['warning']}")

    from env_loader import load_video_agent_env

    load_video_agent_env(root)
    from custom_tools.video_generation import video_generation_tool as vgt

    for note in channel_notes(todo, vgt):
        print(f"  ! {note}", flush=True)
    if dry_run:
        return 0

    results_path = path.with_name("results.json")
    results = json.loads(results_path.read_text(encoding="utf-8")) if results_path.is_file() else {"results": {}}
    tool = vgt.UniversalVideoGenerationTool()
    routes = {vgt.normalize_video_engine(a): vgt.normalize_video_engine(b) for a, b in engine_routes().items()}
    failed = []
    for j in todo:
        Path(j["params"]["output_dir"]).mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        label = j["id"] if j.get("unit") else f"shot {j['shot']}"
        print(f"{label}: {j['params']['generation_type']} via {j['params']['engine']} ...", flush=True)
        if j.get("warning"):
            print(f"  ! {j['warning']}", flush=True)
        key = j["id"] if j.get("unit") else str(j["shot"])  # a unit's clip covers several shots: assembly splits it
        before = results["results"].get(key) or {}
        fingerprint = None

        def keep_task(task_id: str) -> None:  # saved as soon as the task exists, so a crash cannot lose a paid result
            results["results"][key] = {**before, "id": j["id"], "video": None, "task_id": task_id, "task_fingerprint": fingerprint}
            results_path.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

        try:
            if j.get("unit"):  # a unit's references go straight to the engine's own tool
                params = {k: v for k, v in j["params"].items() if k != "engine"}
                engine = vgt.normalize_video_engine(j["params"]["engine"])
                engine = routes.get(engine, engine)
                fingerprint = task_fingerprint(engine, params)
                unit_tool = vgt._tool_for_engine(engine)
                accepts = inspect.signature(unit_tool._run).parameters
                if "on_task_id" in accepts:
                    params["on_task_id"] = keep_task
                    if before.get("task_id") and before.get("task_fingerprint") == fingerprint:
                        params["resume_task_id"] = before["task_id"]
                        print("  resuming the saved task, no new submission", flush=True)
                if "output_path" in accepts:
                    params["output_path"] = str(Path(params["output_dir"]) / f"{j['id']}.mp4")
                res = unit_tool._run(**params)
            else:
                res = tool._run(**j["params"])
        except Exception as exc:  # keep going, record the failure
            res = {"error": str(exc)}
        video = video_path(res)
        resumable = isinstance(res, dict) and res.get("resumable") and res.get("task_id")
        results["results"][key] = {"id": j["id"], "video": video, "raw": res if not video else None,
                                   **({"task_id": res["task_id"], "task_fingerprint": fingerprint} if resumable and not video else {}),
                                   "seconds": round(time.time() - t0, 1), "trim_to": j["trim_to"],
                                   **({k: j[k] for k in ("unit", "part", "parts", "shots")} if j.get("unit") else {})}
        results_path.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"  -> {video or res}", flush=True)
        if not video:
            failed.append(key)
    print(f"results: {results_path}")
    if failed:
        print(f"{len(failed)}/{len(todo)} job(s) produced no video: {', '.join(failed)} (details in results.json)")
    return len(failed)
