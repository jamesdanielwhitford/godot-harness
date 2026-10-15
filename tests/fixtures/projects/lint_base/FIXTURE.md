lint_base: clean 4.7 project for A3 (no harness.toml). Owner: A3/T3. Expected `h lint`: PASS, zero findings,
also under `[lint] replay_dirs = ["res://"]`; no Godot invocation. Tests write extra files into a temp copy.
Dirs: scripts/ (player, base, rng, input_remap), sim/ (node-free), scenes/main.tscn.
