<div align="center">

# Capsule Cinema 胶囊影厂

**AI 视频创作工厂：把能跑通的视频流程，沉淀成可复用的创作配方。**

Capsule Cinema 面向持续做短视频的人和团队。它把需求、素材、工具能力和质量标准组织成一套可复用的 Capsule，让同一类视频可以稳定复用结构，同时换主题、换素材、换风格。

<p>
  <a href="./README.en.md">English</a> ·
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-PolyForm%20Noncommercial-111827.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/video-recipes-2563EB.svg" alt="Video recipes">
  <img src="https://img.shields.io/badge/custom-tools-475569.svg" alt="Custom tools">
  <img src="https://img.shields.io/badge/quality-gates-0F172A.svg" alt="Quality gates">
</p>

<p>
  <a href="#demo">Demo</a> ·
  <a href="#为什么需要-capsule-cinema">为什么需要</a> ·
  <a href="#能做什么">能做什么</a> ·
  <a href="#视频能力地图">视频能力地图</a> ·
  <a href="#视频配方">视频配方</a> ·
  <a href="#自定义工具">自定义工具</a> ·
  <a href="#工作方式">工作方式</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#社群">社群</a>
</p>

<img src="docs/assets/readme-hero.svg" width="100%" alt="Capsule Cinema 从需求到成片交付的工作流">

</div>

Capsule Cinema 不是一次性视频生成器。它更像一个可复用的视频生产系统：先把创作过程拆成分镜、工具路线、音频策略、质量规则和返工经验，再把这些稳定部分保存成配方。

## Demo

这些样片来自内置起步配方。它们展示了 Capsule Cinema 能覆盖的栏目、商品、艺术动效和风格化短片方向。

<table>
  <tbody>
    <tr>
      <td width="62%" valign="top">
        <video width="100%" controls src="https://github.com/user-attachments/assets/d81e88b3-a567-4835-9784-c2a65f4fe977"></video>
      </td>
      <td width="38%" valign="top">
        <strong>人生模拟短剧</strong>
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
        卖点拆解、场景演示、商品种草和带货短视频。
      </td>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/5fff44fe-97e5-41e4-a966-2c8565926d89"></video>
        <br>
        <strong>艺术图像动效</strong>
        <br>
        插画、海报、首尾帧和风格化图像的视频化。
      </td>
    </tr>
    <tr>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/b5c672be-cacb-4877-a688-e6d7baa1a3b5"></video>
        <br>
        <strong>国风历史讲解</strong>
        <br>
        历史文化、古风视觉、旁白讲解和知识型短片。
      </td>
      <td width="50%" valign="top" align="center">
        <video width="260" controls src="https://github.com/user-attachments/assets/59f4c71c-9634-4b9f-8b48-e47f7a7c1d5f"></video>
        <br>
        <strong>羊毛毡 ASMR</strong>
        <br>
        手作、软萌食物、细节特写和舒缓节奏视频。
      </td>
    </tr>
  </tbody>
</table>

## 为什么需要 Capsule Cinema

一次性 prompt 可以做出一条视频，但很难稳定复用。真正做账号、栏目、产品视频或团队交付时，问题会变成：

| 真实问题 | Capsule Cinema 的做法 |
| --- | --- |
| 每次都要重新想结构 | 把跑通的栏目结构保存进 Capsule |
| 工具供应商更新太快 | 配方声明需要的能力，运行时匹配可用工具 |
| 生成前很难确认方向 | 先产出可审分镜，再进入媒体生成 |
| 一处不满意就要整条重来 | 支持单镜头、BGM、字幕、拼接等局部返工 |
| 成片能不能交付靠肉眼 | 生成质量检查、修复建议和发布检查点 |
| 参考视频容易变成照搬 | 先分析结构、节奏、风格和音频策略，再生成胶囊草稿 |

## 能做什么

<img src="docs/assets/readme-workflow.svg" width="100%" alt="Capsule Cinema 工作流">

| 视频方向 | 可以覆盖的创作能力 |
| --- | --- |
| 真实素材剪辑生成 | 把已有素材、参考片段、字幕、BGM 和节奏要求整理成剪辑方案，生成可审的成片路线 |
| 通用 AI 视频创作 | 从主题和人群出发，生成分镜、画面、视频、配音、字幕、剪辑和质量检查 |
| 电商带货视频 | 拆卖点、安排展示顺序、控制口播节奏，支持商品图、场景图和演示镜头混合 |
| AI 音乐 MV | 围绕歌词、节拍、情绪段落和视觉风格组织镜头，适合音乐短片和氛围 MV |
| 数字人口播混合 | 把数字人口播、产品 B-roll、字幕卡、图文信息和真实素材组合成完整视频 |
| 动作模仿和跳舞 | 围绕参考动作、角色一致性、节拍卡点和镜头连贯性生成动作类短片 |
| 参考视频生成胶囊草稿 | 分析镜头节奏、文案结构、视觉风格和音频策略，生成可确认的配方草稿 |
| 局部返工 | 只改一个镜头、只换配音、只调 BGM、只重拼已有素材，减少整条重做 |

## 视频能力地图

这张能力地图把视频任务拆成内容类型、底层生成能力和交付检查。它也说明了工具能力的边界：图片生成、AI 视频生成、TTS、AI 音乐、真实素材剪辑、数字人、动作模仿和质量检查可以组合，而不是绑死在某一个平台。

<img src="docs/assets/readme-capability-map.svg" width="100%" alt="Capsule Cinema 视频能力地图">

## 视频配方

Capsule 不是成片，而是一套可迁移的视频工作流。它保存一类视频的不变量：适用场景、分镜结构、视觉风格、音频策略、工具路线、质量规则、返工经验和安全边界。

<img src="docs/assets/readme-capsule-anatomy.svg" width="100%" alt="Capsule 配方结构">

常见配方方向：

| 配方方向 | 适合做什么 |
| --- | --- |
| 栏目型短视频 | 账号固定栏目、剧情口播、知识讲解、系列选题 |
| 商品展示和种草 | 商品卖点、使用场景、对比展示、电商带货 |
| 艺术动效短片 | 插画动效、海报动效、首尾帧过渡、风格实验 |
| 国风历史讲解 | 历史文化、人物故事、古风视觉、旁白科普 |
| 手作和 ASMR | 羊毛毡、食物手作、细节特写、舒缓音画 |
| AI 音乐 MV | 歌词可视化、节奏卡点、视觉概念片、氛围短片 |
| 数字人口播混合 | 主播口播、产品素材、字幕卡、品牌说明和 B-roll 混剪 |
| 动作模仿短片 | 舞蹈、姿态迁移、角色动作演绎、节拍型视频 |

配方可以来自三类来源：

| 来源 | 用法 |
| --- | --- |
| 初始配方 | 用项目内置的种子案例快速开始 |
| 个人配方 | 把满意作品沉淀成账号、品牌或项目经验 |
| 社区配方 | 共享、试用和改进公共创作方法 |

复用时只替换主题、素材和当期文案，保留已经验证过的结构。配方不保存密钥、cookie、客户资料、私有素材、临时链接或一次性运行产物。

## 自定义工具

AI 视频工具更新很快，所以配方不绑定某个平台。配方只描述需要什么能力，工具声明自己能提供什么能力，运行时负责匹配。

| 能力层 | 可以接入的工具 | 支撑的视频类型 |
| --- | --- | --- |
| 图片生成 | 文生图、图生图、商品图、封面图、风格化图像 | 通用 AI 视频、电商、国风、艺术动效 |
| AI 视频生成 | 文生视频、图生视频、首尾帧、镜头延展、镜头转场 | 通用创作、艺术短片、剧情短片、产品演示 |
| 真实素材剪辑 | 素材筛选、片段拼接、字幕、转码、封面和节奏重排 | 真实素材混剪、活动回顾、产品案例、口播 B-roll |
| TTS 和数字人 | 多音色配音、口播、对口型、数字主播和真人素材混合 | 知识讲解、电商口播、品牌说明、短剧旁白 |
| AI 音乐和 BGM | 音乐生成、BGM、音效、节拍点和情绪段落 | 音乐 MV、氛围短片、ASMR、剧情转场 |
| 动作模仿 | 姿态参考、舞蹈动作、角色一致性和动作节奏检查 | 跳舞视频、动作迁移、角色表演、挑战类短片 |
| 质量检查 | 黑屏、画幅、字幕遮挡、响度、时长、语言匹配和发布检查 | 所有需要稳定交付的视频 |
| 凭证和替代路线 | 凭证检查、能力匹配、失败降级和用户确认 | 多供应商组合、团队生产、批量交付 |

工具不可用时，系统会列出替代路线。需要用户确认的降级不会静默执行。

## 工作方式

| 阶段 | 发生什么 |
| --- | --- |
| 输入理解 | 把目标人群、主题、素材、风格和发布场景整理成制作需求 |
| 配方选择 | 选择已有 Capsule，或者根据参考视频和目标生成胶囊草稿 |
| 分镜审阅 | 先确认镜头结构、文案节奏、画面方向和音频策略 |
| 工具调度 | 根据能力匹配图片、视频、TTS、音乐、剪辑、数字人和质检工具 |
| 质量门 | 检查画幅、时长、字幕、声音、镜头完整度和配方约束 |
| 经验回写 | 把返工原因、有效结构和发布检查结果沉淀回配方 |

## Quick Start

把仓库安装为 OpenClaw skill 后，直接在对话里说目标即可。下面这些说法更适合放在产品使用层，不需要你记任何本地入口。

| 目标 | 可以这样说 |
| --- | --- |
| 先看分镜 | "先只生成分镜，不要生成图片、视频和配音。主题是《主题》，我确认后再继续制作。" |
| 做完整成片 | "用 Capsule Cinema 做一个《时长》秒《横屏或竖屏》视频，主题是《主题》，重点突出《价值点》。" |
| 选择能力路线 | "这次优先使用《图片生成、AI 视频、TTS、AI 音乐、真实素材剪辑、数字人或动作模仿》能力，请给我一条可确认的制作路线。" |
| 使用真实素材 | "我有一组素材，请整理成《用途》的短视频，保留可用镜头，补齐字幕、BGM、转场和发布检查。" |
| 做电商视频 | "做一个商品种草视频，产品是《产品》，目标用户是《人群》，卖点是《卖点》，风格要《风格》。" |
| 做 AI 音乐 MV | "围绕这首歌做一个音乐 MV，按歌词段落和节拍设计镜头，画面风格是《风格》。" |
| 做数字人口播 | "用数字人口播加产品 B-roll 做一条说明视频，语气要《语气》，重点讲清《信息》。" |
| 做动作模仿 | "参考这个动作或舞蹈视频，生成一条《角色或主题》的动作短片，注意动作节奏和角色一致性。" |
| 分析参考视频 | "请分析这个参考视频，拆出镜头节奏、文案结构、视觉风格和音频策略，先生成一个胶囊草稿。" |
| 局部返工 | "上一次视频第《编号》个分镜不满意，请保留其他部分，只重做这个分镜：《修改要求》。" |
| 保存成配方 | "这条视频我满意，请保存成《配方名》，以后用于《适用场景》。" |

不确定选哪个配方时，直接描述目标、素材、风格和交付场景。Capsule Cinema 会先给你可审的制作路线，再进入生成。

## 社群

欢迎通过 [GitHub Issues](https://github.com/JuneYaooo/capsule-cinema/issues) 分享配方想法、运行问题、成片案例或改进建议。

中文开发者社区：[LINUX DO](https://linux.do/)

## License

PolyForm Noncommercial License 1.0.0，详见 [LICENSE](./LICENSE)。
