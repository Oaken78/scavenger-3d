extends GutTest
## The 3D presentation's conversions between the sim's 2D world and Godot 3D, and the model fallback.


func test_heading_zero_faces_plus_x() -> void:
	var b := Basis(Vector3.UP, ViewMath.heading_to_rot_y(0.0))
	assert_almost_eq(b * Vector3.RIGHT, Vector3.RIGHT, Vector3.ONE * 0.001)


func test_heading_towards_plus_z_faces_plus_z() -> void:
	# Sim heading increases from +x towards +z; the model must turn the same way.
	var b := Basis(Vector3.UP, ViewMath.heading_to_rot_y(PI * 0.5))
	assert_almost_eq(b * Vector3.RIGHT, Vector3(0, 0, 1), Vector3.ONE * 0.001)


func test_layout_rot_covers_the_same_footprint_as_the_sim() -> void:
	# The sim's blocking rectangle at rot 90 spans the size's x along z; the rotated 3D prop must too.
	var b := Basis(Vector3.UP, ViewMath.layout_rot_to_rot_y(90.0))
	var half_x := b * Vector3(2.0, 0, 0)  # a footprint 4 m along local x
	assert_almost_eq(absf(half_x.z), 2.0, 0.001)
	assert_almost_eq(absf(half_x.x), 0.0, 0.001)


func test_sim_and_world_round_trip() -> void:
	var p := Vector2(3.5, -7.25)
	assert_eq(ViewMath.to_sim(ViewMath.to_world(p, 2.0)), p)


func test_ray_down_hits_ground_below() -> void:
	var hit: Variant = ViewMath.ray_to_plane(Vector3(2, 10, -3), Vector3.DOWN, 0.0)
	assert_almost_eq(hit as Vector3, Vector3(2, 0, -3), Vector3.ONE * 0.001)


func test_ray_parallel_or_away_misses() -> void:
	assert_null(ViewMath.ray_to_plane(Vector3(0, 5, 0), Vector3.RIGHT, 0.0))
	assert_null(ViewMath.ray_to_plane(Vector3(0, 5, 0), Vector3.UP, 0.0))


func test_find_anim_matches_prefixed_names() -> void:
	var names := PackedStringArray(["RESET", "Robot|walk", "idle"])
	assert_eq(ViewMath.find_anim(names, "idle"), "idle")
	assert_eq(ViewMath.find_anim(names, "walk"), "Robot|walk")
	assert_eq(ViewMath.find_anim(names, "attack"), "")


func test_missing_model_gives_a_stand_in() -> void:
	var node := ModelFactory.build("no_such_asset", {"size": [2, 3], "height": 4})
	assert_not_null(node)
	assert_eq(node.name, "StandIn")
	assert_gt(node.get_child_count(), 0)
	node.free()


func test_whole_line_accepts_a_hit_behind_the_origin() -> void:
	# Orthographic picking: the near plane can sit below the ground at the screen edge.
	var hit: Variant = ViewMath.ray_to_plane(Vector3(1, -4, 2), Vector3.DOWN, 0.0, true)
	assert_almost_eq(hit as Vector3, Vector3(1, 0, 2), Vector3.ONE * 0.001)
