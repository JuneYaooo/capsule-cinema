# Assembly, QA, and Pitfalls

## Assembly Order

Standard order:

```text
TTS -> align scene videos to measured audio duration -> concat -> BGM -> subtitles -> final mp4 + txt
```

`assembly/01_concat.mp4` is the clean base with no final subtitle/BGM burn. Preserve it.

For narrated videos, audio duration is the timing authority. Unless the user explicitly asks for a silent intro, outro, title hold, or end card, final video and narration should end together. A small technical tolerance is acceptable, but obvious frozen last frames, stutter, or empty/silent visual tails are blockers.

For presenter or speech-sync videos, matching total duration is not enough. The mouth, face, hands, and body rhythm must stay aligned with the speech. If the audio keeps playing while the face/body freezes, stalls, or loops unnaturally, treat it as a blocker.

## Audio Rules

- `tts_volume` / MiniMax `vol`: API-side TTS loudness.
- `voice_volume`: ffmpeg-side gain during video/audio assembly.
- Keep `voice_volume` around `0.5-2.0`. Higher can clip even if TTS sounded quiet.
- MiniMax often needs API `vol` around `2.0-2.5`.
- Direct Doubao tools use `speed_ratio`, not MiniMax `speed`; the current API maps
  `0.5-2.0` to the official `speech_rate=-50..100` range.
- For Doubao Speech, use only speakers enabled for the configured
  `X-Api-Resource-Id`; a 2.0 voice/resource mismatch is a request blocker.
- Streaming `wav` is discouraged by the provider. Prefer `mp3` for saved
  narration or `pcm` for latency-sensitive streaming, then verify the file.
- With narration, start BGM around `0.05-0.12`. Suspense/serious narration often needs `0.03-0.08`.
- Without narration, BGM can be `0.3-0.5`.
- Use `amix=...:normalize=0` when preserving explicit gains.

Always measure actual duration:

```bash
ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 audio.mp3
```

Compare final video and narration duration before delivery:

```bash
ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 final.mp4
ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 narration.mp3
```

Default tolerance for narrated videos: keep absolute final video/audio duration drift under about `0.3s`. If a deliberate intro/outro/end-card needs more time, document it in the plan and keep it visually meaningful, not a blank or frozen tail.

## Subtitle Rules

- Chinese subtitles must go through ffmpeg drawtext with a Chinese font.
- Do not use English-only subtitle processors.
- Do not burn subtitles on a video that already has burned subtitles.
- Drawtext does not auto-wrap. Split lines manually.
- Vertical `9:16`: around 11-14 Chinese characters per line.
- Horizontal `16:9`: around 20-28 Chinese characters per line.
- The project font may only support Simplified Chinese; convert Traditional Chinese if boxes appear.
- Keep subtitles and lower-thirds inside the platform safe area; avoid bottom UI zones and cropped edges.
- Review burned subtitles for overflow, clipped glyphs, bad wrapping, stray punctuation, mojibake, too-small type, and text that visually dominates the subject.

## Concat and Trim

- Executor assembly should align scene video to measured audio duration, allowing only a small technical tolerance.
- If source video is shorter than its narration, do not rely on a frozen last frame. Generate a longer clip, split the narration, add an approved extra motion shot, or use deliberate Ken Burns motion from an approved image.
- If source video is longer than narration, trim it to the narration endpoint or add intentional audio/BGM coverage. Do not leave a silent visual tail by accident.
- Manual concat must trim explicitly.
- Re-encode concat when sources differ in fps, dimensions, codec, sample rate, or audio stream layout.
- Avoid forcing `-r 30` on 60fps sources; uneven frame drops cause stutter.
- Ensure every segment has an audio stream, even silent, when concat expects audio.

## Approved Fallbacks

If official Volcengine video generation fails:

- Retry once with shorter/clearer prompt.
- Retry the same official route with a shorter, clearer prompt or supported duration.
- Use Ken Burns from approved or user-supplied images for narration-heavy explainers.
- Use real material already supplied/downloaded by the user.

Do not fallback to disabled channels.

## Common Failure Modes

| Symptom | Likely cause | Fix |
|---|---|---|
| Unwanted generated audio | model-generated audio enabled | mute source and use approved TTS; inspect audio before delivery |
| Mouth/lip sync poor | face too small or source has original audio | crop/regen closer face; mute before lip sync |
| Speech and picture out of sync | sync pass drift, wrong audio offset, or source motion too short | regenerate the sync pass, use clearer face/audio, or reassemble against measured audio |
| Audio continues but presenter freezes | source video too short, frozen-frame padding, or concat/timing mismatch | regenerate longer motion or replace the frozen section; do not deliver as a presenter video |
| Visible speaker does not match voice | wrong TTS voice, reused avatar, or mismatched presenter role | choose a matching TTS voice, replace the avatar/role, or explicitly mark it as intentional before review |
| Scene resets object state | independent start frames | extract tail frame and inherit state |
| Character changes between scenes | anchor too vague or too long | compact stable anchor; use one canonical reference |
| Rendered Chinese text is garbled | image model asked to draw text | remove text from image prompt; add text in post |
| Subtitle boxes/mojibake | wrong font/tool | use project drawtext font path and Simplified Chinese |
| Subtitle overflow, bad wrap, or too-small type | line too long, missing safe-area rule, or fixed font size reused across formats | shorten lines, set safe margins, adjust font size per aspect ratio, and re-render captions |
| BGM overwhelms voice | BGM volume too high or normalize applied | lower BGM, `normalize=0`, check loudness |
| Final video shorter than narration | clip too short for TTS | regenerate longer clip, split scene, or add intentional motion; no frozen frame |
| Final video longer than narration | concat not trimmed or empty tail | trim to narration endpoint, add intentional outro audio, or remove tail |
| Final file exists but is hard to find | no manifest or inconsistent output path | write `artifact_manifest.json`, keep final files under the run root |
| RunningHub upload fails | file too large or wrong URL input | compress local file; upload local file, not social URL |
| Super-resolution output is smaller | enhancement wrapper used a long-edge cap lower than the source | set the cap >= source long edge; wrapper should reject accidental downscale unless explicitly allowed |
| Super-resolution changes duration/resolution | enhancement app rewrites media stream | compare source/result with `ffprobe`; for narrated videos reattach original audio and trim/pad to audio master, or block delivery |
| RunningHub logs expose remote URLs | wrapper logs upload/result URL | redact signed/private URLs; keep local path, task id/status, duration, and dimensions only |
| Unlisted cloud tool selected | stale capsule or local registry leak | replace with a public approved route or keep the capsule local-only |

## QA Gate

For full review stages and blocker/warning triage, also use [video-review-gate.md](video-review-gate.md).

Before delivery:

1. MP4 exists, size is reasonable, `ffprobe` can parse duration.
2. Resolution/aspect ratio matches request.
3. Audio stream exists if narration/BGM expected.
4. For narrated videos, final video duration matches narration duration within tolerance unless intentional silent intro/outro/end-card time is requested; for non-narrated videos, duration is at least 80% of target and not abruptly truncated.
5. Subtitles are readable, synced, safe-area compliant, proportionate, naturally wrapped, and not double-burned.
6. For presenter/speech-sync videos, mouth, face, hands/body rhythm, and audio timing align; the visible speaker's voice matches the character.
7. Visual scan catches black frames, frozen frames, deformation, irrelevant effects, or continuity breaks.
8. `artifact_manifest.json` includes `final_video` and copywriting.
9. Generated prompt/parameter snapshots exist under `prompts/` and are listed in `artifact_manifest.json` as `storyboard_prompt`.
10. `compliance_report.json` passes if present.
11. Final artifact path is present in `artifact_manifest.json`.

Delivery language should describe the video, duration, aspect ratio, major scenes, copywriting, and final local artifact path.
