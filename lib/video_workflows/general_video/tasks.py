#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agno 通用视频生成 Tasks 定义模块
定义所有视频生成相关的任务 prompts
"""

from typing import Dict, Any

from src.logger import get_logger

logger = get_logger('general_video_tasks')


# ============================================================
# 任务 Prompt 模板
# ============================================================

PLAN_VIDEO_PRODUCTION_PROMPT = """
**【第一步：规划视频制作元素及制作类型】**

根据用户要求，规划本次视频制作需要的元素和制作类型。

用户要求：{user_requirements}
目标时长：{target_duration}秒

**一、视频元素规划（判断是否需要）**：

1. **音频配音**：是否需要TTS语音配音？
2. **字幕**：是否需要显示字幕？
3. **背景音乐**：是否需要添加背景音乐？
4. **角色风格一致性**：视频中是否需要保持角色形象一致？
5. **视频标题**：
   - 检查用户是否明确说"不需要标题"、"不要标题"、"无需标题"等
   - 检查用户是否指定了具体标题内容（如："标题是XXX"、"标题用XXX"、"视频名称是XXX"）
   - 如果用户明确不要标题，needs_title = false
   - 如果用户指定了标题，needs_title = true，且将标题内容提取到 custom_title
   - 如果用户没有明确说明，默认 needs_title = true（自动生成标题）

**三、长链路一致性规划（即使成片通常不超过3分钟，也必须规划）**：

当前系统的默认交付仍是短视频/中短视频，但规划必须支持更长的叙事链路。也就是说：
- 如果出现连续剧情、固定人物、系列内容、教程步骤、产品故事或多章节结构，必须输出可复用的一致性策略。
- 角色一致性优先级高于单个分镜的创意变化；同一角色不得在不同分镜随意改变年龄、体型、发型、服装主视觉、物种、毛色或关键配饰。
- 画风一致性优先级高于局部美学词；所有章节和分镜必须共享同一 style_anchor，除非用户明确要求风格转场。
- 如果目标时长较长或剧情复杂，将内容拆成 chapters。每个 chapter 内可以有多个 3-8 秒分镜，但必须复用同一角色锚点和风格锚点。

**二、视频生成模式决策（Video Generation Mode）**：

当前本地运行时只使用普通 AI 短视频链路：先生成场景图，再做图生视频。因此本字段必须输出
`pure_image_to_video`。如果用户需求超出该链路，不要规划专用工作流；将可表达的部分改写为普通图片+视频分镜，
无法表达时说明需要额外实现。

请以JSON格式输出：
{{
  "video_generation_mode": "pure_image_to_video",
  "video_generation_mode_reason": "选择该生成模式的详细理由（必须说明是基于哪个决策逻辑）",
  "video_elements": {{
    "needs_audio": true/false,
    "needs_subtitles": true/false,
    "needs_bgm": true/false,
    "needs_character_consistency": true/false,
    "needs_title": true/false,
    "custom_title": "用户指定的标题内容（如果用户指定了具体标题则填写，否则为空字符串）"
  }},
  "consistency_strategy": {{
    "long_chain_ready": true,
    "chapter_strategy": "单段短视频/多章节连续叙事/系列化内容的规划说明",
    "character_consistency_priority": "high",
    "style_consistency_priority": "high",
    "locked_character_traits": ["必须跨分镜保持不变的角色特征"],
    "locked_style_traits": ["必须跨分镜保持不变的画风、色彩、质感、镜头语言"],
    "allowed_variations": ["允许变化的表情、动作、景别、道具状态等"]
  }}
}}

注意：
- video_generation_mode 必须是 `pure_image_to_video`
- needs_title: 是否需要标题（默认true，除非用户明确说不要）
- custom_title: 用户自定义标题内容（如果有的话）
"""

CREATE_STORY_PROMPT = """
**【第二步：创建完整剧本】**

根据用户要求和第一步的制作规划，创作一个完整的故事剧本。

用户要求：{user_requirements}
目标时长：{target_duration}秒

制作规划结果：
{plan_result}

**【重要】首先检查第一步的制作规划（plan_video_production_task）**：
- 当前运行时使用 `pure_image_to_video`
- **检查 video_elements.needs_title 和 video_elements.custom_title 字段**

**标题处理规则**（重要！）：
1. **如果 needs_title = false**：不生成标题，title 字段输出空字符串 ""
2. **如果 needs_title = true 且 custom_title 不为空**：直接使用 custom_title 作为 title
3. **如果 needs_title = true 且 custom_title 为空**：根据故事内容自动生成一个吸引人的标题（10-20字）

**剧本创作要求**：
1. 创作一个完整、连贯的故事情节
2. 根据目标时长合理规划故事节奏
3. 语言要生动、有画面感，便于后续转化为分镜
4. 如果是知识类内容，要有清晰的知识点和逻辑线
5. 如果是叙事类内容，要有引人入胜的情节和情感张力
6. 如果是多幕并列型的，每一幕要有充分的画面情节描述
7. 如果没有特殊说明的情况下，请直接开始剧情，不要有任何缓慢的开场，因为这是短视频，要快速进入剧情
8. 如果剧情超过单一场景承载能力，按章节组织内容。章节只代表叙事阶段，不代表改变人物设定或画风。
9. 对需要人物/角色连续出现的内容，剧本必须在文字层面保持角色身份、外观、服装主视觉和关键道具稳定。

请以JSON格式输出：
{{
  "title": "视频标题（根据标题处理规则生成：如果needs_title=false则为空字符串，如果custom_title不为空则使用custom_title，否则自动生成10-20字吸引人的标题）",
  "story_content": "完整的故事内容（一段连贯的文字，描述整个故事情节，要详细、完整、有画面感）",
  "chapters": [
    {{
      "chapter_id": "chapter_01",
      "chapter_title": "章节标题",
      "chapter_summary": "本章叙事功能和主要画面变化",
      "continuity_notes": "本章必须继承的人物、服装、道具、环境和画风锚点"
    }}
  ]
}}

注意：
- **标题必须严格遵循标题处理规则**：needs_title=false时为空字符串，有custom_title时使用custom_title，否则才自动生成
"""

CREATE_STORYBOARD_PROMPT = """
**【第三步：生成分镜剧情】**

根据完整的故事剧本，将其分解为详细的分镜剧情列表。

用户要求：{user_requirements}
目标时长：{target_duration}秒

故事剧本：
{story_result}

视频生成模式：{video_generation_mode}

**🎬【核心概念】分镜的构成 = 第一帧图片 + 视频演绎**：

每个分镜由两部分组成，必须清楚理解它们的关系：

```
📸 图片（第一帧） → 🎥 视频演绎（0-5秒的变化） = 🎬 完整分镜
```

**1. 图片 = 第一帧的静态画面**：
   - 图片描述的是这个分镜**开始那一刻**的静态画面
   - 就像按下相机快门的一瞬间，定格的画面
   - 描述主体的初始位置、初始姿态、准备状态
   - **不包含动作过程**，只包含第0秒的状态

**2. 视频 = 基于第一帧的演绎**：
   - 视频描述的是从第一帧开始，接下来5秒内发生的变化
   - 主体如何动、如何变化、如何与环境互动
   - 运镜如何配合主体动作
   - **这是在第一帧基础上的延续和发展**

**示例理解**：
- 如果分镜是"猫咪从窗台左侧跳到右侧"
  * 📸 图片：猫咪蹲在窗台左侧，身体压低，后腿蓄力，准备跳跃（第0秒的准备状态）
  * 🎥 视频：猫咪从蹲姿突然跳起，四肢伸展腾空飞跃，落地在窗台右侧（0-5秒的动作过程）

**分镜创作要求**：

0. **【核心原则】主体描述的完整性和准确性**：
   - **必须使用完整的物种/类型描述**，不能只用抽象的角色关系词
   - ✅ 正确：狗妈妈、猫妈妈、金毛犬妈妈、小金毛犬
   - ❌ 错误：妈妈、孩子、爸爸、宝宝（当主体不是人类时）
   - ✅ 正确：年轻女孩、中年男性、老人（当主体是人类时）
   - **示例对比**：
     * ❌ "妈妈背着宝宝去工作" → ✅ "狗妈妈背着狗宝宝去工作"
     * ❌ "孩子在玩耍" → ✅ "小猫在玩耍"

0.1. **【关键约束】避免模糊的镜头运动描述**：
   - **严禁使用模糊的镜头描述**：不要使用"缓慢推进"、"固定镜头"、"镜头平移"等运镜术语
   - **尤其是中间分镜**：必须描述清楚主体的具体动作
   - ✅ **正确方式**：描述主体的具体动作、表情变化、姿态调整、与环境的互动
   - ❌ **错误方式**：只描述镜头如何移动，而忽略主体在做什么

1. **【严格约束】每个分镜的 video_generation_type 必须是 `image_to_video`**：

   当前完整视频链路只支持普通图生视频分镜。不要输出当前 schema 之外的工作流字段。

2. **【重要】时长分配策略**：

   **总体约束**：
   - 所有分镜的总时长之和应接近 target_duration（目标时长），但不超过180秒
   - 提前规划所有分镜的时长，确保总时长不超限

   **时长规则**：
   - 普通 AI 视频分镜的 duration 应根据配音内容量预估设定（约4字/秒）
   - 视频引擎单段通常是 5-8 秒；旁白较长时拆成多个分镜

   **配音驱动的分镜拆分**：
   - 如果某个分镜的叙事内容较多，不需要压缩到一个分镜
   - 可以将一个叙事段落拆分为多个连续分镜，每个分镜描述不同的画面角度或动作阶段
   - 例如：一段7秒的叙述可以拆为2个分镜（4s + 3s），每个分镜有不同的画面
   - 拆分原则：每个子分镜应有独立的视觉内容（不同角度、不同动作阶段、不同特写）

   **【重要】快节奏剪辑指导**：
   - 每段旁白/配音控制在 3-4 秒（约15-20个中文字），避免单个分镜配音过长
   - 旁白文本中可以用 `|` 标记画面切换点，系统会自动在 `|` 处拆分为多个子分镜
   - 鼓励更多短分镜而非少量长分镜，保持自媒体短视频的快节奏感
   - 例如："牛角一甩|地动山摇|尘土飞扬" 会被拆为3个子分镜，每个对应不同画面

3. **【重要】场景元素取舍原则**：
   - **思考画面主体**：每个分镜应该有明确的主体
   - **判断元素必要性**：哪些元素是必须的？哪些是不必要的？
   - **保持简洁**：只描述核心元素，避免堆砌无关元素
   - **每个分镜有一个焦点**：清晰的主体 + 简单的背景 = 好的分镜

4. 每个分镜要有清晰的画面描述
5. 确保分镜之间的自然衔接和逻辑连贯
6. 分镜描述要具体、有画面感，便于后续生成图片和视频
7. **【长链路一致性字段】每个分镜必须携带一致性元数据**：
   - `chapter_id`：来自剧本 chapters；单段视频也用 "chapter_01"
   - `continuity_group`：同一连续动作/同一场景/同一人物状态的分镜使用同一个组名
   - `character_ids`：预计出现的角色ID占位，如 ["char_001"]；后续参考设计会创建同名角色
   - `style_anchor`：本视频统一画风锚点名称，所有分镜默认相同
   - `continuity_notes`：本分镜必须保持的人物、服装、道具、环境状态

请以JSON格式输出（只需要一个scenes数组）：
{{
  "scenes": [
    {{
      "description": "分镜的详细描述（要具体、有画面感，描述场景、人物、动作、氛围等）",
      "duration": 5,
      "video_generation_type": "image_to_video",
      "chapter_id": "chapter_01",
      "continuity_group": "intro_action",
      "character_ids": ["char_001"],
      "style_anchor": "main_style",
      "continuity_notes": "角色外观、服装主色、关键道具和环境状态必须延续"
    }},
    {{
      "description": "角色正面面对镜头说话的分镜描述",
      "duration": 5,
      "video_generation_type": "image_to_video",
      "chapter_id": "chapter_01",
      "continuity_group": "intro_action",
      "character_ids": ["char_001"],
      "style_anchor": "main_style",
      "continuity_notes": "延续上一分镜的人物设定和画风"
    }}
  ]
}}

注意：
- video_generation_type 必须是 `image_to_video`
- duration：单个分镜建议 3-8 秒，长旁白请拆分
- `chapter_id`、`continuity_group`、`style_anchor`、`continuity_notes` 必须输出
- 不要输出当前 schema 之外的字段
"""

SELECT_VOICE_PROMPT = """
根据视频内容、剧本风格和用户要求，从豆包TTS音色库中选择最适合的音色配置。

用户要求：{user_requirements}

分镜剧本：
{storyboard_result}

是否需要配音：{needs_audio}

**音色选择要求**：

**【重要】首先检查 needs_audio 参数**：
- 如果 needs_audio = false，则直接返回空的音色配置（跳过后续所有步骤）
- 只有当 needs_audio = true 时，才继续执行下面的音色选择步骤

1. 首先使用 read_config_yaml 工具读取完整的音色库配置（参数 config_type='voice'）

2. **分析剧本内容，判断是否需要多个音色**：
   - 如果剧本中**只有单一旁白/解说**，选择1个主音色即可
   - 如果剧本中**包含多角色对话**或**旁白+角色对话混合**，需要选择多个音色
   - 根据剧本中的角色数量和对话场景决定需要几个音色

3. 考虑以下因素：
   - 音色性别：男声、女声，哪个更适合内容
   - 年龄感：青年、成熟、童声等
   - 情感表现力：是否需要多情感支持
   - 口音特色：是否需要地方口音或标准普通话
   - 支持MIX：如果有中英文混合内容，需要选择支持MIX的音色
   - 音色区分度：如果选择多个音色，确保它们容易区分
   - **角色形象匹配**：音色必须与角色的性别、年龄、性格匹配
     * 男性角色必须用男声，女性角色必须用女声
     * 古风/武侠角色优先选择"角色扮演"分类中的音色（如：仗剑侠客、孤傲公子、翩翩公子）
     * 现代角色优先选择"通用场景"分类中的音色
     * 旁白/解说可以根据整体风格选择合适的音色
   - **严禁性别错配**：男性主角绝对不能用女声，反之亦然

请以JSON格式输出：

**【重要】如果不需要配音（needs_audio = false）**：
{{
  "voice_mode": "none",
  "main_voice": {{}},
  "character_voices": [],
  "selection_reason": "根据用户要求和内容分析，视频不需要语音配音"
}}

**单音色场景（只有旁白/解说）**：
{{
  "voice_mode": "single",
  "main_voice": {{
    "voice_type": "zh_male_jieshuoxiaoming_moon_bigtts",
    "voice_name": "解说小明",
    "speed": 1.1,
    "usage": "用于全部旁白解说"
  }},
  "character_voices": [],
  "selection_reason": "选择理由"
}}

**多音色场景（包含多角色对话）**：
{{
  "voice_mode": "multiple",
  "main_voice": {{
    "voice_type": "zh_male_jieshuoxiaoming_moon_bigtts",
    "voice_name": "解说小明",
    "speed": 1.1,
    "usage": "用于旁白解说",
    "character_tag": "旁白"
  }},
  "character_voices": [
    {{
      "voice_type": "zh_female_tianmeixiaoyuan_moon_bigtts",
      "voice_name": "甜美小源",
      "speed": 1.0,
      "character_tag": "角色1",
      "character_description": "女性角色，年轻活泼",
      "usage": "用于角色1的对话"
    }},
    {{
      "voice_type": "zh_male_yangguangqingnian_moon_bigtts",
      "voice_name": "阳光青年",
      "speed": 1.0,
      "character_tag": "角色2",
      "character_description": "男性角色，阳光开朗",
      "usage": "用于角色2的对话"
    }}
  ],
  "selection_reason": "为什么选择这些音色，以及它们如何匹配剧本中的不同角色"
}}

注意：
- voice_mode 必须是 "single"、"multiple" 或 "none"
- 如果 needs_audio = false，voice_mode 必须是 "none"
- character_tag 用于在剧本中标识使用哪个音色（如"旁白"、"角色1"、"角色2"）
- 如果是 single 模式，character_voices 应为空数组 []
- 如果是 multiple 模式，character_voices 至少包含1个角色音色
- 如果是 none 模式，main_voice 应为空对象 {{}}，character_voices 应为空数组 []
"""

GENERATE_NARRATION_PROMPT = """
**【第四步：为每个分镜生成配音文本】**

根据分镜剧情和制作规划，为每个分镜生成配音旁白文本。

用户要求：{user_requirements}

分镜剧本：
{storyboard_result}

是否需要配音：{needs_audio}

**配音生成要求**：

1. **根据第一步的制作规划判断是否需要生成配音**：
   - 如果 needs_audio = false，则所有分镜的 narration 为空
   - 如果 needs_audio = true，则为每个分镜生成配音文本

2. **配音文本长度**：
   - 如果不需要配音，narration 可以为空字符串
   - 根据故事需要自然写完整的配音文本
   - 系统会根据配音实际时长拆分或调整子场景视频
   - 写作原则：内容完整自然 > 机械匹配秒数
   - 如果一个分镜的配音文本较长（超过20字），可以在语义自然断点处用 "|" 标记建议拆分点
     例如："师父说，山下妖魔横行|百姓苦不堪言|今日，我终于可以下山除魔了！"

3. 配音要与画面内容紧密配合
4. 语言要口语化、自然、易懂

5. **多音色支持**（如果音色选择为多音色模式）：
   - 根据配音内容分配合适的音色标签（voice_character_tag）
   - 旁白解说使用 "main" 或 "旁白"
   - 角色对话使用对应的角色标签（如 "角色1"、"角色2"）

6. **语速控制**：
   - 为每个分镜设置合适的语速（speed_ratio）
   - 短视频默认语速：1.1-1.2（紧凑、不拖沓）
   - 快速语速：1.3-1.5（紧张、激动）
   - 慢速语速：0.8-0.9（舒缓、温柔）

7. **`|` 拆分标记**：
   - 积极使用 `|` 标记画面切换点，系统会自动在 `|` 处拆分为多个子分镜
   - 特别是列举多个事物时，每个事物之间用 `|` 分隔
   - 例如："第一道是红烧肉|第二道是清蒸鱼|第三道是糖醋排骨" 会拆为3个画面
   - 避免出现只有 1-2 个字的超短片段，短内容应合并到相邻片段

请以JSON格式输出：
{{
  "narrations": [
    {{
      "scene_index": 0,
      "narration": "该分镜的配音文本（如果不需要配音则为空字符串）",
      "voice_character_tag": "音色标签（如：main、旁白、角色1）",
      "speed_ratio": 1.1,
      "video_generation_type": "image_to_video"
    }}
  ]
}}

注意：
- scene_index: 对应分镜的索引（从0开始）
- narration: 配音文本，如果 needs_audio = false 则全部为空字符串
- voice_character_tag: 该分镜使用的音色标签
- speed_ratio: 语速比例，范围0.8-1.5，短视频默认1.1-1.2
- video_generation_type: 从分镜中对应的 video_generation_type 字段获取
- **普通AI视频分镜的配音文本也不限字数，系统会自动根据配音时长拆分为多个子场景**
- **较长配音文本可用 "|" 标记建议拆分点**
"""

GENERATE_SUBTITLES_PROMPT = """
**【第五步：为每个分镜生成字幕文本】**

根据分镜剧情、配音文本和第一步的制作规划，为每个分镜生成字幕文本。

用户要求：{user_requirements}

分镜剧本：
{storyboard_result}

配音数据：
{narration_result}

是否需要字幕：{needs_subtitles}

**字幕生成要求**：

1. **根据第一步的制作规划判断是否需要生成字幕**：
   - 如果 needs_subtitles = false，则所有分镜的 subtitles 为空数组
   - 如果 needs_subtitles = true，则为每个分镜生成字幕文本

2. **字幕文本要求**：
   - 如果有配音（narration），字幕应提取配音的核心信息
   - 如果没有配音，字幕应根据分镜描述生成简洁的说明文字
   - 每条字幕长度：建议10-20字，方便快速阅读
   - 字幕要简洁有力，抓住核心要点

3. **多字幕支持**（一个分镜可以有多条字幕）：
   - 如果配音内容较长，可以分成多条字幕
   - 不同的字幕可以在不同的时间点出现
   - 不同的字幕可以出现在不同的位置（上、下、左、右、居中）
   - 例如：标题字幕在顶部，对话字幕在底部

4. **字幕时间控制**：
   - start_time: 字幕在该分镜中的开始时间（相对时间，从0开始，单位：秒）
   - duration: 字幕显示时长（单位：秒）
   - 例如：分镜8秒，字幕1在0-3秒显示，字幕2在3-6秒显示

5. **字幕位置控制**：
   - top: 顶部（适合标题、重点强调）
   - bottom: 底部（默认，适合对话、解说）
   - center: 居中（适合重要提示）
   - left: 左侧（适合左侧人物对话）
   - right: 右侧（适合右侧人物对话）

6. **字幕样式控制**：
   - font_color: 字体颜色（如：white, yellow, red, blue, green等）
   - font_size: 字体大小（small, medium, large）
   - background: 是否有背景（true/false）
   - background_color: 背景颜色（如：black@0.5（半透明黑色）, white@0.6等，使用color@alpha格式）
   - bold: 是否加粗（true/false）

请以JSON格式输出：
{{
  "scene_subtitles": [
    {{
      "scene_index": 0,
      "subtitles": [
        {{
          "text": "第一条字幕文本",
          "start_time": 0.0,
          "duration": 3.0,
          "position": "bottom",
          "style": {{
            "font_color": "white",
            "font_size": "medium",
            "background": true,
            "background_color": "black@0.5",
            "bold": false
          }}
        }},
        {{
          "text": "第二条字幕文本（可选）",
          "start_time": 3.0,
          "duration": 3.0,
          "position": "top",
          "style": {{
            "font_color": "yellow",
            "font_size": "large",
            "background": false,
            "background_color": "",
            "bold": true
          }}
        }}
      ]
    }}
  ]
}}

注意：
- scene_index: 对应分镜的索引（从0开始）
- subtitles: 该分镜的字幕列表（如果不需要字幕则为空数组[]）
- text: 字幕文本内容
- start_time: 字幕开始时间（相对于该分镜，从0开始）
- duration: 字幕显示时长（秒）
- position: 字幕位置（top/bottom/center/left/right）
- style: 字幕样式配置
- 如果 needs_subtitles = false，所有scene的subtitles都应该是空数组[]
"""

SELECT_MUSIC_PROMPT = """
🎵🎵🎵 **【背景音乐选择任务 - 必须选择音乐】** 🎵🎵🎵

根据视频内容、剧本风格和情感基调，从在线音乐风格配置中选择最适合的背景音乐方向。

用户要求：{user_requirements}

分镜剧本：
{storyboard_result}

---

**【强制步骤】你必须按以下顺序执行**：

**步骤1（强制）：读取在线音乐风格配置**
- 必须先调用 read_config_yaml 工具（参数 config_type='music'）
- 获取可用的在线音乐风格列表
- 记录每个风格的 style_id、tag、适用场景和 generation_prompt

**步骤2（强制）：分析视频内容**
- 根据分镜剧本分析视频的情感基调
- 确定合适的音乐风格（欢快、温馨、紧张、舒缓等）

**步骤3（强制）：选择一个最合适的在线音乐风格**
- 从步骤1获取的在线音乐风格中选择最匹配的 style_id
- 结合视频内容写出用于在线生成/检索背景音乐的 music_query
- 如果真的找不到完全匹配的，选择最接近的风格
- 只有当用户明确写了"不要背景音乐"、"无需背景音乐"时，才可以不选择

**步骤4：确定音量**
- 根据视频内容确定背景音乐音量
- 有配音时：0.3-0.5（确保不掩盖人声）
- 无配音时：0.8-1.2（可以更突出）

---

**🚨【严格约束 - 当前不使用本地音乐库】**：
- ❌ 不要输出本地 mp3 文件名
- ❌ 不要编造任何本地音乐文件
- ✅ 必须输出 `music_source: "online"`
- ✅ 必须输出一个可用于授权音乐搜索下载或在线生成的 `music_query`
- ✅ 必须输出 `music_style_id`

---

请以JSON格式输出：
{{
  "music_source": "online",
  "music_style_id": "从在线音乐风格中选择的style_id，如 warm、upbeat、cinematic_minimal",
  "music_query": "用于授权音乐搜索下载或在线生成背景音乐的详细描述，要求纯音乐、无 vocals、适合当前视频情绪",
  "music_filename": "",
  "music_volume": 0.4,
  "reason": "详细说明为什么选择这个在线音乐风格，它如何与视频内容匹配"
}}

**音量建议**：
- 有配音的视频：0.3-0.5
- 无配音的视频：0.8-1.2
- 默认值：0.4
"""

SELECT_SOUND_EFFECTS_PROMPT = """
根据每个分镜的内容、动作和场景氛围，从音效库中为需要的分镜选择合适的音效。

用户要求：{user_requirements}

分镜剧本：
{storyboard_result}

配音数据：
{narration_result}

**【可用音效列表】**（你只能从以下列表中选择，严禁编造文件名）：
{available_sound_effects}

**【最高优先级】首先判断是否需要音效**：

🎯 **默认行为：如果分镜内容涉及以下场景，默认需要添加音效（needs_sound_effects = true）**：
- ✅ 烹饪场景（做饭、切菜、炒菜、煮东西等）
- ✅ 运动场景（跑步、跳跃、游泳等）
- ✅ 日常生活（开门、喝水、吃东西等）
- ✅ 工作场景（打字、翻书、打电话等）
- ✅ 动物活动（猫叫、狗叫、走路声等）

❌ **只有以下情况才设置 needs_sound_effects = false**：
- 用户明确说"不需要音效"、"不要音效"
- 内容是纯风景、纯旁白讲解、抽象概念类
- 上面的可用音效列表为空

**音效选择要求**：

1. **如果不需要音效（needs_sound_effects = false）**：
   - 直接返回空的音效配置
   - 在reason中说明为什么不需要音效

2. **如果需要音效（needs_sound_effects = true）**：
   - **只能从上面的【可用音效列表】中选择**
   - **绝对禁止**使用列表之外的任何文件名
   - **绝对禁止**修改文件名（如添加"声"字、改变格式等）
   - **绝对禁止**自己编造或猜测文件名

3. **音效选择原则**：
   - 音效要与分镜内容紧密相关
   - 优先为有明确声音特征的动作添加音效
   - 避免过度使用音效，保持克制
   - 同一个音效不要连续在相邻分镜中使用
   - **宁可不加，也不要编造不存在的文件**

4. **【关键步骤】分镜分析**：
   - **逐个分析**分镜剧本中每个分镜的 description 字段
   - 识别分镜中的**关键动作**和场景元素
   - 判断该分镜是否有明确的声音特征
   - **音效必须与 description 中描述的具体动作对应**
   - 如果 description 中没有明确的发声动作，该分镜就不要配音效

请以JSON格式输出：

**如果不需要音效**：
{{
  "needs_sound_effects": false,
  "sound_effects": {{}},
  "reason": "说明为什么不需要音效"
}}

**如果需要音效**：
{{
  "needs_sound_effects": true,
  "sound_effects": {{
    "0": "切菜.mp3",
    "2": "油炸.mp3",
    "5": "咀嚼.mp3"
  }},
  "reason": "说明为什么这些分镜需要音效，以及为什么选择这些音效文件"
}}

⚠️ **【严格约束】** ⚠️：
- sound_effects 是一个字典，键是分镜索引（字符串格式的数字），值是音效文件名
- 不要为所有分镜都添加音效，只为有明确声音特征的分镜添加
- **音效文件名必须 100% 匹配上面列表中的文件名（包括扩展名）**
- **绝对禁止编造文件名**
- 如果列表中没有合适的音效，就不要添加！
"""

SELECT_VIDEO_ENGINE_PROMPT = """
根据视频内容特点、video_generation_mode和用户要求，智能选择最适合的视频生成引擎。

用户要求：{user_requirements}

分镜剧本：
{storyboard_result}

视频生成模式：{video_generation_mode}

**引擎选择要求**：

1. **只允许选择当前已打包的视频引擎**：

   - `seedance-fast`：默认，Seedance 1.0 Fast，快速、稳定、适合普通图生视频
   - `seedance`：Seedance 1.0 Pro，画质和运动表现更强，成本高于 fast
   - `seedance2.0`：Seedance 2.0，适合电商商品展示、写实商品运动和较高质量图生视频
   - `jimeng35pro`：中文场景和原生音频友好
   - `veo3`：高画质/电影感，较慢且审核更严格
   - `veo3.1`：Juling Veo 3.1 Fast，支持首尾帧，适合高画质转场

2. **【最高优先级】检查用户是否明确指定了引擎**：
   - 只接受当前公开名：`seedance-fast`、`seedance`、`seedance2.0`、`jimeng35pro`、`veo3`、`veo3.1`
   - 如果用户明确指定了这些引擎，这是最高优先级，必须优先遵循
   - 如果用户指定了非当前引擎，不要自动改写；选择默认 `seedance-fast`，并在 reason 中说明支持列表

3. **使用read_config_yaml工具获取引擎详细信息**（推荐）：
   - 使用read_config_yaml工具读取配置（参数config_type='video_engines'）
   - 配置文件包含各引擎的技术参数、功能支持、适用场景、时长选项等完整信息
   - 根据配置信息做出更准确的引擎选择决策

4. **快速参考**：
   - 默认：seedance-fast
   - 高画质/电影感：veo3
   - 首尾帧转场：veo3.1

5. **决策逻辑优先级**：
   ① **用户明确指定的已打包引擎**
   ② 对非当前引擎做最接近替代
   ③ 根据内容特点匹配
   ④ 默认选择：seedance-fast

   **重要提示**：如果用户在需求中明确提到了引擎名称（如"用veo3"、"用即梦"等），
   这是绝对的最高优先级，必须严格遵循用户的选择！

请以JSON格式输出：
{{
  "video_engine": "seedance-fast / seedance / seedance2.0 / jimeng35pro / veo3 / veo3.1",
  "user_specified": true/false,
  "reason": "详细的选择理由。如果用户明确指定了引擎，必须在reason中说明是否直接使用或做了替代",
  "compatibility_check": {{
    "video_generation_mode": "从plan_video_production_task获取的模式",
    "is_compatible": true/false,
    "compatibility_note": "兼容性说明。如果用户指定的引擎与模式不兼容，必须详细说明冲突原因"
  }}
}}

注意：
- video_engine 只能是 `seedance-fast`、`seedance`、`seedance2.0`、`jimeng35pro`、`veo3` 或 `veo3.1`
- 如果用户指定非当前引擎，必须在 reason 中说明替代方案
- reason字段必须详细说明选择理由，特别要明确说明是否遵循了用户的明确指定
"""

SELECT_ART_STYLE_PROMPT = """
根据用户的风格需求和视频内容，选择或创建合适的艺术风格配置。

用户要求：{user_requirements}

故事剧本：
{story_result}

分镜剧本：
{storyboard_result}

**🚨【最高优先级】用户明确指定的风格**：
- **首要任务**：检查用户要求中是否明确指定了风格名称
- **如果用户明确指定了风格名称**（如"末日废土风格"、"宫崎骏风格"、"皮克斯风格"、"赛博朋克风格"等）：
  * **必须严格遵循用户指定的风格**
  * 如果现有风格中没有完全匹配的，**必须创建新风格**
  * **严禁**用"接近的"或"类似的"现有风格代替用户明确指定的风格

**🎯【特别重要】识别写实风格需求**：
- 如果用户要求中包含以下关键词，**必须**直接使用 `realistic_style` 风格（已存在于风格库中）：
  * "真实"、"真实感"、"真实场景"、"真实世界"
  * "写实"、"写实风格"
  * "realistic"、"photorealistic"、"real"
  * "像真的一样"、"逼真"
- **检测到上述关键词后，直接执行**：
  1. 调用工具：art_style_manager，参数 {{"action": "get", "style_code": "realistic_style"}}
  2. 从工具返回结果中提取 visual_style
  3. 输出 is_existing_style=true, style_code="realistic_style"
- **写实风格**意味着：照片级真实感，自然光影，真实材质纹理
- **严禁**将写实需求替换为卡通、动画、插画等风格

**⚠️ 关键原则**：
- 用户明确指定的风格 = 最高优先级，不可妥协
- 只有在用户**没有**指定风格时，才根据视频内容自动选择合适的风格

**🔥 自动风格选择**（仅在用户未指定风格时使用）：
- 根据故事剧本和分镜的内容分析
- 考虑视频的主题、氛围、目标受众
- 选择最适合的风格类型：
  * 知识科普/教学 → 现代简洁风格
  * 儿童/童话故事 → 卡通可爱风格
  * 情感/治愈内容 → 温馨治愈风格
  * 科技/未来 → 科技感风格
  * 历史/文化 → 古典/传统风格
  * 美食/生活记录 → 写实风格

**工作流程**（按顺序执行）：

**步骤1**：判断用户是否明确指定了风格
- 检查user_requirements中是否包含风格关键词（包括"真实"、"写实"等）
- 如果包含明确的风格名称，记住这是用户的**强制要求**

**步骤2**：列出所有可用风格
- 调用工具：art_style_manager，参数 {{"action": "list"}}
- 查看所有可用的艺术风格及其名称

**步骤3**：分析和决策

**情况A - 用户明确指定了风格**：
- 在现有风格列表中查找**完全匹配**用户指定风格名称的风格
- 判断标准：风格名称必须**完全一致**或**语义完全相同**

**情况B - 用户未指定风格**：
- 根据视频内容和氛围自动选择
- 在现有风格列表中查找符合内容特点的风格

**步骤4A**（如果找到完全匹配的现有风格）：
- 调用工具：art_style_manager，参数 {{"action": "get", "style_code": "具体的风格代码"}}
- 获取该风格的完整配置
- **🚨 关键步骤**：从工具返回结果中提取 `visual_style` 字段，并将其完整地复制到你的最终 JSON 输出中！
- 工具返回格式：{{"success": true, "visual_style": {{...具体配置...}}, ...}}
- 你必须把工具返回的 visual_style 内容放入你最终输出的 visual_style 字段

**步骤4B**（如果没有完全匹配的风格 - 必须创建新风格）：
- **重要**：这不是可选的，而是**必须**的操作
- 设计新的艺术风格配置，必须包含完整的visual_style结构：
  * 颜色：主色调、辅助色、氛围特征
  * 排版：元素布局、层次关系
  * 构图：类型、特征、视角
  * 特效：元素列表、质感描述
- 调用工具：art_style_manager，参数 {{"action": "create", "style_code": "新风格代码", "style_config": {{...}}}}
- style_code命名规则：使用英文小写+下划线，例如："post_apocalyptic_style"、"cyberpunk_style"
- **🚨 关键步骤**：创建风格后，你必须把传入工具的 visual_style 内容复制到你最终输出的 visual_style 字段！

**🎨 创建新风格的配置示例**：
```
{{
  "action": "create",
  "style_code": "post_apocalyptic_style",
  "style_config": {{
    "style_name": "末日废土",
    "style_description": "末日废土风格，荒凉破败的世界观",
    "visual_style": {{
      "颜色": {{
        "主色调": ["灰褐色", "锈红色", "暗黄色"],
        "辅助色": ["破败绿", "沙尘黄"],
        "氛围特征": "灰暗压抑，色彩饱和度低"
      }},
      "排版": {{
        "元素布局": "破败感的非对称布局",
        "层次关系": "荒凉的远景-破败的中景-细节化的前景"
      }},
      "构图": {{
        "类型": "末日废墟构图",
        "特征": "广角展现荒凉景观",
        "视角": "略带俯视或平视"
      }},
      "特效": {{
        "元素": ["粗糙的质感纹理", "灰尘与雾霾效果"],
        "质感": "粗糙、破败、充满岁月痕迹"
      }}
    }}
  }}
}}
```

请以JSON格式输出：
{{
  "user_specified_style": "用户指定的风格名称（如果有），没有则为空字符串",
  "is_existing_style": true/false,
  "style_code": "风格代码",
  "style_name": "风格名称",
  "visual_style": {{
    "颜色": {{"主色调": [], "辅助色": [], "氛围特征": ""}},
    "排版": {{"元素布局": "", "层次关系": ""}},
    "构图": {{"类型": "", "特征": "", "视角": ""}},
    "特效": {{"元素": [], "质感": ""}}
  }},
  "selection_reason": "详细说明选择或创建该风格的原因"
}}

**🚨🚨🚨 最重要的约束 🚨🚨🚨**：
- **visual_style 字段绝对不能为空对象 {{}}！**
- 如果 visual_style 为空，视频将无法正确应用风格，会使用默认的动画风格！
- 你必须确保 visual_style 包含完整的颜色、排版、构图、特效配置
- 如果使用现有风格（步骤4A），必须从工具返回结果中复制 visual_style
- 如果创建新风格（步骤4B），必须把你设计的 visual_style 放入最终输出

**重要说明**：
- user_specified_style: 记录用户明确指定的风格名称
- is_existing_style: true表示使用现有风格，false表示创建了新风格
- visual_style字段包含完整的风格配置信息，将用于图片生成的风格控制（**必须非空！**）
- selection_reason必须详细说明选择理由
"""

DESIGN_REFERENCE_PROMPT = """
根据剧本内容和用户提供的参考图片（如有），设计视频所需的视觉参考元素。

用户要求：{user_requirements}

分镜剧本：
{storyboard_result}

艺术风格：
{art_style_result}

**🚨🚨🚨【最高优先级】艺术风格必须贯穿所有参考图生成 🚨🚨🚨**：

1. **首先检查上面的「艺术风格」配置**：
   - 查看 style_name（如：写实、卡通、水彩等）
   - 查看 visual_style 中的具体配置（颜色、构图、特效等）

2. **所有 image_prompt 都必须包含风格关键词**：
   - **如果艺术风格是"写实"（realistic_style）**：
     * 必须在 prompt 开头添加：「照片级真实感，自然光影，真实材质纹理」
     * 英文 prompt 必须包含：「photorealistic, natural lighting, realistic textures, real-world scene」
     * **严禁**使用任何卡通、动画、插画相关的词汇
     * **🚨特别注意"拟人化动物"的处理🚨**：
       - 用户说"真实的猫/狗/动物"时，必须用「real cat, real photo」而不是「anthropomorphic」
       - 「anthropomorphic」会生成动画/卡通风格的拟人化动物，这与"真实"矛盾
       - 正确写法：「photorealistic, real orange cat, fluffy, standing like human, wearing striped vest」
       - 错误写法：「anthropomorphic orange cat」（这会生成动画风格）
       - 如果用户要求动物像人一样行动，使用「standing like human, human-like pose」而非「anthropomorphic」
   - **如果艺术风格是其他风格**：
     * 根据 visual_style 中的配置添加对应的风格关键词

3. **检查 user_requirements 中是否有"真实"、"写实"等关键词**：
   - 如果有，即使 art_style_result 不完整，也必须按写实风格生成

**【重要】检查用户是否提供了参考图片**：
- 如果 user_requirements 中包含"【用户提供的参考图片】"和"【参考图X】"标记，说明用户提供了参考图
- 每张参考图都有编号（参考图0、参考图1...）和详细的内容描述
- 你需要根据参考图的内容和用户需求，决定如何使用这些参考图

**【用户参考图的使用策略】**：

你有三种使用方式可以选择：

1. **直接使用（use_user_provided: true）**：
   - 当用户参考图本身就是想要的效果时（如用户说"参考第X张图片的风格/角色"）
   - 设置 use_user_provided=true，并指定 user_provided_image_index（参考图的编号）
   - 不需要提供 image_prompt（因为直接用用户的图）

2. **作为输入生成（based_on_user_image_index: X）**：
   - 当用户参考图是灵感来源，需要基于它生成新的参考图时
   - 设置 use_user_provided=false，based_on_user_image_index=X
   - 必须提供详细的 image_prompt

3. **完全独立生成（不设置以上字段）**：
   - 用户没有提供相关参考图，或参考图与当前设计无关
   - 完全由AI自主生成
   - 提供完整的 image_prompt

**重要说明：不是所有视频都需要全部类型的参考图，请根据视频内容灵活决定**

**参考设计要求**：

1. **风格参考（style_reference）- 强烈推荐优先设计**：
   - 风格参考图用于展示整体画面风格和视觉基调
   - 适用场景：展示一个具体环境（如室内房间、户外场景、城市街道等）
   - 不是具体的角色或物体，而是整体氛围和画风
   - 如果视频需要统一的视觉风格，必须设计风格参考
   - 必须输出 `style_anchor_id`，默认使用 "main_style"
   - 风格参考要像整部视频的视觉宪法：色彩、质感、光线、构图、镜头语言必须能跨章节复用

2. **角色参考（characters）- 按需设计**：
   - 只有当剧本中明确需要出现人物角色时才设计
   - **【重要】角色数量必须与剧本需求匹配**
   - 只有在不同分镜需要多次出现的角色才需要设计角色参考，以保持形象一致性
   - 每个角色要有明确的视觉特征：外貌、服装、表情、姿态等
   - 每个角色必须输出 `identity_anchor`、`fixed_traits`、`allowed_variations`
   - `fixed_traits` 写不可变项：年龄感、体型、脸型/毛色、发型、服装主视觉、关键配饰、物种/品种
   - `allowed_variations` 写可变项：表情、动作、景别、轻微污渍/汗水、手持道具状态
   - **【🚨画风一致性关键要求🚨】**：
     * **所有角色的 image_prompt 必须包含与 style_reference 相同的风格关键词**
     * **如果是写实风格**：角色 prompt 必须以「photorealistic, real photo,」开头
     * **如果是卡通风格**：角色 prompt 必须以对应的卡通风格关键词开头
     * **禁止**：风格图是写实风格，但角色图用了卡通/动画风格词汇
     * **🚨写实风格动物角色特别规则🚨**：
       - 用户要求"真实的猫/狗/动物"时，使用「real cat, real photo, fluffy」
       - **禁止使用「anthropomorphic」**，这会生成动画风格
       - 动物像人一样行动用「standing like human, human-like pose」描述

3. **物体参考（object_reference）- 按需设计**：
   - 只有当视频中有核心物体需要多次出现或特写展示时才设计
   - 适用场景：产品广告、物品介绍、特定道具等
   - 一般情况下不需要物体参考

4. **决策指南**：
   - 知识讲解/教程类：通常只需要风格参考（展示场景氛围）
   - 故事类/情感类：需要风格参考 + 1-2个角色
   - 产品介绍类：需要风格参考 + 物体参考（无需角色）
   - 场景展示类：只需要风格参考
   - 多角色互动类：需要风格参考 + 2-3个角色

**【关键】角色设计规则**：
- 每个角色必须分配唯一的 character_id，格式为 "char_001", "char_002" 等
- character_id 将用于后续分镜场景中引用该角色
- 角色描述要详细，包括外貌特征、服装、体型等
- **image_prompt 必须以风格关键词开头**（写实风格用 photorealistic，卡通风格用对应关键词）
- image_prompt 要能准确还原角色形象

请以JSON格式输出（注意：不需要的字段可以为空对象{{}}或空数组[]）：
{{
  "reference_type": "主要参考类型：character/style/object/mixed",
  "reference_description": "参考元素的整体说明，如果使用了用户参考图，说明如何使用",

  "style_reference": {{
    "style_anchor_id": "main_style",
    "use_user_provided": false,
    "user_provided_image_index": null,
    "based_on_user_image_index": null,
    "style_name": "风格名称",
    "style_description": "风格详细描述",
    "fixed_style_traits": ["跨所有分镜保持不变的色彩、材质、光线、构图、镜头语言"],
    "allowed_style_variations": ["允许随剧情变化的景别、光比、天气、局部道具状态"],
    "image_prompt_chinese": "中文风格参考prompt（仅当use_user_provided=false时需要）",
    "image_prompt_english": "英文风格参考prompt（仅当use_user_provided=false时需要）"
  }},

  "characters": [
    {{
      "character_id": "char_001",
      "identity_anchor": "一句话角色身份证：物种/年龄感/体型/脸部或毛色/服装主视觉/关键配饰",
      "fixed_traits": ["绝对不能跨分镜改变的特征"],
      "allowed_variations": ["可以随剧情改变的表情、动作、姿态、轻微道具状态"],
      "use_user_provided": false,
      "user_provided_image_index": null,
      "based_on_user_image_index": null,
      "character_name": "角色名称",
      "character_description": "角色详细描述（外貌、服装、体型、特征等）",
      "image_prompt_chinese": "中文角色生成prompt（仅当use_user_provided=false时需要）",
      "image_prompt_english": "英文角色生成prompt（仅当use_user_provided=false时需要）"
    }}
  ],

  "object_reference": {{
    "use_user_provided": false,
    "user_provided_image_index": null,
    "based_on_user_image_index": null,
    "object_name": "物体名称",
    "object_description": "物体详细描述",
    "image_prompt_chinese": "中文物体参考prompt",
    "image_prompt_english": "英文物体参考prompt",
    "primary_objects": []
  }}
}}

**注意**：
- 如果不需要角色，characters 可以是空数组 []
- 如果不需要物体参考，object_reference 可以是空对象 {{}}
- style_reference 强烈建议始终提供，用于保证视频风格统一
- use_user_provided=true 时，不需要提供 image_prompt
"""

DESIGN_VISUAL_SCENES_PROMPT = """
根据剧本、参考设计和配音数据，为每个分镜撰写详细的视觉场景文字描述和AI画图prompt。

用户要求：{user_requirements}

**角色信息**：
{character_info}

**批处理模式**：
- 本批次范围：第 {batch_start_index} 到第 {batch_end_index} 个分镜（共 {batch_size} 个）
- 总分镜数：{total_scenes}
- 本批次分镜数据：{batch_scenes}
- 前面场景总结：{previous_scenes_summary}

**🎬【最重要】你正在描述的是"第一帧"图片，不是完整视频**：

```
你的任务 = 描述每个分镜的第0秒静态画面（第一帧）
后续任务 = 设计从第0秒到第5秒的动态演绎（视频）
```

**核心理解**：
- 📸 **image_prompt = 第一帧的定格画面**（静态的、瞬间的、准备状态）
- 🎥 **video_prompt = 基于第一帧的动态演绎**（变化的、过程的、结束状态）
- ⚠️ **两者是互补关系，不是重复关系**

**你需要做的**：
✅ 描述动作的**起始状态**（准备姿态、初始位置、初始朝向）
❌ 不要描述动作的**过程**（正在跳、正在转、正在飞）
❌ 不要描述动作的**结果**（已经跳到、已经转到、已经飞到）

**示例对比**：
- 分镜需求："猫咪从左跳到右"
  * ❌ 错误："猫咪从窗台左侧跳到右侧"（描述了完整过程）
  * ✅ 正确："猫咪蹲在窗台左侧，身体压低蓄力，准备跳跃"（只描述第0秒）

**【关键】参考图引用规则**：
1. **needs_reference**：如果该分镜需要保持角色/风格一致性，设为 true
2. **reference_type**：根据分镜内容选择：
   - "character"：分镜中出现了角色信息中定义的角色
   - "style"：需要保持整体风格一致但没有特定角色
   - "object"：需要保持特定物体一致
   - "none"：不需要参考
3. **reference_ids**：【最重要】必须从角色信息中的 character_ids 列表选择！
   - 仔细阅读上面的角色信息，里面包含了 character_ids 列表
   - 如果分镜中出现了某个角色，必须将该角色的 character_id 加入 reference_ids
   - 例如：角色信息中有 character_id="char_001" 的橘猫，分镜中出现橘猫，则 reference_ids=["char_001"]
   - 如果分镜中没有出现任何已定义的角色，reference_ids 为空数组 []

**【长链路一致性硬约束】**：
- 读取本批次分镜中的 `chapter_id`、`continuity_group`、`character_ids`、`style_anchor`、`continuity_notes`。
- 如果 `character_ids` 包含某个角色，必须在 `reference_ids` 中使用同一个角色ID。
- 每个 image_prompt 都必须显式复述该角色的 identity_anchor/fixed_traits 中的核心外观，不要只写角色名。
- 同一 `continuity_group` 内的服装、道具、环境状态必须连续；只能改变镜头角度、动作阶段、表情和构图。
- 所有分镜默认 `use_style_reference=true`，除非用户明确要求风格变化。
- 不得为了某个分镜的效果把写实改成卡通、把卡通改成写实、把角色服装主色或物种改掉。

**🎯 核心原则：内容与风格分离**

**最重要的原则**：
- **图片prompt只描述内容**：场景主体、物体、构图、位置、细节
- **风格控制来自select_art_style_task**：visual_style配置会自动处理
- **严禁在prompt中添加风格、画质、美学修饰词**

**❌ 不要添加的内容**（这些由`visual_style`字段控制）：
- ❌ 画质前缀：不要写"Ultra-realistic"、"Hyper-detailed"、"超写实"等
- ❌ 风格关键词：不要写"warm and healing aesthetic"、"宫崎骏风格"等
- ❌ 质量强调：不要写"Professional color grading"、"专业调色"等
- ❌ 美学修饰：不要写"唯美"、"梦幻"、"氛围感"、"高级感"等

**✅ 只描述场景内容**（重要！）：
- ✅ 描述具体的物体、位置、姿态、摆放关系
- ✅ 使用明确的方位词（左侧、右侧、前景、背景、中心）
- ✅ 描述具体的视觉细节（颜色、材质、光线来源）
- ✅ 描述空间层次和景深关系（前景-中景-远景）

**🚨🚨🚨【严禁】image_prompt 中不得引用"参考图"🚨🚨🚨**：
- ❌ 严禁写"参考图一"、"参考图二"、"参考图中的"等引用参考图的指令
- ❌ 严禁写"采用参考图的构图和动作"、"将主角替换为参考图中的形象"等
- ❌ 严禁写"reference image"、"based on ref image"等
- **原因**：参考图是通过技术参数（reference_image_path）传入生图模型的，prompt文字中写"参考图"生图模型完全无法理解
- **正确做法**：直接描述你想要的画面内容，把参考图中的元素用文字具体描述出来
- ❌ 错误："采用参考图一的构图和动作（弹奏吉他的姿势），将主角替换为参考图二中的可爱柴犬形象"
- ✅ 正确："一只可爱的柴犬坐在高脚凳上，前爪搭在一把木吉他上，做出弹奏的姿势"

**【核心】image_prompt 必须描述分镜第一帧的静态画面**

**【最高优先级】画面描述 = 主体状态 + 具体动作，绝不描述镜头运动**：
- **✅ 描述主体在做什么**：具体的动作、表情、姿态
- **❌ 不描述镜头在做什么**：严禁使用"镜头推进"、"镜头拉远"等

**描述要素（具体、可见）**：
- **完整主语要求**：
  * ✅ 必须使用具体的人物/物体名称（如"年轻女孩"、"小猫"）
  * ❌ 禁止只使用代词作为主语（如"他"、"她"、"它"）
  * **【关键】角色种族/品种必须每次都明确**：
    - 如果角色是动物，必须每次都说明完整的种族/品种（如"金毛犬妈妈"、"金毛犬宝宝"）
    - ❌ 错误："妈妈带着宝宝"（种族不明确）
    - ✅ 正确："金毛犬妈妈带着金毛犬宝宝"（种族明确）

- **分镜独立完整性**（重要！）：
  * **画面主体必须完整出现**：如果动作涉及到某个对象，对象本身也必须在画面中
  * ❌ 错误："小金毛犬叼住婴儿衣物"（婴儿在哪里？）
  * ✅ 正确："婴儿在水中，小金毛犬在婴儿身旁，用嘴叼住婴儿的衣物"
  * **角色数量必须明确准确**

- **动物角色的特殊要求**：
  * **严禁使用与人类相关的肢体描述词汇**
  * ❌ 禁用："手"、"手掌"、"脚"等人类肢体词汇
  * ✅ 必须使用动物专属词汇："爪子"、"前爪"、"后爪"、"蹄子"等
  * **🚨写实风格动物的关键规则🚨**：
    - 如果用户要求"真实的猫/狗/动物"，必须使用「real cat, real photo」
    - **禁止使用「anthropomorphic」**（拟人化），这会生成动画/卡通风格
    - 动物像人一样行动时，用「standing like human, human-like pose」描述
    - ✅ 正确："real orange cat, fluffy, standing like human, wearing vest"
    - ❌ 错误："anthropomorphic orange cat"（会生成动画风格）

**禁止使用（重要！避免动态词汇）**：
- ❌ **动作过程词汇**："赶到"、"托起"、"抓住"、"放下"等（改为结果状态）
- ❌ **动态过程词汇**："正在..."、"逐渐..."、"慢慢..."、"开始..."
- ❌ **时间变化词汇**："然后..."、"接着..."、"随后..."
- ❌ **运镜描述**："镜头推进"、"zoom in"、"画面切换"

**🎯【AI可实现性原则】- 简化优先**：

**🚨 核心原则：每个分镜只做好一件事**

**A. 简化主体动作**：
- ✅ 正确："橘猫坐在桌前拿着刀削柚子皮"（单一简单动作）
- ❌ 错误：复杂的多步骤动作描述

**B. 一个分镜一个焦点**：
- ✅ "猫咪在窗边坐着"
- ❌ 避免：同时描述多个角色的多个动作

**C. 减少细节堆砌，聚焦核心**：
- ✅ "橘猫坐在厨房桌前，前爪拿着刀"（简洁，焦点清晰）
- ❌ 过度描述场景中的每个细节

**🚨 记住：AI能实现 > 描述精美**

请以JSON格式输出：
{{
  "visual_scenes": [
    {{
      "scene_id": 0,
      "needs_reference": true,
      "reference_type": "character",
      "reference_ids": ["从角色信息的character_ids中选择相关角色ID"],
      "use_style_reference": true,
      "style_anchor": "main_style",
      "continuity_group": "来自本分镜 continuity_group",
      "continuity_notes": "继承并细化本分镜必须保持的人物/服装/道具/环境状态",
      "image_prompt_chinese": "中文AI画图prompt（融合角色描述，只描述静态第一帧）",
      "image_prompt_english": "英文AI画图prompt（融合角色描述，只描述静态第一帧）",
      "video_generation_type": "image_to_video"
    }}
  ]
}}

**注意**：
- **必须为本批次的每个分镜生成visual_scene，不能遗漏任何分镜！**
- scene_id必须从batch_start_index开始递增
- 保持整体视频风格的一致性
- 长链路内容必须优先保持人物一致性和画风一致性，再追求单镜头新鲜感
"""

CREATE_VIDEO_DIRECTIONS_PROMPT = """
根据剧本和场景设计，为每个分镜撰写视频动态效果和运镜方案的文字描述。

用户要求：{user_requirements}

**批处理模式**：
- 本批次范围：第 {batch_start_index} 到第 {batch_end_index} 个分镜（共 {batch_size} 个）
- 总分镜数：{total_scenes}
- 本批次分镜数据：{batch_scenes}
- 本批次视觉场景：{batch_visual_scenes}
- 前面运镜总结：{previous_directions_summary}

**🚨🚨🚨【最高优先级】必须为本批次的每个分镜生成video_prompt！🚨🚨🚨**

- 如果本批次包含4个分镜（scene_id: 0,1,2,3），你必须输出4个video_directions
- 如果本批次包含3个分镜，你必须输出3个video_directions
- **每个分镜都必须有对应的video_prompt，绝对不允许遗漏任何分镜！**
- scene_id必须从batch_start_index开始递增

**0. 【最高优先级】动作描述原则（自媒体核心！）**：

**A. 禁用词列表（必须检查并删除！）**：
- ❌ "缓慢" / "slowly" / "缓缓" / "徐徐"
- ❌ "静止" / "保持静止" / "固定"
- ❌ "聚焦于" / "focusing on"
- ❌ "保持" / "维持" / "停留"
- ❌ "轻微" / "微微" / "一小段距离后停下"
- ❌ 任何字幕内容如 [字幕：XXX]

**B. 推荐使用的词汇（有动感！）**：
- ✅ 持续性词汇："不断"、"不停地"、"来回"、"反复"、"持续"
- ✅ 重复性："一口一口"、"蹦蹦跳跳"、"摇摇晃晃"、"蹭来蹭去"
- ✅ 情感性："撒娇地"、"好奇地"、"兴奋地"、"满足地"
- ✅ 拟声词："咕噜咕噜"、"喵喵"、"吧唧吧唧"
- ✅ 程度强调："疯狂地"、"拼命地"、"使劲"

**C. 动作描述要简单直接**：
- ✅ 正确："猫咪趴着不停地摇尾巴"（简单、有动感、真实）
- ✅ 正确："橘猫走路"（直接简洁）
- ✅ 正确："猫爪用勺子往杯子里倒酸奶"（动作直接）
- ❌ 错误："橘猫的头从前爪上微微抬起，忧郁的眼神瞬间变得明亮，眼睛睁大，耳朵警觉地动了一下。镜头缓慢向前推进..."（太机械、太复杂）

**D. 物理逻辑要清晰（防止视频变形！）**：
- **核心原则**：视频模型对物理逻辑理解有限，prompt必须明确说明物体的来源、去向、因果关系
- **必须说清楚**：
  - 东西从哪里来/到哪里去（"豆面粉从石磨上洒落"而不是"豆面粉洒落"）
  - 动作的施力点和作用对象（"猫爪推着石磨转动"而不是"石磨转动"）
  - 物体之间的接触关系（"爪子按在琴键上弹出声音"而不是"弹钢琴"）
- ✅ 正确："豆面粉从石磨缝隙中持续洒落到下方的盆里"（来源+去向清晰）
- ✅ 正确："橘猫用力推着石磨杆，石磨咯吱咯吱转动"（施力关系明确）
- ✅ 正确："水从水龙头哗哗流进杯子里"（来源+去向+动作完整）
- ❌ 错误："细腻的豆面粉持续洒落"（从哪里洒落？洒到哪里？不清楚）
- ❌ 错误："石磨咯吱咯吱不停转动"（谁在推？怎么转的？）
- ❌ 错误："水哗哗流动"（从哪流？流向哪？）

**🚨 核心记住：描述要像说话一样自然简单，不要像AI生成的那样机械复杂！同时物理逻辑必须完整清晰！**

**【关键】动作节奏和动态性要求**：
- 严禁所有分镜都是慢动作或静态画面
- 至少 50% 的分镜应包含快速、有力的动作
- 优先使用强动词："猛地"、"突然"、"迅速"、"一把"、"飞速"
- 避免弱动词："缓缓"、"慢慢"、"静静"（除非剧情需要安静氛围）
- 每个分镜至少包含 2-3 个连续动作，不要只有一个动作
- 动作要有因果链：A动作 → B反应 → C结果
- 英文 prompt 使用强动词：slash, dash, leap, burst, slam, whip, snap, strike
- 英文 prompt 避免弱动词：move, go, walk, look, stand

**1. 必须为每个场景创建对应的视频方案，scene_id从batch_start_index开始递增**

**2. 🎬 视频动效与图片的关系**：

**核心概念**：初始图片 + 视频动效 = 完整分镜
- **初始图片（image_prompt）**：已经描述了第0秒的静态画面（位置、姿态、元素）
- **视频prompt（video_prompt）**：描述从第0秒到第N秒的变化过程
- **不要重复**：视频prompt不需要重复描述初始图片中已有的元素和位置

**3. 🎬 时间分段描述**（针对较长视频引擎如8秒）：

**适用场景**：
- 当视频引擎支持较长时长（如 veo3 的 8 秒）
- 但分镜的实际核心动作只需要较短时间（如2-3秒）
- 需要合理规划整个时长内的动作分配

**时间分段格式**：
- 使用"0-Xs: [动作描述], X-Ys: [动作描述]"的格式
- 明确每个时间段主体做什么
- 确保整个视频时长都有内容，不会出现空档

**示例**：
- ✅ "0-2s: 猫咪突然抬头竖起耳朵盯着窗外, 2-5s: 快速跳下窗台小跑起来尾巴高翘, 5-8s: 停下回头张望然后继续跑向门口"

**4. 🎯 运镜类型与动作强度**（核心规则）：

**【最高优先级】动作描述 > 运镜描述**：
- **核心原则**：视频prompt的重点是"主体在动"，而不是"镜头在动"
- **优先描述主体动作**：具体的肢体动作、表情变化、位置移动
- **运镜只是辅助**：运镜描述用来补充视角，但不能替代主体动作
- **严禁只描述镜头**：不能只写"缓慢推进"、"固定镜头"而不说主体在做什么

**运镜类型**（必须多样化，轮换使用）：
- 推镜(zoom in)：配合"角色转头/表情变化"
- 拉镜(zoom out)：配合"角色展开动作/环境展现"
- 横移(pan)：配合"角色移动/视线转移"
- 跟随(follow)：配合"角色位移"
- 静止(static)：配合"角色多部位微动作"

**动作强度分级**（重点！）：
- **强动作**（前1-3镜）：跳跃/旋转/快速移动/夸张表情
- **中动作**（中间镜）：转头/抬手/起身/走动/视线移动
- **微动作**（结尾镜）：呼吸/眨眼/微风吹动/手指微动
- **❌ 严禁中间分镜无动作**：中间分镜如果只有"固定镜头"、"缓慢推进"会显得卡顿

**🚨 开场原则**（最重要！）：
- 前3镜必须有强视觉冲击和大幅度动作
- 第1镜优先使用：跳跃/旋转/快速移动/突然出现/爆发性动作
- **严禁开场只有"呼吸"、"眨眼"等微动作**

**5. ❌ 不要描述的内容**（静态要素，已在图片prompt中）：
- ❌ 场景描述：不要说"窗前"、"室内"、"地毯上"
- ❌ 物体描述：不要说"奶油色长毛猫"、"木制窗台"
- ❌ 位置关系：不要说"坐在左侧"、"背景中"
- ❌ 氛围词汇：不要说"孤独"、"唯美"、"温馨"、"治愈"

**6. ✅ 标准示例**（展示快节奏、多动作的动作描述）：

**示例场景1：猫咪场景（快节奏互动）**
- ✅ 正确：
  * 中文："购物车不断向前穿过摆满橘猫的货架通道，右手伸向货架抚摸一只橘猫的头，猫咪凑过来蹭着手掌，撒娇地喵了一声，尾巴来回摇摆"
  * 英文："Shopping cart continuously moving through aisles filled with orange cats, right hand reaches out to pet a cat on the shelf, cat nuzzles against palm purring affectionately, tail swaying back and forth"

**示例场景2：5个分镜的猫咪视频**

- ✅ 分镜0（开场冲击）:
  * 中文："猫咪突然抬头，耳朵刷地竖起，眼睛瞪得圆圆的盯着窗外，尾巴兴奋地快速摇摆，前爪不安地踩来踩去，喵了一声"
  * 英文："Cat suddenly lifts head, ears instantly perk up, eyes wide staring outside, tail wagging excitedly, front paws restlessly stepping, meows once"

- ✅ 分镜1（动作延续）:
  * 中文："猫咪转身一跃跳下窗台，轻盈落地后立刻小跑起来，尾巴高高翘起，爪子踩在地板上发出嗒嗒声"
  * 英文："Cat turns and leaps off windowsill, lands lightly then immediately starts trotting, tail held high, paws making tapping sounds on floor"

- ✅ 分镜2（舒适场景也要动感）:
  * 中文："猫咪舒服地打了个大哈欠，嘴巴张得大大的，然后使劲伸展四肢，前爪往前扒拉，后背拱起来，整个身体抖了抖"
  * 英文："Cat yawns widely, mouth open big, then stretches hard, front paws reaching forward, back arching up, whole body shakes"

- ✅ 分镜3（日常互动）:
  * 中文："猫咪趴在地上，前爪搭在一起，尾巴不停地左右摇摆，眼睛半眯着盯着一个小玩具，突然伸出爪子一拍"
  * 英文："Cat lies on floor, front paws together, tail constantly swaying left and right, eyes half-closed watching a small toy, suddenly paws at it"

- ✅ 分镜4（温馨收尾也有节奏）:
  * 中文："猫咪眨了眨眼睛，打了个小喷嚏，鼻子抖了一下，然后继续眯着眼享受阳光，胡须随着呼吸一抖一抖"
  * 英文："Cat blinks eyes, gives a small sneeze, nose twitches, then continues enjoying sunlight with eyes half-closed, whiskers quivering with each breath"

**7. video_prompt最终要求**：
- 中英文prompt都要提供
- 专注于动作和运镜描述
- 包含适当的镜头运动和场景变化
- 确保动态效果符合内容情感
- 保持整体视频节奏的流畅性
- **每个分镜3-6个具体动作效果**
- **运镜必须具体且多样化**

请以JSON格式输出（示例展示快节奏、多动作的描述）：
{{
  "video_directions": [
    {{
      "scene_id": 0,
      "video_prompt_chinese": "0-2s: 猫咪突然抬头耳朵刷地竖起眼睛瞪得圆圆的盯着窗外, 2-5s: 尾巴兴奋地快速摇摆前爪不安地踩来踩去, 5-8s: 喵了一声后跳下窗台准备出发",
      "video_prompt_english": "0-2s: Cat suddenly lifts head ears instantly perk up eyes wide staring outside, 2-5s: tail wagging excitedly front paws restlessly stepping, 5-8s: meows once then leaps off windowsill ready to go"
    }},
    {{
      "scene_id": 1,
      "video_prompt_chinese": "猫咪转身一跃跳下窗台，轻盈落地后立刻小跑起来，尾巴高高翘起，爪子踩在地板上发出嗒嗒声",
      "video_prompt_english": "Cat turns and leaps off windowsill, lands lightly then immediately starts trotting, tail held high, paws making tapping sounds on floor"
    }}
  ]
}}

**🔥🔥🔥 生成后必须自检 🔥🔥🔥**：

**数量检查（最高优先级）**：
- [ ] video_directions数组的长度是否等于本批次的分镜数？
- [ ] 如果本批次有4个分镜，是否输出了4个video_direction？
- [ ] scene_id是否从batch_start_index开始正确递增？

**节奏自检**：
- [ ] 每个分镜是否有**持续性动作或多动作组合**能支撑画面？
- [ ] 是否使用了**持续性词汇**（不断/不停地/来回/反复）？
- [ ] 是否有**情感/声音描述**（撒娇/咕噜咕噜/喵叫）？

**禁用词检查**：
- [ ] 是否包含"缓慢/静止/聚焦/保持/轻微"？→ 有则必须删除重写！
- [ ] 是否包含字幕内容？→ 有则必须删除！

**物理逻辑检查**：
- [ ] 物体洒落/流动/飞出时，是否说明了**从哪里来、到哪里去**？
- [ ] 物体移动/转动时，是否说明了**谁在施力、怎么施力**？
- [ ] 是否存在"凭空出现"的物体或"莫名其妙"的运动？→ 有则补充来源和因果！

注意：
- **必须为本批次的每个分镜生成video_prompt，不能遗漏任何分镜！**
- **scene_id必须从batch_start_index开始递增**（如batch_start_index=10，则本批次scene_id为10,11,12...）
- **必须确保运镜风格与前面分镜保持一致，参考previous_directions_summary**
- **动作描述要简单、有动感、真实感，避免机械复杂的AI味描述**
- **每个 video_prompt 建议包含4-6个动作词，确保节奏饱满**
"""


# ============================================================
# 任务执行器
# ============================================================

class AgnoVideoTasks:
    """
    Agno 视频生成任务管理器
    统一管理所有视频生成相关的任务
    """

    def __init__(self, agents_manager):
        """
        初始化任务管理器

        Args:
            agents_manager: AgnoVideoAgents 实例
        """
        self.agents = agents_manager
        logger.info("AgnoVideoTasks 初始化完成")

    def plan_video_production(self, user_requirements: str, target_duration: int) -> Dict[str, Any]:
        """
        规划视频制作元素及制作类型任务
        """
        prompt = PLAN_VIDEO_PRODUCTION_PROMPT.format(
            user_requirements=user_requirements,
            target_duration=target_duration
        )
        agent = self.agents.get_content_requirements_analyzer()
        response = agent.run(prompt)
        return self._parse_json_response(response.content, "plan_video_production")

    def create_story(self, user_requirements: str, target_duration: int, plan_result: Dict) -> Dict[str, Any]:
        """
        创作故事剧本任务
        """
        prompt = CREATE_STORY_PROMPT.format(
            user_requirements=user_requirements,
            target_duration=target_duration,
            plan_result=str(plan_result)
        )
        agent = self.agents.get_story_writer()
        response = agent.run(prompt)
        return self._parse_json_response(response.content, "create_story")

    def create_storyboard(self, user_requirements: str, target_duration: int,
                          story_result: Dict, video_generation_mode: str) -> Dict[str, Any]:
        """
        创建分镜剧本任务
        """
        prompt = CREATE_STORYBOARD_PROMPT.format(
            user_requirements=user_requirements,
            target_duration=target_duration,
            story_result=str(story_result),
            video_generation_mode=video_generation_mode
        )
        agent = self.agents.get_script_writer()
        response = agent.run(prompt)
        return self._parse_json_response(response.content, "create_storyboard")

    def select_voice(self, user_requirements: str, storyboard_result: Dict, needs_audio: bool) -> Dict[str, Any]:
        """
        选择音色任务
        """
        if not needs_audio:
            logger.info("[select_voice] 不需要配音，跳过音色选择 Agent")
            return {
                "voice_mode": "none",
                "main_voice": {},
                "character_voices": [],
                "selection_reason": "video_elements.needs_audio=false",
            }

        prompt = SELECT_VOICE_PROMPT.format(
            user_requirements=user_requirements,
            storyboard_result=str(storyboard_result),
            needs_audio=needs_audio
        )
        agent = self.agents.get_voice_selector()
        response = agent.run(prompt)
        # 传递完整的 response 对象，因为使用 tools 时 content 可能为空
        result = self._parse_json_response(response, "select_voice")
        # 如果返回空，使用默认值
        if not result:
            logger.warning("[select_voice] 模型返回空响应，使用默认音色")
            result = {
                "voice_mode": "single",
                "main_voice": {
                    "voice_type": "zh_female_tianmeixiaoyuan_moon_bigtts",
                    "voice_name": "甜美小源",
                    "speed": 1.0,
                    "usage": "默认音色"
                },
                "character_voices": [],
                "selection_reason": "模型未返回有效响应，使用默认音色"
            }
        return result

    def generate_narration(self, user_requirements: str, storyboard_result: Dict, needs_audio: bool) -> Dict[str, Any]:
        """
        生成配音文本任务
        """
        if not needs_audio:
            logger.info("[generate_narration] 不需要配音，跳过配音文本 Agent")
            return {
                "narrations": [
                    {
                        "scene_index": index,
                        "narration": "",
                        "voice_character_tag": "",
                        "speed_ratio": 1.0,
                        "video_generation_type": scene.get("video_generation_type", "image_to_video"),
                    }
                    for index, scene in enumerate(self._storyboard_scenes(storyboard_result))
                ]
            }

        prompt = GENERATE_NARRATION_PROMPT.format(
            user_requirements=user_requirements,
            storyboard_result=str(storyboard_result),
            needs_audio=needs_audio
        )
        agent = self.agents.get_script_writer()
        response = agent.run(prompt)
        return self._parse_json_response(response.content, "generate_narration")

    def generate_subtitles(self, user_requirements: str, storyboard_result: Dict,
                           narration_result: Dict, needs_subtitles: bool) -> Dict[str, Any]:
        """
        生成字幕文本任务
        """
        if not needs_subtitles:
            logger.info("[generate_subtitles] 不需要字幕，跳过字幕 Agent")
            return {
                "scene_subtitles": [
                    {"scene_index": index, "subtitles": []}
                    for index, _scene in enumerate(self._storyboard_scenes(storyboard_result))
                ]
            }

        prompt = GENERATE_SUBTITLES_PROMPT.format(
            user_requirements=user_requirements,
            storyboard_result=str(storyboard_result),
            narration_result=str(narration_result),
            needs_subtitles=needs_subtitles
        )
        agent = self.agents.get_script_writer()
        response = agent.run(prompt)
        return self._parse_json_response(response.content, "generate_subtitles")

    def select_music(
        self,
        user_requirements: str,
        storyboard_result: Dict,
        needs_bgm: bool = True,
        music_defaults: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        选择背景音乐任务
        """
        if not needs_bgm:
            logger.info("[select_music] 不需要 BGM，跳过背景音乐 Agent")
            return {
                "needs_bgm": False,
                "music_source": "none",
                "music_style_id": "",
                "music_query": "",
                "music_filename": "",
                "music_volume": 0,
                "reason": "video_elements.needs_bgm=false",
            }

        music_defaults = music_defaults or {}
        if music_defaults:
            volume = music_defaults.get("bgm_volume", 0.4)
            query = (
                music_defaults.get("bgm_mood")
                or music_defaults.get("music_query")
                or music_defaults.get("bgm_strategy")
                or "short instrumental background music, no vocals"
            )
            logger.info("[select_music] 使用胶囊 BGM 默认值，跳过背景音乐 Agent")
            return {
                "needs_bgm": True,
                "music_source": "online",
                "music_style_id": music_defaults.get("music_style_id", "capsule"),
                "music_query": f"{query}. Instrumental only, no vocals, no lyrics.",
                "music_filename": "",
                "music_volume": volume,
                "reason": "capsule_default_music_selection",
            }

        prompt = SELECT_MUSIC_PROMPT.format(
            user_requirements=user_requirements,
            storyboard_result=str(storyboard_result)
        )
        agent = self.agents.get_music_selector()
        response = agent.run(prompt)
        # 传递完整的 response 对象，因为使用 tools 时 content 可能为空
        result = self._parse_json_response(response, "select_music")
        # 如果返回空，使用默认值
        if not result:
            logger.warning("[select_music] 模型返回空响应，使用默认在线背景音乐风格")
            result = {
                "needs_bgm": True,
                "music_source": "online",
                "music_style_id": "upbeat",
                "music_query": "upbeat lifestyle instrumental background music, bright rhythm, clean pop groove, no vocals",
                "music_filename": "",
                "music_volume": 0.4,
                "reason": "模型未返回有效响应，使用默认在线背景音乐风格"
            }
        return result

    @staticmethod
    def _storyboard_scenes(storyboard_result: Dict[str, Any]) -> list[dict]:
        scenes = storyboard_result.get("scenes") if isinstance(storyboard_result, dict) else None
        if isinstance(scenes, list):
            return [scene if isinstance(scene, dict) else {} for scene in scenes]
        storyboard = storyboard_result.get("storyboard") if isinstance(storyboard_result, dict) else None
        if isinstance(storyboard, list):
            return [scene if isinstance(scene, dict) else {} for scene in storyboard]
        return []

    def select_sound_effects(self, user_requirements: str, storyboard_result: Dict,
                             narration_result: Dict) -> Dict[str, Any]:
        """
        选择音效任务
        """
        # 先获取可用音效列表，直接包含在 prompt 中，避免模型调用工具
        from src.utils.sound_effects_utils import SoundEffectsManager
        available_sounds = SoundEffectsManager.get_available_sound_effects()

        if available_sounds:
            sound_effects_text = "\n".join([f"- {sound}" for sound in available_sounds])
            logger.info(f"[select_sound_effects] 找到 {len(available_sounds)} 个可用音效")
        else:
            logger.warning("[select_sound_effects] 音效库为空")
            return {
                "needs_sound_effects": False,
                "sound_effects": {},
                "reason": "sound_effect_library_empty",
            }

        prompt = SELECT_SOUND_EFFECTS_PROMPT.format(
            user_requirements=user_requirements,
            storyboard_result=str(storyboard_result),
            narration_result=str(narration_result),
            available_sound_effects=sound_effects_text
        )

        # 使用 content_requirements_analyzer agent（没有工具，适合分析任务）
        agent = self.agents.get_content_requirements_analyzer()
        response = agent.run(prompt)
        result = self._parse_json_response(response.content, "select_sound_effects")
        # 如果返回空，使用默认值（不添加音效）
        if not result:
            logger.warning("[select_sound_effects] 模型返回空响应，使用默认值（不添加音效）")
            result = {
                "needs_sound_effects": False,
                "sound_effects": {},
                "reason": "模型未返回有效响应，默认不添加音效"
            }
        return result

    def select_video_engine(
        self,
        user_requirements: str,
        storyboard_result: Dict,
        video_generation_mode: str,
        forced_engine: str | None = None,
    ) -> Dict[str, Any]:
        """
        选择视频生成引擎任务
        """
        forced_engine = str(forced_engine or "").strip()
        if forced_engine:
            logger.info("[select_video_engine] 使用运行时/胶囊指定引擎，跳过视频引擎 Agent")
            return {
                "video_engine": forced_engine,
                "user_specified": True,
                "override_reason": "runtime_or_capsule_forced_engine",
                "compatibility_check": {
                    "video_generation_mode": video_generation_mode,
                    "is_compatible": True,
                    "compatibility_note": "engine supplied by runtime/capsule contract",
                },
            }

        prompt = SELECT_VIDEO_ENGINE_PROMPT.format(
            user_requirements=user_requirements,
            storyboard_result=str(storyboard_result),
            video_generation_mode=video_generation_mode
        )
        agent = self.agents.get_video_engine_selector()
        response = agent.run(prompt)
        # 传递完整的 response 对象，因为使用 tools 时 content 可能为空
        result = self._parse_json_response(response, "select_video_engine")
        # 如果返回空，使用默认值
        if not result:
            logger.warning("[select_video_engine] 模型返回空响应，使用默认引擎 seedance-fast")
            result = {
                "video_engine": "seedance-fast",
                "reason": "模型未返回有效响应，使用默认引擎"
            }
        return result

    def select_art_style(self, user_requirements: str, story_result: Dict,
                         storyboard_result: Dict) -> Dict[str, Any]:
        """
        选择艺术风格任务
        """
        prompt = SELECT_ART_STYLE_PROMPT.format(
            user_requirements=user_requirements,
            story_result=str(story_result),
            storyboard_result=str(storyboard_result)
        )
        agent = self.agents.get_art_style_selector()
        response = agent.run(prompt)

        # 传递完整的 response 对象，因为使用 tools 时 content 可能为空
        result = self._parse_json_response(response, "select_art_style")

        # 如果返回空，使用默认值
        if not result:
            logger.warning("[select_art_style] 模型返回空响应，使用默认艺术风格")
            result = {
                "style_code": "default_style",
                "style_name": "默认风格",
                "visual_style": {
                    "颜色": {"主色调": ["暖色调"], "辅助色": ["柔和中性色"], "氛围特征": "温馨"},
                    "排版": {"元素布局": "居中", "层次关系": "主体清晰、背景简洁"},
                    "构图": {"类型": "稳定居中构图", "特征": "主体突出", "视角": "正面"},
                    "特效": {"元素": ["自然光"], "质感": "柔和干净"}
                },
                "reason": "模型未返回有效响应，使用默认风格"
            }

        # 调试日志：检查 visual_style 是否存在
        if result.get('visual_style'):
            logger.info(f"[select_art_style] ✅ visual_style 存在: {list(result['visual_style'].keys())}")
        else:
            logger.warning(f"[select_art_style] ⚠️ visual_style 不存在或为空！完整结果: {result}")

        return result

    def design_reference(self, user_requirements: str, storyboard_result: Dict,
                         art_style_result: Dict) -> Dict[str, Any]:
        """
        设计参考元素任务
        """
        prompt = DESIGN_REFERENCE_PROMPT.format(
            user_requirements=user_requirements,
            storyboard_result=str(storyboard_result),
            art_style_result=str(art_style_result)
        )
        agent = self.agents.get_reference_designer()
        response = agent.run(prompt)
        return self._parse_json_response(response.content, "design_reference")

    def design_visual_scenes(self, user_requirements: str, character_info: str,
                             batch_start_index: int, batch_end_index: int, batch_size: int,
                             total_scenes: int, batch_scenes: str,
                             previous_scenes_summary: str) -> Dict[str, Any]:
        """
        设计视觉场景任务
        """
        prompt = DESIGN_VISUAL_SCENES_PROMPT.format(
            user_requirements=user_requirements,
            character_info=character_info,
            batch_start_index=batch_start_index,
            batch_end_index=batch_end_index,
            batch_size=batch_size,
            total_scenes=total_scenes,
            batch_scenes=batch_scenes,
            previous_scenes_summary=previous_scenes_summary
        )
        agent = self.agents.get_scene_designer()
        response = agent.run(prompt)
        return self._parse_json_response(response.content, "design_visual_scenes")

    def create_video_directions(self, user_requirements: str,
                                batch_start_index: int, batch_end_index: int, batch_size: int,
                                total_scenes: int, batch_scenes: str, batch_visual_scenes: str,
                                previous_directions_summary: str) -> Dict[str, Any]:
        """
        创建视频指导任务
        """
        prompt = CREATE_VIDEO_DIRECTIONS_PROMPT.format(
            user_requirements=user_requirements,
            batch_start_index=batch_start_index,
            batch_end_index=batch_end_index,
            batch_size=batch_size,
            total_scenes=total_scenes,
            batch_scenes=batch_scenes,
            batch_visual_scenes=batch_visual_scenes,
            previous_directions_summary=previous_directions_summary
        )
        agent = self.agents.get_video_director()
        response = agent.run(prompt)
        return self._parse_json_response(response.content, "create_video_directions")

    def _extract_content_from_response(self, response) -> str:
        """
        从 Agno RunOutput 中提取内容

        当使用 tools 时，response.content 可能为空，
        但实际内容在 response.messages 的最后一条 assistant 消息中

        Gemini 模型的消息内容可能是 parts 列表格式，需要特殊处理
        """
        # 如果 response 是字符串，直接返回
        if isinstance(response, str):
            return response

        # 如果 response 是字典，直接返回
        if isinstance(response, dict):
            return response

        # 尝试获取 content
        content = getattr(response, 'content', None)
        if content:
            # 处理 content 可能是复杂对象的情况
            extracted = self._extract_text_from_content(content)
            if extracted:
                return extracted

        # 如果 content 为空，尝试从 messages 中获取
        messages = getattr(response, 'messages', None)
        if messages:
            # 从后往前找最后一条有内容的 assistant 消息
            for msg in reversed(messages):
                role = getattr(msg, 'role', None)
                if role in ('assistant', 'model'):
                    msg_content = getattr(msg, 'content', None)
                    if msg_content:
                        extracted = self._extract_text_from_content(msg_content)
                        if extracted:
                            logger.debug(f"从 messages 中提取内容: {extracted[:100]}...")
                            return extracted

        return ""

    def _extract_text_from_content(self, content) -> str:
        """
        从各种格式的 content 中提取文本

        支持的格式：
        - 字符串
        - 包含 'text' 键的字典
        - parts 列表（Gemini 格式）
        - 包含 parts 属性的对象
        """
        if isinstance(content, str):
            return content

        if isinstance(content, dict):
            # 尝试获取 text 字段
            if 'text' in content:
                return content['text']
            # 尝试获取 parts 字段
            if 'parts' in content:
                return self._extract_text_from_parts(content['parts'])

        # 尝试获取 parts 属性（Gemini 响应格式）
        parts = getattr(content, 'parts', None)
        if parts:
            return self._extract_text_from_parts(parts)

        # 尝试获取 text 属性
        text = getattr(content, 'text', None)
        if text:
            return text

        # 如果是列表，尝试作为 parts 处理
        if isinstance(content, list):
            return self._extract_text_from_parts(content)

        return ""

    def _extract_text_from_parts(self, parts) -> str:
        """
        从 parts 列表中提取文本内容

        Gemini 模型的响应格式可能是:
        [{'text': '...'}, {'function_call': {...}}, ...]
        """
        if not parts:
            return ""

        text_parts = []
        for part in parts:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, dict):
                if 'text' in part:
                    text_parts.append(part['text'])
            else:
                # 尝试获取 text 属性
                text = getattr(part, 'text', None)
                if text:
                    text_parts.append(text)

        return '\n'.join(text_parts)

    def _parse_json_response(self, response_text, task_name: str) -> Dict[str, Any]:
        """
        解析 Agent 返回的 JSON 响应

        Args:
            response_text: 可以是字符串、字典或 Agno RunOutput 对象
            task_name: 任务名称，用于日志

        Returns:
            解析后的字典
        """
        import json
        import re

        # 先提取内容（处理 Agno RunOutput 对象）
        response_text = self._extract_content_from_response(response_text)

        def normalize_create_storyboard(payload):
            if task_name != "create_storyboard":
                return payload
            if isinstance(payload, list):
                return {"scenes": payload}
            if isinstance(payload, dict):
                normalized = dict(payload)
                storyboard = normalized.get("storyboard")
                if "scenes" not in normalized and isinstance(storyboard, list):
                    normalized["scenes"] = storyboard
                return normalized
            return payload

        if isinstance(response_text, dict):
            return normalize_create_storyboard(response_text)

        if not response_text:
            logger.warning(f"[{task_name}] 空响应")
            return {}

        # 记录原始响应用于调试
        logger.debug(f"[{task_name}] 原始响应: {response_text[:500]}...")

        try:
            return normalize_create_storyboard(json.loads(response_text))
        except json.JSONDecodeError:
            # 尝试从 markdown 代码块中提取 JSON
            json_code_block = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
            if json_code_block:
                try:
                    return normalize_create_storyboard(json.loads(json_code_block.group(1)))
                except json.JSONDecodeError:
                    pass

            # 尝试匹配 JSON 对象（贪婪匹配最外层大括号）
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                try:
                    return normalize_create_storyboard(json.loads(json_match.group()))
                except json.JSONDecodeError:
                    # 尝试修复常见的 JSON 问题
                    json_str = json_match.group()
                    # 移除尾部多余的逗号
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    try:
                        return normalize_create_storyboard(json.loads(json_str))
                    except json.JSONDecodeError:
                        pass

            logger.warning(f"[{task_name}] JSON 解析失败，原始响应: {response_text[:200]}...")
            return {"raw_output": response_text}
