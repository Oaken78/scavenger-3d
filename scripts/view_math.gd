class_name ViewMath
extends RefCounted
## Pure conversions between the rules' 2D world (Vector2 x east, z south) and Godot 3D. No nodes.

const MODEL_DIR := "res://assets/models/"


## Sim position (x, z) at height y as a 3D point.
static func to_world(p: Vector2, y: float = 0.0) -> Vector3:
	return Vector3(p.x, y, p.y)


## 3D point to sim position (drops y).
static func to_sim(p: Vector3) -> Vector2:
	return Vector2(p.x, p.z)


## Sim heading (radians, 0 = +x, increasing towards +z) as rotation.y for a model that faces +X.
static func heading_to_rot_y(heading: float) -> float:
	return -heading


## Layout prop rotation (degrees about +y, x towards z) as rotation.y.
static func layout_rot_to_rot_y(rot_deg: float) -> float:
	return -deg_to_rad(rot_deg)


## Where a ray meets the horizontal plane at height y; null when it runs parallel or points away.
## whole_line: also accept a hit behind the origin (orthographic rays are parallel lines whose origin sits on an
## arbitrary near plane, so the line is what counts).
static func ray_to_plane(origin: Vector3, dir: Vector3, y: float = 0.0, whole_line: bool = false) -> Variant:
	if absf(dir.y) < 0.000001:
		return null
	var t := (y - origin.y) / dir.y
	if t < 0.0 and not whole_line:
		return null
	return origin + dir * t


## Shortest-arc blend between two angles (radians), weight 0..1.
static func lerp_angle_to(from: float, to: float, weight: float) -> float:
	return lerp_angle(from, to, clampf(weight, 0.0, 1.0))


## Path of the model for an asset name (it may not exist yet).
static func model_path(asset: String) -> String:
	return MODEL_DIR + asset + ".glb"


## True when an imported model exists for the asset (then it replaces the grey-box stand-in).
static func has_model(asset: String) -> bool:
	return ResourceLoader.exists(model_path(asset))


## Animation name in a list that matches want exactly, or ends with it ("Armature|walk"), or "".
static func find_anim(names: PackedStringArray, want: String) -> String:
	for n in names:
		if n == want:
			return n
	for n in names:
		var lower := n.to_lower()
		if lower.ends_with("|" + want) or lower.ends_with("_" + want) or lower.ends_with(want):
			return n
	return ""
