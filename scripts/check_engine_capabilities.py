#!/usr/bin/env python3
"""Compare what rea-video's capability map says a model can do with what this repo's engine catalog says. Read-only.

  model_unstated   the catalog has a limit the capability map does not state
  catalog_above    the catalog claims more than the model's stated limit: one of the two is out of date
  catalog_below    the catalog runs less than the model can do: normal for a channel, worth knowing
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from src import video_engines as ve  # noqa: E402
from src.remake_runner import _height  # noqa: E402

REFS = {"image": "max_reference_images", "video": "max_reference_videos", "audio": "max_reference_audios"}


def capability_models(rea_root: str | None) -> dict[str, dict]:
    if rea_root:
        path = Path(rea_root).expanduser() / "rea_video" / "capabilities" / "models" / "video.yaml"
    else:
        import rea_video

        path = Path(rea_video.__file__).parent / "capabilities" / "models" / "video.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(m["id"]).lower(): m for m in data.get("models") or [] if isinstance(m, dict) and m.get("id")}


def compare_engine(key: str, caps: dict, model: dict) -> list[dict]:
    limits = model.get("limits") or {}
    out = []

    def add(kind: str, field: str, catalog, stated) -> None:
        out.append({"engine": key, "model": model["id"], "kind": kind, "field": field, "catalog": catalog, "model_limit": stated})

    def number(field: str, catalog, stated) -> None:
        if catalog is None:
            return
        if stated is None:
            add("model_unstated", field, catalog, None)
        elif catalog != stated:
            add("catalog_above" if catalog > stated else "catalog_below", field, catalog, stated)

    span = caps.get("duration_range") or [None, None]
    number("max_seconds", span[1], (limits.get("duration_s") or {}).get("max"))
    refs = limits.get("refs") or {}
    for kind, name in REFS.items():
        number(f"reference_{kind}s", caps.get(name), refs.get(kind))
    have, stated = [max(map(_height, x), default=0) for x in (caps.get("resolutions") or [], limits.get("resolutions") or [])]
    if have and stated and have != stated:
        add("catalog_above" if have > stated else "catalog_below", "max_resolution", f"{have}p", f"{stated}p")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rea-root", help="rea-video checkout; default: the installed package")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        models = capability_models(args.rea_root)
    except (ImportError, OSError) as exc:
        print(f"rea-video capability map not found: {exc}", file=sys.stderr)
        return 2
    rows, unmatched = [], []
    for key in ve.catalog_engine_keys():
        spec = ve.get_engine_spec(key)
        names = [key, *(spec.aliases if spec else ())]
        model = next((models[n.lower()] for n in names if n.lower() in models), None)
        if model and spec:
            rows += compare_engine(key, spec.capabilities, model)
        else:
            unmatched.append(key)
    if args.json:
        print(json.dumps({"differences": rows, "not_in_map": unmatched}, ensure_ascii=False, indent=1))
        return 0
    for kind in ("catalog_above", "model_unstated", "catalog_below"):
        for r in (x for x in rows if x["kind"] == kind):
            print(f"{kind}: {r['engine']} {r['field']}: catalog {r['catalog']}, capability map {r['model_limit']}")
    if unmatched:
        print("not in the capability map: " + ", ".join(unmatched))
    return 0


if __name__ == "__main__":
    sys.exit(main())
