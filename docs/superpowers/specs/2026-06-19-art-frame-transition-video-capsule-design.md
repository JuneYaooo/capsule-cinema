# Art Frame Transition Video Capsule Design

## Goal

Build a reusable local-script capsule that turns user text and optional reference images into an artistic first/last-frame Veo 3.1 transition video with tasteful subtitles, Veo-native object/environment sound effects, and a subtle external BGM bed.

## Capsule Identity

- Name: `art_frame_transition_video`
- Display name: `艺术图像首尾帧动态短片`
- Execution mode: `local_script`
- Status after implementation: `active` only after smoke test and local QA pass
- Package target: `capsules/art_frame_transition_video.capsule.zip`
- Primary script target: `capsules/art_frame_transition_video/run_art_frame_transition_video.py`

This capsule is style-adaptive. It must not assume guofeng by default. It should infer the visual language from user input and reference images, then choose a fitting direction: classical painting, oil painting, ink wash, printmaking, photography, modern art, artifact/still life, museum display, paper relief, sculptural/3D depth, or another style clearly supported by the source material.

## User Inputs

Required:

- `prompt`: user description, intent, or desired transformation.

Optional:

- `reference_images`: local image paths. One or more images may be provided.
- `aspect_ratio`: default `9:16`; allowed `9:16`, `16:9`, `1:1`.
- `target_duration`: default `8`, because Veo 3.1 first/last-frame output is currently 8 seconds.
- `mood`: `auto`, `comfortable`, `novel`; default `auto`.
- `style_hint`: optional user style direction, such as `油画`, `国风`, `现代艺术`, `摄影`, `博物馆展陈`.
- `caption_language`: default `zh-CN`.
- `bgm_query`: optional user-provided BGM search direction.

The script should reject runs with neither prompt nor reference images.

## Tool Policy

Use approved local runtime tools only:

- Image generation and reference image processing: `Seedream5ImageGeneratorTool` or `GptImage2Tool` through Juling.
- First/last-frame video: `Veo31VideoGeneratorTool` through Juling.
- Video assembly: local `ffmpeg`.
- BGM retrieval: online search/download only from sources that appear reusable for local production, then store as a local file. The script must record source name and license note when available, but must not store signed or temporary URLs in manifest files.

Veo prompt must ask for native sound effects that match the visual transformation, but must explicitly ask for no background music. External BGM is added in post so the mix is controllable.

## Reference Image Decision

The script creates a `frame_decision.json` artifact with these fields:

- `reference_images`: local paths and image metadata.
- `visual_analysis`: concise subject/style/quality notes.
- `anchor_frame`: `start`, `end`, or `unknown`.
- `start_frame_strategy`: `use_reference`, `derive_from_reference`, `generate_from_text`, or `select_from_inputs`.
- `end_frame_strategy`: `use_reference`, `derive_from_reference`, `generate_from_text`, or `select_from_inputs`.
- `image_processing_actions`: planned preprocessing steps.
- `risk_notes`: uncertainty notes, especially when artwork identity is not verified.

Decision rules:

1. If a reference image appears to be a complete, full, peak, finished, or visually rich state, treat it as the likely end frame.
2. If a reference image appears to be an empty, initial, minimal, dormant, closed, or before state, treat it as the likely start frame.
3. If exactly two images are provided and one is visually simpler while the other is richer, use them as start and end respectively.
4. If exactly one image is provided and it is not obviously an initial state, preserve it as the anchor end frame and derive a consistent start frame from it.
5. If no image is provided, generate both start and end frames from the user prompt.
6. If user instructions explicitly mark a frame role, the user instruction wins unless it conflicts with missing files or unsafe content.

## Image Processing

The script should decide whether each frame needs preprocessing before Veo:

- Crop or pad to requested aspect ratio.
- Resize/compress to Veo-friendly JPEG input, default `720x1280` for `9:16`.
- Improve clarity when the image is soft, low resolution, or noisy.
- Remove visible AI badges or watermarks only from generated local intermediate frames, not from third-party copyrighted source images.
- Derive a matching start or end frame using reference image generation when the two frames are inconsistent.
- Add subtle spatial depth when useful: shallow depth of field, layered paper relief, sculptural lighting, exhibit-style side light, material texture, or parallax-ready separation.

The 3D feeling must remain tasteful. Avoid plastic-looking 3D, neon effects, cheap fantasy glow, over-sharpening, or style drift away from the source.

## Motion Direction

The script chooses one of three routes:

1. `comfortable_immersive`: calm, beautiful, emotionally comfortable. Use slow light movement, paper texture, gentle growth, clouds, water, brush bloom, fabric movement, or object awakening.
2. `novel_attention`: visually surprising but still artistic. Use restrained impossible motion, a painting element leaving the canvas, pigment becoming space, still objects revealing hidden life, or time flowing through the artwork.
3. `famous_art_deconstruction`: for likely famous artworks or historically meaningful images. Use a knowledge hook first, then animate key motifs in a respectful, artful way.

Default route selection:

- Use `famous_art_deconstruction` when the user names a known artwork, artist, museum, dynasty, school, or when the visual analysis confidently identifies a notable artwork.
- Use `comfortable_immersive` for landscapes, guofeng, still life, flowers, artifacts, quiet interiors, and healing scenes.
- Use `novel_attention` for modern art, surreal images, strong symbols, unusual objects, or when the user asks for attention-grabbing novelty.
- If mood is `comfortable` or `novel`, respect it.

## Caption Strategy

No voiceover by default. Captions are not word-for-word narration; they are short art-label style lines.

Caption structure:

1. Hook: famous-art identity, historical origin, collection clue, visual shock, or a strong interpretive line.
2. Context: what the image or artwork depicts.
3. Distinction: what makes it special.
4. Emotional ending: a blessing, philosophical reflection, or memorable meaning for the viewer.

Examples of tone, not fixed text:

- `这幅画最动人的地方，不是热闹，而是时间慢了下来。`
- `它把一瞬间的花影，留成了可以反复靠近的风景。`
- `愿你也能在流动的日子里，留住一处清明。`

Famous artwork rule:

- If identity is verified by user input or reliable local/online source, the hook may mention title, artist, museum, period, or art-historical status.
- If identity is uncertain, do not invent facts. Use cautious phrasing such as `从画面气质看` or `这类作品最特别的地方`.
- Captions must not contain internal production wording such as draft, v1, source, repair, revision, or QA.

Subtitle visual style:

- Choose font color from the image palette.
- Use low-saturation ivory, warm gold, ink black, museum white, muted bronze, or restrained accent colors.
- Use subtle shadow or outline only for readability.
- Avoid blocking the subject.
- Keep text short and readable on mobile.
- Use positions that match the composition: lower third for quiet scenes, side label for museum/exhibit scenes, top hook only when it does not compete with the artwork.

## BGM And Sound

The final audio mix contains:

- Veo-native audio track when available, because it can include object/environment transformation sound effects.
- External BGM at low volume as an atmosphere bed.

Veo prompt audio rule:

- Ask for subtle scene sound effects: paper unfolding, brush/pigment bloom, leaves growing, gallery ambience, light shimmer, water ripple, ceramic resonance, or other subject-specific sounds.
- Explicitly say no background music.
- Avoid spoken dialogue unless the user explicitly asks.

BGM rule:

- Search online for a suitable subtle instrumental track when no local BGM is supplied.
- Prefer public-domain, royalty-free, Creative Commons, or otherwise clearly reusable sources.
- Record local BGM file path, source name, and license note in `bgm_selection.json`.
- Do not write signed URLs, temporary URLs, API keys, or cookies into any artifact.
- Mix BGM below native sound effects; default BGM volume target is subtle, around `0.06-0.12` relative mix depending on source loudness.

## Output Contract

Every run must produce a run directory under `output/art_frame_transition_video/<timestamp_slug>/` with:

- `inputs/` copied input references or an input manifest.
- `analysis/frame_decision.json`.
- `prompts/` prompt snapshots for image generation, Veo, caption writing, and BGM selection.
- `frames/start_frame.png` and `frames/end_frame.png`.
- `frames/veo_inputs/start.jpg` and `frames/veo_inputs/end.jpg`.
- `videos/veo_raw.mp4`.
- `audio/bgm.*` when BGM is used.
- `final/final_video.mp4`.
- `qa/contact_sheet.jpg`.
- `qa/local_video_qa.json`.
- `artifact_manifest.json`.

The manifest must identify:

- final video
- raw Veo video
- start/end frames
- caption file
- BGM local path and license note
- prompt index
- QA artifacts

## Error Handling

- Missing input image: fail with a clear path error.
- No prompt and no images: fail before any API call.
- Image generation failure: write error summary, keep any completed artifacts, and return non-zero.
- Veo generation failure: keep frame artifacts and prompt payloads for retry.
- BGM search/download failure: continue with Veo native audio only, mark BGM status as unavailable, unless the user explicitly requires BGM.
- Caption render failure: do not deliver a silent uncaptained final as success; keep raw video and report the failure.

## Quality Gates

Required checks:

- Final video exists.
- Final video has the requested aspect ratio.
- Final video duration is close to target duration.
- Final video has an audio track unless user disables all audio.
- Captions are readable and do not cover the main subject.
- Start/end frames are visually consistent.
- Transformation is either comfortable/immersive or novel/attention-grabbing, but not random.
- The result keeps an artistic feel.
- If famous artwork facts are included, their source must be recorded or user-provided.
- No secrets, signed URLs, or remote cloud URLs are stored in manifest files.

## Testing Plan

Implementation should add focused tests for:

- Reference image role decisions.
- Image preprocessing decision output.
- Caption structure and cautious famous-art wording.
- Veo prompt audio rule: sound effects requested, background music forbidden.
- BGM metadata redaction.
- Manifest output shape.
- Capsule package manifest includes local script and no remote URLs.

## README Example Scope

README usage examples should stay simple:

1. Text-only:
   `做一段关于一只空花瓶慢慢长出端午花草的艺术短片`
2. One reference image:
   `参考这张画，做一个从静止画面到花影流动的艺术视频`
3. Two reference images:
   `第一张做首帧，第二张做尾帧，中间要舒适但有一点意外感`

The README should not expose provider tokens, cloud URLs, or long internal design language.
