# 胶囊与工具能力抽象层 设计文档

状态: 设计稿（未上线，允许破坏式重构，不需要向后兼容）
作者: -
最后更新: 2026-06-24

## 0. 一图看懂（概览）

本质就三句话，L1–L5 和各项决策都只是它的实现细节：

```
   胶囊 ── 只说「要什么」(风格 + 成品意图)
   工具 ── 只说「我能做什么」(能力 + 需要什么凭证)
 运行时 ── 负责「把两者对上 → 执行 → 验收」
```

> 关键好处：换人、换工具，**胶囊一个字都不用改**——因为胶囊从不提"用哪个模型"。这正是 §1.2 说的"活配方"。

整个系统的流程：

```
            ┌───────────────────────────────────┐
            │        你: 说需求 + 点名胶囊         │
            └───────────────────────────────────┘
                             │
          ┌──────────────────┴──────────────────┐
          ▼                                       ▼
 ┌──────────────────┐                  ┌──────────────────────┐
 │   胶囊 (配方)     │                  │    工具库 (能力)      │
 │  · 风格          │   不写死模型      │  每个工具声明:        │
 │  · 输出意图      │ ◄──────────────► │  · 我能做什么         │
 │  · 能力需求      │                  │  · 需要哪些 env/凭证   │
 └──────────────────┘                  └──────────────────────┘
          │                                       │
          └──────────────────┬──────────────────┘
                             ▼
                ┌──────────────────────────┐
                │   撮合 (Resolver)         │  "你本地有什么能满足胶囊?"
                │   按能力选工具 + 备选链    │   缺能力 → 直接报错,不硬跑
                └──────────────────────────┘
                             ▼
                ┌──────────────────────────┐
                │   本次执行计划 (可复现)    │  ← 这就是「按胶囊规划本次任务」
                └──────────────────────────┘
                             ▼
        ┌──────────────────────────────────────────┐
        │   固定流水线                               │
        │   图  →  视频  →  配音  →  后期  →  拼接   │
        └──────────────────────────────────────────┘
                             ▼
                ┌──────────────────────────┐
                │   质检 (按胶囊标准验收)    │  合规? 达到质量标准? (有样片才比对)
                └──────────────────────────┘
                             ▼
                ┌──────────────────────────┐
                │   成片 + 能不能发布报告    │
                └──────────────────────────┘
```

图里每个框对应下文的术语：

| 图里的框 | 下文术语 | 作用 |
|---|---|---|
| 胶囊"能力需求" | `roles`（requires/prefers，§3 L3） | 说清需要什么能力，不绑工具 |
| 胶囊"输出意图" | `output_contract`（§2、§3 L3） | 成品该长什么样（静音/字幕/配音…） |
| 工具库 | `capabilities.yaml` + `tool_capabilities.yaml`（§3 L1/L2） | 工具自报能力 |
| 撮合 | Resolver（§3 L4） | 按本地可用工具选型 + 自动 fallback |
| 本次执行计划 | Preflight / `execution_plan.json`（§4） | 按胶囊规划本次任务 |
| 质检 | `quality_rules` + 质检（§7 决策三、附录） | 验收成片是否合规且达标 |

---

## 1. 背景与问题

Capsule Cinema 的目标是让一个"胶囊"（一种视频作品的风格 + 制作工艺）可以被复用：A 调通的胶囊，B 拿过去也能跑出同样气质的作品。但当前架构做不到这一点，因为**胶囊和具体工具/模型是硬绑定的**。

### 1.1 现状问题（基于现有代码）

**问题一：胶囊直接写死具体工具，且命名混乱。**

`capsules/video_workflow_online_capsule_reference.json` 里：

```json
// guofeng_history
"image_engine": "GptImage2Tool",
"video_engine": "SeedanceFastVideoGeneratorTool",
"tts_provider": "minimax",

// healing-asmr
"video_engine": "jimeng35pro",
"image_engine": "gemini3_pro",

// food-video / viral-video-breakdown / cinematic-cat-mv
"video_engine": "grok",
"image_engine": "seedream5",

// dance-action
"action_engine": "animate4",

// digital-human
"lip_sync_engine": "wan22",
```

同一个字段，取值既有 Python 类名（`GptImage2Tool`、`SeedanceFastVideoGeneratorTool`），又有短名（`grok`、`seedance5`、`gemini3_pro`、`jimeng35pro`、`animate4`、`wan22`）。两套命名靠 `scripts/capsule_store.py` 里的 `ENGINE_NAME_MAP` 硬桥接。换一个人，只要本地没有这个确切工具（没凭证、没接入），胶囊直接跑不了。

**问题二：注册表里有能力标注，但运行时根本不用。**

`lib/config/tool_registry.yaml` 已经给工具标了 `strengths` / `limits`：

```yaml
Jimeng35ProVideoGeneratorTool:
  strengths: [chinese_prompt, native_audio, chinese_short_video_style]
  limits: {duration_options: [5, 10, 12], aspect_ratios: ["16:9", "9:16", "1:1"]}
SeedanceFastVideoGeneratorTool:
  strengths: [fast_iteration, image_to_video, text_to_video]
```

但这些标注**没有任何选择逻辑去读它**。运行时的工具选择和 fallback 是全局硬编码在 `lib/src/video_generation_config.py`：

```python
VIDEO_ENGINE_FALLBACK_ORDER = ["seedance-fast", "jimeng35pro", "veo3.1", "veo3"]
IMAGE_ENGINE_FALLBACK_ORDER = ["seedream5", "gemini3_pro"]
```

这个顺序跟"胶囊需要什么"、"用户本地有什么"完全无关。

**问题三：注册表本身不完整、不一致。**

`grok` 被 `food-video`、`viral-video-breakdown`、`cinematic-cat-mv` 等多个胶囊使用，但 `tool_registry.yaml` 里根本没有 `GrokVideoGeneratorTool` 条目。能力元数据和实际使用脱节。

**问题四：输出意图散落成一堆裸布尔，没有统一模型。**

胶囊里已经零散存在"成品该长什么样"的描述：

```json
"has_narration": false,
"add_subtitles": false,
"add_background_music": true,
"mode": "mixed",
"lip_sync_engine": "wan22",
```

这些其实就是"输出契约"的雏形，但它们是平铺的布尔、没有结构、各胶囊字段集还不一样（有的有 `has_narration`，有的没有），无法被统一的逻辑消费。

### 1.2 目标

让胶囊只存储**风格 + 制作工艺 + 输出意图**，把"具体用哪个模型"彻底抽离出去。换个人、换一套工具，只要本地工具的**能力**能满足胶囊的**需求**，就能跑出符合作品特色的成品。

**这是本项目区别于其他视频生成项目的核心价值：分享的不是"死配方"（写死某个模型，换台机器就跑不起来），而是"活配方"——能在每个人各自异构的本地环境里自适应跑通。** 项目开源后，跨用户的胶囊移植会**立刻**成为高频场景：任何人下载他人发布的 `.capsule.zip`，本地工具、凭证、接入的模型都和作者不同。没有这套抽象，每个分享出去的胶囊对"缺作者那套确切工具"的人都是**开箱即死**；有了它，体验变成**开箱即用 + 透明告知**（"你没有作者用的工具，但你的 X 能力满足，已自动替代；以下维度会降级，确认后开跑"）。**这条线直接决定开源后的首次体验和采纳率，不是锦上添花。**

本期目标范围：
- 胶囊与具体工具/模型彻底解耦（能力撮合，而非死绑）。
- **跨用户、跨工具集的胶囊可移植**——本期核心，开源即生效。
- 运行前能力审视（Preflight）：生成前就确定"能不能做、用什么做、哪里降级"。

非目标（本期不做）：托管式共享后端、胶囊市场、计费、账号体系等**中心化基础设施**。
**注意区分**：被推迟的只是上述"托管/市场/计费"这类中心化设施；**基于文件分发（`.capsule.zip`）的可移植性本身不在推迟之列，它正是本期要交付的核心**。设计仍要为未来的中心化共享留好接口。

---

## 2. 核心设计：三个分离的概念

整套设计建立在三个**严格分离**的概念上。这是全文最重要的部分。

| 概念 | 谁声明 | 回答什么问题 | 例子 |
|---|---|---|---|
| **Capability（能力）** | 工具/模型 | "我能做什么" | `native_audio: true`、`text_rendering: reliable` |
| **Output Contract（输出契约）** | 胶囊 | "成品每条轨道/图层应该长什么样" | `voice: unified_tts`、`clip_audio: silent` |
| **Adapter（适配器）** | 每个工具一份 | "给定契约 + 我的能力，具体怎么做" | 引擎能出声但契约要静音 → 注入负向提示 + 后期 mute |

### 2.1 为什么能力不能直接决定流程

一个直觉的错误设计是：「引擎能原生出声 → 就跳过 TTS 步骤」。这是错的。

反例：如果一个作品的**特色就是统一 TTS 配音 + 多段视频拼接**，那么即使某段视频引擎能出声，也不该让它出声——正确做法是 prompt 里禁止对话/说话、只保留环境音效，或者直接 mute 这段的音轨。决定流程的是**胶囊的意图**，不是**工具的能力**。

所以：**胶囊声明 Output Contract（意图），工具声明 Capability（事实），Adapter 负责把两者撮合，让固定的流水线总是收敛到契约。** 能力差异被 Adapter 吸收，胶囊永远不为某个具体工具写分支。

### 2.2 撮合表（reconcile）示例

音频维度（对应 §1.1 问题四的 `has_narration` 等裸布尔）：

| 胶囊 clip_audio 意图 | 工具 native_audio | Adapter 动作 |
|---|---|---|
| `silent`（统一 TTS 作品） | 有 | 负向提示「无对话/说话」+ 后期 mute/剥离人声，可保留环境音效 |
| `silent` | 无 | 无需处理 |
| `native`（如 ASMR 作品） | 有 | 直接使用，requires 满足 |
| `native` | 无 | requires **不满足** → 该工具淘汰 |

画面文字维度（证明撮合模型通用）：

| 胶囊 on_frame_text 意图 | 工具 text_rendering | Adapter 动作 |
|---|---|---|
| `required` | `reliable` | 直接在图里渲染文字 |
| `required` | `unreliable`（会乱码） | 文字降级走后期字幕/叠加层 |
| `none` | 任意 | 无需处理 |

当前实现状态：音频维度已经接入真实运行时（prompt 负向约束 + 拼接前静音）；画面文字维度只做 Preflight 校验。因为图片生成运行时还没消费 image directive，后期 overlay 也缺少明确文字源，`on_frame_text: required` 目前会被 blocked，避免系统假装完成未执行的契约。

关键结论：别人换了工具，**Contract 不变**，只是走了不同 Adapter 分支，产出仍符合作品特色。

---

## 3. 分层架构

对应 §0 的三个角色，把职责展开成 5 层：

```
胶囊「要什么」
  L3  胶囊定义        *.capsule               Style + Method + Roles + Output Contract

工具「能做什么」
  L1  能力词表        capabilities.yaml        合法能力取值（地基，受控）
  L2  工具能力        tool_capabilities.yaml   每个工具 provides / limits / requires_env

运行时「对上 + 执行」
  L4  Resolver                                按能力撮合工具 + 自动 fallback
  L5  Adapter（每工具一份）                     把 Output Contract 翻成执行指令；流水线固定
```

### L1 — 能力词表（capabilities.yaml）

**这是整套方案成败的关键。** tag 必须是受控词表，不能自由书写。如果 A 写 `有声音`、B 写 `native_audio`、C 写 `带音频`，"类似匹配"就彻底崩了。

词表按模态分维度，每个维度给出合法枚举值，并带版本号（新增能力需要升版本，方便检测旧胶囊）。

```yaml
# lib/config/capabilities.yaml
version: 1

modalities:
  image:
    # 布尔能力
    flags:
      text_to_image: "文生图"
      image_to_image: "图生图（参考图）"
      character_reference: "角色一致性参考"
    # 枚举能力
    enums:
      text_rendering: [reliable, partial, unreliable]   # 画面内文字渲染可靠度
      prompt_language: [zh, en, both]
    tags:                                                # 软性特征，用于打分
      - high_quality
      - realistic_photo
      - ink_wash_friendly
      - style_reference

  video:
    flags:
      text_to_video: ""
      image_to_video: ""
      first_last_frame: "首尾帧转场"
      native_audio: "原生音频（人声/音效/音乐）"
    enums:
      emotion_expressiveness: [low, medium, high]        # 情绪表现力，如 seedance 系
    limits:                                              # 数值约束，硬过滤用
      duration_options: int_list
      aspect_ratios: str_list
    tags:
      - fast_iteration
      - cinematic
      - chinese_short_video_style
      - paper_theater_motion

  voice:        # TTS
    enums:
      lang: [zh-CN, en-US, ja-JP, ...]
      gender: [male, female, neutral]
      age: [child, young, middle, senior]
      tone: [calm-narration, energetic, dramatic, asmr-whisper, ...]

  music:
    flags:
      text_to_music: ""
      stem_separation: ""
    tags: [bgm, cinematic, lofi, ...]

  lip_sync:
    flags:
      image_audio: "图+音对口型"
      video_to_video: "视频对口型"

  action_transfer:
    flags:
      single_person: ""
      multi_person: ""
      dance: ""

# Output Contract 字段的合法取值也在这里定义，保证胶囊侧和工具侧用同一套词
output_contract_vocab:
  clip_audio: [native, silent, sfx_only]
  voice: [unified_tts, per_clip_native, none]
  on_frame_text: [required, none]
  subtitle: [burned, overlay, none]
  bgm: [external, none]
```

### L2 — 工具能力描述（tool_capabilities.yaml）

合并并扩展现有的 `tool_registry.yaml` + `video_engines.yaml`。每个工具：声明它 `provides` 的能力（取值必须来自 L1）、软性 `tags`、`limits`、以及运行所需的环境变量 `requires_env`（与 `lib/config/env_registry.json` 对齐，作为"本地是否可用"的判据）。

```yaml
# lib/config/tool_capabilities.yaml
version: 1

tools:
  SeedanceFastVideoGeneratorTool:
    module: custom_tools.video_generation.seedance_video_generator_tool
    modality: video
    provides:
      flags: {text_to_video: true, image_to_video: true, native_audio: false}
      enums: {emotion_expressiveness: high}
      limits: {duration_options: [5, 10], aspect_ratios: ["16:9", "9:16", "1:1"]}
    tags: [fast_iteration]
    requires_env: [JULING_API_KEY, JULING_BASE_URL]
    cost_tier: low

  Jimeng35ProVideoGeneratorTool:
    module: custom_tools.video_generation.jimeng35pro_video_generator_tool
    modality: video
    provides:
      flags: {text_to_video: true, image_to_video: true, native_audio: true}
      enums: {emotion_expressiveness: medium}
      limits: {duration_options: [5, 10, 12], aspect_ratios: ["16:9", "9:16", "1:1"]}
    tags: [chinese_short_video_style]
    requires_env: [JULING_API_KEY, JULING_BASE_URL]
    cost_tier: medium

  GptImage2Tool:
    module: custom_tools.image_generation.seedream5_image_generator_tool
    modality: image
    provides:
      flags: {text_to_image: true, image_to_image: true, character_reference: true}
      enums: {text_rendering: reliable, prompt_language: both}
    tags: [high_quality, realistic_photo]
    requires_env: [JULING_API_KEY, JULING_BASE_URL]

  # 注意：grok 当前被多个胶囊使用但 tool_registry.yaml 里缺失，迁移时必须补齐
  GrokVideoGeneratorTool:
    module: custom_tools.video_generation.<TODO>
    modality: video
    provides: {flags: {...}, limits: {...}}
    requires_env: [GROK_API_KEY]      # 待确认实际 env key
```

注：单一职责。一个工具一个 modality。`UniversalTTSTool`、`MinimaxTTSTool` 等都各自声明 `voice` 维度的 `provides`（TTS 走 provider + voice catalog 两级，见 §7 决策一）。

### L3 — 胶囊定义（新格式）

胶囊砍掉所有 `*_engine` 死绑字段，改为四块：

1. `style` — 风格契约（沿用现有 `style_contract` / `default_style` / `quality_profile`）
2. `method` — 制作工艺（沿用现有 `method` / `quality_rules` / 各种 `*_rules`）
3. `roles` — 各角色的能力**需求**（替代死绑）
4. `output_contract` — 成品意图（替代散落的裸布尔）

`roles` 每个角色三档：
- `requires`：硬约束，不满足则该工具淘汰（取值来自 L1）
- `prefers`：软偏好，用于在候选里打分排序（取值来自 L1 tags/enums）
- `validated_with`：可选 provenance，记录作者当初调通用的工具，**仅供复现与"替代产出"标记，不参与合约**

以 `guofeng_history` 为例，从死绑改造为新格式：

```yaml
# capsules/guofeng_history/capsule.yaml
name: guofeng_history
display_name: 古风历史人物讲解视频
capabilities_version: 1          # 锚定 L1 词表版本

style:
  default_style: strong_shuimo_ink_guoman_anime
  quality_profile: strong-shuimo-ink-guoman-story-v5
  style_contract:
    required: [宣纸留白, 湿墨晕染, 断笔边缘, 黑灰分层墨色, 克制矿物色点缀]
    forbidden: [真人风, 真实古装剧质感, 过度真实电影光, 同角度人物肖像复用]

method:
  workflow_template: culture_v1
  target_duration_max: 60
  quality_rules: [...]           # 沿用现有 quality_rules

roles:
  image:
    requires: [image_to_image]                       # 必须支持参考图（脸部一致性）
    prefers:  [ink_wash_friendly, high_quality]
    prefers_enums: {prompt_language: zh}
    validated_with: GptImage2Tool
  video:
    requires: [image_to_video]
    prefers:  [paper_theater_motion]
    prefers_enums: {emotion_expressiveness: high}
    validated_with: SeedanceFastVideoGeneratorTool
  voice:
    requires_enums: {lang: zh-CN}
    prefers_enums: {gender: male, age: middle, tone: calm-narration}
    validated_with: minimax/Chinese_deep_voiced_male_vv1

output_contract:
  clip_audio: silent          # 视频段静音
  voice: unified_tts          # 统一 TTS 配音（作品特色）
  on_frame_text: none         # 画面内不放文字
  subtitle: overlay           # 后期叠加字幕（transparent_png_inkwash_gold_v7）
  bgm: external
```

对比 ASMR 胶囊（说明 output_contract 如何表达不同作品特色）：

```yaml
# healing-asmr
roles:
  video:
    requires: [native_audio]          # 原生音频是这个作品的核心，硬需求
output_contract:
  clip_audio: native                  # 要保留原生音效
  voice: none
  bgm: none
```

同一套字段，`guofeng` 用 `clip_audio: silent` + `requires: image_to_video`，ASMR 用 `clip_audio: native` + `requires: native_audio`——意图差异完全由契约表达，由能力满足。

### L4 — Resolver（撮合器）

输入：胶囊的 `roles` + L2 工具能力库 + 本地环境（哪些 env key 有值）。
输出：每个角色一个**有序候选链**（首选 + 自动 fallback）+ 替代标记。

算法（每个 role 独立执行）：

```
1. 取该 role 的 modality，从 L2 取出所有同 modality 工具
2. 可用性过滤：requires_env 的所有 key 在本地 .env 都有值
3. requires 硬过滤：工具 provides 必须满足 role 的所有 requires / requires_enums / limits
   （limits 检查举例：胶囊 aspect_ratio=9:16 必须 ∈ 工具 limits.aspect_ratios）
4. forbids 过滤（若胶囊声明了 forbids 标签）：命中即淘汰
5. 打分排序：对 prefers / prefers_enums 命中数加权求和；同分时 validated_with 优先，仍同分再用 cost_tier 兜底
6. 排序结果即 fallback 链。若链为空 → 明确报错（缺能力 X），不静默降级
7. 若最终选中的不是 validated_with 指定的工具 → 标记 substituted=true → 触发质检
```

这一层**取代**了 `video_generation_config.py` 里的全局 `*_FALLBACK_ORDER`：fallback 不再是写死的全局顺序，而是"按胶囊需求 + 本地可用性"动态算出来的。

### L5 — Adapter 层

每个工具一份 Adapter，实现统一接口，把 Output Contract 翻译成该工具的具体执行指令。流水线 DAG 固定，变化点收敛在 Adapter 内。

```python
# 接口草图
class ToolAdapter(Protocol):
    def reconcile(self, contract: OutputContract, role_input: RoleInput) -> ExecutionDirective:
        """给定输出契约 + 角色输入，产出具体执行指令（prompt 注入 / 后处理步骤等）。"""

@dataclass
class ExecutionDirective:
    prompt_additions: list[str]       # 注入正向提示
    prompt_negatives: list[str]       # 注入负向提示（如 "no speech, no dialogue"）
    post_steps: list[PostStep]        # 后处理（mute / strip_audio / overlay_subtitle / ...）
    notes: list[str]                  # 替代/降级说明，进质检报告
```

示例：Seedance（无原生音频）和 Jimeng（有原生音频）面对同一个 `clip_audio: silent` 契约：

```python
# JimengAdapter.reconcile(contract={clip_audio: silent}, ...)
#   -> prompt_negatives += ["no speech", "no dialogue", "no singing"]
#      post_steps += [MuteAudioTrack()]        # 兜底剥离
#      notes += ["引擎原生有声，按契约 silent 已静音处理"]

# SeedanceAdapter.reconcile(contract={clip_audio: silent}, ...)
#   -> 无操作（本就不出声）
```

两者最终都收敛到「静音视频段」，下游统一 TTS + 拼接逻辑完全一致。

---

## 4. 运行前能力审视与作品规划（Preflight）

在胶囊真正开始生成之前，必须先有一步**自动审视本地环境、据此制定本作品的执行规划**。这是把 L1–L5 在运行时串起来的编排层，落地为一个独立 skill（暂名 `capsule-preflight`），也是 §1.2 "可移植"目标的最后一块。

没有这一步，胶囊会在生成到一半时才发现某个工具不可用，浪费时间和算力。Preflight 把"能不能做、用什么做、哪里会降级"全部提前到生成之前确定。

### 4.1 流程

```
1. 环境扫描：读取 L2 工具能力库 + 本地 .env(env_registry)，
            算出"本地可用工具快照"——requires_env 全部有值的工具
2. 健康探活（可选）：对可用工具做轻量 ping / 余额检查，剔除接入了但实际不可用的
3. 逐 role 撮合：用快照跑 Resolver(L4)，得到每个 role 的选中工具 + fallback 链
4. 分类每个 role 的结果：
     ok        选中了 validated_with 同一工具
     substituted  选了合法替代工具（能力满足，非原作者工具）
     degraded     触发了 output_contract 里显式允许的降级（见 §7 决策四）
     blocked      某 requires 无任何本地工具满足，且无 fallback
5. 若存在 blocked → 立即失败，给可执行的提示
     （"本作品需要具备 native_audio 的视频工具，本地可用工具均不满足；
       请接入以下之一：Jimeng35ProVideoGeneratorTool(JULING_API_KEY) ..."）
6. 否则产出执行规划 + 审视报告，substituted/degraded 项需用户确认后再生成
7. 把规划交给固定流水线执行；substituted/degraded 进质检关注项
```

### 4.2 产出物

Preflight 产出两个 artifact，落到 session 目录：

`preflight_report.json` —— 给人看的审视结论：

```json
{
  "capsule": "guofeng_history",
  "capabilities_version": 1,
  "local_snapshot": { "available_tools": ["SeedanceFastVideoGeneratorTool", "GptImage2Tool", ...] },
  "roles": {
    "image": { "selected": "GptImage2Tool", "status": "ok", "fallback": ["Seedream5ImageGeneratorTool"] },
    "video": { "selected": "Jimeng35ProVideoGeneratorTool", "status": "substituted",
               "validated_with": "SeedanceFastVideoGeneratorTool",
               "note": "原作者工具不可用，已替代；jimeng 原生有声，按契约 clip_audio=silent 将注入负向提示+mute" },
    "voice": { "selected": "minimax/Chinese_deep_voiced_male_vv1", "status": "ok" }
  },
  "degradations": [],
  "blocked": [],
  "requires_confirmation": true
}
```

`execution_plan.json` —— 给流水线吃的规划：把胶囊的 `style`/`method` 实例化，绑定每个 role 的选中工具 + Adapter 产出的 `ExecutionDirective`（prompt 注入、后处理步骤）。

### 4.3 与现有契约的衔接

复用 `lib/src/contracts/production_contract.py` 的 `validate_preflight_contract`：把它从"校验输入是否匹配 promise"扩展成"校验本地能力是否满足胶囊 roles"，blocked 即校验失败。Preflight 是这个契约校验的运行时入口。

---

## 5. 数据流（端到端）

```
胶囊(L3 roles + output_contract)
        │
        ▼
Preflight(§4) ── 环境扫描 → 本地可用工具快照
        │
        ▼
Resolver(L4) ──读── 工具能力库(L2) ──校验── 能力词表(L1)
        │           本地 .env(env_registry)
        ▼
每个 role: [选中工具, fallback 链, status: ok/substituted/degraded/blocked]
        │
        ├─ blocked → 立即失败（可执行提示，不进入生成）
        ▼
Adapter(L5).reconcile(output_contract) → ExecutionDirective
        │
        ▼
preflight_report.json + execution_plan.json（substituted/degraded 需确认）
        │
        ▼
固定流水线执行（图 → 视频 → 音频 → 后处理 → 拼接）
        │
        ▼
若 substituted 或发生降级 → 标记进质检(VideoQualityCheckerTool)
```

---

## 6. 迁移计划（一次性，破坏式）

项目未上线，不保留旧格式、不做兼容 shim。Resolver 不需要 legacy 分支。

落地顺序（建议每步独立提交，可独立验证）：

1. **L1 能力词表**：新建 `lib/config/capabilities.yaml`，定义各模态维度 + output_contract_vocab。先和团队对齐枚举值。
2. **L2 工具能力库**：把 `tool_registry.yaml` + `video_engines.yaml` 合并扩展成 `tool_capabilities.yaml`，补齐缺失工具（尤其 `grok`），统一命名（彻底废弃 `ENGINE_NAME_MAP` 双命名，全部用类名）。
3. **L4 Resolver**：实现撮合算法，写单元测试覆盖：硬过滤、limits 校验、打分排序、空链报错、substituted 标记。
4. **L3 胶囊迁移**：写一次性脚本，把 `video_workflow_online_capsule_reference.json` 里所有胶囊从死绑 `*_engine` + 裸布尔，转成 `roles` + `output_contract`。转完删除旧字段，源码不留旧格式痕迹。
5. **L5 Adapter**：先实现音频维度（`clip_audio`/`native_audio` 撮合）并接入运行时；画面文字维度（`on_frame_text`/`text_rendering`）先做能力校验与 blocked 报告，等图片 prompt directive 或后期 overlay 文字源接入后再开放执行。
6. **Preflight skill**：实现 `capsule-preflight`（§4）——环境扫描 + 调 Resolver + 产出 `preflight_report.json`/`execution_plan.json` + blocked 即失败。扩展 `production_contract.validate_preflight_contract` 做能力校验。
7. **清理与运行时重连**：删除 `video_generation_config.py` 的全局 `*_FALLBACK_ORDER`，运行时改为调用 Preflight → Resolver。`capsule_store.py` 不再暴露 `ENGINE_NAME_MAP`，SQLite 新建合同默认使用 `roles` + `output_contract`；旧 `image_engine`/`video_engine`/TTS 布尔字段只在仓库导入与旧行迁移边界转换为新合同，短名映射也只保留为 legacy alias，不继续污染新格式胶囊。

迁移完成的验收标准：把 `guofeng_history` 的 `validated_with` 工具的 env key 在本地清空，Resolver 应自动选到合法替代工具并标记 `substituted`，成品仍符合 output_contract（静音段 + 统一 TTS + 叠加字幕）。

---

## 7. 决策（已定）

### 决策一：TTS/voice 走「provider + voice catalog」两级

工具能力库（L2）里 TTS provider 只声明它**支持哪些 voice 维度**（lang/gender/age/tone 的可选集合）。具体 voice 放进一份独立的 voice 目录：

```yaml
# lib/config/voice_catalog.yaml
version: 1
voices:
  minimax/Chinese_deep_voiced_male_vv1:
    provider: minimax
    requires_env: [MINIMAX_API_KEY]
    lang: zh-CN
    gender: male
    age: middle
    tone: calm-narration
  doubao/zh_male_sunwukong_mars_bigtts:
    provider: doubao
    requires_env: [DOUBAO_TTS_APPID, DOUBAO_TTS_TOKEN]
    lang: zh-CN
    gender: male
    age: young
    tone: dramatic
```

Resolver 解析 voice role：先按 `requires_env` 过滤掉本地没凭证的 voice，再按 `requires_enums`（如 `lang: zh-CN`）硬过滤，最后按 `prefers_enums`（gender/age/tone）打分选具体 voice。`validated_with` 可锚定到具体 voice id 做复现。

理由：minimax 一个 provider 下有几百个 voice，维度匹配必须落到 voice 粒度；但 provider 级的接入/凭证又是 provider 粒度。两级正好分别承接。这个模式未来也能复用到 image/video 的「风格预设」。

### 决策二：prefers 等权（本期），保留加权语法

本期所有 `prefers` 命中等权（每项权重 1），打分 = 命中数，平手用 `cost_tier` 兜底（低成本优先）。

保留向前兼容的加权写法，Resolver 读到时 `weight` 缺省为 1：

```yaml
prefers: [ink_wash_friendly, high_quality]                    # 本期形态
prefers: [{tag: ink_wash_friendly, weight: 3}, high_quality]  # 保留，暂不强制
```

理由：等权实现简单、行为可预测；真出现"某偏好压倒性重要"再开加权，避免过早引入调参复杂度。

### 决策三：能力先人工标注，预留能力探针

L2 每个工具加 `capability_source` 字段，本期一律 `manual`。`substituted`/`degraded` 触发质检（`VideoQualityCheckerTool`）作为标注不准的兜底。

后期引入"能力探针"：每个能力 flag 配一个 fixture 测试（如 `text_rendering` 探针 = 用已知文字生成图 → OCR 比对），定期跑、自动回填 `capability_source: probe@<date>` 并报告漂移。探针接口本期先留空壳，不实现。

```yaml
GptImage2Tool:
  provides: {...}
  capability_source: manual        # 后期可变 probe@2026-08-01
```

### 决策四：降级必须胶囊显式授权

每个可降级的 output_contract 维度都配一个 `<dim>_fallback`，取值含 `fail`。Resolver/Adapter **只在显式授权时降级**，否则按 blocked 处理、硬失败并给提示。

```yaml
output_contract:
  on_frame_text: required
  on_frame_text_fallback: overlay     # 允许降级到后期叠加；写 fail 则不允许，直接报错
  clip_audio: silent
  # clip_audio 无 fallback 字段 → 不允许降级
```

理由：降级会改变成品观感，是否可接受是作品作者的判断，不能由系统静默决定。`fail` 让作者能强制"宁可不做也不降级"。

### 决策五：能力词表同步 + 迁移映射

胶囊和工具库都锚定 `capabilities_version`，且必须**锁步**：词表升版本时，工具库与胶囊一并迁移，不允许混用。

升版本要交付两样东西：

```yaml
# lib/config/capabilities_migrations/v1_to_v2.yaml
renames:   { emotion_expressiveness: emotion_level }   # 改名
merges:    { [native_audio, native_voice]: native_audio }  # 合并
splits:    { ... }
removed:   [ deprecated_tag ]                           # 移除（命中即告警）
```

外加一个 validator CLI：升级胶囊/工具库到新版本、对无法映射的 tag 报错。Preflight 启动时校验 `capabilities_version` 与本地词表一致，不一致拒跑并提示先迁移。

理由：能力词表是所有人共享的"协议"，必须强一致；同步 + 自动迁移映射，避免协议漂移导致的静默错配。

**落地分期（与 §1.2 一致）**：词表是跨用户协议，**v1 词表 + 扩展治理规则（谁拥有词表、贡献者如何提议新枚举、新工具合入门槛）必须在开源前就位**——这是开源后众多贡献者能互通的前提。而上面的迁移工具链（migration YAML + validator CLI）是 **fast-follow**：在词表真正开始演进、出现第一次升版本需求时再补，不阻塞首发。

### 决策六：跨模态用 role 级 `depends_on`，拓扑序解析

role 可声明 `depends_on`，Resolver 按依赖拓扑序解析，被依赖 role 的选中结果作为约束传入；Adapter 负责校验产物兼容性。

```yaml
roles:
  image: { requires: [...] }
  lip_sync:
    requires: [image_audio]
    depends_on: [image]              # image 先解析，其产出供 lip_sync 校验
    compatible_with: {image: any}    # 预留：限定可配对的上游工具
```

理由：现有胶囊（`digital-human`、`cinematic-cat-mv`）确实存在 lip_sync 依赖 image 产出的耦合，`depends_on` 是满足这些胶囊的最小机制。更复杂的"工具对必须同源"约束用 `compatible_with` 预留接口，本期不实现。

---

## 8. 附录：现有相关文件索引

- 胶囊参考数据：`capsules/video_workflow_online_capsule_reference.json`
- 工具注册表（待合并）：`lib/config/tool_registry.yaml`、`lib/config/video_engines.yaml`
- 全局 fallback（待删除）：`lib/src/video_generation_config.py`
- 旧双命名迁移边界：`scripts/capsule_store.py` 的 `LEGACY_TOOL_NAME_ALIASES`
- 环境变量注册表：`lib/config/env_registry.json`、`lib/.env.example`
- 现有契约：`lib/src/contracts/storyboard_contract.py`、`lib/src/contracts/production_contract.py`
- 运行时：`lib/src/runtime/general_video_crew/{image_generator,video_generator,post_processor,scene_regenerator}.py`
- 质检：`lib/custom_tools/quality_check/video_quality_checker_tool.py`
