<div align="center">

# Capsule Cinema

**把一次跑通的方法，变成你自己的短视频工厂。**

Capsule Cinema 是安装到 Coding Agent 中的短视频生产系统。它把栏目结构、分镜规则、生成渠道、质量门和返工经验整理成可迁移、可更新的视频配方。下一期只换主题和素材，不必重新搭建整套流程。

<p>
  <a href="./README.en.md">English</a> ·
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-111827.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/Agent-Skills-16A34A.svg" alt="Agent Skills">
  <img src="https://img.shields.io/badge/video-recipes-2563EB.svg" alt="Video recipes">
  <img src="https://img.shields.io/badge/targeted-rework-7C3AED.svg" alt="Targeted rework">
  <img src="https://img.shields.io/badge/release-QA-0F172A.svg" alt="Release QA">
</p>

<p>
  <strong>可审分镜 · 自选渠道 · 单镜头返工 · 发布前 QA · 配方打包迁移</strong>
</p>

<p>
  <a href="#为什么需要视频配方">为什么需要</a> ·
  <a href="#demo">Demo</a> ·
  <a href="#同一个胶囊做不同主题">复用示例</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#内置视频配方">内置配方</a> ·
  <a href="#质量门与局部返工">质量与返工</a> ·
  <a href="#使用自己的生成渠道">生成渠道</a> ·
  <a href="#社群">社群</a>
</p>

<img src="docs/assets/readme-hero.svg" width="100%" alt="Capsule Cinema：把一次跑通的视频流程变成可复用配方">

</div>

Capsule Cinema 面向持续运营账号、制作栏目或商品视频的创作者和团队。它更适合中文短视频生产场景，仓库内置抖音感剧情、商品种草、国风讲解等起步配方。

它不是网页式一键生成器，也不提供模型算力。项目运行在用户自己的 Agent 和本地工作区中，媒体生成使用用户配置的 API。当前公开渠道包括 Seedream、Seedance、Agnes 图片/短视频、MiniMax、豆包语音和本地 FFmpeg。

## 为什么需要视频配方

一次性 prompt 可以做出一条视频，但很难稳定地做下一期。视频配方保存一类视频中已经验证过的部分，让新的主题继续沿用同一套生产方法。

| 常见的一次性做法 | Capsule Cinema |
| --- | --- |
| 每次重新解释栏目结构 | 复用已经确认的分镜机制、节奏和视觉规则 |
| 生成前很难确认方向 | 先审分镜，再试一个代表镜头，然后继续生成 |
| 一个镜头有问题就整条重做 | 只返工指定镜头、配音、字幕、BGM 或拼接结果 |
| 有 MP4 就当作完成 | 检查画幅、黑帧、响度、字幕、安全区和交付物 |
| 工具不可用时临时换一条路线 | 展示替代渠道及影响，改变交付效果时等待确认 |
| 成功经验留在聊天记录里 | 回写到配方，经过校验后再用于下一期 |
| 流程只能留在当前机器 | 打包配方，在另一台机器或团队环境中安装 |

<img src="docs/assets/readme-workflow.svg" width="100%" alt="Capsule Cinema 从需求到经验回写的生产闭环">

视频配方保存可复用的制作方法，也可以打包安装到另一台机器。一个配方通常包含：

```text
视频配方
= 输入与使用边界
+ 分镜、视觉和音频配方
+ 工具能力要求
+ 质量门与发布检查
+ 经过验证的返工经验
```

## Demo

这些样片来自内置起步配方，对应的配方包随公开仓库提供。你可以保留已经跑通的结构和质量规则，只替换主题、素材、商品或当期文案。

<table>
  <tbody>
    <tr>
      <td width="62%" valign="top">
        <video width="100%" controls src="https://github.com/user-attachments/assets/d81e88b3-a567-4835-9784-c2a65f4fe977"></video>
      </td>
      <td width="38%" valign="top">
        <strong>人生模拟短剧</strong>
        <br>
        配方：<code>life_sim</code>
        <br><br>
        面向打工人剧情、生活共情、动漫口播和系列化栏目。
        <br><br>
        配方保存第二人称叙事、钩子结构、情绪推进、角色一致性、镜头节奏和 TTS 规则。
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
        配方：<code>ecommerce_product_showcase</code>
        <br>
        商品身份锚定、卖点顺序、场景展示、口播节奏和合规规则。
      </td>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/5fff44fe-97e5-41e4-a966-2c8565926d89"></video>
        <br>
        <strong>艺术图像动效</strong>
        <br>
        配方：<code>art_motion</code>
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
        配方：<code>guofeng_history</code>
        <br>
        国风视觉、人物讲解、旁白节奏和历史内容边界。
      </td>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/59f4c71c-9634-4b9f-8b48-e47f7a7c1d5f"></video>
        <br>
        <strong>羊毛毡 ASMR 手作</strong>
        <br>
        配方：<code>felt_asmr</code>
        <br>
        材质特写、制作步骤、舒缓节奏和 ASMR 音画规则。
      </td>
    </tr>
  </tbody>
</table>

### 同一个胶囊，做不同主题

胶囊名称：<strong>高抽象成长卡片</strong>（`high_abstraction_growth_card`）

<strong>能做什么：</strong>把满意的视频做法保存下来，换一个主题继续做，保持相同的栏目风格。

<strong>怎么做：</strong>告诉 Agent 使用这个胶囊，再说清楚下一期想做什么。

```text
用「高抽象成长卡片」胶囊，
做一期“为什么一直很忙，却还是很难成长”。
```

下面四条视频都用同一个胶囊完成，但主题和内容各不相同：

<table width="100%">
  <tbody>
    <tr>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/c563194d-d475-4fa1-87c8-866ddf28cb22"></video>
        <br>
        <strong>不确定感</strong>
        <br>
        真正让人焦虑的，不是事情没结果
      </td>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/c56d4068-676c-47c1-b1fa-191c6bf4c5e9"></video>
        <br>
        <strong>自控力</strong>
        <br>
        别把重要决定留给最疲惫的自己
      </td>
    </tr>
    <tr>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/d4982df6-b414-4810-943c-9e096bc458db"></video>
        <br>
        <strong>职场成长</strong>
        <br>
        一直很忙，为什么还是很难升级
      </td>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/6e9c8879-39b2-486e-ad69-645e30e8b531"></video>
        <br>
        <strong>关系边界</strong>
        <br>
        看一个人如何回应你的拒绝和不同
      </td>
    </tr>
  </tbody>
</table>

同一个胶囊，可以不断换题做成一个系列。**满意的方法留下来，下一期继续用。**

## Quick Start

你不需要记命令。把安装、制作、返工和保存配方的要求直接告诉 Agent 即可。

### 1. 让 Agent 安装

把下面这段话发给 Codex、Claude Code、OpenClaw、Cursor、Trae、Hermes Agent，或其他支持 Skills 的 Agent：

```text
帮我安装 Capsule Cinema：
https://raw.githubusercontent.com/JuneYaooo/capsule-cinema/main/docs/install.md
```

Agent 会完成安装和环境检查。安装好以后，直接告诉它想做什么即可。完整说明见 [安装指南](docs/install.md)。

### 2. 建议先跑一次低成本项目展示

第一次上手，建议先用内置配方 `repo_signal_grid` 给这个仓库做一条介绍视频。它直接使用真实网页截图和本地排版渲染，**不需要配置 AI 视频、TTS 或图片生成工具**，适合快速确认安装、截图、渲染和质检流程是否正常。

把下面这段话发给 Agent：

```text
请打开并了解这个项目：
https://github.com/JuneYaooo/capsule-cinema

使用内置视频配方 `repo_signal_grid`，为这个项目制作一条项目介绍视频。
```

建议同时给 Agent 安装一个浏览器 CLI Skill，方便它打开网页并截图。

结果示例：

<video width="420" controls src="https://github.com/user-attachments/assets/162037a1-5484-4554-bd38-976e3970c524"></video>

### 3. 先审分镜和代表镜头

```text
帮我用 Capsule Cinema 做一条 25 秒竖屏视频：
一只橘猫深夜经营路边摊，温暖治愈一点。
先给我看分镜，确认后只试做一个代表镜头。
```

分镜和代表镜头都确认后，再让 Agent 完成整条视频。正式产物位于独立的 `output/<run>/`：`release/` 保存交付文件，`work/` 保存中间媒体和编辑计划，`qa/` 保存检查结果与修复建议。

生成图片、视频和语音需要相应渠道。只浏览、校验、打包和安装配方不会调用媒体生成 API。不要把密钥粘贴到对话、配方、prompt、脚本或 Git 中。

### 4. 把满意的方法保存成配方

```text
这条视频我很满意，保存成「治愈系夜间小摊」配方，以后做同类视频继续用。
```

配方保存可复用的制作方法，不保存当期事实、临时素材或密钥。

也可以从参考视频整理配方草稿。Agent 会先拆解钩子、镜头节奏、文案结构、视觉、运动和声音，再区分样片内容与可复用方法：

```text
参考这个本地视频，整理一份可复用的视频配方草稿。
先告诉我准备保存哪些方法，确认后再写入配方。
```

### 5. 继续复用、更新或分享

```text
用「治愈系夜间小摊」配方，做一期柴犬雨夜卖关东煮的故事。
```

```text
这次产品近景保持 2 秒左右效果更好，看看是否值得记到电商配方里。
```

```text
把「治愈系夜间小摊」配方打包给我，我要在另一台机器安装。
```

## 内置视频配方

仓库提供一组可以直接查看和继续定制的配方：

| 配方 | 适合做什么 | 主要保留内容 |
| --- | --- | --- |
| `life_sim` | 第二人称人生模拟、动漫剧情口播 | 钩子、情绪推进、角色规则、快切节奏 |
| `ecommerce_product_showcase` | 商品展示、种草和带货短视频 | 商品身份、卖点结构、平台语气和合规规则 |
| `art_motion` | 插画、海报和参考帧动态短片 | 风格、运动方式、转场和参考图约束 |
| `felt_asmr` | 羊毛毡烘焙、手作和治愈 ASMR | 材质、步骤、特写、声音和节奏 |
| `guofeng_history` | 国风历史人物和文化讲解 | 国风视觉、人物叙事、旁白和内容边界 |
| `high_abstraction_growth_card` | 高抽象成长类认知卡片视频 | 选题结构、现实场景、观点拆解、行动建议和统一卡片风格 |
| `repo_signal_grid` | GitHub 仓库、工具和 Agent Skill 项目展示 | 真实浏览器截图、6:7 暖白橙网格、五幕事实链和本地低成本渲染 |

## 质量门与局部返工

Capsule Cinema 把「能播放」和「能交付」分开处理。完成媒体生成后，系统会建立编辑计划并检查本地文件、时间线和发布要求。检查项可以包括：

| 检查对象 | 示例 |
| --- | --- |
| 视频文件 | 画幅、时长、编码、黑帧、静帧和音轨 |
| 声音 | 响度、削波、静音、TTS 与画面时长匹配 |
| 画面与字幕 | 字幕布局、安全区、可读性、角色和风格一致性 |
| 配方合同 | 必需镜头、交付物、禁止降级和发布检查点 |
| 交付包 | 成片、封面和平台文案 |

发现问题时，可以只重做一个镜头，也可以只换配音、字幕、BGM 或重新拼接：

```text
第 3 个镜头里角色变形了，只改这个镜头，其他镜头和音频保持不动。
```

修复后会重新质检。还有阻断项时，视频不会进入交付状态。

## 视频配方保存什么

配方保存适用场景、输入要求、分镜结构、视觉风格、音频策略、工具能力、质量规则和经过验证的经验。它不保存某一期的完整成片，也不复制上一期的事实、文案和临时素材。

配方可以来自三类来源：

| 来源 | 用法 |
| --- | --- |
| 内置配方 | 从仓库随附的起步案例开始 |
| 个人配方 | 把自己的满意作品沉淀成账号、品牌或项目方法 |
| 可分享配方 | 打包后交给另一台机器、团队成员或社区用户安装 |

密钥、客户资料和单次运行产物不会写入可分享配方。

## 使用自己的生成渠道

视频配方声明需要什么能力，不绑定某个供应商。运行时根据本机已经配置和验证过的工具，匹配图片、视频、TTS、音乐、数字人、动作迁移、剪辑和 QA 渠道。

| 能力 | 当前公开示例 |
| --- | --- |
| 图片生成 | 火山方舟 Seedream、Agnes Image 2.1 Flash |
| 视频生成 | 火山方舟 Seedance、Agnes Video v2.0 文生短视频 |
| 语音合成 | 豆包语音、MiniMax |
| 动作迁移和口型 | RunningHub |
| 剪辑、字幕和 QA | 本地 FFmpeg 和质量检查工具 |

### 第一次试跑：推荐 Agnes

如果只是想先跑通 AI 图片和短视频链路，可以从 Agnes 开始：到 [Agnes API 平台](https://platform.agnes-ai.com/) 注册并在控制台生成自己的 API Key，再把它配置为 `AGNES_API_KEY`。它适合先做一张代表镜头和一段几秒级文生动作样片，确认提示词、画幅、下载和质检流程都能工作；它不是完整的图生视频或长视频引擎。

截至 2026-07-27，[Agnes 官方 FAQ](https://wiki.agnes-ai.com/en/docs/faqs.md) 表示核心文本、图片、视频和多模态模型可“无限期免费使用”，没有公布免费层结束日期。这不等于无限调用或无限额度：[当前限额说明](https://wiki.agnes-ai.com/en/docs/tokenplan.md) 中，免费默认档图片有效限速约为 1K 20 RPM、2K 10 RPM、3K/4K 1 RPM，视频约为 1 RPM。官方没有公开免费用户每天具体可生成多少秒视频；文档中的 500 秒/天属于付费 Token Plan。免费档没有生产 SLA，额度、限流、模型规则和输出规格仍可能调整。

仓库不内置或共享 Agnes API Key。服务可能调整实际输出尺寸；Agnes 视频工具只声明已经验证过的短文生视频能力，并默认移除供应商原生音轨。

工具不可用时，系统会说明可用替代路线。替代方案会改变交付效果时，运行会停下来等待确认，不会静默降低质量。

## 社群

欢迎通过 [GitHub Issues](https://github.com/JuneYaooo/capsule-cinema/issues) 分享配方想法、运行问题、成片案例或改进建议。

中文开发者社区：[LINUX DO](https://linux.do/)

微信群：交流视频制作经验，分享自己的视频配方。扫码加入 capsule-cinema 交流群。

<p align="left">
  <img src="docs/assets/wechat-group.jpg" alt="capsule-cinema 微信交流群二维码" width="400">
</p>

## License

本项目使用 Apache License 2.0，允许商业使用、修改和再分发。完整条款见 [LICENSE](./LICENSE)。
