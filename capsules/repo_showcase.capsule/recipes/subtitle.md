# Subtitle

## five_line_bottom_cards_policy

{
  "default": "bottom_lines 默认优先 5 行。",
  "fallback": "如果硬凑第 5 行会变成废话，允许 4 行；少于 4 行需要明确原因。",
  "layout_pairing": "与 adaptive_bottom_layout_policy 配合使用：5 行自动收紧字号和行距，4 行中等密度，3 行仅在信息不足时放大展示。",
  "line_rules": [
    "每行必须是一句完整短句。",
    "每行只推进一个痛感场景、事实证据、输出价值、机制信息或可信边界。",
    "不要把文件名、命令、安装步骤、链接或操作教程当成主要内容。",
    "5 行不是凑字数；删掉任意一行后用户理解明显变少，才算有效。"
  ],
  "purpose": "repo_showcase 底部卡片默认做成高密度价值卡，避免 3 行版本画面偏空、信息量不足。",
  "qa_requirement": "5 行版本必须抽帧检查：文字不能出框、不能压脚注、不能因为英文/.pptx 混排变得难读。",
  "required": true
}
