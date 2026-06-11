# TikHub Recipes

Use TikHub as a collection layer, not as the whole analysis. Always preserve raw responses and then normalize.

## Setup

If `tikhub` is not in `PATH`, use:

```bash
TIKHUB=/Users/june2/code/github/video_workflow/.claude/skills/account-diagnostic/tikhub/bin/tikhub
$TIKHUB --health
$TIKHUB --platforms
```

Before using an endpoint:

```bash
$TIKHUB list <platform> <keyword>
$TIKHUB describe <platform> <tool_name>
```

Some cached catalogs may show incomplete schemas for newer endpoints. In that case, inspect adjacent web/app endpoints, run a tiny probe, or refresh the tool cache if appropriate.

## Douyin Common Routes

Discovery:

```bash
$TIKHUB list douyin search
$TIKHUB list douyin user
$TIKHUB list douyin video
```

Useful tools seen in the bundled catalog:

- `douyin_search_fetch_user_search`: user search.
- `douyin_search_fetch_video_search_v1` / `v2`: video search.
- `douyin_web_fetch_hot_search_result`: hot search.
- `douyin_billboard_fetch_hot_account_search_list`: account search.
- `douyin_web_handler_user_profile`: profile by `sec_user_id`.
- `douyin_web_handler_user_profile_v2`: profile by `unique_id`.
- `douyin_web_fetch_user_post_videos`: homepage posts by `sec_user_id`.
- `douyin_web_fetch_one_video`: single post by `aweme_id`.
- `douyin_web_fetch_video_high_quality_play_url`: high-quality media URL by `aweme_id` or share URL.
- `douyin_web_fetch_video_comments`: comments by post.

Example profile-post path:

```bash
$TIKHUB describe douyin douyin_web_fetch_user_post_videos
$TIKHUB douyin douyin_web_fetch_user_post_videos \
  --sec_user_id '<sec_user_id>' \
  --count:int=20 \
  --max_cursor '0' > raw/posts/<account_id>_page1.json
```

Example video media URL path:

```bash
$TIKHUB describe douyin douyin_web_fetch_video_high_quality_play_url
$TIKHUB douyin douyin_web_fetch_video_high_quality_play_url \
  --aweme_id '<aweme_id>' > raw/posts/<aweme_id>_play_url.json
```

Then download only when rights/access allow and save to `media/videos/<post_id>.mp4`. Do not store signed URLs in final reports.

## Detail Completion With Extractor

TikHub remains the broad collection layer. If a selected winner needs concrete content beyond title/metrics/tags, use the local extractor only for that winner after a share/full URL is available:

```text
/Users/june2/code/github/video_workflow/backend/video_workflow/custom_tools/extract_content/social_media_content_extractor_tool.py
```

Use it for selected downloads, transcript, and optional video analysis. Required env depends on the enabled step: `XIAOLVFANG_API_TOKEN` or `VIDEO_PARSE_API_TOKEN` for parsing, `SILICONFLOW_API_KEY` for transcript, and `VIDEO_ANALYSIS_*` or Gemini-compatible env for visual analysis. Save durable outputs under the run's `05_video_multimodal/` folders and redact parse/media URLs from human-facing artifacts.

## Xiaohongshu Common Routes

Discovery:

```bash
$TIKHUB list xiaohongshu search
$TIKHUB list xiaohongshu note
$TIKHUB list xiaohongshu user
```

Useful tools seen in the bundled catalog:

- `xiaohongshu_web_search_notes`
- `xiaohongshu_web_search_notes_v3`
- `xiaohongshu_web_search_users`
- `xiaohongshu_web_get_note_info_v2` / `v4` / `v7`
- `xiaohongshu_web_get_note_comments`
- `xiaohongshu_web_get_user_notes_v2`
- `xiaohongshu_web_get_note_id_and_xsec_token`
- `xiaohongshu_web_v2_fetch_note_image`
- `xiaohongshu_app_v2_get_video_note_detail`
- `xiaohongshu_app_v2_get_user_posted_notes`

For video notes, prioritize note detail plus media/cover evidence, then run multimodal review when video is available.

## Bilibili Common Routes

Discover first:

```bash
$TIKHUB list bilibili search
$TIKHUB list bilibili video
$TIKHUB list bilibili user
```

Use Bilibili especially for AI open-source, developer, long tutorial, and tool-demo accounts. Because Bilibili videos are longer, sample the first 30-90 seconds and major chapter/turning points for multimodal review.

## Raw Storage Rules

- Save every response under `raw/<type>/`.
- Include query, tool, arguments, platform, and retrieval time in the filename or sidecar metadata when possible.
- Do not overwrite raw responses during retries; add page/cursor/timestamp suffixes.
- Normalize later with `scripts/normalize_samples.py` or a project-specific parser.

## Rate And Error Handling

- Keep concurrency low, ideally 1-3 requests.
- On `401`, fix API key outside the repo.
- On `429`, slow down and continue from saved raw pages.
- On stale schema/tool errors, run `list`/`describe` again and use the closest current endpoint.
