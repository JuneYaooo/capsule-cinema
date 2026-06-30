# Legacy Notes

## assembly_rules

- Generate narration as one continuous full-track voiceover after the final script is approved; do not create separate padded TTS clips for each scene.
- Keep the narration at the capsule speed and use no per-scene audio padding. Cut visuals to narration instead of slowing the voice or inserting silence.
- When final audio is mixed, storyboard audio_path should point to the final aligned full-track audio used in the release video.

## character_continuity_rules

- Design a character bible before generating storyboard images. It must define Yang Zhen, Wang Mi, and recurring props/locations before the first scene image is made.
- Yang Zhen anchor: elderly Eastern Han scholar-official, lean face, gray-black long beard, calm severe eyes, dark ink official robe, black guan hat, restrained upright posture.
- Wang Mi anchor: younger county magistrate, mid-aged, narrower face, anxious respectful expression, lighter official robe, deferential posture, never visually merged with Yang Zhen.
- Create or select a canonical character reference sheet before story-frame generation, with front/three-quarter views and costume notes for Yang Zhen and Wang Mi.
- Every storyboard image prompt must reuse the relevant role anchor or the canonical character reference sheet; independent redesign of recurring characters is a release blocker.
- If a scene uses silhouettes or distant figures, the prompt must still preserve role identity through costume, posture, age, and relative placement.
- A canonical character reference sheet locks identity, not exact pose, action, camera angle, layout, or location; scene prompts should adapt the character to the current story beat.
- Side, back, three-quarter, distant, and silhouette views are allowed when the scene calls for them, as long as identity markers such as age, robe value, hat shape, beard length, posture, and relative role remain clear.
- Do not force full front-facing character views into every storyboard image. A beat may show a shoulder, back, partial figure, reflection, shadow, or distant figure if that better serves the story.
- Scene-appropriate costume and state variation is allowed: sleeves, robe visibility, lighting, posture, age phase emphasis, and spatial placement may change with the beat; do not copy the reference-sheet pose or four-view layout into story frames.

## motion_generation_rules

- For final delivery, convert each approved first frame into a real image-to-video segment using the capsule video_engine or approved fallback video engine.
- A static zoompan fallback is preview-only. It may be used to inspect script timing or first-frame variation, but it must not be marked pass as the final release.
- If image-to-video generation fails for a segment, retry or regenerate that segment. Do not silently replace the whole final with static Ken Burns motion.
- Final QA must distinguish generated motion segments from ffmpeg zoompan/static-image segments before recording a pass run.

## prompt_rules

- Every scene prompt must state age phase, costume logic, expression, pose, camera angle, and ink/paper motion.
- Vary age, costume, expression, pose, and camera angle across scenes; same-angle portrait reuse is a failure.
- Render people as 2D strong shui-mo ink guoman characters, not live action, not costume-drama stills, not 3D.
- Use xuan paper negative space, wet ink bloom, dry-brush broken edges, layered black-gray ink wash, and restrained mineral pigments.
- Avoid hand-to-hand action, complex fingers, violent handheld props, readable generated Chinese text, and UI-like typography inside scene images.
- Motion should feel like paper-theater layers, scroll reveal, ink-stroke scene formation, and foreground parallax rather than shaky camera footage.
- Every scene prompt must name a different primary subject and camera composition from adjacent scenes so the first-frame sheet cannot collapse into repeated visuals.
- Every scene involving Yang Zhen or Wang Mi must include the approved role anchor or reference-sheet instruction; do not let the image model reinvent the character.
- When passing a character reference image, state that it is an identity/style anchor only and must not copy the reference sheet pose, action, camera angle, white-background layout, or character placement.
- Storyboard prompts should choose scene-appropriate staging: front, side, back, three-quarter, distant, silhouette, reflection, or partial-body views are all valid if the role identity remains legible.

## quality_review_focus

- Contact sheet must show strong water-ink style in every scene.
- No black frames; no unintended long freeze. A deliberate question hold must be short and justified by narration.
- Audio/video duration must match TTS; final video should not have silent or frozen tails.
- Subtitle lines must remain short, readable, and inside safe bounds on 9:16 mobile framing.
- Reference images, if any, are identity/style anchors only and cannot collapse shot variation.
- Continuous narration must have no artificial gaps from per-scene audio padding; verify with silencedetect and edit-plan audio/video duration checks.
- Segment first-frame contact sheet must show one visually distinct frame per story beat; ordinary fps=1 contact sheets are not enough to judge repeated first frames.
- Reject final videos where multiple story beats reuse the same image, same source clip, or same table/person composition unless explicitly designed as one continuous beat.
- Final delivery must show real generated motion in most visual segments; static zoompan-only assemblies are preview artifacts and must not pass release.
- QA must compare narration meaning against visual segment timecodes; a technically aligned audio/video duration is not enough if the picture is still showing a previous story beat.
- QA must check recurring character consistency against the character bible/reference sheet, not only style consistency or first-frame uniqueness.

## routing_rules

- Use preset route in Capsule Cinema; do not depend on the remote local_script.
- If the user supplies only a figure name, build a concise 45-60 second narration rather than a chronology.
- If the user supplies a full script, preserve its factual claims and reshape only pacing, scene breaks, and visual prompts.
- If a reference image is supplied, use it only for facial identity or style anchoring; do not copy pose, age, costume, lens, or lighting.
- Produce both subtitle and no-subtitle masters when the assembly path supports it; at minimum do not burn unreadable dense subtitles.
- For narration-driven historical explainers, build the final audio as a continuous track first, then trim or assemble visuals to that track.
- For each storyboard beat, generate or select a separate first frame; do not rely on cropping a small set of old clips to simulate new scenes.
- For recurring historical figures, create the character bible and canonical reference sheet before generating any story beat images.
- Build the narration beat map before I2V generation; scene durations should follow semantic narration beats, not an equal division of total audio duration.

## semantic_timing_rules

- Before generating scene images or I2V clips, build a narration beat map with start/end timestamps for each meaning unit after measuring the final continuous TTS track.
- Do not split visual segments into equal durations. Equal duration cuts are allowed only for rough timing previews and cannot pass release QA.
- For release assembly, derive scene start and end times from narration meaning units, clause boundaries, and intended story emphasis, then trim/cut visuals to that timeline.
- Each visual segment must be labeled with the exact narration sentence or clause it supports, so QA can compare what the voice says against what the picture shows.
- If a line talks about a later concept, the image should already be in that concept or use a deliberate transition shot; it must not remain on an earlier story state by accident.

## source_refs

- video_workflow_db:guofeng_history@v5
- capsule-cinema:lib/art_styles/strong_shuimo_ink_guoman.yaml

## visual_variation_rules

- Every narrative story beat must start from one distinct generated first frame or one distinct source clip with a unique subject, camera angle, and composition.
- Do not split one source image or source clip into multiple story beats. Reusing a source is allowed only inside a single beat as a deliberate hold, and it must be labeled as such.
- Before assembly, create first_images_contact_sheet.jpg from generated first frames and reject repeated same-angle or same-source frames.
- After final assembly, create segment_first_frames_contact_sheet.jpg with exactly one representative frame per visual segment and review it for repeated first frames.
