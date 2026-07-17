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
    "局部放大没有关注真正的信息点，反而裁掉证据。",
    "为了展示完整页面而让真正能证明文案的核心区域始终过小。"
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
    "dense_detail_image": "密集 UI 或图表优先直接截核心区域；必须保留上下文时使用 local_zoom，并用 core_focus 或 motion_focus 指向 left/right/top/bottom。",
    "manual_override": "profile 或 scene 可以显式设置 motion_direction: zoom_in/local_zoom/center_zoom/slide_in_left/slide_in_right/slide_in_top/slide_in_bottom/none；优先用 core_focus 记录文案对应的证据重点，兼容使用 motion_focus。",
    "regular_result_image": "普通结果图或封面式素材：可以做一次干净滑入，避免每页都同一种方向。",
    "tall_or_vertical_long_image": "只有多个纵向区域的先后关系本身有意义时才上下滑；单一核心证据优先紧裁或局部放大。",
    "wide_or_horizontal_long_image": "只有横向对比或多个区域关系本身有意义时才左右滑；单一核心证据优先紧裁或局部放大。"
  },
  "profile_fields": {
    "content_features": "每幕可写内容特征列表，帮助自动动效选择，例如 ['PPT 缩略图', '数据图表']。",
    "motion_amount": "放大强度，常规建议 0.06-0.12；过大容易裁掉信息。",
    "core_focus": "与本幕底部事实链直接对应的核心证据区域；可使用 center、left、right、top、bottom、top_left、top_right、bottom_left、bottom_right。",
    "motion_direction": "可选动效覆盖：auto、none、zoom_in、center_zoom、local_zoom、slide_in_left、slide_in_right、slide_in_top、slide_in_bottom。",
    "motion_focus": "局部放大重点：center、left、right、top、bottom、top_left、top_right、bottom_left、bottom_right。"
  },
  "purpose": "每个分镜先锁定与底部事实链对应的核心证据区域，再决定紧裁、局部放大或长轴移动。动效服务证明与阅读，不服务页面全貌展示。",
  "qa_requirement": "contact sheet 和关键帧抽检必须看中间素材重点是否更清楚；如果放大裁掉标题、图例、关键数字或主要 UI，改为中心放大、减小 motion_amount 或回到滑动展示。",
  "renderer_behavior": "motion_plan_for_source() accepts content_features and requested_focus. Extreme aspect-ratio images use scroll_long_axis. Regular detail-heavy images use zoom_in with motion_focus. Simple regular images keep clean slide-in by default.",
  "required": true,
  "selection_order": [
    "先锁定证据：明确底部事实链对应的 core_focus，并检查关键帧能否在手机上读懂。",
    "再定截图范围：单一证据优先紧裁；需要上下文时保留 context_plus_core 并使用 local_zoom。",
    "最后看关系和比例：只有多区域顺序或对比本身有意义时才使用上下滑或左右滑；普通素材才使用干净滑入。"
  ],
  "version": "2026-06-27-content-aware-middle-motion"
}
