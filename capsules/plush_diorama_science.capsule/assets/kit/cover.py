"""封面：揭晓镜头的一帧 + 和标题带同一句的大字（两行：关键词一行，问句一行）。

python3.12 cover.py → ../cover.jpg     哪一帧读 episode.COVER_FRAME。
"""
from PIL import Image

import overlay as O
from episode import COVER_FRAME, TITLE

shot, frame = COVER_FRAME
base = Image.open(O.ROOT / "frames" / shot / f"f_{frame:04d}.jpg").convert("RGBA")
(kw, kw_color), (rest, rest_color) = TITLE[0], TITLE[1]
l1, _, _ = O.line_img([(kw, kw_color)], 230, O.F_TITLE, stroke=14)
l2, _, _ = O.line_img([(rest, rest_color)], 140, O.F_TITLE, stroke=11)
s1 = min(1.0, (O.W - 80) / l1.width)          # 关键词太长就整体缩小，左右各留 40 px
s2 = min(1.0, (O.W - 80) / l2.width)
O.paste_center(base, l1, O.W / 2, 265, s1)
O.paste_center(base, l2, O.W / 2, 265 + 197 * (0.5 + 0.5 * s1), s2)
base.convert("RGB").save(O.ROOT / "cover.jpg", quality=95)
print("cover ->", O.ROOT / "cover.jpg")
