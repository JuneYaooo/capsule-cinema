---
name: capsule-cinema
version: 2.0.0
description: "Capsule Cinema 视频配方工厂：按配方生产 AI 短视频的本地工作室。运行时（分镜、图片/视频/TTS、字幕/BGM、质检）+ 制作方法论（路由、渠道政策、钩子审计、产物规范）+ active OKF 配方目录包（内部格式名 capsule）"
author: june2
license: PolyForm-Noncommercial-1.0.0

capabilities:
  - id: generate-full-video
    description: "根据一句话需求生成本地短视频：LLM 分镜、图片、视频、TTS、拼接、字幕、BGM 和文案"
  - id: generate-storyboard
    description: "只生成分镜 JSON，不执行图片、视频和音频生成"
  - id: feedback-driven-regeneration
    description: "在已有 workspace 中重生成指定分镜的图片/视频，再用拼接脚本重组"
  - id: generate-image
    description: "使用官方火山引擎 Ark 生成图片"
  - id: generate-video-clip
    description: "使用官方火山引擎 Ark Seedance 生成单个视频片段"
  - id: generate-tts-audio
    description: "使用 Universal TTS（MiniMax、豆包语音或本机 provider）将文本转成语音"
  - id: concatenate-videos
    description: "将多个视频片段和可选配音拼接为一个视频"
  - id: add-subtitles
    description: "为视频烧录字幕，支持普通自适应字幕和 SRT 字幕"
  - id: add-background-music
    description: "使用用户提供或胶囊自带的本地 BGM，并混入视频"
  - id: generate-social-copy
    description: "根据视频内容生成社交平台文案和标签"
  - id: check-video-quality
    description: "检测视频质量、生成本地 QA 报告，并按 rubric 打分"
  - id: build-edit-plan
    description: "从 workspace/storyboard 和本地媒体生成 work/edit_plan.json，作为可审计的时间线中间层"
  - id: validate-edit-plan
    description: "校验 work/edit_plan.json 的本地媒体路径、时间线连续性、场景覆盖和源文件时长，生成 qa/edit_plan_validation.json"
  - id: plan-repairs
    description: "把质量评分中的 blocker/manual review 项转换为 qa/repair_plan.json 修复建议"
  - id: create-release-checkpoint
    description: "汇总 final、manifest、EditPlan、QA、修复计划和审片资产，生成 release/release_checkpoint.json"
  - id: analyze-video-to-capsule
    description: "使用本地覆盖层中显式配置的视频解析工具生成胶囊草稿"
  - id: manage-local-capsules
    description: "管理 active OKF 胶囊目录包：创建、更新、打包、安装、注入胶囊合同/资产并沉淀通用经验"

permissions:
  network: true
  filesystem: true
  shell: true
  env:
    - PYTHON_BIN
    - DOTENV_PATH
    - VIDEO_RESOURCES_PATH
    - OPENCLAW_OUTPUT_DIR
    - CAPSULE_CINEMA_LOCAL_CHANNELS_DIR
    - ARK_API_KEY
    - ARK_BASE_URL
    - ARK_SEEDREAM_MODEL
    - ARK_SEEDANCE_MODEL
    - ARK_SEEDANCE20_MODEL
    - CREW_API_KEY
    - CREW_BASE_URL
    - CREW_MODEL_NAME
    - MINIMAX_API_KEY
    - MINIMAX_GROUP_ID
    - DOUBAO_TTS_API_KEY
    - DOUBAO_TTS_RESOURCE_ID
    - DOUBAO_TTS_MODEL
    - DOUBAO_TTS_SPEAKER
    - DOUBAO_TTS_WS_URL
    - RUNNINGHUB_API_KEY
    - WANANIMATE2_API_KEY
    - WANANIMATE2_WEBAPP_ID
    - WAN22_API_KEY
    - WAN22_WEBAPP_ID

inputs:
  - name: user_requirements
    type: string
    required: false
    description: "完整视频或仅分镜工作流的视频创作需求，例如：一只橘猫做饭的搞笑短视频"
  - name: workflow
    type: string
    required: false
    default: "auto"
    description: "auto、full-video、storyboard-only、concat 或 feedback"
  - name: target_duration
    type: number
    required: false
    default: 30
    description: "目标时长，单位秒，最大 180"
  - name: aspect_ratio
    type: string
    required: false
    default: "9:16"
    description: "画面比例：9:16、16:9 或 1:1"
  - name: video_engine
    type: string
    required: false
    default: "seedance2.0"
    description: "公开视频引擎：官方火山引擎 Ark Seedance 2.0"
  - name: image_engine
    type: string
    required: false
    default: "volcengine-seedream"
    description: "公开图片引擎：官方火山引擎 Ark 图片生成；本地覆盖层可追加本机渠道"
  - name: bgm_path
    type: string
    required: false
    description: "可选的用户自定义本地 BGM 音频路径"
  - name: capsule
    type: string
    required: false
    description: "可选的 active 胶囊短名；优先读取 capsules/<name>.capsule/，并注入胶囊合同、默认参数和本地资产"
  - name: capsule_params_json
    type: string
    required: false
    default: "{}"
    description: "胶囊 input_schema 声明输入的 JSON 对象；用于多必填字段和胶囊专用参数"
  - name: allow_generic_capsule_fallback
    type: boolean
    required: false
    default: false
    description: "专用路线胶囊是否允许退回普通图生视频预览；默认禁止"
  - name: accept_preflight_changes
    type: boolean
    required: false
    default: false
    description: "是否接受胶囊 Preflight 选用替代工具或显式降级；未接受时 needs_confirmation 会阻止生成"
  - name: delivery_promise
    type: string
    required: false
    description: "可选交付承诺：motion_led、source_led、tts_led_explainer、reference_remake、capsule_preset 或 specialized_route；不传时按路线和输入自动推断"
  - name: source_review_path
    type: string
    required: false
    description: "source_led 路线的源素材审查 JSON 路径；声明 source_led 时必须提供"
  - name: reference_analysis_path
    type: string
    required: false
    description: "reference_remake 路线的参考分析 JSON 路径；用于证明参考特征已被分析"
  - name: workspace_dir
    type: string
    required: false
    description: "已有 workspace 路径；提供后自动进入 feedback 工作流"
  - name: scene_id
    type: number
    required: false
    description: "要重生成的分镜编号，从 1 开始"
  - name: image_prompt
    type: string
    required: false
    description: "feedback 工作流中的新图片 prompt"
  - name: video_prompt
    type: string
    required: false
    description: "feedback 工作流中的新视频 prompt"
  - name: skip_image
    type: boolean
    required: false
    default: false
    description: "feedback 工作流是否跳过图片重生成，只重生成视频"
  - name: source_video_path
    type: string
    required: false
    description: "video-to-capsule 工作流的本地源视频路径"
  - name: video_analysis_tool
    type: string
    required: false
    default: ""
    description: "视频解析工具名；必须在 Git 忽略的 local-channels/tool_registry.yaml 中显式配置"
  - name: capsule_name
    type: string
    required: false
    description: "写入胶囊时使用的安全短名；write_capsule=true 时必填"
  - name: capsule_display_name
    type: string
    required: false
    description: "可选胶囊展示名；不传时从 capsule_name 生成"
  - name: capsule_summary
    type: string
    required: false
    description: "可选胶囊摘要；不传时使用解析结果摘要"
  - name: write_capsule
    type: boolean
    required: false
    default: false
    description: "是否把草稿写成 capsules/<name>.capsule/ active 胶囊包"
  - name: include_source_video
    type: boolean
    required: false
    default: false
    description: "写胶囊时是否把源视频作为 reference_only 资产打包"
  - name: local_script_source
    type: string
    required: false
    description: "仅当审阅后的执行策略为 local_script 时使用；指向已经成功运行并完成泛化审计的 Python 脚本或脚本目录，不接受分析器临时生成的代码"
  - name: local_script_entry
    type: string
    required: false
    description: "local_script_source 为目录时必填；相对于该目录的 Python 入口文件"
  - name: script_evidence_json
    type: string
    required: false
    description: "local script 复用证据 JSON 或 JSON 文件路径；必须声明成功运行次数、跨主题验证、确定性步骤和参数化输入"
  - name: overwrite_capsule
    type: boolean
    required: false
    default: false
    description: "目标胶囊已存在时是否允许覆盖"
  - name: analysis_prompt
    type: string
    required: false
    description: "追加给视频解析模型的自定义分析要求"
  - name: target_platform
    type: string
    required: false
    description: "可选发布平台提示，用于解析和胶囊草稿提炼"

outputs:
  - name: video_path
    type: string
    description: "最终视频本地路径"
  - name: workspace_dir
    type: string
    description: "工作目录路径"
  - name: storyboard
    type: object
    description: "完整分镜数据"
  - name: storyboard_formatted
    type: object
    description: "适合展示的分镜摘要"
  - name: storyboard_path
    type: string
    description: "storyboard.json 路径"
  - name: cover_image
    type: string
    description: "封面或首张预览图路径"
  - name: preview_images
    type: object
    description: "前几张场景图路径"
  - name: reference_images
    type: object
    description: "角色/风格参考图路径"
  - name: scene_video_paths
    type: object
    description: "前几个分镜视频路径"
  - name: progress_summary
    type: string
    description: "当前产物阶段摘要"
  - name: duration
    type: number
    description: "最终视频时长"
  - name: scene_count
    type: number
    description: "分镜数量"
  - name: engine_used
    type: string
    description: "实际视频引擎"
  - name: delivery_promise
    type: object
    description: "本次运行的交付承诺，用于后续 QA 和发布检查点判断是否兑现"
  - name: production_proposal_path
    type: string
    description: "work/production_proposal.json 路径"
  - name: decision_log_path
    type: string
    description: "work/decision_log.json 路径"
  - name: artifact_manifest_path
    type: string
    description: "artifact_manifest.json 路径"
  - name: edit_plan_path
    type: string
    description: "work/edit_plan.json 路径"
  - name: edit_plan_validation_path
    type: string
    description: "qa/edit_plan_validation.json 路径"
  - name: local_video_qa_path
    type: string
    description: "qa/local_video_qa.json 路径"
  - name: repair_plan_path
    type: string
    description: "qa/repair_plan.json 路径"
  - name: release_checkpoint_path
    type: string
    description: "release/release_checkpoint.json 路径"
  - name: deliverable
    type: boolean
    description: "本次运行是否通过后置 QA 和发布检查，达到可交付状态"
  - name: run_status
    type: string
    description: "运行状态：deliverable、generated_but_failed_qa、generation_failed 或 storyboard_only"
  - name: qa_blockers
    type: object
    description: "阻止本次运行被视为可交付的 QA 或发布检查项"
  - name: capsule_lifecycle
    type: object
    description: "本次胶囊运行的 Instance、ProductionPlan、阶段上下文和 EffectReport 产物引用"
  - name: capsule_release_recommendation
    type: string
    description: "胶囊生命周期发布建议：ready、review_required 或 blocked"
  - name: post_run_warnings
    type: object
    description: "后置 QA、EditPlan、发布检查点或生产契约写入时产生的警告列表"
  - name: video_analysis_path
    type: string
    description: "analysis/video_breakdown.json 路径"
  - name: capsule_draft_path
    type: string
    description: "analysis/capsule_draft.json 路径"
  - name: capsule_dir
    type: string
    description: "write_capsule=true 时创建的 active 胶囊目录"
  - name: execution_strategy
    type: object
    description: "视频蒸馏胶囊的执行策略判定：preset、local_script 或 review_required，以及确定性步骤、参数化输入和复用证据"
  - name: analysis_tool_used
    type: string
    description: "实际使用的视频解析工具"
  - name: warnings
    type: object
    description: "解析或写胶囊过程中的非阻断警告"

tags:
  - video-generation
  - ai-video
  - short-video
  - tts
  - okf-capsules
  - capsules
  - content-creation

dependencies:
  skills: []

execution:
  timeout: 600
  longRunning: true

minOpenClawVersion: "2.1.0"
---

## Agent Operating Contract

Before planning or running tools, classify the request and read `references/production-guide.md` before planning for video-production routing. Use the runtime only within the workflows registered in this package.

- Route first: choose post-production, reference remake, capsule, new AI video, action transfer, digital human/lip sync, music MV, or blocker before writing prompts.
- Capsule first: for capsule tasks, load the active capsule package from `capsules/<name>.capsule/` before planning; do not use archived or single-file capsule sources as the current recipe.
- Progressive capsule lifecycle: consume only `routing` and `planning` while planning, add `generation` when the runner starts, and load `qa` only after the runner returns. Do not load `learning` automatically. This stages the authored capsule content; it does not remove or summarize it.
- Capsule tool confirmation first: before generating with a capsule, confirm the final in-capsule tool chain with the user. List the selected image, video/motion, TTS/voice, BGM/music, SFX, subtitle, compositing/editing, and local-script tools or channels; why each was selected; same-role alternatives available from the selected capsule route and local approved tools; missing or blocked alternatives; and any substitution or downgrade. This confirms tools inside the selected capsule, not replacement capsules. Do not start generation until the user approves; storyboard-only planning may stop before this gate when no media is generated.
- Capsule update conflict gate: before updating an active capsule, run a conflict review against the existing capsule surfaces. If proposed metadata, capability, tag, runtime, recipe, QA, or promoted-lesson content contradicts existing content, show the conflict points to the user and wait for their confirmed resolution before writing. Structural validation is not a substitute for semantic conflict review.
- Capsule content-scope gate: before creating, updating, or materializing a capsule from video analysis, read `contracts/content_scope.yaml`. Preserve declared series-fixed identity such as recurring characters, BGM, CTA, visual skin, layout, narrative mechanism, and QA methods. Supply episode-variable people, projects, accounts, course names, facts, evidence, metrics, prices, titles, narration, and diagram-node copy only from the current run input. Never promote one episode's literals into capsule metadata, runtime defaults, active recipes, QA, or learning. Current-run input may legitimately reuse a forbidden literal; that does not authorize storing it in reusable package surfaces. Generalize new lessons, use placeholders in active examples, and run `scripts/capsule_package_validate.py` after every create or update.
- Capsule script-solidification gate: keep a capsule as `preset` when contracts and recipes express the workflow. Use `local_script` only for an existing mature deterministic renderer, timeline, compositor, or specialized pipeline with successful-run evidence, cross-topic verification, explicit deterministic steps, and parameterized episode inputs. Incomplete candidates remain `review_required`. Video analysis may recommend the mode but must never generate and auto-package code or choose a local path; the caller supplies the reviewed script. Promoting or replacing a runner must pass the capsule update conflict gate.
- Policy first: choose tools only after reading the active channel policy, `lib/config/tool_capabilities.yaml`, and `lib/config/tool_registry.yaml`; use capabilities for fit/provider requirements and the registry only for direct invocation. Never fall back to an unapproved provider.
- Promise first: define the delivery promise before generation. Decide whether the run is motion-led, source-led, TTS-led explainer, reference remake, capsule preset, or specialized route, then judge every fallback and QA result against that promise.
- Proposal first for serious generation: before paid/batch generation, summarize the proposed viewer experience, tool route, expected limits, first-scene/sample gate, and release QA bar. Do not batch-generate until the user has accepted the direction or explicitly asked to skip proposal review. The runtime proposal artifact is an audit record, not a substitute for pre-run proposal review.
- Prototype first: for new AI video, generate and inspect one representative hard scene before batching.
- Release first: final deliverables must stay under `output/` and include `artifact_manifest.json`, QA reports, repair plan when needed, and `release/release_checkpoint.json`.
- No silent downgrade: if an approved tool/provider/route fails, retry or switch only within the approved policy and record the fallback. If the switch changes the promised output, stop for approval or report a blocker.
- Blockers are honest output: if route, channel, asset, delivery promise, QA, EditPlan validation, visible copy lint, or release checkpoint blocks delivery, fix it or report it; do not describe the run as complete.
- Lifecycle release is authoritative: a capsule lifecycle result of `blocked` must not be reported as complete; `review_required` must remain pending until the required human review is resolved.

## Business Production Contract

Capsule Cinema should behave like a small production studio, not a loose tool runner. Every serious run needs a visible business contract:

1. **Delivery promise**: state what the user is actually buying/expecting: real motion, source-footage edit, narrated explainer, ASMR ambience, action transfer, lip sync, music-led MV, or a reusable capsule format.
2. **Approved route**: map that promise to one allowed route. Generic `run_video.py` may create ordinary image-to-video shorts, but it must not masquerade as action transfer, digital human, music MV, super-resolution, or a source-footage edit.
3. **User-visible choices**: expose decisions the user would care about: video engine, image engine, TTS provider/voice, BGM strategy, aspect ratio, duration, and whether a fallback would change the output character.
4. **Evidence before confidence**: reference remakes require source/reference analysis; source-led edits require probe/frames/transcript where applicable; capsule runs require contract inspection; generated runs require a first hard scene/sample check before scale-out.
5. **Decision log**: for serious runs, keep or append `work/decision_log.json` with provider choices, capsule overrides, fallbacks, user approvals, and QA-driven repairs. This is an audit trail, not user-facing copy.
6. **Promise-aware delivery**: final QA must answer whether the delivery promise was honored. A technically playable MP4 is not complete if it violates the promised route or silently downgrades quality.

## 当前边界

Capsule Cinema 是一个本地短视频生成 skill：`scripts/` 下的 Python 封装脚本是命令入口（OpenClaw 场景由 `index.js` 调用）。当前能力范围：完整视频、仅分镜、指定分镜重生成、单工具调用、拼接、EditPlan 时间线及校验、release checkpoint、质量修复计划、语言检测、active OKF 胶囊目录包（创建、更新、打包、安装、合同/资产注入、通用经验沉淀）和本地 QA。超出这些工作流时，不扩展新工作流；只能按现有短视频生成链路处理，无法处理时说明需要额外实现。

## 制作方法论

做视频前先读 `references/production-guide.md`（任务路由、渠道政策、钩子审计、受众审计、产物落盘规范、生产循环）。它会按需路由到其余 references：分镜技巧（storyboard-craft）、制作模式（production-patterns）、命令配方（tool-recipes）、公共渠道政策（channel-policy）、active 胶囊目录包（capsule-package-format）、装配质检踩坑（assembly-qc-pitfalls）、审片门（video-review-gate）等。硬性规则（契约、QA 门、注册表）在运行时代码里；方法论指导创作判断。

默认单次成片仍按短视频/中短视频设计，`target_duration` 上限为 180 秒。系统需要支持“长逻辑链路”：当内容包含连续剧情、固定人物、系列章节、教程步骤或产品故事时，必须先建立可复用的一致性契约，再按分镜批量生成。长链路支持不等于单个模型直接生成长视频，而是通过章节、角色锚点、风格锚点、参考图和分段拼接来保持人物与画风一致。

长链路一致性要求：

- 规划阶段输出 `consistency_strategy`，明确角色一致性、画风一致性、章节策略和允许变化项。
- 参考设计阶段输出 `style_anchor_id`、`fixed_style_traits`、角色 `identity_anchor`、`fixed_traits` 和 `allowed_variations`。
- 每个分镜携带 `chapter_id`、`continuity_group`、`character_ids`、`style_anchor`、`continuity_notes`。
- 自动拆分的子分镜必须继承父分镜的角色、风格和连续性字段。
- 同一角色跨分镜不得改变物种/年龄感/体型/脸型或毛色/发型/服装主视觉/关键配饰；同一视频默认不得切换画风。

## 工作流

| 意图 | 执行方式 |
|------|----------|
| 一句话生成完整短视频 | `scripts/run_video.py`，OpenClaw workflow 为 `full-video` |
| 只要分镜脚本 | `scripts/run_video.py --storyboard_only`，workflow 为 `storyboard-only` |
| 重生成指定分镜 | `scripts/run_scene.py`，workflow 为 `feedback` |
| 重新拼接 workspace | `scripts/run_concat.py`，workflow 为 `concat` |
| 解析视频生成胶囊草稿 | `scripts/analyze_video_to_capsule.py`，workflow 为 `video-to-capsule` |
| 校验分镜契约 | `scripts/validate_storyboard.py` |
| 检查人物/画风一致性契约 | `scripts/run_consistency_qa.py` |
| 成片技术 QA | `scripts/local_video_qa.py` |
| 成片质量评分 | `scripts/score_video_quality.py`（本地技术检查；可选本地覆盖层审片工具） |
| 生成时间线中间层 | `scripts/build_edit_plan.py` |
| 校验时间线中间层 | `scripts/validate_edit_plan.py` |
| 生成 QA 修复计划 | `scripts/plan_repairs.py` |
| 生成发布检查点 | `scripts/release_checkpoint.py` |
| 调单个底层工具 | `scripts/run_tool.py` |
| 管理 active 经验胶囊 | `scripts/capsule_package_create.py` / `scripts/capsule_package_update.py` / `scripts/capsule_package_pack.py` / `scripts/capsule_package_install.py` |

架构边界见 `references/architecture.md`。工具 API 见 `references/tools-api.md`。引擎和音色见 `references/engines-and-voices.md`。分镜结构见 `references/storyboard-schema.md`。制作经验见 `references/video-recipes.md`。

## 运行约定

本包自包含 Python 代码，运行时从 `lib` 加入 `PYTHONPATH`。优先用 `python3.12`，并先安装依赖：

```bash
cd "$(git rev-parse --show-toplevel)"
python3.12 -m pip install -r lib/requirements.txt
```

常用环境变量：

| 变量 | 用途 |
|------|------|
| `PYTHON_BIN` | OpenClaw 子进程 Python，默认 `python3.12` |
| `DOTENV_PATH` | 可选 `.env` 路径 |
| `VIDEO_RESOURCES_PATH` | 字体、音效和本地 BGM 等资源目录 |
| `OPENCLAW_OUTPUT_DIR` | 生成物根目录；必须指向本仓库 `output/` 或其子目录 |
| `CREW_API_KEY` / `CREW_BASE_URL` / `CREW_MODEL_NAME` | LLM 分镜规划 |
| `ARK_API_KEY` / `ARK_BASE_URL` | 官方火山引擎 Ark；base URL 可选 |
| `ARK_SEEDREAM_MODEL` / `ARK_SEEDANCE_MODEL` | 可选模型覆盖；默认 Seedream 5.0 Pro / Seedance 2.0 官方 Model ID |
| `MINIMAX_API_KEY` / `MINIMAX_GROUP_ID` | 官方 MiniMax TTS |
| `DOUBAO_TTS_API_KEY` | 豆包语音官方 API Key（默认使用双向 WebSocket） |
| `DOUBAO_TTS_RESOURCE_ID` / `DOUBAO_TTS_MODEL` / `DOUBAO_TTS_SPEAKER` | 豆包语音 2.0 可选资源、模型与默认音色 |
| `RUNNINGHUB_API_KEY` | RunningHub 公开工作流示例 |
| `CAPSULE_CINEMA_LOCAL_CHANNELS_DIR` | 可选，本地渠道覆盖目录；默认 `local-channels/` |

输出目录布局：每次运行在输出根目录下创建一个 run 目录（通常是 `output/general_video_<timestamp>/` 或 `output/<workflow>_<timestamp>[_<project>]/`），包含 `artifact_manifest.json`、`release/`（最终成片、发布文件和 `release_checkpoint.json`）、`work/`（`edit_plan.json`、images/audios/videos/reference_images/temp 等中间产物）、`qa/`（`edit_plan_validation.json`、质检报告和 `repair_plan.json`）、`prompts/`（分镜、图片、视频、TTS、音乐和装配参数快照）、`logs/`。完整视频主流程会把 scene 级 `audio_path` / `image_path` / `video_path` 回写到 `storyboard.json`，并在成功后自动生成 EditPlan、EditPlan 校验、本地 QA、修复计划和发布检查点。
最终交付件、QA 报告、封面、发布文案和手动 `run_tool.py` 产物都必须写在本仓库 `output/` 下；不要写到 `/tmp`、仓库根目录、父目录或任意外部目录。

## 运行时维护

维护本运行时（脚本、包元数据、工具注册表、环境变量管道；本地测试代码不入库）时遵循以下规则：

1. 改模块边界前读 `references/architecture.md`；改封装脚本或工具参数前读 `references/tools-api.md`；改分镜输出/校验前读 `references/storyboard-schema.md`。
2. 元数据、env 白名单、包或封装脚本变更后运行 `npm test`；本机如有额外本地测试，可另行运行，但不要入库。
3. 保持小写 `skill.md`；不要新建 `SKILL.md`（大小写不敏感文件系统会覆盖本文件）。
4. 脚本用显式 `python3.12` 运行，不依赖可执行权限位；`--help` 与参数校验阶段延迟重型 import。
5. 不要硬编码 API key、签名 URL、cookie、私有端点。env 变量需在本文件 permissions 与 `index.js` 白名单中保持同步。
6. 新工具不要直接加进 `scripts/run_tool.py`；更新 `lib/config/tool_registry.yaml` 注册元数据，并把工具类放入 `lib/custom_tools/<category>/`。
7. 不要创建 `lib/.env`（本地校验会拒绝）；保持 `lib/.env.example` 无密钥，并与本文件、`index.js`、`references/channel-policy.md` 对齐。

## 脚本示例

完整视频：

```bash
cd "$(git rev-parse --show-toplevel)"
PYTHONPATH=lib python3.12 scripts/run_video.py \
  --user_requirements "一只橘猫做饭的搞笑短视频" \
  --target_duration 30 \
  --aspect_ratio "9:16" \
  --video_engine seedance2.0
```

按本地胶囊生成分镜：

```bash
cd "$(git rev-parse --show-toplevel)"
PYTHONPATH=lib python3.12 scripts/run_video.py \
  --capsule ecommerce_product_showcase \
  --user_requirements "一款桌面收纳产品的 20 秒展示" \
  --storyboard_only
```

仅分镜：

```bash
cd "$(git rev-parse --show-toplevel)"
PYTHONPATH=lib python3.12 scripts/run_video.py \
  --user_requirements "一只橘猫做饭的搞笑短视频" \
  --target_duration 30 \
  --storyboard_only
```

重生成第 2 个分镜：

```bash
cd "$(git rev-parse --show-toplevel)"
PYTHONPATH=lib python3.12 scripts/run_scene.py \
  --workspace_dir output/<run_id> \
  --scene_id 2 \
  --image_prompt "新的图片描述" \
  --video_prompt "新的视频动作描述" \
  --image_engine volcengine-seedream \
  --video_engine seedance2.0
```

单工具调用：

```bash
cd "$(git rev-parse --show-toplevel)"
PYTHONPATH=lib python3.12 scripts/run_tool.py \
  --tool VolcengineImageGeneratorTool \
  --params '{"prompt":"一只橘猫在厨房做饭","output_path":"output/manual_tool/work/images/cat.png","aspect_ratio":"9:16"}'
```

成片本地质量检查：

```bash
cd "$(git rev-parse --show-toplevel)"
PYTHONPATH=lib python3.12 scripts/local_video_qa.py \
  --final-video output/<run_id>/release/final.mp4 \
  --output output/<run_id>/qa/local_video_qa.json
```

口型、字幕布局、角色声音匹配等无法由本地技术检查可靠判断的项目，必须保留人工审片门；如本机配置了额外分析器，只能通过 Git 忽略的本地覆盖层显式调用。

生成时间线、修复计划和发布检查点：

```bash
cd "$(git rev-parse --show-toplevel)"
PYTHONPATH=lib python3.12 scripts/build_edit_plan.py \
  --workspace output/<run_id>

PYTHONPATH=lib python3.12 scripts/validate_edit_plan.py \
  --workspace output/<run_id>

PYTHONPATH=lib python3.12 scripts/plan_repairs.py \
  --workspace output/<run_id>

PYTHONPATH=lib python3.12 scripts/release_checkpoint.py \
  --workspace output/<run_id>
```

## Prompt 规则

- 完整视频工作流当前只要求分镜输出普通 `image_to_video` 场景。
- `image_prompt` 推荐中文，且不要要求模型生成文字、标题或字幕。
- `video_prompt`：公开的 `seedance2.0` 路线可使用中文。
- 旁白始终按中文短视频节奏写，单段较长时用 `|` 标记画面切换点。
- 生成模型自带音频时必须人工抽检语言；旁白成片优先关闭模型音频并使用批准的 TTS。
- 有人物连续出现时，必须优先使用角色参考图和 `reference_ids`；不要只在 prompt 里写“同一个人/同一只猫”。
- 有统一画风要求时，必须使用 `style_reference` 和 `visual_style`，所有场景默认 `use_style_reference=true`。
- 对长链路或系列化内容，先生成并检查一组角色/风格参考图，再批量扩展分镜。

## 胶囊仓库

当前可用胶囊以目录包形式存放在仓库根目录 `capsules/<name>.capsule/`，运行时 `--capsule <name>` 只读取 active 目录包。Active 胶囊可打包分享给其他人（初始胶囊与分享胶囊同一格式）：

```bash
# 打成可分享的 active 包（含本地资产与脚本，附 sha256 校验）
python3.12 scripts/capsule_package_pack.py capsules/<name>.capsule --out /path/to/dir

# 在另一台机器安装到 active capsules 目录
python3.12 scripts/capsule_package_install.py /path/to/dir/<name>.video-capsule.zip --out capsules [--force]
```

打包前会自动做密钥、远程 URL、运行产物和 stale evidence 扫描，命中即拒绝打包；安装会校验 `manifest.json`、文件 sha256 和 active 包结构。

新建、更新或从视频蒸馏胶囊时，先读取 `contracts/content_scope.yaml` 并将内容分为 `series_fixed` 与 `episode_variable`。栏目固定角色、BGM、CTA、视觉皮肤、版式、叙事机制和 QA 方法可以保留；单集的人物、项目、账号、课程、事实、数字、价格、标题、旁白和图解节点只能来自当前输入。已知单集残留必须写入 `forbidden_reusable_literals`，不得进入 metadata、runtime defaults、active recipes、QA 或 learning。当前运行输入合法出现同名内容，不等于允许将它固化回胶囊。更新后必须运行 package validator；若某项真正升级为栏目资产，应显式重分类，不能靠确认冲突绕过。
