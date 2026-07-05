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

The runner should call `SocialMediaContentExtractorTool()._run(...)` with transcript enabled, video analysis disabled by default, a run-specific output directory, and `save_video=True`.

If the extractor import or parse call fails, write `00_source/source_status.md`, `artifact_manifest.json`, and `evidence_map.json`, then suggest `--local-video` fallback.

Do not persist API keys, cookies, or signed remote media URLs in recipe seeds.
