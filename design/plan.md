# Scavenger tech prototypes - production plan (shared by scavenger-2d and scavenger-3d)

Edited only by the lead, on `main`. Packets live in `design/tasks/<id>.md` (identical copies in both games).

## Milestones
| Id | Name | Acceptance criteria | Proof | Status |
|---|---|---|---|---|
| P0 | Two playable prototypes | Both: click-to-move robot, fuel drain and canisters, drones to fight, lights with shadows, fog toggle, outcomes, frame time readout, same map and rules | `play_loop`, `perf_street`, `test_sim.gd` in each game; two playtest builds | planned |

## Order
1. T01 (rules, both games) and A01 (models + pre-renders, both games) in parallel.
2. T02 (3D) and T03 (2D) in parallel once T01 is merged; they pick up A01 batches as they land on main.
3. Tier 3 on each main, then one playtest build per game.

## Tasks
Status: ready, in-progress, review-passed, done.

| Id | Title | Owned paths | Tier | Status | Branch |
|---|---|---|---|---|---|
| T01 | Rules core (both games) | scripts/rules, test/unit/test_sim.gd | 2 | in-progress | feat/scavenger-{2d,3d}-rules |
| A01 | Models, glTF, 2D pre-renders | 3d: art, assets/models; 2d: assets/sprites | 2 | in-progress | art/scavenger-3d-models, art/scavenger-2d-sprites |
| T02 | 3D prototype | scenes, scripts (not rules), shaders, data, test/scenarios | 2 | planned | feat/scavenger-3d-demo |
| T03 | 2D prototype | scenes, scripts (not rules), shaders, data, test/scenarios | 2 | planned | feat/scavenger-2d-demo |

## Follow-ups
None yet.
