"""Pre-rendered sprites for scavenger-2d: colour (albedo x baked AO), screen-space normal map, emissive layer.

Camera = the 3D game's: orthographic, Godot Camera3D.rotation_degrees (-30, 45, 0): 30 degrees down, looking from
+x+z towards -x-z (Blender: rotation_euler (60, 0, 45) degrees). 64 px per metre. Cycles renders data passes only
(diffuse colour, AO, normal, emission, alpha); numpy composes the PNGs, so no scene light ever reaches a sprite.
"""
import math
import os
import struct
import tempfile
import zlib

import bpy
import numpy as np
from mathutils import Vector

PX_PER_M = 64
MARGIN = 3
CAM_DIST = 120.0
EMIT_STRENGTH = 4.0
AO_MIX = 0.7          # colour = albedo * (1 - AO_MIX + AO_MIX * ao)


# ---------------------------------------------------------------------------------------------------------------
# PNG writing (no dependency on Blender's image colour management)
# ---------------------------------------------------------------------------------------------------------------
def write_png(path, img):
    """img: uint8 array (H, W, 3|4), top row first."""
    h, w, c = img.shape
    raw = b"".join(b"\x00" + img[y].tobytes() for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6 if c == 4 else 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)


def to_srgb8(lin):
    lin = np.clip(lin, 0.0, 1.0)
    s = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)
    return np.clip(np.round(s * 255.0), 0, 255).astype(np.uint8)


def to_u8(v):
    return np.clip(np.round(np.clip(v, 0, 1) * 255.0), 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------------------------------------------
# Scene setup
# ---------------------------------------------------------------------------------------------------------------
def use_gpu(scene):
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = kind
            except TypeError:
                continue
            prefs.get_devices()
            devs = [d for d in prefs.devices if d.type == kind]
            if devs:
                for d in prefs.devices:
                    d.use = d.type == kind
                scene.cycles.device = "GPU"
                return kind
    except Exception as exc:  # noqa: BLE001 - any failure falls back to CPU
        print("sprites: GPU setup failed, using CPU:", exc)
    scene.cycles.device = "CPU"
    return "CPU"


class SpriteRig:
    def __init__(self, tmpdir=None):
        scene = bpy.context.scene
        self.scene = scene
        self.tmp = tmpdir or tempfile.mkdtemp(prefix="sc_sprites_")
        scene.render.engine = "CYCLES"
        self.device = use_gpu(scene)
        c = scene.cycles
        c.samples = 48
        c.use_adaptive_sampling = False
        c.use_denoising = False
        c.max_bounces = 0
        c.diffuse_bounces = 0
        c.glossy_bounces = 0
        c.transmission_bounces = 0
        c.transparent_max_bounces = 4
        c.pixel_filter_type = "BLACKMAN_HARRIS"
        c.filter_width = 1.2
        scene.render.film_transparent = True
        scene.render.resolution_percentage = 100
        scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1.0
        scene.view_settings.view_transform = "Standard"
        if scene.world is None:
            scene.world = bpy.data.worlds.new("World")
        scene.world.use_nodes = True
        bg = scene.world.node_tree.nodes.get("Background")
        if bg:
            bg.inputs["Color"].default_value = (0, 0, 0, 1)
            bg.inputs["Strength"].default_value = 0.0
        vl = scene.view_layers[0]
        vl.use_pass_normal = True
        vl.use_pass_ambient_occlusion = True
        vl.use_pass_diffuse_color = True
        vl.use_pass_emit = True
        # camera
        cam_data = bpy.data.cameras.new("sprite_cam")
        cam_data.type = "ORTHO"
        cam_data.sensor_fit = "HORIZONTAL"
        cam_data.clip_start = 1.0
        cam_data.clip_end = CAM_DIST * 2
        self.cam = bpy.data.objects.new("sprite_cam", cam_data)
        scene.collection.objects.link(self.cam)
        self.cam.rotation_euler = (math.radians(60), 0.0, math.radians(45))
        scene.camera = self.cam
        bpy.context.view_layer.update()
        m = self.cam.matrix_world.to_3x3()
        self.right, self.up, self.back = m.col[0].normalized(), m.col[1].normalized(), m.col[2].normalized()
        # an AO-only ground: invisible to the camera, but it darkens the AO where things meet the ground
        me = bpy.data.meshes.new("ao_ground")
        s = 60.0
        me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
        self.ground = bpy.data.objects.new("ao_ground", me)
        self.ground.visible_camera = False
        scene.collection.objects.link(self.ground)
        # compositor: every pass to its own float EXR
        scene.use_nodes = True
        tree = scene.node_tree
        for n in list(tree.nodes):
            tree.nodes.remove(n)
        rl = tree.nodes.new("CompositorNodeRLayers")
        comp = tree.nodes.new("CompositorNodeComposite")
        tree.links.new(rl.outputs["Image"], comp.inputs["Image"])
        fo = tree.nodes.new("CompositorNodeOutputFile")
        fo.base_path = self.tmp
        fo.format.file_format = "OPEN_EXR"
        fo.format.color_depth = "32"
        fo.format.color_mode = "RGBA"
        # (file_slots.clear() leaks a block in Blender 4.4, so the default slot is renamed instead)
        fo.file_slots[0].path = "img"
        tree.links.new(rl.outputs["Image"], fo.inputs[0])
        for slot, out in (("nrm", "Normal"), ("ao", "AO"), ("dif", "DiffCol"), ("emi", "Emit")):
            fo.file_slots.new(slot)
            tree.links.new(rl.outputs[out], fo.inputs[slot])
        scene.frame_current = 1

    def remove_helpers(self):
        bpy.data.objects.remove(self.ground, do_unlink=True)
        bpy.data.objects.remove(self.cam, do_unlink=True)

    # --- projection ---
    def project_bounds(self, asset):
        r, u = self.right, self.up
        xs, ys = [], []
        for ob in asset.objects():
            if ob.type != "MESH":
                continue
            mw = ob.matrix_world
            for v in ob.data.vertices:
                p = mw @ v.co
                xs.append(p.dot(r))
                ys.append(p.dot(u))
        return min(xs), max(xs), min(ys), max(ys)

    def frame_layout(self, asset, set_dir):
        """Image size and ground-origin pixel covering every dir and frame of the asset."""
        b = [0.0, 0.0, 0.0, 0.0]   # the ground origin is always inside the image
        for d in range(asset.dirs):
            for anim, a in asset.anims.items():
                for i in range(a["frames"]):
                    asset.pose(anim, i / a["frames"])
                    set_dir(d)
                    x0, x1, y0, y1 = self.project_bounds(asset)
                    b = [min(b[0], x0), max(b[1], x1), min(b[2], y0), max(b[3], y1)]
        set_dir(0)
        ox = math.ceil(-b[0] * PX_PER_M) + MARGIN
        oy = math.ceil(b[3] * PX_PER_M) + MARGIN
        w = ox + math.ceil(b[1] * PX_PER_M) + MARGIN
        h = oy + math.ceil(-b[2] * PX_PER_M) + MARGIN
        return w, h, ox, oy

    def place_camera(self, w, h, ox, oy):
        sc = self.scene
        sc.render.resolution_x, sc.render.resolution_y = w, h
        self.cam.data.ortho_scale = w / PX_PER_M
        a = (w / 2 - ox) / PX_PER_M
        b = (oy - h / 2) / PX_PER_M
        self.cam.location = self.right * a + self.up * b + self.back * CAM_DIST
        bpy.context.view_layer.update()

    # --- render one frame ---
    def _load(self, slot, w, h):
        path = os.path.join(self.tmp, f"{slot}0001.exr")
        img = bpy.data.images.load(path, check_existing=False)
        buf = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(buf)
        bpy.data.images.remove(img)
        return buf.reshape(h, w, 4)[::-1]

    def render(self, w, h, ao_distance):
        self.scene.world.light_settings.distance = ao_distance
        bpy.ops.render.render(write_still=False)
        img = self._load("img", w, h)
        nrm = self._load("nrm", w, h)
        ao = self._load("ao", w, h)
        dif = self._load("dif", w, h)
        emi = self._load("emi", w, h)
        a = np.clip(img[..., 3], 0, 1)
        inv = np.where(a > 1e-4, 1.0 / np.maximum(a, 1e-4), 0.0)[..., None]
        # colour: albedo with baked AO
        albedo = dif[..., :3] * inv
        aov = np.clip(ao[..., :1] * inv, 0, 1)
        col = albedo * (1.0 - AO_MIX + AO_MIX * aov)
        colour = np.dstack([to_srgb8(col), to_u8(a)])
        colour[a <= 1e-4] = 0
        # normal: world -> screen (x right, y up, z towards the viewer), 0..1
        nw = nrm[..., :3] * inv
        R, U, B = (np.array(v[:], dtype=np.float32) for v in (self.right, self.up, self.back))
        ns = np.stack([nw @ R, nw @ U, nw @ B], axis=-1)
        ln = np.linalg.norm(ns, axis=-1, keepdims=True)
        ns = np.where(ln > 1e-4, ns / np.maximum(ln, 1e-4), np.array([0, 0, 1], dtype=np.float32))
        ns[a <= 1e-3] = (0, 0, 1)
        normal = to_u8(ns * 0.5 + 0.5)
        # emissive: emission colour, alpha = how much of the pixel glows
        e = emi[..., :3] / EMIT_STRENGTH
        ea = np.clip(e.max(axis=-1), 0, 1)
        erg = e / np.maximum(ea, 1e-4)[..., None]
        emissive = np.dstack([to_srgb8(erg), to_u8(ea)])
        emissive[ea <= 1e-3] = 0
        return colour, normal, emissive, bool((ea > 0.02).any())


# ---------------------------------------------------------------------------------------------------------------
# Whole asset
# ---------------------------------------------------------------------------------------------------------------
def actor_dir(asset, k):
    # sim heading k*45 deg: 0 = +x, increasing towards +z (= Blender -Y), i.e. clockwise seen from above
    asset.root.rotation_euler = (0, 0, -math.radians(45 * k))
    bpy.context.view_layer.update()


def prop_dir(asset, d):
    # rot = d*90 deg about +y, as Godot's rotation_degrees.y = rot (+x turns towards -z = Blender +Y)
    asset.root.rotation_euler = (0, 0, math.radians(90 * d))
    bpy.context.view_layer.update()


def render_asset(rig, asset, out_dir, ao_distance, has_emissive):
    set_dir = (lambda d: actor_dir(asset, d)) if asset.kind == "actor" else (lambda d: prop_dir(asset, d))
    w, h, ox, oy = rig.frame_layout(asset, set_dir)
    rig.place_camera(w, h, ox, oy)
    folder = os.path.join(out_dir, asset.name)
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        if f.endswith(".png"):
            os.remove(os.path.join(folder, f))
    previews = {}
    for anim, a in asset.anims.items():
        for d in range(asset.dirs):
            for i in range(a["frames"]):
                asset.pose(anim, i / a["frames"])
                set_dir(d)
                colour, normal, emissive, _ = rig.render(w, h, ao_distance)
                stem = os.path.join(folder, f"{anim}_{d}_{i}")
                write_png(stem + ".png", colour)
                write_png(stem + "_n.png", normal)
                if has_emissive:
                    write_png(stem + "_e.png", emissive)
                previews[(anim, d, i)] = (colour, normal, emissive)
    set_dir(0)
    if asset.rest:
        asset.rest()
    entry = {
        "kind": asset.kind,
        "size": [w, h],
        "origin": [ox, oy],
        "dirs": asset.dirs,
        "anims": {n: {"frames": a["frames"], "fps": a["fps"], "loop": a["loop"]} for n, a in asset.anims.items()},
        "emissive": has_emissive,
    }
    return entry, previews
