extends Node2D
## Minimal playable scene so the verification tiers have something real to run. Replace it.

signal level_started

@export var move_speed: float = 240.0
@export var start_delay_frames: int = 60

var _frames: int = 0
var _started: bool = false

@onready var _player: Node2D = $Player


func _process(delta: float) -> void:
	_frames += 1
	if not _started and _frames >= start_delay_frames:
		_started = true
		level_started.emit()
	var direction := Input.get_axis("ui_left", "ui_right")
	_player.position.x += direction * move_speed * delta
