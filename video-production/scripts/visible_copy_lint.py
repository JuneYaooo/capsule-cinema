#!/usr/bin/env python3
"""Lint viewer-facing video copy for leaked planning/meta language."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


DEFAULT_FORBIDDEN = [
    "前置宣传",
    "要前置",
    "前置到",
    "信任钩子",
    "记忆点",
    "传播资产",
    "策略语言",
    "制作策略",
    "内部策略",
    "数字负责吸引",
    "IP 负责记住",
    "front the proof",
    "proof fronting",
    "trust hook",
    "memory anchor",
    "propagation asset",
]

POLICY_LINE_MARKERS = [
    "不要出现",
    "不得出现",
    "禁止",
    "不能出现",
    "must not",
    "do not",
    "forbidden",
    "avoid",
]


def iter_text_lines(path: Path) -> list[tuple[int, str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        raise SystemExit(f"cannot read {path}: {exc}") from exc
    return list(enumerate(text.splitlines(), start=1))


def is_policy_line(line: str) -> bool:
    lower = line.lower()
    return any(marker.lower() in lower for marker in POLICY_LINE_MARKERS)


def lint(paths: list[Path], forbidden: list[str], *, allow_policy_lines: bool) -> list[dict]:
    hits: list[dict] = []
    for path in paths:
        for lineno, line in iter_text_lines(path):
            if allow_policy_lines and is_policy_line(line):
                continue
            for term in forbidden:
                if re.search(re.escape(term), line, flags=re.IGNORECASE):
                    hits.append({
                        "path": str(path),
                        "line": lineno,
                        "term": term,
                        "text": line.strip(),
                    })
    return hits


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Viewer-facing text/script/storyboard files to scan")
    parser.add_argument("--forbid", action="append", default=[], help="Additional forbidden term")
    parser.add_argument("--no-policy-line-allow", action="store_true", help="Do not ignore rule/instruction lines")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    paths = [Path(item).expanduser().resolve() for item in args.paths]
    forbidden = DEFAULT_FORBIDDEN + list(args.forbid or [])
    hits = lint(paths, forbidden, allow_policy_lines=not args.no_policy_line_allow)
    if args.json:
        print(json.dumps({"ok": not hits, "hits": hits}, ensure_ascii=False, indent=2))
    elif hits:
        print("visible_copy_lint: failed")
        for hit in hits:
            print(f"- {hit['path']}:{hit['line']} [{hit['term']}] {hit['text']}")
    else:
        print("visible_copy_lint: ok")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
