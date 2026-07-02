<div align="center">

# Capsule Cinema 胶囊影厂

**把一次跑通的 AI 视频流程，沉淀成可复用的视频配方。**

面向持续做短视频的人和团队。Capsule Cinema 不只生成一条视频，而是把可复用的选题结构、分镜节奏、工具路线、质量规则和返工经验保存成可迁移的 Capsule。

<p>
  <a href="./README.en.md">English</a> ·
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-PolyForm%20Noncommercial-111827.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/video-recipes-0EA5E9.svg" alt="Video recipes">
  <img src="https://img.shields.io/badge/custom-tools-14B8A6.svg" alt="Custom tools">
  <img src="https://img.shields.io/badge/local-QA-F97316.svg" alt="Local QA">
</p>

<p>
  <a href="#demo">Demo</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#为什么需要-capsule-cinema">为什么需要</a> ·
  <a href="#核心能力">核心能力</a> ·
  <a href="#视频配方">视频配方</a> ·
  <a href="#自定义工具">自定义工具</a> ·
  <a href="#架构">架构</a> ·
  <a href="#社群">社群</a>
</p>

<img src="docs/assets/readme-hero.svg" width="100%" alt="Capsule Cinema 从 brief 到 release package 的工作流">

</div>

Capsule Cinema 适合那些需要反复做同一类视频的人：每次换主题、素材或文案，但保留已经验证过的结构。它把创作过程拆成可审的分镜、可替换的工具能力、可复用的 Capsule 包和本地 QA 交付物。

## Demo

这些样片来自内置起步配方。它们展示了 Capsule Cinema 能覆盖的栏目、商品、艺术动效和风格化短片方向，并标注了对应的英文胶囊名。

<table>
  <tbody>
    <tr>
      <td width="62%" valign="top">
        <video width="100%" controls src="https://github.com/user-attachments/assets/d81e88b3-a567-4835-9784-c2a65f4fe977"></video>
      </td>
      <td width="38%" valign="top">
        <strong>人生模拟短剧</strong>
        <br>
        对应胶囊：<code>life_sim</code>
        <br><br>
        面向打工人剧情、生活共情、动漫口播和多场景快切。
        <br><br>
        适合强钩子开场、连续情绪推进、统一 TTS 节奏和系列化栏目。
      </td>
    </tr>
  </tbody>
</table>

<table width="100%">
  <tbody>
    <tr>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/c7722195-0c14-4478-aeb8-b5e950518669"></video>
        <br>
        <strong>电商商品展示</strong>
        <br>
        对应胶囊：<code>ecommerce_product_showcase</code>
        <br>
        卖点拆解、场景演示、商品种草和带货短视频。
      </td>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/5fff44fe-97e5-41e4-a966-2c8565926d89"></video>
        <br>
        <strong>艺术图像动效</strong>
        <br>
        对应胶囊：<code>art_motion</code>
        <br>
        插画、海报、首尾帧和风格化图像的视频化。
      </td>
    </tr>
    <tr>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/b5c672be-cacb-4877-a688-e6d7baa1a3b5"></video>
        <br>
        <strong>国风历史文化讲解</strong>
        <br>
        对应胶囊：<code>guofeng_history</code>
        <br>
        国风视觉、历史故事、文化知识和口播解释短片。
      </td>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/59f4c71c-9634-4b9f-8b48-e47f7a7c1d5f"></video>
        <br>
        <strong>羊毛毡 ASMR 手作</strong>
        <br>
        对应胶囊：<code>felt_asmr</code>
        <br>
        羊毛毡烘焙、毛绒食物、治愈手作和风格化 ASMR。
      </td>
    </tr>
  </tbody>
</table>

## Quick Start

把仓库安装为 OpenClaw skill 后，不需要自己执行脚本。直接把目标、素材、风格和限制说清楚；Capsule Cinema 会根据你的意图选择合适的分镜、配方、工具路线和 QA 交付流程。

> 用 Capsule Cinema 做一个 30 秒竖屏短视频，主题是 `<主题>`，目标观众是 `<人群>`，风格要 `<风格>`。

可以直接点名这些内置胶囊：

| 胶囊名 | 适合做什么 |
| --- | --- |
| `life_sim` | 人生模拟、打工人剧情、共情口播 |
| `ecommerce_product_showcase` | 商品展示、卖点演示、种草短视频 |
| `art_motion` | 艺术图像动态化、首尾帧短片 |
| `guofeng_history` | 国风历史文化讲解 |
| `felt_asmr` | 羊毛毡、软萌食物、ASMR 手作 |

常见启动方式：

| 目标 | 直接这样说 |
| --- | --- |
| 先看方案 | “先只生成分镜，不要生成图片、视频和配音。主题是 `<主题>`，我确认后再继续制作。” |
| 做完整成片 | “用 Capsule Cinema 做一个 30 秒竖屏视频，主题是 `<主题>`，目标观众是 `<人群>`，风格是 `<风格>`。” |
| 指定胶囊 | “请用 `ecommerce_product_showcase` 胶囊做一条商品种草视频，商品是 `<商品>`，卖点是 `<卖点>`。” |
| 局部返工 | “上一版第 3 个分镜不满意，请保留其他部分，只重做这个分镜：`<修改要求>`。” |
| 保存方法 | “这条视频我满意，请把这套结构保存成 `<配方名>`，以后用来做 `<适用场景>`。” |

完成后，Capsule Cinema 会把成片、分镜、时间线、QA、修复建议和发布检查点一起放进本地 workspace，方便继续返工或沉淀配方。

## 为什么需要 Capsule Cinema

一次性 prompt 可以做出一条视频，但很难稳定复用。真正做账号、栏目、产品视频或团队交付时，问题会变成：

| 真实问题 | Capsule Cinema 的做法 |
| --- | --- |
| 每次都要重新想结构 | 把跑通的栏目结构保存进 Capsule |
| 工具供应商更新太快 | 配方声明能力，运行时匹配可用工具 |
| 生成前很难确认方向 | 先产出可审分镜，再进入媒体生成 |
| 一处不满意就要整条重来 | 支持单镜头、BGM、字幕、拼接局部返工 |
| 成片能不能交付靠肉眼 | 生成本地 QA、修复建议和 release checkpoint |
| 参考视频容易变成照搬 | 先分析结构、节奏、风格和音频策略，再生成胶囊草稿 |

## 核心能力

<img src="docs/assets/readme-workflow.svg" width="100%" alt="Capsule Cinema 工作流">

| 你想做的事 | Capsule Cinema 怎么帮你 |
| --- | --- |
| 从一句需求开始做视频 | 把主题、人群、风格和素材拆成分镜、画面、视频、音频和剪辑流程 |
| 先看方案再生成 | 可以只出分镜，确认后再继续生成图片、视频、配音和字幕 |
| 局部返工 | 只重做某个镜头、只换 BGM、只重拼已有素材，不必整条视频重来 |
| 稳定做同一类内容 | 把跑通的流程保存成视频配方，复用结构、节奏、风格和质检规则 |
| 学习参考视频 | 分析镜头节奏、文案结构、视觉风格和音频策略，先生成胶囊草稿，确认后再写入配方 |
| 接入自己的工具 | 让配方描述需要的能力，运行时匹配图像、视频、TTS、BGM、字幕、剪辑和质检工具 |
| 判断能不能发布 | 生成本地 QA、质量评分、修复建议和发布检查点 |

## 视频配方

Capsule 不是成片，而是一套可迁移的视频工作流。它保存一类视频的不变量：适用场景、输入要求、分镜结构、视觉风格、音频策略、工具路线、质量规则、返工经验和安全边界。

<img src="docs/assets/readme-capsule-anatomy.svg" width="100%" alt="Capsule 包结构">

项目内置了这些 starter capsules：

| Capsule | 适合做什么 | 执行方式 |
| --- | --- | --- |
| `life_sim` | 人生模拟、打工人剧情、共情口播 | local script |
| `ecommerce_product_showcase` | 商品展示、卖点演示、种草短视频 | preset |
| `art_motion` | 艺术图像动态化、首尾帧短片 | local script |
| `guofeng_history` | 国风历史文化讲解 | preset |
| `felt_asmr` | 羊毛毡、软萌食物、ASMR 手作 | preset |

配方可以来自三类来源：

- 初始配方：项目内置的种子案例，用来快速上手。
- 个人配方：你从满意作品里沉淀出的账号、品牌或项目经验。
- 社区配方：可以分享、试用和改进的公共创作方法。

复用时只替换主题、素材和当期文案，保留已经验证过的结构。配方不应该保存密钥、cookie、客户资料、私有素材、临时链接或一次性运行产物。

## 自定义工具

AI 视频工具更新很快，所以配方不绑定某个平台。配方只说明需要什么能力，工具声明自己能提供什么能力，运行时负责匹配。

你可以接入这些工具：

| 工具类型 | 用途 |
| --- | --- |
| 图像生成 | 文生图、图生图、风格化、封面图 |
| 视频生成 | 文生视频、图生视频、首尾帧、动作迁移、对口型 |
| 音频生成 | TTS、音色库、BGM、音效、音乐生成 |
| 后期处理 | 字幕、拼接、转码、封面、片头片尾 |
| 质量检查 | 黑屏、画幅、字幕遮挡、声音响度、发布前检查 |

运行前会做凭证检查和能力匹配。工具不可用时，系统会列出替代路线；需要用户确认的降级不会静默执行。

## 架构

Capsule Cinema 是一个 OpenClaw skill，同时包含运行时和制作方法论两层：

| 层 | 路径 | 作用 |
| --- | --- | --- |
| 插件入口 | `index.js` | OpenClaw 输入、环境变量白名单、子进程调度 |
| 脚本入口 | `scripts/` | 分镜、完整视频、局部返工、拼接、QA、胶囊管理 |
| 视频工作流 | `lib/video_workflows/general_video/` | 规划、分镜、素材生成、后期和状态传递 |
| 工具库 | `lib/custom_tools/` | 图片、视频、TTS、BGM、字幕、质检等 provider 封装 |
| 胶囊包 | `capsules/*.capsule/` | 可复用的视频配方、合同、资产、质量规则 |
| 文档方法论 | `references/` | 生产路线、渠道政策、分镜规范、交付标准 |

更完整的运行时说明见 [references/architecture.md](references/architecture.md)。

### 视频能力地图

<img src="docs/assets/readme-capability-map.svg" width="100%" alt="Capsule Cinema 视频能力地图">

## 常用说法

| 想做什么 | 对 AI 这样说 |
| --- | --- |
| 先看分镜 | “先只生成分镜，不要生成图片、视频和配音。主题是 `<主题>`，我确认后再继续制作。” |
| 做完整成片 | “用 Capsule Cinema 做一个 `<时长>` 秒 `<横屏/竖屏>` 视频，主题是 `<主题>`，重点突出 `<价值点>`。” |
| 局部返工 | “上一次视频第 `<编号>` 个分镜不满意，请保留其他部分，只重做这个分镜：`<修改要求>`。” |
| 复用已有素材 | “这些分镜素材已经可以了，请重新拼接，并按新的字幕、BGM 和节奏要求调整最终成片。” |
| 检查能不能发 | “请检查这个成片是否可发布，重点看画面、声音、字幕、时长、语言匹配和配方质检规则。” |
| 保存成配方 | “这条视频我满意，请保存成 `<配方名>`，适合以后做 `<适用场景>`。” |
| 分析参考视频 | “请分析这个本地参考视频 `<视频路径>`，拆出可复用的结构、风格、节奏、文案和质量规则，先生成 `<配方名>` 的胶囊草稿。” |
| 新增工具渠道 | “帮我新增一个 `<工具/渠道名>`，接口文档如下：`<粘贴文档>`。请把它接入 Capsule Cinema，并写一个简单用户示例。” |

## 社群

欢迎通过 [GitHub Issues](https://github.com/JuneYaooo/capsule-cinema/issues) 分享配方想法、运行问题、成片案例或改进建议。

中文开发者社区：[LINUX DO](https://linux.do/)

## License

PolyForm Noncommercial License 1.0.0，详见 [LICENSE](./LICENSE)。
