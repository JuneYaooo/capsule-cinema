---
type: Video Capsule Card
title: 三色毛衣搭配
description: 固定全身机位的三色穿搭演示与本地服装合成。
stage: routing
profile: video.okf.capsule.v1
primary_workflow: three_color_reveal
tags:
- 毛衣
- 配色
---

# 三色毛衣搭配

使用 scripts/run_capsule.py，传入 --capsule knit_palette_reveal、--topic、--params 和 --output-dir。参数文件见本期交付目录 params.json。

选款版在每个 looks 元素中增加 product 和 demo_start。product 包含 title、name 和 photo，可用 hero 指定另一个上身图。demo_start 为切回配色示范的绝对秒数。选款版参数与商品来源保存在本期 DAXUEN 目录。

试穿版使用 tryon_assets 指定姿态、服装区域遮罩与商品原图目录，按模特的肩、肘、腕和髋部位置合成衣身和袖子。配饰、人脸、头发与手在渲染时分别处理。本期三款商品的纹理取样坐标在 scripts/knit_tryon.py 中，更换商品需重新校准。使用试穿参数时，每段直接显示换装后的表演。

运行环境需要 macOS 系统字体、Python、OpenCV、NumPy、SciPy、Pillow 和 FFmpeg。可从 [试穿参数示例](examples/tryon.json) 开始，将素材路径替换为本机路径。
