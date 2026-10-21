# Scavenger (tech prototype: real 3D) - Game Design Document

This game is one of two throwaway tech prototypes (`scavenger-2d`: classic 2D with pre-rendered sprites;
`scavenger-3d`: real 3D). Klas plays both and picks the rendering technique for Scavenger. Both run the same rules
(`scripts/rules/`, identical copies) on the same map (`design/layout.json`, identical copies); only the presentation
differs. Delivered fast; nothing here is final.

## 1. One-liner, player fantasy, story and main goal
- Store line: a forgotten robot scavenges fuel in an overgrown, ruined world before its tank runs dry.
- Story (Klas, abridged, for the full game; the prototype shows only the opening situation):

  > Robot vaknar/aktiveras men minns ej vem den är, vad dess uppgift är, hur länge den legat där osv. Länge
  > antagligen för mossa växer över halva robotkroppen. Den (och spelaren) vet endast att om den inte får påfyllnad
  > av bränsle snart stannar den för evigt. (Vad som hänt är att en mus trampat på startknappen.)
  >
  > Spelarvyn och perspektivet är ett top-down/isometriskt action-RPG. Världen är i postapokalyptisk anime-stil,
  > 200 år efter katastrofen. Allt är övervuxet och förfallet. Skyskrapornas och husens betong har till stor del
  > vittrats sönder. Den visuella stilen är som om animeserien Shumatsu Touring möter Fallout. Världen gick snabbt
  > från mycket hög teknologi till stenålder med vissa spår av senaste civilisationens tech kvar. Ett fåtal
  > överlevande robotar och människor finns kvar. [...] Robotar driver runt och letar energi från olika källor:
  > sol, el, etanol, bensin, gas, kärnkraft, och de mest avancerade militära robotarna använder kall fusion.
  >
  > Världskartan är mycket stor och uppdelad i koncentriska cirklar med spelstart i mitten. [...] Spelaren börjar
  > i en förfallen förort. [...] Tunnelbanestationer och militärbunkrar skiftar vyn till underjordisk.
- Prototype goal: walk the robot around one dusk suburb street, find fuel, fight scrap drones, run dry or not.

## 2. Pillars
Not set for the prototype (Klas's call for the real game).

## 3. Core loop (prototype)
Click to walk -> fuel drains -> find canisters, avoid or fight drones -> fuel 0 = the robot powers down; R restarts.

## 5. Feel targets (starting values, judged in the build)
- Robot walk speed 3.5 m/s. Fuel 100, drains 0.8/s standing, 1.5/s walking. A canister gives +35.
- Scrap drone: notices the robot at 7 m, flies 2.5 m/s, a touch costs 8 fuel (at most once per 1 s), 3 hits destroy it.
- Robot attack: melee swipe, reach 1.6 m, one hit per 0.6 s.

## 6. Player verbs, controls, input map
- Left click on the ground: walk there (path around obstacles). Left click on a drone: walk into reach and attack
  until it is destroyed. Click again to change the order.
- R: restart. F: fog on/off (to compare the techniques). F3: frame time readout on/off.

## 7. Failure, success
Fuel 0: the robot stops, its lights fade out, "OUT OF FUEL - R to restart". All canisters taken: "Tank stable".

## 8. Systems
- 8.1 Rules (`scripts/rules/`, identical in both prototypes): a pure GDScript simulation in world metres (x east,
  z south, y up) with a fixed step: robot, fuel, drones, canisters, grid pathing (AStarGrid2D over the layout's
  footprints). The presentation only reads its state and sends it commands.
- 8.2 Map: `design/layout.json`, a 40 x 40 m patch of a ruined suburb street.

## 10. Visual direction
- Dusk turning to night: dim blue moonlight, the robot's headlight, two street lamps (one flickering), a campfire,
  the drones' red eyes. Moving lights and their shadows are the point of the comparison. Low ground fog.
- Overgrown, crumbling concrete, moss, rust (Shumatsu Touring meets Fallout).
- Camera: fixed isometric-style view, orthographic, 30 degrees down, 45 degrees yaw (from +x+z looking towards
  -x-z). The Blender models are shared; the 2D prototype uses pre-renders of them from the same angle.
- All looks are placeholders. Keeper looks: none.

## 13. Tech constraints
Godot 4.7, Windows. Frame time readout on screen (F3) so the two can be compared on Klas's machine.
Buildings: seeded generation by the building-lab combination (B04; `games/building-lab`, `scripts/runtime/`, `scripts/kit/`, `art/blender/kit/`), see the Decisions log.

## 15. Out of scope
Inventory, levels, dialogue, sound, underground view, saving, menus beyond the HUD.

## 17. Decisions log (append-only)
| Date | Decision | Why | Rejected alternatives |
|---|---|---|---|
| 2026-10-20 | Two throwaway prototypes, 2D pre-rendered vs real 3D, same rules and map | Klas picks the rendering technique by playing both | One prototype only |
| 2026-10-20 | 2D art = Blender pre-renders with normal maps (StarCraft/C&C/Diablo II way) | Same models in both, so the comparison is the technique, not the art | Hand-drawn sprites, pixel art |
| 2026-10-20 | Click-to-move (Diablo-style) | Klas's pick | WASD + mouse aim |
| 2026-10-20 | Two separate builds | Klas's pick | One build with a menu, live split-screen |
| 2026-10-20 | Dusk/night with moving lights and ground fog | Shows the hardest case for 2D lighting | Overcast day, day/night toggle |
| 2026-10-21 | Buildings are generated by the building-lab combination (B04): GDScript rules (grammar, damage field, support check) decide each building and its ruin from a seed; a Blender kit of pieces with damage states supplies the geometry, drawn as one MultiMesh per kit mesh in 3D, or the same layouts rendered in Blender for 2D | Klas's pick after the lab's four spikes (games/building-lab, art/renders/): best ruin detail at play scale, about 0.27 s per skyscraper on a worker, a 100-building city in 266 draw calls; works for either rendering technique | Whole buildings as Blender meshes (B01: 4-17 MB each, offline only), runtime meshes without a kit (B03), voxels, volume erosion, runtime CSG |

## 18. Open questions
None for the prototype.
