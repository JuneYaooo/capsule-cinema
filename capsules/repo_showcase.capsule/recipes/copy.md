---
type: Video Recipe
title: Copy Recipe
description: Voiceover, subtitles, titles, cover copy, lyrics, and CTA rules.
stage: planning
domain: copy
profile: video.okf.capsule.v1
tags:
- copy
---

# Copy

## wechat_social_value_gate

- Before writing a WeChat Channels title or body copy, verify the angle has hard_value, distinctive_view, or unexpected_use.
- Prefer user value and a specific point of view over generic interaction bait.
- Keep this gate internal; do not print method labels in viewer-facing copy.

## copy_policy

{
  "ai_flavored_template_copy_policy": {
    "forbidden_pattern_types": [
      "模板化 AI 句式",
      "否定转折模板",
      "三段式口号",
      "把抽象词对抽象词的金句式标题",
      "没有具体任务、对象、输入或输出的漂亮句子",
      "X 是 Y，不是 Z 式解释句",
      "不是 A，而是 B 式否定转折"
    ],
    "preferred_examples": [
      "先把商品做一份卖前体检报告",
      "给商品、产地、目标市场，输出准入和补件清单",
      "把项目链接交给 Agent，先拿到能不能用的判断",
      "63.2k 星让你点进来，真正要看的是 spec、test、review 怎么管住 Agent",
      "先让 Agent 写 spec 和测试计划，再让它动手改代码"
    ],
    "purpose": "降低短视频标题和卡片的模板化 AI 句式，避免观众感到空泛、套话或高跳出。",
    "required": true,
    "rewrite_rules": [
      "标题和底部卡片优先直接写具体用途：输入什么、检查什么、输出什么、接下来怎么判断或怎么问。",
      "不要用抽象名词互相对打来制造高级感；改成项目能交付的报告、清单、对标、安装或提问动作。",
      "避免用否定转折模板做标题；需要边界时，直接写清能做什么和不能代替什么。",
      "如果一句话删掉项目名后仍像通用鸡汤、判断句或平台爆款模板，重写成项目专属用法。",
      "不要写“X 是 Y，不是 Z”“不是 A，而是 B”“X 不是 Y，是 Z”这类说明句；改成具体动作、结果、输入输出、用户收益或可执行下一步。",
      "星标、截图数、开源等 proof 只做支撑；主文案直接写观众为什么要用、怎么用、能少踩什么坑。"
    ]
  },
  "copy_rules": [
    "3:4 成片默认不再额外预留视频号上下安全空白；顶部/底部文字要足够大，底部事实链卡片应向下扩展并使用 4 行左右有效信息填满画幅。只有用户明确要求平台 UI 安全区时才收窄底部。",
    "不要承诺自动保证质量、完全替代人工评审、所有项目都适合；把边界写成可信度的一部分。",
    "中间主视觉不能固定某几张图或固定 README 截图；每个仓库先审计仓库自带图片、README/docs 内嵌图、demo/UI/产物图、GIF/视频。没有可用图片或证据不够时，才补 README/GitHub/source 截图；自制总结卡只能是记录原因后的 fallback。",
    "事实链先问目标用户最关心什么，再筛事实；不要为了密度堆中性信息。",
    "做 repo/tool/skill 视频时，不要停在 README 摘要或数字罗列。先读源码、脚本、配置、示例和截图，再把项目到底是什么、能帮目标用户完成什么、为什么值得停留或收藏，翻译成用户能立刻理解的标题和画面。",
    "公开视频文案只解释项目是什么而没有用户为什么在意，必须改成用户收益、用户张力、证据、边界或评论判断。",
    "发布前扫描可见文案，禁止版本、修正、source、real asset、draft 等制作/交付词残留。",
    "开源/GitHub/免费/替代付费工具等承诺必须有画面证据；证据不够时改成更克制的学习/试用/可参考表述。",
    "强 proof 数字可以前置，但必须绑定核心对象和核心转化；数字不能替代主体。",
    "成片画面不要出现 HOOK、卖点、痛点、策略、传播资产、信任钩子、记忆点等制作术语。",
    "标题不是分类名，必须先给用户结果、痛点反差、证据数字、独特机制或评论争议点。",
    "标题和底部文案是本胶囊的重点：必须表达用户痛点、强反差、真实机制、可见证据、可转发价值、评论张力或可信边界。",
    "视频号标题和正文优先主打独特视角与用户价值：先判断内容是否具备极致干货、独特见解或同一工具的非显而易见用法，再判断公开爱心是否能强化观看者的判断力/专业感，以及是否存在清晰的熟人转发价值；不要把这些内部判断词直接写给观众。",
    "标题必须通过不可替换测试：换成另一个项目仍成立，就说明钩子太泛。",
    "标题必须通过观众复述测试：看完后能用一句人话讲给朋友，否则重写。",
    "标题钩子必须同时说清项目专属识别物和具体用途；只写星标数、截图数、技能数量、开源/AI工具类别，会让观众不知道这到底是干嘛的，必须重写。",
    "每次先生成至少12个标题候选，覆盖成本收益、停止旧做法、证据+转化、评论争议四类钩子。",
    "每页底部3-5行；每行都要让用户更想读完、保存、转发、尝试或评论。",
    "第一屏像用户问题，不像产品说明书；最大字号优先放痛点、反差、结果或成本取舍。",
    "脚本前必须完成 project_value_scouting：硬事实、可包装价值、最强证据、可吹嘘边界、禁止夸大的点。",
    "脚本前必须完成 retention_share_comment_strategy：停留理由、逐页追看理由、收藏/转发理由、评论钩子和事实边界。",
    "评论钩子要围绕真实取舍、适用场景或边界争议，不要写泛泛的“你怎么看”。",
    "项目名、README hero 图、口号、文件名和视觉符号要作为记忆锚评估，不能只当 metadata。",
    "首屏固定标题、封面标题和发布标题必须来自同一个最高分钩子，不允许后期各写各的。",
    "默认短视频为无口播、4-5页、10秒内；除非用户明确要求，不要按更长结构规划。",
    "Repo/tool/skill 视频必须写清楚项目类型和用户能拿它做什么：这是 Agent Skill、工具、设计资源库、模板、库还是工作流；不要只写“GitHub 项目/AI 工具”。",
    "开源信息有证据时只写“开源免费”；公开视频不要写“商用可用”、MIT 或其他协议名。用户要求授权细节时，把协议原文和风险提醒放到发布包或 internal/technical，不上屏。",
    "收到局部反馈先最小范围修正：不要把单点反馈当成核心重做；默认沉淀规则或局部 patch，不自动重渲染、不自动创建新 release。",
    "中间真实素材动效是内部制作规则，不能把“长图按页面滚动”“页面滚动”“滚动展示”“缩放抖动”等词放进公开视频、封面或发布文案。",
    "用户明确给出目标人群、身份词或“必看/必备/收藏”等提示时，默认把它作为内部受众线索；公开视频和发布文案优先写具体用途、输入资料、输出结果、安装和使用步骤，避免“X人必看”式人群诱导。",
    "公开视频、封面、标题、底部卡片和发布正文要避开模板化 AI 句式、否定转折模板和三段式口号；优先直接写具体用途、输入、输出、安装和使用动作。",
    "短视频信息必须层层递进：每一页只推进一个新信息，上一页提出疑问，下一页回答或推进；默认按问题定位、输入或素材、机制展开、证据证明、输出和实用判断组织。胶囊只写通用结构，不把单条视频、单个项目或单个行业的具体术语沉淀为默认规则。",
    "公开视频、封面、标题、底部卡片和发布正文禁止使用“X 是 Y，不是 Z”“不是 A，而是 B”“X 不是 Y，是 Z”这类说明式否定转折；直接写用途、动作、结果、输入输出或观众收益。",
    "公开视频、封面、标题、底部卡片、发布正文和可见素材截图不得出现网址、域名、URL、二维码、扫码或链接引导；选材时先裁掉或遮住网络地址，裁不干净就换素材。"
  ],
  "user_prompt_public_copy_policy": {
    "default_behavior": "公开文案优先翻译成具体用途、任务收益、输入资料、输出结果、安装和使用步骤，以及事实边界；默认避免“X人必看”式人群诱导。",
    "example_rewrites": [
      {
        "reason": "去掉人群召唤，改成这个 Skill 能完成的具体任务。",
        "user_prompt": "用户给了身份词和必看提示",
        "viewer_facing": "先把商品做一份卖前体检报告"
      },
      {
        "reason": "保留决策场景，不公开放大身份召唤。",
        "user_prompt": "用户给了决策人群提示",
        "viewer_facing": "一屏看清这个项目能不能继续投"
      }
    ],
    "normalization_rules": [
      "用户给出的人群词先用于判断谁会在意、为什么会停下、现有替代做法是什么，而不是直接上屏。",
      "如果项目是单个 Skill，公开视频可以写 Agent Skill；只有项目确实是技能合集时才写 Skills。",
      "必看、必备、收藏等强词默认改写为具体观看理由，例如先判断能不能卖、先生成报告、先检查风险、先给可执行清单。",
      "首屏、底部卡片和发布正文至少一处要说清项目有什么用；安装页要说清把哪个 项目名给 Agent，以及安装后怎么问。",
      "只有身份词安全、不过度圈定、且不带必看诱导时，才可在发布正文里克制提及适用对象。"
    ],
    "public_copy_gate": "如果没有采用用户给出的人群词，不需要在公开视频补偿性出现；必须在公开文案里说明具体用途、输入、输出、安装和使用方法。",
    "purpose": "当用户在需求或反馈里给出明确目标人群、身份词、必看/必备/收藏等传播提示时，胶囊把它当作内部受众线索，不默认照搬进公开视频、封面、标题或发布正文。",
    "required": true
  },
  "visible_copy_lint_tool": {
    "blocker": "Any hit in public copy is a blocker; rewrite to natural audience language before rendering or delivery.",
    "example_command": "python scripts/visible_copy_lint.py <voiceover.txt> <storyboard.json> <publishing.md> --json",
    "when": "Run before delivery on silent card script, storyboard JSON, rendered/public platform copy, and any text that will appear in cards/subtitles/cover."
  }
}

## hook_and_title

{
  "category_difference_result_title_logic": {
    "required": true,
    "core_formula": "熟悉品类 + 反常识新能力 + 具体结果",
    "purpose": "让陌生观众第一眼知道这条内容属于什么任务、这个项目比同类多做了哪一步、最后能拿到什么结果。",
    "why": [
      "只写用户场景会像职场建议，观众不知道它和项目有什么关系。",
      "只写项目名或开源身份会像工具摘要，观众不知道为什么要停。",
      "好标题要先借用户已懂的品类入口，再用一个差异动词钉住项目独特性，最后用输入输出补清楚。"
    ],
    "required_slots": {
      "familiar_category": "用户已经懂的对象、任务或交付物。不要只写项目身份。",
      "old_world": "用户当前怎么痛苦解决，也就是旧世界。要具体到旧动作、旧成本或旧失败。",
      "difference_verb": "项目比同类多做的关键动作，也就是差异动词。要口语、具体、能成画面。",
      "concrete_result": "最后能拿到的东西、判断、文件、报告、清单或可执行下一步。",
      "subtitle_completion": "标题不负责讲完，副标题负责补清楚项目名、输入、输出、边界或证据。"
    },
    "good_shapes": [
      "{品类任务}，现在能先 {差异动作} 了",
      "能 {差异动作} 的 {品类工具}，真的来了",
      "把 {输入材料} 丢给 {工具/Agent}，直接出 {结果}",
      "{一份/一页/一张}{输入材料}，生成 {新结果}",
      "{项目名}：{一句人话差异}"
    ],
    "example_policy": "不要把单条视频的项目名、行业、文件类型、动作词或输出格式写进胶囊示例；只保留可替换的占位结构和判断问题。",
    "safety_boundary": [
      "差异动词可以口语，但必须被项目事实支持。",
      "如果差异动作涉及版权、合规、资质、收益、诊断、投资、法律等边界，底部卡和发布正文必须补清适用条件。",
      "不要用否定转折模板解释机制；用具体输入、动作、输出说清楚。"
    ],
    "hard_tests": [
      "3 秒测试：不解释项目，用户能不能知道这是干嘛的。",
      "替换测试：把项目名换成另一个工具，标题还成立就太泛。",
      "动词测试：标题里有没有一个具体动作，而不是能力、方案、体系、效率这类抽象名词。",
      "旧世界测试：标题是否打破用户对同类工具的旧印象。",
      "画面测试：首屏能不能马上用真实素材证明标题。",
      "复述测试：用户看完能不能跟朋友说一句人话，包含品类、差异动作和结果。"
    ],
    "reject": [
      "只有痛点，没有品类入口，用户不知道是工具、教程还是模板网站。",
      "只有项目名，没有差异动作，用户不知道为什么要看。",
      "只有反差，没有具体结果，用户不知道能拿到什么。",
      "只有功能摘要，删掉项目名后像任何 AI 工具都能说。"
    ]
  },
  "avoid": [
    "AI 自动生成",
    "AI工具分享",
    "GitHub 项目推荐",
    "一个很强的开源项目",
    "今天分享一个 GitHub 仓库",
    "今天给大家介绍",
    "保姆级教程",
    "先讲背景再给结果",
    "免费开源工具",
    "免费开源效率神器",
    "全网最强",
    "只写 GitHub 星标，不写用户结果",
    "只写截图/星标/案例数量，观众不知道项目在解决什么",
    "只写证据数字，但不写核心对象",
    "只报星标数但不说结果",
    "只讲功能摘要，不提最强名字/IP/数字/视觉记忆点",
    "建议大家收藏这个项目",
    "建议收藏",
    "开源 AI 工具",
    "开源项目推荐",
    "把 proof 当主语，例如“2986张截图可回看”但不说是什么课程或 Skill",
    "效率神器",
    "这个项目最近很火",
    "项目名/IP很强却只当 repo name 或背景信息处理",
    "高星标、高截图数、高成本优势等强 proof 被埋到结尾才出现"
  ],
  "bottom_copy": {
    "bad_patterns": [
      "只堆功能、参数、文件名，用户不知道为什么在意",
      "只写 GitHub 星标，不写它解决谁的什么问题",
      "事实很多但没有冲突、成本、收益、评论张力或边界",
      "每页只有来源标签或普通项目说明",
      "把“最佳套路”“全网最强”等无法证明的包装当结论"
    ],
    "card_shape": [
      "line 1: judgment/conflict/hook tied to the visible evidence",
      "line 2: mechanism or workflow change",
      "line 3: project/source proof",
      "line 4: user consequence, quality payoff, or cost/risk implication",
      "line 5: boundary, save/share reason, or comment-worthy tradeoff"
    ],
    "fact_chain_definition": "A fact-chain card starts with the target user’s concern, then adds mechanism, proof, consequence, and boundary/action/comment tension. Facts are chosen because they make the viewer keep reading.",
    "good_example_shapes": [
      "Token 很贵 / 返工更贵 -> README 写死开工顺序 -> TDD/Subagent/Review 做质量闸门 -> 证据只到流程、测试和评审 -> 但团队用 AI 的成本要重算",
      "Agent 一开写就容易跑偏 -> brainstorming/plans/TDD/review 串成开工顺序 -> 每个任务先查该用哪种 skill -> 覆盖多种 Code Agent CLI -> 争议点是值不值这些上下文",
      "高星标背后是质量闸门 -> 它把 Agent 从直接开写拽回来 -> 多耗上下文，少赌返工 -> 真实项目要稳，也要算成本"
    ],
    "public_comment_prompt_examples": [
      "你会为代码质量多烧一倍上下文吗？",
      "Agent 写代码，你更想要快，还是更想要稳？",
      "这种流程适合小团队，还是只适合重工程团队？"
    ],
    "target": "4-5 pages, each with 3-5 dense lines. The viewer should learn one sharp fact-chain even with no narration.",
    "user_interest_gate": [
      "Name the primary user before writing cards.",
      "Name the painful current alternative or desired status/control before selecting facts.",
      "Each fact must answer: why should this user care now?",
      "Each page should create a small curiosity gap that the next page resolves or deepens.",
      "Drop neutral feature lists unless they connect to user cost, quality, speed, money, credibility, safety, or workflow control."
    ]
  },
  "first_screen_formulas": [
    "别再{旧做法}，这个项目能先给你{可见结果}",
    "{数量/证据}个{证据资产}，把{散乱材料}变成{可调用结果}",
    "{付费/笨重工具}可以先停一下，这个开源方案已经能{具体能力}",
    "普通 AI 只能{弱结果}，这个多了{独特机制/可追溯证据}",
    "喂进去{输入材料}，直接拿到{输出产物}，还能回到{证据来源}",
    "不会{专业术语}，也能从{白话输入}查到{结构化线索}",
    "{低成本/本地/开源}跑{高级能力}，先看{实测/文档/界面证明}",
    "界面不花，但它把{高频痛点任务}做到了{具体程度}",
    "{工具A}+{工具B}，把{复杂任务}拆成{低门槛步骤}",
    "{大厂/热点模型}已经很多，先看它能不能落到{普通人场景}"
  ],
  "good_examples": [
    "2986张截图证据，装进Agent",
    "30块钱跑口袋版AI Agent，先看实机",
    "baoyu-skills：把写图文、做图、发平台变成 Agent 可调用技能",
    "你更怕 Token 贵，还是返工贵？",
    "别催 Agent 直接开写",
    "别再手工整理Excel，让AI先生成脚本",
    "别把 Skills 全装进上下文：宝玉这套按需调用",
    "喂一份模板，仿出整套新PPT",
    "学倪师课程，别再一节节翻",
    "宝玉的 21 个 Agent Skills：按需给 Codex/Claude 加工具",
    "界面不花，但它把PDF修复做成了开源全家桶",
    "给 Agent 装一套日常工具箱：21 个技能按需开",
    "耗 Token，但真能压返工",
    "课程检索 Skill：能查证据和边界",
    "这个项目，把 AI 开工顺序管住了",
    "高星标火在它管住 AI 乱写"
  ],
  "hook_archetypes": [
    {
      "formula": "{强 proof 数字}的{名字/IP隐喻}：把{对象}变成{结果}",
      "id": "proof_plus_memory_anchor",
      "use_when": "项目同时有高信任数字和强名字/IP/视觉符号，例如高星标 repo、爆款案例、强品牌名、强隐喻",
      "visual_proof": "首屏同时放数字证据、项目名/视觉锚和核心转化，不让数字或名字任何一方单独抢戏"
    },
    {
      "formula": "把{核心课程/资料}蒸馏成{体系化 Skill/可调用知识库}",
      "id": "subject_to_system_skill",
      "use_when": "课程、知识库、Agent Skill、资料整理类项目的核心价值是把高密度资料体系化",
      "visual_proof": "先出现课程/资料主体和 Skill 结构，再用截图数量、模块覆盖、查询路径证明质量"
    },
    {
      "formula": "先看结果：{输入} -> {输出}; 这个开源项目能把{输入}直接变成{输出}",
      "id": "result_first",
      "use_when": "有真实输出、demo、前后对比或成品画面",
      "visual_proof": "0-3 秒先放结果/成品/前后对比，不先放仓库名"
    },
    {
      "formula": "别再{手工动作}了，这个{工具/Skill}可以{新动作/新结果}",
      "id": "stop_old_way",
      "use_when": "用户有明确手工低效流程",
      "visual_proof": "错误做法或低效流程一闪而过，立刻切新结果"
    },
    {
      "formula": "{数字}{证据资产}，把{对象}变成{结果}",
      "id": "proof_number",
      "use_when": "有星标、截图数量、案例数量、成本、速度等可信数字",
      "visual_proof": "数字必须来自 README、GitHub、截图索引、真实录屏或本地统计"
    },
    {
      "formula": "{付费/笨重工具}可以先停一下，这个开源方案已经能{能力}",
      "id": "paid_or_heavy_replacement",
      "use_when": "确有可验证的开源替代或轻量替代价值",
      "visual_proof": "对比点只讲已验证能力，不写“最强/完爆/全部替代”"
    },
    {
      "formula": "界面不花，但它把{高价值任务}做到了{具体程度}",
      "id": "ugly_but_useful",
      "use_when": "项目 UI 一般但功能硬、技术可信",
      "visual_proof": "用 GitHub、终端、软件 UI、输出结果形成可信链"
    },
    {
      "formula": "先划清边界：{真实安全用途}；不做{错误/高风险用途}",
      "id": "wrong_expectation_reframe",
      "use_when": "项目容易被误解，尤其医疗、金融、法律、安全相关",
      "visual_proof": "首屏或前 8 秒出现边界，不把风险承诺放到结尾才补"
    },
    {
      "formula": "{复杂任务}不用从头学，按{路径/模板/Skill}先跑起来",
      "id": "low_barrier",
      "use_when": "安装、部署、使用门槛明显比用户想象低",
      "visual_proof": "安装界面、配置文件、一次成功的输入输出"
    },
    {
      "formula": "{常规方案}一跑就翻车，换成{机制}才稳",
      "id": "bug_or_failure_progression",
      "use_when": "技术项目能用“出问题 -> 修复 -> 新瓶颈 -> 终局方案”讲清楚",
      "visual_proof": "报错、失败状态、修复后状态都要有画面"
    }
  ],
  "medical_finance_legal_security_rule": "高风险相邻项目要直接写边界：只做检索、学习、整理、复核证据，不给诊断、投资、法律结论或攻击指导。",
  "memorability_gate": {
    "checks": [
      "strongly_related: 标题必须使用目标项目独有或高相关的识别物，例如项目名、作者/IP、核心对象、README 口号、独有机制或标志性素材。",
      "what_it_does_clear: 标题必须让陌生观众知道项目到底解决什么任务、把什么输入变成什么结果，或如何改变工作流。",
      "proof_bound_to_use: stars、forks、截图数、skill 数量、成本、速度等 proof 可以前置，但必须绑定核心对象和核心转化，不能单独当主标题。",
      "non_confusable: 把标题里的项目名换成另一个 repo 后仍然成立，就说明太泛，必须重写。",
      "recall_sentence: 标题应能导出一句自然复述，例如“宝玉这套 skills 是给 Codex/Claude 按需加日常工具的”。"
    ],
    "fail_fast": [
      "不知道项目干嘛的标题直接淘汰",
      "换成任意 AI 工具仍成立的标题直接淘汰",
      "只靠数字、星标、开源、免费、效率神器吸引注意的标题直接淘汰"
    ],
    "reject": [
      "只说明项目身份，没有用户结果",
      "无法在首屏找到对应证据画面",
      "夸大免费、替代、疗效、收益或自动化程度",
      "与视频首屏固定标题不是同一个核心卖点",
      "换成另一个项目名仍然成立，缺少独占记忆点",
      "把强 proof 数字机械放到结尾，浪费第一眼信任",
      "公开标题/正文出现“前置、信任钩子、记忆点、传播资产、策略”等制作词",
      "把为什么这么写标题的内部理由直接说给观众听"
    ],
    "required": true,
    "rule": "标题钩子必须同时说清项目专属识别物和具体用途：观众只看标题，也能知道这是什么、能用来做什么、为什么不能换成另一个项目。",
    "title_slots": {
      "bottom_cards": "展开 proof、安装方式、技能分类、按需使用边界和目标用户为什么会收藏",
      "main_title": "项目专属识别物 + 具体用途/核心转化",
      "subtitle": "强 proof 或边界，例如 21 个 skills / 21.8k stars / 按需安装 / 避免上下文开销"
    }
  },
  "memory_assets": {
    "asset_inventory": [
      "trust_click_proof: stars、forks、截图数、案例数、成本、速度、版本、真实用户或实测结果",
      "memory_anchor: 项目名、人名、IP、隐喻、视觉符号、口号、动作、仪式、可复述短句",
      "core_transformation: 什么对象被变成什么新产物或新能力",
      "contrast: 旧做法 vs 新路径、普通工具 vs 独特机制、用户原本的成本 vs 项目给出的新选择",
      "visual_proof: 首屏能放哪张图、哪个数字、哪个 demo 或哪段真实 UI",
      "boundary: 哪些不能夸大，如何把边界写成可信度"
    ],
    "hard_tests": [
      "friend_retell_test: 观众能否用一句人话复述，例如“23.5k 星的女娲，用公开资料造思维分身”",
      "non_replaceable_test: 把项目名换成另一个 repo 后仍成立，则钩子太泛",
      "three_second_cover_test: 只看封面/首屏 3 秒，是否同时知道为什么值得点开和为什么值得记住",
      "proof_balance_test: 数字是否前置建立信任，同时没有遮住核心 promise",
      "ip_not_metadata_test: 项目名、IP、隐喻、视觉符号是否被当成故事资产，而不是角标信息"
    ]
  },
  "platform_title_styles": {
    "bilibili": "机制讲清楚：项目机制 + 证据数字 + 适用边界。",
    "douyin": "短、硬、先数字或动作：{数字证据}+{具体结果}；正文第一句直接痛点。",
    "kuaishou": "口语短句：先说烦恼，再说怎么查/怎么跑。",
    "wechat_channels": "可信、克制、适合转发：证据 + 边界 + 适合谁。",
    "xiaohongshu": "收藏笔记感：适合谁收藏 + 为什么省时间 + 清单化证据。"
  },
  "principle": [
    "标题从“项目身份/能力介绍”改为“结果、反差、证据、低门槛、边界”优先。",
    "第一屏必须同时保留第一眼信任或可见 proof、最强记忆锚、核心对象和核心转化；强 proof 不要埋到最后，项目名/IP/隐喻也不能当 metadata。",
    "第一屏先说清：这是什么 + 为什么值得收藏。",
    "先打真实使用痛点，再给可复用结果；最大字号服务痛点、转化或结果。",
    "证据和项目元信息可以出现，但不要抢最大字号；内部制作/版本词不上屏。",
    "最大字号不能只放 proof 或类别名；必须让不认识项目的观众立刻知道“这是什么 + 用来完成什么任务”。"
  ],
  "public_language_rule": "传播资产审计是内部策略。公开成片、字幕、卡片、封面、平台正文不能出现“前置、信任钩子、记忆点、传播资产、策略”等制作词；必须翻译成自然观众语言，例如“这个仓库已经 23.5k stars，点进去才发现它火得有原因”。",
  "publishing_titles": {
    "backup_count": 8,
    "candidate_mix": {
      "audience_specific": 2,
      "boundary_trust": 2,
      "contrast_or_replacement": 2,
      "memory_anchor_or_ip": 2,
      "non_replaceable_hook": 1,
      "pain_stop_old_way": 2,
      "proof_number": 2,
      "proof_trust_front": 2,
      "result_first": 2
    },
    "must_include": [
      "至少 1 个标题带可验证数字或证据资产",
      "至少 1 个标题带具体目标人群",
      "至少 1 个标题把边界写成可信度",
      "至少 1 个标题使用停止旧做法、低门槛试用或边界判断结构",
      "至少 1 个标题把强 proof 数字前置，并绑定核心对象和转化",
      "至少 1 个标题使用项目名/IP/隐喻作为记忆锚",
      "最终标题必须通过不可替换测试和观众复述测试",
      "至少 1 个标题把强 proof 数字和项目名/IP/隐喻绑定，而不是二选一",
      "至少 1 个标题通过观众复述测试，能被一句话讲给朋友",
      "至少 1 个标题使用项目名字、IP、视觉符号或隐喻作为主记忆点"
    ],
    "recommended_count": 1
  },
  "purpose": "Title and bottom copy extraction are the main creative work of this capsule; visuals prove the claim, but copy creates retention.",
  "required_dimensions": [
    "项目专属识别度",
    "具体用途清晰度",
    "不可替换性",
    "proof 与承诺绑定程度",
    "目标用户停留/收藏理由"
  ],
  "title_scoring": {
    "audience_recall": "观众是否能用一句人话转述给朋友",
    "contrast": "是否存在旧做法 vs 新路径、普通工具 vs 独特机制的反差",
    "memory_anchor": "标题是否包含观众会记住的名字、IP、隐喻、视觉符号或短句",
    "non_replaceability": "把项目名换掉后是否仍成立；越不可替换越高分",
    "proof_density": "是否带星标、截图、案例、成本、版本、真实 UI 等证明；proof 只能加分，不能替代 subject 和 transformation",
    "risk_control": "是否避开夸大承诺，并把边界写成可信度而不是削弱卖点",
    "save_value": "观众是否会觉得值得收藏或评论求安装笔记",
    "subject_clarity": "标题是否明确核心对象：项目/课程/工具/人名/资料类型，观众能否一眼知道在看什么",
    "task_specificity": "是不是具体到一个用户任务，而不是泛泛工具推荐",
    "transformation_clarity": "标题是否明确核心转化：蒸馏成 Skill、克隆成模板、修复成文件、部署成服务等",
    "visible_result": "首屏能不能立刻展示结果/失败/对比/证据"
  },
  "title_workflow": [
    "先做 propagation_asset_inventory：强 proof 数字、名字/IP隐喻、视觉符号、反差、可复述短句。",
    "先写 audience_recall_sentence：观众会怎么向朋友复述这条内容。",
    "判断 strong_proof_should_front：如果 stars/截图/成本/速度足够高信号，必须生成前置数字标题。",
    "做 non_replaceable_test：换项目名仍成立的标题降权或淘汰。",
    "做 non_replaceable_test：换项目名后仍成立的标题必须重写。",
    "强 proof 数字不要默认后置；判断是否应进封面、首屏、开头画面或平台文案。",
    "先写 audience_recall_sentence：观众能讲给朋友的一句话。",
    "先做 propagation_asset_inventory：强数字、名字/IP、隐喻、视觉符号、口号、反差、评论点。",
    "先写 core_subject：这条到底讲谁/什么项目/什么资料，例如 倪海厦课程、PPT模板、PDF扫描件。",
    "再写 core_transformation：它被做成了什么新产物，例如 体系化 Skill、可交付 PPT、可检索知识库、可运行服务。",
    "再写 category_difference_result_title：熟悉品类 + 反常识新能力 + 具体结果。标题如果缺品类入口、差异动词或输出结果，先重写。",
    "为主标题和副标题分工：主标题负责停留，副标题负责补项目名、输入材料、输出结果和边界。",
    "再写 proof：星标、截图、案例、成本、版本、真实 UI、demo。proof 只证明转化，不替代转化。",
    "先填 value_card：目标用户、用户任务、痛点敌人、项目结果、独特机制、证据素材、边界提醒。",
    "从 hook_archetypes 至少生成 12 个标题候选，不同类别都要覆盖。",
    "每个候选标注画面证据：首屏能放什么、5 秒内能证明什么。",
    "用 title_scoring_rubric 打分，只选总分最高的一个做固定顶部标题。",
    "封面标题、发布推荐标题、视频首屏标题沿用同一核心钩子；平台文案只调整语气，不换卖点。"
  ],
  "viewer_copy_forbidden_terms": [
    "前置宣传",
    "前置",
    "信任钩子",
    "记忆点",
    "传播资产",
    "策略",
    "trust hook",
    "memory anchor",
    "front the proof",
    "proof fronting"
  ]
}
