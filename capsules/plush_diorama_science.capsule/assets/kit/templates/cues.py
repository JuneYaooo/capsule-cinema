"""本期音效表：每个镜头里什么时候响什么。mix.py 调 schedule(tl)，返回 [(绝对秒, 音频, dB, 声像)]。

原则（详见胶囊 recipes/audio.md）
- 时间不靠耳朵对，照抄 scene3d/shots.py 里同一个镜头的动画节点：关键词事件 E(...)、smoothstep 区间、
  步态相位过零（footfalls）。动画改了，这里同步改同一个数。
- 每个看得见的动作配一个声音；持续的状态（下雨、冒泡、时间流逝）用带淡入淡出的长音。
- 有音高的（blip / sparkle / ding / tada）自动落在 BGM 的调上；一串东西出现就用上行音阶 X.note(i)。
- 电平参考：最响的单发 −14～−18 dB（裂开、揭晓、盖章），普通动作 −20～−26，脚步、环境 −28～−36。
- 声像 pan 在 −0.4～0.4 之间，跟着物体在画面里的左右。

下面的例子是占位的镜头 id，演示常用写法；按本期 shots.py 改写。
"""
import numpy as np

import sfx as X

SR = X.SR


def smoothstep_inv(a, b, y):
    """smoothstep(a, b, t) = y 的 t（二分）。动画在 smoothstep 里走到第 y 比例时出声。"""
    lo, hi = 0.0, 1.0
    for _ in range(40):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if 3 * m * m - 2 * m ** 3 < y else (lo, m)
    return a + (b - a) * (lo + hi) / 2


def schedule(tl):
    shots = {s["id"]: s for s in tl["shots"]}
    out = []
    rng = np.random.default_rng(7)

    def at(sid, t, y, gain, pan=0.0):
        """镜头内时间 t（秒）放音频 y。"""
        if sid in shots:
            out.append((shots[sid]["start"] + t, y, gain, pan))

    def E(sid, key, default):
        """镜头里的口播事件时间：kw:<词> 关键词、c<句>.<段> 字幕段开口、end<句> 句末。"""
        return shots[sid]["events"].get(key, default) if sid in shots else default

    def dur(sid):
        return shots[sid]["end"] - shots[sid]["start"] if sid in shots else 0.0

    def footfalls(sid, speed, offset, t_end):
        """shots.py 里 phase = t*speed + offset，腿摆 sin(phase) 过零 = 落脚。返回镜头内时间列表。"""
        k = int(np.ceil(offset / np.pi))
        ts = []
        while True:
            t = (k * np.pi - offset) / speed
            if t > t_end:
                return ts
            if t >= 0:
                ts.append(t)
            k += 1

    # ---- 例 1：开场一队角色小碎步（每只脚步音高略不同，声像跟着位置）
    for i, (pitch, pan) in enumerate([(1.0, 0.25), (1.15, 0.0), (1.3, -0.25)]):
        for t in footfalls("sh01", 11, i * 1.1, dur("sh01")):
            at("sh01", t, X.step(pitch * rng.uniform(0.95, 1.05), seed=int(t * 100) + i), -31, pan)
    at("sh01", 0.02, X.pop(1.2), -22)                         # 标题弹出

    # ---- 例 2：揭晓前的预告——光慢慢亮（shimmer 提前 0.6 s 进），说到词时啵 + 闪光
    k = E("sh03", "kw:<成品名>", 1.6)
    at("sh03", k - 0.6, X.shimmer(0.9, seed=3), -32)
    at("sh03", k - 0.05, X.pop(0.8), -20)
    at("sh03", k + 0.05, X.sparkle(5), -22, 0.15)

    # ---- 例 3：一串东西一个个冒出来 → 上行五声音阶（与 shots.py 里 0.3 + 0.12*i 的出现时间一致）
    for i in range(8):
        at("sh04", 0.3 + 0.12 * i + 0.08, X.blip(X.note(i)), -24, float(rng.uniform(-0.35, 0.35)))

    # ---- 例 4：外壳裂开（全片最响的单发之一）
    at("sh06", E("sh06", "kw:<词>", 0.1) + 0.12, X.crack(), -14)

    # ---- 例 5：数值一降一升 → 两段滑哨，左右分开
    k1, k2 = E("sh07", "kw:<下降的词>", 0.7), E("sh07", "kw:<上升的词>", 2.3)
    at("sh07", k1, X.slide(900, 450, 0.6), -26, -0.3)
    at("sh07", k2, X.slide(450, 900, 0.6), -26, 0.3)

    # ---- 例 6：分裂繁殖 1→2→4→8→16（与 shots.py 里 gen = smoothstep(0, 1.7, t) * 4 一致）
    for b in range(1, 5):
        t_b = smoothstep_inv(0.0, 1.7, (b - 0.5) / 4)
        for _ in range(2 ** (b - 1)):
            at("sh10", t_b + float(rng.uniform(-0.04, 0.04)), X.pop(0.9 + 0.15 * b), -24 - 1.5 * (b - 1),
               float(rng.uniform(-0.35, 0.35)))

    # ---- 例 7：时间流逝 → 越走越快的钟
    at("sh11", 0.0, X.tick_tock(dur("sh11")), -27)

    # ---- 例 8：揭晓（全片最响）
    at("sh12", E("sh12", "kw:<成品名>", 0.74) - 0.05, X.tada(), -16)

    # ---- 例 9：警告：坏角色冒出来 + 禁止牌
    k1, k2 = E("sh13", "kw:<坏东西>", 0.7), E("sh14", "kw:<千万别……>", 1.4)
    for i in range(6):
        at("sh13", k1 - 0.3 + 0.08 * i + 0.15, X.evil_bloop(0.9 + 0.08 * i), -24, -0.3 + 0.1 * i)
    at("sh14", k2, X.stamp(), -16, 0.2)
    at("sh14", k2 + 0.05, X.buzz(), -26, 0.2)
    return out
