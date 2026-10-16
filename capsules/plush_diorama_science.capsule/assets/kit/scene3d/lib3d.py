"""毛绒手办微缩布景的程序化资产库（Blender 5.2，bpy，EEVEE + 粒子毛发）。

坐标：x 向右，y 远离镜头（纵深），z 向上；镜头在 -y 方向看 +y。台面顶面 z=0。
所有网格按真实尺寸建（物体 scale 保持 1），毛发长度即世界单位。
动画不用关键帧：每帧由 shot 的 state(t, ev) 直接设置变换和材质参数。

分区：颜色/材质 → 网格 → 布景灯光相机 → 角色（PlushCritter）→ 主容器（HollowTree、CutawayJar）
→ 小物件与微观角色（FruitBank、FluffAgent、SpikyAgent、molecule）→ 隐喻道具 → 缓动 → 镜头小工具。
主容器协议：有 root、cav=(rx, ry, rz)、cav_z、hole_z、opening()、hole_world()，CutLiquid / drop_pile 只认这几个。
"""
import math
import random

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector, noise


# ---------------------------------------------------------------- 颜色与基础

def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def col(h, a=1.0):
    h = h.lstrip("#")
    return tuple(_lin(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)) + (a,)


def scale_col(c, k):
    return tuple(min(1.0, x * k) for x in c[:3]) + (1.0,)


def mix_col(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3)) + (1.0,)


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    FluffAgent._mats = {}       # 材质缓存随场景重置失效
    SpikyAgent._mats = None
    return bpy.context.scene


def link(ob, coll=None):
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob


def empty(name, loc=(0, 0, 0), parent=None, coll=None):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_size = 0.1
    link(ob, coll)
    ob.parent = parent
    ob.location = loc
    return ob


# ---------------------------------------------------------------- 材质

def new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    return m, nt, nt.nodes["Principled BSDF"]


def mat_basic(name, color, rough=0.6, spec=0.3, sss=0.0, sheen=0.0, coat=0.0,
              emit=None, emit_strength=0.0, alpha=None, metallic=0.0):
    m, nt, p = new_mat(name)
    p.inputs["Base Color"].default_value = col(color) if isinstance(color, str) else color
    p.inputs["Roughness"].default_value = rough
    p.inputs["Specular IOR Level"].default_value = spec
    p.inputs["Metallic"].default_value = metallic
    if sss:
        p.inputs["Subsurface Weight"].default_value = sss
        p.inputs["Subsurface Radius"].default_value = (1.0, 0.45, 0.25)
        p.inputs["Subsurface Scale"].default_value = 0.03
    if sheen:
        p.inputs["Sheen Weight"].default_value = sheen
        p.inputs["Sheen Roughness"].default_value = 0.5
    if coat:
        p.inputs["Coat Weight"].default_value = coat
        p.inputs["Coat Roughness"].default_value = 0.05
    if emit:
        p.inputs["Emission Color"].default_value = col(emit) if isinstance(emit, str) else emit
        p.inputs["Emission Strength"].default_value = emit_strength
    if alpha is not None:
        p.inputs["Alpha"].default_value = alpha
        m.surface_render_method = "BLENDED"
    return m


def _noise_ramp(nt, c1, c2, scale=5.0, detail=6.0, roughness=0.55, stretch=(1, 1, 1),
                coords="Object", pos=(0.35, 0.65), kind="NOISE"):
    """返回 (ramp 节点, 纹理 fac 输出)，纹理坐标可拉伸。"""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = stretch
    nt.links.new(tc.outputs[coords], mp.inputs["Vector"])
    if kind == "NOISE":
        tx = nt.nodes.new("ShaderNodeTexNoise")
        tx.inputs["Scale"].default_value = scale
        tx.inputs["Detail"].default_value = detail
        tx.inputs["Roughness"].default_value = roughness
        fac = tx.outputs["Fac"]
    else:  # WAVE 条纹
        tx = nt.nodes.new("ShaderNodeTexWave")
        tx.wave_type = kind  # 'BANDS' / 'RINGS'
        tx.inputs["Scale"].default_value = scale
        tx.inputs["Distortion"].default_value = 6.0
        tx.inputs["Detail"].default_value = detail
        tx.inputs["Detail Scale"].default_value = 1.5
        fac = tx.outputs["Fac"]
    nt.links.new(mp.outputs["Vector"], tx.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = pos[0]
    ramp.color_ramp.elements[1].position = pos[1]
    ramp.color_ramp.elements[0].color = c1
    ramp.color_ramp.elements[1].color = c2
    nt.links.new(fac, ramp.inputs["Fac"])
    return ramp, fac


def _bump(nt, p, fac, strength=0.2, distance=0.02):
    b = nt.nodes.new("ShaderNodeBump")
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = distance
    nt.links.new(fac, b.inputs["Height"])
    nt.links.new(b.outputs["Normal"], p.inputs["Normal"])


def mat_textured(name, c1, c2, rough=0.7, scale=5.0, bump=0.1, stretch=(1, 1, 1), kind="NOISE",
                 pos=(0.35, 0.65), detail=6.0, sss=0.0, sheen=0.0, spec=0.3):
    m, nt, p = new_mat(name)
    ramp, fac = _noise_ramp(nt, col(c1) if isinstance(c1, str) else c1, col(c2) if isinstance(c2, str) else c2,
                            scale=scale, stretch=stretch, kind=kind, pos=pos, detail=detail)
    nt.links.new(ramp.outputs["Color"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = rough
    p.inputs["Specular IOR Level"].default_value = spec
    if sss:
        p.inputs["Subsurface Weight"].default_value = sss
        p.inputs["Subsurface Scale"].default_value = 0.03
    if sheen:
        p.inputs["Sheen Weight"].default_value = sheen
    if bump:
        _bump(nt, p, fac, strength=bump)
    return m


def mat_fur(name, color, root=0.62, tip=1.06, rough=0.55):
    m, nt, p = new_mat(name)
    c = col(color) if isinstance(color, str) else color
    hi = nt.nodes.new("ShaderNodeHairInfo")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = scale_col(c, root)
    ramp.color_ramp.elements[1].color = scale_col(c, tip)
    nt.links.new(hi.outputs["Intercept"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = rough
    p.inputs["Specular IOR Level"].default_value = 0.25
    return m


def mat_liquid(name, color, emit_strength=0.6, alpha=None, rough=0.12):
    m = mat_basic(name, color, rough=rough, spec=0.6, emit=color, emit_strength=emit_strength, alpha=alpha)
    return m


def set_mat_color(m, color, emit_strength=None):
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = color
    if emit_strength is not None:
        p.inputs["Emission Color"].default_value = color
        p.inputs["Emission Strength"].default_value = emit_strength


def set_mat_alpha(m, a):
    m.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = a


# ---------------------------------------------------------------- 网格

def mesh_obj(name, build, mat=None, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, smooth=True, coll=None,
             mats=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    build(bm)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        me.shade_smooth()
    ob = link(bpy.data.objects.new(name, me), coll)
    for mm in (mats or ([mat] if mat else [])):
        me.materials.append(mm)
    ob.parent = parent
    ob.location = loc
    ob.rotation_euler = rot
    return ob


def ellipsoid(name, rx, ry=None, rz=None, segs=40, rings=20, **kw):
    ry = rx if ry is None else ry
    rz = rx if rz is None else rz

    def b(bm):
        bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=1.0)
        bmesh.ops.scale(bm, vec=(rx, ry, rz), verts=bm.verts)
    return mesh_obj(name, b, **kw)


def cone(name, r1, r2, depth, segs=48, cap=True, **kw):
    def b(bm):
        bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segs, radius1=r1, radius2=r2,
                              depth=depth)
    return mesh_obj(name, b, **kw)


def box(name, sx, sy, sz, **kw):
    def b(bm):
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    kw.setdefault("smooth", False)
    return mesh_obj(name, b, **kw)


def torus(name, R, r, segs=48, rsegs=16, **kw):
    def b(bm):
        rows = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            row = []
            for j in range(rsegs):
                c = 2 * math.pi * j / rsegs
                x = (R + r * math.cos(c)) * math.cos(a)
                y = (R + r * math.cos(c)) * math.sin(a)
                z = r * math.sin(c)
                row.append(bm.verts.new((x, y, z)))
            rows.append(row)
        for i in range(segs):
            for j in range(rsegs):
                a, b2 = rows[i], rows[(i + 1) % segs]
                bm.faces.new((a[j], b2[j], b2[(j + 1) % rsegs], a[(j + 1) % rsegs]))
    return mesh_obj(name, b, **kw)


def plane_xz(name, w, h, **kw):
    """立在 XZ 平面、法线朝 -y（朝镜头）的平面。"""
    def b(bm):
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
        bmesh.ops.scale(bm, vec=(w, h, 1), verts=bm.verts)
        bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, "X"), verts=bm.verts)
    kw.setdefault("smooth", False)
    return mesh_obj(name, b, **kw)


def curve_obj(name, pts, bevel=0.01, mat=None, parent=None, loc=(0, 0, 0), taper=None, coll=None,
              closed=False, res=12, kind="NURBS"):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = bevel
    cu.bevel_resolution = 4
    cu.use_fill_caps = True
    cu.resolution_u = res
    sp = cu.splines.new(kind)
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        w = 1.0
        if taper is not None:
            w = 1.0
        sp.points[i].co = (p[0], p[1], p[2], w)
        if taper is not None:
            sp.points[i].radius = taper[i]
    sp.use_endpoint_u = True
    sp.use_cyclic_u = closed
    sp.order_u = min(4, len(pts))
    ob = link(bpy.data.objects.new(name, cu), coll)
    if mat:
        cu.materials.append(mat)
    ob.parent = parent
    ob.location = loc
    return ob


def bake_mesh(ob, name=None):
    """把修改器结果固化成新网格（布尔、倒角），删除原物体。"""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    new = link(bpy.data.objects.new(name or ob.name + "_baked", me),
               ob.users_collection[0] if ob.users_collection else None)
    new.matrix_world = ob.matrix_world.copy()
    bpy.data.objects.remove(ob, do_unlink=True)
    return new


def boolean(ob, cutter, op="DIFFERENCE"):
    md = ob.modifiers.new("bool_" + cutter.name, "BOOLEAN")
    md.operation = op
    md.solver = "MANIFOLD"   # EXACT 在「空腔+洞口+剖半」连续布尔时会返回空网格
    md.object = cutter
    md.material_mode = "TRANSFER"
    cutter.hide_render = True
    return md


def vgroup_by(ob, name, fn):
    vg = ob.vertex_groups.new(name=name)
    for v in ob.data.vertices:
        vg.add([v.index], max(0.0, min(1.0, fn(v.co))), "REPLACE")
    return vg


def add_fur(ob, fur_mat, length=0.05, count=1500, children=10, root=0.35, tip=0.0,
            rough1=0.02, rough2=0.06, rough_end=0.02, clump=0.15, seed=0, vgroup=None, steps=4,
            comb=0.0, kink=0.0, radius_scale=0.006):
    if fur_mat.name not in [m.name for m in ob.data.materials]:
        ob.data.materials.append(fur_mat)
    slot = [m.name for m in ob.data.materials].index(fur_mat.name) + 1
    ob.modifiers.new("fur", "PARTICLE_SYSTEM")
    psys = ob.particle_systems[-1]
    psys.seed = seed
    ps = psys.settings
    ps.type = "HAIR"
    ps.use_advanced_hair = True
    ps.count = count
    ps.hair_length = length
    ps.emit_from = "FACE"
    ps.use_even_distribution = True
    ps.child_type = "INTERPOLATED" if children else "NONE"
    ps.rendered_child_count = children
    ps.child_percent = max(1, children // 4)
    ps.clump_factor = clump
    ps.roughness_1 = rough1
    ps.roughness_2 = rough2
    ps.roughness_endpoint = rough_end
    ps.root_radius = root
    ps.tip_radius = tip
    ps.radius_scale = radius_scale
    ps.use_close_tip = True
    if comb:   # 毛向下梳：沿物体 -z 的附加速度（与法向速度 1.0 同一量纲）
        ps.object_align_factor = (0.0, 0.0, -comb)
    if kink and children:
        ps.kink = "WAVE"
        ps.kink_amplitude = kink
        ps.kink_frequency = 2.0
        ps.kink_shape = 0.0
    ps.render_step = steps
    ps.display_step = 2
    ps.material = slot
    if vgroup:
        psys.vertex_group_density = vgroup
        psys.vertex_group_length = vgroup
    return psys


# ---------------------------------------------------------------- 布景

PAL = dict(
    wall="#8b9585", wall_hi="#a6ad9f", ledge="#efebe1", ledge_dark="#d9d3c5",
    straw="#c9b48a", straw_dark="#9c8559", bark="#7d6c5b", bark_dark="#584b40", cutwood="#e2cfa8",
    cavity="#3d3029", leaf="#8a9567", leaf_autumn="#c98d52", orange="#d9774b", blue="#8faac8",
    cream="#efe6d4", sage="#9fb08f",
)


def build_stage(ledge_front=-1.8, ledge_back=3.2, ledge_h=4.0, width=40.0, wall_y=3.2):
    wall = plane_xz("wall", width, 24, loc=(0, wall_y, 6.0),
                    mat=mat_textured("m_wall", "#86907f", "#949d8d", rough=0.95, scale=1.6, bump=0.03,
                                     stretch=(1, 1, 1), spec=0.1))
    ledge = box("ledge", width, ledge_back - ledge_front, ledge_h,
                loc=(0, (ledge_front + ledge_back) / 2, -ledge_h / 2),
                mat=mat_textured("m_ledge", "#ece7dc", "#f2eee5", rough=0.75, scale=6.0, bump=0.02, spec=0.25))
    bev = ledge.modifiers.new("bev", "BEVEL")
    bev.width = 0.04
    bev.segments = 4
    return wall, ledge


def build_lights(key=1200.0, fill=350.0, rim=500.0, world="#9aa494", world_strength=0.55):
    def area(name, loc, target, energy, size, color="#fff6ea"):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy
        ld.size = size
        ld.color = col(color)[:3]
        ob = link(bpy.data.objects.new(name, ld))
        ob.location = loc
        d = Vector(target) - Vector(loc)
        ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        return ob
    lights = dict(
        key=area("key", (-5, -6, 8), (0, 0, 0.8), key, 7.0, "#fff3e3"),
        fill=area("fill", (6, -5, 3.5), (0, 0, 1.0), fill, 7.0, "#eef3f6"),
        rim=area("rim", (1.5, 2.6, 7.5), (0, 0, 1.0), rim, 4.0, "#fffaf0"),
    )
    w = bpy.data.worlds.new("world")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = col(world)
    bg.inputs[1].default_value = world_strength
    bpy.context.scene.world = w
    return lights


def make_camera(lens=50.0):
    cd = bpy.data.cameras.new("cam")
    cd.lens = lens
    cd.sensor_fit = "AUTO"
    cd.sensor_width = 36.0
    cd.clip_start = 0.05
    cd.clip_end = 300
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = 4.0
    cam = link(bpy.data.objects.new("cam", cd))
    bpy.context.scene.camera = cam
    return cam


def aim_camera(cam, loc, target, lens=None, fstop=None, roll=0.0, focus=None):
    cam.location = loc
    d = Vector(target) - Vector(loc)
    q = d.to_track_quat("-Z", "Y")
    if roll:
        q = q @ Euler((0, 0, roll)).to_quaternion()
    cam.rotation_euler = q.to_euler()
    if lens:
        cam.data.lens = lens
    if fstop:
        cam.data.dof.aperture_fstop = fstop
    cam.data.dof.focus_distance = focus if focus else d.length


def setup_render(res=(1080, 1920), samples=32, fps=30, motion_blur=False):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.fps = fps
    ee = sc.eevee
    ee.taa_render_samples = samples
    ee.use_raytracing = True
    ee.ray_tracing_method = "SCREEN"
    ee.use_fast_gi = True
    ee.fast_gi_method = "GLOBAL_ILLUMINATION"
    ee.use_shadows = True
    ee.shadow_ray_count = 2
    ee.shadow_step_count = 6
    sc.render.hair_type = "STRIP"
    sc.render.hair_subdiv = 1
    sc.render.film_transparent = False
    sc.render.filter_size = 1.2
    sc.view_settings.view_transform = "AgX"
    for look in ("AgX - Medium Low Contrast", "Medium Low Contrast"):
        try:
            sc.view_settings.look = look
            break
        except TypeError:
            pass
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 94
    sc.render.use_motion_blur = motion_blur
    if motion_blur:
        sc.render.motion_blur_shutter = 0.4
        ee.motion_blur_steps = 1
    sc.render.use_persistent_data = True
    return sc


# ---------------------------------------------------------------- 角色：毛绒小动物

class PlushCritter:
    """毛绒小动物手办：大头、豆豆眼带高光、腮红、浅色脸盘、短手短脚。所有可动部位是 empty pivot。
    物种靠 ears / tail / 毛色区分：ears = side（圆耳在两侧，猴、熊猫）/ top（圆耳在头顶，熊、鼠）/
    pointy（尖耳，猫、狐）/ tall（长耳，兔）；tail = curl（卷尾）/ pom（绒球短尾）/ none。
    身份靠配饰：hat=True 斗笠，scarf=颜色 围巾。主角固定一套毛色 + 配饰，全片不换。"""

    def __init__(self, name, fur="#b48a62", face="#efc6a4", hat=False, scarf=None, seed=0, s=1.0,
                 fur_scale=1.0, ears="side", tail="curl"):
        self.name = name
        self.s = s
        k = s
        self.root = empty(name + "_root")
        self.root.scale = (s, s, s)
        self.bob = empty(name + "_bob", parent=self.root)
        furc = col(fur)
        self.m_fur = mat_fur(name + "_fur", furc)
        self.m_base = mat_basic(name + "_base", scale_col(furc, 0.7), rough=0.85)
        self.m_skin = mat_basic(name + "_skin", face, rough=0.45, sss=0.25, spec=0.35)
        self.m_eye = mat_basic(name + "_eye", "#120e0c", rough=0.05, spec=0.8, coat=1.0)
        self.m_dark = mat_basic(name + "_dark", "#4a2e24", rough=0.6)
        self.m_hi = mat_basic(name + "_hi", "#ffffff", rough=0.3, emit="#ffffff", emit_strength=3.0)
        self.m_blush = mat_basic(name + "_blush", "#e7958f", rough=0.6, emit="#e7958f", emit_strength=0.25)
        fs = fur_scale

        # 身体
        self.body = ellipsoid(name + "_body", 0.19, 0.17, 0.21, loc=(0, 0, 0.36), parent=self.bob,
                              mats=[self.m_base])
        add_fur(self.body, self.m_fur, length=0.05 * fs, count=1600, seed=seed + 1)
        # 头
        self.head = empty(name + "_headpiv", loc=(0, 0, 0.52), parent=self.bob)
        hd = ellipsoid(name + "_head", 0.24, 0.23, 0.225, loc=(0, 0, 0.2), parent=self.head, mats=[self.m_base])
        fdir = Vector((0, -1, -0.15)).normalized()

        def furw(co):
            d = co.normalized()
            a = d.dot(fdir)
            return 1.0 - max(0.0, min(1.0, (a - 0.55) / 0.15))
        vg = vgroup_by(hd, "fur", furw)
        add_fur(hd, self.m_fur, length=0.055 * fs, count=2200, seed=seed + 2, vgroup=vg.name)
        # 脸
        ellipsoid(name + "_face", 0.165, 0.085, 0.115, loc=(0, -0.172, 0.235), parent=self.head,
                  mats=[self.m_skin])
        ellipsoid(name + "_muzzle", 0.11, 0.08, 0.085, loc=(0, -0.198, 0.135), parent=self.head,
                  mats=[self.m_skin])
        self.eyes = []
        for sx in (-1, 1):
            e = ellipsoid(f"{name}_eye{sx}", 0.042, 0.03, 0.05, loc=(sx * 0.07, -0.252, 0.25), parent=self.head,
                          mats=[self.m_eye], segs=24, rings=12)
            ellipsoid(f"{name}_eyehi{sx}", 0.012, 0.008, 0.012, loc=(-0.013, -0.026, 0.02), parent=e,
                      mats=[self.m_hi], segs=12, rings=6)
            self.eyes.append(e)
        for sx in (-1, 1):
            ellipsoid(f"{name}_nost{sx}", 0.009, 0.006, 0.006, loc=(sx * 0.018, -0.276, 0.155), parent=self.head,
                      mats=[self.m_dark], segs=12, rings=6)
        self.mouth = curve_obj(name + "_mouth", [(-0.035, -0.272, 0.118), (0, -0.281, 0.1),
                                                (0.035, -0.272, 0.118)],
                               bevel=0.0065, mat=self.m_dark, parent=self.head)
        self.cheeks = []
        for sx in (-1, 1):
            c = ellipsoid(f"{name}_cheek{sx}", 0.035, 0.012, 0.024, loc=(sx * 0.118, -0.222, 0.165),
                          parent=self.head, mats=[self.m_blush], segs=16, rings=8)
            self.cheeks.append(c)
        # 开心眼 ^ ^（默认隐藏）
        self.happy = []
        for sx in (-1, 1):
            h = curve_obj(f"{name}_happy{sx}", [(-0.03, 0, -0.01), (0, 0, 0.022), (0.03, 0, -0.01)],
                          bevel=0.008, mat=self.m_eye, parent=self.head, loc=(sx * 0.07, -0.262, 0.25))
            h.scale = (1e-4, 1e-4, 1e-4)
            self.happy.append(h)
        # 晕眼 @ @（默认隐藏）
        self.dizzy = []
        for sx in (-1, 1):
            pts = []
            for i in range(28):
                a = i * 0.55
                r = 0.004 + 0.0016 * i
                pts.append((r * math.cos(a), 0, r * math.sin(a)))
            d = curve_obj(f"{name}_dizzy{sx}", pts, bevel=0.0045, mat=self.m_eye, parent=self.head,
                          loc=(sx * 0.07, -0.262, 0.25))
            d.scale = (1e-4, 1e-4, 1e-4)
            self.dizzy.append(d)
        # 耳朵：(半径 x, y, z, 位置, 绕 y 外倾角)
        ear_spec = dict(side=(0.07, 0.028, 0.075, (0.235, -0.01, 0.23), 0.0),
                        top=(0.07, 0.03, 0.07, (0.16, 0.0, 0.4), 0.45),
                        pointy=(0.06, 0.03, 0.1, (0.15, 0.0, 0.41), 0.35),
                        tall=(0.05, 0.03, 0.17, (0.09, 0.02, 0.5), 0.15))[ears]
        for sx in (-1, 1):
            rx, ry, rz, (ex, ey, ez), tilt = ear_spec
            ear = ellipsoid(f"{name}_ear{sx}", rx, ry, rz, loc=(sx * ex, ey, ez),
                            rot=(0, sx * tilt, sx * math.radians(18) if ears == "side" else 0), parent=self.head,
                            mats=[self.m_base])
            if ears == "pointy":
                for v in ear.data.vertices:   # 上半截收窄成尖
                    k = max(0.0, v.co.z / rz)
                    v.co.x *= 1 - 0.75 * k
            ellipsoid(f"{name}_earin{sx}", rx * 0.64, ry * 0.43, rz * 0.66, loc=(0, -ry * 0.8, 0), parent=ear,
                      mats=[self.m_skin], segs=20, rings=10)
        # 手臂 / 腿：pivot 在关节
        self.arms, self.legs, self.hands = [], [], []
        for sx in (-1, 1):
            piv = empty(f"{name}_arm{sx}", loc=(sx * 0.165, -0.01, 0.49), parent=self.bob)
            a = ellipsoid(f"{name}_armm{sx}", 0.05, 0.05, 0.11, loc=(0, 0, -0.09), parent=piv, mats=[self.m_base])
            add_fur(a, self.m_fur, length=0.04 * fs, count=450, seed=seed + 3 + sx)
            self.hands.append(ellipsoid(f"{name}_hand{sx}", 0.045, 0.042, 0.045, loc=(0, -0.005, -0.2), parent=piv,
                                        mats=[self.m_skin], segs=20, rings=10))
            self.arms.append(piv)
        for sx in (-1, 1):
            piv = empty(f"{name}_leg{sx}", loc=(sx * 0.085, 0, 0.22), parent=self.bob)
            lg = ellipsoid(f"{name}_legm{sx}", 0.055, 0.055, 0.09, loc=(0, 0, -0.08), parent=piv, mats=[self.m_base])
            add_fur(lg, self.m_fur, length=0.035 * fs, count=380, seed=seed + 6 + sx)
            ellipsoid(f"{name}_foot{sx}", 0.05, 0.075, 0.035, loc=(0, -0.025, -0.188), parent=piv,
                      mats=[self.m_skin], segs=20, rings=10)
            self.legs.append(piv)
        # 尾巴
        if tail == "curl":
            curve_obj(name + "_tail", [(0, 0.14, 0.27), (0, 0.3, 0.2), (0, 0.44, 0.33), (0, 0.42, 0.55),
                                       (0, 0.33, 0.6), (0, 0.3, 0.5)],
                      bevel=0.028, mat=self.m_base, parent=self.bob, taper=[1, 1, 0.9, 0.8, 0.7, 0.6])
        elif tail == "pom":
            pom = ellipsoid(name + "_tail", 0.06, loc=(0, 0.17, 0.26), parent=self.bob, mats=[self.m_base])
            add_fur(pom, self.m_fur, length=0.04 * fs, count=300, seed=seed + 9)
        # 斗笠 / 围巾
        self.hat = None
        if hat:
            self.hat = cone(name + "_hat", 0.36, 0.0, 0.14, segs=64, loc=(0, 0, 0.47), parent=self.head,
                            rot=(math.radians(-6), 0, 0),
                            mats=[mat_textured(name + "_straw", PAL["straw_dark"], PAL["straw"], rough=0.8,
                                               scale=38.0, kind="RINGS", bump=0.25, pos=(0.2, 0.8))])
            sol = self.hat.modifiers.new("sol", "SOLIDIFY")
            sol.thickness = 0.012
            ellipsoid(name + "_hattop", 0.018, loc=(0, 0, 0.075), parent=self.hat, mats=[self.hat.data.materials[0]],
                      segs=12, rings=6)
        if scarf:
            torus(name + "_scarf", 0.15, 0.042, loc=(0, -0.005, 0.535), parent=self.bob,
                  mats=[mat_basic(name + "_cloth", scarf, rough=0.9, sheen=0.6)])
        self.set_eyes("open")

    # ---- 姿态
    def set_eyes(self, mode, k=1.0):
        """mode: open / blink(k=闭合程度) / happy / dizzy"""
        z = 1e-4
        for e in self.eyes:
            if mode in ("open", "blink"):
                sz = 1.0 - (0.9 * k if mode == "blink" else 0.0)
                e.scale = (1, 1, max(0.08, sz))
            else:
                e.scale = (z, z, z)
        for h in self.happy:
            h.scale = (1, 1, 1) if mode == "happy" else (z, z, z)
        for d in self.dizzy:
            d.scale = (1, 1, 1) if mode == "dizzy" else (z, z, z)

    def set_blush(self, k):
        for c in self.cheeks:
            s = 0.75 + 0.6 * k
            c.scale = (s, s, s)
        set_mat_color(self.m_blush, col("#e7958f"), emit_strength=0.25 + 1.2 * k)

    def pose(self, loc=(0, 0, 0), heading=0.0, gait=0.0, phase=0.0, arm_l=None, arm_r=None,
             head=(0, 0, 0), lean=0.0, hop=0.0, roll=0.0):
        """gait: 0..1 步伐幅度；phase: 步态相位（弧度）；arm_*: (x,y,z) 欧拉角覆盖；head: (俯仰,横滚,偏航)。"""
        self.root.location = loc
        self.root.rotation_euler = (0, roll, heading)
        sw = math.sin(phase)
        self.bob.location = (0, 0, gait * 0.03 * abs(math.sin(phase)) + hop)
        self.bob.rotation_euler = (lean, gait * 0.07 * sw, 0)
        self.legs[0].rotation_euler = (gait * 0.55 * sw, 0, 0)
        self.legs[1].rotation_euler = (-gait * 0.55 * sw, 0, 0)
        default_l = (-gait * 0.45 * sw, 0.18, 0)
        default_r = (gait * 0.45 * sw, -0.18, 0)
        self.arms[0].rotation_euler = arm_l if arm_l is not None else default_l
        self.arms[1].rotation_euler = arm_r if arm_r is not None else default_r
        self.head.rotation_euler = (head[0] + gait * 0.04 * math.sin(2 * phase), head[1], head[2])


# ---------------------------------------------------------------- 主容器：带空腔的树

def _trunk_mesh(name, r=0.62, h=2.9, seed=3, mats=None, parent=None, loc=(0, 0, 0)):
    random.seed(seed)
    off = random.random() * 10

    def b(bm):
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=72, radius1=1.0, radius2=1.0, depth=1.0)
        edges = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 0.5]
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=26, use_grid_fill=True)
        for v in bm.verts:
            z = v.co.z + 0.5  # 0..1
            a = math.atan2(v.co.y, v.co.x)
            rr = math.hypot(v.co.x, v.co.y)
            if rr < 1e-4:
                v.co = Vector((0, 0, z * h))
                continue
            n = noise.noise(Vector((math.cos(a) * 1.3 + off, math.sin(a) * 1.3, z * 2.2)))
            n2 = noise.noise(Vector((math.cos(a) * 4 + off, math.sin(a) * 4, z * 7)))
            radius = r * (1 - 0.12 * z) * (1 + 0.07 * n + 0.025 * n2)
            flare = max(0.0, 1 - z / 0.22) ** 2
            lobes = (0.5 + 0.5 * math.cos(5 * a + 1.3)) ** 3
            radius *= 1 + flare * (0.25 + 0.55 * lobes)
            scale = radius / rr * rr
            v.co = Vector((math.cos(a) * scale, math.sin(a) * scale, z * h))
    return mesh_obj(name, b, mats=mats, parent=parent, loc=loc)


class HollowTree:
    """主容器示例一：树干里有椭球空腔、侧面开口的树。cutaway=True 时纵向剖开（剖面朝镜头，开口在左侧）。
    同一个容器既拍整体外观（角色世界），也拍剖面（剖面世界），观众才认得出「还是那个地方」。"""

    def __init__(self, name="tree", loc=(0, 0, 0), cutaway=False, autumn=False, canopy=True, seed=3,
                 hole_z=1.02, cav=(0.42, 0.4, 0.62), cav_z=0.88):
        self.name = name
        self.cutaway = cutaway
        self.root = empty(name + "_root", loc=loc)
        self.hole_z = hole_z
        self.cav = cav
        self.cav_z = cav_z
        self.m_bark = mat_textured(name + "_bark", PAL["bark_dark"], PAL["bark"], rough=0.9, scale=7.0,
                                   kind="BANDS", stretch=(1, 1, 0.25), bump=0.5, pos=(0.25, 0.75))
        self.m_cav = mat_textured(name + "_cav", "#2a201b", PAL["cavity"], rough=0.95, scale=9.0, bump=0.4)
        self.m_cut = mat_textured(name + "_cut", "#b88f60", "#d9b886", rough=0.8, scale=22.0,
                                  kind="RINGS", stretch=(1, 1, 0.0), bump=0.12, pos=(0.25, 0.75))
        trunk = _trunk_mesh(name + "_trunk", seed=seed, mats=[self.m_bark])
        cavity = ellipsoid(name + "_cavcut", cav[0], cav[1], cav[2], loc=(0, 0, cav_z), mats=[self.m_cav])
        boolean(trunk, cavity)
        # 洞口：椭圆柱，宽 0.2（水平）× 高 0.27，轴沿开口方向
        hole = cone(name + "_holecut", 1.0, 1.0, 1.4, segs=48, mats=[self.m_cav])
        if cutaway:   # 轴沿 x（洞口朝左）：local x→world -z，local y→world y
            for v in hole.data.vertices:
                v.co.x *= 0.27
                v.co.y *= 0.2
            hole.rotation_euler = (0, math.radians(90), 0)
            hole.location = (-0.62, 0, hole_z)
        else:         # 轴沿 y（洞口朝镜头）：local x→world x，local y→world z
            for v in hole.data.vertices:
                v.co.x *= 0.2
                v.co.y *= 0.27
            hole.rotation_euler = (math.radians(90), 0, 0)
            hole.location = (0, -0.62, hole_z)
        boolean(trunk, hole)
        if cutaway:
            cut = box(name + "_halfcut", 6, 3, 8, loc=(0, -1.5, 3.0), mats=[self.m_cut])
            boolean(trunk, cut)
        self.trunk = bake_mesh(trunk, name + "_trunkb")
        self.trunk.parent = self.root
        self.trunk.data.shade_smooth()
        for o in (cavity, hole):
            bpy.data.objects.remove(o, do_unlink=True)
        if cutaway:
            bpy.data.objects.remove(bpy.data.objects[name + "_halfcut"], do_unlink=True)
        self.canopy = []
        if canopy:
            leafc = PAL["leaf_autumn"] if autumn else PAL["leaf"]
            self.m_leaf_fur = mat_fur(name + "_leaffur", leafc, root=0.7, tip=1.1)
            self.m_leaf = mat_basic(name + "_leafbase", scale_col(col(leafc), 0.75), rough=0.9)
            blobs = [(0, 0.05, 3.15, 0.95), (-0.85, 0.15, 2.85, 0.7), (0.85, 0.1, 2.9, 0.72),
                     (-0.4, -0.2, 3.65, 0.62), (0.45, -0.15, 3.7, 0.6), (0.0, 0.3, 4.0, 0.55)]
            for i, (x, y, z, r) in enumerate(blobs):
                bl = ellipsoid(f"{name}_leaf{i}", r, r * 0.9, r * 0.85, loc=(x, y, z), parent=self.root,
                               mats=[self.m_leaf])
                add_fur(bl, self.m_leaf_fur, length=0.07, count=int(2600 * r * r), children=8, clump=0.35,
                        rough1=0.04, rough2=0.08, seed=seed * 10 + i)
                self.canopy.append(bl)

    def opening(self):
        """开口在容器局部坐标里的位置，和朝里的方向（剖开时开口在左侧，完整时朝镜头）。"""
        if self.cutaway:
            return Vector((-0.62, 0, self.hole_z)), Vector((1, 0, 0))
        return Vector((0, -0.62, self.hole_z)), Vector((0, 1, 0))

    def hole_world(self):
        return self.root.matrix_world @ self.opening()[0]


class CutawayJar:
    """主容器示例二：釉面陶缸（泡、腌、酿、储存、沉淀这类过程）。cutaway=True 时纵向剖开，剖面朝镜头。
    协议同 HollowTree：root / cav / cav_z / hole_z / hole_world()，开口朝上；lid 是可以弹开的木盖（剖开时没有）。
    缸底比台面低一点（藏进台面里），看起来是平放的。"""

    def __init__(self, name="jar", loc=(0, 0, 0), cutaway=False, r=0.6, h=1.3, glaze="#6b4a33", lid=True):
        self.name = name
        self.root = empty(name + "_root", loc=loc)
        cz, rz = h * 0.45, h * 0.5
        self.cav = (r * 0.82, r * 0.82, rz * 0.8)
        self.cav_z = cz
        self.hole_z = cz + rz * 0.9
        self.m_glaze = mat_basic(name + "_glaze", glaze, rough=0.22, coat=0.8, spec=0.5)
        self.m_inner = mat_textured(name + "_inner", "#2c211b", "#3f3129", rough=0.6, scale=9.0, bump=0.2)
        self.m_cut = mat_textured(name + "_cut", "#b98c66", "#d2a77f", rough=0.85, scale=18.0, bump=0.15)
        body = ellipsoid(name + "_body", r, r, rz, loc=(0, 0, cz), mats=[self.m_glaze], segs=64, rings=32)
        rim = torus(name + "_rim", r * 0.42, r * 0.07, loc=(0, 0, self.hole_z), mats=[self.m_glaze])
        cavity = ellipsoid(name + "_cavcut", *self.cav, loc=(0, 0, cz), mats=[self.m_inner])
        mouth = cone(name + "_mouthcut", r * 0.38, r * 0.38, h, segs=48, loc=(0, 0, cz + rz), mats=[self.m_inner])
        boolean(body, cavity)
        boolean(body, mouth)
        cutters = [cavity, mouth]
        if cutaway:
            half = box(name + "_halfcut", 6, 3, 8, loc=(0, -1.5, 3.0), mats=[self.m_cut])
            boolean(body, half)
            boolean(rim, half)
            cutters.append(half)
            rim = bake_mesh(rim, name + "_rimb")
            rim.parent = self.root
        else:
            rim.parent = self.root
        self.body = bake_mesh(body, name + "_bodyb")
        self.body.parent = self.root
        self.body.data.shade_smooth()
        for o in cutters:
            bpy.data.objects.remove(o, do_unlink=True)
        self.lid = None
        if lid and not cutaway:
            self.lid = empty(name + "_lid", loc=(0, 0, self.hole_z + r * 0.05), parent=self.root)
            cone(name + "_liddisc", r * 0.5, r * 0.48, r * 0.06, segs=48, parent=self.lid,
                 mats=[mat_textured(name + "_wood", "#9c7552", "#b88c62", rough=0.6, scale=30, kind="RINGS",
                                    bump=0.05, pos=(0.3, 0.7))])
            ellipsoid(name + "_lidknob", r * 0.08, loc=(0, 0, r * 0.07), parent=self.lid,
                      mats=[mat_basic(name + "_knob", "#7d5a3c", rough=0.5)])

    def opening(self):
        """开口在容器局部坐标里的位置，和朝里的方向（缸口朝上）。"""
        return Vector((0, 0, self.hole_z)), Vector((0, 0, -1))

    def hole_world(self):
        return self.root.matrix_world @ self.opening()[0]


# ---------------------------------------------------------------- 小物件与微观角色

FRUIT_KINDS = dict(
    persimmon=dict(c="#d9773f", r=(0.1, 0.1, 0.082), sheen=0.0, rough=0.35, calyx=True),
    plum=dict(c="#7b4f72", r=(0.085, 0.082, 0.09), sheen=0.3, rough=0.4, calyx=False),
    pear=dict(c="#c4b75a", r=(0.08, 0.08, 0.098), sheen=0.0, rough=0.45, calyx=False),
    peach=dict(c="#e79d7b", r=(0.095, 0.09, 0.09), sheen=0.8, rough=0.55, calyx=False),
    berry=dict(c="#b9483f", r=(0.055, 0.055, 0.055), sheen=0.0, rough=0.3, calyx=False),
)


class FruitBank:
    """共享网格的果子：make(kind) 返回链接复制体（每个可独立动画）。"""

    def __init__(self):
        self.meshes = {}
        self.m_calyx = mat_basic("calyx", "#5d6b3f", rough=0.7)
        for k, d in FRUIT_KINDS.items():
            m = mat_basic("fruit_" + k, d["c"], rough=d["rough"], sheen=d["sheen"], sss=0.15, spec=0.45)
            ob = ellipsoid("proto_" + k, *d["r"], mats=[m], segs=32, rings=16)
            if d["calyx"]:
                for i in range(4):
                    a = i * math.pi / 2 + 0.4
                    leaf = ellipsoid(f"calyxp_{k}{i}", 0.045, 0.02, 0.008, mats=[self.m_calyx], segs=12, rings=6,
                                     loc=(math.cos(a) * 0.03, math.sin(a) * 0.03, d["r"][2] * 0.95),
                                     rot=(0, 0, a))
                    leaf.parent = ob
            ob.hide_render = True
            ob.location = (0, 0, -50)
            self.meshes[k] = ob

    def make(self, kind, name):
        proto = self.meshes[kind]
        ob = link(bpy.data.objects.new(name, proto.data))
        for ch in proto.children:
            c2 = link(bpy.data.objects.new(name + "_" + ch.name, ch.data))
            c2.parent = ob
            c2.location = ch.location
            c2.rotation_euler = ch.rotation_euler
        return ob


class FluffAgent:
    """好的微观角色（菌、细胞、颗粒都行）：浅色毛球 + 豆豆眼，会眨眼、会死（X 眼）。
    同色的个体共用一套材质（self.M），改 self.M["fur"] 的颜色会让同色的全部一起变（集体变灰正好用这个）。"""
    _mats = {}

    def __init__(self, name, r=0.06, seed=0, fur=True, color="#f3efe6"):
        if color not in FluffAgent._mats:
            k = len(FluffAgent._mats)
            FluffAgent._mats[color] = dict(
                fur=mat_fur(f"agent{k}_fur", color, root=0.8, tip=1.05),
                base=mat_basic(f"agent{k}_base", scale_col(col(color), 0.95), rough=0.8),
                eye=mat_basic(f"agent{k}_eye", "#15110f", rough=0.08, coat=1.0, spec=0.8),
                hi=mat_basic(f"agent{k}_hi", "#ffffff", emit="#ffffff", emit_strength=3.0),
            )
        M = self.M = FluffAgent._mats[color]
        self.root = empty(name)
        self.body = ellipsoid(name + "_b", r, r, r * 0.95, parent=self.root, mats=[M["base"]], segs=32, rings=16)
        if fur:
            front = Vector((0, -1, 0.1)).normalized()
            vg = vgroup_by(self.body, "fur", lambda co: 1.0 - smoothstep(0.45, 0.66, co.normalized().dot(front)))
            self.psys = add_fur(self.body, M["fur"], length=r * 0.5, count=int(1100 * (r / 0.06) ** 2), children=8,
                                rough1=0.03, rough2=0.12, rough_end=0.05, clump=0.1, seed=seed, root=0.25,
                                vgroup=vg.name)
        self.eyes = []
        for sx in (-1, 1):
            e = ellipsoid(f"{name}_e{sx}", r * 0.15, r * 0.09, r * 0.2, loc=(sx * r * 0.27, -r * 0.97, r * 0.14),
                          parent=self.root, mats=[M["eye"]], segs=12, rings=6)
            ellipsoid(f"{name}_eh{sx}", r * 0.05, r * 0.03, r * 0.05, loc=(-r * 0.04, -r * 0.08, r * 0.07),
                      parent=e, mats=[M["hi"]], segs=8, rings=4)
            self.eyes.append(e)
        self.xeyes = []
        for sx in (-1, 1):
            grp = empty(f"{name}_x{sx}", loc=(sx * r * 0.27, -r * 0.99, r * 0.14), parent=self.root)
            for a in (math.radians(45), math.radians(-45)):
                bar = box(f"{name}_xb{sx}{a:.1f}", r * 0.32, r * 0.05, r * 0.06, parent=grp, mats=[M["eye"]])
                bar.rotation_euler = (0, a, 0)
            grp.scale = (1e-4, 1e-4, 1e-4)
            self.xeyes.append(grp)

    def set_dead(self, k):
        """k: 0 活着, 1 死透（X 眼）。"""
        z = 1e-4
        for e in self.eyes:
            e.scale = (1, 1, 1) if k < 0.5 else (z, z, z)
        for x in self.xeyes:
            x.scale = (1, 1, 1) if k >= 0.5 else (z, z, z)


def molecule(name, kind, scale=1.0, tint=None):
    """玩具球棍分子模型。kind: sucrose / glucose / fructose / ethanol / co2 / o2 / h2o / acid / ester。
    颜色约定：碳深灰（tint 可换）、氧红、氢白；六元环蓝、五元环粉。新分子照 elif 分支加一段原子 + 键。"""
    root = empty(name)
    mC = mat_basic(name + "_c", tint or "#5b6070", rough=0.25, coat=0.6, spec=0.6)
    mO = mat_basic(name + "_o", "#e0675a", rough=0.25, coat=0.6, spec=0.6)
    mH = mat_basic(name + "_h", "#f4f1ea", rough=0.25, coat=0.6, spec=0.6)
    mG = mat_basic(name + "_g", "#7fa7d6", rough=0.25, coat=0.6, spec=0.6)   # 葡萄糖环
    mF = mat_basic(name + "_f", "#e59bb5", rough=0.25, coat=0.6, spec=0.6)   # 果糖环
    mS = mat_basic(name + "_s", "#d8d2c4", rough=0.4)
    s = scale
    atoms, bonds = [], []

    def ring(cx, n, rr, m, z=0):
        idx = []
        for i in range(n):
            a = 2 * math.pi * i / n + math.pi / 2
            atoms.append(((cx + rr * math.cos(a), 0, z + rr * math.sin(a)), 0.07, m))
            idx.append(len(atoms) - 1)
        for i in range(n):
            bonds.append((idx[i], idx[(i + 1) % n]))
        return idx
    if kind in ("sucrose", "glucose", "fructose"):
        if kind in ("sucrose", "glucose"):
            gi = ring(-0.32 if kind == "sucrose" else 0, 6, 0.2, mG)
        if kind in ("sucrose", "fructose"):
            fi = ring(0.32 if kind == "sucrose" else 0, 5, 0.17, mF)
        if kind == "sucrose":
            atoms.append(((0, 0, -0.02), 0.06, mO))
            o = len(atoms) - 1
            bonds.append((gi[4], o))
            bonds.append((fi[2], o))
    elif kind == "ethanol":
        atoms += [((-0.17, 0, 0), 0.085, mC), ((0.0, 0, 0.1), 0.085, mC), ((0.18, 0, 0), 0.075, mO),
                  ((0.28, 0, 0.08), 0.045, mH)]
        bonds += [(0, 1), (1, 2), (2, 3)]
    elif kind == "h2o":
        atoms += [((0, 0, 0), 0.08, mO), ((-0.1, 0, -0.07), 0.05, mH), ((0.1, 0, -0.07), 0.05, mH)]
        bonds += [(0, 1), (0, 2)]
    elif kind == "o2":
        atoms += [((-0.075, 0, 0), 0.075, mO), ((0.075, 0, 0), 0.075, mO)]
        bonds += [(0, 1)]
    elif kind == "co2":
        atoms += [((-0.15, 0, 0), 0.07, mO), ((0, 0, 0), 0.08, mC), ((0.15, 0, 0), 0.07, mO)]
        bonds += [(0, 1), (1, 2)]
    elif kind == "acid":
        atoms += [((-0.1, 0, 0), 0.08, mC), ((0.08, 0, 0.1), 0.07, mO), ((0.08, 0, -0.1), 0.07, mO),
                  ((-0.26, 0, 0.0), 0.08, mC)]
        bonds += [(0, 1), (0, 2), (0, 3)]
    elif kind == "ester":
        atoms += [((-0.36, 0, 0), 0.08, mC), ((-0.2, 0, 0.08), 0.08, mC), ((-0.04, 0, 0), 0.07, mO),
                  ((0.12, 0, 0.06), 0.08, mC), ((0.12, 0, 0.22), 0.07, mO), ((0.28, 0, 0), 0.08, mC)]
        bonds += [(0, 1), (1, 2), (2, 3), (3, 4), (3, 5)]
    objs = []
    for i, (p, r, m) in enumerate(atoms):
        objs.append(ellipsoid(f"{name}_a{i}", r * s, loc=tuple(c * s for c in p), parent=root, mats=[m],
                              segs=20, rings=10))
    for i, (a, b) in enumerate(bonds):
        pa, pb = Vector(atoms[a][0]) * s, Vector(atoms[b][0]) * s
        d = pb - pa
        st = cone(f"{name}_b{i}", 0.022 * s, 0.022 * s, d.length, segs=12, parent=root, mats=[mS])
        st.location = (pa + pb) / 2
        st.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    return root


class Cloud:
    def __init__(self, name, loc=(0, 0, 4)):
        self.root = empty(name, loc=loc)
        mf = mat_fur(name + "_fur", "#f6f4ef", root=0.85, tip=1.03)
        mb = mat_basic(name + "_b", "#ebe8e1", rough=0.9)
        for i, (x, z, r) in enumerate([(0, 0, 0.42), (-0.45, -0.08, 0.32), (0.45, -0.06, 0.34),
                                       (-0.2, 0.22, 0.3), (0.22, 0.2, 0.28), (-0.75, -0.15, 0.2),
                                       (0.78, -0.13, 0.22)]):
            b = ellipsoid(f"{name}_{i}", r, r * 0.8, r * 0.85, loc=(x, 0, z), parent=self.root, mats=[mb])
            add_fur(b, mf, length=0.06, count=int(2400 * r * r), children=8, clump=0.2, seed=40 + i,
                    rough1=0.04, rough2=0.1)


class SpikyAgent:
    """坏的微观角色（杂菌、病毒、污染物）：深色刺毛球 + 黄眼 + 坏笑白牙。和 FluffAgent 一眼分得出好坏。"""
    _mats = None

    def __init__(self, name, r=0.08, hue="#4b5a3c", seed=0):
        if SpikyAgent._mats is None:
            SpikyAgent._mats = dict(
                eye=mat_basic("germ_eye", "#f2d64b", rough=0.2, emit="#f2d64b", emit_strength=1.5),
                pupil=mat_basic("germ_pupil", "#111111", rough=0.1),
                tooth=mat_basic("germ_tooth", "#f5f2ea", rough=0.3),
                mouth=mat_basic("germ_mouth", "#2a1214", rough=0.6),
            )
        M = SpikyAgent._mats
        self.root = empty(name)
        mb = mat_basic(name + "_b", scale_col(col(hue), 0.7), rough=0.8)
        mf = mat_fur(name + "_f", hue, root=0.5, tip=1.2)
        body = ellipsoid(name + "_body", r, parent=self.root, mats=[mb], segs=24, rings=12)
        add_fur(body, mf, length=r * 0.7, count=int(500 * (r / 0.08) ** 2), children=6, clump=0.85,
                rough1=0.0, rough2=0.02, seed=seed, root=0.5)
        for sx in (-1, 1):
            e = ellipsoid(f"{name}_e{sx}", r * 0.22, r * 0.1, r * 0.2, loc=(sx * r * 0.33, -r * 1.02, r * 0.25),
                          parent=self.root, mats=[M["eye"]], segs=12, rings=6, rot=(0, sx * 0.4, 0))
            ellipsoid(f"{name}_p{sx}", r * 0.08, r * 0.05, r * 0.1, loc=(0, -r * 0.08, -r * 0.02), parent=e,
                      mats=[M["pupil"]], segs=8, rings=4)
        ellipsoid(name + "_m", r * 0.45, r * 0.08, r * 0.16, loc=(0, -r * 1.0, -r * 0.25), parent=self.root,
                  mats=[M["mouth"]], segs=16, rings=8)
        for i in range(5):
            x = (i - 2) * r * 0.15
            box(f"{name}_t{i}", r * 0.11, r * 0.05, r * 0.11, loc=(x, -r * 1.07, -r * 0.18), parent=self.root,
                mats=[M["tooth"]])


def glass_tube(name, r=0.12, h=0.9, liquid="#d9a441", loc=(0, 0, 0)):
    root = empty(name, loc=loc)
    glass = mat_basic(name + "_glass", "#ffffff", rough=0.05, spec=0.9, alpha=0.18)
    tube = cone(name + "_tube", r, r, h, segs=48, cap=False, parent=root, loc=(0, 0, h / 2), mats=[glass])
    sol = tube.modifiers.new("sol", "SOLIDIFY")
    sol.thickness = 0.01
    ellipsoid(name + "_bottom", r, r, r * 0.4, loc=(0, 0, 0.0), parent=root, mats=[glass])
    lm = mat_liquid(name + "_liq", liquid, emit_strength=0.3)
    liq = cone(name + "_liquid", r * 0.86, r * 0.86, 1.0, segs=40, parent=root, mats=[lm])
    for v in liq.data.vertices:
        v.co.z += 0.5  # 底在 0，高 1，用 scale.z 控制液面
    liq.location = (0, 0, 0.01)
    base = cone(name + "_base", r * 1.5, r * 1.6, 0.06, segs=48, parent=root, loc=(0, 0, 0.03),
                mats=[mat_basic(name + "_wood", "#a88762", rough=0.7)])
    return dict(root=root, liquid=liq, mat=lm, h=h, base=base)


def mountains(name, layers, coll=None):
    """立在台面后方的纸板远山剪影。layers: [(y, color, height, seed)]"""
    objs = []
    for li, (y, c, hgt, seed) in enumerate(layers):
        random.seed(seed)
        m = mat_basic(f"{name}_m{li}", c, rough=0.95, spec=0.1)
        pts = []
        x = -9.0
        while x < 9.0:
            pts.append((x, hgt * (0.35 + 0.65 * random.random()) * (0.6 + 0.4 * math.sin(x * 0.7 + seed))))
            x += 0.6 + random.random() * 1.0

        def b(bm, pts=pts):
            vs = [bm.verts.new((-9.0, 0, 0))]
            for (px, pz) in pts:
                vs.append(bm.verts.new((px, 0, max(0.15, pz))))
            vs.append(bm.verts.new((9.0, 0, 0)))
            f = bm.faces.new(vs)
            ext = bmesh.ops.extrude_face_region(bm, geom=[f])
            for v in [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]:
                v.co.y += 0.04
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        ob = mesh_obj(f"{name}_{li}", b, mats=[m], loc=(0, y, 0), smooth=False, coll=coll)
        bev = ob.modifiers.new("bev", "BEVEL")
        bev.width = 0.015
        bev.segments = 2
        objs.append(ob)
    return objs


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def ease_out_back(t, s=1.70158):
    t = max(0.0, min(1.0, t)) - 1
    return t * t * ((s + 1) * t + s) + 1


def ease_in_out(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    if isinstance(a, (tuple, list, Vector)):
        return tuple(a[i] + (b[i] - a[i]) * t for i in range(len(a)))
    return a + (b - a) * t


def bounce_drop(t):
    """0..1 → 落下后弹两下的高度系数（1=起点高度, 0=落地）。"""
    t = max(0.0, min(1.0, t))
    if t < 0.55:
        u = t / 0.55
        return 1 - u * u
    if t < 0.82:
        u = (t - 0.55) / 0.27
        return 0.18 * (1 - (2 * u - 1) ** 2)
    u = (t - 0.82) / 0.18
    return 0.05 * (1 - (2 * u - 1) ** 2)


# ---------------------------------------------------------------- 更多道具

def set_fur_color(m, c, root=0.62, tip=1.06):
    ramp = next(n for n in m.node_tree.nodes if n.type == "VALTORGB")
    ramp.color_ramp.elements[0].color = scale_col(c, root)
    ramp.color_ramp.elements[1].color = scale_col(c, tip)


def hide(ob, k=0.0):
    """用缩放显隐（带毛发的物体也适用）。k=0 隐藏，1 原尺寸。"""
    s = max(1e-4, k)
    ob.scale = (s, s, s)


def lolli_tree(name, loc, h=1.1, r=0.45, color="#9fb08f", seed=0):
    root = empty(name, loc=loc)
    cone(name + "_trunk", 0.06, 0.04, h, segs=16, loc=(0, 0, h / 2), parent=root,
         mats=[mat_basic(name + "_tr", "#8a7563", rough=0.9)])
    mb = mat_basic(name + "_cb", scale_col(col(color), 0.75), rough=0.9)
    mf = mat_fur(name + "_cf", color, root=0.7, tip=1.08)
    cb = ellipsoid(name + "_can", r, r * 0.9, r * 1.1, loc=(0, 0, h + r * 0.7), parent=root, mats=[mb])
    add_fur(cb, mf, length=0.06, count=int(2600 * r * r), children=8, clump=0.3, rough1=0.04, rough2=0.08,
            seed=seed)
    return root


def bush(name, loc, r=0.5, color="#8f9f73", seed=0, n=4):
    root = empty(name, loc=loc)
    mb = mat_basic(name + "_b", scale_col(col(color), 0.75), rough=0.9)
    mf = mat_fur(name + "_f", color, root=0.65, tip=1.1)
    random.seed(seed)
    for i in range(n):
        a = i / n * math.tau + random.random()
        rr = r * (0.55 + 0.3 * random.random())
        b = ellipsoid(f"{name}_{i}", rr, rr * 0.9, rr * 0.85,
                      loc=(math.cos(a) * r * 0.45, math.sin(a) * r * 0.25, rr * 0.75), parent=root, mats=[mb])
        add_fur(b, mf, length=0.06, count=int(2600 * rr * rr), children=8, clump=0.3, rough1=0.04, rough2=0.09,
                seed=seed * 7 + i)
    return root


def basket(name, loc, r=0.2, h=0.14):
    root = empty(name, loc=loc)
    m = mat_textured(name + "_m", PAL["straw_dark"], PAL["straw"], rough=0.85, scale=40, kind="BANDS", bump=0.3,
                     pos=(0.2, 0.8))
    body = cone(name + "_b", r * 0.8, r, h, segs=48, cap=False, loc=(0, 0, h / 2), parent=root, mats=[m])
    sol = body.modifiers.new("s", "SOLIDIFY")
    sol.thickness = 0.015
    cone(name + "_bot", r * 0.8, r * 0.8, 0.015, segs=48, loc=(0, 0, 0.008), parent=root, mats=[m])
    torus(name + "_rim", r, 0.02, loc=(0, 0, h), parent=root, mats=[m])
    return root


def text3d(name, body, font_path, size=0.2, extrude=0.02, mat=None, parent=None, loc=(0, 0, 0)):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.font = bpy.data.fonts.load(font_path, check_existing=True)
    cu.size = size
    cu.extrude = extrude
    cu.bevel_depth = extrude * 0.3
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    if mat:
        cu.materials.append(mat)
    ob = link(bpy.data.objects.new(name, cu))
    ob.parent = parent
    ob.location = loc
    ob.rotation_euler = (math.radians(90), 0, 0)   # 立起来，字面朝 -y（镜头）
    return ob


def labeled_jar(name, loc, s=1.0, font=None, glyph=None, cloth="#c2453b"):
    """釉面陶罐 + 红布封口 + 斜贴的方签；glyph 是签上的一个字（需要 font）。揭晓物、成品都能用。"""
    root = empty(name, loc=loc)
    root.scale = (s, s, s)
    glaze = mat_basic(name + "_g", "#6b4a33", rough=0.22, coat=0.8, spec=0.5)
    ellipsoid(name + "_body", 0.3, 0.3, 0.32, loc=(0, 0, 0.32), parent=root, mats=[glaze], segs=48, rings=24)
    cone(name + "_neck", 0.15, 0.16, 0.1, segs=40, loc=(0, 0, 0.66), parent=root, mats=[glaze])
    ellipsoid(name + "_cloth", 0.21, 0.21, 0.07, loc=(0, 0, 0.72), parent=root,
              mats=[mat_basic(name + "_c", cloth, rough=0.9, sheen=0.5)])
    torus(name + "_rope", 0.165, 0.014, loc=(0, 0, 0.69), parent=root,
          mats=[mat_basic(name + "_r", "#d9c49a", rough=0.8)])
    lab = box(name + "_label", 0.17, 0.01, 0.17, loc=(0, -0.3, 0.36), rot=(0, math.radians(45), 0), parent=root,
              mats=[mat_basic(name + "_p", "#d9573f", rough=0.8)])
    if font and glyph:
        text3d(name + "_glyph", glyph, font, size=0.13, extrude=0.006, parent=root, loc=(0, -0.312, 0.35),
               mat=mat_basic(name + "_ink", "#1d1512", rough=0.5))
    return root


def bowl(name, loc, r=0.16, liquid="#e3a24c", parent=None):
    root = empty(name, loc=loc, parent=parent)
    wood = mat_textured(name + "_w", "#9c7552", "#b88c62", rough=0.55, scale=30, kind="RINGS", bump=0.05,
                        pos=(0.3, 0.7))

    def b(bm):
        bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=1.0)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z > 0.02], context="VERTS")
        bmesh.ops.scale(bm, vec=(r, r, r * 0.75), verts=bm.verts)
    sh = mesh_obj(name + "_shell", b, parent=root, mats=[wood], loc=(0, 0, r * 0.75))
    sol = sh.modifiers.new("s", "SOLIDIFY")
    sol.thickness = 0.016
    lm = mat_liquid(name + "_l", liquid, emit_strength=0.9)
    liq = ellipsoid(name + "_liq", r * 0.92, r * 0.92, 0.012, loc=(0, 0, r * 0.75 - 0.035), parent=root, mats=[lm])
    return dict(root=root, liquid=liq, mat=lm)


def toggle_switch(name, loc):
    root = empty(name, loc=loc)
    bx = box(name + "_base", 0.56, 0.26, 0.1, loc=(0, 0, 0.05), parent=root,
             mats=[mat_basic(name + "_b", "#efe6d4", rough=0.5)])
    bev = bx.modifiers.new("bev", "BEVEL")
    bev.width = 0.03
    bev.segments = 4
    piv = empty(name + "_piv", loc=(0, 0, 0.1), parent=root)
    cone(name + "_lever", 0.026, 0.02, 0.3, segs=16, loc=(0, 0, 0.15), parent=piv,
         mats=[mat_basic(name + "_l", "#5b6070", rough=0.3, metallic=0.6)])
    ellipsoid(name + "_knob", 0.055, loc=(0, 0, 0.31), parent=piv,
              mats=[mat_basic(name + "_k", "#d9573f", rough=0.3, coat=0.5)])
    mL = mat_basic(name + "_mL", "#7fb3e0", rough=0.3, emit="#7fb3e0", emit_strength=0.0)
    mR = mat_basic(name + "_mR", "#f0a43a", rough=0.3, emit="#f0a43a", emit_strength=0.0)
    ellipsoid(name + "_lampL", 0.035, loc=(-0.19, -0.12, 0.09), parent=root, mats=[mL])
    ellipsoid(name + "_lampR", 0.035, loc=(0.19, -0.12, 0.09), parent=root, mats=[mR])
    return dict(root=root, piv=piv, mL=mL, mR=mR)


def no_sign(name, loc, r=0.34, post=0.0):
    root = empty(name, loc=loc)
    red = mat_basic(name + "_r", "#d33b2f", rough=0.35, coat=0.4, emit="#d33b2f", emit_strength=0.2)
    white = mat_basic(name + "_w", "#f6f2ea", rough=0.5)
    torus(name + "_ring", r, r * 0.13, parent=root, mats=[red], rot=(math.radians(90), 0, 0))
    cone(name + "_disc", r, r, 0.02, segs=64, parent=root, rot=(math.radians(90), 0, 0), loc=(0, 0.012, 0),
         mats=[white])
    box(name + "_bar", r * 1.9, 0.05, r * 0.24, parent=root, mats=[red], loc=(0, -0.02, 0),
        rot=(0, math.radians(45), 0))
    if post:
        cone(name + "_post", 0.028, 0.028, post, segs=12, loc=(0, 0.045, -post / 2 - r), parent=root,
             mats=[mat_basic(name + "_p", "#8a7563", rough=0.8)])
    return root


def heart(name, s=0.06, mat=None, parent=None):
    def b(bm):
        vs = []
        for i in range(40):
            tt = i / 40 * math.tau
            x = 16 * math.sin(tt) ** 3
            z = 13 * math.cos(tt) - 5 * math.cos(2 * tt) - 2 * math.cos(3 * tt) - math.cos(4 * tt)
            vs.append(bm.verts.new((x / 17 * s, 0, z / 17 * s)))
        f = bm.faces.new(vs)
        ext = bmesh.ops.extrude_face_region(bm, geom=[f])
        for v in [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]:
            v.co.y += s * 0.5
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh_obj(name, b, mats=[mat], parent=parent, smooth=False)
    bev = ob.modifiers.new("bev", "BEVEL")
    bev.width = s * 0.15
    bev.segments = 3
    return ob


def sparkle(name, s=0.05, mat=None, parent=None):
    def b(bm):
        vs = []
        for i in range(8):
            a = i / 8 * math.tau + math.pi / 2
            r = s if i % 2 == 0 else s * 0.3
            vs.append(bm.verts.new((r * math.cos(a), 0, r * math.sin(a))))
        f = bm.faces.new(vs)
        ext = bmesh.ops.extrude_face_region(bm, geom=[f])
        for v in [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]:
            v.co.y += s * 0.15
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, b, mats=[mat], parent=parent, smooth=False)


def swirl(name, base, h=1.0, amp=0.12, turns=1.4, color="#f2c38b", phase=0.0, parent=None):
    n = 18
    pts = []
    for i in range(n):
        u = i / (n - 1)
        pts.append((base[0] + amp * math.sin(phase + u * turns * math.tau) * (0.4 + u),
                    base[1] - 0.04 * u, base[2] + h * u))
    m = mat_basic(name + "_m", color, rough=0.4, emit=color, emit_strength=1.4)
    ob = curve_obj(name, pts, bevel=0.016, mat=m, parent=parent,
                   taper=[0.35 + 0.65 * math.sin(math.pi * min(1.0, (i / (n - 1)) * 1.15)) for i in range(n)])
    ob.data.bevel_factor_mapping_end = "SPLINE"
    ob.data.bevel_factor_end = 0.0
    return ob


def drop_mesh(name, r=0.03, mat=None, parent=None):
    def b(bm):
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=1.0)
        for v in bm.verts:
            z = v.co.z
            k = 1.0 - 0.8 * max(0.0, z)
            v.co.x *= k * r
            v.co.y *= k * r
            v.co.z = z * r * (1.7 if z > 0 else 1.0)
    return mesh_obj(name, b, mats=[mat], parent=parent)


def blob(name, rx, ry, rz, amp=0.18, freq=3.0, seed=0, mats=None, parent=None, loc=(0, 0, 0)):
    """凹凸不平的团块（果泥塞子、雪堆）。"""
    def b(bm):
        bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=20, radius=1.0)
        for v in bm.verts:
            n = noise.noise(v.co * freq + Vector((seed * 3.1, seed * 1.7, 0)))
            v.co *= 1.0 + amp * n
            v.co.x *= rx
            v.co.y *= ry
            v.co.z *= rz
    return mesh_obj(name, b, mats=mats, parent=parent, loc=loc)


def thermometer(name, loc, h=0.5):
    t = glass_tube(name, r=0.03, h=h, liquid="#d9473b", loc=loc)
    ellipsoid(name + "_bulb", 0.052, loc=(0, 0, 0.05), parent=t["root"], mats=[t["mat"]])
    return t


def petri(name, loc, r=0.8):
    root = empty(name, loc=loc)
    glass = mat_basic(name + "_g", "#eef3f1", rough=0.08, spec=0.8, alpha=0.35)
    cone(name + "_dish", r, r, 0.025, segs=96, loc=(0, 0, 0.0125), parent=root, mats=[glass])
    torus(name + "_rim", r, 0.02, loc=(0, 0, 0.04), parent=root, mats=[glass])
    cone(name + "_agar", r * 0.96, r * 0.96, 0.03, segs=96, loc=(0, 0, 0.03), parent=root,
         mats=[mat_basic(name + "_a", "#f1d9a6", rough=0.35, sss=0.4, spec=0.4)])
    return root


def stick_between(ob, pa, pb, base_len=1.0):
    """把沿 z 的圆柱摆到 pa→pb（世界坐标，物体无父级）。"""
    pa, pb = Vector(pa), Vector(pb)
    d = pb - pa
    ob.location = (pa + pb) / 2
    ob.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    ob.scale = (1, 1, max(1e-4, d.length / base_len))


# ---------------------------------------------------------------- 剖面容器里的东西

class CutLiquid:
    """主容器空腔里的液体：空腔椭球 ∩ (y≥0, z≤液面)。set_level(0..1) 按空腔高度比例；half=False 时是整团
    （整体外观镜头里透出来的光）。液面高度、颜色是剖面世界的「进度条」：每次回到剖面都要接着上一次的状态。"""

    def __init__(self, tree, name="liquid", color="#d38a3a", emit=0.45, half=True):
        rx, ry, rz = tree.cav
        self.tree = tree
        self.half = half
        self.mat = mat_basic(name + "_m", color, rough=0.08, spec=0.7, emit=color, emit_strength=emit)
        self.mat.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 0.62
        self.mat.surface_render_method = "DITHERED"
        self.ob = ellipsoid(name, rx * 0.996, ry * 0.996, rz * 0.996, loc=(0, 0, tree.cav_z), parent=tree.root,
                            mats=[self.mat], segs=64, rings=32)
        self.cut = box(name + "_cut", 2.0, 1.0 if half else 2.0, 2.0, parent=tree.root, mats=[self.mat])
        md = self.ob.modifiers.new("lv", "BOOLEAN")
        md.operation = "INTERSECT"
        md.solver = "MANIFOLD"
        md.object = self.cut
        self.cut.hide_render = True
        self.set_level(0.0)

    def level_z(self, frac):
        rz = self.tree.cav[2]
        return self.tree.cav_z - rz + 2 * rz * frac

    def set_level(self, frac):
        self.cut.location = (0, 0.5 if self.half else 0.0, self.level_z(frac) - 1.0)
        self.ob.hide_render = frac <= 0.002

    def set_color(self, c, emit=None):
        set_mat_color(self.mat, c, emit_strength=emit)


FRUIT_ORDER = ["persimmon", "plum", "pear", "peach", "berry", "persimmon", "peach", "plum"]


def drop_pile(tree, n, seed=0, ymin=0.1, ymax=0.3, rmin=0.07, rmax=0.095, kinds=None):
    """往剖开的空腔里一颗颗「丢」小物件：每颗从底往上找第一个不重叠的位置。返回 [(局部坐标, 半径, 种类)]。"""
    kinds = kinds or FRUIT_ORDER
    rx, ry, rz = tree.cav
    zc = tree.cav_z
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        r = rnd.uniform(rmin, rmax)
        best = None
        for _ in range(12):
            x = rnd.uniform(-rx + r, rx - r)
            y = rnd.uniform(ymin, ymax)
            z = zc - rz + r
            while z < zc + rz - r:
                inside = (x / (rx - r)) ** 2 + (y / (ry - r)) ** 2 + ((z - zc) / (rz - r)) ** 2 <= 1
                if inside and all((Vector((x, y, z)) - p).length >= (r + pr) * 0.93 for p, pr, _ in out):
                    break
                z += 0.012
            if best is None or z < best[0].z:
                best = (Vector((x, y, z)), r)
        out.append((best[0], best[1], kinds[i % len(kinds)]))
    return out


def point_light(name, loc, energy=0.0, color="#ffb347", radius=0.1, parent=None):
    ld = bpy.data.lights.new(name, "POINT")
    ld.energy = energy
    ld.color = col(color)[:3]
    ld.shadow_soft_size = radius
    ob = link(bpy.data.objects.new(name, ld))
    ob.parent = parent
    ob.location = loc
    return ob


def arrow(name, length=0.4, r=0.035, color="#d9573f", up=True, loc=(0, 0, 0), parent=None):
    """竖直箭头，root 在箭尾。"""
    root = empty(name, loc=loc, parent=parent)
    m = mat_basic(name + "_m", color, rough=0.35, coat=0.4, emit=color, emit_strength=0.3)
    shaft = length * 0.6
    head = length - shaft
    sgn = 1 if up else -1
    cone(name + "_shaft", r, r, shaft, segs=20, loc=(0, 0, sgn * shaft / 2), parent=root, mats=[m])
    hd = cone(name + "_head", r * 2.5, 0.0, head, segs=24, loc=(0, 0, sgn * (shaft + head / 2)), parent=root,
              mats=[m])
    if not up:
        hd.rotation_euler = (math.pi, 0, 0)
    return root


# ---------------------------------------------------------------- 镜头小工具（shots.py 里每个镜头都用）

def stage_base(cam_lens=50, mountains_on=True, ledge=True, world="#9aa494", key=1200.0):
    """标准布景：灰绿墙 + 米白台面 + 三层纸板远山 + 三盏面光 + 相机。返回 (cam, lights)。
    剖面镜头和桌面实验镜头一般 mountains_on=False（背景越干净，注意力越集中在过程上）。"""
    if ledge:
        build_stage()
    else:
        plane_xz("wall", 40, 24, loc=(0, 3.2, 6.0),
                 mat=mat_textured("m_wall", "#86907f", "#949d8d", rough=0.95, scale=1.6, bump=0.03, spec=0.1))
    lights = build_lights(key=key, world=world)
    if mountains_on:
        mountains("mtn", [(2.9, "#a3ab9c", 2.2, 1), (2.5, "#949d8c", 1.6, 5), (2.1, "#87917f", 1.1, 9)])
    return make_camera(cam_lens), lights


def walk_phase(t, speed=11.0):
    """小碎步的步态相位：speed 11 ≈ 每秒 3.5 步。cues.py 的 footfalls 用同一个 speed 算落脚点。"""
    return t * speed


def cam_move(cam, t, dur, p0, p1, tgt0, tgt1, lens0, lens1, fstop=3.2, ease=ease_in_out, focus=None):
    """镜头在 dur 秒内从 (p0, tgt0, lens0) 缓动到 (p1, tgt1, lens1)。默认整镜都在慢慢推，不停。"""
    u = ease(t / max(0.01, dur))
    aim_camera(cam, lerp(p0, p1, u), lerp(tgt0, tgt1, u), lens=lerp(lens0, lens1, u), fstop=fstop, focus=focus)


def ease_out_cubic(u):
    """推镜头的「快进慢停」：揭晓、特写用。"""
    return 1 - (1 - min(1.0, max(0.0, u))) ** 3


def evt(ev, key, default):
    """镜头里的口播事件时间；timeline 还没排出来时用 default 预览。"""
    return ev.get(key, default)


def drop_in(ob, base_loc, t, t0, h=0.35, dur=0.45, spin=4.0):
    """t0 时从上方落到 base_loc（带两下弹跳），之前隐藏。"""
    if t < t0:
        hide(ob, 0)
        return
    hide(ob, 1)
    u = (t - t0) / dur
    ob.location = (base_loc[0], base_loc[1], base_loc[2] + h * bounce_drop(u))
    ob.rotation_euler = (0, 0, spin * min(1.0, u))


def place_pile(container, bank, pile, name="p"):
    """drop_pile 算出的位置 → 共享网格的小物件，挂在容器 root 下。返回 [(物体, 位置, 缩放)]。"""
    obs = []
    for i, (p, r, k) in enumerate(pile):
        f = bank.make(k, f"{name}{i}")
        f.parent = container.root
        obs.append((f, p, r / max(FRUIT_KINDS[k]["r"])))
    return obs


def pile_state(obs, squash=0.0, appear=None):
    """一堆小物件的状态：squash 0..1 越压越扁（底下的压得更狠），appear(i) 控制第 i 个的显隐比例。"""
    for i, (f, p, sc) in enumerate(obs):
        z_s = 1.0 - squash * (0.35 + 0.1 * math.sin(i * 1.7))
        x_s = 1.0 + squash * 0.18
        k = 1.0 if appear is None else appear(i)
        f.location = (p.x, p.y, p.z - squash * 0.04 * (p.z - 0.5))
        f.scale = (sc * x_s * k, sc * x_s * k, sc * z_s * k)
        f.rotation_euler = (0.3 * math.sin(i), 0.4 * math.cos(i * 2), i * 0.7)
