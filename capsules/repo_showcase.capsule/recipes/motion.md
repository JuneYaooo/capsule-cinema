---
type: Video Recipe
title: Motion Recipe
description: Camera motion, action, transitions, dynamic generation, and editing rhythm.
stage: generation
domain: motion
profile: video.okf.capsule.v1
tags:
- motion
---

# Motion

## content_aware_motion_policy

{
  "anti_pattern": [
    "所有图片都从左往右进入，导致动效单调。",
    "小字密集图只滑入不放大，观众看不清重点。",
    "长图强行 contain，画面变小、周围留白过多。",
    "局部放大没有关注真正的信息点，反而裁掉证据。"
  ],
  "content_feature_keywords": [
    "chart",
    "graph",
    "dashboard",
    "ui",
    "table",
    "thumbnail",
    "deck",
    "detail",
    "dense",
    "diagram",
    "flow",
    "图表",
    "数据",
    "看板",
    "面板",
    "界面",
    "缩略",
    "细节",
    "小字",
    "表格",
    "机制",
    "流程"
  ],
  "motion_choices": {
    "dense_detail_image": "图表、数据看板、PPT 缩略图、UI 面板、机制图、表格、小字截图：使用中心放大，必要时用局部放大 motion_focus 指向 left/right/top/bottom。",
    "manual_override": "profile 或 scene 可以显式设置 motion_direction: zoom_in/local_zoom/center_zoom/slide_in_left/slide_in_right/slide_in_top/slide_in_bottom/none；可用 motion_focus 指定局部放大重点。",
    "regular_result_image": "普通结果图或封面式素材：可以做一次干净滑入，避免每页都同一种方向。",
    "tall_or_vertical_long_image": "高图、长截图、长 README 内容区、竖向流程图：按宽度铺满中间区域，上下滑展示全貌。",
    "wide_or_horizontal_long_image": "宽图、横向 UI、长表格、宽机制图：按高度铺满中间区域，左右滑展示全貌。"
  },
  "profile_fields": {
    "content_features": "每幕可写内容特征列表，帮助自动动效选择，例如 ['PPT 缩略图', '数据图表']。",
    "motion_amount": "放大强度，常规建议 0.06-0.12；过大容易裁掉信息。",
    "motion_direction": "可选动效覆盖：auto、none、zoom_in、center_zoom、local_zoom、slide_in_left、slide_in_right、slide_in_top、slide_in_bottom。",
    "motion_focus": "局部放大重点：center、left、right、top、bottom、top_left、top_right、bottom_left、bottom_right。"
  },
  "purpose": "每个分镜的中间主视觉动效要服务观看细节，而不是所有图片都从左往右进入。动效先根据图片比例，再根据内容特征选择。",
  "qa_requirement": "contact sheet 和关键帧抽检必须看中间素材重点是否更清楚；如果放大裁掉标题、图例、关键数字或主要 UI，改为中心放大、减小 motion_amount 或回到滑动展示。",
  "renderer_behavior": "motion_plan_for_source() accepts content_features and requested_focus. Extreme aspect-ratio images use scroll_long_axis. Regular detail-heavy images use zoom_in with motion_focus. Simple regular images keep clean slide-in by default.",
  "required": true,
  "selection_order": [
    "先看图片比例：特别高或特别长的素材，用长边位移展示全貌；高图上下滑，宽图左右滑。",
    "再看内容特征：如果是图表、PPT 缩略图、UI 面板、机制图、表格、小字密集截图，优先用中心放大或局部放大，让观众看清重点。",
    "最后看叙事需要：需要制造进入感的普通素材，才使用左/右/上/下滑入。"
  ],
  "version": "2026-06-27-content-aware-middle-motion"
}
