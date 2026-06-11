# Production Patterns

Use these patterns as reusable starting points. Always filter tools through the active channel policy; if a listed pattern would require a disabled channel, migrate it to an approved route.

## Pattern Selection

| Video type | Default chain | Notes |
|---|---|---|
| Voiceover / explainer | per scene: image -> video; assembly: TTS -> concat -> BGM -> subtitles -> copywriting | Most common vertical short-video route |
| Silent visual / ASMR | per scene: image -> video; assembly: concat -> BGM -> copywriting | No TTS/subtitles unless requested |
| Music MV / mood montage | image/video scenes -> beat-aware concat -> BGM/music -> copywriting | Keep one subject/style through intro, verse, chorus, bridge |
| Digital human / lip sync | source image/video -> TTS -> mute source -> lip-sync -> assembly | Source face must be clear and close enough |
| Action transfer | local reference video + character image -> action imitation -> BGM/copywriting | Usually one or few scenes, not many generated shots |
| Product/tutorial | problem -> interface/process -> result -> CTA | Use real UI/material when supplied; avoid unreadable generated UI text |
| News/data card | card-like scene images -> short motion -> TTS/subtitles | Add text in post or code render; do not ask image model to draw dense text |
| Code-rendered graphics | HyperFrames/local render -> TTS/BGM/subtitles/copywriting | Use for exact text, charts, UI motion, title cards; not a third-party generation channel |
| Story/drama | 5-8 narrative beats with consistent character anchors | Split by true story beat, not every sentence |
| Culture/travel/vlog | place/time/object anchors -> atmospheric scene sequence | Keep geography, season, props, and color language consistent |

## Voiceover / Explainer

Good for knowledge, news, commentary, reviews, and short explainers.

Rules:

- TTS duration drives scene duration.
- Each narration scene needs enough motion to cover audio without frozen frames.
- Use subtitles by default for Chinese short-video delivery.
- Keep BGM low under narration.
- Write copywriting alongside final video.

## Silent Visual / ASMR

Good for texture, craft, nature, food, healing, or pure visual loops.

Rules:

- No TTS unless requested.
- Use tighter macro prompts and tactile details.
- Use real or generated foley/BGM carefully; do not overpower the visual rhythm.
- Stateful actions need tail-frame inheritance.

## Music MV / Mood Montage

Good for emotional montage or music-led visuals.

Rules:

- Keep a stable subject, outfit, color palette, or symbolic object.
- Plan visual rhythm around musical sections, not fixed equal scene durations.
- Avoid excessive plot details; the emotional arc carries retention.

## Digital Human / Lip Sync

Good for presenter, avatar, or talking-head content.

Rules:

- Generate or choose a clear face before lip sync.
- Mute source video before applying TTS audio.
- Avoid tiny faces and extreme side profiles.
- Review mouth movement and audio sync as blockers for close-ups.

## Action Transfer

Good for dance, exercise, sports, martial arts, or movement imitation.

Rules:

- Download reference video locally first; do not pass social URLs directly.
- Check single-person vs multi-person before choosing the tool.
- Compress or trim reference video if upload limits fail.
- Keep character image clear, full body visible, and matching output aspect.

## Product / Tutorial / Step Card

Good for product demos, efficiency tools, workflows, or operational explainers.

Rules:

- Use real UI screenshots or supplied assets when available.
- Generated UI text is unreliable; add labels and captions in post.
- One screen should carry one clear step or selling point.
- Prefer predictable before -> action -> result structure.

## Code-Rendered Graphics

Good for exact typography, data cards, charts, UI motion, transitions, and title sequences.

Rules:

- Treat local code rendering as a separate production mode, not as an external image/video generation channel.
- Use HyperFrames patterns when available; invoke the dedicated HyperFrames skill for implementation details.
- Keep TTS, BGM, subtitles, manifest, and final QA under this video-production workflow.
- Use this instead of image/video models when text must be exact or charts must be legible.
- Do not use code rendering to bypass an active channel policy; it must be allowed by the project/user policy.

## Story / Drama

Good for short narrative, manga/drama, emotional conflict, or mini story.

Rules:

- Keep 5-8 core beats unless the user asks for a longer episode.
- Use compact anchors for recurring characters.
- Separate dialogue, reaction, and action beats when lip sync or emotion matters.
- Avoid changing location/viewpoint without story reason.

## Reference Remake Pattern

When remaking a reference video:

1. Analyze hook, pacing, shot durations, emotional trigger, and essential mechanism.
2. Separate essence from surface styling.
3. Merge continuous actions into fewer generated scenes.
4. Rebuild with approved channels and user-confirmed constraints.
5. Keep real/tactile triggers when realism is the source of retention.

Do not generate blindly from a reference link without analysis.
