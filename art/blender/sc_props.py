"""Props: house ruins, subway entrance, car wreck, street lamp, campfire, tree, bush.

Blender coords; footprint size [x, z] from design/layout.json maps to Blender (x, y). The street-facing front of a
prop at rot 0 is Blender -Y (glTF +Z). One opaque + one foliage material per prop; glowing parts are own nodes.
"""
import math

import bmesh
from mathutils import Matrix, Vector

from sc_kit import MB, MOSS, Asset, emit_object, empty, lin, trs

LEAVES = ("leaf", "leaf_lt", "leaf_dk", "moss_lt")
GRASS = ("grass", "grass_dry", "leaf_lt", "moss_lt")


def mix(a, b, f):
    a, b = lin(a), lin(b)
    return tuple(x + (y - x) * f for x, y in zip(a, b))


def clamp01(v):
    return max(0.0, min(1.0, v))


# ---------------------------------------------------------------------------------------------------------------
# Walls from slices: crumbled tops and openings come for free
# ---------------------------------------------------------------------------------------------------------------
def wall(mb, axis, fixed, u0, u1, z0, top_fn, thick, openings, cols, step=0.5):
    """Axis-aligned wall along `axis` ('x' or 'y') at the other coordinate `fixed`, from u0 to u1, built as
    vertical slices. top_fn(u) gives each slice's top; openings are (u_a, u_b, z_a, z_b)."""
    cuts = {u0, u1}
    for (a, b, _, _) in openings:
        cuts |= {a, b}
    n = max(1, math.ceil((u1 - u0) / step))
    cuts |= {u0 + (u1 - u0) * i / n for i in range(n)}
    cuts = sorted(c for c in cuts if u0 <= c <= u1)
    for a, b in zip(cuts, cuts[1:]):
        if b - a < 0.02:
            continue
        m = (a + b) / 2
        top = top_fn(m)
        if top <= z0 + 0.03:
            continue
        ivs = [(z0, top)]
        for (oa, ob, oz0, oz1) in openings:
            if oa <= m <= ob:
                new = []
                for (s, e) in ivs:
                    if oz1 <= s or oz0 >= e:
                        new.append((s, e))
                        continue
                    if oz0 > s:
                        new.append((s, oz0))
                    if oz1 < e:
                        new.append((oz1, e))
                ivs = new
        for s, e in ivs:
            if e - s < 0.04:
                continue
            c = (m, fixed, (s + e) / 2) if axis == "x" else (fixed, m, (s + e) / 2)
            size = (b - a, thick, e - s) if axis == "x" else (thick, b - a, e - s)
            mb.box(c, size, mb.rng.choice(cols))


def _house(name, sx, sy, h, wall_hex, roof_hex, side, door_u):
    """A two-storey suburban house ruin. `side` (+1/-1) picks the collapsed front corner (+X or -X)."""
    root = empty(name)
    mb = MB(name + "_ruin", jitter=0.07)
    rng = mb.rng
    hx, hy, T = sx / 2 - 0.2, sy / 2 - 0.2, 0.25
    roof_h = min(1.0, h * 0.17)
    wt = h - roof_h            # wall top
    st = wt / 2                # storey height
    eave = hy + 0.35
    wall_cols = (wall_hex, wall_hex, mix(wall_hex, "concrete_dk", 0.25), mix(wall_hex, "concrete", 0.4))
    break_cols = ("break", "concrete_lt", "concrete")

    def dmg(x, y):
        fx = clamp01((side * x - hx * 0.05) / (hx * 0.5))
        fy = clamp01((-y + hy * 0.35) / (hy * 0.8))
        return fx * fy

    def top_at(x, y, base):
        f = dmg(x, y)
        if f <= 0.02:
            return base
        low = st * rng.uniform(0.45, 1.05)
        return base - f * (base - low) + rng.uniform(-0.3, 0.05) * f

    win_g, win_u = (0.95, 1.9), (st + 0.8, st + 1.75)
    front_open = [(door_u - 0.5, door_u + 0.5, 0.0, 2.15)]
    for u in (-0.72 * hx, 0.0, 0.62 * hx):
        if abs(u - door_u) > 1.0:
            front_open.append((u - 0.5, u + 0.5) + win_g)
    for u in (-0.6 * hx, 0.0, 0.6 * hx):
        front_open.append((u - 0.5, u + 0.5) + win_u)
    back_open = [(u - 0.5, u + 0.5) + w for u in (-0.5 * hx, 0.5 * hx) for w in (win_g, win_u)]
    side_open = [(-0.5, 0.5) + win_g, (-0.4 * hy - 0.45, -0.4 * hy + 0.45) + win_u,
                 (0.4 * hy - 0.45, 0.4 * hy + 0.45) + win_u]
    walls = [
        ("x", -hy + T / 2, -hx, hx, front_open, lambda u: (u, -hy)),
        ("x", hy - T / 2, -hx, hx, back_open, lambda u: (u, hy)),
        ("y", -hx + T / 2, -hy + T, hy - T, side_open, lambda u: (-hx, u)),
        ("y", hx - T / 2, -hy + T, hy - T, side_open, lambda u: (hx, u)),
    ]
    for axis, fixed, u0, u1, opens, xy in walls:
        door = [o for o in opens if o[2] == 0.0]
        wall(mb, axis, fixed + (-0.02 if fixed < 0 else 0.02), u0, u1, 0.0, lambda u: 0.45, T + 0.04, door,
             ("concrete_dk", "concrete"))
        wall(mb, axis, fixed, u0, u1, 0.45, lambda u, xy=xy: top_at(*xy(u), wt), T, opens, wall_cols)
        # sills under windows that still stand, a crumbled top course on the damaged part
        for (a, b, z0, z1) in opens:
            if z0 > 0 and top_at(*xy((a + b) / 2), wt) > z1:
                out = -1 if fixed < 0 else 1
                c = ((a + b) / 2, fixed + out * 0.1, z0 - 0.05) if axis == "x" else \
                    (fixed + out * 0.1, (a + b) / 2, z0 - 0.05)
                sz = (b - a + 0.15, T + 0.1, 0.08) if axis == "x" else (T + 0.1, b - a + 0.15, 0.08)
                mb.box(c, sz, "concrete_lt")
    # boarded-up windows (front ground floor, the first window)
    a, b, z0, z1 = front_open[1]
    for i in range(3):
        mb.box(((a + b) / 2, -hy - 0.03, z0 + 0.2 + i * 0.3), (b - a + 0.2, 0.04, 0.14), "wood",
               rot=(0, rng.uniform(-0.25, 0.25), 0))
    # floors
    mb.box((0, 0, 0.03), (2 * hx - 0.1, 2 * hy - 0.1, 0.06), "concrete_dk")
    nx, ny = int(2 * hx), int(2 * hy)
    for i in range(nx):
        for j in range(ny):
            x = -hx + (i + 0.5) * (2 * hx / nx)
            y = -hy + (j + 0.5) * (2 * hy / ny)
            f = dmg(x, y)
            if f > 0.5 or (f > 0.3 and rng.random() < 0.6):
                continue
            tilt = (rng.uniform(-0.25, 0.25), rng.uniform(-0.25, 0.25), 0) if f > 0.2 else (0, 0, 0)
            mb.box((x, y, st - 0.1 - (0.15 if f > 0.2 else 0)), (2 * hx / nx, 2 * hy / ny, 0.2),
                   rng.choice(("concrete", "concrete_lt")), rot=tilt)
            if 0.15 < f <= 0.5:
                mb.rebar((x + side * 0.4, y - 0.4, st - 0.1), (side, -0.6, rng.uniform(-0.5, 0.2)), 0.6)
    # roof: tile strips on both slopes, rafters where they fell in
    pitch = math.atan2(h - wt, eave)
    slope = math.hypot(h - wt, eave) + 0.1
    nstrips = int((2 * hx + 0.6) / 0.9)
    sw = (2 * hx + 0.6) / nstrips
    for s in (-1, 1):
        for i in range(nstrips):
            x = -hx - 0.3 + (i + 0.5) * sw
            f = dmg(x, s * hy * 0.5) if s < 0 else dmg(x, -hy * 0.1) * 0.8
            cy, cz = s * eave / 2, wt + (h - wt) / 2 + 0.06
            if f > 0.3:
                if rng.random() < 0.7:   # a rafter, sometimes broken short
                    k = rng.uniform(0.4, 1.0)
                    mb.box((x, s * eave * (1 - k / 2), wt + (h - wt) * (k / 2) + 0.02), (0.09, slope * k, 0.12),
                           "wood_dk", rot=(-s * pitch, 0, 0))
                continue
            sag = (f * 1.5, rng.uniform(-0.05, 0.05)) if f > 0.12 else (0, 0)
            mb.box((x, cy, cz - sag[0] * 0.3), (sw - 0.02, slope, 0.12),
                   rng.choice((roof_hex, roof_hex, mix(roof_hex, "concrete_dk", 0.3))),
                   rot=(-s * pitch - s * sag[0] * 0.3, sag[1], 0))
    # ridge beam and gable ends
    for i in range(nstrips):
        x = -hx - 0.3 + (i + 0.5) * sw
        if dmg(x, -hy * 0.2) < 0.35:
            mb.box((x, 0, h - 0.02), (sw, 0.16, 0.12), "wood_dk")
    for gx in (-hx + T / 2, hx - T / 2):
        wall(mb, "y", gx, -hy, hy, wt, lambda u, gx=gx: wt + (h - wt - 0.1) * (1 - abs(u) / eave) -
             (st * 0.9 if dmg(gx, u) > 0.3 else 0.0), T, [], wall_cols, step=0.4)
    # chimney on the standing side
    cx = -side * hx * 0.55
    mb.box((cx, hy * 0.25, (wt + h) / 2 - 0.3), (0.55, 0.55, h - wt + 0.6), "concrete_dk")
    mb.box((cx, hy * 0.25, h - 0.08), (0.65, 0.65, 0.12), "concrete")
    # rubble at the collapsed corner, inside and out
    rub = ("concrete", "concrete_lt", "break", wall_hex, roof_hex)
    mb.rubble((side * hx * 0.65, -hy - 0.5, 0), 1.6, 34, rub, size=(0.12, 0.45))
    mb.rubble((side * hx * 0.5, -hy * 0.4, 0.05), 1.5, 26, rub, size=(0.15, 0.5))
    for k in range(2):   # fallen roof sheets
        mb.box((side * hx * (0.35 + 0.25 * k), -hy * 0.35 + k * 0.6, 0.45 + k * 0.3), (0.9, 1.8, 0.1), roof_hex,
               rot=(rng.uniform(0.4, 0.8), rng.uniform(-0.3, 0.3), rng.uniform(-0.5, 0.5)))
    for k in range(5):   # rebar out of the broken wall tops
        u = side * hx * rng.uniform(0.3, 0.95)
        mb.rebar((u, -hy + 0.1, top_at(u, -hy, wt)), (rng.uniform(-0.3, 0.3), -0.2, 1), rng.uniform(0.3, 0.6))
    mb.splotch(lambda c, n: abs(n.z) < 0.3 and c.z < 0.8, ("dirt", "concrete_dk", "moss_dk"), 0.35)
    mb.overgrow(prob_top=0.45, prob_side=0.25, side_pred=lambda c, n: c.z < 1.2 and abs(n.z) < 0.3)
    # vines down the walls, grass along the base, a few bushes
    for u in (-0.85 * hx, -0.2 * hx, 0.4 * hx):
        mb.vine((u, -hy - 0.02, top_at(u, -hy, wt) - 0.05), 0.3, (0, -1, 0), LEAVES)
    for u in (-0.6 * hy, 0.5 * hy):
        mb.vine((hx + 0.02, u, wt - 0.1), 0.6, (1, 0, 0), LEAVES)
        mb.vine((-hx - 0.02, u, wt - 0.2), 1.0, (-1, 0, 0), LEAVES)
    mb.vine((0.2 * hx, hy + 0.02, wt - 0.1), 0.4, (0, 1, 0), LEAVES)
    for k in range(26):
        t = rng.random()
        edge = rng.choice(((-hx + t * 2 * hx, -hy - 0.25), (hx + 0.25, -hy + t * 2 * hy),
                           (-hx - 0.25, -hy + t * 2 * hy), (-hx + t * 2 * hx, hy + 0.25)))
        mb.tuft((edge[0], edge[1], 0), rng.uniform(0.25, 0.5), GRASS, blades=7, spread=0.2)
    for p in ((-side * hx - 0.1, -hy - 0.3), (side * hx + 0.2, hy * 0.6)):
        mb.blob((p[0], p[1], 0.35), 0.45, "leaf", subdiv=2, squash=(1.2, 1, 0.8), cols=LEAVES)
    mb.to_object(name.replace("house_", "") , root)
    a = Asset(name, root, "prop", 4)
    a.ao_distance = 0.9
    return a


def house_ruin_a():
    return _house("house_ruin_a", 8, 7, 6, "plaster_cream", "roof_red", 1, -0.3 * 3.8)


def house_ruin_b():
    return _house("house_ruin_b", 7, 6, 5, "plaster_blue", "roof_slate", -1, 0.35 * 3.3)


# ---------------------------------------------------------------------------------------------------------------
# subway_entrance: 4 x 6 m, stairs entered from -Y going down towards +Y, rusty railing, a broken sign
# ---------------------------------------------------------------------------------------------------------------
def subway_entrance():
    root = empty("subway_entrance")
    mb = MB("entrance", jitter=0.07)
    rng = mb.rng
    iw, wall_t, top = 1.3, 0.35, 0.9
    y0, nsteps, run, rise = -2.6, 12, 0.3, 0.18
    depth = nsteps * rise
    for i in range(nsteps):   # steps darken as they go down
        z = -(i + 1) * rise
        f = (i + 1) / nsteps
        mb.box((0, y0 + (i + 0.5) * run, z + rise / 2 - 0.15), (2 * iw, run, 0.3 + rise),
               mix("concrete", "void", f * 0.75))
        if rng.random() < 0.4:
            mb.rubble((rng.uniform(-1, 1), y0 + (i + 0.5) * run, z + rise), 0.3, 3, ("concrete", "break"),
                      size=(0.08, 0.18))
    yl = y0 + nsteps * run
    mb.box((0, (yl + 3.0) / 2, -depth - 0.1), (2 * iw, 3.0 - yl, 0.2), mix("concrete", "void", 0.85))
    mb.box((0, 2.85, -depth / 2 + 0.2), (2 * iw + 0.2, 0.3, depth + 1.4), "concrete_dk")
    mb.box((0, 2.69, -depth + 1.0), (1.6, 0.04, 2.0), "void")                       # dark doorway
    for s in (-1, 1):
        x = s * (iw + wall_t / 2)
        mb.box((x, 0.2, (top - depth) / 2 - 0.1), (wall_t, 5.6, top + depth + 0.2), "concrete",
               bevel=0.03, edge_col="break")
        mb.box((x, 0.2, top + 0.04), (wall_t + 0.1, 5.7, 0.08), "concrete_lt")       # coping
        mb.box((s * (iw + wall_t + 0.17), 0.0, 0.02), (0.36, 6.0, 0.04), "concrete_dk")   # paving collar
        # railing: posts, a top and a mid rail; one bay bent outwards, one post gone
        posts = [y for y in (-2.5, -1.6, -0.7, 0.2, 1.1, 2.0, 2.9)]
        for k, y in enumerate(posts):
            if s > 0 and k == 4:
                continue
            mb.cyl((x, y, top + 0.08), (x, y, top + 0.95), 0.025, rng.choice(("rust", "rust_dk")), segs=5)
        for k, (ya, yb) in enumerate(zip(posts, posts[1:])):
            bend = 0.35 if (s > 0 and k in (3, 4)) else 0.0
            for zr in (0.95, 0.55):
                mb.cyl((x, ya, top + zr), (x + s * bend, (ya + yb) / 2, top + zr - bend * 0.6), 0.02, "rust", segs=4)
                mb.cyl((x + s * bend, (ya + yb) / 2, top + zr - bend * 0.6), (x, yb, top + zr), 0.02, "rust",
                       segs=4)
    mb.box((0, -3.0 + 0.2, 0.02), (2 * iw, 0.4, 0.04), "concrete_dk")
    # broken sign: a pole at the front left, the sign hanging askew, a snapped second pole
    mb.cyl((-1.75, -2.75, 0), (-1.75, -2.75, 2.75), 0.05, "metal_dk", segs=6)
    sign = trs((-1.55, -2.78, 2.45), (0, 0.42, 0.05))
    before = set(mb.bm.verts)
    mb.box((0, 0, 0), (1.0, 0.1, 0.55), "sign_blue")
    for (cx, cz, w, hh, r) in ((-0.2, 0, 0.07, 0.36, 0), (0.2, 0, 0.07, 0.36, 0), (-0.09, 0.06, 0.07, 0.25, 0.5),
                               (0.09, 0.06, 0.07, 0.25, -0.5)):    # a blocky white "M"
        mb.box((cx, -0.06, cz), (w, 0.02, hh), "sign_white", rot=(0, r, 0))
    bmesh.ops.transform(mb.bm, matrix=sign, verts=[v for v in mb.bm.verts if v not in before])
    mb.cyl((1.75, -2.75, 0), (1.78, -2.7, 1.1), 0.05, "metal_dk", segs=6)
    mb.cyl((1.78, -2.7, 1.1), (1.95, -2.5, 1.2), 0.04, "rust", segs=6)
    mb.splotch(lambda c, n: abs(n.z) < 0.3 and c.z > -0.5, ("dirt", "concrete_dk", "moss_dk"), 0.25)
    mb.overgrow(prob_top=0.55, cols=MOSS)
    for s in (-1, 1):
        for y in (-1.8, 0.5, 2.2):
            mb.vine((s * (iw - 0.02), y, top - 0.05), -1.2, (-s, 0, 0), LEAVES)
        for k in range(7):
            mb.tuft((s * rng.uniform(1.75, 1.95), rng.uniform(-2.8, 2.9), 0), rng.uniform(0.25, 0.45), GRASS,
                    blades=6, spread=0.12)
    mb.blob((1.7, 2.6, 0.3), 0.4, "leaf", subdiv=2, squash=(1, 1.2, 0.8), cols=LEAVES)
    mb.to_object("entrance", root)
    a = Asset("subway_entrance", root, "prop", 4)
    a.ground_hole = (-iw, iw, y0, 2.7)
    a.ao_distance = 0.7
    return a


# ---------------------------------------------------------------------------------------------------------------
# car_wreck: 4.2 x 1.9 m, front at +X, rusted, flat tyres, grass growing through
# ---------------------------------------------------------------------------------------------------------------
def car_wreck():
    root = empty("car_wreck")
    mb = MB("wreck", jitter=0.08)
    rng = mb.rng
    for (x, y) in ((1.3, 0.78), (1.3, -0.78), (-1.3, 0.78), (-1.3, -0.78)):
        faces, verts = mb.cyl((x, y - 0.11, 0.3), (x, y + 0.11, 0.3), 0.32, "ash", segs=12)
        for v in verts:
            if v.co.z < 0.1:
                v.co.z = 0.02 + (v.co.z - 0.0) * 0.15
        mb.cyl((x, y + (0.115 if y > 0 else -0.115), 0.3), (x, y + (0.12 if y > 0 else -0.12), 0.3), 0.17,
               "rust_dk", segs=8)
    mb.box((0.05, 0, 0.58), (4.05, 1.8, 0.56), "car", bevel=0.09, edge_col="rust")
    mb.box((1.45, 0, 0.88), (1.1, 1.66, 0.06), "car", rot=(0, 0.06, 0))                       # hood, ajar
    cab = mb.box((-0.35, 0, 1.13), (2.1, 1.62, 0.56), "car", taper=(0.78, 0.86))
    mb.bm.normal_update()
    for f in cab:
        if abs(f.normal.z) < 0.85:
            mb.paint([f], "glass")
    for xb, xt in ((0.7, 0.47), (-0.35, -0.35), (-1.4, -1.17)):   # pillars
        for s in (-1, 1):
            mb.cyl((xb, s * 0.8, 0.86), (xt, s * 0.7, 1.4), 0.045, "car", segs=4)
    for s in (1, -1):   # bumpers and lamps
        mb.box((s * 2.08, 0, 0.45), (0.12, 1.85, 0.16), "metal_dk")
        for y in (-0.6, 0.6):
            mb.cyl((s * 2.06, y, 0.68), (s * 2.1, y, 0.68), 0.09, "glass" if s > 0 else "rust", segs=8)
    mb.splotch(lambda c, n: True, ("rust", "rust_lt", "rust_dk"), 0.35)
    mb.splotch(lambda c, n: c.z < 0.6, ("rust_dk", "dirt"), 0.6)
    mb.overgrow(prob_top=0.45, cols=MOSS)
    mb.blob((-0.5, 0.2, 1.42), 0.32, "moss", squash=(1.4, 1, 0.3), cols=MOSS)
    for k in range(18):
        x, y = rng.uniform(-2.1, 2.1), rng.choice((-1, 1)) * rng.uniform(0.85, 1.05)
        mb.tuft((x, y, 0), rng.uniform(0.3, 0.6), GRASS, blades=7, spread=0.15)
    for (x, y) in ((1.3, 0.6), (1.3, -0.5), (-1.3, 0.6), (1.6, 0.0), (-2.0, 0.3)):
        mb.tuft((x, y, 0.6 if abs(x) < 1.6 else 0), 0.55, GRASS, blades=9, spread=0.25)
    mb.sprig((1.5, 0.1, 0.92), 0.35, LEAVES, leaves=7)                                       # out of the engine bay
    mb.sprig((-0.4, -0.3, 1.38), 0.22, LEAVES, leaves=5)
    mb.transform_all(trs((0, 0, 0), (0.025, -0.03, 0)))                                      # sits crooked
    mb.to_object("wreck", root)
    a = Asset("car_wreck", root, "prop", 4)
    a.ao_distance = 0.45
    return a


# ---------------------------------------------------------------------------------------------------------------
# street_lamp: 4.5 m, bent, bulb at 4.2 m on its own node, the arm reaching towards -Z (glTF) = Blender +Y
# ---------------------------------------------------------------------------------------------------------------
BULB = Vector((0.05, 1.15, 4.2))


def street_lamp():
    root = empty("street_lamp")
    mb = MB("lamp", jitter=0.06)
    rng = mb.rng
    mb.box((0, 0, 0.17), (0.32, 0.32, 0.34), "concrete", bevel=0.03, edge_col="break")
    pts = [Vector(p) for p in ((0, 0, 0.3), (0, 0, 2.3), (0.03, 0.18, 3.4), (0.05, 0.38, 4.28), (0.05, 0.8, 4.47),
                               (0.05, 1.12, 4.4))]
    radii = (0.08, 0.075, 0.07, 0.06, 0.05)
    for p0, p1, r in zip(pts, pts[1:], radii):
        mb.cyl(p0, p1, r, "metal", segs=8)
    mb.box((0.05, 1.15, 4.32), (0.26, 0.42, 0.12), "metal_dk", rot=(0.15, 0, 0), taper=(0.6, 0.6))
    mb.cyl((0.05, 1.15, 4.27), (0.05, 1.15, 4.25), 0.1, "rust_dk", segs=10)
    mb.cyl((0.05, 0.6, 4.4), (0.12, 0.52, 3.6), 0.008, "void", segs=3)                      # a hanging wire
    mb.splotch(lambda c, n: True, ("rust", "rust_dk", "rust_lt"), 0.4)
    mb.overgrow(prob_top=0.9, cols=MOSS)
    for k in range(16):   # ivy spiralling up the pole
        a = k * 1.1
        z = 0.4 + k * 0.15
        d = Vector((math.cos(a), math.sin(a), 0.3))
        mb.leaf((math.cos(a) * 0.07, math.sin(a) * 0.07, z), d, 0.17, 0.11, rng.choice(LEAVES))
    mb.tuft((0.15, -0.1, 0), 0.4, GRASS, blades=8, spread=0.15)
    mb.tuft((-0.15, 0.12, 0), 0.3, GRASS, blades=6, spread=0.1)
    ob = mb.to_object("lamp", root)

    def bulb(bm):
        bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=0.075,
                                  matrix=Matrix.Translation(BULB))
    emit_object("bulb", "bulb", bulb, parent=root)
    empty("light", parent=root, loc=BULB)
    a = Asset("street_lamp", root, "prop", 4)
    a.lights = {"light": (BULB.x, BULB.z, -BULB.y)}
    return a


# ---------------------------------------------------------------------------------------------------------------
# campfire: 1.2 m ring of stones, logs, glowing embers and small flames (one emissive node)
# ---------------------------------------------------------------------------------------------------------------
def campfire():
    root = empty("campfire")
    mb = MB("fire_pit", jitter=0.1)
    rng = mb.rng
    for k in range(10):
        a = k / 10 * math.tau + rng.uniform(-0.1, 0.1)
        mb.blob((math.cos(a) * 0.47, math.sin(a) * 0.47, 0.06), rng.uniform(0.1, 0.14), "stone", subdiv=1,
                squash=(1.2, 1, 0.75), noise=0.2, smooth=False, cols=("stone", "stone_dk", "ash"))
    mb.cyl((0, 0, 0), (0, 0, 0.03), 0.38, "ash", segs=12)
    for k in range(4):
        a = k / 4 * math.tau + 0.4
        p0 = Vector((math.cos(a) * 0.36, math.sin(a) * 0.36, 0.05))
        p1 = Vector((math.cos(a) * 0.05, math.sin(a) * 0.05, 0.38))
        mb.cyl(p0, p0 + (p1 - p0) * 0.65, 0.05, rng.choice(("wood", "bark")), segs=6)
        mb.cyl(p0 + (p1 - p0) * 0.65, p1, 0.045, "ash", segs=6)
    mb.cyl((-0.25, 0.15, 0.06), (0.2, -0.28, 0.08), 0.055, "bark", segs=6)                    # a log lying across
    for k in range(6):
        a = rng.uniform(0, math.tau)
        mb.tuft((math.cos(a) * 0.6, math.sin(a) * 0.6, 0), 0.2, GRASS, blades=5, spread=0.06)
    mb.to_object("fire_pit", root)

    def embers(bm):
        for k in range(9):
            a, r = rng.uniform(0, math.tau), rng.uniform(0, 0.2)
            bmesh.ops.create_icosphere(bm, subdivisions=1, radius=rng.uniform(0.035, 0.06),
                                       matrix=Matrix.Translation((math.cos(a) * r, math.sin(a) * r, 0.05)))
        for k, (x, y, hgt) in enumerate(((0, 0, 0.42), (0.07, 0.05, 0.3), (-0.06, 0.04, 0.26))):
            bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.09, radius2=0.0, depth=hgt,
                                  matrix=Matrix.Translation((x, y, 0.05 + hgt / 2)) @ Matrix.Rotation(k, 4, "Z"))
    emit_object("embers", "embers", embers, parent=root)
    empty("light", parent=root, loc=(0, 0, 0.6))
    a = Asset("campfire", root, "prop", 4)
    a.lights = {"light": (0.0, 0.6, 0.0)}
    a.ao_distance = 0.25
    return a


# ---------------------------------------------------------------------------------------------------------------
# tree (6 m, trunk footprint 1 m) and bush (1 m)
# ---------------------------------------------------------------------------------------------------------------
def _foliage_tint(mb, faces):
    mb.bm.normal_update()
    for f in faces:
        n = f.normal.z
        col = "leaf_dk" if n < -0.3 else ("leaf_lt" if n > 0.55 and mb.rng.random() < 0.7 else
                                          mb.rng.choice(("leaf", "leaf", "moss_lt")))
        mb.paint([f], col, smooth=True)


def tree():
    root = empty("tree")
    mb = MB("tree", jitter=0.08)
    rng = mb.rng
    pts = [Vector(p) for p in ((0, 0, 0), (0.06, 0.02, 1.2), (-0.04, 0.1, 2.4), (0.05, 0.02, 3.4))]
    radii = (0.28, 0.23, 0.19, 0.15)
    for p0, p1, r0, r1 in zip(pts, pts[1:], radii, radii[1:]):
        mb.cyl(p0, p1, r0, "bark", segs=8, r2=r1)
    for k in range(5):
        a = k / 5 * math.tau + 0.3
        mb.cyl((math.cos(a) * 0.48, math.sin(a) * 0.48, 0.0), (math.cos(a) * 0.12, math.sin(a) * 0.12, 0.55),
               0.08, "bark", segs=5, r2=0.11)
    for a, z in ((0.4, 2.6), (2.5, 3.0), (4.4, 2.8)):
        mb.cyl((0, 0.05, z), (math.cos(a) * 1.1, math.sin(a) * 1.1, z + 0.9), 0.08, "bark", segs=5, r2=0.04)
    mb.splotch(lambda c, n: c.z < 1.5, ("moss_dk", "moss", "bark"), 0.45)
    for k in range(12):
        a = k * 0.9
        mb.leaf((math.cos(a) * 0.27, math.sin(a) * 0.27, 0.3 + k * 0.17), (math.cos(a), math.sin(a), 0.4), 0.2, 0.13,
                rng.choice(LEAVES))
    canopy = [((0, 0, 4.3), 1.55, (1, 1, 0.75)), ((1.15, 0.3, 3.85), 1.0, (1, 1, 0.8)),
              ((-1.0, 0.6, 4.0), 1.05, (1, 1, 0.8)), ((0.2, -1.1, 3.9), 1.0, (1, 1, 0.8)),
              ((-0.5, -0.7, 4.7), 0.95, (1, 1, 0.85)), ((0.5, 0.8, 4.9), 0.9, (1, 1, 0.85)),
              ((0.1, 0.0, 5.35), 0.75, (1, 1, 0.85))]
    for c, r, sq in canopy:
        faces = mb.blob(c, r, "leaf", subdiv=2, squash=sq, noise=0.16)
        _foliage_tint(mb, faces)
    for k in range(8):
        a = rng.uniform(0, math.tau)
        mb.tuft((math.cos(a) * rng.uniform(0.4, 0.8), math.sin(a) * rng.uniform(0.4, 0.8), 0), 0.4, GRASS, blades=7)
    mb.to_object("tree", root)
    a = Asset("tree", root, "prop", 4)
    a.ao_distance = 0.8
    return a


def bush():
    root = empty("bush")
    mb = MB("bush", jitter=0.08)
    rng = mb.rng
    for c, r in (((0, 0, 0.5), 0.5), ((0.35, 0.15, 0.35), 0.38), ((-0.3, 0.2, 0.33), 0.36),
                 ((0.05, -0.32, 0.32), 0.35)):
        faces = mb.blob(c, r, "leaf", subdiv=2, squash=(1, 1, 0.95), noise=0.18)
        _foliage_tint(mb, faces)
    for k in range(7):
        a, rr = rng.uniform(0, math.tau), rng.uniform(0.1, 0.4)
        mb.blob((math.cos(a) * rr, math.sin(a) * rr, 0.85 + rng.uniform(-0.15, 0.1)), 0.035,
                rng.choice(("flower_w", "flower_y")), subdiv=1, smooth=False)
    for k in range(6):
        a = rng.uniform(0, math.tau)
        mb.tuft((math.cos(a) * 0.55, math.sin(a) * 0.55, 0), 0.3, GRASS, blades=6)
    mb.to_object("bush", root)
    a = Asset("bush", root, "prop", 4)
    a.ao_distance = 0.4
    return a


PROPS = {"house_ruin_a": house_ruin_a, "house_ruin_b": house_ruin_b, "subway_entrance": subway_entrance,
         "car_wreck": car_wreck, "street_lamp": street_lamp, "campfire": campfire, "tree": tree, "bush": bush}
