extends Node3D
## T02: the dusk street in real 3D. Builds the scene from data/layout.json, runs the shared Sim (scripts/rules/)
## and only presents its state: models or grey-box stand-ins, lights, fog, camera, click input and the HUD.

signal level_started
signal canister_taken(id: int)
signal drone_destroyed(id: int)

## The layout (a copy of design/layout.json; design/ is not imported).
@export_file("*.json") var layout_path: String = "res://data/layout.json"
## Frames before level_started fires (scenarios wait on it).
@export var start_delay_frames: int = 30

@export_group("Camera")
## Metres of ground visible across the screen (orthographic width).
@export var view_width: float = 20.0
## Distance from the followed point back along the view ray (only clipping depends on it).
@export var camera_distance: float = 40.0
## How quickly the camera catches up with the robot (1/s; higher = tighter).
@export var follow_speed: float = 4.0

@export_group("Moon")
@export var moon_color: Color = Color(0.5, 0.6, 1.0)
@export var moon_energy: float = 0.9
## Moon direction as Euler degrees; a low moon behind the houses throws long shadows towards the camera.
@export var moon_rotation: Vector3 = Vector3(-28, 160, 0)
@export var ambient_color: Color = Color(0.22, 0.28, 0.45)
@export var ambient_energy: float = 0.25
@export var sky_color: Color = Color(0.015, 0.02, 0.04)

@export_group("Headlight")
@export var headlight_color: Color = Color(1.0, 0.95, 0.85)
@export var headlight_energy: float = 9.0
@export var headlight_range: float = 16.0
## Half-angle of the cone in degrees.
@export var headlight_angle: float = 26.0
## Downward tilt in degrees.
@export var headlight_tilt: float = 10.0
## How brightly the headlight cone shows in the volumetric fog.
@export var headlight_fog: float = 2.5
## Seconds for the headlight to die when fuel runs out (GDD section 7).
@export var headlight_fade_time: float = 2.0

@export_group("Lamps and fire")
@export var lamp_color: Color = Color(1.0, 0.68, 0.35)
@export var lamp_energy: float = 8.0
@export var lamp_range: float = 12.0
## Light position relative to a lamp's origin (rotated with the prop); the bulb hangs off the arm.
@export var lamp_light_offset: Vector3 = Vector3(0.6, -0.1, 0.0)
@export var fire_color: Color = Color(1.0, 0.45, 0.12)
@export var fire_energy: float = 4.0
@export var fire_range: float = 8.0
@export var lamp_fog: float = 1.5

@export_group("Drones and canisters")
@export var eye_color: Color = Color(1.0, 0.08, 0.04)
@export var eye_energy: float = 2.5
@export var eye_range: float = 3.0
## Eye light multiplier while a drone flashes from a hit.
@export var eye_hit_boost: float = 5.0
@export var canister_glint_color: Color = Color(1.0, 0.8, 0.3)
@export var canister_glint_energy: float = 0.8
## Click pick radius around a drone, metres.
@export var drone_pick_radius: float = 1.1

@export_group("Atmosphere")
@export var fog_density: float = 0.006
@export var fog_albedo: Color = Color(0.55, 0.62, 0.8)
## Low ground fog in the FogVolume.
@export var ground_fog_density: float = 0.18
@export var ground_fog_height: float = 1.6
@export var ssao_intensity: float = 2.0
@export var glow_intensity: float = 0.9

@export_group("Cutaway")
## Props at least this tall fade out when they stand between the camera and the robot.
@export var cutaway_min_height: float = 2.5
## How see-through a prop gets while it hides the robot (0 = solid, 1 = gone).
@export_range(0.0, 1.0) var cutaway_amount: float = 0.75
## Fade speed of the cutaway (1/s).
@export var cutaway_speed: float = 6.0

var sim: Sim
var layout: Dictionary = {}
## Scenario-visible state.
var fuel: float:
	get:
		return sim.fuel if sim != null else 0.0
	set(value):
		if sim != null:
			sim.fuel = clampf(value, 0.0, sim.fuel_max)
var canisters_left: int:
	get:
		return sim.canisters.filter(func(c: Dictionary) -> bool: return not c["taken"]).size()
var drones_alive: int:
	get:
		return sim.drones.filter(func(d: Dictionary) -> bool: return d["alive"]).size()
var outcome: String:
	get:
		return sim.outcome
var robot_x: float:
	get:
		return sim.robot_pos.x
var robot_z: float:
	get:
		return sim.robot_pos.y
var clicks_handled: int = 0
var fog_on: bool = true

var _frames := 0
var _started := false
var _hover_height := 1.2
var _camera: Camera3D
var _cam_target := Vector3.ZERO
var _env: Environment
var _fog_volume: FogVolume
var _robot: Node3D
var _robot_anim: AnimationPlayer
var _robot_visual: Node3D
var _headlight: SpotLight3D
var _robot_glow: MeshInstance3D
var _drones: Array = []  ## {node, visual, anim, eye}
var _occluders: Array = []  ## {node, box: AABB (prop local), meshes: Array, fade: float}
var _canisters: Array = []  ## Node3D per sim canister
var _marker: MeshInstance3D
var _marker_t := 1.0
var _hud: Hud
var _shown_outcome := ""
var _time := 0.0


func _ready() -> void:
	var f := FileAccess.open(layout_path, FileAccess.READ)
	layout = JSON.parse_string(f.get_as_text())
	sim = Sim.new(layout)
	_hover_height = float(layout["footprints"]["scrap_drone"].get("hover_height", 1.2))
	_build_environment()
	_build_ground()
	_build_props()
	_build_robot()
	_build_drones()
	_build_canisters()
	_build_marker()
	_build_camera()
	_hud = Hud.new()
	_hud.name = "Hud"
	add_child(_hud)
	_present(0.0, true)


func _physics_process(delta: float) -> void:
	sim.advance(delta)
	for e: Dictionary in sim.events:
		_on_sim_event(e)


func _process(delta: float) -> void:
	_frames += 1
	_time += delta
	if not _started and _frames >= start_delay_frames:
		_started = true
		level_started.emit()
	_present(delta, false)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT:
			click_at_screen(mb.position)
			get_viewport().set_input_as_handled()
		return
	if event.is_action_pressed("restart"):
		get_tree().reload_current_scene()
	elif event.is_action_pressed("toggle_fog"):
		set_fog(not fog_on)
	elif event.is_action_pressed("toggle_stats"):
		_hud.toggle_stats()


# ---- public: input and scenario hooks ----------------------------------------------------------

## A left click at a screen position: attack the drone under it, else walk to the ground point.
func click_at_screen(screen_pos: Vector2) -> void:
	var origin := _camera.project_ray_origin(screen_pos)
	var dir := _camera.project_ray_normal(screen_pos)
	var ortho := _camera.projection == Camera3D.PROJECTION_ORTHOGONAL
	var ground: Variant = ViewMath.ray_to_plane(origin, dir, 0.0, ortho)
	var at_hover: Variant = ViewMath.ray_to_plane(origin, dir, _hover_height, ortho)
	var drone := -1
	if at_hover != null:
		drone = sim.drone_at(ViewMath.to_sim(at_hover), drone_pick_radius)
	if drone < 0 and ground != null:
		drone = sim.drone_at(ViewMath.to_sim(ground), drone_pick_radius * 0.7)
	if drone >= 0:
		sim.command_attack(drone)
		_show_marker(ViewMath.to_world(sim.drones[drone]["pos"]), true)
	elif ground != null:
		sim.command_move(ViewMath.to_sim(ground))
		_show_marker(ground, false)
	else:
		return
	clicks_handled += 1


func debug_move_to(x: float, z: float) -> void:
	sim.command_move(Vector2(x, z))
	_show_marker(Vector3(x, 0, z), false)


## index into the layout's enemies (= the sim's drone id).
func debug_attack(index: int) -> void:
	sim.command_attack(index)


func set_fog(on: bool) -> void:
	fog_on = on
	_env.volumetric_fog_enabled = on
	_fog_volume.visible = on


# ---- building ----------------------------------------------------------------------------------

func _build_environment() -> void:
	_env = Environment.new()
	_env.background_mode = Environment.BG_COLOR
	_env.background_color = sky_color
	_env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	_env.ambient_light_color = ambient_color
	_env.ambient_light_energy = ambient_energy
	_env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	_env.tonemap_exposure = 1.1
	_env.ssao_enabled = true
	_env.ssao_radius = 1.2
	_env.ssao_intensity = ssao_intensity
	_env.glow_enabled = true
	_env.glow_intensity = glow_intensity
	_env.glow_bloom = 0.04
	_env.glow_hdr_threshold = 0.9
	_env.glow_blend_mode = Environment.GLOW_BLEND_MODE_SOFTLIGHT
	_env.volumetric_fog_enabled = true
	_env.volumetric_fog_density = fog_density
	_env.volumetric_fog_albedo = fog_albedo
	_env.volumetric_fog_emission = sky_color
	_env.volumetric_fog_emission_energy = 0.2
	_env.volumetric_fog_length = camera_distance + 40.0
	_env.volumetric_fog_anisotropy = 0.4
	_env.volumetric_fog_ambient_inject = 0.15
	_env.volumetric_fog_detail_spread = 1.0
	var we := WorldEnvironment.new()
	we.name = "WorldEnvironment"
	we.environment = _env
	add_child(we)

	var moon := DirectionalLight3D.new()
	moon.name = "Moon"
	moon.light_color = moon_color
	moon.light_energy = moon_energy
	moon.rotation_degrees = moon_rotation
	moon.shadow_enabled = true
	moon.directional_shadow_max_distance = camera_distance + 40.0
	moon.light_volumetric_fog_energy = 0.6
	add_child(moon)

	_fog_volume = FogVolume.new()
	_fog_volume.name = "GroundFog"
	var b: Array = layout["bounds"]
	_fog_volume.size = Vector3(b[2] - b[0] + 8.0, ground_fog_height * 2.0, b[3] - b[1] + 8.0)
	_fog_volume.position = Vector3((b[0] + b[2]) * 0.5, 0.0, (b[1] + b[3]) * 0.5)
	var fm := FogMaterial.new()
	fm.density = ground_fog_density
	fm.albedo = fog_albedo
	fm.height_falloff = 1.2
	fm.edge_fade = 0.3
	var noise := FastNoiseLite.new()
	noise.frequency = 0.05
	var tex := NoiseTexture3D.new()
	tex.width = 48
	tex.height = 8
	tex.depth = 48
	tex.noise = noise
	fm.density_texture = tex
	_fog_volume.material = fm
	add_child(_fog_volume)


func _build_ground() -> void:
	var b: Array = layout["bounds"]
	var plane := PlaneMesh.new()
	plane.size = Vector2(b[2] - b[0] + 30.0, b[3] - b[1] + 30.0)
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/ground.gdshader")
	var road: Dictionary = layout["road"]
	mat.set_shader_parameter("road_from", Vector2(road["from"][0], road["from"][1]))
	mat.set_shader_parameter("road_to", Vector2(road["to"][0], road["to"][1]))
	mat.set_shader_parameter("road_half_width", float(road["width"]) * 0.5)
	var mi := MeshInstance3D.new()
	mi.name = "Ground"
	mi.mesh = plane
	mi.material_override = mat
	mi.position = Vector3((b[0] + b[2]) * 0.5, 0.0, (b[1] + b[3]) * 0.5)
	add_child(mi)


func _build_props() -> void:
	var props := Node3D.new()
	props.name = "Props"
	add_child(props)
	var fps: Dictionary = layout["footprints"]
	var i := 0
	for p: Dictionary in layout["props"]:
		var asset: String = p["asset"]
		var fp: Dictionary = fps[asset]
		var node := Node3D.new()
		node.name = "%s_%d" % [asset, i]
		node.position = Vector3(p["pos"][0], 0.0, p["pos"][1])
		node.rotation.y = ViewMath.layout_rot_to_rot_y(float(p["rot"]))
		var visual := ModelFactory.build(asset, fp)
		node.add_child(visual)
		props.add_child(node)
		if p.has("light"):
			_add_prop_light(node, visual, str(p["light"]), fp)
		_add_occluder(node, visual, asset, fp)
		i += 1


func _add_prop_light(node: Node3D, visual: Node3D, kind: String, fp: Dictionary) -> void:
	var light := FlickerLight.new()
	light.name = "Light"
	light.shadow_enabled = true
	light.glow_mesh = visual.find_child("Glow", true, false) as MeshInstance3D
	var h := float(fp.get("light_height", 1.0))
	if kind == "fire":
		light.light_color = fire_color
		light.base_energy = fire_energy
		light.omni_range = fire_range
		light.wobble = 0.35
		light.wobble_speed = 3.0
		light.position = Vector3(0, h, 0)
	else:
		light.light_color = lamp_color
		light.base_energy = lamp_energy
		light.omni_range = lamp_range
		light.position = Vector3(0, h, 0) + lamp_light_offset
		if kind == "lamp_flicker":
			light.stutter_rate = 0.35
			light.wobble = 0.05
	light.omni_attenuation = 1.2
	light.light_volumetric_fog_energy = lamp_fog
	node.add_child(light)


## Tall props get a box (prop local) used to fade them while they hide the robot.
func _add_occluder(node: Node3D, visual: Node3D, asset: String, fp: Dictionary) -> void:
	var h := float(fp.get("height", 0.0))
	if h < cutaway_min_height:
		return
	var size: Array = fp["size"]
	var sx := float(size[0])
	var sz := float(size[1])
	if asset == "tree":  # the crown is wider than the trunk footprint
		sx = 4.0
		sz = 4.0
	var meshes: Array = visual.find_children("*", "GeometryInstance3D", true, false)
	if visual is GeometryInstance3D:
		meshes.append(visual)
	var box := AABB(Vector3(-sx * 0.5, 0.0, -sz * 0.5), Vector3(sx, h, sz))
	_occluders.append({"node": node, "box": box, "meshes": meshes, "fade": 0.0})


func _update_cutaway(delta: float) -> void:
	var from := _robot.global_position + Vector3(0, 0.7, 0)
	var to_cam := _camera.global_transform.basis.z
	for o: Dictionary in _occluders:
		var node: Node3D = o["node"]
		var inv := node.global_transform.affine_inverse()
		var box: AABB = o["box"]
		var hides := box.intersects_ray(inv * from, inv.basis * to_cam) != null
		var want := cutaway_amount if hides else 0.0
		var fade := move_toward(float(o["fade"]), want, cutaway_speed * delta)
		if not is_equal_approx(fade, float(o["fade"])):
			o["fade"] = fade
			for m: GeometryInstance3D in o["meshes"]:
				m.transparency = fade


func _build_robot() -> void:
	var fp: Dictionary = layout["footprints"]["robot"]
	_robot = Node3D.new()
	_robot.name = "Robot"
	add_child(_robot)
	_robot_visual = ModelFactory.build("robot", fp)
	_robot.add_child(_robot_visual)
	_robot_anim = ModelFactory.find_anim_player(_robot_visual)
	_robot_glow = _robot_visual.find_child("Glow", true, false) as MeshInstance3D
	_headlight = SpotLight3D.new()
	_headlight.name = "Headlight"
	_headlight.position = Vector3(0.35, float(fp.get("headlight_height", 1.1)), 0)
	_headlight.rotation_degrees = Vector3(-headlight_tilt, -90.0, 0)  # -Z of the light -> +X of the robot
	_headlight.light_color = headlight_color
	_headlight.light_energy = headlight_energy
	_headlight.spot_range = headlight_range
	_headlight.spot_angle = headlight_angle
	_headlight.spot_attenuation = 0.8
	_headlight.spot_angle_attenuation = 1.5
	_headlight.shadow_enabled = true
	_headlight.light_volumetric_fog_energy = headlight_fog
	_robot.add_child(_headlight)


func _build_drones() -> void:
	var fp: Dictionary = layout["footprints"]["scrap_drone"]
	var parent := Node3D.new()
	parent.name = "Drones"
	add_child(parent)
	for d: Dictionary in sim.drones:
		var node := Node3D.new()
		node.name = "Drone_%d" % d["id"]
		parent.add_child(node)
		var visual := ModelFactory.build("scrap_drone", fp)
		visual.position.y = _hover_height
		node.add_child(visual)
		var eye := OmniLight3D.new()
		eye.name = "Eye"
		eye.light_color = eye_color
		eye.light_energy = eye_energy
		eye.omni_range = eye_range
		eye.shadow_enabled = false
		eye.position = Vector3(0.45, 0.0, 0.0)
		visual.add_child(eye)
		var anim := ModelFactory.find_anim_player(visual)
		_play(anim, "hover", true)
		_drones.append({"node": node, "visual": visual, "anim": anim, "eye": eye})


func _build_canisters() -> void:
	var fp: Dictionary = layout["footprints"]["fuel_canister"]
	var parent := Node3D.new()
	parent.name = "Canisters"
	add_child(parent)
	for c: Dictionary in sim.canisters:
		var node := Node3D.new()
		node.name = "Canister_%d" % c["id"]
		node.position = ViewMath.to_world(c["pos"])
		node.add_child(ModelFactory.build("fuel_canister", fp))
		var glint := OmniLight3D.new()
		glint.light_color = canister_glint_color
		glint.light_energy = canister_glint_energy
		glint.omni_range = 1.8
		glint.position = Vector3(0, 0.8, 0)
		node.add_child(glint)
		parent.add_child(node)
		_canisters.append(node)


func _build_marker() -> void:
	var torus := TorusMesh.new()
	torus.inner_radius = 0.3
	torus.outer_radius = 0.38
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.albedo_color = Color(0.6, 1.0, 0.7)
	_marker = MeshInstance3D.new()
	_marker.name = "ClickMarker"
	_marker.mesh = torus
	_marker.material_override = mat
	_marker.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_marker.visible = false
	add_child(_marker)


func _build_camera() -> void:
	_camera = Camera3D.new()
	_camera.name = "Camera"
	_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	_camera.keep_aspect = Camera3D.KEEP_WIDTH
	_camera.size = view_width
	_camera.rotation_degrees = Vector3(-30, 45, 0)
	_camera.near = 0.5
	_camera.far = camera_distance * 2.5
	add_child(_camera)
	_camera.make_current()


# ---- presenting --------------------------------------------------------------------------------

func _present(delta: float, snap: bool) -> void:
	# Robot.
	_robot.position = ViewMath.to_world(sim.robot_pos)
	var want := ViewMath.heading_to_rot_y(sim.robot_heading)
	_robot.rotation.y = want if snap else ViewMath.lerp_angle_to(_robot.rotation.y, want, delta * 14.0)
	_animate_robot()
	# Drones.
	for i in _drones.size():
		var d: Dictionary = sim.drones[i]
		var v: Dictionary = _drones[i]
		var node: Node3D = v["node"]
		if not d["alive"]:
			node.visible = false
			continue
		node.position = ViewMath.to_world(d["pos"])
		var dw := ViewMath.heading_to_rot_y(d["heading"])
		node.rotation.y = dw if snap else ViewMath.lerp_angle_to(node.rotation.y, dw, delta * 8.0)
		var flash := float(d["hit_flash"]) > 0.0
		var visual: Node3D = v["visual"]
		visual.scale = Vector3.ONE * (1.2 if flash else 1.0)
		(v["eye"] as OmniLight3D).light_energy = eye_energy * (eye_hit_boost if flash else 1.0)
		if v["anim"] == null:
			visual.position.y = _hover_height + sin(_time * 3.0 + i) * 0.08
	# Canisters.
	for i in _canisters.size():
		var node: Node3D = _canisters[i]
		node.visible = not sim.canisters[i]["taken"]
		node.rotation.y = _time * 0.8 + i
	# Click marker.
	if _marker.visible:
		_marker_t += delta / 0.6
		var m := _marker.material_override as StandardMaterial3D
		m.albedo_color.a = 1.0 - _marker_t
		_marker.scale = Vector3.ONE * (1.0 + _marker_t * 0.6)
		if _marker_t >= 1.0:
			_marker.visible = false
	_update_cutaway(delta)
	# Camera.
	var target := _robot.position
	if snap:
		_cam_target = target
	else:
		_cam_target = _cam_target.lerp(target, 1.0 - exp(-follow_speed * delta))
	_camera.position = _cam_target + _camera.global_transform.basis.z * camera_distance
	# HUD.
	_hud.set_fuel(sim.fuel, sim.fuel_max)
	if sim.outcome != _shown_outcome:
		_shown_outcome = sim.outcome
		_hud.set_outcome(sim.outcome)


func _animate_robot() -> void:
	match sim.robot_anim:
		"walk":
			_play(_robot_anim, "walk", true)
		"attack":
			if _play(_robot_anim, "attack", false):
				_robot_anim.seek(sim.attack_phase * _robot_anim.current_animation_length, true)
		"off":
			if _robot_anim != null:
				_robot_anim.pause()
		_:
			_play(_robot_anim, "idle", true)
	if _robot_anim == null:
		# Stand-in motion: a bob while walking, a lunge on the swing.
		var bob := absf(sin(_time * 10.0)) * 0.08 if sim.robot_anim == "walk" else 0.0
		var lunge := sin(sim.attack_phase * PI) * 0.35 if sim.robot_anim == "attack" else 0.0
		_robot_visual.position = Vector3(lunge, bob, 0)
		_robot_visual.rotation.z = -lunge * 0.6


## Plays a named animation if the player has one; returns false when it cannot.
func _play(anim: AnimationPlayer, want: String, loop: bool) -> bool:
	if anim == null:
		return false
	var found := ViewMath.find_anim(anim.get_animation_list(), want)
	if found.is_empty():
		return false
	if anim.current_animation != found or not anim.is_playing():
		var a := anim.get_animation(found)
		if loop and a.loop_mode == Animation.LOOP_NONE:
			a.loop_mode = Animation.LOOP_LINEAR
		anim.play(found)
	return true


func _on_sim_event(e: Dictionary) -> void:
	match e["type"]:
		"pickup":
			for c: Dictionary in sim.canisters:
				if c["taken"] and c["pos"] == e["pos"]:
					canister_taken.emit(c["id"])
		"drone_destroyed":
			_burst(ViewMath.to_world(e["pos"], _hover_height))
			for d: Dictionary in sim.drones:
				if not d["alive"] and d["pos"] == e["pos"]:
					drone_destroyed.emit(d["id"])
		"out_of_fuel":
			_power_down()


## The robot's lights die over headlight_fade_time (GDD section 7).
func _power_down() -> void:
	var tw := create_tween().set_parallel(true)
	tw.tween_property(_headlight, "light_energy", 0.0, headlight_fade_time)
	if _robot_glow != null:
		var m := (_robot_glow.material_override as StandardMaterial3D).duplicate() as StandardMaterial3D
		_robot_glow.material_override = m
		tw.tween_property(m, "emission_energy_multiplier", 0.0, headlight_fade_time)


## A short orange flash where a drone dies.
func _burst(at: Vector3) -> void:
	var flash := OmniLight3D.new()
	flash.light_color = Color(1.0, 0.55, 0.2)
	flash.light_energy = 8.0
	flash.omni_range = 5.0
	flash.position = at
	add_child(flash)
	var tw := create_tween()
	tw.tween_property(flash, "light_energy", 0.0, 0.5)
	tw.tween_callback(flash.queue_free)


func _show_marker(at: Vector3, attack: bool) -> void:
	_marker.position = at + Vector3(0, 0.05, 0)
	_marker_t = 0.0
	_marker.visible = true
	var m := _marker.material_override as StandardMaterial3D
	m.albedo_color = Color(1.0, 0.3, 0.2) if attack else Color(0.6, 1.0, 0.7)
