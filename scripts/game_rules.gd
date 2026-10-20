class_name GameRules
extends RefCounted
## Pure rules with no node dependencies: easy to unit test, easy to reuse. Example for the pattern.

const MAX_COMBO := 10


static func score_for_combo(combo: int) -> int:
	var c := clampi(combo, 0, MAX_COMBO)
	return 100 * c * c


static func combo_after_hit(combo: int, hit: bool) -> int:
	if hit:
		return mini(combo + 1, MAX_COMBO)
	return 0
