# R1.8 Determinism and fixed-step replay in Godot 4.7

Binary: `Godot_v4.7-stable_linux.x86_64` (`4.7.stable.official.5b4e0cb0f`), Linux x86_64, 4 cores, run `--headless` unless stated. Test project and scripts: `/tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad/research/r1_8_work/` (`proj/main.gd` is the harness, `projj/` is the same project with Jolt, `u.gd` the RNG comparisons).

## Answer

1. Same binary, same machine: a seeded, fixed-tick scene is bit-exact. I ran 600- and 1200-tick rigid-body + CharacterBody scenarios 3-5 times per configuration and every run had an identical SHA of the full float64 state, for both Godot Physics and Jolt, 2D and 3D. [Run: tables below]
2. The simulation follows physics ticks, not rendered frames. `--fixed-fps` 17/23/30/60, real-time, headless vs Xvfb+gl_compatibility, 1 CPU vs 4 CPUs, `max_physics_steps_per_frame` 1 vs 8, jitter fix 0/0.5/2, and physics interpolation on/off all produced the same final state. [Run]
3. What does change the result: `physics_ticks_per_second`, `Engine.time_scale` (it scales the physics delta; the tick count does not change), the physics engine choice, and anything driven by `_process`/idle delta. [Run]
4. Global RNG (`randi`, `randf`, `randi_range`, `randfn`, `Array.shuffle`, `Array.pick_random`) is seeded randomly at startup and shared. A harness must call `seed()` first, or use its own `RandomNumberGenerator` instances. [Doc] [Run] Warning: `RandomNumberGenerator.randf()` and global `randf()` give different values from the same seed, so you cannot swap one for the other. [Run]
5. Tween, Timer and AnimationPlayer are deterministic only in physics process mode. In idle mode they depend on the render frame rate. Set all of them to physics. [Run]
6. Cross-machine or cross-binary bit-exactness is not guaranteed by anything in Godot's docs. Use exact-match assertions only on the same binary and CPU class. Use tolerance assertions for cross-machine runs. SG Physics 2D (fixed-point) is the only route to cross-platform exactness, and it is stale (Godot 4.1-era, last commit April 2024). [Src] [Doc]

## Determinism checklist

Project settings:
- `physics/common/physics_ticks_per_second`: pin it (60 default). It is part of the replay identity: 60 and 120 gave different outcomes. Record it in replay files. [Run]
- Do not use `Engine.time_scale` for speeding up replays. It changes the physics delta (0.05 at 3x), which changed the final state in both engines. Run more ticks per second in wall time instead. [Run]
- `physics/common/physics_jitter_fix`: no effect on results in my runs (0 / 0.5 / 2 all identical). The docs recommend 0 for networked or custom-interpolation games [Doc: https://docs.godotengine.org/en/stable/classes/class_engine.html#class-engine-property-physics-jitter-fix]; set 0 anyway.
- `physics/common/max_physics_steps_per_frame`: has no effect on results, only on wall-clock speed. With a low render FPS and a high tick rate the game slows down but the physics delta is unchanged. [Doc: class_engine.html#class-engine-property-max-physics-steps-per-frame] [Run: maxsteps=1 and fps=7 / maxsteps=2 identical hashes]
- `physics/common/physics_interpolation`: no effect on simulated state in my runs. It only affects rendered transforms. [Run]
- `physics/3d/physics_engine`: the value for Jolt is the string `Jolt Physics`. `JoltPhysics3D` is silently ignored and falls back to Godot Physics. [Run: my first Jolt run with that string printed `GodotPhysics3D` hashes]
- Run with the physics engine fixed per test suite. Godot Physics and Jolt give different but each-self-consistent trajectories. [Run]
- `physics/3d/run_on_separate_thread` and `physics/2d/run_on_separate_thread`: leave off. I saw no change when on (3 runs each, headless), but I did not confirm the thread actually started. The Godot docs call Jolt thread-safety "experimental" [Doc: https://docs.godotengine.org/en/stable/tutorials/physics/using_jolt_physics.html, "Thread safety"].

Harness and code conventions:
- Drive the sim from `_physics_process` only. Count ticks (`Engine.get_physics_frames()` or your own counter), not frames. At `--fixed-fps 60` 600 ticks took 599 process frames. [Run]
- Do not use `delta` from `_process` for gameplay. It varies with `--fixed-fps` and real-time. [Run]
- Seed explicitly: `seed(N)` for global calls, `rng.seed = N` for instances. Do not rely on a default-constructed `RandomNumberGenerator`: its default seed is time-based and two instances created in the same instant had identical seeds in one of my 3 runs. [Run: `default seed1=4679508199360780068 seed2=4679508199360780068`] Prefer one root RNG that derives sub-seeds (the "mother seed" approach in the rollback addon [Src: godot-rollback-netcode@0b907fb:README.md:274-281]).
- Setting `rng.seed` resets state. If restoring from a save, set `seed` first and then `state` [Doc: https://docs.godotengine.org/en/stable/classes/class_randomnumbergenerator.html#class-randomnumbergenerator-property-state].
- Never mix global-RNG calls (`shuffle`, `pick_random`, `randi`) with instance RNG calls and expect separate streams: they are separate, but any engine code or addon that calls the global one consumes it. `RandomNumberGenerator` instances are independent of `seed()`. [Run: `RNG independent of global seed: true`]
- Use the same iteration order everywhere. Dictionaries iterate in insertion order [Run: `["b","a","c"]`]. Avoid iterating over anything keyed by object ids or hashes of nodes.
- Set Tween / Timer / AnimationPlayer to physics: `Tween.set_process_mode(TWEEN_PROCESS_PHYSICS)`, `Timer.process_callback = TIMER_PROCESS_PHYSICS`, `AnimationMixer.callback_mode_process = ANIMATION_CALLBACK_MODE_PROCESS_PHYSICS`. [Run]
- Keep wall-clock inputs (`Time.get_ticks_msec()`, `OS.get_unix_time()`, `Time.get_ticks_usec`) out of simulation code.
- Create the same nodes in the same order and with the same properties. Node insertion order is the order of body creation in the physics space and affects contact solving order. [Unverified: I did not test scene-order sensitivity; this follows from Jolt's own docs that API call order must be identical, https://jrouwe.github.io/JoltPhysics/ "Deterministic Simulation"]
- Hash state with exact bytes (`PackedFloat64Array.to_byte_array()` → sha256), not formatted strings, for exact-match checks. Note GDScript's `%` format has no `%g` (my first attempt produced literal `%.9g` strings and a meaningless hash; fixed before the table below).

## Experiments

### E1: RNG behaviour [Run: `main.gd mode=rng`, `u.gd`]

| Call | Seed 12345 result | Notes |
|---|---|---|
| `RandomNumberGenerator.randi()` x5 | 1321476956, 17539747, 3348728241, 2863338820, 85463406 | same sequence as global `randi()` |
| global `randi()` x3 | 1321476956, 17539747, 3348728241 | matches RNG instance |
| `randi_range(0,99)` x3 | 56, 47, 41 | RNG and global agree |
| `rng.randf()` | 0.25204190611839 | double-precision path |
| global `randf()` | 0.30768033862114 | differs from `rng.randf()` for the same seed |
| `rng.randf_range(0,1)` / global `randf_range(0,1)` | 0.25204190611839 / 0.25204189538254 | differ in the 8th digit (32-bit float path) |
| `rng.randfn()` / global `randfn()` | -0.83005064725876 / -1.64725788694158 | differ |
| global `Array.shuffle()` of 1..10 | [4,3,6,9,5,1,10,2,8,7] both times | uses the global RNG, so `seed()` controls it |
| `rand_from_seed(12345)` | [1321476956, 12345] | pure function, returns [value, seed] |
| global RNG unseeded, fresh process | 3522943765 then 1228668886 in two script-mode runs | randomised per process at startup, matching the docs |

Docs: "This function is called automatically when the project is run" for `randomize()` [Doc: https://docs.godotengine.org/en/stable/classes/class_@globalscope.html#class-globalscope-method-randomize]. `Array.shuffle()` and `pick_random()`: "uses a common, global random seed ... see @GlobalScope.seed()" [Doc: https://docs.godotengine.org/en/stable/classes/class_array.html#class-array-method-shuffle]. `RandomNumberGenerator.seed`: "does not have an avalanche effect ... consider using a hash function" for externally sourced seeds [Doc: class_randomnumbergenerator.html#class-randomnumbergenerator-property-seed].

Seed behaviour across platforms: the integer stream is PCG32, a pure integer algorithm, so `randi()` should match everywhere [Unverified for other platforms; I only ran Linux x86_64]. The float variants involve float conversion and 32-bit vs 64-bit paths (shown above), so I recommend deriving gameplay values from `randi_range` or integers where cross-platform matters. `rand_from_seed` is documented as always returning the same array for the same seed [Doc: class_@globalscope.html, `rand_from_seed`].

### E2: Physics repeatability [Run]

Scenario: static floor + tilted slab, 40 RigidBody3D (sphere/box/capsule, seeded random pose and velocity), 4 CharacterBody3D with `move_and_slide`, gravity applied by script; 2D variant: 40 RigidBody2D (circle/box) + 4 CharacterBody2D. Hash = sha256 of all positions and linear velocities as float64. 600 ticks unless noted.

| Config | Runs | Distinct hashes | Final hash (first 16 hex) |
|---|---|---|---|
| Godot Physics 3D, `--fixed-fps 60` | 5 | 1 | fb3f8d08ef0198b2 |
| Godot Physics 3D, real-time (no fixed-fps) | 5 | 1 | fb3f8d08ef0198b2 |
| Godot Physics 3D, `--fixed-fps 30` / `17` | 5 each | 1 | fb3f8d08ef0198b2 |
| Godot Physics 3D, Xvfb + gl_compatibility | 3 | 1 | fb3f8d08ef0198b2 |
| Godot Physics 3D, jitter fix 0.0 / 2.0 | 3 each | 1 | fb3f8d08ef0198b2 |
| Godot Physics 3D, physics_interpolation on | 3 | 1 | fb3f8d08ef0198b2 |
| Godot Physics 3D, `run_on_separate_thread` 2D+3D on | 3 | 1 | fb3f8d08ef0198b2 |
| Godot Physics 3D, max_physics_steps=1 / `--fixed-fps 7` with max 2 | 3 / 1 | 1 | fb3f8d08ef0198b2 |
| Godot Physics 3D, 120 ticks/s (ticks=600) | 5 | 1 | e98d7bd4566c1c4d (differs: tick rate matters) |
| Godot Physics 3D, `--time-scale 3` | 3 | 1 | cf5f7f81b92940d2 (differs: delta 0.05) |
| Godot Physics 2D, `--fixed-fps 60` | 5 | 1 | 01c1afe2e6e13bec |
| Jolt 3D, `--fixed-fps 60` | 5 | 1 | 749ffb9074588c27 |
| Jolt 3D, real-time / fps 23 / Xvfb gl_compat | 3 each | 1 | 749ffb9074588c27 |
| Jolt 3D, interpolation / jitter 0 / separate thread | 3 each | 1 | 749ffb9074588c27 |
| Jolt 3D, 120 ticks/s | 3 | 1 | 2295313489 (hash32; differs) |
| Jolt 3D, `--time-scale 3` | 3 | 1 | 2fad70794fe710e1 (differs) |
| Godot Physics 3D, 400 bodies, 1200 ticks | 4 | 1 | 085e0ab26b32de0d |
| Jolt 3D, 400 bodies, 1200 ticks | 4 | 1 | 2215e4f3a96ffd73 |
| both engines, 400 bodies, pinned to 1 CPU (`taskset -c 0`) | 2 each | 1, equal to the 4-CPU hash | same as above |

Time per run (400 bodies, 1200 ticks, headless, 4 cores): Godot Physics about 5.5 s, Jolt about 3.7 s. 40 bodies / 600 ticks: about 0.5 s including startup (5 runs in 2.7 s).

Same-binary caveat: all the above are one binary on one machine. Jolt's own docs say determinism holds for the same binary code (any AMD/Intel CPU), and cross-platform only when built with `CROSS_PLATFORM_DETERMINISTIC`, which is "approximately 8% slower" [Doc: https://jrouwe.github.io/JoltPhysics/ "Deterministic Simulation"]. The standalone Godot Jolt extension README says Godot's integration "is not able to make such guarantees" and results "may happen to be deterministic, but this should not be relied upon if determinism is a hard requirement" [Src: godot-jolt@7f22589:README.md:49-51]. That statement is about the extension; I found no equivalent statement about the built-in module in the 4.7 docs. [Unverified whether the built-in module is built with CROSS_PLATFORM_DETERMINISTIC; I did not check the Godot source.]

### E3: `--fixed-fps`, time scale, tick rates and delta [Run: `main.gd mode=time`]

| Flags | Physics ticks | `_physics_process` delta | `_process` delta | Max ticks in one frame |
|---|---|---|---|---|
| `--fixed-fps 60` | 120 in 120 | 0.016667 constant | 0.016667 constant | 1 |
| `--fixed-fps 30` | 120 in 60 frames | 0.016667 | 0.025 to 0.0417 (varies: ticks catch up) | 2 |
| `--fixed-fps 120` | 120 in 238 frames | 0.016667 | 0.00833 | 1 |
| `--fixed-fps 7` (ticks=30) | 30 in 3 frames | 0.016667 | 0.14 to 0.145 | 9 (exceeds default max of 8 once) |
| `--fixed-fps 60 --time-scale 3` | 120 | 0.05 | 0.05 | 1 |
| `--fixed-fps 60 --time-scale 0.5` | 120 | 0.008333 | 0.008333 | 1 |
| `--fixed-fps 60`, `Engine.time_scale=2` in script | 120 | 0.03333 | 0.03333 | 1 |
| `--fixed-fps 60`, `physics_ticks_per_second=30` | 120 | 0.03333 | 0.0167 / 0.0333 | 1 |
| no flags (real-time) | 60 | 0.016667 | 0.001 to 0.0167 (real) | 1 |

Reading: `_physics_process` delta is always `time_scale / ticks_per_second`; tick count tracks `fixed-fps` time, not render rate. `--fixed-fps N` fakes the clock so each rendered frame advances exactly 1/N seconds and disables real-time sync [Doc: `--fixed-fps` help text from `godot --headless --help`: "Force a fixed number of frames per second. This setting disables real-time synchronization."]. Engine docs: `time_scale` "affects Timer, SceneTreeTimer, and all other simulations that make use of delta time" and "does not automatically adjust physics_ticks_per_second ... simulation may become less precise" [Doc: class_engine.html#class-engine-property-time-scale]. Helper note: the first frame has no tick (599 frames for 600 ticks at 60/60).

### E4: Tween / Timer / AnimationPlayer at 60 ticks (1 s of sim time), `main.gd mode=anim` [Run]

Targets: tween and animation move x from 0 to 100 over 1 s; the report is taken inside `_physics_process` on tick 60 (the last tick), so exact values depend on the update order inside the tick.

| Flags | Tween PHYSICS x | Tween IDLE x | AnimPlayer physics x | AnimPlayer idle x | Timer(0.1s) physics fire ticks | Timer idle fire ticks |
|---|---|---|---|---|---|---|
| fixed-fps 60 | 98.333 | 98.333 | 96.667 | 96.667 | 7,13,19,25,31,37,43,49,55 | same |
| fixed-fps 30 | 98.333 | 99.167 | 96.667 | 96.667 | same | same |
| fixed-fps 13 | 98.333 | 99.167 | 96.667 | 91.474 | same | 8,13,22,27,31,36,45,50,54 |
| real-time (2 runs) | 98.333 | 99.725 / 99.588 | 96.667 | 98.058 / 97.921 | same | 6,12,18,... |
| fixed-fps 60, time-scale 2 (30 ticks) | 96.667 | 96.667 | 93.333 | 93.333 | 4,7,10,... | same |

The physics-mode variants are identical across every setting. The idle-mode variants vary with fps and differ between real-time runs (nondeterministic). A 0.1 s Timer fires every 6 or 7 ticks in a pattern (7,13,19,...), i.e. it quantises to tick boundaries, so use tick counters instead for exact gameplay timing.

### E5: Threading, WorkerThreadPool

- Pinning the whole process to one core gave bit-identical results for both engines versus 4 cores, 400 bodies, 1200 ticks. This suggests the multi-threaded solver paths I exercised are order-independent here. [Run] That is evidence for my scenario, not a proof.
- Jolt itself says that broadphase queries, listener callbacks, `GetActiveBodies` order and narrowphase result order are not deterministic because they come from multiple threads; only the simulation step is [Doc: https://jrouwe.github.io/JoltPhysics/ "Deterministic Simulation"]. In Godot terms: sort the results of `intersect_ray`, `intersect_shape`, `get_overlapping_bodies` and collision-signal order before acting on them. [Unverified for how Godot's Jolt module exposes this; it is an inference from the Jolt docs.]
- Do not use `WorkerThreadPool` for gameplay logic that writes shared state. [Unverified, no experiment.]

## Float determinism across machines

- Gaffer on Games: determinism is achievable "provided you use an executable built with the same compiler, run on machines with the same architecture, and perform some platform-specific tricks", and it is "incredibly naive" to expect arbitrary C/C++ floating-point code to match across compilers or architectures [Doc: https://gafferongames.com/post/floating_point_determinism/].
- SG Physics 2D's README says the same about Godot: "Most physics engines aren't deterministic (including the builtin physics engine in Godot)" and picks 64-bit fixed-point math with 16 fractional bits [Src: sg-physics-2d@48688eb:README.md:18-60].
- Practical consequence: same binary and CPU architecture is the only configuration I ran. A CI that records golden hashes on one runner image and replays on the same image is fine. Cross-OS or cross-architecture golden files are not safe.

## Community lockstep / rollback projects

- Godot Rollback Netcode (David Snopek), GDScript addon, project config targets Godot 4.6 [Src: godot-rollback-netcode@0b907fb (2026-06-06):project.godot:19]. Repo is on GitLab (`gitlab.com/snopek-games/godot-rollback-netcode`); `github.com/snopek-games/...` failed with an auth prompt. It does not make Godot physics deterministic. It runs your game from `_physics_process` ticks, saves/loads state through `_save_state` / `_load_state` virtual methods, replays ticks with `_network_process(input)`, and detects mismatches by hashing state. It provides `NetworkRandomNumberGenerator` (seed shared at match start, state rolled back with the game; wraps a `RandomNumberGenerator` instance), `NetworkTimer` and `NetworkAnimationPlayer` (advances per tick, not per time), plus a "Random Rollback Ticks" debug setting that rolls back random counts each tick to flush out non-determinism, and a log-based state comparer. [Src: README.md:267-281, 255-258, 434-436; addons/godot-rollback-netcode/NetworkRandomNumberGenerator.gd:1-31]
- SG Physics 2D (Snopek): 2D physics engine as a GDExtension using 64-bit fixed-point math for cross-platform determinism, for rollback netcode. Godot 4 project in the repo is marked 4.1; last commit 2024-04-18. [Src: sg-physics-2d@48688eb:README.md:5-60; projects/godot-4/project.godot:15] I did not build it or test it on 4.7. [Unverified compatibility with 4.7]
- Godot Jolt extension: README states no determinism guarantee. [Src: above]

Lessons the harness can borrow: (a) tick-driven everything, (b) explicit state save/load plus hashing for mismatches, (c) a seed-injection RNG wrapper, (d) a fault-injection mode that rolls back or reorders to expose hidden nondeterminism, (e) per-tick input records as the replay format.

## Recommendation: exact vs tolerance by subsystem

| Subsystem | Same binary + same machine class (CI) | Across machines/OS/arch |
|---|---|---|
| Integer game state, RNG integers, entity ids, tick counters, inventory/score, turn logic | Exact | Exact (integers; RNG `randi` PCG32 unverified on other platforms) |
| Seeded `RandomNumberGenerator` float outputs (`randf`, `randfn`) | Exact | Tolerance 1e-6 relative, or avoid in gameplay |
| Simple kinematic scripted motion with plain float math (add, mul, no trig) | Exact | Tolerance 1e-5 to 1e-4 |
| Rigid body (Godot Physics or Jolt) positions/velocities | Exact hash OK (verified for 600 and 1200 ticks, 40-400 bodies) | Not safe; use tolerance (e.g. 1e-3 m positions, and compare only coarse outcomes like "body settled on floor", ordering, counts) |
| CharacterBody `move_and_slide` | Exact OK (verified) | Tolerance, plus exact on discrete outcomes (`is_on_floor`, collision counts) |
| Physics queries (rays, overlaps, signal order) | Sort results, then exact | Sort, then tolerance |
| Tween / Timer / AnimationPlayer in physics mode | Exact | Tolerance on values, exact on tick of firing |
| Tween / Timer / AnimationPlayer in idle mode | Not assertable | Not assertable (frame-rate dependent) |
| Rendering/screenshots | Not part of determinism; use image diff tolerance (R1.7) | Same |

Default harness policy: record golden state as an exact hash plus a tolerance-comparable dump (positions rounded), compare hash first and fall back to tolerance only when the hash differs, and treat "hash differs but tolerance passes" as a warning (it means the environment changed), not a failure. This keeps CI sharp while not breaking on a runner upgrade.

## Blocked sources

- `https://github.com/snopek-games/godot-rollback-netcode`: git clone failed (`could not read Username`, i.e. not found at that path); used `https://gitlab.com/snopek-games/godot-rollback-netcode.git` instead (OK).
- `https://docs.godotengine.org/en/stable/tutorials/physics/jolt_physics.html`: 404; the correct page is `using_jolt_physics.html` (200).
- `docs.godotengine.org/.../physics_servers.html`: 404 (not needed).
- No other blocked hosts. YouTube transcripts were not fetched (not needed).

## Open questions

- Is the built-in Jolt module built with `CROSS_PLATFORM_DETERMINISTIC` (Godot source/SCons flags)? Not checked; needs a source read of `modules/jolt_physics` and `thirdparty/jolt_physics`.
- Does `run_on_separate_thread` actually activate under `--headless`? Results unchanged, activation unconfirmed.
- Scene-tree insertion order sensitivity for body creation and contacts: untested.
- Cross-OS / ARM results for Godot Physics and Jolt in 4.7: untested (only Linux x86_64 available).
- Does `WorkerThreadPool` use inside user code affect physics determinism: untested.
- Does SG Physics 2D build and run on Godot 4.7: untested.
