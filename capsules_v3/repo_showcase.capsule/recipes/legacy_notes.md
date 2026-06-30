# Legacy Notes

## adaptive_bottom_layout_policy

{
  "line_count_presets": {
    "1-2": "更大字号和更宽行距，填充卡片高度。",
    "3": "大字号、较宽行距，优先解决周围空的问题。",
    "4": "中等字号和行距，保持信息密度。",
    "5+": "收紧字号和行距，优先不溢出、不压脚注。"
  },
  "purpose": "底部卡片根据 bottom_lines 数量自动调整字号和行距，避免 3 行挤在中间，也避免 5 行溢出。",
  "qa_requirement": "每次改动底部布局后抽取 contact sheet 和 0.4/2.4/4.4/6.4/8.4 秒关键帧，检查底部文字是否充满、可读、无遮挡、无截断。",
  "renderer_behavior": "render_repo_showcase_video.py exposes bottom_body_typography() and draw_bottom() uses its body_size/body_size_min/line_step/line_step_max values before fitting real text width.",
  "required": true
}

## copy_hook_patterns

{
  "fit_for_silent_cards": "默认 short_silent_repo_showcase 没有口播时，也要先写卡片级叙事草稿，再压缩成底部 4-5 行完整句。这样底部卡才有故事，不会像功能清单。",
  "narrative_modes": {
    "mode_a_tool_review": {
      "arc": [
        "焦虑",
        "共鸣",
        "惊喜",
        "信服",
        "行动"
      ],
      "name": "工具评测",
      "scene_mapping": "第 1 页给具体焦虑，第 2 页说旧办法为什么难受，第 3 页给意外能力，第 4 页用真实素材或数字证明，第 5 页给边界和下一步。",
      "use_when": "视频重点是一个 repo/tool/skill 能不能帮用户解决具体工作问题。"
    },
    "mode_b_industry_info": {
      "arc": [
        "好奇",
        "震惊",
        "恍然大悟",
        "期待"
      ],
      "name": "行业资讯",
      "scene_mapping": "第 1 页抛出反常识或高 proof，第 2 页给令人意外的变化，第 3 页解释为什么会这样，第 4-5 页给可期待的后续和边界。",
      "use_when": "视频重点是一个新趋势、开源动向、行业变化或项目爆火原因。"
    }
  },
  "numeric_anchoring": {
    "allowed_anchors": [
      "GitHub stars/forks/releases/examples/screenshots",
      "README 写明的样例数量、文件数量、模型数量、导出格式",
      "本地实测耗时、渲染时长、输出页数、关键帧数量",
      "用户场景里的页码、改稿轮数、文件大小、会议时长"
    ],
    "guardrail": "没有可靠数字时，不硬编百分比；可以用页数、样例数、星标数、场景数字做锚点。",
    "pattern": "以前{时间/成本}，现在{时间/成本}。便宜{数字}%，不是{数字}折，是{数字}%",
    "rule": "每次对比尽量用具体数字，不用空泛形容词。"
  },
  "pain_concretization": {
    "bad_example": "AI 太贵了，普通人用不起。",
    "good_example_shape": "以前用 {工具/流程} 做一次 {复杂任务}，成本够 {具体消费锚点}。现在用 {新方案} 跑同样的事，花的钱连 {更小消费锚点} 都不到。",
    "guardrail": "数字和对比必须有来源、测量或明确标注为编辑推断；没有证据时用保守表达，不编具体百分比。",
    "repo_showcase_examples": [
      "以前改一页 AI PPT，要把整张图重新做。现在至少能点进文本框和图表继续修。",
      "以前找一个截图证据要翻 40 分钟课程。现在先问 Skill，它直接把相关片段拎出来。",
      "以前让 Agent 直接开写，20 分钟后才发现方向错了。现在先把 spec、测试和 review 卡住。"
    ],
    "rule": "不抽象说效率低、价格高、质量差；必须极度具象化场景，最好带对象、时间、成本、页码、文件类型、返工动作或失败后果。"
  },
  "public_language_gate": "对标公式可以作为内部生成器；公开视频、标题和发布文案不能出现公式名、钩子公式、痛点公式、数字锚定、叙事模式等制作术语。",
  "purpose": "为 repo_showcase 的标题、底部价值卡和发布文案提供可复用钩子模式；保留对标账号的停留逻辑，但所有表达必须回到仓库事实和可证明价值。",
  "required": true,
  "required_output_when_copy_planning": [
    "静音卡片叙事稿",
    "选中标题",
    "章节划分",
    "徽章时间表",
    "每幕 bottom_title 和 4-5 行 bottom_lines",
    "发布正文和置顶评论"
  ],
  "short_silent_open_source_skills_flash": {
    "copywriting_rules": {
      "ending": [
        "视频结尾继续给信息，不写互动动作。",
        "最后一页优先补结果、证据、边界、适用场景或怎么问。",
        "不引导站外联系或非官方渠道。"
      ],
      "title": [
        "先写观众利益，再写工具名。",
        "有数字就前置数字；没有证据就用场景词，不硬编百分比。",
        "标题留下一个缺口，但正文和视频必须兑现。"
      ],
      "visible_copy": [
        "每张图只保留一个主信息。",
        "大字优先写结果、痛点、数字、身份，不写概念定义。",
        "辅助字用 10-18 个字补证据或场景。",
        "无 TTS 时不要写需要读 5 秒的长句。"
      ]
    },
    "cover_and_title_rules": {
      "cover": "封面只放一个大判断和一个证据锚点，例如工具名、stars、输出截图或 5 张图结构。",
      "ending": "结尾页不写互动动作，只做价值密度总结：结果、证据、适用场景、边界或一个可直接复用的问题。",
      "opening_0_3s": "0-3 秒由第 1 张图和第 2 张图前半段共同完成：先给结果或痛点，再马上补旧方法的难受。",
      "structure": "第 1 张停下，第 2 张共鸣，第 3 张证明工具存在，第 4 张证明有用，第 5 张继续补价值密度和边界。",
      "title": "标题负责人群 + 结果 + 好奇缺口，优先短句，避免内部公式名。"
    },
    "evidence_guardrails": [
      "每个可见 claim 必须能被 repo、README、截图、demo、stars、license、实测输出或编辑计数支撑。",
      "不能直接套模板；模板变量必须改成具体仓库名、具体用户场景和具体结果。",
      "不要默认商用可用、开源免费、完全替代人工、永久免费或官方认证。",
      "避免神器、王炸、必看、全网最强、闭眼入等无法证明或广告感强的词。",
      "不使用长钩子、旁白依赖、字幕解释或需要 TTS 才能成立的结构。",
      "视频内不写评论、关注、收藏、下条、安装承接或任何互动动作。"
    ],
    "five_card_flash_structure": [
      {
        "big_text_goal": "4-8 个字给结果、痛点、数字或身份。",
        "role": "hook",
        "time": "0-2s",
        "visual": "结果截图、公式卡、GitHub 星标、工具界面中最强的一帧。"
      },
      {
        "big_text_goal": "写旧动作或旧成本，让观众觉得自己也这样。",
        "role": "pain_or_context",
        "time": "2-4s",
        "visual": "手写提示词、翻 README、复制粘贴、反复改稿等旧流程证据。"
      },
      {
        "big_text_goal": "证明工具存在，不写长说明。",
        "role": "repo_or_skill_proof",
        "time": "4-6s",
        "visual": "repo 首页、README 核心图、目录、stars、demo、workflow 文件。"
      },
      {
        "big_text_goal": "给输出、前后对比或用户场景。",
        "role": "result_or_use_case",
        "time": "6-8s",
        "visual": "输出样例、生成结果、对比图、可复用流程截图。"
      },
      {
        "big_text_goal": "收束最强价值点、证据边界或使用场景。",
        "role": "value_density_summary",
        "time": "8-10s",
        "value_examples": [
          "适合把重复流程存起来",
          "证据来自 README 和输出样例",
          "边界：先验证结果，再放进工作流"
        ],
        "visual": "输出样例、能力清单、边界说明、可复用问题或 repo 关键信息。"
      }
    ],
    "format": {
      "bgm_only": true,
      "copy_limits": {
        "big_text_chars_cn": "4-8",
        "long_paragraphs_allowed": false,
        "primary_messages_per_image": 1,
        "support_text_chars_cn": "10-18"
      },
      "duration_seconds": 10,
      "image_count": 5,
      "no_video_action_prompt": true,
      "page_logic": "每一页都有丰富的价值点，靠结果、场景、证据、边界和对比完成停留。",
      "route": "short_silent_repo_showcase",
      "seconds_per_image": 2,
      "sequence": [
        "hook",
        "pain_or_context",
        "repo_or_skill_proof",
        "result_or_use_case",
        "value_density_summary"
      ],
      "subtitle": false,
      "tts": false
    },
    "opening_hook_cards": [
      {
        "best_for": "能展示输出样例的 repo 或 skill。",
        "hook_type": "result_first",
        "image_1_big_text": "自动出脚本",
        "image_1_support_text": "给一个选题，吐出标题+分镜",
        "image_2_big_text": "以前从零写",
        "image_2_support_text": "现在把流程存成 skill"
      },
      {
        "best_for": "替代重复劳动、降低操作成本的 workflow。",
        "hook_type": "pain_first",
        "image_1_big_text": "别再手写提示词",
        "image_1_support_text": "重复流程应该存起来",
        "image_2_big_text": "每次都重来",
        "image_2_support_text": "选题、拆钩子、写标题全靠复制"
      },
      {
        "best_for": "高星工具、热榜项目、功能清晰的开源 repo。",
        "hook_type": "number_first",
        "image_1_big_text": "10秒看懂这个 repo",
        "image_1_support_text": "5 张图只讲一个结果",
        "image_2_big_text": "先看能做啥",
        "image_2_support_text": "再看证据和边界"
      }
    ],
    "output_when_copy_planning": [
      "选中的 title_hook_library 类型",
      "标题 3-5 个候选",
      "封面大字和辅助字",
      "0-3 秒钩子两张图文案",
      "5 张图的 big_text/support_text/visual_evidence/role",
      "第 5 页价值密度总结和事实边界"
    ],
    "purpose": "为开源 skills、AI workflow、GitHub 工具类 repo_showcase 提供 10 秒静音快闪的标题、封面、0-3 秒钩子、5 张图结构和价值密度模板。",
    "required": true,
    "selection_rule": "先从 title_hook_library 选择 1-2 类，再用仓库事实、目标人群和可见证据改写；不能直接套模板，不能编造数字、商用可用、开源免费或完全替代。视频内不放互动、关注、收藏、下条或安装承接。",
    "title_hook_library": {
      "GitHub热榜": {
        "cover_examples": [
          "热榜新工具",
          "高星快闪",
          "先看结果"
        ],
        "formula": "GitHub 热榜/高星项目 + 第一个强结果",
        "guardrail": "不要只罗列项目名；必须补一个可见结果或明确适用人群。",
        "title_examples": [
          "今天 GitHub 热榜，第一个能帮 AI 减负",
          "这周 3 个开源 skills，第 2 个适合剪辑号",
          "高星工具快闪：先看能输出什么"
        ],
        "use_when": "做每日/每周工具快闪、涨星项目、官方工具或多 repo 清单。"
      },
      "去痛替代": {
        "cover_examples": [
          "别再手写提示词",
          "别再从零剪",
          "少翻文档"
        ],
        "formula": "不用 [旧成本]，也能 [具体结果]",
        "guardrail": "旧成本要具体到动作，结果要能被截图、输出样例或仓库说明证明。",
        "title_examples": [
          "别再手写提示词，先把流程存成 skill",
          "不用从零剪辑，也能先拆出爆款钩子",
          "不用翻半小时文档，先让 Agent 抓重点"
        ],
        "use_when": "skill 替代重复手工动作，或开源 repo 减少付费、翻文档、反复复制粘贴。"
      },
      "反常识": {
        "cover_examples": [
          "流程才稳定",
          "别只看功能",
          "重点是复用"
        ],
        "formula": "[常见误区] -> [真正卡点] -> [repo/skill 解决物]",
        "guardrail": "反差必须落到具体 repo、skill、输出或截图；不要写成抽象观点。",
        "title_examples": [
          "AI 写得慢，可能卡在流程",
          "普通提示词不够，流程才稳定",
          "这个 skill 重点不是酷，是能复用"
        ],
        "use_when": "需要把观众从提示词、单个工具名、单点功能，转向可复用流程和工作流结果。"
      },
      "数字证明": {
        "cover_examples": [
          "5张图看懂",
          "10秒看懂",
          "3步出稿"
        ],
        "formula": "[可核验数字] + [成本/结果变化]",
        "guardrail": "数字只能来自仓库、截图、本地实测或明确的编辑计数；没有来源时不用百分比。",
        "title_examples": [
          "5 张图，讲清一个开源 skill",
          "10秒看懂这个 repo",
          "3 步把选题变成视频脚本"
        ],
        "use_when": "README、GitHub、实测流程或生成结果里有星标、样例数、步骤数、页面数、耗时等数字。"
      },
      "结果公式": {
        "cover_examples": [
          "自动出脚本",
          "一键拆钩子",
          "流程跑起来"
        ],
        "formula": "[工具/skill A] + [工具/skill B] = [具体结果]",
        "guardrail": "等号右边必须是观众能看懂的结果，不写框架、协议、生态这类解释词。",
        "title_examples": [
          "Codex + Skills = 自动出脚本",
          "账号诊断 Skill + 对标库 = 下一条可发稿",
          "GitHub 工具 + AI 工作流 = 10 秒找素材"
        ],
        "use_when": "两个工具、一个 skill 加一个资料库，或 repo 接入 Agent 后能产生可见输出。"
      },
      "身份锁定": {
        "cover_examples": [
          "剪辑号先收",
          "运营可收藏",
          "开发者先看"
        ],
        "formula": "[窄人群] 先看/先收的 [N] 个 skill 或工具",
        "guardrail": "人群必须窄；不要写所有人必看，也不要用无法证明的强迫感压用户。公开视频优先写具体用途和可见结果。",
        "title_examples": [
          "AI 创作者先看这 3 个 skills",
          "剪辑号先收：找对标、拆钩子、写标题",
          "做 Agent 开发，先补这套流程"
        ],
        "use_when": "观众身份明确，例如 AI 创作者、剪辑号、账号运营、Agent 开发者、产品经理。"
      }
    },
    "version": "2026-06-29"
  },
  "title_hook_formulas": {
    "contrast_suspense": {
      "formula": "同样是 {X}，{Y} 和 {Z} 哪个更让你心动？",
      "label": "对比悬念",
      "repo_showcase_guardrail": "比较对象必须具体，不能比较一个真实项目和一个稻草人。",
      "use_when": "可以做两个真实选项的取舍，例如好看但改不动 vs 可编辑、快但返工多 vs 慢但稳定。"
    },
    "counterintuitive_opening": {
      "formula": "怪不得都说 {X}，因为 {Y}",
      "label": "反常识开头",
      "repo_showcase_guardrail": "Y 必须是仓库事实、README 证据、截图结果或合理编辑推断；不要把普通功能包装成反常识。",
      "use_when": "项目有一个反直觉判断，例如看起来不是最炫的工具，却解决了更真实的返工、成本或质量问题。"
    },
    "free_or_low_cost_surprise": {
      "formula": "居然是免费版/开源版的 {XX}，{项目名} 你到底还藏着什么？",
      "label": "免费/低成本惊喜",
      "repo_showcase_guardrail": "只有证据足够时才写免费、开源或低成本；不默认写商用可用，不暗示完整替代付费产品。",
      "use_when": "仓库确实开源、免费可试或明显降低试错成本。"
    },
    "must_know": {
      "formula": "真的我不允许 {目标用户} 还不知道 {项目/能力}",
      "label": "不准不知道",
      "repo_showcase_guardrail": "不要泛写所有人必看；必须点名具体人群和具体工作场景。",
      "use_when": "项目对明确人群有强相关性，例如打工人、产品经理、运营、开发者、做汇报的人。"
    },
    "surprising_use": {
      "formula": "没想到 {X} 还能这么用",
      "label": "惊喜发现",
      "repo_showcase_guardrail": "惊喜点要能在中间真实素材里看见，不能只靠文案强行制造惊讶。",
      "use_when": "仓库把熟悉对象变成意外用途，例如 PPT、PDF、截图、课程、代码库、Agent Skill 被接入新流程。"
    }
  },
  "tone": {
    "avoid": [
      "全网最强、吊打、闭眼入、神器、必须收藏等无法证明或广告感强的词。",
      "报告腔：该项目提供、核心能力、价值体系、生态能力。",
      "空泛热情：太强了、太震撼了、效率翻倍，但没有场景和数字。"
    ],
    "do": [
      "用具体场景开头，而不是介绍项目。",
      "允许轻微第一人称判断，例如我会先下载样例拆开看。",
      "用反问推进评论和判断，例如你更怕它丑，还是更怕后面改不动？"
    ],
    "target": "口语化、有安利感、有反问句和感叹句，但不冷冰冰评测，也不做倾向性广告。"
  },
  "version": "2026-06-27-self-media-hook-patterns"
}

## revision

{
  "edit_revision_rules": [
    "先复述本次只改什么、不改什么；局部反馈默认局部处理。",
    "不自动重渲染、不自动创建新 release，除非用户明确要求替换成片或 QA 需要。",
    "把可复用的反馈沉淀到胶囊规则、测试或 lint，而不是每次重做一个版本。"
  ]
}

## humanized_repo_value_cards_policy

{
  "bottom_card_rules": [
    "每个 bottom_lines 条目必须是一句完整的话，不写碎片标签。",
    "每行只推进一个钩子、判断、痛点、证据或边界。",
    "底部卡片默认 3-5 行，写用户为什么停留、保存、转发或评论，不写文件/命令操作指南。",
    "允许使用具象痛点公式，但要中性可信，不写倾向性广告和保证结果。",
    "优先写具体场景、数字、文件类型、可下载样例、输出形态和限制条件。"
  ],
  "copy_review_loop": [
    "用户进入文案确认流程时，先给标题、每幕 bottom_title、bottom_lines 和发布文案，不先渲染。",
    "用户批准后再渲染；若 QA 发现溢出，只做等意压缩并记录原因。"
  ],
  "forbidden_public_patterns": [
    "核心差异",
    "能力边界",
    "生态能力",
    "可信边界",
    "README 反复强调",
    "这说明",
    "这决定",
    "真正值得看的是",
    "X 是 Y，不是 Z",
    "不是 A，而是 B",
    "不只是 A，更是 B",
    "HOOK",
    "卖点",
    "痛点",
    "策略",
    "传播资产"
  ],
  "humanizer_pass": [
    "删掉意义膨胀、促销词、抽象总结、报告味标题、三段式口号和假金句。",
    "少用漂亮但无信息量的判断句；一句话删掉项目名仍通用就重写。",
    "允许口语化和轻微判断，但所有判断必须能回到 README、样例、截图或源码事实。"
  ],
  "layout_preflight": [
    "渲染前检查 bottom_lines 行长；含英文、数字或 .pptx 等混排时进一步缩短。",
    "如果关键帧出现横向溢出、截断或难读，不通过压低字号硬扛，先压缩句子再重渲染。",
    "上屏句子优先控制在约 26 个中文等效字符以内；必须更长时拆成两句，但每句仍要完整。"
  ],
  "purpose": "把 repo_showcase 的上屏文案从项目介绍改成高密度用户价值卡，同时降低 AI 味和渲染溢出风险。",
  "required": true,
  "source_grounding": [
    "先读 README/docs/examples/source_asset_manifest，抽取项目真实能力、样例、边界和可见结果。",
    "优先把仓库结果图、产物图、机制图、图表、UI/demo/GIF/视频对应到具体用户价值。",
    "没有 rich visuals 时才用 README 主页面渲染内容区截图；源码、命令、文件树、manifest 只做最多一页证明。"
  ]
}

## identity

{
  "applicable_to": [
    "GitHub 仓库介绍",
    "AI 工具推荐",
    "Agent Skill 展示",
    "设计/开发工作流项目",
    "有真实 demo 或可视化证据的开源项目"
  ],
  "not_applicable_to": [
    "没有 demo、效果图或明确使用场景的项目",
    "无法证明差异化、只能泛泛宣传的项目",
    "逐步安装教学型长视频"
  ],
  "positioning": "通用 GitHub/AI 工具/Agent Skill 价值展示视频胶囊；先提炼用户价值，再套 3:4 视觉系统。PPT 模板克隆只是验证案例。",
  "skill_capsule_fit_contract": {
    "capsule_role": "Concrete repo-showcase defaults: 3:4, no narration, 4-5 pages, <=10 seconds, real screenshots, user-interest-driven fact-chain bottom cards, tech gradient background, BGM, middle-panel motion, project value scouting, and retention/share/comment hypothesis.",
    "conflict_rule": "Latest route config wins: short_silent_repo_showcase is the only exposed repo_showcase route: no voiceover, 4-5 pages, <=10 seconds, BGM only.",
    "keep_compact": "Do not keep older longer/page-heavy, narration-default, or low-density bottom-copy rules as active rules. Do not keep multiple incompatible hook frameworks; merge them into project_value_scouting plus retention_share_comment_strategy.",
    "skill_role": "video-production handles routing, artifact discipline, QA, visible-copy lint, and run/revision notes recording. craft-viral-clips contributes hook, first-2-second retention, packaging, and comment-prompt discipline."
  }
}

## narrative_arc

{
  "compact_fact_chain_structure": {
    "bottom_lines": "3-5 lines per page",
    "duration": "<=10 seconds",
    "page_arc": [
      "问题定位: what concrete problem makes the viewer stop and what question remains unanswered",
      "输入或素材: what the viewer, model, tool, or workflow needs before it can work",
      "机制展开: what process, rule, decomposition, generation, or organization makes the result possible",
      "证据证明: what screenshot, file, demo, number, comparison, or case proves the mechanism",
      "输出和下一步动作: what artifact, action, installation/use path, save reason, or next step the viewer can take"
    ],
    "page_count": "4-5 pages",
    "principle": "Start from the user’s strongest self-interest, then choose facts that increase curiosity, proof, perceived value, disagreement, or credibility.",
    "reject_if": [
      "facts are neutral feature stacking with no user consequence",
      "bottom copy only labels the middle screenshot source",
      "comment prompt is generic or unrelated to the project tradeoff",
      "claim sounds exciting but cannot be mapped to a visible fact or supported inference"
    ],
    "required": true
  },
  "progressive_information_arc_policy": {
    "core_rule": "每一页只推进一个新信息；底部文案不能把问题、输入、机制、证据、输出和行动一次性堆完。",
    "generality_rule": "胶囊只沉淀通用结构，不写入某条视频、某个项目、某个行业或某个仓库的专属术语；具体项目词只出现在单次 profile、release 或 run notes。",
    "page_link_rules": [
      "上一页提出的疑问，下一页必须回答或推进，不允许每页都是并列功能点。",
      "每页底部标题只承担一个动作或判断：问题、输入、机制、证据、输出或行动，不能混写。",
      "中间真实素材负责证明当前页的新信息；底部文字负责解释为什么这个信息值得继续看。",
      "如果任意调换两页顺序后不影响理解，说明递进不足，必须重写。",
      "最后一页不能只做口号收尾，必须给可执行动作：尝试入口、安装路径、提问示例、下载方式、保存理由或下一步。"
    ],
    "purpose": "短视频信息必须层层递进，让观众每一页都获得新答案，同时产生继续看下一页的理由。",
    "reject_patterns": [
      "五页都是项目功能清单",
      "每页只换截图但底部信息没有推进",
      "首屏把所有信息讲完，后面只重复展开",
      "最后一页没有承接前面输出产物"
    ],
    "required": true,
    "required_arc": [
      "问题定位：先让观众知道这条内容解决什么具体问题，并留下为什么需要继续看的疑问。",
      "输入或素材：说明需要给工具、模型或流程什么材料，让观众知道使用门槛。",
      "机制展开：解释它如何拆解、处理、判断、生成或组织信息，避免只喊结果。",
      "证据证明：用真实截图、文件、demo、对比、数字或案例证明上一页机制成立。",
      "输出和下一步动作：说清最终产物、可执行动作、尝试入口、安装/使用路径或提问方式。"
    ]
  },
  "retention_share_comment_strategy": {
    "card_quality_gate": [
      "Every bottom card must contain at least two of: pain pressure, unexpected value, real proof, mechanism, user consequence, boundary, debate/comment tension.",
      "A card that only names files, features, or screenshots fails unless it also says why the target user cares.",
      "The final publishing package must include a comment prompt that asks for judgment, not a generic “你怎么看”."
    ],
    "comment_trigger_patterns": [
      "tradeoff: “你更怕 Token 贵，还是返工贵？”",
      "workflow judgment: “你会让 Agent 开工前先问一轮吗？”",
      "team debate: “小团队该追求快交付，还是先把 AI 工作流管住？”",
      "boundary debate: “这种流程是质量护栏，还是 token 黑洞？”"
    ],
    "default_page_arc_4_to_5_pages": [
      "Page 1: sharp verdict or tradeoff. Make the viewer feel the problem is about their workflow.",
      "Page 2: mechanism. Explain what the project changes, not just what it contains.",
      "Page 3: proof. Show README, repo page, source file, demo, numbers, or real [final artifact path omitted].",
      "Page 4: consequence. Translate the mechanism into quality, time, risk, cost, credibility, or control.",
      "Page 5 optional: boundary plus action/comment. Give the credible limit and one reason to save, share, try, or argue."
    ],
    "positioning": "This is a default high-probability hypothesis, not a universal best routine. For serious releases, write the hypothesis first and validate with A/B data when possible.",
    "public_language_rule": "Do not expose terms like retention, share trigger, strategy, or hypothesis. Translate them into natural viewer-facing copy.",
    "purpose": "Make each short repo showcase optimize for stop, stay, save/share, and comment instead of only summarizing facts.",
    "required_internal_fields": [
      "primary_audience: the specific people likely to stop scrolling",
      "stop_reason_0_2s: proof, pain, identity pressure, contradiction, or visible result that makes them pause",
      "stay_reason_page_to_page: the curiosity gap that pulls the viewer through 4-5 pages",
      "save_or_share_reason: the reusable checklist, workflow warning, tool lead, or team discussion value",
      "comment_trigger: a real judgment question, tradeoff, or disagreement tied to the project facts",
      "fact_boundary: what is directly proven, what is an editorial inference, and what must not be claimed",
      "wechat_value_angle: hard_value, distinctive_view, or unexpected_use selected for title/body copy",
      "wechat_like_signal: what public endorsement says about the viewer without exposing the internal label",
      "wechat_share_target: the concrete person/group/use situation that makes forwarding practically useful"
    ],
    "share_save_patterns": [
      "Save because it is a checklist for using coding agents without乱开工.",
      "Share because it gives a team a concrete debate about AI coding cost versus quality.",
      "Forward to people already using Codex/Claude/Cursor/Gemini, not to vague AI-curious viewers."
    ]
  }
}

## public_self_media_copy_policy

{
  "body_rules": [
    "正文按真人推荐口吻写，先说为什么停住，再说项目怎么解决，再说证据和边界。",
    "不要逐条复述 README；把 README 事实翻译成具体改稿、返工、保存、拆源文件、后续维护等场景。",
    "不要写成信息点排列；句子之间要有自然推进。",
    "标题可以保留强 proof 数字，但正文不能只围绕数字展开。"
  ],
  "comment_rules": [
    "置顶评论必须问一个用户真的会选的问题。",
    "不要写 欢迎评论/你怎么看 这类泛互动。",
    "优先用两个具体困扰做对比，让用户容易回答。"
  ],
  "humanizer_checks": [
    "删掉报告腔、意义膨胀、模板化否定转折和泛泛称赞。",
    "如果删掉项目名后正文仍适用于任何 AI 工具，必须重写。",
    "公开文案不能像 README 摘要，必须有具体场景和真人判断。"
  ],
  "opening_rules": [
    "正文第一句优先从目标用户的具体场景切入。",
    "允许轻微第一人称或真人判断，但判断必须能被 README、样例或源素材支撑。",
    "不要用 这是一个/这个仓库提供了/核心价值是 这类说明书开头。"
  ],
  "purpose": "避免发布标题、正文、置顶评论写成 AI 味 README 摘要或信息点排列。",
  "required": true
}

## publishing

{
  "artifact_landing_standard": {
    "current_pointer_rule": "Update CURRENT_RELEASE.md after QA passes; explicitly say older versions should not be used when they were superseded.",
    "manifest_required_fields": [
      "version_slug",
      "status",
      "source_url",
      "final_video",
      "cover",
      "publishing_package",
      "qa_report",
      "lint_report",
      "created_at",
      "supersedes"
    ],
    "public_folder_rule": "Only public/ should be cited for publishing/handoff. It must not contain hook bakeoffs, value cards, strategy notes, failed drafts, secrets, or signed URLs.",
    "purpose": "Avoid loose artifact dumps and ambiguous v1/v2/v3 roots; every accepted [final artifact path omitted] lands as a clean release package.",
    "required": true,
    "root_layout": [
      "CURRENT_RELEASE.md at [final artifact path omitted] points to the current approved release",
      "release/<version_slug>/README.md explains what to use and what not to use",
      "release/<version_slug>/release_manifest.json records final paths, QA, lint, source, and predecessor",
      "release/<version_slug>/public/ contains only final publishable assets",
      "release/<version_slug>/qa/ contains QA/lint/review frames",
      "release/<version_slug>/technical/ contains render status, ffprobe and runtime details",
      "release/<version_slug>/internal/ contains value cards, hook bakeoffs, storyboards, compliance notes"
    ],
    "version_rule": "Create a new release/<version_slug>/ for every accepted replacement. Do not force the user to infer the latest version from scattered filenames."
  },
  "final_install_usage_card": {
    "avoid": [
      "MIT",
      "商用可用",
      "复杂安装教程",
      "制作过程术语",
      "网址",
      "域名",
      "二维码",
      "扫码",
      "链接引导"
    ],
    "duration_seconds": 1.0,
    "required_lines": [
      "安装：使用项目名作为检索线索，让它查找并确认可用流程",
      "使用：发你的任务、素材和目标场景",
      "怎么问：按当前项目用途给一个可直接复制的问题"
    ]
  },
  "local_script_contract": {
    "inputs": [
      "--topic",
      "--params",
      "--output-dir"
    ],
    "profile_extensions": {
      "hero_value_text": "可选：一行大字，写本项目对目标用户最核心的转化或结果。",
      "image_mode": "可选：contain 或 cover。仓库截图默认建议 contain，避免真实 UI 被裁掉。",
      "top_subtitle_font_size": "可选：副标题字号，脚本会自动适配。",
      "top_title_font_size": "可选：顶部标题字号，脚本会自动适配。",
      "value_badges": "可选：大字标签，写用户身份、痛点或结果；证据标签放小字。"
    },
    "qa_command": "python scripts/local_video_qa.py --run-dir <run_dir> --aspect-ratio 3:4 --require-prompts",
    "required_outputs": [
      "release/video.mp4",
      "release/copy.txt",
      "qa/run_notes.json",
      "prompts/prompt_index.json",
      "publishing manifest",
      "qa/visible_text_for_lint.txt",
      "qa/visible_copy_lint.json"
    ],
    "script_package_path": "script/render_repo_showcase_video.py"
  },
  "publishing_package_rules": {
    "body_rules": [
      "正文第一段直接说用户痛点",
      "第二段说项目独特价值，不复述泛泛项目身份",
      "后面给证据、适用场景、边界提醒",
      "正文逻辑必须和视频首帧一致，不能换成另一个卖点",
      "视频号正文开头要说明目标用户为什么值得看：给方法、判断、避坑、可复用动作、独特分析或非显而易见用法之一，再给证据和边界。",
      "当用户提供明确人群提示时，正文第一句或第一段优先使用该人群表达，并立刻说明为什么值得看。"
    ],
    "default_path": "[final artifact path omitted]",
    "manifest_rule": "发布包必须写入 publishing manifest，category 为 publishing_package",
    "platform_copy_directory": {
      "adaptation_rules": [
        "视频号偏可信克制，标题和正文优先呈现独特视角与用户价值，正文强调证据、边界和清晰的熟人转发理由",
        "小红书偏收藏笔记，正文清单化，强调适合谁和为什么收藏",
        "快手偏口语短句，先说痛点，再说怎么查",
        "B站偏结构化项目介绍，可以展开项目机制、模块覆盖和适合人群",
        "抖音偏短标题强钩子，正文短，第一句必须是痛点或数字证据"
      ],
      "default_path": "[final artifact path omitted]",
      "manifest_rule": "多平台目录必须写入 publishing manifest，category 为 platform_copy_directory；platform_copy_manifest.json 也要写入。",
      "per_platform_required_sections": [
        "平台适配说明",
        "推荐标题",
        "标题备选",
        "正文或简介",
        "标签",
        "评论引导或置顶评论",
        "发布提醒"
      ],
      "required": true,
      "required_files": [
        "README.md",
        "wechat_channels.md",
        "xiaohongshu.md",
        "kuaishou.md",
        "bilibili.md",
        "douyin.md",
        "platform_copy_manifest.json"
      ]
    },
    "required": true,
    "required_sections": [
      "推荐标题",
      "标题备选",
      "封面文字",
      "视频号正文",
      "短正文",
      "标签",
      "置顶评论",
      "评论区引导",
      "发布提醒"
    ],
    "risk_rules": [
      "医疗、金融、法律、投资等高风险领域，正文和置顶评论必须保留边界提醒",
      "不要使用暗示直接决策、保证效果或替代专业服务的标题",
      "发布提醒必须列出不能夸大的词和平台风险点"
    ],
    "tag_rules": [
      "8-15 个标签",
      "包含项目品类、目标用户、具体能力和平台语境",
      "至少一半标签必须和项目真实能力相关，避免堆泛词"
    ],
    "title_alignment_rule": "推荐标题、封面文字和片内顶部固定标题尽量使用同一个核心钩子。",
    "title_rules": [
      "推荐标题只给一个最建议发布的版本",
      "标题备选给 6-10 个，覆盖强痛点、强结果、证据数字、适用人群和边界可信度",
      "标题不要只写开源项目推荐、AI工具分享、效率神器，必须写具体用户收益",
      "至少一个标题带项目最强证据或差异点，例如 2986张截图证据、一键复刻模板、本地可控",
      "视频号推荐标题优先选择能表达独特视角和用户价值的版本；不得为了互动而牺牲项目事实、具体用途或可信边界。",
      "用户给出的“谁必看/谁必备”提示必须进入至少一个推荐标题或标题备选；最终推荐标题优先选择事实安全且人群清晰的版本。"
    ]
  }
}

## quality_rules

- 公开视频和可见文案禁止出现 MIT、商用可用、长图按页面滚动、页面滚动、滚动展示、缩放抖动；命中就改成用户能理解的项目类型、结果、证据或边界。
- 公开视频不要默认写“商用可用”；开源信息只写“开源免费”，除非用户明确要求授权细节。
- 最终安装/使用页应控制在最后 1 秒左右，只写把 项目名发给 Agent、确认可用流程，以及一个怎么问的例子。
- 用户只反馈一个细节时，不要把单点反馈当成核心重做；先说明变更范围，不自动重渲染。
- {
  "category": "copy",
  "id": "user_prompt_utility_translation_required",
  "rule": "当输入或反馈包含明确目标人群、身份词或“必看/必备/收藏”等传播提示时，默认作为内部受众线索；公开文案必须翻译成具体用途、输入资料、输出结果、安装和使用方式，并避免“X人必看”式人群诱导。",
  "type": "copy_review"
}
- {
  "category": "copy",
  "id": "ai_flavored_template_copy_forbidden",
  "rule": "公开视频、封面、标题、底部卡片和发布正文不得使用模板化 AI 句式、否定转折模板或三段式口号；必须直接写具体用途、输入资料、输出结果、安装方式或下一步动作。",
  "type": "copy_review"
}
- {
  "category": "copy",
  "id": "progressive_information_arc_required",
  "rule": "默认 4-5 页短视频必须层层递进：每一页只推进一个新信息；上一页的疑问由下一页回答或推进；推荐顺序是问题定位、输入或素材、机制展开、证据证明、输出和下一步动作；如果调换页面顺序不影响理解，说明信息链太平，必须重写。",
  "type": "copy_review"
}
- {
  "category": "copy",
  "id": "no_x_is_y_not_z_template",
  "rule": "公开视频、封面、标题、底部卡片和发布正文禁止使用“X 是 Y，不是 Z”“不是 A，而是 B”“X 不是 Y，是 Z”这类解释式否定转折；必须改成具体动作、结果、输入输出、用户收益或可执行下一步。",
  "type": "copy_review"
}

## repo_showcase_current_playbook

{
  "copywriting": {
    "bottom_cards": [
      "底部卡默认优先 5 行，允许 4 行；少于 4 行需要明确原因。",
      "每一行都必须是完整句子，不能是碎片标签。",
      "每行只推进一个痛感场景、事实证据、机制信息、输出价值或可信边界。",
      "不要写文件说明、命令说明、操作指南或 README 摘要。",
      "删掉任意一行后，用户理解明显变少，才算有效信息。"
    ],
    "forbidden_public_patterns": [
      "核心差异",
      "能力边界",
      "生态能力",
      "可信边界",
      "README 反复强调",
      "真正值得看的是",
      "X 是 Y，不是 Z",
      "不是 A，而是 B",
      "不只是 A，更是 B",
      "HOOK",
      "卖点",
      "痛点",
      "策略",
      "传播资产"
    ],
    "hook_pattern_usage": "写标题、底部卡或发布正文前，先从 method.copy_hook_patterns 选择 1-2 个钩子模式；再用仓库事实、人群场景和数字锚点改写，不能直接套模板。",
    "hook_style": [
      "可以使用具象痛点公式，但必须落到真实用户场景、数字、文件类型、输出形态或返工代价。",
      "不要抽象说效率低、能力强、价值高；改成具体场景，例如改数字、拆图表、下载样例、二次精修。",
      "不要反复说同一件事；每页必须递进一个新信息。"
    ],
    "humanizer_gate": "如果删掉项目名后文案仍适用于任何 AI 工具，或者有 AI 味、README 摘要感、报告总结感、模板化金句感，就必须重写。",
    "overall_tone": "自媒体推荐口吻，但不做倾向性广告；要像人真的看完仓库后给出的判断。",
    "title": "标题优先绑定强 proof 数字、项目名和核心可用价值；不要只写 GitHub 项目推荐、AI 工具分享或功能分类。"
  },
  "default_route": "short_silent_repo_showcase，默认 3:4、8-10 秒、4-5 页、BGM only；没有明确要求时不做口播、不烧字幕、不做视频内 CTA。",
  "layout": {
    "bottom_density": "底部卡根据 3/4/5 行自动调整字号和行距；5 行收紧但不溢出，3 行放大并增加间距避免全挤在中间。",
    "middle_motion": "中间主视觉不要默认全都从左往右进入；根据图片比例和内容特征选择上下滑、左右滑、中心放大或局部放大，让观众看清图片里的关键结果和机制。",
    "middle_visual": "中间素材标题只是证据标签，不承担主叙事；画面足够清楚时可省略或减弱。",
    "safe_area": "默认不画实心安全区黑条，背景网格和光效铺满 3:4 画布。",
    "top_title": "两行顶部标题默认 top_title_line_gap_preferred >= 16；标题带描边时必须抽首帧检查，不能重叠、贴住或笔画互相挤压。"
  },
  "purpose": "把 repo_showcase 从仓库摘要视频沉淀成高浓度、真实素材优先、真人自媒体口吻的 repo 价值展示胶囊。",
  "required": true,
  "version": "2026-06-27-revision notes-rollup",
  "video_page_logic": "每一页都有丰富的价值点；5 页分别承担停留、痛点、证据、结果、价值密度总结，不把最后一页留给评论、关注、收藏、下条或安装承接。",
  "visual_selection": {
    "fallback_scope": "README fallback 必须截主页面/渲染内容区，裁掉浏览器地址、URL、侧栏、文件列表、命令块和源码视图。",
    "priority": [
      "先审计仓库自带结果图、产物图、输出预览、示例 deck、gallery、图表和 UI/demo 画面。",
      "其次使用仓库或文档中的机制图、架构图、流程图、能力图、对比表和数据图表。",
      "再考虑 README/docs 内嵌的丰富视觉素材，前提是它们能证明当前页主张。",
      "仓库 rich visuals 不足时，才使用 README 主页面或渲染内容区截图。",
      "源码、命令、文件树、manifest、README 源码截图只做 proof-only，rich visuals 可用时默认最多 1 页。",
      "自制总结卡和 AI 概念图是最后 fallback，必须记录原因并得到用户认可。"
    ],
    "qa": "source_asset_manifest 要标注 result_visual、mechanism_visual、demo_ui_visual、readme_main_page_screenshot 或 proof_only_text_screenshot；contact sheet 中 rich visuals 应占多数。"
  },
  "workflow": {
    "copy_review": "用户要求先看文案时，必须先给标题、章节、每幕 bottom_title/bottom_lines、发布正文和置顶评论；用户认可后再渲染。",
    "revision": "局部反馈先局部修正并沉淀规则；只有用户明确要求或 QA 必须时才重做整条视频。",
    "qa": "成片前跑视频 QA、visible_copy_lint、URL/内部术语扫描、artifact manifest 路径检查、contact sheet 和关键帧抽检。",
    "release_gate": "最终 public/ 里 copy.txt、publishing_package.md、platform_copy_manifest.json 必须保持同一版人化文案；重渲染后要检查 copy.txt 是否被覆盖回 profile 摘要。"
  }
}

## routing

{
  "audio_rules": [
    "Only route: no narration, no TTS, and no burned subtitles; visible cards plus BGM carry the message.",
    "Only route: 4-5 pages, about 2 seconds each, total duration <=10 seconds.",
    "Only route: use the packaged Manten Diloty BGM asset or another local BGM; verify an audio track exists."
  ],
  "coding_agent_quality_tradeoff_hook": {
    "accepted_examples": [
      "很耗 Token，但真能提升代码质量",
      "这个插件不省 token，但代码更稳",
      "别只催 AI 快点写代码",
      "多花 token，少返工"
    ],
    "applies_to": [
      "coding agent workflow projects",
      "developer quality tools",
      "TDD/review/debugging/process repositories",
      "tools that spend more context/time to reduce rework"
    ],
    "guardrails": [
      "必须有真实素材支撑流程、TDD、评审或验证机制",
      "不要承诺自动保证质量；表达为减少乱改、减少返工、更稳",
      "成本词如 token、时间、步骤要和可见收益绑定，不能只做耸动标题"
    ],
    "required_when_applicable": false,
    "rule": "当项目的真实卖点是用更多上下文、token、步骤或验证换代码质量时，标题优先考虑成本/收益反差，而不是只写项目类型。"
  },
  "default_route": {
    "id": "short_silent_repo_showcase",
    "owns": [
      "duration",
      "layout",
      "visible copy",
      "real source material priority",
      "aspect-aware middle motion",
      "tech gradient background",
      "BGM"
    ],
    "rule": "Use this route for repo_showcase: no voiceover, 4-5 pages, <=10 seconds."
  },
  "knowledge_skill_lane": {
    "accepted_examples": [
      "倪海厦课程，蒸馏成体系化 Skill",
      "把倪师课程整理成可调用 Skill",
      "一套倪海厦课程 Skill：能检索、能追溯、有边界"
    ],
    "positioning": "用于课程/知识库/Agent Skill 类仓库。主标题必须表达“核心资料被体系化蒸馏成 Skill”，不要只写证据数量。",
    "reject_examples": [
      "别再一节节翻，2986张截图可回看",
      "2986张截图证据，装进Agent"
    ],
    "title_formulas": [
      "把{核心课程}蒸馏成体系化 Skill",
      "{核心课程}，被整理成一套可调用 Skill",
      "一套{核心课程}Skill：能检索、能追溯、知道边界",
      "把散乱{资料类型}整理成{体系化学习 Skill}",
      "{人群}学{核心课程}，先用这套 Skill 找路径和证据"
    ],
    "title_slots": {
      "bottom_cards": "展开痛点、模块覆盖、白话入口、截图证据和边界",
      "main_title": "核心对象 + 核心转化，例如 倪海厦课程 / 蒸馏成体系化 Skill",
      "subtitle": "证明和边界，例如 2986张截图证据 / 可检索 / 可追溯 / 不做诊断处方"
    }
  },
  "mode_selection_rules": {
    "conflict_resolution": "If old audio/TTS notes conflict with config.default_route, follow default_route and ignore voiceover/subtitle checks.",
    "default": "short_silent_repo_showcase",
    "short_silent_when": [
      "user asks for this capsule",
      "repo/tool/skill showcase",
      "each image about 2 seconds",
      "no narration or no voiceover",
      "social-feed quick recommendation"
    ]
  },
  "ppt_template_clone_specialization": {
    "case_frame_structure": [
      "强钩子：喂一份模板 / 仿出整套新 PPT",
      "痛点对比：普通 AI PPT / 不像你的公司",
      "审美完成度：第一版 / 就要像个样",
      "核心差异：模板克隆 / 才是杀手锏",
      "交付友好：客户只改一页 / 别毁整套",
      "真实素材：截图和 Logo / 别让 AI 乱画",
      "适用人群：最适合 / 手里有模板的人",
      "边界与结论：别用错场景 / 它不是校对器"
    ],
    "core_user_value": "一键复刻你的 PPT 模板审美，蒸馏版式、配色、字体节奏，生成能交付的新主题 PPT。",
    "first_screen_examples": [
      "喂一份模板 / 仿出整套新 PPT",
      "把你的模板 / 复刻成精美 PPT",
      "旧模板换新主题 / 还保留高级感"
    ],
    "viral_hypothesis": "让观众相信：这个仓库不是普通 AI PPT 生成器，而是能把自己的 PPT 模板审美复刻成一套精美专业新稿。"
  },
  "validated_short_silent_repo_showcase": {
    "activation": "The only exposed route for this capsule.",
    "audio": "Use BGM only; do not generate TTS, voiceover, or subtitles.",
    "avoid": [
      "facts that only describe the repo but do not explain why the viewer should care",
      "low-density slogan cards",
      "internal production/version words on screen",
      "generic tool praise without a target user",
      "longer/page-heavy variants unless the capsule contract is intentionally changed",
      "claiming any routine is the universal best instead of treating it as a testable hypothesis",
      "flat page lists where every scene is a parallel feature point instead of a progressive information chain"
    ],
    "copy_principle": "Every visible line must answer why the primary user cares, why they continue reading, what proof supports the claim, what they may save/share, or what judgment they may comment on.",
    "duration": "4-5 pages, about 2 seconds each, total duration <=10 seconds.",
    "layout": [
      "Top fixed title: one strong hook, usually 1-2 lines, aligned with cover and publishing title.",
      "Middle panel: real repo/README/plugin/skill/docs/demo evidence wherever available; generated summary cards are fallback only.",
      "Bottom card: 3-5 dense fact-chain lines selected by user interest, not neutral fact stacking."
    ],
    "narrative_arc": "问题定位 -> 输入或素材 -> 机制展开 -> 证据证明 -> 输出和下一步动作。每页只推进一个新信息，下一页承接上一页的问题。",
    "planning_hook": "Before writing pages, define primary user, current painful alternative, project value scouting, retention/share/comment hypothesis, and visible proof.",
    "route_id": "short_silent_repo_showcase"
  }
}

## top_title_spacing_policy

{
  "defaults": {
    "top_subtitle_suffix_default": "",
    "top_title_line_gap_preferred": 16,
    "top_title_max_h": 166
  },
  "purpose": "两行顶部标题必须有明确行距，避免中文、英文和描边在视觉上粘连或重叠。",
  "qa_requirement": "标题为两行时必须抽首帧检查；如果两行标题贴住、描边重叠或中文笔画互相挤压，增加 top_title_line_gap 后重渲染。",
  "renderer_behavior": "draw_title() uses top_title_line_gap_for_profile() for both title fit and draw_centered(); renderer fallback default is 16, and profiles may override top_title_line_gap when a title needs more breathing room.",
  "required": true
}

## user_usefulness_revision_policy

{
  "conflict_resolution": "当“机制展开”和“不要讲技术实现”冲突时，优先讲用户可观察的流程、前提、结果和边界；只有开发者受众需要时才展示实现术语。",
  "ecosystem_constraint_handling": "用户指定地域、行业或工具生态时，素材和案例优先贴合该生态；与项目事实冲突时先暴露冲突，不擅自硬套。",
  "implementation_detail_handling": {
    "allowed_when": "目标受众是开发者或技术决策者，且术语会直接影响能不能用、怎么评估风险或结果质量。",
    "default": "技术实现细节进入 internal/technical，不作为公开视频主体。",
    "translate_to_user_language": [
      "把依赖/命令改写成使用前准备。",
      "把 API/协议改写成能拿到的资料类型和结果。",
      "把源码/脚本改写成可验证的输出或边界。",
      "把技术失败码改写成用户能采取的下一步。"
    ]
  },
  "public_copy_should_answer": [
    "目标用户是谁，以及他们会用自己的话怎么描述问题。",
    "用户现在不用这个项目时通常怎么做，代价或风险在哪里。",
    "可以交给项目的输入、材料、对象或上下文是什么。",
    "适合的 2-3 个具体工作场景是什么。",
    "使用前要确认的权限、账号、文件、数据、授权或质量前提是什么。",
    "用户最后拿到的输出物是什么，能接到哪个后续流程。",
    "哪些事情它不负责，哪些缺口要显式列出。"
  ],
  "purpose": "把一次具体反馈泛化为 repo/tool/skill 展示的默认审稿门槛：公开内容先服务用户判断和使用，不从实现路线出发。",
  "visual_material_ladder": [
    "项目/仓库自带真实视觉资产",
    "README/docs 内嵌真实素材或内容区截图",
    "项目方/官方/primary-source 网页或产品截图",
    "真实 source/SKILL/manifest 截图，只用于证明特定边界",
    "生成总结卡，仅在无真实素材并经用户同意时使用"
  ]
}

## value_scouting

{
  "project_value_scouting": {
    "fact_to_packaging_map": [
      {
        "boundary": "Do not claim it automatically guarantees code quality.",
        "fact": "Repo says it is a complete software development methodology with composable skills.",
        "value_packaging": "不是普通提示词包，是把开工顺序和质量动作变成可触发流程。"
      },
      {
        "boundary": "State as workflow discipline, not magic execution.",
        "fact": "README describes design signoff, implementation planning, subagent work, inspection, and review.",
        "value_packaging": "它把 Agent 从“直接开写”拉回需求、设计、计划、实现、评审链路。"
      },
      {
        "boundary": "Use only as repo contribution boundary, not a universal benchmark.",
        "fact": "Public contributor guide says the repo has a 94% PR rejection rate and closes low-quality PRs fast.",
        "value_packaging": "这个项目的狠点，是把 AI 乱交差的代价摆到台面。"
      },
      {
        "boundary": "Only list harnesses visible in the current source.",
        "fact": "Repo lists support for multiple coding-agent harnesses.",
        "value_packaging": "它不是绑死一个 Agent，而是想把同一套方法迁移到多种 CLI/IDE。"
      }
    ],
    "forbidden_packaging": [
      "保证代码质量",
      "自动替你完成高质量 PR",
      "完全替代工程师评审",
      "所有项目都适合",
      "只要装上就不会返工"
    ],
    "purpose": "Act like a scout: find what is worth amplifying in the project while staying inside the factual boundary.",
    "required": true,
    "scout_sequence": [
      "Collect hard facts first: README claims, repo stats, releases, supported platforms, source files, demos, screenshots, docs, issues, PR rules, and changelog.",
      "Find the viewer pressure: what pain, cost, risk, status, credibility, time, or money does this fact touch?",
      "Turn fact into value angle: mechanism, transformation, avoided failure, new workflow, lower barrier, proof of trust, or credible boundary.",
      "Mark the claim boundary: direct fact, supported inference, or forbidden overclaim.",
      "Pick the strongest combination of proof + memory anchor + core transformation + comment tension."
    ],
    "superpowers_example_angles": [
      "不主打省 Token，主打少返工、少乱写、少低质量 PR 风险。",
      "可吹嘘点不是“更快写代码”，而是“先让 Agent 学会停下来”。",
      "评论钩子应围绕成本取舍：多烧上下文换质量，到底值不值？"
    ],
    "value_asset_types": [
      "strong proof numbers: stars, forks, versions, screenshots, cases, cost, speed, adoption, or visible [final artifact path omitted]",
      "workflow reversal: the project makes users stop doing an old/default behavior",
      "anti-failure mechanism: the project prevents a failure the target audience already fears",
      "credible boundary: the project is more trustworthy because it says what it does not do",
      "multi-platform reach: support across popular CLIs/IDEs only when the repo itself proves it",
      "team implication: why a small team, maintainer, or power user may need to recalculate workflow cost"
    ]
  },
  "skill_collection_hook_gate": {
    "accepted_patterns": [
      "给 Agent 接一条内容生产线：抓资料、做图卡、发平台",
      "宝玉这套 skills，把 Codex/Claude 变成内容工作台",
      "不是聊天助手：这 21 个 skills 让 Agent 会做图、排版、发布",
      "从 YouTube/网页抓素材，到公众号/X 发出去：一套 Agent skills"
    ],
    "checks": [
      "workflow_named: 标题或首屏必须命名具体工作流，例如内容生产、资料抓取、图文设计、发布分发、代码质量、研究整理等。",
      "signature_examples_visible: 前 8 秒必须出现 3-5 个高画面感代表技能或结果，避免抽象说“工具合集”。",
      "audience_self_interest: 文案必须说明目标用户为什么会用：省哪一步、补哪个能力、把什么交给 Agent 做。",
      "count_as_proof_only: skill 数量只能做 proof 或副标题，不能替代核心用途。",
      "cluster_before_catalog: 先归类成 2-4 个用户能理解的任务簇，再列具体技能；不要把 21 个名字平铺成清单。"
    ],
    "recommended_clusters": [
      "内容生产：小红书图卡、信息图、SVG 图表、封面、幻灯片、知识漫画、文章插图",
      "资料处理：YouTube 转录、网页转 Markdown、X 转 Markdown、公众号摘要、Electron 抽取",
      "发布分发：发 X、发公众号、发微博",
      "格式工具：压图、Markdown 排版、Markdown 转 HTML、翻译",
      "AI 后端：多供应商图像生成、Gemini Web 文本/图片"
    ],
    "reject_examples": [
      "宝玉的 21 个 Agent Skills",
      "21 个 skills，别一次全装",
      "一个 AI Agent 效率工具合集",
      "2.1 万星的开源 skills 仓库"
    ],
    "required": true,
    "rule": "skills/tools 集合只是 user_value_translation_gate 的特例：先讲用户工作流和可用结果，再用数量和代表技能证明。",
    "why": "核心不是“数量翻译”，而是让观众理解这个集合对自己的具体用途。"
  },
  "user_value_translation_gate": {
    "accepted_patterns": [
      "把 Agent 变成内容工作台：抓资料、做图卡、发平台",
      "给 Codex/Claude 补一条图文生产线，而不是只陪你聊天",
      "网页/YouTube/X 进来，图卡/HTML/公众号出去",
      "多花 token 换代码更稳：流程、测试、审查都进 Agent 工作流"
    ],
    "checks": [
      "what_is_it: 陌生观众只看标题和前 2 秒，也能说出项目是什么类型的东西。",
      "user_job: 文案必须对应一个具体用户任务，例如抓资料、生成图文、做图解、发布平台、改代码质量、整理知识等。",
      "useful_outcome: 必须说清输入变成什么输出、或旧流程被缩短/变稳/变可控在哪里。",
      "source_depth: README 不足以解释价值时，必须继续看源码目录、skill 文件、脚本、配置、截图或 examples。",
      "proof_serves_value: stars、forks、数量、截图数、命令、文件名只作为证明，不能代替用户价值。",
      "bole_not_invention: 可以把事实包装成用户收益和工作流意义，但不能发明功能、保证效果或扩大适用范围。"
    ],
    "reject_patterns": [
      "只说“开源 AI 工具/效率神器/GitHub 项目推荐”",
      "只说 stars、forks、skill 数量、截图数量",
      "把 README 小标题平铺成清单，但没有说明用户为什么在意",
      "标题需要看完整 README 才知道项目干嘛",
      "从作者/工具介绍者视角出发，没有转成目标用户的任务和收益"
    ],
    "required": true,
    "rule": "标题、首屏和事实链必须回答目标用户的“这是什么、对我有什么用、为什么现在值得看/收藏”。不能只讲项目身份、README 摘要、星标、数量或作者视角。",
    "scouting_sources": [
      "README/README.zh: 定位、安装、作者明确提醒和示例命令",
      "skills/*/SKILL.md 或同级说明: 每个 skill 的真实触发场景、输入输出和限制",
      "scripts、packages、plugin/marketplace 配置: 项目实际注册了什么、如何运行、哪些能力是可用的",
      "screenshots、examples、docs: 最能让观众看懂结果的真实产物证据",
      "issues/releases/changelog: 稳定性、近期维护和边界事实，必要时再查"
    ],
    "special_case_skill_collections": {
      "example_clusters": [
        "内容生产：图卡、信息图、图表、封面、幻灯片、漫画、插图",
        "资料处理：YouTube/网页/X/公众号转成可用文本",
        "发布分发：X、公众号、微博",
        "格式整理：压图、排版、HTML、翻译"
      ],
      "rule": "如果项目是 skills/tools 集合，先归纳用户工作流，再选 3-5 个最有画面感的代表技能或产物上屏；数量只是 proof。"
    },
    "why": "观众不是来听仓库介绍的；他们只会为自己的任务、焦虑、成本、质量、创作效率或工作流改善停下。Agent 要像伯乐一样从仓库事实里找出对用户有用的价值。"
  },
  "value_extraction_method": {
    "scoring_dimensions": [
      "痛点强度",
      "结果具体度",
      "差异化",
      "画面可证明",
      "受众规模",
      "可信度",
      "记忆点强度",
      "可复述性",
      "不可替换性",
      "信任数字前置价值",
      "评论争议潜力",
      "事实边界清晰度"
    ],
    "selection_rule": "先选最高分“可传播价值组合”，不是只选功能摘要：proof + memory anchor + core transformation + viewer pressure + fact boundary.",
    "source_scan_order": [
      "GitHub repo page: stars, forks, releases, description, topics, license",
      "README: headline promise, supported platforms, install flow, demo images, workflow description",
      "source files and manifests: real mechanisms, skill names, hook/bootstrap files, examples",
      "docs/CLAUDE/AGENTS/contributor rules: quality gates, boundaries, anti-slop requirements",
      "issues/FAQ/changelog: user pain, recent changes, repeated failure modes, limitations"
    ],
    "value_card_fields": [
      "目标用户：谁会真的想保存或转发这个项目",
      "用户任务：他原本要完成什么工作",
      "痛点敌人：现在最烦、最慢、最容易翻车的地方",
      "硬事实：README/源码/截图/数字/规则能证明什么",
      "可包装价值：这些事实说明它解决了什么高价值问题",
      "独特机制：为什么不是普通同类工具",
      "最强证据：哪张图、哪个文件、哪个数字、哪条规则能上屏",
      "收藏/转发理由：观众为什么会把它发给团队或朋友",
      "评论钩子：哪一个真实取舍最容易引发判断",
      "边界提醒：哪些承诺不能乱说",
      "观众复述句：不用术语，能讲给朋友的一句话"
    ]
  }
}

## visual

{
  "actual_source_image_gate": {
    "definition": {
      "actual_source": [
        "repo-provided [final artifact path omitted] asset",
        "README/docs embedded image or media from the project",
        "real [final artifact path omitted] screenshot from the project or primary source",
        "cropped GitHub README/docs/source-file content screenshot when no project image exists",
        "web original/raw image or video frame from a primary source"
      ],
      "not_actual_source": [
        "agent-made summary/evidence card",
        "PIL/HTML recreated README excerpt",
        "manually retyped source fact card",
        "AI-generated concept image",
        "generic stock-like illustration"
      ]
    },
    "failure_example": "The 20260621 Markdown office run used reconstructed source-evidence cards; those must fail this gate in future runs.",
    "purpose": "Prevent fake-real evidence cards from replacing actual screenshots or project images.",
    "required": true,
    "workflow": [
      "First audit repo-provided visual assets and README/docs embedded media.",
      "If no repo images exist, capture actual GitHub README/docs/source content screenshots with URL/browser chrome removed.",
      "Create inputs/source_asset_manifest.json before rendering and map every scene image to an asset_id.",
      "Reject release approval if fewer than 4 middle visuals are actual_source in a 4-5 scene default video.",
      "Use fallback generated cards only after user approval and mark them visibly in internal QA, never as actual_source."
    ]
  },
  "content_aware_motion_policy": {
    "profile_fields": [
      "content_features",
      "motion_direction",
      "motion_focus",
      "motion_amount"
    ],
    "required": true,
    "rule": "中间主视觉动效根据图片比例和内容特征选择：长图上下滑、宽图左右滑，细节密集图表/UI/PPT 缩略图做中心或局部放大，普通图再用干净滑入。"
  },
  "layout_revision_policy": {
    "middle_visual_title": "中间素材标题只是来源/证据标签，不承担主叙事；画面证据足够清楚时可省略。",
    "rule": "顶部主标题默认上移；顶部副标题可常驻追加“”；中间素材标题默认变小，必要时可省略，避免抢底部事实链。",
    "usage_hint": "使用方法类提示优先放顶部副标题后缀，不挤占底部事实链。"
  },
  "real_source_middle_visual_policy": {
    "avoid_fixed_asset_rule": "不要固定套用某几张图或固定 README 截图模板；每个仓库根据实际提供的 GitHub 素材、demo、文档、源码证据和外部原素材重新选中间主视觉。",
    "default": "每次先做仓库丰富视觉资产审计：优先选择仓库里的结果图、产物图、示例图、图表、机制图、流程图、UI/demo 截图、GIF、视频或 gallery。只有这些不存在、不可访问、不可读或无法证明主张时，才考虑 README 主页面/渲染内容区截图。不要默认用代码、命令、文件名、README 源码截图充主视觉。",
    "fallback_rule": "只有当 GitHub 素材、外部原始素材和可截图 README 内容都无法访问、不可读或无法证明主张时，才允许生成证据卡；fallback 原因必须写入 internal/ 或 qa/ notes。",
    "first_version_gate": "第一版 contact sheet 中如果中间主视觉大多是生成总结卡，而不是 GitHub 自带素材、外部原始素材、README 内容截图或真实页面/源码证据，应视为需要重做，不记录成功运行。",
    "minimum_real_source_frames": 4,
    "motion_rule": "长图按宽度铺满中间区域并从上往下展示；宽图/横视频按高度铺满并从左往右展示；比例接近时做局部放大。",
    "readme_screenshot_rule": "README 截图是结果图/机制图/demo 素材不足时的 fallback；必须截渲染后的 README 主页面或内容区，不能截 README 源码、纯代码目录、文件列表、命令块、侧栏、浏览器地址栏或任何露出链接的区域。",
    "required": true,
    "result_visual_majority_gate": "如果仓库存在可用结果图、机制图、图表、demo 或 UI 输出，默认 4-5 页中至少 3 页中间主视觉应来自这些 rich visuals；代码/命令/文件/README 源码截图不得占多数。",
    "source_file_proof_limit": "源码、命令、manifest、文件树和 README 源码截图只做 proof-only：当它们证明具体能力且 rich visuals 无法证明时才用；rich visuals 可用时默认最多 1 页。",
    "source_priority": [
      "仓库结果图/产物图/示例图/导出预览/前后对比/丰富图表",
      "仓库机制图/架构图/流程图/能力图/对比表/数据图表",
      "仓库 demo、UI、gallery、GIF、视频或可视化输出截图",
      "README/docs 内嵌的丰富视觉素材",
      "相关 primary-source 网页里的原始结果图或机制图",
      "README 主页面或渲染内容区截图，仅在前面素材不足时使用",
      "源码、命令、文件树、manifest、SKILL.md 截图，仅限证明特定主张且最多少量使用",
      "自制总结卡，仅限真实素材和 README 主页面截图都不可用并记录 fallback 原因"
    ],
    "story_copy_pairing": "真实素材负责证明，底部卡负责钩子和故事。不要因为换成真实素材就削弱底部叙事；底部仍要保留反差、机制、收益、边界、收口。",
    "web_original_rule": "网上素材只接受相关原始图片、官方/项目方 demo、原始 UI/产物视频或未二次解说加工的素材；不要用解说、reaction、搬运混剪、教程讲解或二次加工视频当主素材。"
  },
  "rich_visual_first_revision_2026_06_27": {
    "fallback": "实在没有 rich visuals 时，使用 README 主页面/渲染内容区截图；不要用 README 源码卡、代码命令名、文件树或文本重排卡替代。",
    "qa": [
      "source_asset_manifest must label which scenes are result_visual, mechanism_visual, demo_ui_visual, readme_main_page_screenshot, or proof_only_text_screenshot.",
      "contact sheet must show rich result/mechanism/demo visuals as the majority when available.",
      "if text/code screenshots are the majority, internal QA must document that no rich visuals were available and show the audit evidence."
    ],
    "required": true,
    "rule": "Repo showcase 主视觉优先选仓库里的结果图、产物图、机制图、图表、UI/demo/gallery 等能吸引停留的丰富视觉；README/源码/命令/文件截图只能做 fallback 或 proof-only。"
  },
  "safe_area_background_rule": {
    "default": "show_safe_bands=false",
    "override": "Only enable solid safe bands when the user explicitly asks for protected empty bars for platform UI.",
    "qa": [
      "Inspect a contact sheet or review frame for accidental black top/bottom bars inside the video frame.",
      "Confirm ffprobe dimensions match the requested aspect ratio; if a 9:16 player adds outer bars around a 3:4 video, explain that as player fitting, not export letterboxing."
    ],
    "required": true,
    "rule": "Do not render solid top or bottom safe-area bands by default. The background grid/glow must extend to the full canvas so the video does not look letterboxed or empty."
  },
  "self_media_hook_layout_revision": {
    "bottom_copy_readability": {
      "preferred_bottom_font_size": 34,
      "preferred_bottom_line_step": 38,
      "preferred_bottom_title_font_size": 44,
      "preferred_line_count": "3-5 concise fact-chain lines per page; each line must earn attention."
    },
    "latest_revision": "Facts must be selected by target-user interest first. Dense copy is not neutral fact stacking.",
    "middle_bottom_title_separation": {
      "bottom_title_role": "viewer-facing judgment, conflict, or value claim",
      "middle_visual_title_role": "source/evidence label only, e.g. GitHub 项目预览, README 顶部定位, TDD + Subagent",
      "rule": "Do not duplicate the bottom title in the middle visual title."
    },
    "top_tag_policy": {
      "rule": "Do not render internal planning/stage labels. If a label is shown, it must be audience-facing and useful.",
      "show_top_tag_default": false
    }
  },
  "three_by_four_layout_density_gate": {
    "checks": [
      "middle_source_larger: 中间真实素材区域要明显大于旧 6:7 版本，不能只拉高背景。",
      "bottom_frame_filled: 底部事实链卡片下移并填满新增空间，不能留下大块空白。",
      "source_motion_matches_aspect: 极端长宽比素材按长边展示完整内容；常规比例素材用干净 PPT 式滑入，不做局部缩放抖动。",
      "safe_area_opt_in: 只有用户明确要求平台 UI 安全空间时，才额外保留底部安全区。"
    ],
    "default_profile_values": {
      "aspect_ratio": "3:4",
      "bottom_box_y1": 956,
      "bottom_box_y2": 1362,
      "bottom_font_size": 48,
      "bottom_line_step": 58,
      "bottom_title_font_size": 60,
      "footer_font_size": 27,
      "footer_y_offset": 42,
      "height": 1440,
      "top_subtitle_font_size": 36,
      "top_title_font_size": 78,
      "width": 1080
    },
    "required": true,
    "rule": "默认 3:4 repo showcase 要把新增高度优先给中间真实素材和底部事实链：顶部标题清晰，素材区域明显放大，底部卡片接近画面底部但保留正常阅读边距。"
  },
  "visible_url_link_policy": {
    "material_rules": [
      "使用网页、GitHub 或 README 来源时，只截内容区；浏览器地址栏、命令里的网络地址、文档里的跳转地址必须裁掉或遮住。",
      "Quick Start、安装命令、文档段落如果露出网络地址，不作为公开视频中间素材；改用不露地址的 README 结构、Skills 清单、源码或本地文件截图。",
      "发布包里只写项目名、仓库名或搜索提示，不写可点击地址、裸域名、二维码或扫码引导。",
      "内部 release_manifest/source_url 可以保留用于溯源，但不能进入 public/ 文案或实际上屏文本。"
    ],
    "preferred_public_install_copy": [
      "使用项目名作为检索线索，让它查找并安装 Agent Skills。",
      "再问：先给我写 spec 和测试计划。"
    ],
    "public_surface": [
      "公开视频",
      "封面",
      "标题",
      "底部卡片",
      "中间截图",
      "image_labels/footer",
      "发布正文",
      "置顶评论"
    ],
    "required": true,
    "rule": "公开视频、封面、标题、底部卡片、发布正文和可见素材截图不得出现网址、域名、URL、二维码、扫码或链接引导。"
  },
  "visual_style_lock": {
    "background": "dark navy/black gradient base with subtle cyan/gold glow and perspective grid",
    "base_color": "#020810",
    "forbidden_elements": [
      "light parchment or paper texture as the main background",
      "ancient book page background",
      "single flat beige/cream theme",
      "project-specific decorative background that overrides the capsule system"
    ],
    "name": "dark_gradient_grid_showcase",
    "renderer_anchor": "script/render_repo_showcase_video.py::make_bg",
    "required": true,
    "required_elements": [
      "dark gradient canvas",
      "subtle perspective grid lines",
      "low-opacity cyan/gold glow accents",
      "white fixed top title with stroke",
      "dark bottom safety band"
    ],
    "review_gate": "Contact sheet must visibly match the dark gradient grid system before recording a successful run."
  },
  "visual_system": {
    "canvas": "微信视频号 1080 x 1440，3:4，比旧 6:7 更高但不跳到 9:16",
    "fixed_top_title_rules": [
      "顶部标题区不要每帧换文案，它是观众理解整条视频的锚点",
      "顶部标题必须讲清楚项目最吸引人的点、最大证据或最大结果",
      "顶部可以包含一个短 tag、一个两行主标题、一个项目定位副标题",
      "主画面和底部解释可以随帧变化，底部负责解释当前画面的价值",
      "发布标题、封面主标题、片内顶部标题要尽量一致，避免用户感知割裂",
      "如果项目有强数字或强机制，优先放进固定顶部，例如 2986张截图证据 / 装进 Agent",
      "顶部最大字优先写用户价值，不写制作版本、修正说明或单纯证据标签。"
    ],
    "layout": [
      "上方固定大字报标题，居中，多行，作为贯穿全片的核心钩子",
      "中间主画面随帧变化，展示项目证据图、四格漫画、截图、before/after 或流程图",
      "下方多行解释卡随主画面变化，补充痛点、差异、适用人群或边界",
      "中间放项目证据图、四格漫画、截图、before/after 或流程图，居中展示",
      "下方放多行解释卡，补充痛点、差异、适用人群或边界",
      "标题、素材、底部卡片整体居中均衡",
      "中间素材尽量完整展示，不裁到只剩局部"
    ],
    "material_priority": [
      "GitHub 仓库自带图片、README/docs 内嵌图片、demo/UI/产物截图、GIF、视频或 gallery",
      "网上相关原始图片或原始视频素材，排除解说、reaction、教程讲解、搬运混剪和二次加工视频",
      "README 渲染后的内容区截图，仅在素材不足时使用，不截纯代码目录",
      "能证明具体主张的源码、manifest、SKILL.md 或配置截图",
      "AI 生成概念图，只能作为记录原因后的 fallback",
      "所有可见素材都必须做无链接检查：不得露出网址、域名、二维码、扫码或命令中的网络地址。"
    ],
    "safe_area": "默认不额外画实心安全区；只保留正常阅读边距，素材区和底部卡片使用新增高度。",
    "shot_types": [
      "四格漫画：开头或核心机制，把抽象价值讲成故事",
      "before/after：展示质量提升、模板复刻、效果对比",
      "证据截图：展示真实 repo、demo、命令、产物",
      "流程图：说明输入、处理、输出",
      "人群卡：收束谁该用",
      "边界卡：避免广告感，提高可信度"
    ],
    "style_lock": {
      "background": "dark navy/black gradient base with subtle cyan/gold glow and perspective grid",
      "base_color": "#020810",
      "forbidden_elements": [
        "light parchment or paper texture as the main background",
        "ancient book page background",
        "single flat beige/cream theme",
        "project-specific decorative background that overrides the capsule system"
      ],
      "name": "dark_gradient_grid_showcase",
      "renderer_anchor": "script/render_repo_showcase_video.py::make_bg",
      "required": true,
      "required_elements": [
        "dark gradient canvas",
        "subtle perspective grid lines",
        "low-opacity cyan/gold glow accents",
        "white fixed top title with stroke",
        "dark bottom safety band"
      ],
      "review_gate": "Contact sheet must visibly match the dark gradient grid system before recording a successful run."
    }
  }
}

## wechat_social_value_gate

{
  "evidence_boundary": "Every angle must map to repo facts, documentation, screenshots, demos, source files, or a clearly defensible editorial inference.",
  "in_video_influence": "optional_when_natural",
  "in_video_rule": "The first-screen title and bottom fact-chain may borrow this angle only when it makes the project clearer and more useful; do not weaken source-grounded explanation to chase social framing.",
  "primary_angle": "distinctive_view_with_user_value",
  "priority": "wechat_title_and_body_first",
  "public_language_rules": [
    "Do not expose internal labels such as hard_value, distinctive_view, unexpected_use, like_signal, or share_target in viewer-facing copy.",
    "Do not write generic calls such as like, save, and share unless the copy explains the specific value behind the action.",
    "Do not turn one successful example into a universal template for unrelated projects."
  ],
  "purpose": "For WeChat Channels publishing copy, make the title and body worth a public like or a targeted share by grounding them in a distinctive, useful angle instead of generic interaction bait.",
  "reject_if": [
    "The title is only a project label, platform category, or generic recommendation.",
    "The body asks for interaction without saying what judgment, method, use case, or practical value earns it.",
    "The angle sounds clever but cannot be tied back to visible evidence or source facts.",
    "The rule forces a sample-specific lens onto a project where it does not fit."
  ],
  "required": true,
  "social_check_definitions": {
    "like_signal": "The viewer can publicly endorse the content because it signals judgment, professionalism, taste, information advantage, or domain fluency.",
    "share_target": "The viewer can imagine a specific friend, colleague, team, or group that would get practical value from receiving it."
  },
  "social_checks": [
    "like_signal",
    "share_target"
  ],
  "title_body_requirements": [
    "Before selecting the WeChat Channels title, identify which value angle is strongest and why the target user benefits from it.",
    "The recommended title should express the distinctive angle or useful takeaway before platform interaction language.",
    "The body opening should clarify why this is valuable to the target user, not merely introduce the project category.",
    "The body should imply a credible share target through use case, situation, or audience fit rather than asking broadly for forwarding.",
    "If the topic does not naturally support a social signal, keep the copy useful and evidence-grounded instead of forcing the frame."
  ],
  "value_angle_definitions": {
    "distinctive_view": "A supported interpretation, classification, tradeoff, or counter-obvious angle that goes beyond summarizing what the project is.",
    "hard_value": "A concrete method, checklist, judgment, diagnostic point, avoidable mistake, or reusable action the viewer can take away.",
    "unexpected_use": "A factual but less obvious way to use the same repo, tool, or skill, without inventing unsupported capabilities."
  },
  "value_angles": [
    "hard_value",
    "distinctive_view",
    "unexpected_use"
  ]
}
