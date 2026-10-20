extends Node
## DevHarness: dormant unless Godot gets `-- --scenario=res://test/scenarios/<name>.json --out=<abs dir>`.
## Runs the scenario steps, counts engine errors, captures screenshots and metrics, writes result.json,
## then quits with: 0 ok, 10 assertion failed, 11 engine errors, 12 timeout, 13 scenario could not load.
## Step schema: .claude/skills/godot-cli/SKILL.md. Driven by tools/smoke.ps1 and tools/shots.ps1.

const EXIT_OK := 0
const EXIT_ASSERT := 10
const EXIT_ENGINE_ERROR := 11
const EXIT_TIMEOUT := 12
const EXIT_LOAD := 13


## Counts ERROR / SCRIPT ERROR / SHADER ERROR lines (push_error arrives with an empty rationale and the text in code).
class ErrorCounter:
	extends Logger
	var errors: PackedStringArray = PackedStringArray()
	var _mutex := Mutex.new()

	func _log_error(
		function: String,
		file: String,
		line: int,
		code: String,
		rationale: String,
		_editor_notify: bool,
		error_type: Logger.ErrorType,
		_script_backtraces: Array[ScriptBacktrace]
	) -> void:
		if error_type == ERROR_TYPE_WARNING:
			return
		var message := rationale if not rationale.is_empty() else code
		_mutex.lock()
		errors.append("%s (%s:%d in %s)" % [message, file, line, function])
		_mutex.unlock()

	func _log_message(_message: String, _error: bool) -> void:
		pass


var _active := false
var _counter: ErrorCounter
var _scenario_path := ""
var _out_dir := ""
var _seed := 1234
var _screens := false
var _running := false
var _finished := false
var _frame := 0
var _timeout_frames := 3600
var _steps_log: Array = []
var _screenshots: Array = []


func _init() -> void:
	for a: String in OS.get_cmdline_user_args():
		if a.begins_with("--scenario="):
			_scenario_path = a.trim_prefix("--scenario=")
		elif a.begins_with("--out="):
			_out_dir = a.trim_prefix("--out=")
		elif a.begins_with("--seed="):
			_seed = int(a.trim_prefix("--seed="))
		elif a == "--screens=1" or a == "--screens":
			_screens = true
	if _scenario_path.is_empty():
		return
	_active = true
	_counter = ErrorCounter.new()
	OS.add_logger(_counter)


func _ready() -> void:
	if not _active:
		set_process(false)
		return
	process_mode = Node.PROCESS_MODE_ALWAYS
	if _out_dir.is_empty():
		_out_dir = ProjectSettings.globalize_path("res://.reports/last")
	DirAccess.make_dir_recursive_absolute(_out_dir)
	_run_scenario()


func _process(_delta: float) -> void:
	if not _running:
		return
	_frame += 1
	if _frame > _timeout_frames:
		_finish(EXIT_TIMEOUT, "scenario timed out after %d frames" % _timeout_frames)


func _run_scenario() -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	var scenario := _load_scenario()
	if scenario.is_empty():
		_finish(EXIT_LOAD, "could not load scenario %s" % _scenario_path)
		return
	seed(_seed)
	_timeout_frames = int(scenario.get("timeout_frames", 3600))
	_running = true
	var scene_path: String = str(scenario.get("scene", ""))
	if not scene_path.is_empty():
		var current := get_tree().current_scene
		if current == null or current.scene_file_path != scene_path:
			var err := get_tree().change_scene_to_file(scene_path)
			if err != OK:
				_finish(EXIT_LOAD, "change_scene_to_file(%s) failed with %d" % [scene_path, err])
				return
			await get_tree().process_frame
			await get_tree().process_frame
	var steps: Array = scenario.get("steps", [])
	var index := 0
	for step_v: Variant in steps:
		if _finished:
			return
		index += 1
		var step: Dictionary = step_v
		var outcome: Dictionary = await _run_step(step)
		_steps_log.append(
			{
				"index": index,
				"step": _step_name(step),
				"status": outcome.status,
				"detail": outcome.detail
			}
		)
		if outcome.status == "fail":
			_finish(
				EXIT_ASSERT, "step %d %s failed: %s" % [index, _step_name(step), outcome.detail]
			)
			return
		if outcome.status == "error":
			_finish(EXIT_ENGINE_ERROR, "step %d %s: %s" % [index, _step_name(step), outcome.detail])
			return
	_finish(EXIT_OK, "ok")


func _run_step(step: Dictionary) -> Dictionary:
	if step.has("wait_frames"):
		await _wait_frames(int(step["wait_frames"]))
		return _ok()
	if step.has("assert_node"):
		var node := _find_node(str(step["assert_node"]))
		var want: bool = bool(step.get("exists", true))
		if (node != null) == want:
			return _ok()
		return _fail("node %s exists=%s, expected %s" % [step["assert_node"], node != null, want])
	if step.has("action_press"):
		var action := str(step["action_press"])
		if not InputMap.has_action(action):
			return _fail("unknown input action %s" % action)
		_send_action(action, true)
		await _wait_frames(int(step.get("frames", 1)))
		_send_action(action, false)
		await _wait_frames(2)
		return _ok()
	if step.has("key_tap"):
		var key_name := str(step["key_tap"])
		var keycode := OS.find_keycode_from_string(key_name)
		if keycode == KEY_NONE:
			return _fail("unknown key %s" % key_name)
		_send_key(keycode, true)
		await _wait_frames(int(step.get("frames", 1)))
		_send_key(keycode, false)
		await _wait_frames(2)
		return _ok()
	if step.has("mouse_click"):
		var pos_arr: Array = step["mouse_click"]
		var pos := Vector2(float(pos_arr[0]), float(pos_arr[1]))
		var button := MOUSE_BUTTON_LEFT
		if str(step.get("button", "left")) == "right":
			button = MOUSE_BUTTON_RIGHT
		_send_mouse(pos, button, true)
		await _wait_frames(int(step.get("frames", 1)))
		_send_mouse(pos, button, false)
		await _wait_frames(2)
		return _ok()
	if step.has("assert_prop"):
		var spec: Dictionary = step["assert_prop"]
		var node := _find_node(str(spec.get("node", ".")))
		if node == null:
			return _fail("node %s not found" % spec.get("node"))
		var value: Variant = node.get_indexed(NodePath(str(spec["prop"])))
		var expected: Variant = spec["value"]
		var op := str(spec.get("op", "=="))
		if _compare(value, op, expected):
			return _ok()
		return _fail(
			(
				"%s.%s is %s, expected %s %s"
				% [spec.get("node"), spec["prop"], str(value), op, str(expected)]
			)
		)
	if step.has("set_prop"):
		var spec: Dictionary = step["set_prop"]
		var node := _find_node(str(spec.get("node", ".")))
		if node == null:
			return _fail("node %s not found" % spec.get("node"))
		node.set_indexed(NodePath(str(spec["prop"])), spec["value"])
		return _ok()
	if step.has("call"):
		var spec: Dictionary = step["call"]
		var node := _find_node(str(spec.get("node", ".")))
		if node == null:
			return _fail("node %s not found" % spec.get("node"))
		var method := str(spec["method"])
		if not node.has_method(method):
			return _fail("node has no method %s" % method)
		node.callv(method, spec.get("args", []))
		await _wait_frames(1)
		return _ok()
	if step.has("expect_signal"):
		var spec: Dictionary = step["expect_signal"]
		var node := _find_node(str(spec.get("node", ".")))
		if node == null:
			return _fail("node %s not found" % spec.get("node"))
		var sig := str(spec["signal"])
		if not node.has_signal(sig):
			return _fail("node has no signal %s" % sig)
		var state := {"fired": false}
		var cb := func(
			_a: Variant = null, _b: Variant = null, _c: Variant = null, _d: Variant = null
		) -> void:
			state["fired"] = true
		node.connect(sig, cb, CONNECT_ONE_SHOT)
		var limit := int(spec.get("timeout_frames", 300))
		var waited := 0
		while not state["fired"] and waited < limit:
			await get_tree().process_frame
			waited += 1
		if is_instance_valid(node) and node.is_connected(sig, cb):
			node.disconnect(sig, cb)
		if state["fired"]:
			return _ok("after %d frames" % waited)
		return _fail("signal %s not emitted within %d frames" % [sig, limit])
	if step.has("screenshot"):
		var shot_name := str(step["screenshot"])
		if DisplayServer.get_name() == "headless":
			return _skip("screenshot %s skipped: headless" % shot_name)
		if not _screens:
			return _skip("screenshot %s skipped: --screens not set" % shot_name)
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		var img := get_viewport().get_texture().get_image()
		if img == null or img.is_empty():
			return _fail("screenshot %s: empty image" % shot_name)
		var path := _out_dir.path_join(shot_name + ".png")
		var err := img.save_png(path)
		if err != OK:
			return _fail("screenshot %s: save_png failed with %d" % [shot_name, err])
		_screenshots.append(path)
		return _ok("saved " + path)
	if step.has("metrics"):
		var spec: Dictionary = step["metrics"]
		return await _collect_metrics(
			str(spec.get("name", "metrics")), int(spec.get("frames", 300))
		)
	if step.has("assert_no_errors"):
		if _counter.errors.is_empty():
			return _ok()
		return _error(
			"%d engine error(s), first: %s" % [_counter.errors.size(), _counter.errors[0]]
		)
	if step.has("inject_error"):
		push_error("DevHarness inject_error: %s" % str(step["inject_error"]))
		await _wait_frames(1)
		return _ok()
	return _fail("unknown step %s" % JSON.stringify(step))


func _collect_metrics(metrics_name: String, frames: int) -> Dictionary:
	var samples := {
		"process_ms": [],
		"physics_ms": [],
		"frame_ms": [],
		"draw_calls": [],
		"nodes": [],
		"orphan_nodes": [],
		"static_mem_mb": [],
	}
	# frame_ms is wall-clock time between consecutive process frames (with --fixed-fps and no vsync that is
	# pure work time). The TIME_* monitors refresh only about once per second, so they are kept as extras.
	await get_tree().process_frame
	var last_usec := Time.get_ticks_usec()
	for i in range(frames):
		await get_tree().process_frame
		var now_usec := Time.get_ticks_usec()
		samples["frame_ms"].append(float(now_usec - last_usec) / 1000.0)
		last_usec = now_usec
		var p := Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0
		var ph := Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0
		samples["process_ms"].append(p)
		samples["physics_ms"].append(ph)
		samples["draw_calls"].append(
			Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)
		)
		samples["nodes"].append(Performance.get_monitor(Performance.OBJECT_NODE_COUNT))
		samples["orphan_nodes"].append(
			Performance.get_monitor(Performance.OBJECT_ORPHAN_NODE_COUNT)
		)
		samples["static_mem_mb"].append(
			Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0
		)
	var report := {
		"name": metrics_name,
		"frames": frames,
		"headless": DisplayServer.get_name() == "headless",
		"renderer": RenderingServer.get_current_rendering_method(),
	}
	for key: String in samples.keys():
		report[key] = _stats(samples[key])
	var path := _out_dir.path_join("metrics__%s.json" % metrics_name)
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		return _fail("cannot write " + path)
	f.store_string(JSON.stringify(report, "  "))
	f.close()
	return _ok("wrote " + path)


func _stats(values: Array) -> Dictionary:
	if values.is_empty():
		return {"p50": 0.0, "p95": 0.0, "max": 0.0, "mean": 0.0}
	var sorted := values.duplicate()
	sorted.sort()
	var total := 0.0
	for v: Variant in sorted:
		total += float(v)
	return {
		"p50": snappedf(float(sorted[int(sorted.size() * 0.5)]), 0.001),
		"p95": snappedf(float(sorted[mini(int(sorted.size() * 0.95), sorted.size() - 1)]), 0.001),
		"max": snappedf(float(sorted[sorted.size() - 1]), 0.001),
		"mean": snappedf(total / sorted.size(), 0.001),
	}


func _wait_frames(n: int) -> void:
	for i in range(maxi(n, 1)):
		await get_tree().process_frame


func _find_node(path: String) -> Node:
	var root := get_tree().current_scene
	if path == "." or path.is_empty():
		return root
	if path.begins_with("/root"):
		return get_tree().root.get_node_or_null(NodePath(path))
	if root == null:
		return null
	var n := root.get_node_or_null(NodePath(path))
	if n == null:
		n = root.find_child(path, true, false)
	return n


func _compare(value: Variant, op: String, expected: Variant) -> bool:
	var numeric := (value is float or value is int) and (expected is float or expected is int)
	if numeric:
		var a := float(value)
		var b := float(expected)
		match op:
			"==":
				return is_equal_approx(a, b)
			"!=":
				return not is_equal_approx(a, b)
			">":
				return a > b
			">=":
				return a >= b
			"<":
				return a < b
			"<=":
				return a <= b
		return false
	match op:
		"==":
			return value == expected
		"!=":
			return value != expected
	return false


func _send_action(action: String, pressed: bool) -> void:
	var ev := InputEventAction.new()
	ev.action = action
	ev.pressed = pressed
	ev.strength = 1.0 if pressed else 0.0
	Input.parse_input_event(ev)
	Input.flush_buffered_events()


func _send_key(keycode: Key, pressed: bool) -> void:
	var ev := InputEventKey.new()
	ev.keycode = keycode
	ev.physical_keycode = keycode
	ev.key_label = keycode
	ev.pressed = pressed
	Input.parse_input_event(ev)
	Input.flush_buffered_events()


func _send_mouse(pos: Vector2, button: MouseButton, pressed: bool) -> void:
	var move := InputEventMouseMotion.new()
	move.position = pos
	move.global_position = pos
	Input.parse_input_event(move)
	var ev := InputEventMouseButton.new()
	ev.position = pos
	ev.global_position = pos
	ev.button_index = button
	ev.pressed = pressed
	Input.parse_input_event(ev)
	Input.flush_buffered_events()


func _load_scenario() -> Dictionary:
	if not FileAccess.file_exists(_scenario_path):
		return {}
	var text := FileAccess.get_file_as_string(_scenario_path)
	var json := JSON.new()
	if json.parse(text) != OK:
		return {}
	if typeof(json.data) != TYPE_DICTIONARY:
		return {}
	return json.data


func _step_name(step: Dictionary) -> String:
	if step.is_empty():
		return "empty"
	return str(step.keys()[0])


func _ok(detail: String = "") -> Dictionary:
	return {"status": "ok", "detail": detail}


func _skip(detail: String) -> Dictionary:
	return {"status": "skipped", "detail": detail}


func _fail(detail: String) -> Dictionary:
	return {"status": "fail", "detail": detail}


func _error(detail: String) -> Dictionary:
	return {"status": "error", "detail": detail}


func _finish(code: int, message: String) -> void:
	if _finished:
		return
	_finished = true
	_running = false
	var engine_errors: Array = []
	if _counter != null:
		engine_errors = Array(_counter.errors)
	if code == EXIT_OK and not engine_errors.is_empty():
		code = EXIT_ENGINE_ERROR
		message = (
			"%d engine error(s) during the run, first: %s"
			% [engine_errors.size(), engine_errors[0]]
		)
	var result := {
		"ok": code == EXIT_OK,
		"code": code,
		"message": message,
		"frames": _frame,
		"seed": _seed,
		"scenario": _scenario_path,
		"headless": DisplayServer.get_name() == "headless",
		"steps": _steps_log,
		"engine_errors": engine_errors,
		"screenshots": _screenshots,
	}
	var f := FileAccess.open(_out_dir.path_join("result.json"), FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(result, "  "))
		f.close()
	print("DevHarness: %s (code %d, %d frames)" % [message, code, _frame])
	get_tree().quit(code)
