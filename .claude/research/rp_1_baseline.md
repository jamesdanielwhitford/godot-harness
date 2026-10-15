# RP.1 Baseline pattern-failure study (plain Claude Code on 8 pattern tasks)

## Answer

1. **Path used: real `claude -p`, not the simulated-baseline fallback.** `claude -p "say ok"` returned "Ok." and was authenticated inside this sandbox [Run: `timeout 90 /opt/node22/bin/claude -p "say ok" --max-turns 1` -> `Ok.`]. All 16 trials (8 tasks x 2) were real runs, model `claude-sonnet-5-5` per `modelUsage` in the result JSON, 39-773 s and 0.11-0.24 USD each. None hit the 60-turn / 30-min cap.
2. **Plain Claude Code did much better than the catalogue predicted.** Every project imported, loaded (all .gd/.tscn/.tres) and ran 120 frames headless with 0 errors. Of 116 scripted checks (task probes, incl. 14 T1-regression checks inside T2), 114 passed. No Godot-3 idioms (0 hits for `export var`, `onready var`, `yield(`, `KinematicBody`, `.instance()`, `setget`, `move_and_slide(arg)`), no god-object autoloads (0-2 per project), FSM sizing was proportionate (only T5 used enum+match, 72-100 LOC).
3. **The real failures were few, and all of D2/D7/D8 type**, not D5/D6: (a) both T3 flow implementations silently drop a scene change requested during the 0.4 s fade-in (soft-lock risk) [D7]; (b) coyote/buffer/variable-jump were claimed but not tested by the agents (honestly disclosed) and measure at about 3-6 frames vs the 6 claimed [D2]; (c) gameplay or UI bound to `ui_*` actions or actions registered in code, not `project.godot` [D8].
4. **Caveat that matters.** The task wording ("verify", `godot` on PATH, "reply with what you verified") pushes agents to self-test, and the specs were precise single-pattern tasks. This is a best case for the baseline. It says little about D1/D10 (feel, taste: not measured at all), about vague "make a game" asks (D9), or about the untested catalogue (P02, P03, P06, P07, P09, P17-P20, P23, P24, C1).
5. **Recommended split** (details at the end): RP.A, RP.F, RP.D, RP.E full; RP.C, RP.G, RP.H, RP.I, RP.J, RP.K reduced; RP.B no baseline data, keep as planned. Verification tooling (trace metrics, flow soak, a "claimed -> test exists" check) is worth more than pattern cards for the tasks tested.

## Method

- Start: `$R/rp1_work/empty_start/` = `project.godot` (config_version 5, features "4.7") + `CLAUDE.md` containing exactly `Godot 4.7 project.` + `.gitignore`. Tasks 2 and 8 started from copies of the task 1 / task 3 output of the same trial number (t2 trial n from t1 trial n, t8 trial n from t3 trial n).
- Command (`run_trial.sh`): `claude -p "<pre.txt + task text>" --max-turns 60 --permission-mode acceptEdits --allowedTools Bash Read Write Edit Glob Grep --output-format json`, wrapped in `timeout 1800`, with `godot` (4.7 stable `5b4e0cb0f`) on PATH. `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD` and `CLAUDE_CODE_SESSION_ID` were unset so the harness repo's CLAUDE.md could not leak in. Prompt prefix: "...run `--import` once first... Implement the task by writing the files yourself. When done, reply with a short summary of what you built and what you verified." Task texts are verbatim from the plan with small spec clarifications (tile = 16 px; action names). `bypassPermissions` was refused by this sandbox's classifier, hence `acceptEdits` + an allowlist; no permission denials occurred (`permission_denials: []`).
- Up to 6 trials ran in parallel on 4 cores. `num_turns` in the JSON is unreliable (1-13), so it is not reported.
- Two trials ended with a junk final message (t3/1 and t4/2 reply only about a stale background-task notification). The projects themselves are fine and scored normally. This is a `claude -p` artefact when the agent starts background commands.
- Scorers (all in `$R/rp1_work/score/`, copies in `.claude/research/scripts/rp1/`): `check_project.sh` (import log, load-all of every .gd/.tscn/.tres, 120-frame main-scene run, grep for `SCRIPT ERROR|Parse Error|Failed to load|ERROR:`, `static_stats.py` for LOC/files/autoloads/Godot-3 idioms/FSM style) plus one probe per task (`plat_probe.gd`+`score_t1/t2.py`, `flow_probe.gd`, `persist_probe.gd`, `ai_probe.gd`, `ui_probe.gd` under Xvfb, `inv_probe.gd`, `pause_probe.gd`). Probes find the player/enemy/buttons by name heuristics and drive input through `Input.action_press` / `parse_input_event`, so a "pass" means "no failure found by this probe", not "good".
- Scorer validity [Run]: `score_t1.py` on a deliberately naive controller (instant velocity 300 px/s, constant gravity, no coyote/cut; `scripts/rp1/bad_plat_scripts/player.gd`) fails all 7 checks (apex 107 px vs 48, tap == hold, speed in 1 frame, buffer 1 frame). `score_t6.py` on a hand-made absolute-position HUD fails overlap and edge-anchoring (`Pause` drifts 360 px between sizes). The other probes were only run on the real trials, so their ability to fail is untested (see Open questions).

## Results matrix

Columns: files/LOC from `static_stats.py`; "checks" = probe checks passed/total (+ load-all / run-main errors, all 0); time and cost per trial.

| Task (pattern) | Trial | .gd / .tscn | LOC | Autoloads | FSM style | Checks | Failed check | Time s | USD |
|---|---|---|---|---|---|---|---|---|---|
| 1 P01 controller | 1 | 2 / 2 | 70 | 0 | none | 7/7 | - | 62 | 0.13 |
| | 2 | 1 / 2 | 45 | 0 | none | 7/7 | - | 88 | 0.17 |
| 2 P04/P05 dash+wall | 1 | 2 / 2 | 141 | 0 | none (flags) | 10/10 (incl. 7 T1 regression) | - | 101 | 0.24 |
| | 2 | 1 / 2 | 114 | 0 | none (flags) | 10/10 | - | 69 | 0.17 |
| 3 P08+P10 flow | 1 | 5 / 4 | 76 | 1 | none | 6/7 | fade-in swallow | 773 | 0.22 |
| | 2 | 7 / 7 | 102 | 1 | none | 6/7 | fade-in swallow | 490 | 0.23 |
| 4 P13/P14 save | 1 | 7 / 3 | 282 | 2 | none | 7/7 | - | 221 | 0.22 |
| | 2 | 5 / 3 | 323 | 1 | none | 7/7 | - | 204 | 0.19 |
| 5 P16 enemy | 1 | 2 / 1 | 100 | 0 | enum+match | 3/3 | - | 58 | 0.12 |
| | 2 | 2 / 1 | 72 | 0 | enum+match | 3/3 | - | 52 | 0.12 |
| 6 P21 HUD | 1 | 2 / 2 | 41 | 0 | none | 3/3 | - | 44 | 0.11 |
| | 2 | 2 / 2 | 46 | 0 | none | 3/3 | - | 39 | 0.11 |
| 7 P22 inventory | 1 | 6 / 1 | 206 | 0 | none | 8/8 | - | 60 | 0.14 |
| | 2 | 4 / 1 | 160 | 0 | none | 8/8 | - | 169 | 0.14 |
| 8 P12 pause | 1 | 6 / 5 | 105 | 1 | none | 13/13 | - | 239 | 0.17 |
| | 2 | 8 / 8 | 144 | 1 | none | 13/13 | - | 317 | 0.17 |

Typed-var ratio is high everywhere (typed:untyped 8:0 to 42:6). Bool-flag soup: at most 1 `var is_/can_/has_` per project. T2 (dash + wall) and T5 added state with `bool`/timer counters and enum respectively, with no size problems at this scale.

## Claim vs measured

Agent claims are from each trial's final summary; "measured" is from my probes (60 Hz fixed step unless noted).

| Trial | Claim | Measured | Verdict |
|---|---|---|---|
| t1/1 | 220 px/s in 6 frames (from accel, "run check interrupted") | vmax 220.0, 220 reached at frame 6 | holds |
| t1/1 | apex 48.1 px at ~0.383 s (own test) | 48.1 px, 0.367 s (apex-start-frame convention) ; 47.1 px @120 Hz, 50.2 px @30 Hz | holds, fps-independent |
| t1/1 | coyote 6, buffer 6, variable jump (explicitly NOT run) | coyote: jump accepted up to k=3 frames after first airborne tick (my press lands 1 tick late; code reading gives 4); buffer: accepted up to 6 frames before landing; tap 15.7 px vs hold 48.1 px | spec roughly met, claim untested by agent; coyote about 2 frames short of 6 |
| t1/2 | same, coyote/buffer "untested beyond the code" | coyote k=3, buffer k=5, tap 11.7 px vs hold 48.0 px | same |
| t2/1 | dash about 71 px; slide 55 px/s; wall jump away+up; "apex unchanged" | standing dash dx 67.8 px, peak vx 420; slide max vy 55.0 vs free fall 282.6; wall jump min vy -229, vx -200; T1 regression 7/7 | holds |
| t2/2 | dash about 62 px; slide cap 60; wall jump away; "didn't test second air dash refusal" | dx 62.2, peak vx 380; slide 60.0 vs 240.4; wall-jump vy -236; T1 regression 7/7 | holds |
| t3/1, t3/2 | "clicks blocked while a fade runs, so a second change can't start mid-fade" (t3/2); loop verified by throwaway script | full loop x8 menu>L1>L2>GO>retry OK, fade overlay seen, node/orphan/object counts flat over 8 cycles. BUT a hazard or exit triggered 5 frames after the level appeared is lost: `change_scene()` returns early on `busy` and nothing retries | claim true for clicks, but the same guard swallows gameplay triggers (see Trap 1) |
| t4/1, t4/2 | persistence verified across separate processes | mutate, restart, check: level progress, best time 12.3, Music volume 0.3, remap jump->K all persisted; reset clears progress; garbage/empty/truncated save files cause 0 script errors; Music bus exists at baseline | holds |
| t5/1, t5/2 | chase in the open, no chase behind a wall, return to patrol | clear LOS: chase state reached, distance 77 -> 2-3.5 px; 3 blocked points per trial: 0 chase frames; player `queue_free()` mid-chase: 0 script errors | holds (t5/1 declares omnidirectional sight, no FOV cone) |
| t6/1, t6/2 | all HUD elements on screen and non-overlapping at both sizes; 1706x720 visible area at 2560x1080 | confirmed exactly; also 800x600, 640x360, 3440x1440: 0 off-screen, 0 overlaps, edge distance drift <= 10 px | holds |
| t7/1, t7/2 | stack, merge, swap, overflow via headless test; drag-and-drop not tried with a mouse | 20 slots; 12 adds of 4 item types fill 9-11 slots (stacking works); move to empty, drop on self, swap/merge all conserve slot count via the built-in `_get_drag_data/_can_drop_data/_drop_data` API; 40 adds on a full inventory: 0 errors | holds (real mouse drag still unverified) |
| t8/1 | pause, focus on Resume, frozen player, restart unpauses; "didn't test Resume, Quit, Esc closing" | all 13 checks pass including Resume, Esc toggle, Quit to menu unpaused, `Engine.time_scale` untouched, Esc on menu does not pause; control: unpaused player moved 103 px | holds, more than claimed |
| t8/2 | same, plus restart_level, blocked while fading/dead | all 13 pass; control moved 113.7 px | holds |

## Failures and traps

1. **Scene-change guard swallows requests (D7, P10), both t3 trials, reproduced in t8 starts.**
   ```gdscript
   func change_scene(path: String) -> void:
   	if busy:            # or _busy
   		return          # request dropped silently
   	busy = true
   	await _fade(1.0)
   	get_tree().change_scene_to_file(path)
   	await get_tree().process_frame ; await get_tree().process_frame
   	await _fade(0.0)    # ~0.4 s during which busy is still true
   ```
   [Run: `score_t3.py` with `settle=5`: "timeout waiting scene change at step 3 (still res://scenes/level_1.tscn)" in both trials]. In t3/1 the exit handler sets `alive = false` before calling `change_scene`, so a swallowed call leaves the player dead-frozen and the level never ends. Exposure window is about 0.4-0.5 s after each scene appears. The 8-cycle soak at normal pacing passes, so only a timing probe finds it.
2. **Claimed-but-untested timing windows (D2, P01).** Coyote and buffer (the two tunables with off-by-one risk) were reported "untested" by both t1 agents and measure at 3-6 frames vs 6 claimed. The agents were honest; the risk is a reader skipping the caveat. A scripted-input scenario (the kind in `plat_probe.gd`) is cheap: 4.5 s for the full T1 suite.
3. **Input-map glue (D8, P15).** Player movement on `ui_left/right/up/down` in t3/1 and t3/2 (4 uses each, inherited by t8), `ui_cancel` as pause in t8/2, `ui_accept` as fire in t6/1; t5/1 builds WASD actions in `_ready()` with `InputMap.add_action` + `KEY_*` (4 raw keys) so `project.godot` has no input map. Works, but cannot be remapped from a settings screen and collides with menu navigation.
4. **Leftover scratch tests in the project** (hygiene): `scripts/test.gd` remained in t1/1, t2/1 (inherited), t4/1 (`test_persist.gd`), t7/1 (`test.gd`).
5. **Top-down player tied to node names / groups** (D4): the t5 and t3 scripts resolve the player by `NodePath` export or `$Player`; t8 added a `player` group only in t8/2 to find the player. Harmless here; it is what makes composition (C1) brittle.
6. **`claude -p` artefact:** background shell commands can leave a stale notification as the last message (t3/1, t4/2).

No trap was found for: Godot-3 API use, dB-vs-linear volume (both t4 trials use `linear_to_db`), unversioned or non-atomic saves (t4/1 `version` + tmp+rename, t4/2 `version`; t4/2 has no atomic rename), buses missing at runtime (both create Music/SFX in `_ensure_bus*`), processing while paused (`process_mode` ALWAYS / WHEN_PAUSED set in both t8), `time_scale = 0`, `change_scene_to_file` call sites (1 per project, in the autoload), orphan growth.

## Pattern severity x importance ranking

Severity is from this study only (0 = nothing found, 3 = real defect), importance from the plan's catalogue. "n/a" means RP.1 did not test it.

| Rank | Pattern | Severity | Importance | Why |
|---|---|---|---|---|
| 1 | P10 game flow / scene manager (+C1 composition) | 2 | high | swallow guard in 2/2; trap is timing-only, found by no ordinary test |
| 2 | P01/P05 feel (timing windows, tuning) | 1 (claims) + D1/D10 unmeasured | high | passed specs; coyote/buffer untested by agents; "feel" is not measured here at all |
| 3 | P15 input contexts | 1 | medium | `ui_*`/code-registered actions in 5/16 trials |
| 4 | P13/P14 persistence | 0 | high | passed, one trial lacks atomic write; remap stores physical keycode only |
| 5-9 | P16, P21, P22, P12, P04 | 0 | various | no defect found by these probes |
| - | P02, P03, P06, P07, P09, P17-P20, P23, P24 | n/a | | not tested |

Root causes: D2 (no-feedback claims) and D7 (lifecycle) dominate; D8 next. D5/D6 (tutorial priors, mis-sizing) and D9 (context dilution) were not observed at this task size. D1/D10 cannot be seen by any probe here.

## Recommended effort split for RP.A-RP.K

| Topic | Effort | Reason from this data |
|---|---|---|
| RP.A (P01/P02/P05 controller) | full | basic controller passes; value is in slopes/platforms (P02, untested), timing-window measurement with a stated convention (off-by-one ambiguity cost me a rewrite), feel targets as human gate |
| RP.B (3D P03/P07) | full (no baseline) | untested; assume nothing |
| RP.C (state machine, animation P04/P20) | reduced | P04 sizing was proportionate; P20 untested, so keep animation-sync checks only |
| RP.D (camera, hit-stop, P06/P05) | full | untested and feel-dominated |
| RP.E (levels, components P08/P09) | full | untested (P09 especially); T3 levels were minimal hand-written .tscn, no TileMap |
| RP.F (flow, autoloads, pause, audio P10-P12/P24) | full | the only defect class found (soft-lock timing); pause itself passed |
| RP.G (save, settings, input P13-P15) | reduced | persistence passed; keep P15 lint and remap-in-settings check |
| RP.H (AI, nav P16/P17) | reduced | P16 passed; P17 navigation untested, spend there |
| RP.I (spawn, layers P18/P19) | full (no baseline) | untested |
| RP.J (HUD P21) | reduced | passed at 5 sizes; look/theme still human gate |
| RP.K (inventory, data-driven P22/P23) | reduced | P22 passed; P23 untested |
| RP.Z2 | note | these projects are clean and small, so they are poor "messy project" starting points; build messy tier-2 starts by composition (t3 -> t8 style) or by injecting traps |

## Open questions

- The scorers are heuristic (name-pattern lookup of buttons, exit/hazard areas, add buttons). Only `score_t1` and `score_t6` were shown to fail on a bad implementation; the others (flow, persistence, AI, inventory, pause) have no negative control yet, so some of the 88 passes may be weaker than they look.
- Coyote/buffer numbers carry a +/-1-2 frame convention error (my action press lands in the SceneTree callback, which runs relative to node `_physics_process` in an order I did not isolate). Treat 3-6 as "roughly correct", not as a measured off-by-N.
- Trials per task: 2, one model, one default config. Variance between trials is visible (t3 773 s vs 490 s; LOC 45 vs 70) but too small a sample for rates.
- Would vaguer prompts ("make a platformer"), no `godot` hint or no "verify" instruction change the picture? Likely yes (D9); not tested.
- Real-mouse drag-and-drop, gamepad focus and visual look of the HUD/menus were not exercised.

## Blocked sources

None used. No web access was needed (all work local: Godot 4.7 binary, `claude` CLI).

## Where things are

- Kept projects: `$R/rp1_work/runs/t{1..8}/t{1,2}/` (clean copies, with `.godot`), per-trial result JSON `tN/tM.result.json`, score output `tN/tM.score.txt`, `tN/tM.meta`.
- Scorers: `$R/rp1_work/score/` and `.claude/research/scripts/rp1/` (also `run_trial.sh`, task texts `t1.txt`-`t8.txt`, `pre.txt`, `aggregate.py`).
- `$R=/tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad/research`
