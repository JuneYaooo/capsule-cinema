"""镜头原型库：每个原型一个 build 函数，搭自己的布景，返回 state(t, ev)，按镜头内时间设置一帧。

ev 是这个镜头里的口播事件（相对镜头起点的秒数）：c<句>.<段> 字幕段开口、kw:<词> 关键词、end<句> 句末。
动作的关键时刻一律挂在 ev 上（evt(ev, "kw:<词>", 预览用默认值)），不写死秒数——配音一换，动画自动跟上。

原型按三个世界分组（什么时候用哪个，见胶囊 recipes/structure.md）：
  角色世界：trot_in 小碎步开场 / peek 偷看 / discover 发现与预告 / motive_gather 动机·收集 / motive_need 动机·缺什么 /
           aroma 香气 / reveal 揭晓 / stop_sign 劝阻收尾 / time_lapse 时间流逝
  剖面世界：cutaway_fill 落进容器 / cutaway_rise 液面上涨 / split 分裂繁殖 / plug 堵住 / lack_badge 缺少 /
           die_off 停止·死亡 / warning 坏东西冒出来
  实验台：  condition 条件（锁 + 温度计）/ analogy 相当于 / macro_reveal 推近看到微观角色 / meter 冲到上限 /
           mode_switch 切换模式 / molecule_split 分解 / molecule_merge 结合 / level_compare 一降一升
文件末尾的 SHOTS 把本期镜头 id 映射到原型（和 episode.SHOT_STARTS 一一对应），同一个原型可以给多个镜头用。
普通原型默认固定机位；横向跟拍保持距离与焦段，揭晓和收尾只在事件附近短暂移动，随后停住。
同一原型复用时按分镜改变景别、角度和视觉重点；动作跨切点必须接续，不能重启。
本期照着原型改：换角色、换容器、换道具、换关键词，镜头语法不变；原型里没有的，照同样的写法新加一个。
"""
import math
import random

from mathutils import Vector

import lib3d as L
from lib3d import cam_move, ease_in_out, ease_out_back, ease_out_cubic, evt, lerp, smoothstep, walk_phase

FONT = None   # 由 render_shot 注入（3D 字用）

# 角色表：主角固定一套毛色 + 配饰，全片不换；配角体型小一号、配饰不同
CAST = dict(
    hero=dict(fur="#b8916a", hat=True, scarf="#d9774b", seed=1),
    pal1=dict(fur="#a98260", scarf="#8faac8", seed=7, s=0.82),
    pal2=dict(fur="#c29d76", seed=13, s=0.66),
)
CONTAINER = "tree"            # 主容器：tree（HollowTree）或 jar（CutawayJar）
STUFF = ["persimmon", "plum", "pear", "peach", "berry"]   # 装进容器的小东西（FruitBank 的种类）
LIQ = dict(start="#c9782f", mid="#e2953f", done="#e7a85a", bad="#7d8a3a")   # 剖面液体的颜色进度


def critter(name, role, **kw):
    return L.PlushCritter(name, **{**CAST[role], **kw})


def container(name="box", loc=(0, 0.4, 0), cutaway=False, **kw):
    if CONTAINER == "jar":
        return L.CutawayJar(name, loc=loc, cutaway=cutaway, **kw)
    return L.HollowTree(name, loc=loc, cutaway=cutaway, autumn=True, canopy=not cutaway, **kw)


def sparkles(n, mat_strength=6.0, s=0.05):
    m = L.mat_basic("spark", "#fff1c2", emit="#ffe08a", emit_strength=mat_strength)
    return [L.sparkle(f"sp{i}", s=s, mat=m) for i in range(n)]


def burst(sps, center, t, k, spread=0.3, y=-0.9):
    """k 时刻闪光一圈散开再收掉（揭晓、反应完成）。"""
    v = smoothstep(k, k + 0.3, t) * (1 - smoothstep(k + 0.45, k + 0.8, t))
    for i, s in enumerate(sps):
        a = i / len(sps) * math.tau
        s.location = (center[0] + spread * math.cos(a) * (0.6 + v), y, center[2] + spread * math.sin(a) * (0.6 + v))
        s.rotation_euler = (0, t * 2 + i, 0)
        L.hide(s, v)


def cut_base(level=None, color=LIQ["mid"], n_stuff=26, seed=11, yaw=-15):
    """剖面世界的标准开场：剖开的主容器 + 一堆小东西 + 液体。每次回到剖面都用它，状态接着上一次。"""
    cam, _ = L.stage_base(mountains_on=False)
    box = container("box", loc=(0, 0.3, 0), cutaway=True)
    box.root.rotation_euler = (0, 0, math.radians(yaw))
    obs = L.place_pile(box, L.FruitBank(), L.drop_pile(box, n_stuff, seed=seed, kinds=STUFF)) if n_stuff else []
    liq = None
    if level is not None:
        liq = L.CutLiquid(box, color=color, emit=0.5)
        liq.set_level(level)
    return cam, box, obs, liq


# ============================================================ 角色世界

def trot_in():
    """trot_in：开场一队毛绒角色小碎步横穿台面（系列招牌动作），镜头跟着走。"""
    cam, _ = L.stage_base()
    L.lolli_tree("t1", (-2.3, 1.2, 0), h=1.4, r=0.55, color="#9aa88a", seed=1)
    L.lolli_tree("t2", (2.4, 1.4, 0), h=1.1, r=0.5, color="#a9b496", seed=2)
    L.bush("b1", (1.5, 0.9, 0), r=0.45, seed=3)
    team = [critter("c1", "hero"), critter("c2", "pal1"), critter("c3", "pal2")]

    def state(t, ev):
        lead_x = -0.35 + 0.42 * t
        for i, c in enumerate(team):
            c.pose(loc=(lead_x - i * 0.58, -0.2 + 0.1 * i, 0), heading=math.radians(65), gait=1.0,
                   phase=walk_phase(t) + i * 1.1, head=(0, 0, math.radians(15)))
            c.set_eyes("blink", 1.0 if (t + i * 0.4) % 2.6 < 0.12 else 0.0)
        cx = lead_x - 0.55
        L.aim_camera(cam, (cx - 0.35, -4.6, 1.05), (cx, 0, 0.55), lens=50, fstop=2.8)
    return state


def peek():
    """peek：前景草丛后探出主角的半个头，偷看远处的队伍（浅景深，焦点在主角）。"""
    cam, _ = L.stage_base()
    L.bush("fg", (-0.25, -1.0, 0), r=0.36, seed=21)
    L.lolli_tree("t1", (1.5, 1.5, 0), h=1.3, r=0.5, seed=22)
    spy = critter("spy", "hero")
    lead = [critter("l1", "pal1"), critter("l2", "pal2")]

    def state(t, ev):
        up = ease_out_back(smoothstep(0.0, 0.45, t))
        spy.pose(loc=(-0.25, -0.78, lerp(-0.5, -0.17, up)), heading=math.radians(25), head=(0.05, 0, math.radians(25)))
        spy.set_eyes("blink", 1.0 if 0.9 < t < 1.0 else 0.0)
        for i, c in enumerate(lead):
            c.pose(loc=(0.05 + 0.45 * t + i * 0.55, 0.75, 0), heading=math.radians(70), gait=1.0,
                   phase=walk_phase(t) + i)
        L.aim_camera(cam, (-0.55, -3.7, 0.72), (0.1, 0, 0.5), lens=50, fstop=2.4, focus=2.95)
    return state


def discover():
    """discover：主角走到主容器前停下，开口透出金光，成品（罐子）弹出 + 闪光——给传说结果一个预告。"""
    cam, _ = L.stage_base(key=900)
    box = container("box", loc=(0.35, 0.55, 0))
    hole = box.hole_world()
    lamp = L.point_light("glow", (hole.x, hole.y - 0.2, hole.z), energy=0.0, color="#ffad42", radius=0.15)
    hero = critter("c1", "hero")
    prize = L.labeled_jar("prize", (0.12, -0.55, 0), s=0.5, font=FONT)
    sps = sparkles(5)

    def state(t, ev):
        k = evt(ev, "kw:<成品名>", 1.6)
        g = smoothstep(k - 0.6, k, t)
        lamp.data.energy = 120.0 * g
        prize.scale = (0.55 * ease_out_back(smoothstep(k - 0.15, k + 0.35, t)),) * 3
        burst(sps, (0.1, 0, 0.6), t, k, spread=0.35)
        stop = smoothstep(0.6, 1.2, t)
        hero.pose(loc=(-1.0 + 0.5 * min(t, 1.0), -0.5, 0), heading=math.radians(60 - 60 * stop), gait=1.0 - stop,
                  phase=walk_phase(t), head=(-0.25 * g, 0, 0), arm_r=(-2.4 * g, 0, 0.2) if g > 0 else None)
        hero.set_blush(g)
        L.aim_camera(cam, (-0.3, -6.2, 1.25), (-0.1, 0, 0.85), lens=50, fstop=2.8)
    return state


def motive_gather():
    """motive（「原来……」）：环境变化 + 东西一个个冒出来（音效配上行音阶）。"""
    cam, _ = L.stage_base()
    box = container("box", loc=(0, 0.4, 0))
    bank = L.FruitBank()
    random.seed(4)
    items = []
    for i in range(8):
        a = random.random() * math.tau
        p = (math.cos(a) * 0.9, -0.6, 1.2 + 0.5 * math.sin(a))
        items.append((bank.make(STUFF[i % len(STUFF)], f"h{i}"), p, 0.3 + 0.12 * i))
    hero = critter("c1", "hero")

    def state(t, ev):
        for f, p, t0 in items:
            L.drop_in(f, p, t, t0, h=0.25)
        hero.pose(loc=(-1.0, -0.6, 0), heading=math.radians(30), head=(-0.3, 0, 0.3),
                  arm_l=(-2.4, 0, 0.3), hop=0.03 * abs(math.sin(t * 6)))
        hero.set_eyes("happy" if t > 1.0 else "open")
        L.aim_camera(cam, (0, -6.4, 1.6), (0, 0, 1.25), lens=40, fstop=4)
    return state


def motive_need():
    """motive（「为了……」）：发愁的主角抱胳膊 + 空篮子；冷色光表示缺东西。"""
    cam, lights = L.stage_base(key=900)
    L.basket("bk", (0.35, -0.5, 0), r=0.2)
    hero = critter("c1", "hero")

    def state(t, ev):
        hero.pose(loc=(-0.2, -0.45, 0), heading=math.radians(20), arm_l=(-1.2, 0, 0.9), arm_r=(-1.2, 0, -0.9),
                  head=(0.15, 0.1 * math.sin(t * 2), 0))
        hero.set_eyes("blink", 0.4)
        lights["key"].data.color = L.mix_col(L.col("#fff3e3"), L.col("#e6eef7"), smoothstep(0, 1.0, t))[:3]
        L.aim_camera(cam, (0.1, -3.4, 0.9), (0.1, 0, 0.5), lens=50, fstop=2.8)
    return state


# ============================================================ 剖面世界（同一个容器剖开，状态一镜接一镜往前走）

def cutaway_fill():
    """cutaway_fill：剖面里小东西一颗颗落进来堆满，说到「挤压」时越压越扁。"""
    cam, box, obs, _ = cut_base()
    entry = box.opening()[0] + Vector((0, 0.2, 0))

    def state(t, ev):
        L.pile_state(obs, squash=smoothstep(evt(ev, "kw:<词>", 0.67), 1.6, t) * 0.55)
        for i, (f, p, sc) in enumerate(obs):
            u = (t - 0.03 * i) / 0.32
            if u < 0:
                L.hide(f, 0)
            elif u < 1:
                q = entry.lerp(p, ease_in_out(u))
                f.location = (q.x, q.y, q.z + 0.2 * math.sin(math.pi * u))
        L.aim_camera(cam, (0.0, -4.2, 1.0), (0, 0.3, 0.92), lens=45, fstop=4)
    return state


def cutaway_rise():
    """cutaway_rise：液面从底部涨起来——液面高度和颜色是剖面世界的进度条，下一次回剖面要接着这个状态。"""
    cam, box, obs, liq = cut_base(level=0.0, color=LIQ["start"])

    def state(t, ev):
        L.pile_state(obs, squash=0.55)
        u = smoothstep(0.1, 2.2, t)
        liq.set_level(0.45 * u)
        liq.set_color(L.mix_col(L.col(LIQ["start"]), L.col(LIQ["mid"]), u), emit=0.4 + 0.2 * u)
        L.aim_camera(cam, (0.0, -3.6, 0.9), (0, 0.3, 0.82), lens=48, fstop=4)
    return state


def split():
    """split：一个微观角色啵啵分裂 1→2→4→8→16，挤满液面（cues.py 用同一条 smoothstep 算每代的啵声）。"""
    cam, box, obs, liq = cut_base(level=0.62, color=LIQ["done"])
    top = liq.level_z(0.62)
    random.seed(17)
    agents = []
    for i in range(16):
        a = L.FluffAgent(f"a{i}", r=0.06, seed=i)
        a.root.parent = box.root
        agents.append((a, Vector((random.uniform(-0.3, 0.3), 0.0, top - 0.06 - random.uniform(0, 0.34)))))

    def state(t, ev):
        L.pile_state(obs, squash=0.55)
        gen = smoothstep(0.0, 1.7, t) * 4.0
        for i, (a, p) in enumerate(agents):
            born = 0 if i == 0 else math.floor(math.log2(i)) + 1
            u = ease_out_back(min(1.0, max(0.0, gen - born + 1)))
            q = (agents[i // 2][1] if i else p).lerp(p, u)
            a.root.location = (q.x, q.y, q.z + 0.01 * math.sin(t * 5 + i))
            L.hide(a.root, 0.2 + 0.8 * u if u > 0.01 else 0)
            for e in a.eyes:
                e.scale = (1, 1, 0.1 if ((t + i * 0.37) % 1.8) < 0.1 else 1)
        L.aim_camera(cam, (0.0, -2.6, 0.95), (0, 0.3, 0.86), lens=50, fstop=3.2)
    return state


def warning():
    """warning：坏角色（深色刺球）一个个冒出来，液体变浑绿、冒毒泡。"""
    cam, box, obs, liq = cut_base(level=0.62, color=LIQ["done"])
    top = liq.level_z(0.62)
    bads = []
    for i in range(6):
        g = L.SpikyAgent(f"g{i}", r=0.065 + 0.015 * (i % 3), hue=["#4b5a3c", "#5a4a5e", "#3f5560"][i % 3], seed=i)
        g.root.parent = box.root
        bads.append((g, Vector((-0.3 + 0.12 * i, 0.0, top - 0.08 - 0.28 * ((i * 0.37) % 1.0)))))
    tox_m = L.mat_basic("tox", "#9bc75a", rough=0.2, emit="#9bc75a", emit_strength=1.2, alpha=0.7)
    bubs = [L.ellipsoid(f"tb{i}", 0.025 + 0.01 * (i % 3), mats=[tox_m], segs=16, rings=8) for i in range(10)]
    for b in bubs:
        b.parent = box.root

    def state(t, ev):
        L.pile_state(obs, squash=0.55)
        k1, k2 = evt(ev, "kw:<坏东西>", 0.7), evt(ev, "kw:<有害结果>", 2.3)
        for i, (g, p) in enumerate(bads):
            u = ease_out_back(smoothstep(k1 - 0.3 + 0.08 * i, k1 + 0.05 + 0.08 * i, t))
            g.root.location = (p.x + 0.02 * math.sin(t * 4 + i), p.y, p.z + 0.02 * math.sin(t * 5 + i))
            g.root.rotation_euler = (0, 0.3 * math.sin(t * 3 + i), 0.4 * math.sin(t * 2 + i))
            L.hide(g.root, u)
        tox = smoothstep(k2 - 0.6, k2 + 0.4, t)
        liq.set_color(L.mix_col(L.col(LIQ["done"]), L.col(LIQ["bad"]), tox), emit=0.55 - 0.2 * tox)
        for i, b in enumerate(bubs):
            u = ((t - k2) * 0.7 + i / 10) % 1.0
            b.location = (-0.3 + 0.065 * i, -0.02, top - 0.25 + 0.6 * u)
            L.hide(b, tox * (1 - smoothstep(0.85, 1.0, u)))
        L.aim_camera(cam, (0.0, -2.6, 1.0), (0, 0.3, 0.92), lens=50, fstop=3.2)
    return state


# ============================================================ 隐喻道具与实验台

def condition():
    """condition：「密闭」→ 锁啪地弹出；「稳定」→ 温度计液柱冲上去后稳住。"""
    cam, box, obs, liq = cut_base(level=0.45)
    th = L.thermometer("th", (0.5, -0.45, 0.0), h=0.7)
    th["root"].scale = (1.4, 1.4, 1.0)
    lock_m = L.mat_basic("lock", "#d9b25a", rough=0.3, metallic=0.7)
    lock = L.empty("lock", loc=(-0.42, -0.45, 1.35))
    L.box("lockbody", 0.2, 0.08, 0.16, parent=lock, mats=[lock_m])
    L.torus("lockarc", 0.07, 0.018, loc=(0, 0, 0.09), parent=lock, rot=(math.radians(90), 0, 0), mats=[lock_m])

    def state(t, ev):
        L.pile_state(obs, squash=0.55)
        k1, k2 = evt(ev, "kw:<密闭>", 1.0), evt(ev, "kw:<稳定>", 1.6)
        L.hide(lock, ease_out_back(smoothstep(k1 - 0.1, k1 + 0.25, t)))
        lv = 0.25 + 0.4 * ease_out_back(smoothstep(k2 - 0.2, k2 + 0.5, t)) + 0.01 * math.sin(t * 6)
        th["liquid"].scale = (1, 1, lv * th["h"])
        L.aim_camera(cam, (0.0, -4.6, 1.0), (0, 0.3, 0.75), lens=42, fstop=4)
    return state


def analogy():
    """analogy（「相当于一个……」）：主容器轻轻弹一下，旁边浮出同样形状的人造物 + 「=」号（标签写人造物的名字）。"""
    cam, _ = L.stage_base()
    box = container("box", loc=(-0.55, 0.45, 0))
    twin = L.glass_tube("twin", r=0.34, h=0.95, liquid=LIQ["mid"], loc=(0.85, -0.25, 0))
    twin["liquid"].scale = (1, 1, 0.5)
    eq_m = L.mat_basic("eq", "#f6f0e2", rough=0.4, emit="#ffffff", emit_strength=0.8)
    eq = [L.box(f"eq{i}", 0.3, 0.05, 0.055, loc=(0.2, -0.55, 0.95 + i * 0.13), mats=[eq_m]) for i in range(2)]

    def state(t, ev):
        k = evt(ev, "kw:<类比物名>", 0.77)
        L.hide(twin["root"], ease_out_back(smoothstep(k - 0.2, k + 0.35, t)))
        for e in eq:
            L.hide(e, smoothstep(k, k + 0.2, t))
        sq = 1 + 0.06 * math.sin(max(0, t - k) * 18) * math.exp(-max(0, t - k) * 4) * (t > k)
        box.root.scale = (1 / math.sqrt(sq), 1 / math.sqrt(sq), sq)   # 体积不变的挤一下
        L.aim_camera(cam, (0.15, -7.0, 1.8), (0.15, 0, 1.45), lens=38, fstop=4)
    return state


def meter():
    """meter：微观角色越来越醉/越来越撑，旁边刻度计冲到红色上限带（标签写数值）。"""
    cam, _ = L.stage_base(mountains_on=False)
    hero = L.FluffAgent("hero", r=0.16, seed=5)
    meter = L.glass_tube("meter", r=0.07, h=1.1, liquid="#e09a3a", loc=(0.45, -0.2, 0))
    band_m = L.mat_basic("bandm", "#d33b2f", rough=0.4, emit="#d33b2f", emit_strength=0.8, alpha=0.6)
    band = L.cone("band", 0.09, 0.09, 0.11, segs=32, mats=[band_m])

    def state(t, ev):
        k1, k2 = evt(ev, "kw:<上限>", 0.9), evt(ev, "kw:<数值>", 2.6)
        lv = ease_in_out(smoothstep(0.0, k2 + 0.4, t))
        meter["liquid"].scale = (1, 1, (0.05 + 0.75 * lv) * meter["h"])
        band.location = (0.45, -0.2, 0.01 + 0.8 * meter["h"] * 0.92)
        L.hide(band, smoothstep(k2 - 0.3, k2, t))
        drunk = smoothstep(k1 - 0.5, k2 + 0.3, t)
        sway = 0.3 * drunk * math.sin(t * 3.0)
        hero.root.location = (-0.12 + 0.05 * sway, -0.05, 0.3 + 0.02 * math.sin(t * 5))
        hero.root.rotation_euler = (0, sway, 0)
        for e in hero.eyes:
            e.scale = (1, 1, 1 - 0.6 * drunk)
        L.aim_camera(cam, (0.15, -2.9, 0.65), (0.15, -0.2, 0.42), lens=45, fstop=3.2)
    return state


# ============================================================ 揭晓与收尾（回到角色世界）

def reveal():
    """reveal（「这，就是……」）：主角双手举起成品，朋友们欢呼跳，成品发光 + 闪光，镜头快推慢停。"""
    cam, _ = L.stage_base()
    container("box", loc=(0.75, 0.75, 0))
    hero, p1, p2 = critter("c1", "hero"), critter("c2", "pal1", s=0.75), critter("c3", "pal2", s=0.62)
    bowl = L.bowl("bowl", (0, 0, 0), r=0.12, liquid=LIQ["done"])
    sps = sparkles(7, mat_strength=8.0)
    random.seed(30)
    spp = [(random.uniform(-0.35, 0.35), random.uniform(0.0, 0.5)) for _ in sps]

    def state(t, ev):
        k = evt(ev, "kw:<成品名>", 0.74)
        lift = ease_out_back(smoothstep(k - 0.45, k + 0.05, t))
        hero.pose(loc=(-0.05, -0.45, 0), arm_l=(-1.45 - 0.3 * lift, 0, 0.35), arm_r=(-1.45 - 0.3 * lift, 0, -0.35),
                  head=(0.12 - 0.22 * lift, 0, 0), hop=0.04 * lift)
        hero.set_eyes("happy" if lift > 0.5 else "open")
        hero.set_blush(lift)
        bowl["root"].location = (-0.05, -0.76 - 0.04 * lift, 0.37 + 0.09 * lift)
        for c, x, hd, ph in ((p1, -0.7, 25, 0), (p2, 0.55, -25, 1)):
            c.pose(loc=(x, -0.2, 0), heading=math.radians(hd), arm_l=(-2.6, 0, 0), arm_r=(-2.6, 0, 0),
                   hop=0.06 * abs(math.sin(t * 7 + ph)) * lift)
            c.set_eyes("happy")
        v = smoothstep(k, k + 0.3, t)
        for i, s in enumerate(sps):
            s.location = (-0.05 + spp[i][0], -0.85, 0.55 + spp[i][1] * v)
            sc = v * (0.6 + 0.4 * math.sin(t * 8 + i))
            s.scale = (sc, sc, sc)
        L.set_mat_color(bowl["mat"], L.col(LIQ["done"]), emit_strength=0.9 + 3.0 * v)
        cam_move(cam, t - (k - 0.35), 0.5, (0.0, -4.4, 1.0), (0.0, -3.2, 0.95), (-0.05, 0, 0.7), (-0.05, 0, 0.8), 45, 45, fstop=2.8, ease=ease_out_cubic)
    return state


def stop_sign():
    """stop_sign（「千万别……」）：主角正要伸手，被朋友按住摇头，禁止牌啪地弹出带晃动；镜头往后拉成全景收尾。"""
    cam, _ = L.stage_base()
    container("box", loc=(0.9, 0.7, 0))
    hero, pal = critter("c1", "hero"), critter("c2", "pal1", s=0.85)
    bowl = L.bowl("bowl", (0, 0, 0), r=0.11, liquid=LIQ["bad"])
    sign = L.empty("signroot")
    L.no_sign("no", (0, 0, 0), r=0.26).parent = sign

    def state(t, ev):
        k = evt(ev, "kw:<千万别……>", 1.4)
        reach = smoothstep(0.1, 0.9, t) * (1 - smoothstep(k - 0.1, k + 0.2, t))
        hero.pose(loc=(-0.25, -0.45, 0), heading=math.radians(10), arm_l=(-1.45 - 0.45 * reach, 0, 0.35),
                  arm_r=(-1.45 - 0.45 * reach, 0, -0.35), head=(0.1 - 0.2 * reach, 0, 0))
        bowl["root"].location = (-0.2, -0.75, 0.37 + 0.15 * reach)
        stopper = smoothstep(k - 0.4, k, t)
        shake = 0.35 * math.sin(t * 14) * smoothstep(k, k + 0.2, t) * (1 - smoothstep(k + 1.4, k + 1.8, t))
        pal.pose(loc=(-0.85, -0.4, 0), heading=math.radians(60), arm_r=(-1.6 * stopper, -0.6 * stopper, 0),
                 head=(0, 0, shake))
        u = ease_out_back(smoothstep(k - 0.05, k + 0.3, t))
        sign.location = (0.12, -0.65, 1.05)
        sign.scale = (u, u, u)
        sign.rotation_euler = (0, 0.15 * math.sin(max(0, t - k) * 10) * math.exp(-max(0, t - k) * 3), 0)
        cam_move(cam, t - (k + 0.3), 0.8, (-0.15, -3.9, 1.05), (-0.1, -4.6, 1.15), (-0.15, 0, 0.72), (-0.05, 0, 0.8), 42, 42, fstop=2.8)
    return state


def macro_reveal():
    """macro_reveal：推近一颗小东西，表面的「霜」原来是一颗颗带脸的小毛球，说到词时冒出来、眨眼。"""
    cam, _ = L.stage_base(mountains_on=False)
    hero = L.FruitBank().make(STUFF[1], "hero")
    hero.location = (0, 0, 0.36)
    hero.scale = (4.0, 4.0, 4.0)
    random.seed(13)
    agents = []
    for i, (a, b) in enumerate([(-0.55, 0.25), (0.15, 0.55), (0.6, 0.1), (-0.15, -0.15), (0.35, -0.4),
                                (-0.75, -0.35), (0.85, 0.5), (-0.35, 0.75)]):
        n = Vector((math.sin(a) * math.cos(b), -math.cos(a) * math.cos(b), math.sin(b)))
        ag = L.FluffAgent(f"a{i}", r=0.04 + 0.012 * random.random(), seed=i)
        ag.root.location = Vector((n.x * 0.36, n.y * 0.35, 0.36 + n.z * 0.38))
        ag.root.rotation_euler = (0, 0, math.atan2(n.x, -n.y))
        agents.append((ag, random.random() * 3))

    def state(t, ev):
        k = evt(ev, "kw:<小东西的名字>", 1.8)
        for i, (ag, ph) in enumerate(agents):
            pop = ease_out_back(smoothstep(k - 0.5 + i * 0.04, k - 0.2 + i * 0.04, t))
            L.hide(ag.root, 0.4 + 0.6 * pop)
            for e in ag.eyes:
                e.scale = (1, 1, 0.1 if ((t + ph) % 2.2) < 0.1 else 1) if pop > 0.5 else (1e-4, 1e-4, 1e-4)
        dist = lerp(3.0, 1.95, ease_out_cubic((t - (k - 0.5)) / 0.5))
        cam_move(cam, t - (k - 0.5), 0.5, (0.0, -3.0, 0.75), (0.0, -1.95, 0.6), (0, 0, 0.42), (0, 0, 0.42), 50, 50, fstop=2.8, ease=ease_out_cubic, focus=dist - 0.33)
    return state


def aroma():
    """aroma：容器开口飘出金色香气卷须，角色闻到，闭眼脸红冒爱心。卷须从开口长出来，再从根部散掉。"""
    cam, _ = L.stage_base()
    box = container("box", loc=(0.35, 0.55, 0))
    hero = critter("c1", "hero")
    hole = box.hole_world()
    sw = [L.swirl(f"sw{i}", (hole.x - 0.06 + 0.06 * i, hole.y - 0.08, hole.z), h=0.55 + 0.1 * i, amp=0.12,
                  turns=1.3 + 0.2 * i, color=["#f3b24a", "#ee8f3a", "#f6cf7a"][i], phase=i * 1.7) for i in range(3)]
    for s_ in sw:
        s_.data.bevel_depth = 0.022
    heart_m = L.mat_basic("heart", "#e46f6f", rough=0.4, emit="#e46f6f", emit_strength=0.8)
    hearts = [L.heart(f"h{i}", s=0.05, mat=heart_m) for i in range(3)]

    def state(t, ev):
        k1, k2 = evt(ev, "kw:<香味1>", 1.0), evt(ev, "kw:<香味2>", 1.6)
        for i, s in enumerate(sw):
            s.data.bevel_factor_end = smoothstep(0.2 * i, k2 + 0.3 * i, t)
            s.data.bevel_factor_start = smoothstep(k2 + 0.8 + 0.2 * i, k2 + 2.2 + 0.2 * i, t) * 0.7
        sniff = smoothstep(k1 - 0.3, k1 + 0.2, t)
        hero.pose(loc=(-0.42, -0.6, 0), heading=math.radians(50), head=(-0.25 * sniff, 0, 0.45),
                  arm_l=(-1.0 * sniff, 0, -0.3), arm_r=(-1.0 * sniff, 0, 0.3), lean=-0.1 * sniff,
                  hop=0.01 * math.sin(t * 6))
        hero.set_eyes("happy" if sniff > 0.5 else "open")
        hero.set_blush(sniff)
        for i, h in enumerate(hearts):
            u = ((t - k2) * 0.6 + i / 3) % 1.0
            h.location = (-0.45 + 0.12 * (i - 1) + 0.04 * math.sin(t * 3 + i), -0.6, 0.95 + 0.6 * u)
            L.hide(h, smoothstep(k2, k2 + 0.2, t) * (1 - smoothstep(0.8, 1.0, u)))
        L.aim_camera(cam, (-0.2, -4.1, 1.05), (-0.05, 0, 0.95), lens=45, fstop=2.8)
    return state


def time_lapse():
    """time_lapse（「随着时间流逝」）：叶子飘落、颜色褪掉、光从暖变冷，1–1.5 秒的快速延时（配越走越快的钟声）。"""
    cam, lights = L.stage_base()
    box = container("box", loc=(0, 0.5, 0))
    random.seed(19)
    leaf_m = L.mat_basic("leafm", L.PAL["leaf_autumn"], rough=0.9)
    leaves = [L.ellipsoid(f"lf{i}", 0.05, 0.012, 0.035, mats=[leaf_m]) for i in range(16)]
    lp = [(random.uniform(-1, 1), random.uniform(-0.8, 0), random.uniform(2.0, 3.0), random.random()) for _ in leaves]
    warm, cold = L.col(L.PAL["leaf_autumn"]), L.col("#b9b6a8")
    far = CONTAINER == "tree"

    def state(t, ev):
        u = smoothstep(0, 1.25, t)
        if getattr(box, "canopy", None):
            c = L.mix_col(warm, cold, u)
            L.set_fur_color(box.m_leaf_fur, c, root=0.7, tip=1.1)
            L.set_mat_color(box.m_leaf, L.scale_col(c, 0.75))
            for b in box.canopy:
                b.scale = (1 - 0.15 * u,) * 3
        for (x, y, z, ph), lf in zip(lp, leaves):
            fall = (t * 1.1 + ph) % 1.0
            lf.location = (x + 0.2 * math.sin(fall * 6), y, z - 2.0 * fall)
            lf.rotation_euler = (fall * 6, fall * 4, 0)
            L.hide(lf, 1 if u < 0.95 else 0)
        lights["key"].data.energy = lerp(1200, 800, u)
        lights["key"].data.color = L.mix_col(L.col("#fff3e3"), L.col("#e6eef7"), u)[:3]
        d, z = (7.6, 1.8) if far else (4.8, 0.9)
        L.aim_camera(cam, (0, -d, z + 0.3), (0, 0, z), lens=36, fstop=4)
    return state


def mode_switch():
    """mode_switch（「切换成……模式」）：微观角色面前的拨杆开关「啪」地从左灯拨到右灯（两个状态两种颜色，标签挂在灯上）。"""
    cam, _ = L.stage_base(mountains_on=False)
    hero = L.FluffAgent("hero", r=0.16, seed=5)
    sw = L.toggle_switch("sw", (0.0, -0.55, 0.0))
    gone = [L.molecule(f"used{i}", "o2", scale=0.9) for i in range(3)]   # 先被用完、消失的东西

    def state(t, ev):
        k1, k2 = evt(ev, "kw:<用完>", 0.5), evt(ev, "kw:<新模式>", 1.2)
        for i, mo in enumerate(gone):
            mo.location = (-0.45 + 0.45 * i, -0.15, (0.6, 0.74, 0.62)[i] + 0.03 * math.sin(t * 3 + i))
            L.hide(mo, 1 - smoothstep(k1 + 0.1 * i, k1 + 0.25 + 0.1 * i, t))
        flip = ease_out_back(smoothstep(k2 - 0.1, k2 + 0.15, t))
        sw["piv"].rotation_euler = (0, lerp(-0.6, 0.6, flip), 0)
        L.set_mat_color(sw["mL"], L.col("#7fb3e0"), emit_strength=3.0 * (1 - flip))
        L.set_mat_color(sw["mR"], L.col("#f0a43a"), emit_strength=3.0 * flip)
        hero.root.location = (0, -0.05, 0.42 + 0.03 * math.sin(t * 4))
        hero.root.rotation_euler = (0, 0, 0.25 * math.sin(t * 2.5))
        for e in hero.eyes:
            e.scale = (1, 1, 0.1 if abs(t - k2) < 0.06 else 1)
        L.aim_camera(cam, (0.0, -2.6, 0.75), (0, -0.3, 0.42), lens=45, fstop=2.8)
    return state


def molecule_split():
    """molecule_split（「把 A 分解成 B 和 C」）：微观角色跳起来咬一口，双环分子玩具断成两半（标签挂 link / partL / partR）。"""
    cam, _ = L.stage_base(mountains_on=False)
    left, right = L.molecule("partL", "glucose"), L.molecule("partR", "fructose")
    link = L.ellipsoid("link", 0.07, mats=[L.mat_basic("lnk", "#e0675a", rough=0.25, coat=0.6)])
    biter = L.FluffAgent("biter", r=0.12, seed=3)
    sps = sparkles(4, s=0.06)

    def state(t, ev):
        k = evt(ev, "kw:<产物1>", 1.05) - 0.25   # 说到第一个产物前 0.25 s 咬断
        u = ease_out_back(smoothstep(k, k + 0.45, t))
        left.location = (-0.28 - 0.13 * u, -0.2, 0.75 + 0.06 * math.sin(t * 2))
        right.location = (0.27 + 0.13 * u, -0.2, 0.75 + 0.06 * math.sin(t * 2 + 1))
        link.location = (0.0, -0.2, 0.68)
        L.hide(link, 1 - smoothstep(k, k + 0.15, t))
        bite = smoothstep(k - 0.5, k, t) * (1 - smoothstep(k + 0.1, k + 0.5, t))
        biter.root.location = (0, -0.35, 0.35 + 0.25 * bite)
        biter.root.scale = (1 + 0.15 * bite, 1 + 0.15 * bite, 1 - 0.1 * bite)
        burst(sps, (0, 0, 0.75), t, k, spread=0.25, y=-0.3)
        L.aim_camera(cam, (0.0, -3.9, 0.85), (0, 0, 0.66), lens=45, fstop=4)
    return state


def molecule_merge():
    """molecule_merge（「A 和 B 结合成 C」）：两个分子从两边升起、靠拢，闪光一下合成一个新分子（标签挂 molA / molB / molC）。"""
    cam, _ = L.stage_base(mountains_on=False)
    a = L.molecule("molA", "ethanol", scale=1.4)
    b = L.molecule("molB", "acid", scale=1.4, tint="#6f7d55")
    c = L.molecule("molC", "ester", scale=1.3, tint="#b0764a")
    sps = sparkles(5, s=0.07)

    def state(t, ev):
        k1, k2 = evt(ev, "kw:<B>", 1.3), evt(ev, "kw:<结合>", 2.6)
        rise_a = ease_out_back(smoothstep(0.0, 0.6, t))
        rise_b = ease_out_back(smoothstep(k1 - 0.3, k1 + 0.2, t))
        u = ease_in_out(smoothstep(k2 - 0.7, k2, t))
        a.location = (lerp(-0.42, -0.14, u), -0.25, lerp(0.15, 0.75, rise_a) + 0.04 * math.sin(t * 2))
        b.location = (lerp(0.42, 0.18, u), -0.25, lerp(0.2, 0.75, rise_b) + 0.04 * math.sin(t * 2 + 1))
        merge = smoothstep(k2, k2 + 0.25, t)
        L.hide(a, (1 - merge) * smoothstep(0.0, 0.25, t))
        L.hide(b, (1 - merge) * smoothstep(k1 - 0.3, k1 - 0.05, t))
        c.location = (0.03, -0.25, 0.75)
        c.rotation_euler = (0, 0.15 * math.sin(t * 2), 0)
        L.hide(c, ease_out_back(smoothstep(k2 + 0.05, k2 + 0.4, t)))
        burst(sps, (0.03, 0, 0.75), t, k2, spread=0.35, y=-0.4)
        L.aim_camera(cam, (0.0, -3.5, 0.85), (0, -0.2, 0.72), lens=45, fstop=4)
    return state


def level_compare():
    """level_compare（「A 越来越少，B 持续上升」）：两根量筒一降一升，箭头在说到词时弹出，左右颜色分开。"""
    cam, _ = L.stage_base(mountains_on=False)
    ta = L.glass_tube("tubeA", r=0.16, h=0.95, liquid="#f4efe4", loc=(-0.3, -0.2, 0))
    tb = L.glass_tube("tubeB", r=0.16, h=0.95, liquid="#e09a3a", loc=(0.3, -0.2, 0))
    down = L.arrow("down", length=0.36, r=0.03, color="#5b8fd1", up=False, loc=(-0.53, -0.3, 0.78))
    up = L.arrow("up", length=0.36, r=0.03, color="#d9573f", up=True, loc=(0.53, -0.3, 0.42))

    def state(t, ev):
        k1, k2 = evt(ev, "kw:<减少>", 0.7), evt(ev, "kw:<上升>", 2.3)
        ta["liquid"].scale = (1, 1, (0.85 - 0.7 * ease_in_out(smoothstep(k1 - 0.6, k2 + 0.6, t))) * ta["h"])
        tb["liquid"].scale = (1, 1, (0.1 + 0.72 * ease_in_out(smoothstep(k1 - 0.3, k2 + 0.8, t))) * tb["h"])
        L.hide(down, ease_out_back(smoothstep(k1 - 0.1, k1 + 0.25, t)))
        L.hide(up, ease_out_back(smoothstep(k2 - 0.1, k2 + 0.25, t)))
        down.location = (-0.53, -0.3, 0.78 - 0.04 * math.sin(t * 6))
        up.location = (0.53, -0.3, 0.42 + 0.04 * math.sin(t * 6))
        L.aim_camera(cam, (0.0, -3.4, 0.75), (0, -0.2, 0.62), lens=42, fstop=4)
    return state


def plug():
    """plug（「堵住、封死」）：一团软泥从开口挤进来塞满，里面剩下的气体分子一个个消失。"""
    cam, box, obs, liq = cut_base(level=0.62, color=LIQ["done"])
    pos, inward = box.opening()
    mud = L.mat_textured("plug", "#a8602c", "#c47a3c", rough=0.5, scale=12, bump=0.3, sss=0.2)
    inner = L.blob("plug", 0.2, 0.28, 0.2, amp=0.25, freq=4, seed=5, mats=[mud])
    outer = L.blob("plug2", 0.24, 0.3, 0.14, amp=0.3, freq=3, seed=8, mats=[mud])
    gas = [L.molecule(f"gas{i}", "o2", scale=0.75) for i in range(3)]
    for o in [inner, outer] + gas:
        o.parent = box.root
    top = liq.level_z(0.62)

    def state(t, ev):
        L.pile_state(obs, squash=0.55)
        k = evt(ev, "kw:<堵住>", 1.27)
        u = ease_out_back(smoothstep(0.1, k + 0.1, t))
        inner.location = pos + inward * 0.12
        inner.scale = (u, u, u)
        outer.location = pos - inward * 0.02 + Vector((0, -0.05, 0))
        L.hide(outer, smoothstep(k - 0.3, k + 0.2, t))
        for i, mo in enumerate(gas):
            mo.location = (-0.2 + 0.18 * i, 0.12, top + 0.1 + 0.03 * math.sin(t * 3 + i))
            L.hide(mo, 1 - smoothstep(k + 0.2 + 0.1 * i, k + 0.5 + 0.1 * i, t))
        L.aim_camera(cam, (-0.3, -3.6, 1.0), (-0.15, 0.3, 0.92), lens=45, fstop=4)
    return state


def lack_badge():
    """lack_badge（「缺少 X」）：剖面整体变暗，一个红圈禁止徽章弹出，中间是缺的那样东西（这里用分子）。"""
    cam, box, obs, liq = cut_base(level=0.62, color=LIQ["done"])
    z = box.hole_z + 0.3
    badge = L.no_sign("no", (0.02, -0.3, z), r=0.17)
    thing = L.molecule("lack", "o2", scale=1.0)

    def state(t, ev):
        L.pile_state(obs, squash=0.55)
        k = evt(ev, "kw:<缺少>", 1.19)
        u = ease_out_back(smoothstep(k - 0.15, k + 0.3, t))
        L.hide(badge, u)
        thing.location = (0.02, -0.28, z)
        L.hide(thing, u)
        liq.set_color(L.mix_col(L.col(LIQ["done"]), L.scale_col(L.col(LIQ["done"]), 0.8), smoothstep(0, k, t)),
                      emit=0.6 - 0.25 * u)
        L.aim_camera(cam, (0.0, -3.9, 1.1), (0, 0.3, 1.0), lens=45, fstop=4)
    return state


def die_off():
    """die_off（「停止、死亡」）：微观角色一个个变灰、X 眼、倒下沉底，气泡慢慢停，停止牌弹出。"""
    cam, box, obs, liq = cut_base(level=0.62, color=LIQ["done"])
    top, bottom = liq.level_z(0.62), liq.level_z(0.12)
    agents = [L.FluffAgent(f"a{i}", r=0.065, seed=30 + i) for i in range(5)]
    bub_m = L.mat_basic("bub", "#ffffff", rough=0.05, spec=0.9, alpha=0.45, emit="#ffffff", emit_strength=0.3)
    bubs = [L.ellipsoid(f"bub{i}", 0.02 + 0.01 * (i % 3), mats=[bub_m], segs=16, rings=8) for i in range(12)]
    for o in [a.root for a in agents] + bubs:
        o.parent = box.root
    stop = L.empty("stop", loc=(0.0, -0.3, box.hole_z + 0.2))
    L.cone("stopoct", 0.16, 0.16, 0.03, segs=8, parent=stop, rot=(math.radians(90), 0, math.radians(22.5)),
           mats=[L.mat_basic("stopm", "#d33b2f", rough=0.4, emit="#d33b2f", emit_strength=0.6)])
    L.box("stopbar", 0.18, 0.04, 0.045, parent=stop, loc=(0, -0.02, 0), mats=[L.mat_basic("sbw", "#f6f2ea")])
    M = agents[0].M
    alive_fur, alive_base = L.col("#f3efe6"), L.col("#e8e2d6")

    def state(t, ev):
        L.pile_state(obs, squash=0.55)
        k1, k2 = evt(ev, "kw:<死掉>", 1.12), evt(ev, "kw:<停止>", 2.16)
        dead = smoothstep(k1 - 0.1, k1 + 0.4, t)
        L.set_fur_color(M["fur"], L.mix_col(alive_fur, L.col("#8f8a82"), dead), root=0.8, tip=1.05)
        L.set_mat_color(M["base"], L.mix_col(alive_base, L.col("#7d7871"), dead))
        for i, a in enumerate(agents):
            fall = ease_out_back(smoothstep(k1 + 0.05 * i, k1 + 0.35 + 0.05 * i, t))
            a.root.location = (-0.3 + 0.15 * i, 0.0, lerp(top - 0.12, bottom + 0.06 * (i % 2), fall))
            a.root.rotation_euler = (0, fall * (1.2 if i % 2 else -1.2), 0)
            a.set_dead(fall)
        for i, b in enumerate(bubs):
            u = (t * 0.8 + i / 12) % 1.0
            b.location = (-0.28 + 0.05 * i, -0.02, top - 0.3 + 0.7 * u)
            L.hide(b, (1 - smoothstep(k1, k2, t)) * (1 - smoothstep(0.85, 1.0, u)))
        L.hide(stop, ease_out_back(smoothstep(k2 - 0.1, k2 + 0.25, t)))
        L.aim_camera(cam, (0.0, -3.2, 1.05), (0, 0.3, 0.98), lens=45, fstop=4)
    return state


# ---- 原型表与本期镜头映射

ARCHETYPES = dict(trot_in=trot_in, peek=peek, discover=discover, motive_gather=motive_gather, motive_need=motive_need,
                  cutaway_fill=cutaway_fill, cutaway_rise=cutaway_rise, condition=condition, analogy=analogy,
                  split=split, meter=meter, reveal=reveal, warning=warning, stop_sign=stop_sign,
                  macro_reveal=macro_reveal, aroma=aroma, time_lapse=time_lapse, mode_switch=mode_switch,
                  molecule_split=molecule_split, molecule_merge=molecule_merge, level_compare=level_compare,
                  plug=plug, lack_badge=lack_badge, die_off=die_off)

# 本期镜头 id → 原型（和 episode.SHOT_STARTS 一一对应）
SHOTS = dict(sh01=trot_in, sh02=peek, sh03=discover, sh04=motive_gather, sh05=motive_need, sh06=cutaway_fill,
             sh07=cutaway_rise, sh08=condition, sh09=analogy, sh10=split, sh11=meter, sh12=reveal, sh13=warning,
             sh14=stop_sign)

# 竖屏安全区：顶部 200–370 px 是标题带，1320–1490 px 是字幕带。负值把画面内容往上推（镜头平移，不改透视），
# 让主体落在两条带之间。先出预览 + qa.py safe 看，哪个镜头压带就在这里加，常用 −0.04～−0.10。
SHIFT_Y = dict(sh01=-0.05, sh03=-0.10, sh04=-0.06, sh05=-0.08, sh06=-0.05, sh07=-0.05, sh08=-0.05, sh09=-0.06,
               sh11=-0.04, sh12=-0.07, sh14=-0.05)
