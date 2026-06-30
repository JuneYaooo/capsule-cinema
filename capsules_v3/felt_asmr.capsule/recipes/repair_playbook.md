# Repair Playbook

## repair_playbook

- If image/video becomes realistic food, replace food nouns with craft-object language and add negative real-food terms before retrying.
- If cut interior becomes molten or cheese-like, prompt felt layers/cotton stuffing/soft plush custard instead of creamy center.
- If oven browning becomes real crust, prompt dyed brown wool fibers and toasted-color felt patches, not burnt pastry.
- If continuity jumps, shorten the source segment and bridge with tail-frame inheritance rather than accepting the jump.
- If audio is too weak, raise foley track or lower BGM; target final mean volume around -33 to -29 dB without clipping.
- If a visible process beat feels cognitively incomplete, do not patch only that exact prop; identify the missing affordance/contact/result cue and either add it, hide the gap with a transition, or remove the beat.
- For oven beats specifically, insertion/removal shots do not need the full baking chain, but the shown shot must include a plausible oven structure such as door/door frame/cavity and sensible tray direction.
- If dark speckled powder appears near the opening hook, treat it like a dirty-hair/fuzz risk. Use pastel wool floss, larger colored fiber tufts, or remove the speckled frames; do not accept pepper-like black dots on light wool food surfaces.
- For white toppings, prompt and edit as dry cotton roving or separated wool tufts with visible fibers. Reject smooth whipped-cream or frosting motion unless the fibers remain clearly plush and dry.
- For crust-like borders, describe dyed wool cord, fuzzy needle-felt rope, or plush border. Avoid realistic baked crust, crisp crumbs, glossy pastry, or edible-looking browning.
- When a generated clip has a good action but a problematic sub-beat, prefer micro-editing out the bad frames with precise seeking before rerunning the whole scene.
- If the food object changes shape/container between adjacent state-critical shots, classify the transition: hard continuity needs tail-frame inheritance; soft transformation needs a time-jump mask plus identity locks; free inserts should not be judged as exact continuity.
- If mold-in and mold-out states do not match, either regenerate demold/plating from the mold tail frame, or hide demold completely and cut to a canonical plated state with a clear transition cue.
- If oven-in and oven-out states do not match, avoid showing both as one continuous chain unless using previous tail plus target post-heat reference; otherwise show insertion/closed-door cue and cut to plated reveal.
- If a generated clip has an impossible sub-beat but useful surrounding action, micro-cut the bad frames with precise seeking before rerunning the whole scene.
- If a heat/glow cue appears while a door/lid is open, remove that portion and insert a closed-door still, occlusion, warm flash, or cutaway before the glow/ding.
- If mold-in and mold-out do not match, either regenerate from the filled-mold tail frame or hide demold and cut to a target plated state.
- If oven-in and oven-out do not match, avoid showing them as a continuous chain unless using previous-tail plus post-heat target; otherwise close-door cue then plated reveal is safer.
- If Gemini flags continuity from a tiny sheet, verify with large targeted sheets before deciding whether it is a true blocker or a contact-sheet artifact.
- Use precise seeking for repaired micro-shots; fast keyframe seeking can leak rejected frames back into the edit.
