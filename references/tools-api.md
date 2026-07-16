# Public Tools API

Invoke registered tools through:

```bash
python scripts/run_tool.py --tool ToolClass --params '{"key":"value"}'
```

The tracked registry exposes official Volcengine image/video tools, official
MiniMax TTS, Doubao Speech (API Key + bidirectional WebSocket), RunningHub
workflow examples, and local processing/QA tools. `scripts/run_tool.py` also
merges the ignored local registry when it is present.

Use `python scripts/provider_menu.py --json` to inspect the effective registry
on the current machine. A clean clone shows only the public allowlist; a local
development checkout may show additional `local_only` records.

All generation results must be downloaded to local output paths. Do not put
remote URLs, authorization values, or raw provider responses into manifests or
delivery reports.

The official image tool defaults to `doubao-seedream-5-0-pro-260628` and
accepts `size`, `output_format`, `response_format`, `watermark`,
`optimize_prompt_options`, and up to 10 reference images. It deliberately does
not expose group-image or streaming modes because Seedream 5.0 Pro does not
support them.

The official video tool defaults to `doubao-seedance-2-0-260128`. In addition
to text and first-frame video it accepts explicit first/last frames and
multimodal image/video/audio references. Supported request controls include
`resolution`, `ratio`, `duration`, `generate_audio`, `return_last_frame`,
`callback_url`, `execution_expires_after`, `priority`, `safety_identifier`, and
`watermark`. It downloads both video and requested last frame locally and does
not return expiring signed URLs.

For complete-video runs, pass `--delivery_promise` to `scripts/run_video.py`
when the route has a specific promise such as real motion, source-led editing,
narrated explanation, reference remake, capsule preset, or a specialized
RunningHub workflow.

Evidence-gated routes also accept `--source_review_path` for source-led edits
and `--reference_analysis_path` for reference remakes. The run records its
reviewable route in `work/production_proposal.json` and its decisions/fallbacks
in `work/decision_log.json`.

Capsule runs may pass `--capsule_params_json` for declared capsule inputs and
`--accept_preflight_changes` only after the user has reviewed and accepted a
reported substitution or downgrade.

`scripts/run_video.py --capsule <name>` 会按 active 胶囊目录包注入合同；公开
胶囊必须只引用公开渠道，本地渠道胶囊保持 Git 忽略。
