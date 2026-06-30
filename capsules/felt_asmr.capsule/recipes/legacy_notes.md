# Legacy Notes

## audience_design

{
  "attention_strategy": [
    "Open within 0-2 seconds on a concrete tactile action: crack, squeeze, tear, pour, cut, press, or reveal; do not start with setup or a static beauty shot.",
    "Create a new visual-tactile event every 1.4-2.4 seconds; do not hold one unchanged action over 3 seconds.",
    "Use a micro-cliffhanger chain: ingredient state changes, texture thickens, object inflates, topping droops, final body jiggles.",
    "Reserve the most replayable tactile payoff for the last 4-6 seconds: spoon press, knife split, elastic rebound, felt filling slump, or topping droop.",
    "Keep the viewer reading the object instantly: subject occupies about 65-85% of the frame, background remains soft and uncluttered."
  ],
  "primary_viewer_pull": "Viewers stop for immediate tactile transformation, soft handmade material, pastel macro food-craft fantasy, and a final satisfying press/rebound payoff.",
  "visual_expressiveness": [
    "Every shot needs one clear visible material contrast: matte fiber vs shiny tool, powder vs plush, pale cream vs caramel, soft body vs rigid spoon.",
    "Use macro/ECU/CU as the default; use MS only for oven insertion or a spatial reset, then return to macro immediately.",
    "Palette should be low-saturation pastel with one appetizing accent color; avoid flat beige-only sequences.",
    "Maintain visible fibers, fuzzy edges, needle-felt seams, cotton batting layers, or plush pile in every food surface, including baked crust and cut interiors.",
    "Tools should be familiar ASMR carriers: gloved fingers, whisk, spatula, piping bag, ice cream scoop, knife, spoon, tray, parchment."
  ]
}

## capsule_intent

Produce reusable wool-felt baking ASMR shorts where any dessert or baked-food topic is translated into a handmade plush craft process with strong tactile events, not a realistic cooking video.

## topic_translation_rule

For any requested food, first identify its recognizable silhouette, color contrast, signature transformation, and final tactile payoff; then rewrite the process as a wool-felt craft fantasy. Do not follow real baking steps if they reduce visual tactility.

## workflow

- Analyze or define a reference effect: material consistency, tactile event chain, shot duration distribution, final payoff.
- Build 6-8 scene prompts, each with 2-3 internal timeline beats, but plan final edit as 14-20 micro-shots.
- Generate first hard scene and inspect for wool-felt material before batch generation.
- Use first/last frame generation when possible; for stateful transitions, extract tail frame and inherit it into the next scene.
- Before generating, write the visible process grammar for any real-world action beat: what object affordance must be visible, how the tool/hand contacts it, what result appears, and where skipped steps are hidden.
- Reject and regenerate any shot that becomes real food, especially post-oven, cut-open, or spoon-press shots.
- Assemble clean concat first, preserve it, then mix low-volume BGM under native ASMR foley.
- Run local QA plus Gemini side-by-side reference comparison before delivery.
- Before storyboard prompts, create a state continuity map: state_before, state_after, continuity_mode, reference_sources, identity_lock, allowed_change, and transition_mask for every scene.
- Use hard_tail_inherit only for state-critical adjacent actions; use soft_identity_reference for expected offscreen transformations; use free_tactile_insert for texture/rhythm inserts; use deliberate_reset for clear later-stage jumps.
- For mold, oven, decoration, cut, and press sequences, capture stable state frames as reusable anchors before generating the next stateful scene.
- Every storyboard scene must include reference_profile: type, count, images, lock, allowed_change, and avoid.
- Choose 0/1/2 references by continuity_mode and consistency axes; never use more than 2 raw refs unless first composing a canonical target still.
- For continuity-critical adjacent actions, select one_ref_previous or two_ref_transition before VEO generation and record the actual local reference paths after extraction.
