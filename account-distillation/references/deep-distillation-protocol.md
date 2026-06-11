# Deep Distillation Protocol

Use this protocol when the task is not just scouting accounts, but extracting repeatable self-media playbooks from benchmark creators.

## Depth Gates

Label every run with the highest completed gate:

- `L1_metadata`: account/post/title/metrics only.
- `L2_caption_tag`: L1 plus caption cleanup, hashtag extraction, topic lane, hook tag, CTA signal.
- `L3_comment`: L2 plus sampled comments and comment-intent classification.
- `L4_video_opening`: L3 plus first frame, first 1s, 3s, 5s, 8s video review for key winners.
- `L5_content_complete`: L4 plus full spoken transcript, full-video visual review, and keyframe/proof/CTA/ending audit for selected winners.
- `L6_full_reuse`: L5 plus per-account winner cards, reusable structures, risk notes, material requirements, and production package.

A user-facing "deep distillation" should target `L6_full_reuse`. If platform access blocks video or comments, keep the output but mark the blocked layer as `limited`.

## Organized Run Layout

Use this layout for deep runs:

```text
output/account_distillation/<YYYYMMDD>_<vertical>_<platform>_deep/
├── 00_index/
│   ├── README.md
│   ├── evidence_map.json
│   └── sample_scope.md
├── 01_raw/
│   ├── searches/
│   ├── accounts/
│   ├── posts/
│   ├── comments/
│   └── media_urls_redacted/
├── 02_normalized/
│   ├── accounts.jsonl
│   ├── posts.jsonl
│   ├── comments.jsonl
│   └── media_inventory.jsonl
├── 03_scoring/
│   ├── winner_matrix.csv
│   ├── account_shortlist.csv
│   └── selection_notes.md
├── 04_account_deep_dive/
│   └── <account_slug>/
│       ├── account_brief.md
│       ├── post_matrix.csv
│       ├── comment_intents.md
│       └── winner_cards/
│           └── <post_id>.md
├── 05_video_multimodal/
│   ├── complete/
│   ├── complete_audio/
│   ├── keyframes/
│   ├── limited/
│   └── media/
├── 06_synthesis/
│   ├── executive_summary.md
│   ├── viral_reuse_bank.md
│   ├── hook_and_opening_library.md
│   ├── format_playbook.md
│   ├── hashtag_playbook.md
│   └── risk_and_limits.md
├── 07_production_package/
│   ├── 30_day_topic_calendar.md
│   ├── script_templates.md
│   ├── operator_sop.md
│   ├── material_checklist.md
│   └── qa_checklist.md
└── 99_logs/
    ├── run_log.md
    ├── api_failures.md
    └── redaction_audit.md
```

Do not put final human-facing strategy files only in a loose `reports/` directory for deep runs.

## Sample Tiers

Every candidate account must be assigned one tier:

- `core_deep`: direct benchmark. Build account folder and winner cards. Default 6-10 accounts.
- `supporting_pattern`: useful for one pattern, but not a full benchmark.
- `light_material_pool`: useful for future topic/material screening. Keep metrics and topic labels; do not deep-distill structure unless promoted later.
- `excluded`: explicitly out of scope, such as strong personal IP, AI变现/course-selling accounts, pure opinion, pure AI short-drama output, or non-AI topic drift.

For AI工具/AI开源栏目号 runs:

- Each `core_deep` account should have a 50-post base sample whenever platform access allows it.
- Select 5-10 winners per `core_deep` account for structure distillation.
- Rank winners by account-internal overperformance first, then absolute interactions. Do not let one huge account dominate the entire pattern library.
- Treat AI变现/卖课/招商/个人IP coaching accounts as `excluded` unless the user explicitly changes the research scope.
- Also filter at post level inside otherwise-valid accounts. Posts about AI变现, 获客, 带货, 短剧/剧情流量, course selling, or personal coaching must not become winner cards or light-material recommendations for an AI工具/AI开源栏目号 run.
- The benchmark should be operable as a column: recurring topic lanes, repeatable proof materials, screen/demo/GitHub/tool UI evidence, and weak dependence on the creator's face or personal authority.
- The later `light_material_pool` may pull many more posts from selected accounts or adjacent search results, but it is for topic discovery only: title, metrics, theme, source account, and reuse angle. Do not claim full hook/video structure from this pool.

For `core_deep`, capture:

- positioning and audience
- recurring lanes
- title/caption/hashtag patterns
- 50-post base sample status
- Top 5-10 posts by score and by account-relative overperformance
- first-screen proof style
- comment demand
- visible or inferred conversion path
- reusable structures and non-copyable parts

## Winner Card Standard

Create one card per selected winner:

```markdown
# <post title>

## Evidence
- Account:
- Post ID:
- Link/source:
- Metrics:
- Caption:
- Hashtags:
- Media status: content_complete | transcript_only | visual_limited | keyframe_only | first8_only | metadata_only | missing
- Transcript path:
- Full-video review path:
- Keyframe review path:
- Comment sample: complete | sampled | missing

## Opening Audit
- First frame:
- 0-1s:
- 1-3s:
- 3-5s:
- 5-8s:
- Real hook:
- Title hook alignment:

## Structure
- Lane:
- Hook mechanism:
- Proof type:
- Script beats:
- Visual devices:
- CTA/comment driver:

## Why It Worked
- Likes:
- Saves/favorites:
- Shares:
- Comments:

## Reuse
- Reusable template:
- Required materials:
- Similar topics to produce:
- Risk notes:
- Do not copy:
```

## Video Review Standard

For `L5_content_complete` and `L6_full_reuse`, full video with audio is the default evidence target. First-8-second clips are only an opening-audit supplement or a fallback when full video access fails. If only the first 8 seconds were reviewed, mark the winner card `media_status: first8_only` and do not claim full script structure, CTA, ending, or conversion mechanics from that sample.

When TikHub or search results identify a strong post but lack concrete video/note content, use `/Users/june2/code/github/video_workflow/backend/video_workflow/custom_tools/extract_content/social_media_content_extractor_tool.py` on selected winner URLs to fill content details. Use this after metrics screening, not across the full 50-post base sample. The extractor depends on `XIAOLVFANG_API_TOKEN` or `VIDEO_PARSE_API_TOKEN` for parsing, `SILICONFLOW_API_KEY` for transcript, and the Gemini analyzer path for optional video analysis.

Preferred cost ladder:

- TikHub for broad account/post collection and ranking.
- TikHub one-video/media routes for selected winners when IDs exist but content detail is thin.
- Social-media extractor for selected share/full URLs when metadata cannot answer spoken hook, proof moment, CTA, ending, or visual structure.
- Multimodal full-video review for S-level reuse-bank candidates and representative formats.

Do not upgrade a metadata-only winner into a final hook/script case just because it has high metrics. Keep `media_status: metadata_only` or `limited` until the concrete content layer is reviewed.

Content-complete requires all three layers:

- Full spoken transcript:口播/字幕/OCR text from opening through ending.
- Full-video visual analysis: scene-by-scene observation of UI, demo proof, result proof, subtitles, arrows, zooms, cuts, BGM/SFX, pacing, and trust devices.
- Keyframe/opening audit: first frame, 0-1s, 1-3s, 3-5s, 5-8s, plus keyframes for proof, payoff, CTA, and ending.

If one layer is missing, use a narrower status such as `transcript_only`, `visual_limited`, `keyframe_only`, or `metadata_only`; do not call the post fully distilled.

If a low-resolution proxy is generated for model upload, preserve audio unless the platform/media lacks audio or the user explicitly asks for silent visual analysis. If audio is stripped, label the review `visual_only_proxy` and do not make confident claims about spoken opening, BGM, exact CTA wording, or voice pacing.

A video review must not stop at "looks good". It must answer:

1. What is visible in the first frame?
2. What appears or is spoken in 0-1s, 1-3s, 3-5s, and 5-8s?
3. Does the real opening match the metadata hook?
4. What concrete proof appears before second 5?
5. Does the opening still work muted?
6. Does the opening still work audio-only?
7. Which visual devices create trust or speed?
8. What gap is opened and when is it promised to close?
9. What should be copied as mechanism, and what should not be copied?

For full-video review, also answer:

10. What happens after the hook: setup, proof, demo, caveat, result, CTA?
11. Where does the video prove the title promise?
12. What is the exact ending move: keyword comment, follow, profile click, purchase, course, live, or none?
13. What can be reproduced by an operator with ordinary materials?
14. What requires creator-specific credibility, paid tools, or unavailable assets?
15. Which keyframes are essential to reproduce the effect or credibility of this post?

## Reuse Bank Standard

The reuse bank is the most important production output. Each item needs:

- priority: `S`, `A`, or `B`
- original account and post
- lane
- metrics
- hook mechanism
- why it worked
- reuse template
- 5 concrete derivative topics
- required materials
- CTA/lead magnet
- risk and verification notes

Do not include a post in the main reuse bank if it is only high-traffic but cannot be turned into a repeatable AI tools/open-source column.

## Validation Checklist

Before final response:

- Raw/log artifacts have no API keys, cookies, signed media URLs, or unredacted cache URLs.
- Human-facing files live under `00_index`, `04_account_deep_dive`, `06_synthesis`, and `07_production_package`.
- Every `core_deep` account has an account folder.
- Every S-level reuse item has required materials and risk notes.
- Video conclusions are separated from metadata-only conclusions.
- Limits are explicit: missing comments, missing media, partial first-8s only, platform metric gaps.
