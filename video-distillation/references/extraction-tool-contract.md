# Extraction Tool Contract

Use the external social-media extractor only for URL or copied share-text acquisition:

```text
/Users/june2/code/github/video_workflow/backend/video_workflow/custom_tools/extract_content/social_media_content_extractor_tool.py
```

When a caller passes a different `--external-video-workflow-root` in tests, resolve the same relative tool path below that root:
`backend/video_workflow/custom_tools/extract_content/social_media_content_extractor_tool.py`.

Default root:

```text
/Users/june2/code/github/video_workflow
```

Default env file:

```text
/Users/june2/code/github/video_workflow/.env
```

The runner should call `SocialMediaContentExtractorTool()._run(...)` with transcript enabled, a run-specific output directory, and `save_video=True`. The low-level extractor helper defaults `enable_video_analysis=False`; `run_url_distillation(..., enable_gemini=True)` must pass `enable_video_analysis=True` so the extractor can return Gemini-class or equivalent video analysis when available.

The standalone runner imports the tool by adding `<external_video_workflow_root>/backend/video_workflow` to `sys.path`, then importing `custom_tools.extract_content.social_media_content_extractor_tool`. The configured tool path remains:

```text
<external_video_workflow_root>/backend/video_workflow/custom_tools/extract_content/social_media_content_extractor_tool.py
```

The extractor call must pass URL/share text as `url`, enable transcript acquisition, set `enable_video_analysis` from the runner's Gemini flag, set `save_video=True`, and use an output directory under the current run's `00_source/extractor/` folder.

When the extractor returns video-analysis data, persist it to `04_gemini/video_analysis.json` and `04_gemini/video_analysis.md`, then feed it into copy, whole-video, visual, motion, audio, and production-route builders. When the analysis is disabled or unavailable, mark `V4_multimodal_reviewed` as `limited` instead of claiming full recipe readiness.

Persist a JSON-safe copy of the extractor return value to `00_source/extract_result.json`. If the extractor returns a local video path, continue processing that file in the same run directory so extractor artifacts remain in the manifest.

If the extractor import or acquisition call fails, write `00_source/source_status.md`, `artifact_manifest.json`, and `evidence_map.json`. Failure status must mention `references/extraction-tool-contract.md`, the exact default extractor path, and the configured extractor path. Do not include private env/token names, secret values, `account-distillation/`, cookies, or signed remote media URLs in status output.

Do not persist API keys, cookies, or signed remote media URLs in recipe seeds.
