<div align="center">

# Capsule Cinema

**把一次跑通的方法，变成你自己的短视频工厂。**

Capsule Cinema 是安装到 Coding Agent 中的短视频生产系统。它把栏目结构、分镜规则、生成渠道、质量门和返工经验封装成可迁移、可更新的视频胶囊。下一期只换主题和素材，不必重新搭建整套流程。

<p>
  <a href="./README.en.md">English</a> ·
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-PolyForm%20Noncommercial-111827.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/Agent-Skills-16A34A.svg" alt="Agent Skills">
  <img src="https://img.shields.io/badge/video-capsules-2563EB.svg" alt="Video capsules">
  <img src="https://img.shields.io/badge/targeted-rework-7C3AED.svg" alt="Targeted rework">
  <img src="https://img.shields.io/badge/release-QA-0F172A.svg" alt="Release QA">
</p>

<p>
  <strong>可审分镜 · 自选渠道 · 单镜头返工 · 发布前 QA · 胶囊打包迁移</strong>
</p>

<p>
  <a href="#为什么需要视频胶囊">为什么需要</a> ·
  <a href="#demo">Demo</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#内置视频胶囊">内置胶囊</a> ·
  <a href="#质量门与局部返工">质量与返工</a> ·
  <a href="#使用自己的生成渠道">生成渠道</a> ·
  <a href="#社群">社群</a>
</p>

<img src="docs/assets/readme-hero.svg" width="100%" alt="Capsule Cinema：把一次跑通的视频流程变成可复用胶囊">

</div>

Capsule Cinema 面向持续运营账号、制作栏目或商品视频的创作者和团队。它更适合中文短视频生产场景，仓库内置抖音感剧情、商品种草、国风讲解等起步胶囊。

它不是网页式一键生成器，也不提供模型算力。项目运行在用户自己的 Agent 和本地工作区中，媒体生成使用用户配置的 API。当前公开渠道主要围绕 Seedream、Seedance、MiniMax、豆包语音和本地 FFmpeg。

## 为什么需要视频胶囊

一次性 prompt 可以做出一条视频，但很难稳定地做下一期。视频胶囊保存一类视频中已经验证过的部分，让新的主题继续沿用同一套生产方法。

| 常见的一次性做法 | Capsule Cinema |
| --- | --- |
| 每次重新解释栏目结构 | 复用已经确认的分镜机制、节奏和视觉规则 |
| 生成前很难确认方向 | 先审分镜，再试一个代表镜头，然后继续生成 |
| 一个镜头有问题就整条重做 | 只返工指定镜头、配音、字幕、BGM 或拼接结果 |
| 有 MP4 就当作完成 | 检查画幅、黑帧、响度、字幕、安全区和交付物 |
| 工具不可用时临时换一条路线 | 展示替代渠道及影响，改变交付效果时等待确认 |
| 成功经验留在聊天记录里 | 回写到胶囊，经过校验后再用于下一期 |
| 流程只能留在当前机器 | 打包胶囊，在另一台机器或团队环境中安装 |

<img src="docs/assets/readme-workflow.svg" width="100%" alt="Capsule Cinema 从需求到经验回写的生产闭环">

视频胶囊是可安装、可迁移的生产包，视频配方是胶囊内部保存的制作方法。一个胶囊通常包含：

```text
视频胶囊
= 输入与使用边界
+ 分镜、视觉和音频配方
+ 工具能力要求
+ 质量门与发布检查
+ 经过验证的返工经验
```

## Demo

这些样片来自内置起步胶囊，对应的胶囊包随公开仓库提供。你可以保留已经跑通的结构和质量规则，只替换主题、素材、商品或当期文案。

<table>
  <tbody>
    <tr>
      <td width="62%" valign="top">
        <video width="100%" controls src="https://github.com/user-attachments/assets/d81e88b3-a567-4835-9784-c2a65f4fe977"></video>
      </td>
      <td width="38%" valign="top">
        <strong>人生模拟短剧</strong>
        <br>
        胶囊：<code>life_sim</code>
        <br><br>
        面向打工人剧情、生活共情、动漫口播和系列化栏目。
        <br><br>
        胶囊保存第二人称叙事、钩子结构、情绪推进、角色一致性、镜头节奏和 TTS 规则。
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
        胶囊：<code>ecommerce_product_showcase</code>
        <br>
        商品身份锚定、卖点顺序、场景展示、口播节奏和合规规则。
      </td>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/5fff44fe-97e5-41e4-a966-2c8565926d89"></video>
        <br>
        <strong>艺术图像动效</strong>
        <br>
        胶囊：<code>art_motion</code>
        <br>
        参考帧、风格约束、运动方式和图像转视频的检查规则。
      </td>
    </tr>
    <tr>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/b5c672be-cacb-4877-a688-e6d7baa1a3b5"></video>
        <br>
        <strong>国风历史文化讲解</strong>
        <br>
        胶囊：<code>guofeng_history</code>
        <br>
        国风视觉、人物讲解、旁白节奏和历史内容边界。
      </td>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/59f4c71c-9634-4b9f-8b48-e47f7a7c1d5f"></video>
        <br>
        <strong>羊毛毡 ASMR 手作</strong>
        <br>
        胶囊：<code>felt_asmr</code>
        <br>
        材质特写、制作步骤、舒缓节奏和 ASMR 音画规则。
      </td>
    </tr>
  </tbody>
</table>

公开样片主要使用火山方舟 Seedream 和 Seedance，配音可选 MiniMax 或豆包语音。RunningHub 动作迁移和口型工作流以代码示例保留。具体渠道、模型权限和费用由用户自己的账号决定。

## Quick Start

你不需要记命令。把安装、制作、返工和保存胶囊的要求直接告诉 Agent 即可。

### 1. 让 Agent 安装

把下面这段话发给 Codex、Claude Code、OpenClaw、Cursor、Trae、Hermes Agent，或其他能够读取文件、执行命令并发现 Skills 的 Agent：

```text
帮我安装 Capsule Cinema：
https://raw.githubusercontent.com/JuneYaooo/capsule-cinema/main/docs/install.md

装好后列出内置胶囊和当前可用渠道，不要调用计费 API。
```

Agent 会选择当前环境的安装位置、安装 Python 依赖并检查 FFmpeg。升级已有安装时会保留 `.env`、本地渠道、自建胶囊和历史输出。完整说明见 [安装指南](docs/install.md)。

### 2. 先审分镜和代表镜头

```text
帮我用 Capsule Cinema 做一条 25 秒竖屏视频：
一只橘猫深夜经营路边摊，温暖治愈一点。
先给我看分镜，确认后只试做一个代表镜头。
```

分镜和代表镜头都确认后，再让 Agent 完成整条视频。正式产物位于独立的 `output/<run>/`：`release/` 保存交付文件，`work/` 保存中间媒体和编辑计划，`qa/` 保存检查结果与修复建议。

生成图片、视频和语音需要相应渠道。只浏览、校验、打包和安装胶囊不会调用媒体生成 API。不要把密钥粘贴到对话、胶囊、prompt、脚本或 Git 中。

### 3. 把满意的方法保存成胶囊

```text
这条视频我很满意。
把下一期仍然成立的结构、风格、质量规则和返工经验，
保存成「治愈系夜间小摊」胶囊。
```

保存时，Agent 会区分栏目固定方法和本期变量。人物事实、价格、标题、旁白、临时素材、客户资料、密钥、远程临时 URL、绝对路径和运行产物不会进入可分享胶囊。

也可以从参考视频整理胶囊草稿。Agent 会先拆解钩子、镜头节奏、文案结构、视觉、运动和声音，再区分样片内容与可复用方法：

```text
参考这个本地视频，整理一份可复用的视频胶囊草稿。
先告诉我准备保存哪些方法，确认后再写入配方。
```

### 4. 继续复用、更新或分享

```text
用「治愈系夜间小摊」胶囊，做一期柴犬雨夜卖关东煮的故事。
```

```text
这次产品近景保持 2 秒左右效果更好，看看是否值得记到电商胶囊里。
```

```text
把「治愈系夜间小摊」胶囊打包给我，我要在另一台机器安装。
```

胶囊更新会先检查冲突和内容边界，验证失败时不会留下半更新状态。同名胶囊安装前需要版本或差异确认。

## 内置视频胶囊

仓库提供一组可以直接查看和继续定制的胶囊：

| 胶囊 | 适合做什么 | 主要保留内容 |
| --- | --- | --- |
| `life_sim` | 第二人称人生模拟、动漫剧情口播 | 钩子、情绪推进、角色规则、快切节奏 |
| `ecommerce_product_showcase` | 商品展示、种草和带货短视频 | 商品身份、卖点结构、平台语气和合规规则 |
| `art_motion` | 插画、海报和参考帧动态短片 | 风格、运动方式、转场和参考图约束 |
| `felt_asmr` | 羊毛毡烘焙、手作和治愈 ASMR | 材质、步骤、特写、声音和节奏 |
| `guofeng_history`（草稿） | 国风历史人物和文化讲解 | 国风视觉、人物叙事、旁白和内容边界 |

运行 `python3.12 scripts/capsule.py list` 可以查看当前安装中的胶囊；用 `show` 和 `doctor` 可以查看输入要求、执行方式、所需渠道和诊断结果。

## 质量门与局部返工

Capsule Cinema 把「能播放」和「能交付」分开处理。完成媒体生成后，系统会建立编辑计划并检查本地文件、时间线和发布要求。检查项可以包括：

| 检查对象 | 示例 |
| --- | --- |
| 视频文件 | 画幅、时长、编码、黑帧、静帧和音轨 |
| 声音 | 响度、削波、静音、TTS 与画面时长匹配 |
| 画面与字幕 | 字幕布局、安全区、可读性、角色和风格一致性 |
| 胶囊合同 | 必需镜头、交付物、禁止降级和发布检查点 |
| 交付包 | 成片、封面、平台文案、QA 报告和 manifest |

发现问题时，系统会生成 repair plan。可以只重做一个镜头，也可以只换配音、字幕、BGM 或重新拼接：

```text
第 3 个镜头里角色变形了，只改这个镜头，其他镜头和音频保持不动。
```

修复完成后重新运行 QA 和 release checkpoint。存在阻断项时，系统不会把视频标记为可交付。

## 视频胶囊保存什么

<img src="docs/assets/readme-capsule-anatomy.svg" width="100%" alt="视频胶囊的包结构">

胶囊保存适用场景、输入要求、分镜结构、视觉风格、音频策略、工具能力、质量规则和经过验证的经验。它不保存某一期的完整成片，也不复制上一期的事实、文案和临时素材。

胶囊可以来自三类来源：

| 来源 | 用法 |
| --- | --- |
| 内置胶囊 | 从仓库随附的起步案例开始 |
| 个人胶囊 | 把自己的满意作品沉淀成账号、品牌或项目方法 |
| 可分享胶囊 | 打包后交给另一台机器、团队成员或社区用户安装 |

`quality/` 保存质量门，`learning/` 只保存已经泛化并通过确认的经验。API Key、Cookie、客户资料、签名 URL、绝对路径和 `output/` 运行产物不会进入分享包。

## 使用自己的生成渠道

视频胶囊声明需要什么能力，不绑定某个供应商。运行时根据本机已经配置和验证过的工具，匹配图片、视频、TTS、音乐、数字人、动作迁移、剪辑和 QA 渠道。

| 能力 | 当前公开示例 |
| --- | --- |
| 图片生成 | 火山方舟 `VolcengineImageGeneratorTool`，支持 Seedream 文生图、参考图和商品图 |
| 视频生成 | 火山方舟 `Seedance20VideoGeneratorTool`，支持文生视频、图生视频、首尾帧和多模态参考 |
| 语音合成 | 豆包语音 `DoubaoTTSTool`，MiniMax 路线 `UniversalTTSTool` |
| 动作迁移和口型 | RunningHub 示例工具与可检查的工作流参数 |
| 剪辑、字幕和 QA | 本地 FFmpeg、编辑计划、质量评分、修复计划和发布检查点 |

工具不可用时，系统会说明可用替代路线。替代方案会改变交付效果时，运行会停下来等待确认，不会静默降低质量。

### 把新的 API 文档交给 Agent

```text
这是「渠道名」的官方 API 文档：「链接或本地文件」。
把它安装成 Capsule Cinema 的本地私有渠道。
先做不计费的配置和请求结构检查，需要真实测试时再问我。
```

个人渠道默认放进 Git 忽略的本地覆盖层，密钥不会写入代码或公共胶囊。公共渠道贡献需要同步适配器、注册表、能力标签、环境变量白名单、测试和 QA。详细规则见 [自定义工具说明](lib/custom_tools/README.md)。

<details>
<summary>查看完整视频能力地图</summary>

<img src="docs/assets/readme-capability-map.svg" width="100%" alt="Capsule Cinema 视频能力地图">

</details>

## 技术设计

Capsule Cinema 是一个本地 Skills 项目。Agent 读取 `skill.md`、`references/`、`capsules/*.capsule/` 和工具注册表，通过脚本入口完成规划、生成、剪辑、QA、修复和胶囊生命周期操作。

创意规则可以放在配方和参考文档中，影响交付的要求则落在 contracts、validators、registry 和 QA scripts 中。这样可以保留创作空间，同时让运行结果有结构化证据可查。

进一步阅读：

- [安装指南](docs/install.md)
- [架构图与设计梳理](docs/architecture-map.md)
- [自定义工具说明](lib/custom_tools/README.md)
- [视频胶囊包格式](references/capsule-package-format.md)
- [生产指南](references/production-guide.md)

## 社群

欢迎通过 [GitHub Issues](https://github.com/JuneYaooo/capsule-cinema/issues) 分享胶囊想法、运行问题、成片案例或改进建议。

中文开发者社区：[LINUX DO](https://linux.do/)

微信群：交流视频制作经验，分享自己的视频胶囊。扫码加入 capsule-cinema 交流群。

<p align="left">
  <img src="docs/assets/wechat-group.jpg" alt="capsule-cinema 微信交流群二维码" width="400">
</p>

## License

本项目使用 PolyForm Noncommercial License 1.0.0。商业使用前请阅读 [LICENSE](./LICENSE) 中的完整条款。
