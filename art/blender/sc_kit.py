"""Scavenger model kit: palette, a small mesh builder with per-face colours, materials, animation keying and export.

Conventions (README.md):
- Blender metres, +Z up. glTF/Godot +Y up; Blender +X = glTF +X, Blender -Y = glTF +Z (the sim's z, south).
- Actors face +X at rest. A prop's rot 0 is the model as built; its front (the side facing the street) is -Y.
- Origin of every asset = the ground point at its footprint centre (an Empty named after the asset is the root).
- Colour is a per-face colour attribute "Col" (glTF COLOR_0) on one opaque material, plus a double-sided foliage
  material and, for glowing parts (separate objects), one emissive material. No textures.
- Deterministic: every builder seeds its RNG from its name.
"""
import math
import random
import zlib

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

# ---------------------------------------------------------------------------------------------------------------
# Palette (sRGB hex). Placeholders: overgrown, crumbling concrete, moss, rust; a few faded anime pastels.
# ---------------------------------------------------------------------------------------------------------------
HEX = {
    "concrete": "9A958A", "concrete_dk": "6F6B63", "concrete_lt": "B8B2A4", "break": "C4BCA9",
    "plaster_cream": "C9B998", "plaster_blue": "8FA6AE", "plaster_pink": "C3A196",
    "roof_red": "7A4236", "roof_slate": "4C5761", "wood": "6E5038", "wood_dk": "4A3828", "bark": "4E3E31",
    "rust": "8E4D2B", "rust_dk": "5A321F", "rust_lt": "B26A3A", "metal": "6C6E70", "metal_dk": "3A3C3F",
    "moss": "5D7A2D", "moss_lt": "7F9C3B", "moss_dk": "3E5524",
    "leaf": "4E7B34", "leaf_lt": "7DA54A", "leaf_dk": "2E4D25", "grass": "8AA24A", "grass_dry": "A59D5A",
    "flower_w": "E8E2CF", "flower_y": "E3C14B",
    "void": "17181A", "glass": "22292E", "dirt": "5B5044", "ash": "3A3633", "stone": "7D7A74", "stone_dk": "5A5853",
    "robot": "D3CBB5", "robot_dk": "A49C88", "robot_accent": "C8652E", "joint": "3A3B3E",
    "drone": "6B5B4E", "can": "D6A01F", "can_dk": "8E6A1C", "car": "7FA0A3",
    "sign_blue": "2F5F8F", "sign_white": "E4E0D4",
}
EMIT_HEX = {"headlamp": "FFF1C8", "drone_eye": "FF2A14", "bulb": "FFC27A", "embers": "FF7A26"}
EMIT_STRENGTH = 4.0   # glTF emissive strength (KHR_materials_emissive_strength); the sprites divide it back out

MOSS = ("moss", "moss_lt", "moss_dk")


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def lin(h):
    h = HEX.get(h, h)
    return tuple(srgb_to_linear(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


def seed_of(name):
    return zlib.crc32(name.encode("utf-8"))


# ---------------------------------------------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------------------------------------------
MAT_OPAQUE, MAT_FOLIAGE = 0, 1


def vcol_material(name, double_sided, roughness):
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    col = nt.nodes.new("ShaderNodeVertexColor")
    col.layer_name = "Col"
    nt.links.new(col.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = 0.0
    mat.use_backface_culling = not double_sided   # glTF doubleSided = not culling
    return mat


def base_materials():
    return [vcol_material("sc_opaque", False, 0.85), vcol_material("sc_foliage", True, 0.7)]


def emit_material(key):
    name = "sc_emit_" + key
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    c = lin(EMIT_HEX[key])
    bsdf.inputs["Base Color"].default_value = (c[0] * 0.5, c[1] * 0.5, c[2] * 0.5, 1.0)
    bsdf.inputs["Emission Color"].default_value = c + (1.0,)
    bsdf.inputs["Emission Strength"].default_value = EMIT_STRENGTH
    bsdf.inputs["Roughness"].default_value = 0.4
    mat.use_backface_culling = True
    return mat


# ---------------------------------------------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------------------------------------------
def axis_matrix(p0, p1):
    """Maps a Z-aligned primitive centred at the origin onto the segment p0-p1."""
    p0, p1 = Vector(p0), Vector(p1)
    rot = (p1 - p0).normalized().to_track_quat("Z", "Y").to_matrix().to_4x4()
    return Matrix.Translation((p0 + p1) * 0.5) @ rot


def trs(loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    return (Matrix.Translation(Vector(loc)) @ Euler(rot).to_matrix().to_4x4()
            @ Matrix.Diagonal(Vector(scale).to_4d()))


def _faces_of(verts):
    fs = set()
    for v in verts:
        fs.update(v.link_faces)
    return list(fs)


class MB:
    """One mesh under construction: bmesh plus a colour per face (an index into self.cols)."""

    def __init__(self, name, jitter=0.06):
        self.name = name
        self.bm = bmesh.new()
        self.cl = self.bm.faces.layers.int.new("cid")
        self.cols, self._cmap = [], {}
        self.rng = random.Random(seed_of(name))
        self.jitter = jitter

    def cid(self, col):
        if col not in self._cmap:
            self._cmap[col] = len(self.cols)
            self.cols.append(lin(col) if isinstance(col, str) else tuple(col))
        return self._cmap[col]

    def paint(self, faces, col, mat=MAT_OPAQUE, smooth=False):
        c = self.cid(col)
        for f in faces:
            f[self.cl] = c
            f.material_index = mat
            f.smooth = smooth
        return faces

    # --- primitives (all return their faces) ---
    def box(self, center, size, col, rot=(0, 0, 0), bevel=0.0, edge_col=None, taper=None):
        """A box; `taper` (sx, sy) scales the top face. Bevel chamfers get `edge_col` (worn edges)."""
        m = trs(center, rot, size)
        verts = bmesh.ops.create_cube(self.bm, size=1.0, matrix=Matrix.Identity(4))["verts"]
        if taper:
            for v in verts:
                if v.co.z > 0:
                    v.co.x *= taper[0]
                    v.co.y *= taper[1]
        bmesh.ops.transform(self.bm, matrix=m, verts=verts)
        faces = self.paint(_faces_of(verts), col)
        if bevel > 0:
            edges = list({e for v in verts for e in v.link_edges})
            res = bmesh.ops.bevel(self.bm, geom=edges, offset=bevel, segments=1, affect="EDGES",
                                  profile=0.5, clamp_overlap=True)
            self.paint(res["faces"], edge_col or col)
            faces = _faces_of(res["verts"]) if res["verts"] else faces
        return faces

    def cyl(self, p0, p1, r, col, segs=8, r2=None, caps=True, smooth=False):
        L = (Vector(p1) - Vector(p0)).length
        verts = bmesh.ops.create_cone(self.bm, cap_ends=caps, cap_tris=False, segments=segs, radius1=r,
                                      radius2=r if r2 is None else r2, depth=L,
                                      matrix=axis_matrix(p0, p1))["verts"]
        faces = _faces_of(verts)
        self.paint(faces, col, smooth=smooth)
        return faces, verts

    def blob(self, center, radius, col, subdiv=1, squash=(1, 1, 1), noise=0.18, mat=MAT_OPAQUE, smooth=True,
             cols=None):
        verts = bmesh.ops.create_icosphere(self.bm, subdivisions=subdiv, radius=1.0,
                                           matrix=Matrix.Identity(4))["verts"]
        rng = self.rng
        for v in verts:
            v.co *= 1.0 + rng.uniform(-noise, noise)
        bmesh.ops.transform(self.bm, matrix=trs(center, (0, 0, rng.uniform(0, 6.28)),
                                                (radius * squash[0], radius * squash[1], radius * squash[2])),
                            verts=verts)
        faces = _faces_of(verts)
        self.paint(faces, col, mat, smooth)
        if cols:
            for f in faces:
                self.paint([f], rng.choice(cols), mat, smooth)
        return faces

    def quad(self, pts, col, mat=MAT_OPAQUE):
        vs = [self.bm.verts.new(Vector(p)) for p in pts]
        f = self.bm.faces.new(vs)
        self.paint([f], col, mat)
        return [f]

    def leaf(self, base, direction, length, width, col):
        """A diamond leaf card (double-sided foliage material)."""
        d = Vector(direction).normalized()
        side = d.cross(Vector((0, 0, 1)))
        if side.length < 1e-4:
            side = Vector((1, 0, 0))
        side.normalize()
        b = Vector(base)
        mid = b + d * length * 0.45
        return self.quad([b, mid + side * width * 0.5, b + d * length, mid - side * width * 0.5], col, MAT_FOLIAGE)

    def tuft(self, base, height, col_list, blades=6, spread=0.12):
        """Grass blades: single triangles leaning outwards."""
        rng = self.rng
        b = Vector(base)
        for _ in range(blades):
            a = rng.uniform(0, math.tau)
            lean = Vector((math.cos(a), math.sin(a), 0))
            h = height * rng.uniform(0.6, 1.0)
            w = height * 0.12
            p = b + lean * rng.uniform(0, spread)
            side = Vector((-lean.y, lean.x, 0))
            tip = p + lean * h * rng.uniform(0.25, 0.6) + Vector((0, 0, h))
            self.quad([p - side * w, p + side * w, tip], rng.choice(col_list), MAT_FOLIAGE)

    def sprig(self, base, height, col_list, leaves=5):
        """A small plant: a few leaves fanning up from one point."""
        rng = self.rng
        for i in range(leaves):
            a = i / leaves * math.tau + rng.uniform(-0.3, 0.3)
            d = Vector((math.cos(a) * 0.7, math.sin(a) * 0.7, rng.uniform(0.6, 1.2)))
            self.leaf(base, d, height * rng.uniform(0.7, 1.1), height * 0.45, rng.choice(col_list))

    def rebar(self, base, direction, length, col="rust_dk", bend=0.4, r=0.012):
        d = Vector(direction).normalized()
        mid = Vector(base) + d * length * 0.6
        tip_dir = (d + Vector((self.rng.uniform(-bend, bend), self.rng.uniform(-bend, bend), 0))).normalized()
        self.cyl(base, mid, r, col, segs=4)
        self.cyl(mid, mid + tip_dir * length * 0.4, r, col, segs=4)

    def rubble(self, center, radius, count, cols, size=(0.08, 0.3), zscale=0.6):
        rng = self.rng
        c = Vector(center)
        for _ in range(count):
            a, rr = rng.uniform(0, math.tau), radius * math.sqrt(rng.random())
            s = rng.uniform(*size)
            h = max(0.0, (1 - rr / radius)) * radius * 0.35
            p = c + Vector((math.cos(a) * rr, math.sin(a) * rr, h + s * 0.3 * zscale))
            if rng.random() < 0.5:
                self.box(p, (s, s * rng.uniform(0.5, 1.2), s * zscale), rng.choice(cols),
                         rot=(rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4), rng.uniform(0, 3)))
            else:
                self.blob(p, s * 0.6, rng.choice(cols), subdiv=1, squash=(1, 1, zscale), smooth=False)

    def vine(self, top, bottom_z, normal, cols, step=0.22, wander=0.25, leaf=0.16):
        """Leaves hanging down a wall from `top` to `bottom_z`; `normal` points out of the wall."""
        rng = self.rng
        n = Vector(normal).normalized()
        side = Vector((-n.y, n.x, 0))
        p = Vector(top)
        while p.z > bottom_z:
            for _ in range(2):
                d = (n * 0.5 + side * rng.uniform(-1, 1) + Vector((0, 0, rng.uniform(-1.0, 0.2)))).normalized()
                self.leaf(p + n * 0.02, d, leaf * rng.uniform(0.7, 1.3), leaf * 0.6, rng.choice(cols))
            p = p + Vector((0, 0, -step)) + side * rng.uniform(-wander, wander) * step

    def transform_all(self, m):
        bmesh.ops.transform(self.bm, matrix=m, verts=list(self.bm.verts))

    # --- surface passes ---
    def overgrow(self, prob_top=0.6, prob_side=0.0, side_pred=None, cols=MOSS, min_up=0.65, faces=None):
        """Turn upward faces (and optionally side faces chosen by side_pred(center, normal)) to moss."""
        rng = self.rng
        self.bm.normal_update()
        for f in (faces or list(self.bm.faces)):
            if f.material_index != MAT_OPAQUE:
                continue
            n, c = f.normal, f.calc_center_median()
            if n.z >= min_up and rng.random() < prob_top:
                self.paint([f], rng.choice(cols), smooth=f.smooth)
            elif side_pred is not None and side_pred(c, n) and rng.random() < prob_side:
                self.paint([f], rng.choice(cols), smooth=f.smooth)

    def splotch(self, pred, cols, prob):
        """Recolour faces whose centre/normal satisfy pred (rust patches, dirt bands)."""
        rng = self.rng
        self.bm.normal_update()
        for f in list(self.bm.faces):
            if f.material_index == MAT_OPAQUE and pred(f.calc_center_median(), f.normal) and rng.random() < prob:
                self.paint([f], rng.choice(cols), smooth=f.smooth)

    # --- finish ---
    def to_object(self, name=None, parent=None, loc=(0, 0, 0), mats=None):
        name = name or self.name
        me = bpy.data.meshes.new(name)
        self.bm.normal_update()
        self.bm.to_mesh(me)
        nf = len(me.polygons)
        rng = random.Random(seed_of(name) + 7)
        face_cols = []
        cl_vals = [f[self.cl] for f in self.bm.faces]
        for i in range(nf):
            base = self.cols[cl_vals[i]]
            k = 1.0 + rng.uniform(-self.jitter, self.jitter)
            face_cols.append(tuple(min(1.0, ch * k) for ch in base))
        attr = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
        flat = []
        for poly in me.polygons:
            c = face_cols[poly.index]
            for _ in range(poly.loop_total):
                flat.extend((c[0], c[1], c[2], 1.0))
        attr.data.foreach_set("color", flat)
        me.color_attributes.active_color = attr
        me.color_attributes.render_color_index = 0
        for m in (mats or base_materials()):
            me.materials.append(m)
        self.bm.free()
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        ob.parent = parent
        ob.location = loc
        return ob


def emit_object(name, key, build, parent=None, loc=(0, 0, 0)):
    """A glowing part: `build(bm)` fills a bmesh; one emissive material, no colour attribute."""
    bm = bmesh.new()
    build(bm)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(emit_material(key))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = parent
    ob.location = loc
    ob["emissive"] = key
    return ob


def empty(name, parent=None, loc=(0, 0, 0)):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_size = 0.2
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = parent
    ob.location = loc
    return ob


def reset_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.actions, bpy.data.cameras, bpy.data.images):
        for b in list(coll):
            coll.remove(b)


def descendants(root):
    out = [root]
    for c in root.children:
        out.extend(descendants(c))
    return out


# ---------------------------------------------------------------------------------------------------------------
# Asset record, animation keying and export
# ---------------------------------------------------------------------------------------------------------------
class Asset:
    """A built asset. anims: name -> dict(frames (sprites), fps (sprites), loop, seconds (glTF), pose(t))."""

    def __init__(self, name, root, kind, dirs, anims=None, rest=None):
        self.name, self.root, self.kind, self.dirs = name, root, kind, dirs
        self.anims = anims or {"static": dict(frames=1, fps=1, loop=False, seconds=0, pose=None)}
        self.rest = rest   # callable that restores the rest pose

    def pose(self, anim, t):
        if self.rest:
            self.rest()
        fn = self.anims[anim]["pose"]
        if fn:
            fn(t)
        bpy.context.view_layer.update()

    def objects(self):
        return descendants(self.root)


def key_animations(asset, animated, fps=24):
    """Keys every anim of `asset` on the `animated` objects and pushes each into an NLA track of the anim's name
    (glTF export mode NLA_TRACKS merges same-named tracks across objects into one animation)."""
    scene = bpy.context.scene
    scene.render.fps = fps
    for name, a in asset.anims.items():
        if not a["pose"] or a["seconds"] <= 0:
            continue
        nkeys = max(1, round(a["seconds"] * fps))
        acts = {}
        for ob in animated:
            ob.animation_data_create()
            act = bpy.data.actions.new(f"{ob.name}_{name}")
            ob.animation_data.action = act
            acts[ob.name] = act
        for k in range(nkeys + 1):
            t = k / nkeys   # loops: pose(1) == pose(0) visually, so the last key closes the cycle smoothly
            asset.pose(name, t)
            for ob in animated:
                ob.keyframe_insert("location", frame=k + 1)
                ob.keyframe_insert("rotation_euler", frame=k + 1)
                ob.keyframe_insert("scale", frame=k + 1)
        for ob in animated:
            act = acts[ob.name]
            track = ob.animation_data.nla_tracks.new()
            track.name = name
            track.strips.new(name, 1, act)
            ob.animation_data.action = None
    if asset.rest:
        asset.rest()


def export_glb(asset, path):
    bpy.ops.object.select_all(action="DESELECT")
    for ob in asset.objects():
        ob.select_set(True)
    has_anim = any(a["pose"] for a in asset.anims.values())
    bpy.ops.export_scene.gltf(
        filepath=path, export_format="GLB", use_selection=True, export_cameras=False, export_lights=False,
        export_yup=True, export_apply=False, export_animations=has_anim,
        export_animation_mode="NLA_TRACKS", export_extras=False, export_vertex_color="MATERIAL",
    )


def tri_count(asset):
    n = 0
    for ob in asset.objects():
        if ob.type == "MESH":
            n += sum(len(p.vertices) - 2 for p in ob.data.polygons)
    return n


def material_count(asset):
    used = set()
    for ob in asset.objects():
        if ob.type == "MESH":
            for p in ob.data.polygons:
                used.add(ob.data.materials[p.material_index].name)
    return len(used)


def mesh_count(asset):
    return sum(1 for ob in asset.objects() if ob.type == "MESH")
