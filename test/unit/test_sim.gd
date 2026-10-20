extends GutTest
## Rules of the shared Scavenger simulation (scripts/rules/sim.gd). Rules only, no tuning values.


func _layout() -> Dictionary:
	var f := FileAccess.open("res://design/layout.json", FileAccess.READ)
	return JSON.parse_string(f.get_as_text())


## A small empty map: one robot, optional canisters and drones, no props.
func _tiny(pickups: Array = [], enemies: Array = []) -> Dictionary:
	var l := _layout()
	l["props"] = []
	l["pickups"] = pickups
	l["enemies"] = enemies
	return l


func _run(sim: Sim, seconds: float) -> void:
	for i in int(seconds * 60.0):
		sim.advance(1.0 / 60.0)


func _event_count(sim: Sim, type: String, seconds: float) -> int:
	var n := 0
	for i in int(seconds * 60.0):
		sim.advance(1.0 / 60.0)
		for e in sim.events:
			if e["type"] == type:
				n += 1
	return n


func test_walking_drains_faster_than_standing() -> void:
	var a := Sim.new(_tiny([{"pos": [19, 19]}]))
	var b := Sim.new(_tiny([{"pos": [19, 19]}]))
	b.command_move(b.robot_pos + Vector2(8, 0))
	_run(a, 2.0)
	_run(b, 2.0)
	assert_lt(b.fuel, a.fuel)
	assert_lt(a.fuel, a.fuel_max)


func test_canister_taken_once_and_never_over_max() -> void:
	var sim := Sim.new(_tiny([{"pos": [0, 5]}, {"pos": [19, 19]}]))
	var start_fuel := sim.fuel
	sim.command_move(Vector2(0, 5))
	var pickups := _event_count(sim, "pickup", 3.0)
	assert_eq(pickups, 1)
	assert_true(sim.canisters[0]["taken"])
	assert_lte(sim.fuel, sim.fuel_max)
	assert_gt(sim.fuel, start_fuel - 10.0, "the canister gave fuel")
	# walking away and back does not give it again
	sim.command_move(Vector2(0, 12))
	_run(sim, 3.0)
	var before := sim.fuel
	sim.command_move(Vector2(0, 5))
	_run(sim, 3.0)
	assert_lt(sim.fuel, before, "no second pickup")


func test_all_canisters_taken_is_tank_stable() -> void:
	var sim := Sim.new(_tiny([{"pos": [0, 5]}]))
	sim.command_move(Vector2(0, 5))
	_run(sim, 3.0)
	assert_eq(sim.outcome, "tank_stable")


func test_path_never_enters_a_footprint() -> void:
	var sim := Sim.new(_layout())
	var targets: Array[Vector2] = [Vector2(-3, -15), Vector2(15, -15), Vector2(-14, 12), Vector2(10, -2), Vector2(-4, 1.5)]
	for t in targets:
		var pts: Array = [sim.robot_pos]
		pts.append_array(sim.path_to(t))
		assert_gt(pts.size(), 1, "a path exists to %s" % t)
		for i in range(pts.size() - 1):
			for k in 21:
				var p: Vector2 = pts[i].lerp(pts[i + 1], k / 20.0)
				assert_false(sim.blocked_at(p), "path point %s is free" % p)


func test_clicked_point_is_reached_and_blocked_click_gets_close() -> void:
	var sim := Sim.new(_layout())
	var goal := Vector2(14, 15)
	sim.command_move(goal)
	_run(sim, 15.0)
	assert_lt(sim.robot_pos.distance_to(goal), 0.2)
	# a click inside a house walks to the free ground nearest to it
	var sim2 := Sim.new(_layout())
	var inside := Vector2(-10, -11)
	sim2.command_move(inside)
	_run(sim2, 15.0)
	assert_false(sim2.blocked_at(sim2.robot_pos))
	assert_lt(sim2.robot_pos.distance_to(inside), 8.0)


func test_drone_is_destroyed_by_hits_and_stays_destroyed() -> void:
	var sim := Sim.new(_tiny([{"pos": [19, 19]}], [{"pos": [3, 7], "patrol_radius": 1}]))
	assert_eq(sim.drone_at(sim.drones[0]["pos"], 0.5), 0)
	sim.command_attack(0)
	var hits := _event_count(sim, "drone_hit", 12.0)
	assert_false(sim.drones[0]["alive"])
	assert_gte(hits, 3)
	assert_eq(sim.drone_at(sim.drones[0]["pos"], 5.0), -1, "dead drones cannot be picked")
	var pos: Vector2 = sim.drones[0]["pos"]
	_run(sim, 2.0)
	assert_false(sim.drones[0]["alive"])
	assert_eq(sim.drones[0]["pos"], pos)


func test_drone_touch_costs_fuel_but_not_every_frame() -> void:
	var sim := Sim.new(_tiny([{"pos": [19, 19]}], [{"pos": [0, 9], "patrol_radius": 1}]))
	var frames := 4.0
	var hurts := _event_count(sim, "robot_hurt", frames)
	assert_gte(hurts, 1)
	assert_lt(hurts, int(frames * 60.0) / 5)
	assert_lt(sim.fuel, sim.fuel_max - 8.0 + 0.001)


func test_out_of_fuel_ignores_commands() -> void:
	var sim := Sim.new(_tiny([{"pos": [19, 19]}]))
	sim.fuel = 0.5
	_run(sim, 2.0)
	assert_eq(sim.outcome, "out_of_fuel")
	assert_eq(sim.robot_anim, "off")
	var p := sim.robot_pos
	sim.command_move(p + Vector2(5, 0))
	_run(sim, 1.0)
	assert_eq(sim.robot_pos, p)
	assert_eq(sim.fuel, 0.0)


func test_result_does_not_depend_on_frame_rate() -> void:
	var a := Sim.new(_layout())
	var b := Sim.new(_layout())
	a.command_move(Vector2(8, 8))
	b.command_move(Vector2(8, 8))
	a.advance(1.0 / 30.0)
	a.advance(1.0 / 30.0)
	for i in 4:
		b.advance(1.0 / 60.0)
	assert_eq(a.robot_pos, b.robot_pos)
	assert_eq(a.fuel, b.fuel)
	assert_eq(a.drones[0]["pos"], b.drones[0]["pos"])
