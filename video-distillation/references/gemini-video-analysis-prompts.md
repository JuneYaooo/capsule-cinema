# Gemini Video Analysis Prompts

## Full Video Review

Analyze this short-form video as a deep video-distillation sample. Return structured Markdown or JSON with:

1. duration, aspect ratio, language, visible format;
2. first frame, 0-1s, 1-3s, 3-5s, 5-8s;
3. full spoken/subtitle/OCR transcript if readable or audible;
4. timeline beats: hook, setup, promise, proof/demo/story progression, turning point, payoff, CTA, ending;
5. visual style: medium, character/face use, scene density, palette, typography, subtitles, overlays, UI, proof devices;
6. motion/editing: camera movement, cut rhythm, transition style, animation style, text motion, zooms, arrows, caption timing;
7. audio: voice, TTS-likeness, BGM role, SFX role, silence, rhythm authority;
8. production-route inference: AI video, AI image, digital human, TTS, human voiceover, screen recording, card rendering, motion graphics, subtitle burn-in, BGM, SFX, manual editing;
9. observed vs inferred vs recommended, with evidence timestamps.

Never assert the source used a production tool unless visible evidence supports it. Mark uncertain claims as uncertain.

## Keyframe Review

Given keyframes and a contact sheet, analyze frame grammar, visible text, composition, proof devices, typography, palette, character presence, motion implications, and what each frame contributes to retention.

## Copy And Transcript Review

Analyze title, caption, hashtags, visible text, spoken opening, transcript beats, CTA, risk claims, and reusable copy mechanism. Do not copy the source script as a template.
