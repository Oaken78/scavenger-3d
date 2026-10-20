"""Builds every Scavenger model from factory startup: glTF for scavenger-3d, sprites for scavenger-2d, review sheets.

./tools/blender.ps1 -Script <abs>/art/blender/build_all.py -TimeoutSec 3000 -- --sprites <scavenger-2d>/assets/sprites
  --models DIR    glb output (default: this game's assets/models)
  --sprites DIR   sprite output + manifest.json (omit to skip the sprites)
  --renders DIR   contact sheets (default: art/blender/renders)
  --only a,b      build only these assets (the manifest keeps the other entries)
"""
import json
import os
import struct
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

import sc_kit  # noqa: E402
import sc_sprites  # noqa: E402
from sc_actors import ACTORS  # noqa: E402

try:
    from sc_props import PROPS  # noqa: E402
except ImportError:
    PROPS = {}

ORDER = ["robot", "scrap_drone", "fuel_canister", "house_ruin_a", "house_ruin_b", "subway_entrance", "car_wreck",
         "street_lamp", "campfire", "tree", "bush"]
BUILDERS = dict(ACTORS, **PROPS)


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts = {"models": os.path.normpath(os.path.join(HERE, "..", "..", "assets", "models")), "sprites": None,
            "renders": os.path.join(HERE, "renders"), "only": None}
    i = 0
    while i < len(argv):
        key = argv[i].lstrip("-")
        opts[key] = argv[i + 1]
        i += 2
    if opts["only"]:
        opts["only"] = [s.strip() for s in opts["only"].split(",") if s.strip()]
    return opts


def read_png(path):
    """Reads PNGs written by sc_sprites.write_png (8-bit, filter 0 rows)."""
    data = open(path, "rb").read()
    pos, idat = 8, b""
    w = h = c = 0
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        if tag == b"IHDR":
            w, h, _, ctype = struct.unpack(">IIBB", body[:10])
            c = 4 if ctype == 6 else 3
        elif tag == b"IDAT":
            idat += body
        pos += 12 + ln
    raw = zlib.decompress(idat)
    rows = np.frombuffer(raw, dtype=np.uint8).reshape(h, 1 + w * c)
    return rows[:, 1:].reshape(h, w, c).copy()


def downscale(img, f):
    if f <= 1:
        return img
    h, w = img.shape[0] // f * f, img.shape[1] // f * f
    x = img[:h, :w].astype(np.float32).reshape(h // f, f, w // f, f, img.shape[2]).mean(axis=(1, 3))
    return np.round(x).astype(np.uint8)


def compose_rows(rows, bg=(58, 64, 78), pad=8):
    """rows: list of lists of RGBA uint8 images -> one RGB image."""
    widths = [sum(im.shape[1] + pad for im in r) + pad for r in rows]
    heights = [max(im.shape[0] for im in r) + pad for r in rows]
    W, H = max(widths), sum(heights) + pad
    out = np.zeros((H, W, 3), dtype=np.float32)
    out[:] = bg
    y = pad
    for r, rh in zip(rows, heights):
        x = pad
        for im in r:
            h, w = im.shape[:2]
            a = im[..., 3:4].astype(np.float32) / 255.0
            out[y:y + h, x:x + w] = out[y:y + h, x:x + w] * (1 - a) + im[..., :3].astype(np.float32) * a
            x += w + pad
        y += rh
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


def lit(colour, normal, light=(1.0, 0.25, 0.45)):
    """Colour shaded by its normal map with a light from the screen's right (the normal convention check)."""
    L = np.array(light, dtype=np.float32)
    L /= np.linalg.norm(L)
    n = normal.astype(np.float32) / 255.0 * 2.0 - 1.0   # x right, y up, z to viewer
    d = np.clip(n @ L, 0, 1)[..., None]
    rgb = colour[..., :3].astype(np.float32) * (0.15 + 0.95 * d)
    return np.dstack([np.clip(rgb, 0, 255).astype(np.uint8), colour[..., 3]])


def review_sheets(sprites, renders, manifest):
    os.makedirs(renders, exist_ok=True)
    rows, lit_rows = [], []
    for name in ORDER:
        e = manifest["assets"].get(name)
        if not e:
            continue
        anim = next(iter(e["anims"]))
        f = max(1, -(-e["size"][1] // 420))
        cells = [read_png(os.path.join(sprites, name, f"{anim}_{d}_0.png")) for d in range(e["dirs"])]
        rows.append([downscale(c, f) for c in cells])
        lit_rows.append([downscale(lit(c, read_png(os.path.join(sprites, name, f"{anim}_{d}_0_n.png"))), f)
                         for d, c in enumerate(cells)])
        if name == "robot":
            for a in ("walk", "attack"):
                rows.append([read_png(os.path.join(sprites, name, f"{a}_1_{i}.png"))
                             for i in range(e["anims"][a]["frames"])])
    sc_sprites.write_png(os.path.join(renders, "contact_sheet.png"), compose_rows(rows))
    sc_sprites.write_png(os.path.join(renders, "lit_check.png"), compose_rows(lit_rows, bg=(20, 22, 28)))
    if "robot" in manifest["assets"]:
        big = [np.kron(read_png(os.path.join(sprites, "robot", f"idle_{d}_0.png")), np.ones((2, 2, 1), np.uint8))
               for d in range(8)]
        sc_sprites.write_png(os.path.join(renders, "robot_8dirs.png"), compose_rows([big[:4], big[4:]]))


def main():
    opts = parse_args()
    names = [n for n in ORDER if n in BUILDERS and (not opts["only"] or n in opts["only"])]
    os.makedirs(opts["models"], exist_ok=True)
    manifest = None
    if opts["sprites"]:
        mpath = os.path.join(opts["sprites"], "manifest.json")
        manifest = json.load(open(mpath)) if os.path.exists(mpath) else {"assets": {}}
    t_all = time.time()
    stats = []
    for name in names:
        t0 = time.time()
        sc_kit.reset_scene()
        asset = BUILDERS[name]()
        tris, meshes, mats = sc_kit.tri_count(asset), sc_kit.mesh_count(asset), sc_kit.material_count(asset)
        emissive = any(o.get("emissive") for o in asset.objects())
        if manifest is not None:
            rig = sc_sprites.SpriteRig()
            ao = getattr(asset, "ao_distance", 0.35)
            entry, _ = sc_sprites.render_asset(rig, asset, opts["sprites"], ao, emissive)
            if getattr(asset, "lights", None):
                entry["lights"] = {k: [round(v, 3) for v in p] for k, p in asset.lights.items()}
            manifest["assets"][name] = entry
            rig.remove_helpers()
            print(f"sprites: {name} {entry['size']} origin {entry['origin']} on {rig.device}")
        if getattr(asset, "for_export", None):
            asset.for_export()
        animated = getattr(asset, "animated", [])
        if animated:
            sc_kit.key_animations(asset, animated)
        sc_kit.export_glb(asset, os.path.join(opts["models"], name + ".glb"))
        dt = time.time() - t0
        stats.append((name, tris, meshes, mats, dt))
        print(f"built: {name} tris={tris} meshes={meshes} materials={mats} in {dt:.1f} s")
    if manifest is not None:
        manifest = {
            "px_per_m": sc_sprites.PX_PER_M,
            "camera": {"projection": "orthographic", "godot_rotation_degrees": [-30, 45, 0],
                       "note": "30 deg down, yaw 45, looking from +x+z towards -x-z; same as the 3D game"},
            "files": "<name>/<anim>_<dir>_<frame>.png colour (albedo x baked AO, straight alpha); "
                     "_n.png normal map; _e.png emissive layer (only when emissive is true), drawn unlit on top",
            "normal_map": "screen space: red = +right, green = +up on screen, blue = towards the viewer",
            "origin": "pixel of the asset's ground origin, from the image's top-left corner (pixel corners; "
                      "Sprite2D centered = false, offset = -origin)",
            "dirs_actor": "dir k = world heading k*45 deg (0 = +x, increasing towards +z, as in the sim)",
            "dirs_prop": "dir d = rot/90: the model turned d*90 deg about +y like Godot rotation_degrees.y = rot "
                         "(+x turns towards -z)",
            "frames": "frame i shows the animation at phase i/frames; fps is a suggested playback rate",
            "lights": "light anchors in metres relative to the ground origin at dir 0 (x, y up, z), glTF axes",
            "assets": {n: manifest["assets"][n] for n in ORDER if n in manifest["assets"]},
        }
        with open(os.path.join(opts["sprites"], "manifest.json"), "w", newline="\n") as f:
            json.dump(manifest, f, indent=2)
            f.write("\n")
        review_sheets(opts["sprites"], opts["renders"], manifest)
    print("STATS name tris meshes materials seconds")
    for s in stats:
        print("STATS %s %d %d %d %.1f" % s)
    print(f"build_all: {len(names)} assets in {time.time() - t_all:.1f} s")


main()
