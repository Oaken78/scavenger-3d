# Scavenger models (A01)

One set of Blender Python scripts builds every model of both tech prototypes from factory startup, with no manual
steps: the glTF files for scavenger-3d and the pre-rendered sprites (colour + normal map + emissive) for
scavenger-2d. `.blend` files are never saved. All looks are placeholders (GDD section 10).

## Re-render everything (one command, from the root repo)

```
./tools/blender.ps1 -Script C:/game-dev-godot/games/scavenger-3d/art/blender/build_all.py -TimeoutSec 3000 -- --sprites C:/game-dev-godot/games/scavenger-2d/assets/sprites
```

Use the absolute paths of the checkouts you work in. Options after `--`: `--only robot,tree` (rebuild some; the
manifest keeps the other entries), `--models DIR` (default: this game's `assets/models`), `--renders DIR` (default:
`art/blender/renders`). Without `--sprites` only the glTF files are written. Then run
`./tools/import.ps1 -Game <checkout> -Force` in both games and commit the generated `.import` files.

A full build takes a few minutes (Cycles on the GPU when there is one); the log ends with a `STATS` table
(triangles, meshes, materials, seconds per asset).

## Files

- `sc_kit.py`: palette, the mesh builder (`MB`: boxes, cylinders, blobs, leaves, grass, vines, rubble, rebar, moss
  and rust passes), materials, animation keying, glTF export.
- `sc_actors.py`: `robot`, `scrap_drone`, `fuel_canister`. `sc_props.py`: the houses, subway entrance, car, lamp,
  campfire, tree and bush. One function per asset; sizes come from `design/layout.json` footprints.
- `sc_sprites.py`: the sprite camera and renderer. `build_all.py`: the entry point, manifest and review sheets.
- `renders/`: `contact_sheet.png` (every asset, every dir; the robot's walk and attack frames), `robot_8dirs.png`,
  `lit_check.png` (each sprite shaded from its normal map with a light on the screen's right: the right side must
  be lit).

## Conventions

- Metres. Blender +Z up; glTF/Godot +Y up (Blender -Y becomes glTF +Z, the sim's z). Each asset's root node is an
  empty named after the asset at the ground point of its footprint centre.
- Actors face +X at rest (the sim's heading 0). Props at rot 0 have their front (the street side) towards glTF +Z;
  the subway stairs are entered from +Z and go down towards -Z; the street lamp's arm reaches towards -Z.
- Colour is a per-face colour attribute `Col` (glTF COLOR_0) on one opaque material `sc_opaque`; leaves and grass
  use `sc_foliage` (double-sided). Glowing parts are separate nodes with an `sc_emit_*` material (emission strength
  4 via KHR_materials_emissive_strength): `headlamp`, `eye`, `bulb`, `embers`. Light anchors are empties:
  `headlight` (robot), `eye_light` (drone), `light` (street lamp, campfire).
- Scrap drone hover height (lead decision, 2026-10-20): in the glTF the drone's origin is the centre of its body,
  with no hover height built in (the 3D game lifts the node 1.2 m); the `hover` animation bobs it +-0.05 m around
  that origin. The sprites show it hovering 1.2 m up, and the manifest's `origin` is the ground point under it
  (where the 2D game draws the shadow blob); its `lights.eye_light` is at y 1.2 accordingly.
- Animations are object animations (no armature), one glTF animation per name: robot `idle` (2 s loop), `walk`
  (0.5 s loop), `attack` (0.6 s, one swing); drone `hover` (0.5 s loop). Godot imports them without a loop flag;
  the presentation sets the loop mode.

## Sprite contract (scavenger-2d `assets/sprites/`)

- Orthographic camera = the 3D game's `Camera3D.rotation_degrees = (-30, 45, 0)` (Blender rotation (60, 0, 45)),
  64 px per metre, transparent background.
- `<name>/<anim>_<dir>_<frame>.png`: albedo times baked ambient occlusion, straight alpha, no lights.
  `_n.png`: screen-space normal map, red = right, green = up on screen, blue = towards the viewer.
  `_e.png` (assets with `"emissive": true`): the glowing parts' colour, alpha = glow coverage, drawn unlit on top.
- Actors: 8 dirs, dir k = heading k * 45 deg (0 = +x, increasing towards +z). Props: 4 dirs, dir = rot / 90, where
  rot turns the model like Godot's `rotation_degrees.y` (+x towards -z). `fuel_canister`: dir 0 only. Props have
  anim `static`, frame 0.
- Frame i of an animation shows phase i / frames; `fps` in the manifest is a suggested rate.
- `manifest.json`: per asset `size` [w, h] (the same for all its frames), `origin` [x, y] (the ground origin's
  pixel from the top-left corner, at pixel corners: `Sprite2D.centered = false`, `offset = -origin`), `dirs`,
  `anims` (frames, fps, loop), `emissive`, and `lights` (anchor positions in metres at dir 0, glTF axes).
