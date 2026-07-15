# 视频制作经验

当前可复用配方沉淀到 `capsules/<name>.capsule/` 目录包。

## 通用建议

| 项目 | 建议 |
| --- | --- |
| 竖屏短视频 | `9:16` |
| 横屏视频 | `16:9` |
| 公开图片引擎 | `volcengine-seedream`（官方火山引擎 Ark） |
| 公开视频引擎 | `seedance2.0`（官方火山引擎 Ark） |
| 图片提示词 | 推荐中文；不要要求图片模型生成标题、字幕或 UI 文字 |
| 分镜类型 | 完整视频工作流使用普通 `image_to_video` 分镜 |
| 分镜时长 | 以实测 TTS 时长为准；长旁白拆成多个画面 |
| BGM | 使用用户提供的本地音频或胶囊内公开资产 |
| 字幕 | 后期叠加，不在图片提示词里生成 |

## 质量规则

- 每个分镜只保留一个清晰焦点，主体、动作、环境和镜头意图要具体。
- 先锁角色与画风，再批量扩展分镜；复用稳定的角色和风格参考。
- 同一连续性组只改变动作阶段、表情、景别和镜头角度，不随意改变身份锚点。
- 每批生成后检查角色、画风、比例、道具和商品一致性，再继续下一批。
- 云端结果必须下载到本地；产物清单只记录本地路径。

## 胶囊渠道边界

公开胶囊只能引用公开注册表工具、用户素材、本地处理或胶囊内公开资产。
引用本地覆盖层渠道的胶囊必须保持 Git 忽略状态。

```bash
PYTHONPATH=lib python3.12 scripts/capsule_package_validate.py capsules/<name>.capsule
PYTHONPATH=lib python3.12 scripts/capsule_package_pack.py capsules/<name>.capsule --out dist/capsules
```
