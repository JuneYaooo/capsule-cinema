#!/usr/bin/env python3
"""Initialize an organized deep account-distillation run directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DIRS = [
    "00_index",
    "01_raw/searches",
    "01_raw/accounts",
    "01_raw/posts",
    "01_raw/comments",
    "01_raw/media_urls_redacted",
    "02_normalized",
    "03_scoring",
    "04_account_deep_dive",
    "05_video_multimodal/complete",
    "05_video_multimodal/complete_audio",
    "05_video_multimodal/keyframes",
    "05_video_multimodal/limited",
    "05_video_multimodal/media",
    "06_synthesis",
    "07_production_package",
    "99_logs",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a numbered deep distillation run layout.")
    parser.add_argument("--root", default="output/account_distillation")
    parser.add_argument("--date", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--platform", required=True)
    args = parser.parse_args()

    run = Path(args.root) / f"{args.date}_{args.slug}_{args.platform}_deep"
    for rel in DIRS:
        (run / rel).mkdir(parents=True, exist_ok=True)

    readme = run / "00_index" / "README.md"
    if not readme.exists():
        readme.write_text(
            "\n".join(
                [
                    f"# {args.slug} Deep Account Distillation",
                    "",
                    f"- Date: {args.date}",
                    f"- Platform: {args.platform}",
                    "- Depth target: L6_full_reuse",
                    "",
                    "Use `00_index/evidence_map.json` to trace claims to raw, normalized, video, and account artifacts.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    evidence = run / "00_index" / "evidence_map.json"
    if not evidence.exists():
        evidence.write_text(
            json.dumps(
                {
                    "run": {
                        "date": args.date,
                        "slug": args.slug,
                        "platform": args.platform,
                        "depth_target": "L6_full_reuse",
                    },
                    "accounts": {},
                    "posts": {},
                    "limits": [],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    for rel, title in [
        ("00_index/sample_scope.md", "Sample Scope"),
        ("03_scoring/selection_notes.md", "Selection Notes"),
        ("06_synthesis/executive_summary.md", "Executive Summary"),
        ("06_synthesis/viral_reuse_bank.md", "Viral Reuse Bank"),
        ("06_synthesis/hook_and_opening_library.md", "Hook And Opening Library"),
        ("06_synthesis/format_playbook.md", "Format Playbook"),
        ("06_synthesis/hashtag_playbook.md", "Hashtag Playbook"),
        ("06_synthesis/risk_and_limits.md", "Risk And Limits"),
        ("07_production_package/30_day_topic_calendar.md", "30 Day Topic Calendar"),
        ("07_production_package/script_templates.md", "Script Templates"),
        ("07_production_package/operator_sop.md", "Operator SOP"),
        ("07_production_package/material_checklist.md", "Material Checklist"),
        ("07_production_package/qa_checklist.md", "QA Checklist"),
        ("99_logs/run_log.md", "Run Log"),
        ("99_logs/api_failures.md", "API Failures"),
        ("99_logs/redaction_audit.md", "Redaction Audit"),
    ]:
        path = run / rel
        if not path.exists():
            path.write_text(f"# {title}\n\n", encoding="utf-8")

    print(json.dumps({"run_dir": str(run), "created_dirs": len(DIRS)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
