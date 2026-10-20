class_name Hud
extends CanvasLayer
## Fuel bar, outcome message, control hint and the F3 stats readout. Built in code; Main feeds it.

## Fuel bar fill when there is plenty, and when it runs low.
@export var fuel_color: Color = Color(1.0, 0.75, 0.2)
@export var fuel_low_color: Color = Color(1.0, 0.25, 0.15)
## Fuel fraction below which the bar turns to fuel_low_color.
@export_range(0.0, 1.0) var low_fraction: float = 0.25

var _fuel_bar: ProgressBar
var _fuel_fill: StyleBoxFlat
var _message: Label
var _stats: Label
var _ms_avg := 16.7
var _last_usec := 0


func _ready() -> void:
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)

	var fuel_label := Label.new()
	fuel_label.text = "FUEL"
	fuel_label.position = Vector2(24, 18)
	root.add_child(fuel_label)

	_fuel_bar = ProgressBar.new()
	_fuel_bar.name = "FuelBar"
	_fuel_bar.position = Vector2(70, 18)
	_fuel_bar.size = Vector2(260, 22)
	_fuel_bar.show_percentage = false
	_fuel_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0.05, 0.06, 0.09, 0.8)
	bg.border_color = Color(0.6, 0.6, 0.6, 0.6)
	bg.set_border_width_all(1)
	_fuel_fill = StyleBoxFlat.new()
	_fuel_fill.bg_color = fuel_color
	_fuel_bar.add_theme_stylebox_override("background", bg)
	_fuel_bar.add_theme_stylebox_override("fill", _fuel_fill)
	root.add_child(_fuel_bar)

	_message = Label.new()
	_message.name = "Message"
	_message.set_anchors_preset(Control.PRESET_CENTER)
	_message.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_message.add_theme_font_size_override("font_size", 40)
	_message.add_theme_color_override("font_outline_color", Color.BLACK)
	_message.add_theme_constant_override("outline_size", 8)
	_message.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_message.grow_vertical = Control.GROW_DIRECTION_BOTH
	root.add_child(_message)

	var hint := Label.new()
	hint.text = "Left click: walk / attack a drone    R: restart    F: fog on/off    F3: stats"
	hint.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	hint.grow_horizontal = Control.GROW_DIRECTION_BOTH
	hint.grow_vertical = Control.GROW_DIRECTION_BEGIN
	hint.position.y -= 12
	hint.modulate = Color(1, 1, 1, 0.7)
	root.add_child(hint)

	_stats = Label.new()
	_stats.name = "Stats"
	_stats.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	_stats.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	_stats.position += Vector2(-16, 16)
	_stats.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_stats.visible = false
	root.add_child(_stats)


func _process(_delta: float) -> void:
	# Wall-clock time between frames (delta is fixed under --fixed-fps, so it would always read 16.7).
	var now := Time.get_ticks_usec()
	if _last_usec > 0:
		_ms_avg = lerpf(_ms_avg, float(now - _last_usec) / 1000.0, 0.1)
	_last_usec = now
	if _stats.visible:
		_stats.text = "%.1f ms  %d FPS  %d draw calls" % [
			_ms_avg,
			Engine.get_frames_per_second(),
			Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
		]


func set_fuel(fuel: float, fuel_max: float) -> void:
	_fuel_bar.max_value = fuel_max
	_fuel_bar.value = fuel
	_fuel_fill.bg_color = fuel_low_color if fuel < fuel_max * low_fraction else fuel_color


## outcome is the sim's outcome string; GDD section 7 wording.
func set_outcome(outcome: String) -> void:
	match outcome:
		"out_of_fuel":
			_message.text = "OUT OF FUEL - R to restart"
			_message.add_theme_color_override("font_color", Color(1.0, 0.35, 0.25))
		"tank_stable":
			_message.text = "Tank stable"
			_message.add_theme_color_override("font_color", Color(1.0, 0.85, 0.4))
		_:
			_message.text = ""


func toggle_stats() -> void:
	_stats.visible = not _stats.visible


func stats_visible() -> bool:
	return _stats.visible
