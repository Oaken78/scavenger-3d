class_name ModelFactory
extends RefCounted
## Builds the visual of an asset: the A01 model at assets/models/<asset>.glb when it exists, else a grey-box
## stand-in of the layout footprint and height. Swapping in a model needs no code change.
## Stand-in emissive parts (robot eye, drone eye, lamp bulb, embers) carry the node name "Glow" so the
## presentation can drive them.

const STAND_IN_COLORS := {
	"house_ruin_a": Color(0.42, 0.41, 0.38),
	"house_ruin_b": Color(0.38, 0.39, 0.37),
	"subway_entrance": Color(0.33, 0.34, 0.33),
	"car_wreck": Color(0.36, 0.22, 0.14),
	"street_lamp": Color(0.22, 0.23, 0.24),
	"campfire": Color(0.25, 0.2, 0.17),
	"tree": Color(0.2, 0.3, 0.14),
	"bush": Color(0.16, 0.27, 0.12),
	"fuel_canister": Color(0.95, 0.72, 0.1),
	"scrap_drone": Color(0.4, 0.3, 0.24),
	"robot": Color(0.62, 0.6, 0.52),
}


## The visual node for an asset. footprint is the layout's footprint entry for it.
static func build(asset: String, footprint: Dictionary) -> Node3D:
	if ViewMath.has_model(asset):
		var scene: PackedScene = load(ViewMath.model_path(asset))
		if scene != null:
			var inst := scene.instantiate() as Node3D
			if inst != null:
				inst.name = "Model"
				_cast_shadows(inst)
				return inst
	return _stand_in(asset, footprint)


## First AnimationPlayer under node (models carry one), or null.
static func find_anim_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node
	for c in node.get_children():
		var found := find_anim_player(c)
		if found != null:
			return found
	return null


static func _cast_shadows(node: Node) -> void:
	if node is GeometryInstance3D:
		(node as GeometryInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	for c in node.get_children():
		_cast_shadows(c)


static func _stand_in(asset: String, fp: Dictionary) -> Node3D:
	var root := Node3D.new()
	root.name = "StandIn"
	var size: Array = fp.get("size", [0, 0])
	var height := float(fp.get("height", 1.0))
	var col: Color = STAND_IN_COLORS.get(asset, Color(0.5, 0.5, 0.5))
	match asset:
		"robot":
			_box(root, Vector3(0.8, 1.0, 0.7), Vector3(0, 0.6, 0), col)
			_box(root, Vector3(0.5, 0.35, 0.5), Vector3(0, 1.25, 0), col.darkened(0.15))
			_box(root, Vector3(0.3, 0.25, 0.75), Vector3(-0.05, 0.25, 0), Color(0.18, 0.3, 0.12))
			_glow(root, Vector3(0.08, 0.14, 0.14), Vector3(0.27, 1.2, 0), Color(1.0, 0.95, 0.8), 4.0, false)
		"scrap_drone":
			# Built around y = 0: the presentation lifts the drone to its hover height (models alike).
			_box(root, Vector3(0.6, 0.35, 0.6), Vector3(0, 0, 0), col)
			_box(root, Vector3(0.9, 0.06, 0.2), Vector3(0, 0.2, 0), col.darkened(0.3))
			_glow(root, Vector3(0.1, 0.12, 0.12), Vector3(0.31, 0, 0), Color(1.0, 0.1, 0.05), 6.0, false)
		"fuel_canister":
			_box(root, Vector3(0.36, 0.48, 0.18), Vector3(0, 0.24, 0), col)
		"street_lamp":
			_cylinder(root, 0.09, 4.3, Vector3(0, 2.15, 0), col)
			_box(root, Vector3(0.8, 0.08, 0.1), Vector3(0.35, 4.3, 0), col)
			_glow(root, Vector3(0.3, 0.12, 0.25), Vector3(0.6, 4.22, 0), Color(1.0, 0.7, 0.35), 6.0, true)
		"campfire":
			_cylinder(root, 0.6, 0.2, Vector3(0, 0.1, 0), col)
			_glow(root, Vector3(0.6, 0.15, 0.6), Vector3(0, 0.22, 0), Color(1.0, 0.4, 0.08), 8.0, true)
		"tree":
			_cylinder(root, 0.25, 3.0, Vector3(0, 1.5, 0), Color(0.24, 0.18, 0.12))
			_sphere(root, 2.0, Vector3(0, 4.0, 0), col)
		"bush":
			_sphere(root, 0.6, Vector3(0, 0.45, 0), col)
		_:
			var sx := maxf(float(size[0]), 0.3)
			var sz := maxf(float(size[1]), 0.3)
			_box(root, Vector3(sx, height, sz), Vector3(0, height * 0.5, 0), col)
	return root


static func _material(col: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = col
	m.roughness = 0.85
	return m


static func _add(root: Node3D, mesh: Mesh, pos: Vector3, mat: Material) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.position = pos
	mi.material_override = mat
	root.add_child(mi)
	return mi


static func _box(root: Node3D, size: Vector3, pos: Vector3, col: Color) -> MeshInstance3D:
	var m := BoxMesh.new()
	m.size = size
	return _add(root, m, pos, _material(col))


static func _cylinder(root: Node3D, radius: float, height: float, pos: Vector3, col: Color) -> MeshInstance3D:
	var m := CylinderMesh.new()
	m.top_radius = radius
	m.bottom_radius = radius
	m.height = height
	return _add(root, m, pos, _material(col))


static func _sphere(root: Node3D, radius: float, pos: Vector3, col: Color) -> MeshInstance3D:
	var m := SphereMesh.new()
	m.radius = radius
	m.height = radius * 1.8
	return _add(root, m, pos, _material(col))


## An unshaded-looking emissive part; glow picks it up. no_shadow keeps a bulb from shadowing its own light.
static func _glow(root: Node3D, size: Vector3, pos: Vector3, col: Color, energy: float, no_shadow: bool) -> void:
	var m := StandardMaterial3D.new()
	m.albedo_color = col
	m.emission_enabled = true
	m.emission = col
	m.emission_energy_multiplier = energy
	var mesh := BoxMesh.new()
	mesh.size = size
	var mi := _add(root, mesh, pos, m)
	mi.name = "Glow"
	if no_shadow:
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
