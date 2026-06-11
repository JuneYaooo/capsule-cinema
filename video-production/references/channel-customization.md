# Channel Customization

Use this when the user wants to add, remove, replace, suspend, or narrow video-production channels. The default policy starts with Juling, RunningHub, MiniMax, and Doubao, but channel ownership must remain editable by the user.

This structure follows the original `video-agent` design:

- `tools`: capability records for each tool/channel.
- `engine_decision`: ordered decision rules with fallbacks.
- `tool_chain_patterns`: reusable production DAG patterns.
- local capsule `config`: verified per-capsule defaults.
- `pitfalls` / QA notes: known failure modes and checks.

## Policy Precedence

Resolve channel/tool choice in this order:

1. Current user instruction.
2. Active session/workspace memory, when present.
3. Matching local capsule `config`, when a capsule is selected.
4. User/project-maintained channel registry or channel policy.
5. This skill's default `references/channel-policy.md`.
6. Current code/tool availability.
7. Old capsules, archive scripts, or examples.

Current user instruction can override everything. Old examples cannot resurrect a removed channel. If a capsule references a removed tool, migrate it or report the mismatch instead of executing it blindly.

## Registry Shape

Prefer maintaining custom channels in a registry-shaped record modeled after `.claude/skills/video-agent/tool_registry.json`. The exact storage can be JSON, YAML, or Markdown, but keep these fields:

```json
{
  "tools": {
    "image_generation": {
      "ToolName": {
        "status": "approved",
        "channel": "ProviderName",
        "description": "What it does",
        "best_for": ["specific use case"],
        "avoid_for": ["known bad fit"],
        "inputs": {
          "prompt": {"type": "string", "required": true},
          "output_path": {"type": "string", "required": false, "note": "wrapper/session may inject this"}
        },
        "outputs": {"image": "file path or URL"},
        "env": ["PROVIDER_API_KEY", "PROVIDER_BASE_URL"],
        "limits": {"aspect_ratio": ["9:16", "16:9"], "max_duration_s": 10},
        "pitfalls": ["known failure mode"],
        "qa": ["required check"],
        "fallback": "AnotherApprovedTool"
      }
    }
  },
  "engine_decision": {
    "image_engine": {
      "decision_flow": [
        {
          "condition": "when to use this tool",
          "choose": "ToolName",
          "fallback": "AnotherApprovedTool",
          "note": "why"
        }
      ]
    }
  },
  "tool_chain_patterns": {
    "narration_video": {
      "per_scene": ["[ImageTool] -> [VideoTool]"],
      "assembly": {"tts": true, "subtitle": true, "bgm": true}
    }
  }
}
```

The `status` field is mandatory:

- `approved`: available for automatic selection.
- `suspended`: documented but not selectable unless the user explicitly says to try it.
- `disabled`: not selectable; old references must be migrated.

## Editing Rules

When adding a channel:

- Add a `tools` record with `status`, `channel`, `best_for`, `inputs`, `outputs`, `env`, `limits`, `pitfalls`, `qa`, and `fallback`.
- Env entries must list variable names only. Do not write secret values into the registry, examples, capsules, plans, or logs; follow [env-secrets.md](env-secrets.md).
- Add or update `engine_decision` rules so the planner knows when to choose it.
- Add or update `tool_chain_patterns` if it changes the production DAG.
- Add a runnable command or wrapper snippet in `references/tool-recipes.md`.
- Add failure modes and delivery checks in `references/assembly-qc-pitfalls.md`.
- Keep fallbacks inside tools currently marked `approved`.

When removing a channel:

- Change `status` to `disabled` or remove it from approved sections.
- Remove it from `engine_decision` choices and fallbacks.
- Remove or mark obsolete any recipe that calls it.
- Add migration guidance to the replacement approved channel.
- Check capsules that reference it and either migrate `config` or mark the capsule stale.

When temporarily pausing a channel:

- Set `status` to `suspended`.
- State whether manual retry is allowed.
- State the replacement route.
- Keep it out of automatic fallback choices.

## Capsule Compatibility

Treat local capsule `config` as verified production knowledge, but filter it through the active policy:

- If a capsule's `image_engine`, `video_engine`, `tts_provider`, `tts_voice`, BGM, or volume settings use approved tools, preserve them exactly.
- If a capsule points to a disabled tool, do not run it blindly. Migrate the capsule parameters or report the blocker.
- If a capsule's execution mode is `local_script`, the local script owns the pipeline, but final QA and artifact rules still apply.
- If a capsule's execution mode is `preset`, use its defaults as constraints while keeping the agent in the loop for scene inspection and retries.

## Decision Table Template

Use a compact table when explaining or editing the active policy:

| Need | Preferred | Backup | Disabled/avoid |
|---|---|---|---|
| Realistic image frame | `GptImage2Tool` | user-approved image tool | disabled image tools |
| Image-to-video | `GrokVideoGeneratorTool` | user-approved video tool | disabled video tools |
| Action transfer | `ActionImitateTool` | `WanMultiPersonActionImitateTool` | generic I2V |
| Lip sync | `InfiniteTalkV2VAPI` | user-approved lip-sync tool | generic scene generation |
| Chinese TTS | `DoubaoTTSTool` | `TextToSpeechTool` | voice cloning unless requested |
| Generated BGM/music | `UniversalMusicGenerationTool` with Suno | user-approved local/stock music | cloud/URL-only assets |

Update this table when the user's channel set changes.

## User-Owned Channels

If the user provides their own channel, do not assume it behaves like Juling or RunningHub. Capture:

- provider/channel name
- tool class, wrapper path, CLI command, or API adapter
- input types and max file limits
- duration/aspect-ratio support
- credential/env var names
- moderation/safety constraints
- expected output path or URL shape
- watermark/audio/text behavior
- retry limits, cost constraints, and rate limits
- required QA checks

Approve it only for the use cases it has proven. For unproven routes, mark it `suspended` until a first-scene test passes.

## Safe Fallback Principle

Fallbacks are policy-bound. A failed approved tool can fall back only to:

- another tool currently marked `approved`
- non-generative editing from already approved/generated/user-supplied material
- a reported blocker

Never silently use a disabled or unknown channel because it is available in the codebase.
