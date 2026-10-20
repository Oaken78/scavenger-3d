# Scavenger - 3D prototype (real 3D)

One of two throwaway tech prototypes. Same map, same rules, same camera angle as the 2D build: only the rendering differs.
Rendering: the same Blender models in real 3D, Forward+ renderer, shadowed lights, volumetric fog. All looks are placeholders.

## Run
Unzip and double-click `scavenger-3d.exe`. Windows SmartScreen may warn: "More info", then "Run anyway".

## Keys
- Left click on the ground: walk there. Left click on a drone: walk up and fight it.
- F: fog on/off. F3: frame time, FPS and draw calls. R: restart.

## The game
Your robot's fuel drains (faster when walking). Find the 5 yellow fuel canisters before it runs dry; scrap drones (red eyes) drain fuel when they touch you, 3 hits destroy one. Fuel 0: the robot powers down.

## Try in the first 5 minutes (in both builds, to compare)
1. Walk along a house wall and past the cars. Does the headlight stop at walls and throw moving shadows, or slide over them?
2. Stand under the flickering street lamp and next to a bush, press F a few times. Light shafts and fog depth, or a flat haze? Does the beam leak through the bush?
3. Lure a drone into the open, then under a tree or behind a house, and fight it. Can you still find and click it?
4. Walk behind the big houses and the tree crowns. Do you lose sight of the robot?
5. Press F3 while walking and fighting. Frame time, and how smoothly the robot turns.
6. Stand still until the fuel runs out. Which power-down feels more like a robot dying in the dark?
