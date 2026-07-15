# Storyboard and Shot Craft

Good video output depends more on planning than on model retries. Plan what the viewer experiences, then pick tools.

## Storyboard Shape

Every scene needs:

- `id`: `s01`, `s02`, ...
- `narration`: TTS text, if any
- `description`: human-readable shot intent
- `duration`: rough target, later replaced by measured audio
- `image_prompt`: frame-zero visual state
- `video_prompt`: motion from that frame-zero state
- `steps`: approved image/video tool calls

Useful top-level planning fields:

- `title`, `summary`, `theme`, `tone`, `target_audience`
- `aspect_ratio`, `platform`, `language`
- `voice_selection`: provider, voice, speed, volume
- `music_selection`: BGM style, intensity, volume
- `reference_design`: character/style/reference IDs

Useful scene metadata:

- `emotion`, `transition`, `camera_movement`
- `needs_reference`, `reference_ids`
- `video_generation_type`: `image_to_video`, `text_to_video`, `digital_human`, `action_imitate`, or policy-approved custom values

For most short videos:

```text
scene frame image -> image_to_video clip -> measured trim -> concat -> BGM/subtitles
```

## Scene Count

Do not turn every analyzed reference-video segment into a generated scene. Merge continuous action.

Merge when:

- same subject, same place, same physical action
- camera angle changes can be described inside one timeline prompt
- the viewer would not perceive a true scene change

Split when:

- subject changes
- location changes
- viewpoint jumps too far to be a continuous move
- narration topic changes enough that replacement/regeneration should be independent

Rule of thumb: scene count equals true jump cuts plus one, not the number of analysis rows.

## Duration

Planning estimate:

```text
duration ~= Chinese character count / (4 * tts_speed) + 0.5 to 1.0s
```

After TTS, `ffprobe` duration is authoritative. Align scene video to measured audio duration, allowing only small technical tolerance; do not create frozen tails or empty silent tails.

Engine choices by duration:

- `<=5s`: one 5s clip
- `5-10s`: one 10s clip
- `10-15s`: split by meaning unless an approved, registered long-clip tool is available
- `>15s`: split narration by meaning, not by fixed time

## Image Prompt

Image prompt describes the first frame. Put composition first.

Structure:

```text
shot size + camera angle + subject pose/action, subject anchor, environment and lighting, style
```

Rules:

- Do not request rendered text, captions, UI labels, subtitles, question marks, or decorative symbols unless the whole video is graphic design.
- Keep backgrounds clean. Avoid unnecessary cyberpunk, neon, HUD, abstract geometry, sparkles, pop-art effects, and random icons.
- For one persistent character, define a compact anchor and reuse it. With reference images, 60-80 Chinese characters is enough.
- For multiple characters in one shot, use short anchors, around 20-30 characters per person.
- For distant tiny figures, skip detailed face/wardrobe anchors; they cause oversized faces and distortions.

Public default: use `VolcengineImageGeneratorTool`. Additional local engines
must come from the effective local overlay registry.

## Video Prompt

Video prompt describes motion from the generated frame.

Start with subject action, then mouth/action details, then environment, then camera. If the prompt starts with camera movement, the character often freezes.

Good structure:

```text
subject action + body motion, mouth/lips if speaking, environment response, camera movement, quality/style
```

Limit to 2-3 core actions per clip. Too many simultaneous actions causes partial execution.

## Timeline Prompt

For approved video tools that respond well to time-coded prompts, use compact timeline prompts for high-density clips:

```text
[00:00 - 00:03] CU: subject notices the object, eyes widen, hand reaches forward
[00:03 - 00:08] MS: subject opens it slowly, steam rises, background reacts
[00:08 - 00:10] ECU: subject smiles in relief, camera pushes in
```

Rules:

- Segments must sum to the requested clip duration.
- Use flexible lengths based on content rhythm, not fixed equal chunks.
- Use shot sizes: `ECU`, `CU`, `MS`, `WS`, `EWS`.
- Neighboring segments need visible change in angle, scale, action, or emotional state.

Do not use timeline prompts when strict audio sync inside a clip is required. For narrated videos, TTS timing and post-trim should drive sync.

## Continuity Tricks

### Fixed-Camera State Inheritance

For food, ASMR, craft, tabletop demos, or any stateful scene:

1. Generate first frame.
2. Generate first clip.
3. Extract tail frame.
4. Use tail frame as next clip's start/reference.
5. Prompt the exact remaining state: what has changed, what remains, what happens next.

This prevents continuity resets.

### Image Is Start, Video Is Process

When the hook is transformation, the image prompt should show the "before" state and the video prompt should carry the transformation.

Bad: image already contains the final transformed result.
Good: image is the untouched object; video prompt describes the reveal/change.

### Three-Track Manga/Drama Pattern

For dramatic or comic story videos:

- `narration_action`: compact timeline-like motion prompt, 1 clip with 3-5 internal beats when the selected tool supports it.
- `dialogue`: close/medium character shots with visible mouth movement, then TTS/lip-sync if needed.
- `reaction`: 1.0-1.5s still or short motion shot, strong facial expression, no wasted generation.

This reduces AI drift and improves pacing.

## Reference Video Remakes

Analyze before remake:

- hook type
- what mechanism creates retention
- which details are essential and which are surface styling
- shot duration distribution
- whether scenes should be merged

Reality-discovery hooks are often not directly remakeable. Turn them into "AI fills the blank" or "AI imagines..." hooks instead.

For emotional triggers involving living beings, keep the trigger real and tactile. Do not replace a soft animal/baby/face with a toy/model/cartoon unless the user asked for that style.
