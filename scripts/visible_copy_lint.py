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
    "真实版",
    "真实截图版",
    "截图版",
    "修正版",
    "重做版",
    "终版",
    "最终版",
    "制作说明",
    "制作语言",
    "内部话术",
    "内部文案",
    "内部版本",
    "这版修正",
    "这次修正",
    "按你的反馈",
    "根据你的反馈",
    "source:",
    "real asset",
    "real assets",
    "README real",
    "public-ready",
    "revision",
    "draft",
    "链接",
    "网址",
    "域名",
    "二维码",
    "扫码",
    "URL",
]

DEFAULT_FORBIDDEN_REGEX = [
    r"\bv[0-9]+(?:[._-][0-9]+)?\b",
    r"\bversion\s*[0-9]+\b",
    r"https?://[^\s<>\u3000]+",
    r"\b(?:www\.)?[a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)*\.(?:com|cn|net|org|io|ai|dev|app|co|edu|gov|xyz|me|tv|cc)(?:/[^\s<>\u3000]*)?",
    r"[^，。！？\n]{1,32}是[^，。！？\n]{1,32}，不是[^，。！？\n]{1,32}",
    r"不是[^，。！？\n]{1,48}，而是[^，。！？\n]{1,48}",
    r"不是[^，。！？\n]{1,48}，是[^，。！？\n]{1,48}",
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

METADATA_JSON_KEYS = [
    "path",
    "source_path",
    "source_params_path",
    "source_url",
    "final_video",
    "cover",
    "qa_report",
    "lint_report",
    "created_at",
    "supersedes",
    "version_slug",
    "status",
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


def is_metadata_line(line: str) -> bool:
    stripped = line.strip()
    lower = stripped.lower()
    if re.match(r'^"[^"]*(?:path|url|created_at|status|version_slug|supersedes)"\s*:', lower):
        return True
    return any(re.match(rf'^"{re.escape(key)}"\s*:', lower) for key in METADATA_JSON_KEYS)


def lint(
    paths: list[Path],
    forbidden: list[str],
    forbidden_regex: list[str],
    *,
    allow_policy_lines: bool,
    ignore_metadata_lines: bool,
) -> list[dict]:
    hits: list[dict] = []
    for path in paths:
        for lineno, line in iter_text_lines(path):
            if allow_policy_lines and is_policy_line(line):
                continue
            if ignore_metadata_lines and is_metadata_line(line):
                continue
            for term in forbidden:
                if re.search(re.escape(term), line, flags=re.IGNORECASE):
                    hits.append({
                        "path": str(path),
                        "line": lineno,
                        "term": term,
                        "text": line.strip(),
                    })
            for pattern in forbidden_regex:
                if re.search(pattern, line, flags=re.IGNORECASE):
                    hits.append({
                        "path": str(path),
                        "line": lineno,
                        "term": f"regex:{pattern}",
                        "text": line.strip(),
                    })
    return hits


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Viewer-facing text/script/storyboard files to scan")
    parser.add_argument("--forbid", action="append", default=[], help="Additional forbidden term")
    parser.add_argument("--forbid-regex", action="append", default=[], help="Additional forbidden regex")
    parser.add_argument("--no-policy-line-allow", action="store_true", help="Do not ignore rule/instruction lines")
    parser.add_argument("--no-metadata-line-ignore", action="store_true", help="Do not ignore JSON metadata/path lines")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    paths = [Path(item).expanduser().resolve() for item in args.paths]
    forbidden = DEFAULT_FORBIDDEN + list(args.forbid or [])
    forbidden_regex = DEFAULT_FORBIDDEN_REGEX + list(args.forbid_regex or [])
    hits = lint(
        paths,
        forbidden,
        forbidden_regex,
        allow_policy_lines=not args.no_policy_line_allow,
        ignore_metadata_lines=not args.no_metadata_line_ignore,
    )
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
