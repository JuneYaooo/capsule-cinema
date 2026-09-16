---
type: Video Recipe
title: Screen Recording Recipe
description: GitHub 与 WorkBuddy 真实录屏的采集、来源、隐私和剪辑规则。
stage: generation
domain: screen_recording
profile: video.okf.capsule.v1
tags:
- screen-recording
- github
- workbuddy
---

# 真实录屏证据

## 录屏分工

本配方不是把截图做成“像录屏”的动画，而是要求两条独立的真实视频素材：

1. **GitHub 录屏**：用真实浏览器打开本期 `project_url`，展示仓库身份、README 或一个可见结果区域，做一次短滚动或一次明确导航。
2. **WorkBuddy 录屏**：用原生 OBS 只录 WorkBuddy 主窗口，展示把同一仓库交给 WorkBuddy 后的输入、处理状态和右侧可读产物预览。

两段录屏可以在同一条片中各占 2–6 秒。短版建议 GitHub 在第 3–5 秒出现、WorkBuddy 在第 8–13 秒出现；`complete_45s` 建议 GitHub 在第 10–20 秒之间出现、WorkBuddy 在第 25–35 秒之间出现。角色口播可用 J-cut 压在录屏下方，录屏不单独制造无声展示段。

## GitHub 采集

- 录制前先确定一个事实核心区：仓库名/README 标题、功能说明、Demo 或结果；核心区至少占画面 65%。
- 录屏视口优先使用 1080×1440（9:16 画布友好）或等比例窗口，录制后只做必要裁切，不把横向网页缩成大留白卡片。
- 不显示地址栏、URL、二维码、登录信息、个人头像/私信、无关标签页、桌面或浏览器扩展。
- 记录 `source_url`、`captured_at`、`viewport`、`capture_method=actual_browser_github_scroll_recording`、`capture_scope`、`sha256` 和对应的事实主张。
- 录屏遇到加载失败时可改用真实 README 截图或官方 API 原始素材，但不能用自绘 UI 冒充录屏；本配方的默认发布模式缺少 GitHub 录屏即不通过。

## WorkBuddy 采集

- 依照 WorkBuddy Recording skill：左侧历史栏用 WorkBuddy 自带“收起侧边栏”隐藏，中心聊天与右侧 artifact/preview 面板同时可见；不要进入 artifact-only 全屏。
- OBS 绑定当前 WorkBuddy 主窗口，每次录制前重新绑定窗口；目标 1200×800、30 fps、H.264，隐藏光标，不录环境麦克风。
- 输入提示词前开始 OBS 录制，录制 raw 文件；如做加速或去等待，再额外生成 edited 文件，不能替换或删除 raw。
- 录制内容只包含本期项目的公开仓库分析与结果预览。账号、令牌、Cookie、私聊、其他应用、桌面、OBS 控制台和系统通知都必须避开或遮挡。
- 记录 `source_url`（若有）、`captured_at`、`window_capture=true`、`history_sidebar=collapsed`、`artifact_panel=visible`、`raw_path`、`edited_path`（可选）、`sha256` 和 `privacy_review=passed`。

## 剪辑与验收

- 真实录屏以硬切、整段滑入或平滑推近进入；同一段录屏可以先保留 1.5–3 秒上下文，再做一次与口播主张对应的局部推近（例如 README 事实区、审核结果区），推近后稳定停留 1.5–3 秒。禁止连续微抖、鼠标轨迹装饰、重复缩放和假点击成功状态；局部推近必须来自原始录屏裁切，不能重绘 UI。
- 录屏的原生文字可以保留，禁止额外叠加“真实录屏”“操作说明”“来源/API”“角色标签”或数据卡。全片只保留一个贯穿始终的顶部主标题。
- 每个录屏必须在 `screen_recording_manifest` 和 `source_asset_manifest` 各有一条记录，二者的路径、哈希和来源一致。
- 质检至少包括：文件可解码、画面比例、时长、关键帧清晰度、隐私检查、来源可回溯、raw 保留、时间线确实使用两个录屏片段。
