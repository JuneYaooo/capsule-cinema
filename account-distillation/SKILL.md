---
name: account-distillation
description: Distill social-media accounts and high-performing posts into source-grounded content strategy, hook libraries, format playbooks, and reusable account capsules. Use when the user asks to find benchmark accounts, research AI-news/AI-tools/AI-open-source creators, analyze viral posts, inspect hooks/openings/cover copy/video structure with TikHub or platform data, or build a self-media account methodology from competitors. Chinese triggers: 蒸馏账号, 对标账号, 自媒体账号蒸馏, 爆款内容分析, 高赞内容, 高互动内容, 钩子结构, 开头钩子, 封面文案, AI新闻账号, AI工具账号, AI开源账号, TikHub搜索账号.
---

# Account Distillation

Distill benchmark social-media accounts into evidence-backed strategy, hook structures, and reusable production playbooks.

Core method: **Scout -> Snapshot -> Score -> See -> Segment -> Synthesize -> Codify -> Validate**.

For deep account distillation, use the stricter protocol in
[references/deep-distillation-protocol.md](references/deep-distillation-protocol.md). It defines
the required run layout, depth gates, account folders, post cards, video review standards, and
reuse-bank outputs. Use it whenever the user asks for 深度蒸馏, 爆款复用清单, 批量自媒体打法, or
complains that outputs are shallow or disorganized.

This skill is evidence-first. Preserve raw account/post/video evidence before summarizing, separate platform metrics from multimodal observations, and label unsupported strategy as inference.

## Read When Needed

- Data schemas and artifact layout: [references/schemas.md](references/schemas.md)
- Deep distillation protocol and organized output layout: [references/deep-distillation-protocol.md](references/deep-distillation-protocol.md)
- TikHub collection recipes: [references/tikhub-recipes.md](references/tikhub-recipes.md)
- Hook and format taxonomy: [references/hook-taxonomy.md](references/hook-taxonomy.md)

## Output Boundary

This skill contains methodology only. Distilled results for specific accounts/verticals (account analyses, distilled column capsules, hook libraries, playbooks) are run artifacts: land them under `output/account_distillation/` and never commit them into this skill's `references/`. If a distilled method is worth sharing, package it as a standard video capsule (`capsule_store.py upsert` + `export`) instead of a Markdown reference.

## Trigger Conditions

Use this skill when the user asks to:

- Find or compare benchmark accounts in a vertical.
- Distill AI news, AI tools, AI open-source, developer, product, tutorial, or creator accounts.
- Turn completed AI工具/AI开源/GitHub deep-run evidence into a reusable account capsule or production preset.
- Analyze high-like, high-comment, high-save, high-share, or high-retention posts.
- Extract hook structures, cover text, first-5-second openings, visual style, editing rhythm, or comment drivers.
- Use TikHub or platform APIs to collect account/profile/post/comment data.
- Build account capsules, hook libraries, content templates, topic lanes, or a repeatable self-media strategy.

## Non-Negotiables

- Do not distill viral structure from title/caption/metrics alone when original video is available. High-performing video posts need a multimodal review layer.
- Preserve raw JSON, source URLs/IDs, timestamps, and retrieval time before producing strategy.
- Keep platform facts, model observations, and your synthesis in separate fields or sections.
- Do not copy creators' exact scripts as templates. Extract mechanism, sequence, and reusable pattern.
- Do not treat absolute likes as the only winner signal. Compare against account baseline and normalize by account size when available.
- Respect platform access limits and private data boundaries. Do not store cookies, API keys, signed URLs, or private tokens in artifacts.
- A "deep" result must include account-level, post-level, video-level, comment-level, tag-level, and reuse-level analysis. If one layer is unavailable, mark it explicitly as `limited` or `missing`.
- Do not leave deep-run artifacts scattered across generic `reports/`, `derived/`, and `multimodal/` only. Put human-facing outputs under numbered folders described by the deep protocol.
- For AI工具/AI开源栏目号 research, do not mix in AI变现号, course-selling accounts, strong personal-IP opinion accounts, or broad creator-economy accounts as `core_deep` benchmarks. They may be `excluded` or `supporting_pattern` only when their format is directly reusable by a non-personal column.
- Apply the same exclusion at post level. Even inside a valid AI工具/AI开源 account, remove posts whose primary topic is AI变现, 获客, 带货, 短剧/剧情流量, course selling, or personal coaching unless the user explicitly scopes that lane in.
- For each `core_deep` account, collect a default of 50 recent/public posts before choosing winners. Deep-distill 5-10 high-performing posts per account; do not infer an account pattern from only one or two viral posts.
- For the later "爆款素材池", it is acceptable to widen to more posts/accounts with lightweight metrics-only screening, but label it separately from deep structural distillation.
- Use TikHub for broad screening and account-relative ranking. Use the social-media extractor only for selected winners that need concrete video/transcript/detail completion; do not run parser/download/transcript/model analysis across every 50-post base sample by default.
- Do not label a post `content_complete` unless it has full spoken transcript, full-video visual analysis, and keyframe/opening audit. Missing any one layer means the post is still `metadata_only`, `transcript_only`, `visual_limited`, `keyframe_only`, or `first8_only`.

## Default Workflow

### Output Directory Rule

Do not write research runs into the skill source directory. Use a separate run directory:

```text
output/account_distillation/<YYYYMMDD>_<vertical_slug>_<platform_slug>/
```

Example: `output/account_distillation/<YYYYMMDD>_ai_tools_douyin/`.

Inside each run, keep raw evidence and derived analysis separate:

```text
raw/            # TikHub/search/API responses, never rewritten
media/          # downloaded videos, covers, sampled frames when available
multimodal/     # Gemini-class video reviews and frame/video observations
derived/        # normalized JSONL, scores, extracted fields
reports/        # capsules, hook library, playbook, summary
logs/           # command notes, API blind spots, failed calls
```

Only the skill's reusable instructions, references, and scripts belong inside `account-distillation/`.

For deep runs, initialize a numbered layout instead of the loose default:

```bash
python3 account-distillation/scripts/init_deep_run.py \
  --root output/account_distillation \
  --date YYYYMMDD \
  --slug ai_tools_open_source_deep \
  --platform douyin
```

Then write analysis to `00_index/`, `04_account_deep_dive/`, `05_video_multimodal/`,
`06_synthesis/`, and `07_production_package/` instead of piling everything into `reports/`.

1. **Scope**
   - Define platform(s), vertical, language, geography, time window, and account size tier.
   - For AI verticals, classify lanes: `ai_news`, `ai_tools`, `ai_open_source`, `ai_tutorial`, `ai_workflow`, `ai_opinion`, `ai_productivity`, `ai_dev`.
   - Decide sample size. Default: 20-50 candidate accounts, shortlist 6-10 `core_deep` accounts, 50 posts per core account, deep winner cards for 5-10 posts per account, multimodal review for the strongest available winners.
   - For a deep run, choose tiers: `core_deep` accounts get account folders and 5-10 deep winner cards from a 50-post base sample; `supporting_pattern` accounts feed pattern comparison only; `light_material_pool` accounts/posts feed topic screening only; `excluded` accounts are documented so personal-IP or AI变现 accounts are not mixed with column accounts.
   - For AI工具/AI开源栏目号, `core_deep` means the account can be operated as a栏目号 by a small team: recurring tool/project/tutorial formats, screen/demo proof, weak dependence on personal charisma, and repeatable topic sourcing.
   - Exclude from `core_deep`: AI变现/卖课/招商/IP coaching, pure AI资讯口播 without demo or task translation, pure个人观点, general创业号, and creator accounts whose moat is mainly personal credibility.

2. **Scout**
   - Search by multiple query clusters, not one keyword. Example clusters: `AI工具`, `AI新闻`, `开源AI`, `GitHub项目`, `大模型`, `Agent`, `效率工具`, `程序员AI`.
   - Combine platform search, hot lists, user search, post search, recommendations, and manual seeds when available.
   - Record why each account entered the candidate pool.

3. **Snapshot**
   - Store raw account/profile/post/comment/search responses under `raw/`.
   - Normalize into `accounts.jsonl`, `posts.jsonl`, and optional `comments.jsonl`.
   - For shortlisted posts, store video/media links or local downloaded media paths when legally and technically available.
   - See [schemas.md](references/schemas.md) for required fields.

4. **Score**
   - Score posts with absolute interactions, normalized engagement, and account-internal winner index.
   - Prefer posts that overperform the creator's median, not just posts from already-large accounts.
   - Include separate comment, save/favorite, and share signals when available; for tutorial/tool content, saves/favorites often matter more than likes.
   - Use `scripts/score_posts.py` when normalized JSONL exists.

5. **See**
   - For each selected high-performing video, inspect the original media with a multimodal model such as Gemini or another strong video-understanding model.
   - If TikHub/search data identifies a strong post but does not provide enough concrete content or media detail, use the local social-media extractor at `/Users/june2/code/github/video_workflow/backend/video_workflow/custom_tools/extract_content/social_media_content_extractor_tool.py` on a share/full URL for selected winners only. This is a targeted detail-completion step, not the default for all 50 sampled posts.
   - If TikHub provides metrics and IDs but no usable share/full URL, first try a TikHub one-video/media-url route for the selected post, then mark `detail_enrichment_needed` if a concrete URL still must be obtained manually.
   - Land extractor outputs under the run's `05_video_multimodal/media/`, `complete_audio/`, or `complete/` folders, then update the corresponding winner card and `evidence_map.json`. Store local paths and observations only; do not persist signed media URLs or parse tokens.
   - For content-level winner distillation, require three layers per selected post: complete口播转录, full-video visual review, and keyframe/opening audit. Do not infer CTA, ending, visual proof, pacing, or script sequence from title/caption alone.
   - Required observations: first frame, first 1s, first 3s, first 5s, visible cover/opening text, spoken opening, subtitle/caption strategy, screen/demo evidence, pacing, transitions, audio/BGM, visual proof, emotional/curiosity beats, CTA/comment prompt, and ending.
   - Extract timestamped moments: `hook_0_3s`, `promise_3_8s`, `proof_or_demo`, `turning_point`, `payoff`, `comment_trigger`.
   - If video cannot be downloaded, use available screenshots, cover, caption, comments, and platform metadata, but mark `multimodal_status: limited`.
   - The title/caption hook is not the real hook unless it appears in the first seconds as visible text, spoken words, or concrete proof. Audit first frame, first 1s, 3s, 5s, and 8s.

6. **Segment**
   - Break each winner into reusable structural units: topic, viewer promise, hook mechanism, narrative sequence, proof type, visual device, edit rhythm, packaging, comment driver, and platform fit.
   - Use [hook-taxonomy.md](references/hook-taxonomy.md) to tag hook mechanisms and content formats.

7. **Synthesize**
   - Compare across accounts and posts. Produce findings at three levels:
     - Account: positioning, audience, lanes, cadence, visual system, monetization/funnel hints.
     - Post: winner patterns, hook formulas, structure, visual proof, comment dynamics.
     - Vertical: opportunity gaps, repeatable formats, risky overused formats, content calendar ideas.
   - Distinguish direct evidence from inferred strategy.

8. **Codify**
   - Create durable outputs:
     - `account_registry.jsonl`
     - `posts.jsonl`
     - `winner_matrix.csv`
     - `account_capsules/<handle>.md`
     - `hook_library.md`
     - `format_playbook.md`
     - `topic_lanes.md`
     - `evidence_map.json`
   - For direct production use, add `script_templates.md` with fill-in structures, not copied scripts.
   - For deep runs, also create:
     - `04_account_deep_dive/<account>/account_brief.md`
     - `04_account_deep_dive/<account>/winner_cards/*.md`
     - `04_account_deep_dive/<account>/post_matrix.csv`
     - `06_synthesis/viral_reuse_bank.md`
     - `06_synthesis/hook_and_opening_library.md`
     - `07_production_package/30_day_topic_calendar.md`
     - `07_production_package/operator_sop.md`

9. **Validate**
   - Verify every major claim points to accounts/posts/media evidence.
   - Check that top winners include multimodal observations unless unavailable.
   - Name sample limits, missing metrics, and platform/API blind spots.
   - When proposing new content ideas, state which observed pattern each idea adapts.

## Multimodal Video Review Prompt

Use this prompt shape for Gemini-class video models or any equivalent video-understanding model:

```text
Analyze this short-form video as a competitor-content distillation sample.

Return structured JSON/Markdown with:
1. post_id/source, duration, language, visible format.
2. Full spoken transcript or subtitle/OCR transcript. Separate certain text from uncertain text.
3. First frame, first 1s, first 3s, first 5s, first 8s: what appears, what is said/shown, why it may stop scrolling.
4. Keyframe table: timestamp, frame content, visible text, UI/result proof, camera/edit move, narrative function.
5. Exact visible hook text and spoken opening if readable/audible. If uncertain, mark uncertain.
6. Timeline beats with timestamps: hook, promise, proof/demo, contrast, turning point, payoff, CTA/comment trigger, ending.
7. Visual devices: face, screen recording, product UI, GitHub page, code, charts, screenshots, subtitles, arrows, zooms, cuts, BGM/SFX.
8. Hook mechanism tags and content format tags.
9. Why this could drive likes, saves, shares, or comments.
10. Reusable structure in abstract form. Do not copy the creator's exact script.
11. Evidence gaps or low-confidence observations.
```

Save the response as `multimodal/<post_id>.md` or `.json`, and link it from `evidence_map.json`.

## TikHub Usage

When TikHub is available, discover the current schema before relying on a tool:

```bash
tikhub list douyin search
tikhub describe douyin <tool_name>
tikhub douyin <tool_name> --json '{"key":"value"}'
```

Use the vendored CLI at `/Users/june2/code/github/video_workflow/.claude/skills/account-diagnostic/tikhub/bin/tikhub` when it is not symlinked into `PATH`. Read [tikhub-recipes.md](references/tikhub-recipes.md) for common platform routes.

## Response Rules

- Start with the methodology or sampling frame when the user is still designing the research.
- For completed research, lead with high-signal patterns and cite the local artifact paths.
- Report sample size, platforms, retrieval dates, and missing data.
- Separate `Observed`, `Inferred`, and `Reusable` sections for strategy claims.
- If original videos were not reviewed, say the result is metadata-only and should not be treated as final hook distillation.
