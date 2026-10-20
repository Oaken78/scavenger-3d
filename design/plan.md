# Scavenger tech prototypes - production plan (shared by scavenger-2d and scavenger-3d)

Edited only by the lead, on `main`. Packets live in `design/tasks/<id>.md` (identical copies in both games).

## Milestones
| Id | Name | Acceptance criteria | Proof | Status |
|---|---|---|---|---|
| P0 | Two playable prototypes | Both: click-to-move robot, fuel drain and canisters, drones to fight, lights with shadows, fog toggle, outcomes, frame time readout, same map and rules | `play_loop`, `perf_street`, `test_sim.gd` in each game; two playtest builds | built 2026-10-20 (2d 5b14de7, 3d b91f5a7), with Klas |

## Order
1. T01 (rules, both games) and A01 (models + pre-renders, both games) in parallel.
2. T02 (3D) and T03 (2D) in parallel once T01 is merged; they pick up A01 batches as they land on main.
3. Tier 3 on each main, then one playtest build per game.

## Tasks
Status: ready, in-progress, review-passed, done.

| Id | Title | Owned paths | Tier | Status | Branch |
|---|---|---|---|---|---|
| T01 | Rules core (both games) | scripts/rules, test/unit/test_sim.gd | 2 | done (scavenger-2d 6d9c16b) | feat/scavenger-{2d,3d}-rules |
| A01 | Models, glTF, 2D pre-renders | 3d: art, assets/models; 2d: assets/sprites | 2 | done (scavenger-2d 3341024) | art/scavenger-3d-models, art/scavenger-2d-sprites |
| T02 | 3D prototype | scenes, scripts (not rules), shaders, data, test/scenarios | 2 | done (scavenger-3d b91f5a7) | feat/scavenger-3d-demo |
| T03 | 2D prototype | scenes, scripts (not rules), shaders, data, test/scenarios | 2 | done (5b14de7) | feat/scavenger-2d-demo |

## Follow-ups
From the T01 review (non-blocking; only if play shows a need):
- Sim path search scans the whole 80x80 grid per call and re-plans every 0.3 s while attacking; `advance()` has no
  step cap (a 1 s hitch runs 60 steps). Check with a perf scenario (attack a far drone) before acting.
- A layout with no canisters wins on the first step; `patrol_radius` 0 gives a NaN drone position.
- `drone_at` test only probes the drone's own position.
From the T02/T03 reviews (non-blocking):
- 2D: tall props fade only for the robot, not for drones (a drone behind the tree at (13,10) is nearly hidden; its red eye pool shows).
- 2D: prop lights reach walls behind them (a drone behind a house tints its front wall red); left as is, part of the technique comparison.
- 2D: sprite loader checks only the first anim's frame 0; `light_anchor` takes the first light; the cutaway alpha cache grows if animated tall props are added.
- 3D: model_factory `writable_material` always overrides surface 0 (wrong surface if an emissive material sits elsewhere); the stairwell hole and rot handling assume multiples of 90 degrees.
- 3D: perf metrics report process_ms mean 36 / max 100 next to a 1.3 ms frame: probably a metrics bug.
- Critics (both builds): drones are small and hard to find near trees; the cutaway fades props only for the robot. 3D is much darker than 2D with fog on. No shot of the click marker or the "Tank stable" message.
- Both: the robot has no "off" pose; the sim steps at 60 Hz with no interpolation (steps on high-refresh screens).
