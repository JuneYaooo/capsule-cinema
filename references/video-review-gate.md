# Video Review Gate

Use this before delivering any generated or edited video. The goal is to prevent low-quality output from reaching the user.

## Review Stages

### 1. Preflight Gate

Before generation or assembly:

- Confirm aspect ratio, target platform, language, audience, duration, and audio strategy.
- Confirm the delivery promise: motion-led, source-led, TTS-led explainer, reference remake, capsule preset, or specialized route.
- Check that selected tools are approved by the active channel policy.
- Check prompts do not ask image/video models to render Chinese subtitles, titles, UI labels, or dense text.
- For reference remakes, identify which traits must be preserved and which surface details can change.
- For source-led edits, verify source media has been probed/sampled/transcribed when relevant before planning.
- For capsule runs, verify the active capsule package contract has been inspected and stale/disabled channels are not being executed blindly.
- For specialized routes, verify the selected registered tool or local-script capsule can actually satisfy the route.
- For TTS-led videos, estimate narration length and make sure scene count can fit the audio.

Fail preflight if the plan depends on a disabled channel, unknown secret, impossible duration, unreviewed source/reference assumption, or a generic workflow pretending to satisfy a specialized promise.

### 2. First-Scene Gate

For new AI videos, generate and inspect one representative hard scene before batching.

Check:

- subject identity and style match the plan
- frame has the requested orientation and useful composition
- no garbled text, watermark, broken hands/face, irrelevant icons, or strange background artifacts
- motion starts from the intended first-frame state
- native generated audio is either intentionally used or will be muted
- scene can be trimmed to TTS duration without losing the main action

If the first hard scene fails twice with revised prompts, revisit tool choice, channel policy, storyboard, or art direction before continuing.

### 3. Batch Gate

During multi-scene production:

- Inspect at least every generated scene once before final assembly.
- For continuity-heavy content, extract tail frames and compare state inheritance.
- Check character anchors stay stable across scenes.
- Stop if the same defect appears in two consecutive scenes; fix the prompt/tool strategy instead of generating more.
- Preserve intermediate clean assets for rerendering: original images, generated clips, TTS audio, and `assembly/01_concat.mp4`.

### 4. Final Delivery Gate

Run this after assembly and before telling the user the video is done:

1. MP4 exists and `ffprobe` can read duration, resolution, streams, and codec.
2. Aspect ratio and resolution match the requested platform.
3. Duration is plausible for the script and not abruptly cut off.
4. Audio exists when narration/BGM is expected.
5. For narrated videos, final video duration matches narration duration within normal tolerance unless an intentional silent intro/outro/end card was requested.
6. Voice is intelligible; BGM does not overpower narration.
7. For presenter or speech-sync videos, mouth movement, facial expression, hand/body rhythm, and speech timing stay aligned.
8. If a visible person or avatar speaks, the voice should match the apparent gender, age range, and role unless the mismatch is intentional.
9. Subtitles and on-screen text are readable, synced, within safe area, proportionate to the frame, naturally wrapped, free of mojibake/stray characters, and not double-burned.
10. Visual scan catches black frames, frozen frames, watermarks, deformation, irrelevant effects, flicker, or continuity breaks.
11. Generated clips with accidental English/native audio are muted or replaced.
12. `artifact_manifest.json` contains final video and copywriting.
13. Generated runs include prompt/parameter snapshots under `prompts/`, and `artifact_manifest.json` lists them as `storyboard_prompt`.
14. `compliance_report.json` passes if present.
15. Final artifact path is present, readable, and listed in the manifest.
16. Delivery promise is honored. A playable file is not complete if it violates the approved route.
17. Serious runs include or update `work/decision_log.json` when provider selection, capsule override, fallback, user approval, or QA repair materially affected the result.

Promise-specific checks:

| Promise | Delivery check |
|---|---|
| `motion_led` | Key beats use real generated/source motion or intentional animation. Still-led fallback is blocked unless explicitly approved. |
| `source_led` | Source media was inspected and materially used. The output does not invent source content or replace the source with unrelated generated filler. |
| `tts_led_explainer` | TTS timing is the master. Visual duration, subtitles, and BGM serve the narration without freeze tails or silent tails. |
| `reference_remake` | Reference traits were analyzed, preserved only where approved, and transformed enough to avoid a carbon copy. |
| `capsule_preset` | Capsule quality rules, local assets, and configured defaults were applied or explicitly migrated. |
| `specialized_route` | The result came from the registered specialized tool or capsule local script. Generic image-to-video output can only be marked preview unless the user approved downgrade. |

For local runs, create a machine-readable QA report whenever possible:

```bash
python "scripts/local_video_qa.py" \
  --run-dir "$RUN_ROOT" \
  --aspect-ratio "9:16" \
  --expect-audio \
  --require-prompts \
  --output "$RUN_ROOT/qa/local_video_qa.json"
```

For presenter/speech-sync videos, videos with visible subtitles or on-screen text, and videos where a visible person/avatar speaks, also run the runtime scorer with multimodal video review when available:

```bash
PYTHONPATH=lib python3.12 scripts/score_video_quality.py \
  --run-dir "$RUN_ROOT" \
  --capsule digital_human \
  --aspect-ratio "9:16" \
  --multimodal-review \
  --multimodal-provider gemini3
```

If the multimodal review is unavailable, do not treat required speech-sync, subtitle/text layout, or voice-character gates as passed.

If the report fails, fix the blocker or record why the run is not deliverable. Do not record the run as `success`.

## Blockers vs Warnings

Do not deliver with blockers. Fix or report the blocker.

Blockers:

- black or blank final video
- missing expected audio
- narrated video shorter than audio, causing freeze/stutter or abrupt cutoff
- narrated video longer than audio, leaving accidental empty/silent visual tail
- audio/video desync obvious to a normal viewer
- presenter or speech-sync video where audio continues while the face/body freezes, stalls, or loops unnaturally
- visible person/avatar voice obviously mismatches the apparent gender, age range, or role
- BGM overwhelms narration
- subtitles or on-screen text unreadable, outside safe area, clipped, overflowing, badly wrapped, too small, disproportionate, mojibake, wrong language, or double-burned
- wrong aspect ratio or severe crop of subject
- major face/body/hand deformation in a main subject
- character identity changes in continuity-dependent scenes
- garbled rendered text from the image/video model
- visible watermark or unintended platform/logo overlay
- final file cannot be opened or user cannot access it
- failed compliance report
- disabled/unapproved channel was used without explicit user override
- delivery promise was silently downgraded
- source-led output does not use or inspect the source material
- reference remake was planned from guesses rather than source/reference analysis
- specialized route was replaced by generic image-to-video without explicit approval
- serious fallback occurred but was not recorded in notes, session memory, or `work/decision_log.json`

Warnings:

- minor background artifacts
- slight lip-sync mismatch in non-close-up shots
- small timing drift under half a second when subtitles remain understandable
- mild style variation between scenes that does not affect the story
- minor compression softness

Warnings should be fixed when practical. If left in, mention residual risk only when it affects the user's decision.

## Common Low-Quality Problems

| Problem | Detection | Prevention/Fix |
|---|---|---|
| Black frames or frozen video | contact sheet or quick playback | re-encode source, regenerate bad clip, avoid broken concat |
| Wrong crop/aspect | `ffprobe` width/height and visual scan | regenerate or crop/pad to requested ratio |
| Character drift | compare scene thumbnails | use compact anchor, one canonical reference, fewer independent scenes |
| State reset between clips | object returns to earlier state | tail-frame inheritance and exact state prompts |
| Garbled Chinese text | visual scan | remove text from generation prompt, add text in post |
| English audio in clip | listen or run language check | mute generated clip, use approved TTS |
| Video shorter than narration | duration comparison / frozen tail | generate longer motion, split narration, or add intentional motion; no accidental freeze |
| Video longer than narration | duration comparison / silent tail | trim to narration endpoint or add intentional covered outro |
| Speech and picture out of sync | watch mouth, facial expression, gestures, and subtitle timing | regenerate the sync pass, use clearer face/audio, or reassemble against measured audio |
| Audio continues but presenter freezes | playback plus contact sheet / freezedetect | regenerate the clip or replace the frozen section; do not deliver as a talking video |
| Voice does not match character | multimodal review or human playback | pick a matching TTS voice, change the avatar/role, or state the mismatch as intentional |
| BGM too loud | listen and loudness check | lower BGM, use `amix normalize=0`, adjust TTS API volume |
| Subtitle/text layout problem | multimodal review, contact sheet, or visual scan | shorten lines, use safe-area margins, adjust font size, remove stray characters, and re-render captions |
| Lip sync poor | close-up mouth mismatch | use clearer face crop, mute source first, regenerate/lip-sync again |
| Stutter after concat | playback / frame-rate mismatch | re-encode common fps/codec; avoid forcing bad frame drops |
| Low-res final | `ffprobe` resolution | super-res or render/export at target resolution |
| Enhancement changed timing/resolution | compare before/after `ffprobe` | do not deliver as final; reattach original audio or rerender to match the audio master |
| Artifact hard to find | manifest/local path check | write manifest and verify the final local path exists |

## Useful Checks

Technical probe:

```bash
ffprobe -v error -show_entries format=duration:stream=codec_type,width,height,r_frame_rate \
  -of json final.mp4
```

Contact sheet for visual scan:

```bash
ffmpeg -y -i final.mp4 -vf "fps=1,scale=240:-1,tile=5x6" review_contact_sheet.jpg
```

Audio stream check:

```bash
ffprobe -v error -select_streams a -show_entries stream=codec_type \
  -of default=noprint_wrappers=1 final.mp4
```

Narration/video duration comparison:

```bash
ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 final.mp4
ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 narration.mp3
```

Do not paste command output containing secrets or private signed URLs into the final user message.
