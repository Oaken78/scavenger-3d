class_name FlickerLight
extends OmniLight3D
## An omni light whose energy wobbles (fire) and, optionally, drops out in short stutters (a failing lamp).
## Presentation only: a fixed-seed RNG keeps it the same every run.

## Energy at full brightness.
@export var base_energy: float = 3.0
## How far the smooth wobble swings, as a fraction of base_energy (0 = steady).
@export_range(0.0, 1.0) var wobble: float = 0.0
## Wobble speed in cycles per second.
@export var wobble_speed: float = 6.0
## Chance per second that a stutter (a run of quick dropouts) starts. 0 = never.
@export var stutter_rate: float = 0.0
## Length of a stutter in seconds.
@export var stutter_time: float = 0.6
## Energy fraction during a dropout.
@export_range(0.0, 1.0) var dropout_level: float = 0.08
## Emissive mesh that dims with the light (the bulb or the embers); optional.
var glow_mesh: MeshInstance3D

var _t := 0.0
var _stutter_left := 0.0
var _rng := RandomNumberGenerator.new()
var _glow_base := 1.0
var _glow_mat: StandardMaterial3D


func _ready() -> void:
	_rng.seed = hash(name)
	light_energy = base_energy


func _process(delta: float) -> void:
	_t += delta
	var f := 1.0
	if wobble > 0.0:
		var w := sin(_t * TAU * wobble_speed) * 0.5 + sin(_t * TAU * wobble_speed * 2.37 + 1.3) * 0.3
		w += sin(_t * TAU * wobble_speed * 0.41 + 0.7) * 0.2
		f += w * wobble
	if stutter_rate > 0.0:
		if _stutter_left <= 0.0 and _rng.randf() < stutter_rate * delta:
			_stutter_left = stutter_time
		if _stutter_left > 0.0:
			_stutter_left -= delta
			if int(_t * 22.0) % 3 != 0:
				f = dropout_level
	light_energy = base_energy * maxf(f, 0.0)
	_dim_glow(f)


func _dim_glow(f: float) -> void:
	if glow_mesh == null:
		return
	if _glow_mat == null:
		_glow_mat = ModelFactory.writable_material(glow_mesh)
		if _glow_mat == null:
			glow_mesh = null
			return
		_glow_base = _glow_mat.emission_energy_multiplier
	_glow_mat.emission_energy_multiplier = _glow_base * clampf(f, 0.05, 1.5)
