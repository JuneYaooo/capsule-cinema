---
type: Video Capsule Card
title: X来低模主题宣传变体
description: 输入一个宣传主题，自动生成“遇事失败→哭喊妈妈——→X实体化主角喊X来救场→广告语”的完整低模故事；X、主角形象、解决动作和宣传内容必须直接一致。
stage: routing
profile: video.okf.capsule.v1
primary_workflow: agnes_segmented_animal_fable
tags:
- agnes
- free-tier
- animal-fable
- low-poly
- 5-10s
- long-video
- theme-variants
- promotion
---

# X来低模主题宣传变体

## Purpose

用户最少只输入一个 `topic`，例如“宣传低糖酸奶”或“周末读书会招募”。胶囊先给出多种结构明显不同的创意候选，再生产被选中的一条。

`5-10s` 是 Agnes 的单个生成单元，不再等于默认完整成片。默认 `full_story` 约 `12-18s`：第一单元展示困境、失败和带哭腔的“妈妈——”；第二单元由另一个角色喊“X来！”，完成一个解决动作，再说一句与宣传主题有关的广告语。

`X来`、主角和广告不是三件分开的事。X必须直接来自宣传对象，救场主角必须在视觉上就是X或X的明确化身，并用X特有的动作解决问题。例如“马来”由马登场；“书来”由拟人书本登场。普通猫头鹰只因象征知识而喊“书来”属于弱联想，不通过质量门。

困境须在前 `1.5s` 可读，“妈妈——”发生在一次失败动作之后并持续约 `1.8-3.2s`；停顿 `0.2-0.8s` 后由另一角色喊原创“X来！”，解决动作最迟在成片 `8s` 内启动。广告语在结果读懂后说，不能与撞击声抢位。Agnes 原声只有在三段台词逐字转写和人工审听通过后才保留；不克隆真人儿童或可识别人物声音。

宣传事实不会由模型补写。商品卖点、价格、活动日期、数据、来源、Logo和CTA只有在用户提供或核验后才能进入公开成片，并且全部本地确定性渲染。

## When To Use

- agnes
- free-tier
- animal-fable
- low-poly
- 5-10s
- long-video

## When Not To Use

- 用户要求严格参考图角色一致性或 Agnes 图生视频；当前公开接口不支持。
- 用户要求一次生成超过 10 秒的连续镜头；应改成分场景或换经确认的渠道。
- 用户要求免费渠道的确定 SLA、无限额度或确定每日视频秒数。
- 不复制示例、对标角色、原对白、原音乐或连续镜头。

## Required Confirmation

正式生成前必须向用户展示：Agnes 图片/视频调用数量、预计最短提交时间、`妈妈——→X来！`原声生成与转写审听策略、软一致性限制、首镜样片和无自动付费回退策略，并取得确认。

## Stage Reading

- Routing: read `capsule.yaml`, `index.md`, this card, `contracts/input_schema.yaml`, and `contracts/content_scope.yaml`.
- Planning: read the input/content-scope contracts and the recipe files named under `read_order.planning`.
- Generation: read the runtime contract, motion recipe, and asset index.
- QA: read the quality rules and release gates.
- Learning: read promoted lessons only; raw evidence is local-only.
