# Subtitle

## subtitle_rules

{
  "body_policy": "正文默认不烧底部字幕；只保留片头文字、顶部场景标题和必要警示标签。除非用户明确要求字幕，否则不要烧正文对白字幕。",
  "evidence_artifact": "生成 qa/visible_copy_lint.json 和 internal/viewer_visible_text.txt；正文无字幕时不要求 body ASS 对齐文件。",
  "opening_card_policy": "开头摇摇机卡片显示“每天一个模拟人生/今天抽到/主题”，不要再叠底部对白字幕造成重复。",
  "required_gate": "最终 QA 检查 viewer_visible_text 只包含片头、场景标题、必要警示和平台文案；正文口播不应出现在底部烧录字幕中。若用户临时要求字幕，再单独生成字幕对齐报告。"
}
