"""Actors and pickups: robot (player), scrap_drone, fuel_canister. Blender coords, actors face +X."""
import math

from sc_kit import MB, MOSS, Asset, emit_object, empty
import bmesh
from mathutils import Matrix

TAU = math.tau
LEAVES = ("leaf", "leaf_lt", "moss_lt")


def _smooth(a, b, f):
    f = f * f * (3 - 2 * f)
    return a + (b - a) * f


def _keyed(keys, t):
    """keys: [(t, value tuple)], sorted; smoothstep between neighbours."""
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return tuple(_smooth(a, b, f) for a, b in zip(v0, v1))
    return keys[-1][1]


# ---------------------------------------------------------------------------------------------------------------
# robot: 1.4 m boxy service robot, one headlamp eye (at 1.1 m), moss and small plants over its left half
# ---------------------------------------------------------------------------------------------------------------
HIP_Z = 0.40
SHOULDER_Z = 0.44   # in body space (world 0.84)
NECK_Z = 0.56       # in body space (world 0.96)
LAMP_Z = 1.10 - HIP_Z - NECK_Z


def _robot_leg(name, side, parent):
    mb = MB(name)
    mb.cyl((0, -0.07, 0), (0, 0.07, 0), 0.065, "joint", segs=8)
    mb.box((0, 0, -0.12), (0.12, 0.11, 0.2), "robot_dk", bevel=0.015, edge_col="joint")
    mb.box((0.0, 0, -0.26), (0.15, 0.14, 0.12), "robot", bevel=0.02, edge_col="robot_dk")
    mb.box((0.05, 0, -0.36), (0.30, 0.17, 0.08), "joint", bevel=0.02, edge_col="metal")
    mb.box((0.17, 0, -0.355), (0.04, 0.15, 0.05), "robot_accent")
    if side > 0:   # the mossy side
        mb.overgrow(prob_top=0.9, prob_side=0.5, side_pred=lambda c, n: n.y > 0.5)
        mb.tuft((0.02, 0.09, -0.36), 0.12, ("grass", "leaf_lt"), blades=5, spread=0.03)
    return mb.to_object(name, parent, (0, 0.17 * side, HIP_Z))


def _robot_arm(name, side, parent):
    mb = MB(name)
    mb.cyl((0, -0.06, 0), (0, 0.06, 0), 0.07, "joint", segs=8)
    mb.box((0, 0, -0.12), (0.1, 0.1, 0.18), "robot", bevel=0.015, edge_col="robot_dk")
    mb.cyl((0, -0.055, -0.22), (0, 0.055, -0.22), 0.05, "joint", segs=8)
    mb.box((0.0, 0, -0.31), (0.12, 0.12, 0.16), "robot_dk", bevel=0.02, edge_col="robot")
    for dx in (-0.035, 0.035):   # two-pronged claw
        mb.box((dx, 0, -0.43), (0.03, 0.05, 0.1), "joint", rot=(0, dx * 4, 0))
    if side > 0:
        mb.overgrow(prob_top=1.0, prob_side=0.45, side_pred=lambda c, n: n.y > -0.2)
        mb.blob((0.0, 0.03, 0.06), 0.08, "moss", squash=(1, 1, 0.6), cols=MOSS)
        mb.sprig((0.0, 0.04, 0.1), 0.09, LEAVES, leaves=4)
    return mb.to_object(name, parent, (0, 0.36 * side, SHOULDER_Z))


def _robot_body(parent):
    mb = MB("body")
    mb.box((0, 0, 0.28), (0.52, 0.62, 0.52), "robot", bevel=0.035, edge_col="robot_dk")
    mb.box((0, 0, 0.03), (0.30, 0.42, 0.10), "joint", bevel=0.02)
    mb.box((0.262, 0, 0.44), (0.012, 0.60, 0.06), "robot_accent")          # orange stripe
    mb.box((0.262, -0.12, 0.22), (0.012, 0.22, 0.16), "robot_dk")          # chest hatch
    for i in range(4):                                                     # vent slats
        mb.box((0.262, 0.14, 0.14 + i * 0.045), (0.014, 0.18, 0.02), "joint")
    mb.cyl((-0.32, -0.25, 0.30), (-0.32, 0.25, 0.30), 0.12, "robot_accent", segs=10)   # fuel tank
    mb.cyl((-0.32, -0.27, 0.30), (-0.32, -0.25, 0.30), 0.09, "joint", segs=10)          # filler cap
    mb.cyl((-0.25, 0.0, 0.42), (-0.10, 0.0, 0.53), 0.025, "joint", segs=6)             # pipe
    mb.cyl((0, 0, 0.53), (0, 0, 0.58), 0.09, "joint", segs=8)                           # neck
    mb.splotch(lambda c, n: c.z < 0.12 and n.z < 0.5, ("dirt", "rust_dk"), 0.5)
    mb.overgrow(prob_top=0.85, prob_side=0.6, side_pred=lambda c, n: c.y > 0.02 or c.x < -0.2)
    mb.blob((-0.05, 0.16, 0.55), 0.17, "moss", squash=(1.3, 1, 0.35), cols=MOSS)
    mb.blob((-0.32, 0.12, 0.40), 0.11, "moss", squash=(1, 1.4, 0.6), cols=MOSS)
    mb.blob((0.0, 0.31, 0.30), 0.12, "moss", squash=(1.2, 0.35, 1.3), cols=MOSS)
    mb.sprig((-0.1, 0.2, 0.6), 0.14, LEAVES, leaves=5)
    mb.sprig((-0.33, 0.05, 0.45), 0.11, LEAVES, leaves=4)
    mb.tuft((0.05, 0.08, 0.56), 0.1, ("grass", "leaf_lt"), blades=6, spread=0.06)
    mb.cyl((-0.16, 0.24, 0.58), (-0.15, 0.25, 0.72), 0.006, "leaf_dk", segs=3)          # a little flower
    mb.blob((-0.15, 0.25, 0.73), 0.025, "flower_w", subdiv=1, squash=(1, 1, 0.5), smooth=False)
    mb.blob((-0.15, 0.25, 0.745), 0.01, "flower_y", subdiv=1, smooth=False)
    return mb.to_object("body", parent, (0, 0, HIP_Z))


def _robot_head(parent):
    mb = MB("head")
    mb.box((0, 0, 0.16), (0.40, 0.44, 0.30), "robot", bevel=0.03, edge_col="robot_dk")
    mb.cyl((0.19, 0, LAMP_Z), (0.25, 0, LAMP_Z), 0.10, "joint", segs=12)          # lamp housing
    mb.cyl((0.22, 0, LAMP_Z + 0.115), (0.27, 0, LAMP_Z + 0.105), 0.035, "joint", segs=6)   # brow
    for s in (-1, 1):
        mb.cyl((0, 0.22 * s, 0.16), (0, 0.25 * s, 0.16), 0.055, "joint", segs=8)   # ear bolts
    mb.cyl((-0.1, 0.12, 0.31), (-0.13, 0.15, 0.44), 0.01, "joint", segs=4)          # antenna
    mb.blob((-0.13, 0.15, 0.445), 0.02, "robot_accent", subdiv=1, smooth=False)
    mb.overgrow(prob_top=0.6, prob_side=0.5, side_pred=lambda c, n: c.y > 0.05)
    mb.blob((-0.04, 0.12, 0.31), 0.13, "moss", squash=(1.2, 1, 0.3), cols=MOSS)
    mb.sprig((-0.06, 0.1, 0.33), 0.1, LEAVES, leaves=3)
    ob = mb.to_object("head", parent, (0, 0, NECK_Z))

    def lens(bm):
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.075, radius2=0.07, depth=0.025,
                              matrix=Matrix.Translation((0.26, 0, LAMP_Z)) @ Matrix.Rotation(math.pi / 2, 4, "Y"))
    emit_object("headlamp", "headlamp", lens, parent=ob)
    empty("headlight", parent=ob, loc=(0.28, 0, LAMP_Z))   # SpotLight anchor, shines along +X
    return ob


def robot():
    root = empty("robot")
    leg_l = _robot_leg("leg_l", 1, root)
    leg_r = _robot_leg("leg_r", -1, root)
    body = _robot_body(root)
    head = _robot_head(body)
    arm_l = _robot_arm("arm_l", 1, body)
    arm_r = _robot_arm("arm_r", -1, body)
    parts = [leg_l, leg_r, body, head, arm_l, arm_r]
    rest_tf = {p.name: (p.location.copy(), p.rotation_euler.copy()) for p in parts}

    def rest():
        for p in parts:
            p.location, p.rotation_euler = rest_tf[p.name][0].copy(), rest_tf[p.name][1].copy()

    def idle(t):
        body.location.z += 0.008 * math.sin(TAU * t)
        head.rotation_euler.z = 0.12 * math.sin(TAU * t)
        arm_l.rotation_euler.x = 0.03 * math.sin(TAU * t)
        arm_r.rotation_euler.x = -0.03 * math.sin(TAU * t)

    def walk(t):
        ph = TAU * t
        sw = 0.45 * math.sin(ph)
        leg_l.rotation_euler.y = sw
        leg_r.rotation_euler.y = -sw
        body.location.z += 0.025 * abs(math.cos(ph)) - 0.012
        body.rotation_euler.y = 0.08
        body.rotation_euler.x = 0.04 * math.sin(ph)
        head.rotation_euler.z = 0.05 * math.sin(ph)
        arm_l.rotation_euler.y = -sw * 0.7
        arm_r.rotation_euler.y = sw * 0.7

    attack_keys = [  # (t, (arm_r x, arm_r z, body yaw, body pitch, arm_l y))
        (0.0, (-1.20, -0.50, -0.35, 0.00, 0.2)),
        (1 / 6, (-1.35, -0.85, -0.45, -0.03, 0.3)),
        (2 / 6, (-1.45, 0.60, 0.10, 0.12, -0.2)),
        (3 / 6, (-1.45, 2.10, 0.45, 0.10, -0.3)),
        (4 / 6, (-0.80, 1.20, 0.20, 0.05, -0.1)),
        (5 / 6, (-0.30, 0.40, 0.05, 0.02, 0.0)),
        (1.0, (0.0, 0.0, 0.0, 0.0, 0.0)),
    ]

    def attack(t):
        ax, az, by, bp, aly = _keyed(attack_keys, t)
        arm_r.rotation_euler = (ax, 0.0, az)
        body.rotation_euler.z = by
        body.rotation_euler.y = bp
        arm_l.rotation_euler.y = aly
        leg_r.rotation_euler.y = -0.25
        leg_l.rotation_euler.y = 0.2

    anims = {
        "idle": dict(frames=1, fps=1, loop=True, seconds=2.0, pose=idle),
        "walk": dict(frames=8, fps=16, loop=True, seconds=0.5, pose=walk),
        "attack": dict(frames=6, fps=10, loop=False, seconds=0.6, pose=attack),
    }
    asset = Asset("robot", root, "actor", 8, anims, rest)
    asset.animated = parts
    asset.lights = {"headlight": (0.28, 1.10, 0.0)}
    return asset


# ---------------------------------------------------------------------------------------------------------------
# scrap_drone: rusty, a red eye. Sprites: body centre 1.2 m above the ground origin; glTF: origin = body centre
# ---------------------------------------------------------------------------------------------------------------
HOVER_Z = 1.2
RUST = ("rust", "rust_dk", "rust_lt", "drone")


def scrap_drone():
    root = empty("scrap_drone")
    mb = MB("hull", jitter=0.1)
    mb.cyl((0, 0, -0.11), (0, 0, 0.09), 0.22, "drone", segs=8, r2=0.2)
    mb.blob((0, 0, 0.09), 0.19, "rust", subdiv=1, squash=(1, 1, 0.55), noise=0.12, smooth=False, cols=RUST)
    mb.box((0.2, 0, 0.0), (0.1, 0.26, 0.16), "metal_dk", bevel=0.015, edge_col="rust_lt")     # face plate
    mb.cyl((0.24, 0, 0.0), (0.28, 0, 0.0), 0.075, "metal_dk", segs=10)                       # eye socket
    for i in range(4):
        a = math.pi / 4 + i * math.pi / 2
        c, s = math.cos(a), math.sin(a)
        mb.box((c * 0.22, s * 0.22, 0.02), (0.22, 0.05, 0.04), "metal_dk", rot=(0, 0, a))
        mb.cyl((c * 0.31, s * 0.31, -0.02), (c * 0.31, s * 0.31, 0.06), 0.11, RUST[i % 4], segs=10)
        mb.cyl((c * 0.31, s * 0.31, -0.05), (c * 0.31, s * 0.31, -0.02), 0.03, "metal_dk", segs=6)
    mb.cyl((-0.05, 0, -0.11), (-0.06, 0.02, -0.34), 0.012, "metal_dk", segs=4)              # dangling cable
    mb.box((-0.06, 0.02, -0.37), (0.06, 0.03, 0.06), "rust_dk", rot=(0.3, 0, 0))            # hook
    mb.cyl((-0.12, -0.05, 0.12), (-0.2, -0.08, 0.32), 0.008, "metal_dk", segs=4)            # bent antenna
    mb.cyl((-0.2, -0.08, 0.32), (-0.28, -0.04, 0.36), 0.008, "metal_dk", segs=4)
    mb.splotch(lambda c, n: True, RUST, 0.35)
    mb.overgrow(prob_top=0.35, cols=("moss_dk", "moss"))
    hull = mb.to_object("hull", root, (0, 0, HOVER_Z))

    def eye(bm):
        bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=0.055,
                                  matrix=Matrix.Translation((0.27, 0, 0)))
    emit_object("eye", "drone_eye", eye, parent=hull)
    rotors = []
    for i in range(4):
        a = math.pi / 4 + i * math.pi / 2
        rb = MB(f"rotor_{i}")
        rb.box((0, 0, 0), (0.2, 0.03, 0.008), "metal", rot=(0.15, 0, 0))
        rb.box((0, 0, 0), (0.03, 0.2, 0.008), "metal", rot=(0, 0.15, 0))
        rotors.append(rb.to_object(f"rotor_{i}", hull, (math.cos(a) * 0.31, math.sin(a) * 0.31, 0.065)))
    empty("eye_light", parent=hull, loc=(0.3, 0, 0))
    parts = [hull] + rotors
    rest_tf = {p.name: (p.location.copy(), p.rotation_euler.copy()) for p in parts}
    lift = {"z": HOVER_Z}   # sprites: hovering 1.2 m up; glTF: 0 (the 3D game lifts the node itself)

    def rest():
        for p in parts:
            p.location, p.rotation_euler = rest_tf[p.name][0].copy(), rest_tf[p.name][1].copy()
        hull.location.z = lift["z"]

    def hover(t):
        ph = TAU * t
        hull.location.z = lift["z"] + 0.05 * math.sin(ph)
        hull.rotation_euler = (0.06 * math.sin(ph + 1.0), 0.05 * math.cos(ph), 0.0)
        for i, r in enumerate(rotors):
            r.rotation_euler.z = (2.5 * TAU * t) * (1 if i % 2 else -1)

    asset = Asset("scrap_drone", root, "actor", 8,
                  {"hover": dict(frames=4, fps=8, loop=True, seconds=0.5, pose=hover)}, rest)
    asset.animated = parts
    asset.lights = {"eye_light": (0.3, HOVER_Z, 0.0)}

    def for_export():
        lift["z"] = 0.0
        rest()
    asset.for_export = for_export
    return asset


# ---------------------------------------------------------------------------------------------------------------
# fuel_canister: 0.5 m yellow jerrycan, scuffed
# ---------------------------------------------------------------------------------------------------------------
def fuel_canister():
    root = empty("fuel_canister")
    mb = MB("canister", jitter=0.05)
    mb.box((0, 0, 0.21), (0.17, 0.34, 0.42), "can", bevel=0.025, edge_col="can_dk")
    for s in (-1, 1):   # the embossed X on both faces
        for r in (0.86, -0.86):
            mb.box((0.087 * s, 0, 0.21), (0.012, 0.035, 0.44), "can_dk", rot=(r, 0, 0))
    for y in (-0.08, 0.0, 0.08):   # three handles
        mb.box((0, y, 0.475), (0.035, 0.05, 0.03), "can", bevel=0.006)
        mb.box((0, y, 0.44), (0.03, 0.03, 0.05), "can_dk")
    mb.box((0, 0, 0.475), (0.04, 0.24, 0.025), "can_dk")
    mb.cyl((0, 0.13, 0.41), (0, 0.16, 0.48), 0.028, "metal_dk", segs=8)    # spout
    mb.cyl((0, 0.16, 0.48), (0, 0.17, 0.5), 0.034, "rust", segs=8)
    mb.splotch(lambda c, n: True, ("can_dk", "rust", "metal"), 0.12)
    mb.splotch(lambda c, n: c.z < 0.08, ("dirt", "rust_dk"), 0.6)
    mb.to_object("canister", root)
    return Asset("fuel_canister", root, "prop", 1)


ACTORS = {"robot": robot, "scrap_drone": scrap_drone, "fuel_canister": fuel_canister}
