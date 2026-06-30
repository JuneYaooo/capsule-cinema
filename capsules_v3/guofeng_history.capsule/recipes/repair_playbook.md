# Repair Playbook

## known_pitfalls

- Over-realistic lighting turns the result into a costume drama instead of ink guoman.
- Historical explainers drift into chronology unless the script locks one conflict and one reversal.
- Generated Chinese text on scrolls or plaques often becomes unreadable; avoid relying on it for meaning.
- Handheld books, scrolls, and handoff actions are unstable in image-to-video and should be minimized.
- Fixing narration gaps by padding short per-scene TTS clips creates dead air; use one continuous narration track and cut video to it instead.
- Cutting one validated source video into many story beats can pass timing QA while failing visual variety; each story beat needs its own first frame or source clip.
- A video made only from still images plus ffmpeg zoompan can pass technical duration checks but fail audience expectations for motion; treat it as preview-only.
- Cutting a continuous narration into equal-length visual slots makes the picture lag behind the spoken meaning; historical explainers need a semantic beat map tied to the actual TTS timeline.
- Generating each first frame independently without a character bible causes Yang Zhen and Wang Mi to drift in age, clothing, face, and posture across scenes.
- Over-locking a reference sheet makes every storyboard frame repeat the same full-body or front-facing pose; use the sheet for identity continuity, not as a pose/layout template.
