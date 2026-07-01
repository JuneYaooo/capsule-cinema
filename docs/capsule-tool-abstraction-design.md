# 胶囊与工具能力抽象层

状态: 当前架构合同
最后更新: 2026-06-28

本文描述 Capsule Cinema 当前已经落地的胶囊、工具能力、预检和执行计划边界。它不是迁移草稿，也不是历史数据清单。仓库里的当前胶囊来源只有 `capsules/*.capsule.zip`，每个包的 `manifest.json` 是事实来源。

## 1. 目标

胶囊只表达作品意图和能力需求，工具只声明自己能做什么，运行时负责把两者对上并生成可追溯的执行计划。

核心约束:

- 胶囊不直接依赖某个本地路径、一次性产物或旧数据库导出。
- 胶囊包必须使用短名，例如 `life_sim.capsule.zip`。
- 新格式胶囊使用 `roles` + `output_contract` 表达能力合同。
- 旧字段只允许在导入和迁移边界被读取，然后转换成当前合同。
- Preflight 必须在生成前发现缺失能力、替代工具和阻断项。

## 2. 分层

### L1: 能力词表

文件: `lib/config/capabilities.yaml`

L1 定义合法能力词，包括 flags、enums、limits 和 tags。L2 工具能力声明只能使用 L1 已定义词。新增工具能力时，先扩展 L1，再扩展 L2。

### L2: 工具能力库

文件: `lib/config/tool_capabilities.yaml`

L2 描述每个工具的能力、环境变量需求和成本层级。它回答“这个工具能做什么、需要什么凭证”，不负责直接调用工具。

直接调用入口仍由 `lib/config/tool_registry.yaml` 管理。两者职责不同:

- `tool_capabilities.yaml`: 能力撮合和 preflight。
- `tool_registry.yaml`: 运行时工具名称、模块和批准状态。

### L3: 胶囊合同

来源: `capsules/*.capsule.zip` 内的 `manifest.json`

胶囊的 `config` 必须包含:

- `roles`: 每个制作角色需要的能力，例如 image、video、voice。
- `output_contract`: 成品意图，例如是否静音、是否字幕、是否配音、BGM 策略。

打包胶囊不得保留旧顶层执行字段，例如 `image_engine`、`video_engine`、`has_narration`、`add_subtitles`、`add_background_music`。这些字段只属于迁移输入，不属于当前包格式。

### L4: Resolver

文件: `lib/src/capsule_resolver.py`

Resolver 按 `roles.requires`、本地可用 env、工具能力和 fallback 策略选出可执行工具。它不直接生成视频，只产出选择结果。

### L5: Preflight 和执行计划

文件: `lib/src/capsule_preflight.py`

Preflight 串联 L1-L4，生成:

- `preflight_report.json`: 给人看的能力状态。
- `execution_plan.json`: 给流水线使用的工具选择和 adapter 指令。

任何 blocked role 都必须阻断生成。substituted role 必须显式进入 `needs_confirmation`，不能静默替换。

## 3. L2 工具能力库

每个工具条目必须包含:

- `module`: 对应实现模块。
- `modality`: image、video、voice、action_transfer、lip_sync 等。
- `provides`: 工具提供的 flags、enums、limits。
- `tags`: 非硬性能力标签。
- `requires_env`: 本地运行所需环境变量。
- `cost_tier`: 粗粒度成本等级。

本地校验需要确认 L2 使用的 flags、enums、limits、tags 都来自 L1。这样可以避免工具能力库变成自由文本。

## 4. Preflight 合同

Preflight 输入是一个胶囊合同片段:

```json
{
  "name": "repo_showcase",
  "roles": {
    "image": {
      "requires": ["text_to_image"],
      "validated_with": "GptImage2Tool"
    },
    "video": {
      "requires": ["image_to_video"],
      "validated_with": "Jimeng35ProVideoGeneratorTool"
    }
  },
  "output_contract": {
    "clip_audio": "silent",
    "subtitle": "overlay",
    "bgm": "external"
  }
}
```

Preflight 输出的角色状态只有三类:

- `ok`: 当前已选工具满足要求。
- `substituted`: 原验证工具不可用，但存在能力匹配替代工具。
- `blocked`: 没有可用工具满足能力或输出合同。

命令行入口按胶囊短名读取 `capsules/<name>.capsule.zip`，不读取历史导出文件。

## 5. Adapter 指令

文件: `lib/src/capsule_adapter.py`

Adapter 把 output contract 中的成品要求转换为运行时后处理指令。例如:

- silent contract + 有声视频工具: 添加 `mute_audio`。
- on-frame text required + 不可靠图片工具: 阻断或降级，取决于合同允许的 fallback。
- native audio required + 只能产静音视频的工具: 阻断。

Adapter 不负责选择工具；选择工具属于 Resolver。Adapter 只负责判断“选出来的工具和成品合同是否能兼容”。

## 6. 打包胶囊

当前内置胶囊列表由 `capsules/*.capsule.zip` 决定，README 的内置胶囊表必须和这些包严格一致。

每个胶囊包必须满足:

- 包名、`manifest.capsule.name` 和 README 短名一致。
- 包内不保留旧长名入口。
- `config` 使用 `roles` + `output_contract`。
- preflight 在完整注册 env 集合下为 `ok`。

这些约束需要通过本地校验覆盖，但校验代码不随远端仓库发布。

## 7. 语音目录

文件: `lib/config/voice_catalog.yaml`

语音按 provider + voice id 建模，形式上和工具能力一致:

- `modality: voice`
- `provides.enums`: lang、gender、age、tone
- `requires_env`: provider 凭证

这样 Resolver/Preflight 可以用同一套能力撮合逻辑处理 voice，不需要给 TTS 写特殊分支。

## 8. 迁移边界

旧配置字段只能出现在以下位置:

- `scripts/capsule_store.py`: SQLite 或旧配置导入时转换为当前合同。
- 迁移相关测试: 验证旧输入会被转换，并且不会污染新格式输出。
- 运行时兼容读取: 只允许作为边界处理，不允许成为新包格式。

打包胶囊、README、公开工具文档和 preflight 名称加载不得依赖历史导出数据。

## 9. 质量门

当前架构的质量门:

- `npm test` 必须通过。
- JS 契约测试校验公开文档、胶囊短名、产物布局、运行时边界。
- Python 单元测试校验 resolver、preflight、capsule schema、runtime route 和 QA 合同。
- `py_compile` 覆盖关键脚本，避免语法层面的坏提交。

新增胶囊或工具时，先扩展能力词表和测试，再更新包或实现。
