# Vendored add-ons

- GUT 9.7.1 from https://github.com/bitwes/Gut/archive/refs/tags/v9.7.1.zip (GUT's godot_4_7 line, for Godot 4.7.x).
- Re-vendor with: ./tools/vendor-gut.ps1 -Version <x.y.z>. Never copy GUT from its main branch (targets Godot 4.6).
- Do not edit files under addons/ by hand; the protect hook blocks it.
