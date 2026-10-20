extends GutTest
## Unit tests for scripts/game_rules.gd: one behaviour per test, the name states the rule.


func test_score_grows_quadratically_with_combo() -> void:
	assert_eq(GameRules.score_for_combo(1), 100)
	assert_eq(GameRules.score_for_combo(3), 900)


func test_score_is_capped_at_max_combo() -> void:
	assert_eq(GameRules.score_for_combo(99), GameRules.score_for_combo(GameRules.MAX_COMBO))


func test_miss_resets_combo_and_hit_increments_it() -> void:
	assert_eq(GameRules.combo_after_hit(7, false), 0)
	assert_eq(GameRules.combo_after_hit(7, true), 8)
