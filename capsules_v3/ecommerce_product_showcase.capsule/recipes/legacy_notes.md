# Legacy Notes

## capsule_intent

Generate reusable ecommerce product showcase shorts for TikTok Shop / Douyin style product seeding: product-led, claim-safe, narrated, subtitled, and optimized for quick viewer comprehension.

## examples

- {
  "cta_style": "soft_guidance",
  "marketing_strategy": "pain_solution",
  "platform": "tiktok_shop",
  "product_name": "便携挂烫机",
  "sample_user_requirements": "商品：便携挂烫机；卖点：30秒出蒸汽、可折叠、适合差旅；目标人群：上班族和差旅用户；平台：TikTok Shop。",
  "selling_points": [
    "30秒出蒸汽",
    "可折叠收纳",
    "适合差旅和上班通勤"
  ],
  "target_audience": "上班族和差旅用户"
}

## model_route

{
  "image": "gpt-image-2 via GptImage2Tool",
  "route": "Generate product-consistent first frames with gpt-image-2, then animate each scene with Seedance 2.0 image-to-video.",
  "video": "seedance2.0 via Seedance20VideoGeneratorTool"
}

## product_reference_policy

{
  "allowed_changes": [
    "camera angle",
    "hand interaction",
    "background scene",
    "lighting style",
    "minor placement changes"
  ],
  "forbidden_changes": [
    "invented brand text",
    "wrong product category",
    "changed package shape",
    "unreadable fake labels",
    "hidden product in most scenes"
  ],
  "identity_locks": [
    "silhouette",
    "dominant color",
    "material",
    "packaging proportions",
    "distinctive shape",
    "use context"
  ],
  "primary_anchor": "First product image from product_images or user_reference_images; for ecommerce_product_showcase this is a hard product identity anchor, not a style reference.",
  "runtime_required_when_product_image_provided": [
    "Treat user_reference_images[0] as product_images[0] and the primary product identity anchor.",
    "Set reference_design.object_reference.use_user_provided=true and user_provided_image_index=0.",
    "Do not set object_reference.use_user_provided=false when a product image exists.",
    "Every product-bearing scene must use reference_type object or mixed and reference_ids containing object_reference or a primary object id.",
    "For mixed scenes, include both character ids and object_reference so the runtime can pass the product image to gpt-image-2 edits."
  ]
}

## prompt_rules

- If user_reference_images are present, reference image 0 is the product main image; use it directly as object_reference with use_user_provided=true and user_provided_image_index=0.
- For every scene where the product appears, set needs_reference=true, reference_type=object or mixed, and include object_reference in reference_ids.
- Do not generate a new standalone object reference from text when the user supplied a product image; preserve the supplied silhouette, color, material, and distinctive shape.
- First scene must contain the product, the product in use, or an unmistakable use-case setup; never start with generic empty lifestyle footage.
- When product_images are provided, keep the product visible in at least three quarters of scenes and preserve its silhouette, colors, material, and package proportions.
- Use image/video prompts for visual evidence only; no generated Chinese/English captions, price tags, UI labels, logos, watermarks, or readable text inside frames.
- Prefer clean tabletop, hand demo, lifestyle use, close-up texture, before/after, and practical scenario shots over abstract brand advertising.
- Use realistic but not overproduced lighting; product must stay inspectable, not hidden by blur, darkness, extreme crop, or decorative effects.
- If exact product identity cannot be preserved by the selected video engine, state this as a preview limitation in QA rather than claiming publish-ready fidelity.

## qa_checklist

- 4-6 scenes, 15-30 seconds, vertical 9:16.
- Product or use case appears in the opening scene.
- The sales arc is complete: hook, reveal, demo/benefit, trust or objection, CTA.
- No invented price, promo, certification, medical claim, review count, or absolute guarantee.
- No generated on-frame text inside image/video prompts; subtitles are post-production overlays.
- If product_images were provided, product identity is preserved well enough for the declared delivery promise or marked as preview.
- When product images are provided, verify the final storyboard and prompts use object_reference/user image 0 as the product anchor.

## workflow

- Parse user requirements into product_name, category, selling_points, target_audience, platform, marketing_strategy, CTA, price/promo, and claims_to_avoid.
- If product images are provided, treat the first image as the primary identity anchor and ask image generation to preserve product shape, color, material, and packaging without inventing logos or text.
- Choose 4-6 scenes whose total duration fits 15-30 seconds; use one core selling point per scene and keep narration concise.
- Generate product-consistent first frames with gpt-image-2 before video clips; then create Seedance 2.0 image-to-video clips with silent clip audio so the unified TTS track controls timing.
- Assemble TTS, low-volume BGM, and post-production subtitles; do not ask the visual model to render subtitles or sales labels inside the image/video.
- Run QA for product visibility, sales-arc completeness, claim safety, subtitle readability, and audio balance before delivery.
