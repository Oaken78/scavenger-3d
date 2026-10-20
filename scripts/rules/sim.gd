class_name Sim
extends RefCounted
## Scavenger rules: a presentation-free simulation in world metres (Vector2 = x east, z south).
## Identical copy in scavenger-2d and scavenger-3d. Presentations only read state and call commands.
##
## Use:  var sim := Sim.new(layout_dict)   # layout_dict = parsed design/layout.json
##       sim.advance(delta)                 # every frame; runs fixed 1/60 s steps inside
##       sim.command_move(p) / sim.command_attack(id) / sim.drone_at(p, r)
## Read: robot_pos, robot_heading, robot_anim, attack_phase, fuel, fuel_max, outcome,
##       drones (Array of Dictionary: id, pos, heading, hp, alive, state, hit_flash),
##       canisters (Array of Dictionary: id, pos, taken), events (rebuilt each advance()).
## Event types: pickup, swing, drone_hit, drone_destroyed, robot_hurt, out_of_fuel, tank_stable.
## Each event is {type: String, pos: Vector2}.
## Once outcome != "running" the sim stops advancing (restart = make a new Sim).

const STEP := 1.0 / 60.0
const CELL := 0.5
const WALK_SPEED := 3.5
const FUEL_MAX := 100.0
const DRAIN_STAND := 0.8
const DRAIN_WALK := 1.5
const CANISTER_FUEL := 35.0
const PICKUP_RADIUS := 0.8
const REACH := 1.6
const SWING_TIME := 0.6
const HIT_AT := 0.5  # attack phase at which the swing lands
const DRONE_HP := 3
const DRONE_NOTICE := 7.0
const DRONE_GIVE_UP := 14.0
const DRONE_SPEED := 2.5
const DRONE_PATROL_SPEED := 1.2
const DRONE_TOUCH := 1.0
const DRONE_TOUCH_COST := 8.0
const DRONE_TOUCH_COOLDOWN := 1.0
const HIT_FLASH := 0.15
const REPATH_TIME := 0.3

var robot_pos: Vector2
var robot_heading := 0.0  ## radians, 0 = +x, increasing towards +z
var robot_anim := "idle"  ## idle | walk | attack | off
var attack_phase := 0.0  ## 0..1 through the current swing (0 when not swinging)
var fuel := FUEL_MAX
var fuel_max := FUEL_MAX
var outcome := "running"  ## running | out_of_fuel | tank_stable
var drones: Array = []
var canisters: Array = []
var events: Array = []
var time := 0.0
var robot_radius := 0.45

var _bounds: Rect2
var _cols := 0
var _rows := 0
var _grid: AStarGrid2D
var _rects: Array = []  ## {center, half, rot} blocking footprints (raw, not inflated)
var _acc := 0.0
var _path: Array = []  ## remaining waypoints (Vector2)
var _attack_id := -1
var _swing := -1.0  ## seconds into the current swing, -1 = none
var _repath := 0.0
var _patrol: Array = []  ## per drone: {center, radius, angle}


func _init(layout: Dictionary) -> void:
	var b: Array = layout["bounds"]
	_bounds = Rect2(Vector2(b[0], b[1]), Vector2(b[2] - b[0], b[3] - b[1]))
	_cols = int(round(_bounds.size.x / CELL))
	_rows = int(round(_bounds.size.y / CELL))
	var fps: Dictionary = layout["footprints"]
	robot_radius = float(fps.get("robot", {}).get("radius", 0.45))
	for p in layout["props"]:
		var size: Array = fps[p["asset"]]["size"]
		if size[0] > 0 and size[1] > 0:
			_rects.append({
				"center": Vector2(p["pos"][0], p["pos"][1]),
				"half": Vector2(size[0], size[1]) * 0.5,
				"rot": deg_to_rad(float(p["rot"])),
			})
	_build_grid()
	robot_pos = Vector2(layout["player_start"][0], layout["player_start"][1])
	var i := 0
	for c in layout["pickups"]:
		canisters.append({"id": i, "pos": Vector2(c["pos"][0], c["pos"][1]), "taken": false})
		i += 1
	i = 0
	for e in layout["enemies"]:
		var center := Vector2(e["pos"][0], e["pos"][1])
		var angle := float(i) * 2.1
		var radius := float(e["patrol_radius"])
		_patrol.append({"center": center, "radius": radius, "angle": angle})
		drones.append({
			"id": i, "pos": center + Vector2.from_angle(angle) * radius, "heading": angle + PI * 0.5,
			"hp": DRONE_HP, "alive": true, "state": "patrol", "hit_flash": 0.0, "touch_cd": 0.0,
		})
		i += 1


# ---- public API -------------------------------------------------------------------------------

## Walk to a world point (nearest reachable spot if it is blocked). Ignored when not running.
func command_move(target: Vector2) -> void:
	if outcome != "running":
		return
	_attack_id = -1
	_swing = -1.0
	attack_phase = 0.0
	_path = path_to(target)


## Walk into reach of a drone and swing until it is destroyed. Ignored when not running.
func command_attack(drone_id: int) -> void:
	if outcome != "running" or drone_id < 0 or drone_id >= drones.size():
		return
	if not drones[drone_id]["alive"]:
		return
	_attack_id = drone_id
	_swing = -1.0
	attack_phase = 0.0
	_repath = 0.0
	_path = []


## Id of the nearest living drone within radius of point, or -1.
func drone_at(point: Vector2, radius: float) -> int:
	var best := -1
	var best_d := radius
	for d in drones:
		if d["alive"]:
			var dist: float = d["pos"].distance_to(point)
			if dist <= best_d:
				best_d = dist
				best = d["id"]
	return best


## Waypoints (excluding the robot's current spot) to reach target, from the robot's position.
func path_to(target: Vector2) -> Array:
	var goal := _nearest_reachable(_to_cell(target), _to_cell(robot_pos))
	var from := _to_cell(robot_pos)
	var out: Array = []
	if _grid.is_in_boundsv(from) and not _grid.is_point_solid(from) and goal.x >= 0:
		var ids := _grid.get_id_path(from, goal)
		for k in range(1, ids.size()):
			out.append(_cell_center(ids[k]))
		if goal == _to_cell(target) or out.is_empty():
			var exact := target.clamp(_bounds.position, _bounds.end)
			if out.is_empty():
				out.append(exact if _to_cell(exact) == goal else _cell_center(goal))
			else:
				out[out.size() - 1] = exact
	return out


## True when point lies inside a footprint grown by inflate metres.
func blocked_at(point: Vector2, inflate := 0.0) -> bool:
	for r in _rects:
		var local: Vector2 = (point - r["center"]).rotated(-r["rot"])
		var h: Vector2 = r["half"] + Vector2(inflate, inflate)
		if absf(local.x) < h.x and absf(local.y) < h.y:
			return true
	return false


## Advance the simulation by delta seconds (fixed 1/60 s steps; leftovers carry over).
func advance(delta: float) -> void:
	events = []
	_acc += delta
	while _acc >= STEP - 0.000001 and outcome == "running":
		_acc -= STEP
		_step(STEP)
	if _acc < 0.0:
		_acc = 0.0


# ---- internals --------------------------------------------------------------------------------

func _step(dt: float) -> void:
	time += dt
	var moved := _step_robot(dt)
	_step_drones(dt)
	fuel -= (DRAIN_WALK if moved else DRAIN_STAND) * dt
	for c in canisters:
		if not c["taken"] and c["pos"].distance_to(robot_pos) <= PICKUP_RADIUS:
			c["taken"] = true
			fuel = minf(fuel + CANISTER_FUEL, fuel_max)
			_event("pickup", c["pos"])
	if fuel <= 0.0:
		fuel = 0.0
		outcome = "out_of_fuel"
		robot_anim = "off"
		_path = []
		_swing = -1.0
		attack_phase = 0.0
		_event("out_of_fuel", robot_pos)
	elif canisters.all(func(c): return c["taken"]):
		outcome = "tank_stable"
		_event("tank_stable", robot_pos)


func _step_robot(dt: float) -> bool:
	var moved := false
	if _attack_id >= 0:
		var d: Dictionary = drones[_attack_id]
		if not d["alive"]:
			_attack_id = -1
			_swing = -1.0
			attack_phase = 0.0
		else:
			var to_drone: Vector2 = d["pos"] - robot_pos
			if to_drone.length() <= REACH:
				_path = []
				robot_heading = to_drone.angle()
				if _swing < 0.0:
					_swing = 0.0
					_event("swing", robot_pos)
				else:
					var before := _swing
					_swing += dt
					if before < SWING_TIME * HIT_AT and _swing >= SWING_TIME * HIT_AT:
						_hit_drone(d)
					if _swing >= SWING_TIME:
						_swing = -1.0
				attack_phase = clampf(_swing / SWING_TIME, 0.0, 1.0) if _swing >= 0.0 else 0.0
			else:
				_swing = -1.0
				attack_phase = 0.0
				_repath -= dt
				if _repath <= 0.0 or _path.is_empty():
					_repath = REPATH_TIME
					_path = path_to(d["pos"])
	if _swing < 0.0 and not _path.is_empty():
		var budget := WALK_SPEED * dt
		while budget > 0.0 and not _path.is_empty():
			var to_wp: Vector2 = _path[0] - robot_pos
			var dist := to_wp.length()
			if dist > 0.0001:
				robot_heading = to_wp.angle()
			if dist <= budget:
				robot_pos = _path[0]
				_path.remove_at(0)
				budget -= dist
			else:
				robot_pos += to_wp / dist * budget
				budget = 0.0
			moved = true
	if _swing >= 0.0:
		robot_anim = "attack"
	elif moved:
		robot_anim = "walk"
	else:
		robot_anim = "idle"
	return moved


func _hit_drone(d: Dictionary) -> void:
	d["hp"] -= 1
	d["hit_flash"] = HIT_FLASH
	_event("drone_hit", d["pos"])
	if d["hp"] <= 0:
		d["alive"] = false
		_event("drone_destroyed", d["pos"])


func _step_drones(dt: float) -> void:
	for d in drones:
		if not d["alive"]:
			continue
		var pt: Dictionary = _patrol[d["id"]]
		pt["angle"] += DRONE_PATROL_SPEED / pt["radius"] * dt
		d["hit_flash"] = maxf(0.0, d["hit_flash"] - dt)
		d["touch_cd"] = maxf(0.0, d["touch_cd"] - dt)
		var dist_robot: float = d["pos"].distance_to(robot_pos)
		if d["state"] == "patrol" and dist_robot <= DRONE_NOTICE:
			d["state"] = "chase"
		elif d["state"] == "chase" and dist_robot > DRONE_GIVE_UP:
			d["state"] = "patrol"
		var goal: Vector2
		if d["state"] == "chase":
			goal = robot_pos
		else:
			goal = pt["center"] + Vector2.from_angle(pt["angle"]) * pt["radius"]
		var to_goal: Vector2 = goal - d["pos"]
		var gd := to_goal.length()
		var stop := 0.7 if d["state"] == "chase" else 0.0
		if gd > stop + 0.0001:
			var step := minf(DRONE_SPEED * dt, gd - stop)
			d["pos"] += to_goal / gd * step
			d["heading"] = to_goal.angle()
		if d["state"] == "chase" and d["pos"].distance_to(robot_pos) <= DRONE_TOUCH and d["touch_cd"] <= 0.0:
			d["touch_cd"] = DRONE_TOUCH_COOLDOWN
			fuel -= DRONE_TOUCH_COST
			_event("robot_hurt", robot_pos)


func _event(type: String, pos: Vector2) -> void:
	events.append({"type": type, "pos": pos})


func _build_grid() -> void:
	_grid = AStarGrid2D.new()
	_grid.region = Rect2i(0, 0, _cols, _rows)
	_grid.cell_size = Vector2.ONE
	_grid.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_ONLY_IF_NO_OBSTACLES
	_grid.update()
	for x in _cols:
		for y in _rows:
			if blocked_at(_cell_center(Vector2i(x, y)), robot_radius):
				_grid.set_point_solid(Vector2i(x, y), true)


func _to_cell(p: Vector2) -> Vector2i:
	var q := (p - _bounds.position) / CELL
	return Vector2i(clampi(int(floor(q.x)), 0, _cols - 1), clampi(int(floor(q.y)), 0, _rows - 1))


func _cell_center(c: Vector2i) -> Vector2:
	return _bounds.position + (Vector2(c) + Vector2(0.5, 0.5)) * CELL


## The cell nearest to want that can be walked to from from_cell ((-1,-1) if none).
func _nearest_reachable(want: Vector2i, from_cell: Vector2i) -> Vector2i:
	if _grid.is_point_solid(from_cell):
		return Vector2i(-1, -1)
	var seen := {from_cell: true}
	var queue: Array[Vector2i] = [from_cell]
	var best := from_cell
	var best_d := INF
	var head := 0
	while head < queue.size():
		var c := queue[head]
		head += 1
		var dd := Vector2(c - want).length_squared()
		if dd < best_d:
			best_d = dd
			best = c
		for off in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
			var n: Vector2i = c + off
			if n.x < 0 or n.y < 0 or n.x >= _cols or n.y >= _rows or seen.has(n) or _grid.is_point_solid(n):
				continue
			seen[n] = true
			queue.append(n)
	return best
