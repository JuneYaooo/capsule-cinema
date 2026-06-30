---
type: Video Recipe
title: Visual Recipe
description: Visual style, references, characters, scenes, composition, and continuity.
stage: planning
domain: visual
profile: video.okf.capsule.v1
tags:
- visual
---

# Visual

## continuity_system

{
  "common_process_solutions": {
    "cut_to_press": "Use hard_tail_inherit throughout; the cut line, exposed stuffing, and spoon contact point must match because the viewer tracks this as one payoff action.",
    "mold_to_demold": "If the object leaving the mold is visible, use hard_tail_inherit from the filled/smoothed mold tail and show mold affordance. If demold is skipped, use deliberate_reset to a plated hero with a hand/cloth/cutaway transition.",
    "oven_in_to_oven_out": "If both insertion and removal are shown, either generate removal from the oven-entry tail plus a post-heat target state, or avoid showing removal and cut from closed-door glow/ding to plated post-heat reveal. Do not show open-door heating or visible morphing inside an open oven.",
    "post_heat_to_decoration": "Use soft_identity_reference: the same silhouette and fuzzy border persist, while color may warm and toppings may be added. Decoration contact shots then become hard_tail_inherit."
  },
  "consistency_axes": {
    "scene_consistency": [
      "table surface",
      "bowl/mold/tray/oven/plate relation",
      "lighting",
      "camera scale",
      "hand/tool style"
    ],
    "state_consistency": [
      "before_mold",
      "filled_mold",
      "smoothed_mold",
      "oven_entry",
      "post_heat_base",
      "decorated",
      "cut_open",
      "final_press"
    ],
    "subject_consistency": [
      "silhouette",
      "scale",
      "orientation",
      "color palette",
      "decoration marks",
      "material identity"
    ]
  },
  "continuity_modes": {
    "deliberate_reset": {
      "prompt_rule": "Make the reset legible as later in the process, not a magically morphing adjacent frame.",
      "reference_strategy": "Use a canonical target-state still; do not pretend it is a continuous visible action. Never place contradictory states directly adjacent without a transition mask.",
      "use_when": [
        "A cut intentionally jumps to a new stage: after-bake reveal, plated hero, final cross-section, completed decoration.",
        "The edit hides the missing steps with a clear time jump, cutaway, flash, ding, occlusion, or subtitle cue."
      ]
    },
    "free_tactile_insert": {
      "prompt_rule": "Keep palette, material, and tool language consistent, but do not overload the model with irrelevant earlier references.",
      "reference_strategy": "No strict previous-frame reference required. Use the global style/material anchor and avoid contradicting the current process state.",
      "use_when": [
        "Macro inserts of ingredient fibers, powder, tool contact, cotton tufts, sound details, or texture close-ups where exact object state is not being tracked.",
        "The insert is there for rhythm, tactile appeal, or attention reset."
      ]
    },
    "hard_tail_inherit": {
      "prompt_rule": "State exactly what changed in the previous shot and what remains unchanged: same shape, same mold/tray, same orientation, same visible fibers/toppings.",
      "reference_strategy": "Use extracted tail frame as start image/reference. If available, use first_last_frame with previous tail as start and the intended next stable state as end.",
      "use_when": [
        "The same object continues through a visible physical action: pour into mold -> smooth, smooth -> oven insert, knife touch -> cut open, spoon approach -> press.",
        "The next shot starts where the previous visible action ended, and a mismatch would feel like a reset or wrong object."
      ]
    },
    "soft_identity_reference": {
      "prompt_rule": "Say this is the same wool-felt object after an offscreen transition. Describe which identity features must persist and which process changes are allowed.",
      "reference_strategy": "Use the last stable anchor plus a target-state still/reference. Preserve silhouette, scale, palette, material language, and signature marks; allow controlled changes such as color warming, plate change, or topping added.",
      "use_when": [
        "A transformation is expected but not fully shown: demold, bake, cool, plate, decorate, reveal after time jump.",
        "The viewer only needs to recognize the same dessert identity, not the exact pixel state."
      ]
    }
  },
  "core_principle": "Continuity is required at state-critical transitions, not at every aesthetic insert. Adjacent shots only need exact continuity when the viewer is asked to believe they are watching the same object through the same physical action.",
  "core_principles": [
    "Every storyboard scene must include reference_profile before generation.",
    "Choose references by continuity need and consistency axes, not by habit.",
    "Use 0, 1, or 2 strong references. More raw references usually average states and create contradictions; compose a canonical target still first if a complex transformation needs many inputs.",
    "Do not judge free texture/rhythm inserts as exact continuity, but do keep palette, material, and process stage non-contradictory."
  ],
  "decision_order": [
    "First ask whether a viewer is expected to track the exact same object from the previous beat. If yes, use hard continuity; if no, decide whether this is a semantic later-stage jump or a free tactile insert.",
    "Then choose reference_profile by continuity need, not by habit: no_ref for free inserts, one_ref_previous for adjacent physical continuation, one_ref_target for deliberate later-stage reveal, two_ref_transition for controlled previous-to-target transformation.",
    "Finally write the visible process grammar for the beat: required affordance, hand/tool contact, direction of motion, visible result, and what skipped steps are hidden by the edit."
  ],
  "generic_state_map": [
    {
      "continuity_need": "free_tactile_insert or hard_tail_inherit within same bowl action",
      "stable_anchor": "ingredients/bowl/tool texture",
      "state_id": "before_mold"
    },
    {
      "continuity_need": "hard_tail_inherit",
      "stable_anchor": "mold boundary, fill volume, surface color, fiber direction",
      "state_id": "filled_mold"
    },
    {
      "continuity_need": "hard_tail_inherit into oven_entry if oven insertion is shown",
      "stable_anchor": "exact molded silhouette and tray/mold relation",
      "state_id": "smoothed_mold"
    },
    {
      "continuity_need": "hard_tail_inherit for visible insert; soft_identity_reference for post-heat reveal",
      "stable_anchor": "same tray direction, oven cavity, subject silhouette",
      "state_id": "oven_entry"
    },
    {
      "continuity_need": "soft_identity_reference unless removal is visibly continuous",
      "stable_anchor": "same silhouette plus allowed dyed-wool color shift",
      "state_id": "post_heat_base"
    },
    {
      "continuity_need": "hard_tail_inherit from first decoration contact through topping placement",
      "stable_anchor": "topping count/placement, edge pattern, plate/parchment",
      "state_id": "decorated"
    },
    {
      "continuity_need": "hard_tail_inherit from knife contact through interior reveal and press",
      "stable_anchor": "cut line, exposed stuffing, spoon contact point",
      "state_id": "cut_open"
    },
    {
      "continuity_need": "hard_tail_inherit inside payoff micro-shots",
      "stable_anchor": "compressed area and rebound direction",
      "state_id": "final_press"
    }
  ],
  "intent": "Keep wool-felt food-process videos coherent by deciding which beats need exact object continuity, which beats only need semantic identity, and which beats should stay visually free before choosing reference images.",
  "oven_heat": {
    "forbidden_patterns": [
      "Open oven door plus implied heating or baking duration.",
      "Insertion-only oven shot followed by an out-of-oven transformation without a door-close cue or clear offscreen time jump.",
      "Continuous oven shot where the same subject visibly changes shape, color, or texture unless first/last-frame continuity is exact."
    ],
    "intent": "Make oven/heating beats match basic viewer cognition while avoiding AI continuity穿帮.",
    "prompt_note": "For VEO oven scenes, explicitly prompt: the miniature oven door closes before heating; no open-door baking; no subject deformation visible through an open door; use soft ding and warm light only, no music.",
    "required_action_chain": [
      "Tray or subject enters the oven cavity only while the door is open.",
      "Before any heating, glow, ding, puff, browning, or time jump is implied, show the oven door closing, a closed oven door with warm light, or cut fully offscreen.",
      "After the implied bake, show either the door opening/removal or cut directly to a plated reveal that is clearly after an offscreen bake."
    ],
    "safe_alternatives": [
      "Close-up of oven handle/door closing, then warm light through glass.",
      "Macro timer/ding sound, warm white flash, then plated reveal.",
      "Gloved hand closes oven door and camera cuts before heat transformation.",
      "Skip the oven entirely and present heat as an offscreen ASMR transition."
    ]
  },
  "profile_types": {
    "no_ref": {
      "allowed_change": [
        "new texture angle",
        "new tool contact",
        "rhythm reset"
      ],
      "avoid": [
        "attaching irrelevant previous frames",
        "forcing exact object continuity where variety is useful"
      ],
      "count": 0,
      "images": [],
      "lock": [
        "global style",
        "wool-felt material",
        "palette family",
        "macro ASMR lighting"
      ],
      "use_when": [
        "Free tactile inserts: loose cotton fibers, powder fall, macro texture, tool friction, wool dust, glove contact, sound-detail shots.",
        "The viewer is not expected to track exact object state from the previous shot."
      ]
    },
    "one_ref_previous": {
      "allowed_change": [
        "tool moves",
        "surface compresses",
        "fiber shifts locally",
        "cut line opens"
      ],
      "avoid": [
        "extra unrelated references",
        "changing plate/mold/tray unless hidden"
      ],
      "count": 1,
      "images": [
        "previous_tail_frame"
      ],
      "lock": [
        "silhouette",
        "orientation",
        "container",
        "material",
        "surface marks",
        "tool contact area"
      ],
      "use_when": [
        "Continuous physical actions: smoothing continues, knife cut continues, spoon press/rebound continues, tray/mold handoff continues.",
        "The next clip should start from the previous visible state."
      ]
    },
    "one_ref_target": {
      "allowed_change": [
        "state jumps to target",
        "container changes if transition mask explains it"
      ],
      "avoid": [
        "placing before/after states as adjacent continuous action",
        "using previous frame when it conflicts with the target state"
      ],
      "count": 1,
      "images": [
        "canonical_target_state_still"
      ],
      "lock": [
        "target silhouette",
        "target decoration layout",
        "material identity",
        "camera scale"
      ],
      "use_when": [
        "Direct later-stage jumps where continuity is semantic rather than exact: plated hero, completed decoration, final cross-section, clean reveal after offscreen process.",
        "The edit clearly signals a time jump or reveal."
      ]
    },
    "two_ref_transition": {
      "allowed_change": [
        "controlled state change",
        "color warming",
        "topping added",
        "plate/tray change with mask",
        "cut/reveal opens"
      ],
      "avoid": [
        "more than two raw refs",
        "contradictory container states",
        "state averaging where the object becomes half-molded and half-plated"
      ],
      "count": 2,
      "images": [
        "previous_stable_state",
        "canonical_target_state_still"
      ],
      "lock": [
        "subject silhouette",
        "scale",
        "orientation",
        "palette",
        "material identity",
        "signature marks"
      ],
      "use_when": [
        "Expected transformations that must remain recognizable: mold to demold, oven-in to post-heat reveal, undecorated to decorated, whole to cut-open when using first/last frame.",
        "The model or workflow supports two references or first/last frames."
      ]
    }
  },
  "qa_questions": [
    "Does the reference_profile count match the continuity_mode?",
    "Are the lock axes concrete enough for subject, scene, and process state?",
    "If two refs are used, do they represent previous stable state plus target state rather than unrelated examples?",
    "If no ref is used, is the shot truly a free tactile insert rather than a state-critical transition?",
    "If the object changes mold/plate/oven state, is the change hidden by a transition mask or supported by two_ref_transition?"
  ],
  "qa_requirements": [
    "Check final contact sheet for pacing and full-video texture consistency.",
    "Check large targeted sheets for mold/demold, oven, decoration, cut, and press.",
    "Ask visual QA to distinguish open-door insertion/removal from closed-door heating, and to ignore white/blank contact-sheet padding as non-video space.",
    "Treat real-food leakage, dirty black fuzz in the hook, open-door heating, unreadable subtitles, and severe hand/tool deformation as blockers."
  ],
  "reference_image_policy": [
    "Use at most 1-2 strong references per generated scene: the previous stable state and, when needed, the target state. Too many references can average states and create contradictions.",
    "For hard_tail_inherit scenes, extract the previous clip tail frame and use it as start/reference. Prefer fixed camera or matching scale when possible.",
    "For soft_identity_reference transformations, generate or select a canonical target-state still before video generation; combine it with the previous state only if the model supports first/last or multi-reference input.",
    "For free inserts, use only the global style/material anchor; do not attach previous frames that would reduce visual variety or confuse the action.",
    "For deliberate resets, hide the missing process with an edit mask: close-up, occlusion, warm flash, ding, hand cover, tray/cutaway, or subtitle cue."
  ],
  "reference_profile_policy": {
    "canonical_target_first": "For complex transformations, create one canonical target-state still, then use at most previous state + target state.",
    "mapping": {
      "cotton_powder_fiber_closeups": "no_ref",
      "decoration_to_cut_to_press": "one_ref_previous",
      "in_mold_to_smooth": "one_ref_previous",
      "oven_insert_to_out_or_reveal": "two_ref_transition when showing continuity, otherwise deliberate_reset + one_ref_target after a clear closed-door/ding/cutaway mask",
      "post_heat_to_decoration": "one_ref_target or two_ref_transition depending on whether previous state is adjacent and recognizable",
      "smooth_to_oven_insert": "one_ref_previous"
    },
    "max_raw_refs": 2,
    "summary": "Use reference_profile.type to decide 0/1/2 reference images per scene after choosing continuity_mode."
  },
  "reference_selection_matrix": [
    {
      "avoid": "dragging previous object state into a shot where variety and tactile freshness matter more",
      "beat_type": "free tactile hook or texture insert",
      "continuity_mode": "free_tactile_insert",
      "lock": "global wool-felt style, palette family, macro ASMR lighting",
      "reference_profile": "no_ref",
      "refs": 0,
      "use_for": "fiber pull, powder fall, whisk friction, cotton fluff, macro tool sound, palette/texture rhythm reset",
      "viewer_tracking": "low exact-state tracking"
    },
    {
      "avoid": "changing plate/mold/tray, reversing direction, or adding a target still that averages the current state",
      "beat_type": "adjacent shaping/contact continuation",
      "continuity_mode": "hard_tail_inherit",
      "lock": "silhouette, orientation, container, contact point, cut line, surface marks, tool relation",
      "reference_profile": "one_ref_previous",
      "refs": 1,
      "use_for": "material enters mold then settles, smoothing continues, border placement continues, knife cut continues, spoon press/rebound continues",
      "viewer_tracking": "high exact-state tracking"
    },
    {
      "avoid": "placing this directly after the previous state without an occlusion, hand cover, cutaway, ding, flash, or time-jump cue",
      "beat_type": "clean later-stage reveal after hidden process",
      "continuity_mode": "deliberate_reset",
      "lock": "target silhouette, material identity, color palette, signature decoration layout",
      "reference_profile": "one_ref_target",
      "refs": 1,
      "use_for": "plated hero, completed decoration, clean post-heat reveal, final beauty state after offscreen demold/removal",
      "viewer_tracking": "semantic identity tracking, not exact physical continuation"
    },
    {
      "avoid": "more than two raw refs; if many details are needed, compose a single canonical target still first",
      "beat_type": "controlled transformation that must stay recognizable",
      "continuity_mode": "soft_identity_reference or first_last_frame_transition",
      "lock": "same subject_id, scale, orientation, material identity, persistent edge/mark/topping positions unless intentionally changed",
      "reference_profile": "two_ref_transition",
      "refs": 2,
      "use_for": "mold-to-demold when visible, oven-in-to-post-heat when both states are shown, undecorated-to-decorated, whole-to-cut-open when the tool path matters",
      "viewer_tracking": "medium/high identity tracking across an expected change"
    }
  ],
  "state_anchor_fields": [
    "subject_id: one persistent dessert/craft object name for the current video",
    "silhouette: recognizable food shape such as crescent, round tart, square cake, roll, cup, slice",
    "scale_and_orientation: size in frame, direction, left/right/top orientation",
    "container_affordance: bowl, mold, tray, parchment, plate, oven rack, knife line, spoon contact area",
    "material_state: loose fibers, filled mold, smoothed surface, dyed wool border, cotton roving topping, cut interior",
    "surface_identity: color patches, seams, fibers, toppings, score marks, visible edge pattern",
    "process_state_id: before_mold, filled_mold, smoothed_mold, oven_entry, post_heat_base, decorated, cut_open, final_press",
    "allowed_missing_steps: what is intentionally hidden by cut, occlusion, close-up, time jump, or sound cue"
  ],
  "state_anchor_ladder": [
    "Assign one subject_id for the whole dessert/craft object.",
    "Track process_state_id across the ladder: loose_material -> in_container_or_mold -> smoothed_or_shaped -> transfer_or_heat_entry -> post_transform_base -> decorated -> cut_open -> final_press.",
    "For each state, lock silhouette, scale, orientation, container relation, material identity, signature surface marks, and topping positions when they become visible.",
    "Store stable tail frames and canonical target stills as named anchors; do not rely on memory of previous prompts."
  ],
  "storyboard_metadata_required": {
    "example_values": {
      "allowed_change": "color warms, topping added, plate changes, cut opens, filling exposed",
      "continuity_mode": "hard_tail_inherit | soft_identity_reference | free_tactile_insert | deliberate_reset",
      "identity_lock": "silhouette, orientation, container, color palette, fuzzy material, topping positions",
      "reference_sources": "tail_of_previous_scene, canonical_target_state_still, global_style_only",
      "transition_mask": "none, occlusion, hand cover, flash, ding, cutaway, macro texture insert"
    },
    "fields": [
      "state_before",
      "state_after",
      "continuity_mode",
      "reference_sources",
      "identity_lock",
      "allowed_change",
      "transition_mask"
    ]
  },
  "storyboard_schema": {
    "example": {
      "continuity_mode": "hard_tail_inherit",
      "reference_profile": {
        "allowed_change": [
          "tool moves",
          "surface compresses"
        ],
        "avoid": [
          "extra unrelated references",
          "state averaging"
        ],
        "count": 1,
        "images": [
          "previous_tail_frame"
        ],
        "lock": [
          "silhouette",
          "orientation",
          "container",
          "material",
          "surface_marks"
        ],
        "type": "one_ref_previous"
      }
    },
    "required_field": "reference_profile"
  },
  "visible_process_grammar_generalization": {
    "examples": [
      "Mold: material must sit inside a visible boundary; if demold is skipped, hide it with a cutaway and reveal a canonical plated state.",
      "Oven or lidded heat: open door/lid can show insertion/removal only; glow, ding, puff, browning, or transformation needs closed door/lid or an offscreen mask.",
      "Cut: blade direction and exposed interior must align; if jumping from whole to sliced, use a deliberate reveal cue.",
      "Press: finger/spoon contacts before deformation; rebound should happen on the same contact point.",
      "Piping/decorating: nozzle or hand placement should explain where each tuft/dot lands."
    ],
    "principle": "The edit may skip steps, but any shown key action must be cognitively complete: the viewer sees the needed object affordance, the hand/tool contacts from a plausible direction, and the visible result follows."
  },
  "when_to_use_multiple_refs": [
    "Use two refs only when both before and after state matter and the model/workflow can support first/last or multi-reference control.",
    "The two refs should be previous stable frame + canonical target-state still. Do not mix unrelated style examples, multiple old states, or competing containers.",
    "If a scene needs many visual traits, first create a canonical target still that merges them, then use that one target reference.",
    "Do not use multiple refs for free texture inserts or rhythm shots; they reduce visual freshness and can confuse state."
  ],
  "workflow_mapping": {
    "cotton_powder_fiber_closeups": "no_ref",
    "decoration_to_cut_to_press": "one_ref_previous",
    "in_mold_to_smooth": "one_ref_previous",
    "oven_insert_to_out_or_reveal": "two_ref_transition when showing continuity, otherwise deliberate_reset + one_ref_target after a clear closed-door/ding/cutaway mask",
    "post_heat_to_decoration": "one_ref_target or two_ref_transition depending on whether previous state is adjacent and recognizable",
    "smooth_to_oven_insert": "one_ref_previous"
  }
}

## prompt_contract

{
  "audio_language": "Every VEO prompt must request close-up foley tied to visible contact and explicitly forbid music, melody, singing, speech, voiceover, and subtitles.",
  "negative_anchor": "real pastry, real edible food, glossy custard, molten cheese, wet batter, oily surface, realistic crumbs, realistic burnt crust, liquid egg, real dough, photorealistic bakery product, gore, dirty kitchen, readable text, subtitles, logo, watermark",
  "positive_anchor": "handmade needle-felt craft object shaped like the requested food, visible wool fibers, plush texture, cotton batting, soft-body physics, macro tabletop ASMR, white cotton gloves, pastel kitchen, shallow depth of field",
  "state_language": "Always describe exact current state, remaining state, and next state: what is already mixed, what is still separate, what tool touches it, what visible fiber deformation happens next."
}

## visual_grammar

{
  "core_principle": "The video may skip intermediate steps for pacing, but every visible key beat must be complete enough for the viewer to infer a plausible process. Missing steps should be hidden by cuts, occlusion, close-ups, time jumps, or sound cues, not by showing an impossible or incomplete action.",
  "intent": "Make AI wool-felt baking scenes feel causally and physically legible without forcing every real-world step on screen.",
  "material_perception": {
    "crust_rule": "Tan borders should read as dyed wool cord/fuzzy plush edge, not crispy edible crust.",
    "opening_rule": "Use clean light bowls and pastel fiber effects in the first 0-3 seconds; avoid dark speckled powders in the hook. If needed, skip process frames and jump to a clean fiber stretch.",
    "principle": "Dark dots, black powder, and grey hairy props near light food-shaped felt can be perceived as dirty hair/fuzz even when intended as seasoning or berry dust.",
    "topping_rule": "White decorations should read as cotton roving or wool tufts, with separated puffs and visible fibers, not smooth cream or liquid frosting."
  },
  "other_examples": [
    "Piping: nozzle touches or hovers correctly over the surface; cream/felt cloud appears where the nozzle points.",
    "Cutting: knife direction, blade contact, and exposed interior line should match; do not jump from uncut to sliced without a cut cue unless using a deliberate reveal cut.",
    "Mixing: whisk/spoon should contact material and cause compression, fibers, swirl, or lift; do not float above the bowl while contents change.",
    "Molding: material should enter/settle within the visible mold boundary; do not spill into a different shape without an occluded transition.",
    "Press/rebound: spoon or finger must contact the plush surface before duangduang deformation and recovery."
  ],
  "oven_as_example_not_special_case": {
    "not_required": "Do not require every oven segment to show the full insert -> close door -> bake -> open -> remove chain.",
    "required_when_visible": [
      "If showing insertion, the oven should read as an oven with a door/door frame/cavity and the tray should enter it plausibly.",
      "If showing removal, the tray or subject should be extracted from a plausible oven/cavity direction, or the edit should cut to a plated reveal that clearly implies offscreen removal.",
      "If showing heating while the oven remains visible, do not imply active heating with an obviously open door; use closed-door glow, a cutaway, occlusion, or a time jump.",
      "If the subject changes shape/color/material during heat, keep that transformation offscreen unless the visible continuity is exact."
    ]
  },
  "prompt_note": "For VEO prompts, state the process grammar of each visible beat: object affordance, tool contact, direction, and visible result. Do not merely name the action; describe what makes it believable on screen.",
  "visible_beat_requirements": [
    "Show the necessary object affordances for the action: doors, lids, molds, trays, nozzles, blades, handles, rims, or openings when they define how the action works.",
    "Show a plausible relation between tool, hand, subject, and container: the tool touches the right surface, enters from a believable direction, and causes a visible result.",
    "Make the shown beat self-contained: setup/contact/result should be readable even if the video cuts before or after the beat.",
    "When skipping steps, hide the gap with a deliberate transition or cutaway so the viewer fills it in naturally.",
    "Entry and exit states do not need every in-between frame, but they must not contradict each other when placed adjacent in the edit."
  ]
}
