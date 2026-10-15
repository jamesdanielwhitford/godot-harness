# Addendum P: research plan for making agents good at Godot game-dev PATTERNS ("Round P")

Extends `godot_harness_plan.md` and does not replace it. Tags [K]/[U]/[P], component ids C1–C10 and failure ids F1–F15 are as in the plan.

**What this is.** A plan of Sonnet research subagents, **one per game-dev pattern or topic**: character controller, level organisation, full game structure, and so on. Each one finds out:
1. what good looks like,
2. how to measure it by script,
3. how LLM agents typically get it wrong (shown by experiment),
4. which vetted reference projects to learn from,
5. which techniques (skills, decision rules, scaffolds, generators, acceptance tests, conventions) measurably improve agent output.

§P1 (diagnosis) and §P2 (catalogue) are brief support for the prompts. **§P3 (the prompts) is the deliverable.**

Environment **[P, 2026-10-15]**:
- The `claude` CLI is at `/opt/node22/bin/claude`. Nested `claude -p` runs may be possible; auth inside subagents is [U].
- `node`/`npx` are present.
- `research/` has work dirs for R1.1, 1.3, 1.4, 1.5, 1.7 and 1.8, but **none for R1.2 (MCP)**. See RP.0.

---

## P1. Diagnosis framework (brief)

Why agents fail at pattern-level work, and whether a harness can fix it:

| ID | Root cause | Harness-fixable? |
|---|---|---|
| D1 | **Emergent/feel properties.** Quality lives in time series (jump arc, camera lag), not code text. | Partly. Traces vs targets (C7) yes; choosing targets is taste. |
| D2 | **No feedback signal.** "It parses" is the only check, so the agent claims features it never exercised. | Yes. Per-pattern acceptance scenarios. |
| D3 | **Cross-file architecture.** Flow spans autoloads, `project.godot`, scenes and signals; the agent sees one file at a time. | Mostly. Project digest, structural lint, loop/leak tests. |
| D4 | **Scene-vs-script split.** Either builds levels in code or hand-writes fragile `.tscn` data (tile bytes). | Yes. Generators and the convention "structure = scenes, behaviour = scripts". |
| D5 | **Tutorial-quality priors.** Reproduces the median (often Godot 3) beginner tutorial, e.g. a `Global.gd` god object. | Yes. Vetted local reference library. |
| D6 | **Mis-sized structure.** Boolean soup, or `AbstractState` frameworks for 3 states. | Partly. Explicit decision rules plus a human-set project tier. |
| D7 | **Lifecycle semantics.** Pause `process_mode`, nav map sync on frame 0, `queue_free`/await on freed nodes. | Yes. Trap lists plus tests. |
| D8 | **Missing game glue.** Input contexts, gamepad focus, save versioning, resolution scaling, layer matrix. | Yes. Checklists plus lint. |
| D9 | **Context dilution on big asks** ("make a game"). | Yes. Scaffold-first and pattern-sized tasks. |
| D10 | **Taste.** Fun, pacing, fairness, look. | **No.** Human; the agent measures and proposes variants. |

**Responsibility layers:**
- **Correctness** (spec + test): the agent owns it.
- **Structure** (conventions + lint): the agent follows the rules, and a human sets the tier.
- **Tuning** (numbers vs targets): the agent tunes, and a human sets the targets.
- **Taste:** human only. The agent supplies a `--write-movie` clip + metric table + 2–3 variants and never claims "feels good".

**Method to find out:** first measure plain Claude Code on pattern tasks (RP.1), then invest per pattern in proportion to failure × importance. Re-measure after the fixes (RP.Z2).

## P2. Pattern catalogue (brief index; the topic prompts expand each)

Measure codes:
- **T** per-tick trace metric
- **S** scripted-input scenario test
- **L** structural lint
- **V** screenshot / numeric layout
- **U** unit test

| ID | Pattern | Good (one line) | Measure | Typical LLM failure | Topic agent |
|---|---|---|---|---|---|
| P01 | 2D platformer controller | accel/decel, asymmetric gravity, variable jump, coyote, buffer, tunables in `.tres`, fps-independent | T apex/time-to-apex/accel frames; S coyote/buffer at k frames; S 30/60/120 Hz | instant velocity, floaty constant gravity, no coyote/buffer, Godot 3 `move_and_slide(v)` | RP.A |
| P02 | Slopes / moving / one-way platforms | snap + floor params deliberate | S idle drift, crest launch, platform carry, drop-through | no snap (bouncing), raycast hacks | RP.A |
| P03 | 3D character controller | camera-relative XZ, normalised diagonal, clamped pitch, mouse not × delta | S heading error, diagonal speed, pitch clamp | world-space movement, `basis.z` sign, body pitches | RP.B |
| P04 | State machine sizing | explicit states, one transition site, size fits complexity | S state trace; L graph vs spec, flag count, LOC | boolean soup or over-engineered framework | RP.C |
| P05 | Dash/attack/hit-stop/i-frames | windows from tunables, time_scale restored | T windows; S no damage in i-frames | timers on freed nodes, time_scale stuck | RP.A/RP.D |
| P06 | 2D camera + shake | smoothing, look-ahead, limits from level, trauma shake → 0 | T lag/overshoot; S view inside level rect | camera child of flipping player, hard-coded limits, residual offset | RP.D |
| P07 | 3D camera rig | SpringArm excludes player, smoothing | S corridor clip test | arm collides with own capsule, jitter | RP.B |
| P08 | Level scene structure | BaseLevel slots, TileMapLayer, spawn/exit, player spawned by game | L slots/layers; S load + reachability | levels in code, hand-written tile bytes, player copied into each level | RP.E |
| P09 | Composable components | Hitbox/Health/Pickup scenes reused | L duplicate logic, inheritance depth | copy-paste per enemy or deep inheritance | RP.E |
| P10 | Game flow / scene manager | one SceneManager, fades, threaded load | S full loop ×10, orphan/leak check | scattered `change_scene_to_file`, leaks | RP.F |
| P11 | Autoload discipline | 3–6 single-purpose autoloads | L count/size/node refs | `Global.gd` god object or autoload sprawl | RP.F |
| P12 | Pause & menus | process_mode right, focus | S world frozen, menu alive | menu pauses itself, time_scale=0 | RP.F |
| P13 | Save/load | versioned JSON data in `user://`, atomic, no `.tres` from user | U round-trip, migration, corrupt file | saving scenes/NodePaths, no version | RP.G |
| P14 | Settings & remap | ConfigFile, buses dB, remap persisted | S restart persistence | linear written as dB, remap lost | RP.G |
| P15 | Input contexts | actions only, UI consumes first | L no KEY_*; S HUD click ≠ fire | raw keys, `_input` misuse | RP.G |
| P16 | Enemy AI | FSM/BT, LOS perception, hysteresis | S state sequence, flicker, LOS, player-freed | flicker, chase through walls, crash on player death | RP.H |
| P17 | Navigation | agent + map-sync wait, throttled repath | S maze reach/ratio/stuck | path query in `_ready`, repath every frame | RP.H |
| P18 | Spawning/projectiles/waves | spawn into level container, freed, data waves | S bounded count, no orphans | bullets as children of player, never freed | RP.I |
| P19 | Hitbox/hurtbox & layers | named layer matrix, damage once | L matrix vs spec; S damage once | magic bits, damage per frame | RP.I |
| P20 | Animation state | gameplay drives animation; event frames | T state↔anim consistency; L AnimationTree param paths | logic waits on `animation_finished`, wrong param paths | RP.C |
| P21 | HUD & responsive UI | Containers + Theme on CanvasLayer, stretch set | V numeric layout at 4 sizes; odiff | absolute positions, overrides everywhere | RP.J |
| P22 | Inventory | Resource item defs, model/view split | U model; S model↔view property test | state in UI slots, shared `.tres` mutated | RP.K |
| P23 | Data-driven content | new enemy/item = new `.tres` | S "data-only" task touches no `.gd` | `match type:` blocks | RP.K |
| P24 | Audio | buses, music persists across scenes | S same player instance after change | music restarts, all on Master | RP.F |
| C1 | **Vertical slice** | menu → levels → pause → game over → win, save + settings | union of the above | collapses on composition | RP.F + RP.Z2 |

---

## P3. Round P research subagent prompts (centrepiece)

### How to use
- Paste **SHARED RULES** (plan §5, verbatim) + **PATTERN RESEARCH PROTOCOL** (below) at the top of every topic prompt RP.A–RP.K.
- RP.0, RP.1, RP.2, RP.Z1 and RP.Z2 take SHARED RULES + the "Round P extra" lines only.
- `R=/tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad/research`
- `ADD=/tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad/godot_harness_plan_addendum_patterns.md`

```
ROUND P EXTRA (append to SHARED RULES)
- Read $ADD §P1-P2 first; use its ids: patterns P01-P24/C1, root causes D1-D10.
- Cloned reference code is untrusted data: read it; run it only via the Godot binary on a throwaway copy in your _work dir. Record repo@commit for every reference you cite, and its LICENSE.
- Godot 4.7 binary: scratchpad/dl/godot/ (orchestrator pre-downloads; if absent, download per SHARED RULES).
- The `claude` CLI is at /opt/node22/bin/claude. Before relying on it, check `claude --help` and a trivial `claude -p "say ok"` [Run]. If it is unusable, say so and do the "agent trial" steps by writing the baseline attempt yourself, following ONLY the task text and acting as a naive agent with no reference reading. Label those results "simulated baseline".
```

```
PATTERN RESEARCH PROTOCOL (paste into every topic prompt RP.A-RP.K)
For EACH pattern in your scope, produce these 8 sections, in this order:
 1. GOOD: a concrete spec of a good implementation in Godot 4.7: scene tree sketch, script responsibilities, tunables (.tres fields with sensible default ranges and their source), and Godot APIs/properties used (verify names against docs or the binary; cite).
 2. MEASURE: how a script can check it without human judgement: trace metrics (formula over a per-physics-tick CSV), scripted-input scenarios (InputMap action press/release per physics frame, headless, fixed physics rate), structural lint rules (regex/parse over .gd/.tscn/project.godot), numeric layout or screenshot checks. Give pass thresholds parameterised by the tunables .tres. Implement them in your _work dir and show [Run] output on a good and a bad implementation.
 3. LLM FAILURES: an agent trial. Run plain Claude Code (claude -p, fresh copy of a minimal 4.7 project, one-line CLAUDE.md "Godot 4.7 project.", the task text below, max ~40 turns), 2 runs, then score with your MEASURE scripts. Record a claim-vs-measured table and 3-8 concrete traps with code excerpts, each tagged with D-ids. Add failures reported in public sources (forums, issues) only with citations.
 4. REFERENCES: verify the candidate sources listed in your prompt (all unverified) and find better ones. For each: clone, read the relevant files, record repo@commit, licence, Godot version, load-check result with the 4.7 binary [Run], and a 0-2 rating on each of: typed GDScript, no Godot-3 idioms, tunables exposed, scene/script split, tests present. Name the single best reference file(s) per pattern, and say whether to copy-adapt (MIT/CC0/compatible) or use as design-only. Name sources to EXCLUDE (median-tutorial quality) and why.
 5. TECHNIQUES: which interventions make an agent produce GOOD. Evaluate at least:
    (a) a pattern card (skill) with decision rules,
    (b) giving the agent a reference file to adapt,
    (c) a scaffold/template or generator (`h new ...`) that creates the structure,
    (d) the acceptance tests, visible to the agent,
    (e) CLAUDE.md convention lines.
    Run at least ONE improved agent trial (the same task with your best combination) and compare it with step 3 on your metrics. Recommend the minimum combination that works.
 6. DECISION RULES: when to use which variant (sizing by game scale and genre), written as if/then rules an agent can follow mechanically.
 7. HUMAN GATE: what stays human-judged (feel targets, look, fun), and the exact artefact the agent hands over (clip + metric table + variants).
 8. PATTERN CARD DRAFT: <=120 lines in the fixed format: Intent / Use when / Don't use when / Decision rules / Scene tree / Tunables / Steps (scaffold -> read ref -> adapt -> test) / Acceptance checks (ids + commands) / Known LLM traps / References (repo@commit:path).
Output file layout: start with a 5-10 line "Answer", then one H2 per pattern holding sections 1-8, then "Cross-pattern findings", "Blocked sources" and "Open questions". Max ~4000 words (an exception to the 2500 limit). Code goes in $R/<id>_work/ and is referenced by path, not pasted (except short excerpts).
Integration: if $R/r2_1_core_harness.md, $R/r2_2_replay.md or $R/r2_4_feel.md exist, reuse their runner, trace recorder and `h` verbs. Otherwise write minimal stand-ins (a headless scenario script reading a JSON of {frame, action, pressed}, and a CSV trace recorder) and note that they should be merged later.
```

---

### Cross-cutting prompts (run first, in parallel with Round 1)

**RP.0 Godot MCP servers: discover, download, run, analyse** (supersedes R1.2 if R1.2 has not run; otherwise deepens it)
```
[SHARED RULES + ROUND P EXTRA]
Read first (if present): $R/r1_2_mcp.md, $R/r1_1_cli.md, plan §4 (C1-C10).
Question: Which Godot MCP servers actually exist today? Is any "official" or a de-facto standard? After installing and RUNNING the top 2-3 against a Godot 4.7 project, should the harness adopt one, borrow parts of one, or build its own?
1 Discover; do not assume. Sources to query:
  - the npm search API (https://registry.npmjs.org/-/v1/search?text=godot%20mcp&size=50, also text=godot-mcp);
  - PyPI (https://pypi.org/pypi/<name>/json for candidate names, and simple-index names containing godot and mcp);
  - the MCP registry (try https://registry.modelcontextprotocol.io/v0/servers?search=godot; record the HTTP code);
  - the Godot Asset Library API (https://godotengine.org/asset-library/api/asset?filter=mcp; check the params);
  - awesome-mcp-servers / awesome-godot READMEs via raw.githubusercontent.com.
  Names reported elsewhere (unverified): Coding-Solo/godot-mcp, ee0pdt/Godot-MCP, bradypp/godot-mcp, "GDAI MCP". State with evidence whether godotengine / the Godot Foundation publishes any MCP. If none is found, say "none found"; never invent one.
2 Shortlist 2-3 by: Godot 4.x support, last commit (git log -1 after clone), npm/pypi downloads if visible, licence, tool breadth.
3 Clone with `git clone --depth 50` into scratchpad/dl/mcp/<name>/ (github.com web/API pages are blocked, git clone works). READ the source before running anything:
  - every tool and its args, taken from the source, not the README;
  - transport: stdio; editor plugin over WebSocket/TCP; spawns the godot CLI;
  - any arbitrary GDScript/expression eval;
  - open ports;
  - writes outside the project;
  - scene editing method: raw .tscn text vs the engine API;
  - screenshot and input-injection support;
  - whether it needs the editor GUI.
4 Run. Build a tiny 4.7 project (player, level, one script). Install each server (npm/pip into a venv inside its dl dir). Drive it WITHOUT Claude Code via a minimal stdio MCP client (Python `mcp` package in a scratchpad venv; script in $R/rp_0_work/), or `npx @modelcontextprotocol/inspector --cli` if that works.
  - Record list_tools output [Run].
  - Call 5-8 representative tools: run the project, read output, get the scene tree, add a node and save, take a screenshot (xvfb-run), inject input, stop.
  - Record results, errors, timings and output size in bytes.
  - If a server needs the editor, try `xvfb-run godot --editor --path proj`.
5 Assess against C2, C4/C4w, C6, C8 and C10 (our CLI-first design): context-size hygiene, determinism (seeded / fixed-step?), security and how to sandbox it, maintenance risk. Also: is it useful for PATTERN work specifically, e.g. live scene-tree inspection while building levels or UI?
Output: $R/rp_0_mcp_handson.md:
  - discovery table (name, source, version, last commit, licence, Godot versions, official y/n + evidence);
  - capability matrix;
  - run-log excerpts;
  - recommendation (adopt for C10 only / borrow approach / build own), with a ready .mcp.json snippet and permission/sandbox settings if adopting.
If R1.2 never ran, also write the matrix and recommendation to $R/r1_2_mcp.md.
```

**RP.1 Baseline pattern-failure study (where do agents fail most?)**
```
[SHARED RULES + ROUND P EXTRA]
Read first: $ADD §P1-P2; $R/r1_1_cli.md if present.
Question: Across the whole catalogue, which patterns does plain Claude Code fail worst on, and which root causes dominate? This sets priorities for RP.A-RP.K. It is a broad, shallow pass; the topic agents go deep.
Tasks (8, one prompt each; start from an empty 4.7 project in $R/rp_1_work/<task>/start/):
  (1) P01 2D controller to this spec: max speed 220 px/s in <=8 frames; apex 3 tiles (48 px) at 0.38 s +/-0.03; coyote 6 frames; buffer 6 frames; variable jump height.
  (2) P04/P05 add dash + wall-slide to (1)'s output.
  (3) P08+P10 menu -> 2 levels -> game over -> retry, with fade transitions.
  (4) P13/P14 save level progress + settings.
  (5) P16 patrol/chase enemy with line of sight.
  (6) P21 HUD that works at 1280x720 and 2560x1080.
  (7) P22 inventory with stacking + drag/drop.
  (8) P12 add a pause menu to (3).
Run 2 trials each with claude -p (30 min / 60 turn cap). Score with minimal scripts in $R/rp_1_work/score/: load-all check, one or two key S/T/L checks per task (from §P2), and LOC / files / autoload count / FSM style. Keep a claim-vs-measured table.
Output: $R/rp_1_baseline.md: results matrix; failures tagged with D/P ids; a ranking of patterns by severity x importance; recommended effort split across RP.A-RP.K (full / reduced / skip). Keep all output projects; they become the "messy project" starting points for RP.Z2 tier-2 tasks.
```

**RP.2 Reference corpus census (shared input to all topic agents)**
```
[SHARED RULES + ROUND P EXTRA]
Read first: $ADD §P2.
Question: Which open-source Godot 4.x projects and addons are trustworthy references for game-dev patterns, at which commits, under which licences?
Verify (all unverified):
  - godotengine/godot-demo-projects
  - KidsCanCode godot_recipes 4.x
  - GDQuest demo repos (e.g. godot-open-rpg)
  - KenneyNL Starter-Kit-* (Godot 4)
  - Maaack/Godot-Game-Template
  - ramokz/phantom-camera
  - limbonaut/limboai
  - bitbrain/beehave
  - derkork/godot-statecharts
  - peter-kish/gloot
  - Phazorknight/Cogito
  - dialogic-godot/dialogic
  - NoelFB/Celeste (Player.cs; licence check, design reference only)
Also find more via the awesome-godot README (raw.githubusercontent.com) and the Asset Library API. In particular find 2-4 complete open-source Godot 4 GAMES (not demos) for architecture reference.
For each: shallow clone, commit hash, LICENSE, Godot version from project.godot, last commit date, headless load-check with the 4.7 binary [Run], a quick quality grep (Godot-3 idioms per $R/r1_5_failure_lint.md if present; typed-var ratio), and which P-ids it covers.
Output: $R/rp_2_references.md: a ranked table, a P-id -> candidate files map (topic agents will deepen this), an exclusion list, and a draft refs.yaml (fenced YAML: name, url, commit, licence, godot_version, patterns, paths). Clones stay in scratchpad/dl/refs/<name>/ for topic agents to reuse (tell them the paths).
```

---

### Per-pattern topic prompts (one subagent each; run in parallel after RP.1/RP.2)

**RP.A 2D character controller and movement feel (P01, P02, P05 movement parts)**
```
[SHARED RULES + ROUND P EXTRA + PATTERN RESEARCH PROTOCOL]
Read first: $R/rp_1_baseline.md, $R/rp_2_references.md, $R/r2_4_feel.md (if present; else $R/r1_8_determinism.md), $R/r1_8_determinism.md.
Scope: P01 platformer controller; P02 slopes / moving platforms / one-way platforms; movement parts of P05 (dash, wall-slide/jump, corner correction).
Investigate specifically:
- Jump parameterisation by designer intent (height h, time-to-apex t: g = 2h/t^2, v0 = 2h/t; separate fall gravity; cite "Building a Better Jump", GDC [find URL]).
- Accel/decel curves, ground vs air; coyote and buffer implemented as frame counters vs Timers (which is deterministic under fixed-step?); variable-jump cut; terminal velocity; corner correction.
- CharacterBody2D floor properties (floor_snap_length, floor_max_angle, floor_constant_speed, floor_stop_on_slope, platform_on_leave, platform_floor_layers); one-way collision drop-through methods.
- Frame-rate independence: run at physics 30/60/120 Hz and compare metrics.
- Physics interpolation on/off: effect on traces vs visuals.
Candidate references (unverified): godot-demo-projects 2d/platformer and 2d/kinematic_character; Celeste Player.cs (design-only); GDQuest platformer material; KidsCanCode platform character recipes; Maddy Thorson's/Celeste and "Platformer Toolkit" (GMTK) write-ups on coyote/buffer [U].
Agent trial task text: the RP.1 task (1) spec, plus "support 20-degree slopes, a moving platform, and drop-through one-way platforms".
Measure deliverables: tunables MovementTuning.tres; scenarios (flat run, jump tap vs hold, ledge-walk coyote sweep k=0..10, landing buffer sweep k=0..10, slope course, moving platform, drop-through); metric script; thresholds from the .tres.
Output: $R/rp_a_controller2d.md; code in $R/rp_a_work/.
```

**RP.B 3D character controller and 3D camera rig (P03, P07)**
```
[SHARED RULES + ROUND P EXTRA + PATTERN RESEARCH PROTOCOL]
Read first: $R/rp_1_baseline.md, $R/rp_2_references.md, $R/r2_4_feel.md if present.
Scope: P03 third-person and first-person CharacterBody3D controllers; P07 camera rigs (SpringArm3D orbit, FPS head).
Investigate:
- Camera-relative input (basis of the yaw pivot, flattened to XZ); diagonal normalisation; rotate-to-move-direction with lerp_angle; mouse look (yaw on body/pivot, clamped pitch on camera; never x delta); mouse capture and release with menus; gamepad look with dead zones; stairs/step handling in 3D (is there built-in support in 4.7? Jolt specifics?); SpringArm3D collision excluding the player (exclude RID vs mask).
- Jitter sources: camera updated in _process vs body in _physics_process; physics interpolation in 3D (status in 4.7: check docs).
- Headless measurability: can SpringArm3D / raycasts be evaluated under --headless (physics yes, rendering no)? [Run]
Candidate references (unverified): KenneyNL Starter-Kit-3D-Platformer and Starter-Kit-FPS; GDQuest 3D third-person controller demo; Cogito (FPS); godot-demo-projects 3d/platformer, 3d/character? [U].
Agent trial task text: "Add a third-person controller with an orbit camera that doesn't clip walls, plus a run and jump, to this 3D test level."
Measure: heading error vs camera yaw sweep (0..360 in 15-degree steps), diagonal speed, pitch clamp under extreme mouse input, corridor clip distance, camera-lag settle time.
Output: $R/rp_b_controller3d.md; code in $R/rp_b_work/.
```

**RP.C State machines and animation state (P04, P20)**
```
[SHARED RULES + ROUND P EXTRA + PATTERN RESEARCH PROTOCOL]
Read first: $R/rp_1_baseline.md, $R/rp_2_references.md, $R/rp_a_controller2d.md if done.
Scope: P04 player/entity state machines and their SIZING; P20 animation driven by gameplay state (AnimatedSprite2D, AnimationPlayer, AnimationTree state machine / BlendSpace).
Investigate:
- Implementation styles in Godot 4.7: enum + match; state objects (RefCounted); node-per-state; godot-statecharts; LimboAI HSM. Compare LOC, readability for an LLM (can the agent see the whole graph in one file?), testability (state trace), and over-engineering risk.
- Write the R-FSM sizing rule with worked examples at 3, 7 and 12 states, plus one hierarchical/parallel case (movement x weapon).
- A lint that extracts the transition graph from code (or the addon's data) and compares it with a spec.
- Animation: AnimationTree parameter paths ("parameters/playback", travel vs start); does AnimatedSprite2D.play(same) restart? [Run]; method/call tracks and frame signals for hit frames; why logic gated on animation_finished softlocks; facing/flip in one place.
- Traces: a (gameplay_state, anim_name, anim_frame) consistency metric.
Candidate references (unverified): derkork/godot-statecharts; limbonaut/limboai; GDQuest FSM tutorials (Godot 4 versions); godot-demo-projects animation-related demos.
Agent trial task text: "Refactor this player [give RP.1's boolean-soup output] into a state machine with idle/run/jump/fall/dash/wall-slide/hurt, and drive animations from it."
Output: $R/rp_c_fsm_anim.md; code in $R/rp_c_work/.
```

**RP.D 2D camera and game juice (P06, P05 hit-stop/shake/i-frame feedback)**
```
[SHARED RULES + ROUND P EXTRA + PATTERN RESEARCH PROTOCOL]
Read first: $R/rp_1_baseline.md, $R/rp_2_references.md, $R/r2_4_feel.md and $R/r1_7_visual.md if present.
Scope: P06 Camera2D follow (smoothing, drag margins, look-ahead, limits from level bounds, room/zone transitions); screen shake (trauma model, seeded noise); hit-stop; flash/i-frame blink; tween-based UI juice.
Investigate:
- Camera2D properties in 4.7 (position_smoothing_*, drag_*, limit_*, process_callback); deriving limits automatically from TileMapLayer.get_used_rect().
- Shake via offset with FastNoiseLite seeded from the Rng autoload, decaying to exactly 0.
- Hit-stop by Engine.time_scale vs per-node pausing: trade-offs and restore guarantees.
- Phantom Camera addon: worth adopting? LLM-friendliness of its API.
- Metrics: lag frames, overshoot, settle time, view-rect-inside-level, residual offset, time_scale restored.
- The human-gate artefact: a short clip per variant from --write-movie (under xvfb per R1.7).
Candidate references (unverified): ramokz/phantom-camera; "Math for Game Programmers: Juicing Your Cameras With Math" (Squirrel Eiserloh, GDC) for trauma shake; "Juice it or lose it" (GDC/talk) [U]; godot-demo-projects 2d camera demos.
Agent trial task text: "Add a camera that follows the player smoothly with look-ahead, stays inside the level, and shakes when the player is hit, plus a short hit-stop."
Output: $R/rp_d_camera_juice.md; code in $R/rp_d_work/.
```

**RP.E Level and scene organisation (P08, P09)**
```
[SHARED RULES + ROUND P EXTRA + PATTERN RESEARCH PROTOCOL]
Read first: $R/r1_4_scene_format.md, $R/r2_1_core_harness.md (scene-gen, digest) if present, $R/rp_1_baseline.md, $R/rp_2_references.md.
Scope: P08 how to organise scenes to build many levels; P09 composable entity components.
Investigate:
- BaseLevel with fixed slots (TileMapLayer nodes (TileMap deprecated in 4.3? verify), %PlayerSpawn, %Exit, %Entities, %Bounds, LevelData.tres): inherited scene vs instanced base vs composition. Which works best for agents AND for humans in the editor?
- Player spawned by the game, not stored in levels.
- Named collision layers in project.godot.
- How an agent should CREATE level content without hand-writing tile bytes: an engine-API generator (TileMapLayer.set_cell from an ASCII/JSON level spec, then PackedScene.pack + ResourceSaver.save) [Run]; a "level from ASCII art" spec format; when humans should paint in the editor instead.
- Reachability check: grid BFS spawn->exit with the jump-reach envelope taken from RP.A's tunables, or a NavigationRegion in 3D.
- Components: Health/Hitbox/Hurtbox/Pickup/Interactable as small scenes with typed signals; scene inheritance depth limits; lint for duplicated logic across entity scripts.
- Folder layout conventions (by feature vs by type) and how they affect agent navigation; recommend one.
Candidate references (unverified): godot-demo-projects 2d/platformer, 2d/dynamic_tilemap_layers; KenneyNL starter kits; GDQuest open-rpg (level/map organisation); Godot docs "Scene organization" and "Project organization".
Agent trial task text: "Create 3 platformer levels for this game with a shared structure, each with spawn, exit, 2 enemies and 3 pickups, and make the game load level 1."
Deliverables: generator `h new level` sketch + ASCII level spec format, structural lint rules (id, check, rationale, false-positive risk), reachability script.
Output: $R/rp_e_levels.md; code in $R/rp_e_work/.
```

**RP.F Full game structure: flow, scene manager, autoloads, pause, audio (P10, P11, P12, P24, C1)**
```
[SHARED RULES + ROUND P EXTRA + PATTERN RESEARCH PROTOCOL]
Read first: $R/r2_2_replay.md if present, $R/rp_1_baseline.md, $R/rp_2_references.md, $R/rp_e_levels.md if done.
Scope: composing a full game: boot -> main menu -> level n -> pause -> game over/win -> retry/menu; SceneManager; transitions; threaded loading; autoload set and responsibilities; event bus (when/when not); pause and process_mode; music persisting across scenes; the vertical slice C1.
Investigate:
- change_scene_to_file / change_scene_to_packed vs a manual root-swap under a persistent Main node: which is more robust and testable? [Run]
- ResourceLoader.load_threaded_request flow with a loading screen.
- Blocking input during fades.
- Autoload sizing (the jam/small/large tier rule R-SCALE: what each tier contains).
- Detecting autoloads that hold refs into freed scenes.
- Leak test: 10 full loops, Performance OBJECT_ORPHAN_NODE_COUNT and node count stay flat.
- Pause: process_mode matrix; menu focus for gamepad; mouse mode.
- Audio: bus layout file; music autoload with crossfade.
- KEY QUESTION: is the best agent technique here a ready-made TEMPLATE project (start from it) rather than a skill? Test both: an agent trial from an empty project with the card only, vs from the template.
Candidate references (unverified): Maaack/Godot-Game-Template; godot-demo-projects loading/* demos; Godot docs "Singletons (Autoload)", "Background loading", "Change scenes manually", "Pausing games"; 2-4 open-source complete games found by RP.2.
Agent trial task text: "Turn this single-level prototype into a complete game: main menu, 3 levels in sequence, pause menu, game over with retry, win screen, fade transitions, background music that continues across levels."
Deliverables: a template project in $R/rp_f_work/template/ (or an adoption verdict on Maaack's); a flow scenario driven by input actions only; the leak test; an autoload/flow lint (only SceneManager changes scenes; autoload count and size); a CLAUDE.md "Game architecture" block (<=20 lines); R-SCALE tier definitions.
Output: $R/rp_f_game_structure.md.
```

**RP.G Persistence and input: save/load, settings, remapping, input contexts (P13, P14, P15)**
```
[SHARED RULES + ROUND P EXTRA + PATTERN RESEARCH PROTOCOL]
Read first: $R/rp_1_baseline.md, $R/rp_2_references.md, $R/r2_3_architecture.md if present (sim state serialisation), $R/rp_f_game_structure.md if done.
Scope: P13 save/load; P14 settings + input remapping; P15 input handling and contexts.
Investigate:
- Save formats: JSON (JSON.stringify/parse type caveats: ints become floats), var_to_str, ConfigFile, binary FileAccess.store_var; versioning and migration; atomic write (temp + DirAccess.rename) [Run]; the security of loading .tres/.res from user:// (resources can embed scripts: find the current docs and community guidance and cite them); what to save (data snapshot by stable ids, never NodePaths/instance ids); save slots.
- Settings: AudioServer bus volume via linear_to_db; window mode / resolution / vsync; persisting InputMap remaps (InputEvent serialisation to ConfigFile) and re-applying at boot.
- Input: _input vs _unhandled_input vs _unhandled_key_input; GUI consumption; gamepad UI focus; explicit input contexts (gameplay/menu/dialogue); lint for raw KEY_* outside remap code.
- Tests: round-trip deep-equality, old-version migration, corrupted file, settings persistence across two process runs [Run], HUD click not firing a gameplay action.
Candidate references (unverified): Godot docs "Saving games", "Runtime file loading and saving", "InputEvent"; Maaack template options menu; any well-maintained Godot 4 save addon found during research.
Agent trial task text: "Add save/load of level progress, collected items and settings (volume, fullscreen, key bindings with remapping UI) that persist between launches."
Output: $R/rp_g_persistence_input.md; code in $R/rp_g_work/.
```

**RP.H Enemy AI and navigation (P16, P17)**
```
[SHARED RULES + ROUND P EXTRA + PATTERN RESEARCH PROTOCOL]
Read first: $R/rp_1_baseline.md, $R/rp_2_references.md, $R/rp_c_fsm_anim.md if done, $R/r2_2_replay.md if present.
Scope: P16 enemy behaviour (patrol/chase/attack/search/return; perception; hysteresis); P17 navigation (NavigationAgent2D/3D, NavigationRegion, AStarGrid2D for grid games, avoidance).
Investigate:
- Plain enum FSM vs LimboAI BT/HSM vs Beehave: install each in 4.7 [Run], build the same enemy, compare LOC, whether the BT data is agent-editable text (.tres?), headless testability, determinism, install friction (LimboAI module vs GDExtension). Produce the R-AI decision rule.
- Perception: Area2D + RayCast2D / PhysicsDirectSpaceState2D.intersect_ray for line of sight; collision masks.
- Hysteresis: separate detect and lose radii; minimum time in state.
- Robust target references (player freed / respawned).
- Per-instance state when behaviours are Resources (local_to_scene).
- Navigation gotchas: first-frame map sync (await a physics frame / NavigationServer map_changed), throttled target updates, velocity_computed with avoidance, AStarGrid2D for tile games.
- Tests: scripted player positions -> expected state sequence; flicker rate at the boundary distance; no detection through walls; no ledge walk-off for platformer patrol; no crash when the player is freed; maze reach / path ratio / stuck detection.
Candidate references (unverified): limbonaut/limboai (demo project); bitbrain/beehave (examples); godot-demo-projects 2d/navigation*, 3d/navigation*; GDQuest steering/AI material (check Godot 4 versions).
Agent trial task text: "Add an enemy that patrols between two points, chases the player when it sees them (not through walls), attacks in range, and returns to patrol after losing them for 3 seconds; navigate around obstacles."
Output: $R/rp_h_ai_nav.md; code in $R/rp_h_work/.
```

**RP.I Combat plumbing: spawning, projectiles, waves, hitboxes, collision layers (P18, P19, P05 combat parts)**
```
[SHARED RULES + ROUND P EXTRA + PATTERN RESEARCH PROTOCOL]
Read first: $R/rp_1_baseline.md, $R/rp_2_references.md, $R/rp_e_levels.md if done.
Scope: P18 spawning / projectiles / waves / pooling; P19 hitbox-hurtbox, damage, knockback, i-frames, the collision layer/mask matrix.
Investigate:
- Spawning into a level container vs under the shooter; lifetime and VisibleOnScreenNotifier cleanup; when pooling is warranted (measure instancing cost in 4.7 [Run]) vs premature.
- Wave and spawn tables as Resources.
- Damage-once semantics (area_entered + per-target cooldown vs per-frame overlap).
- A digest that prints the named layer/mask matrix and a lint that compares it with a spec table; unnamed bits in use.
- Physics-frame ordering pitfalls (monitoring changes during callbacks: set_deferred).
- Tests: 600 frames of continuous fire -> bounded count, zero orphans; projectile path unaffected by shooter motion; damage applied exactly once per contact; i-frames honoured.
Candidate references (unverified): godot-demo-projects (2d shooter / bullet demos, e.g. 2d/bullet_shower); GDQuest hitbox/hurtbox material; KidsCanCode recipes on shooting/projectiles.
Agent trial task text: "Give the player a gun that fires projectiles, add enemy waves defined as data, and implement damage with knockback and invulnerability frames for both player and enemies."
Output: $R/rp_i_combat.md; code in $R/rp_i_work/.
```

**RP.J UI, HUD and menus layout (P21)**
```
[SHARED RULES + ROUND P EXTRA + PATTERN RESEARCH PROTOCOL]
Read first: $R/r1_7_visual.md, $R/rp_1_baseline.md, $R/rp_2_references.md.
Scope: P21 HUD and menu layout: CanvasLayer, Containers, anchors, Theme resources, stretch mode/aspect, resolution independence, gamepad focus navigation, signal-driven HUD updates.
Investigate:
- Does Control layout compute correctly under --headless (no renderer), so numeric layout checks can run without xvfb? [Run both]
- Build a layout checker: run a UI scene at 1280x720, 1920x1080, 2560x1080 and 800x1280 (window size via --resolution or Window.size); report controls outside the viewport, overlapping siblings, clipped labels (get_minimum_size vs size), and the per-node theme override count.
- Odiff baseline flow per R1.7, with human approval.
- Theme authoring as a .tres the agent can edit in text.
- Focus neighbours for gamepad navigation.
- Which UI tasks need the human (look) and what the artefact is (screenshot grid of 4 resolutions).
Candidate references (unverified): godot-demo-projects gui/* demos (e.g. gui/multiple_resolutions, gui/theming_override); Maaack template menus; docs "Size and anchors", "Containers", "Multiple resolutions".
Agent trial task text: "Build a HUD (health bar, score, ammo, pause button) and a main menu + options menu that look right at 720p, 1080p, ultrawide and portrait, and work with a gamepad."
Output: $R/rp_j_ui.md; code in $R/rp_j_work/.
```

**RP.K Inventory and data-driven content (P22, P23)**
```
[SHARED RULES + ROUND P EXTRA + PATTERN RESEARCH PROTOCOL]
Read first: $R/rp_1_baseline.md, $R/rp_2_references.md, $R/r2_3_architecture.md if present, $R/rp_g_persistence_input.md if done.
Scope: P22 inventory (item definitions, stacking, equipment slots, drag/drop UI, save); P23 data-driven content (enemies, items, waves, levels defined as Resources).
Investigate:
- ItemData extends Resource with typed @export fields; shared-resource mutation pitfalls (duplicate() / local_to_scene).
- An Inventory model (RefCounted/Resource) with a changed signal, separate from the UI view; drag/drop via _get_drag_data/_can_drop_data/_drop_data; saving by item id.
- GLoot vs a minimal custom model: LLM-friendliness and test coverage.
- A validator script for all .tres of a given class (ranges, required refs, unique ids).
- A "data-only" agent task: add a new enemy/item without touching .gd (does the agent comply, and with what technique?).
- Tests: model unit tests; a random-op model<->view property test; save round-trip.
Candidate references (unverified): peter-kish/gloot; GDQuest inventory material; Godot docs "Resources".
Agent trial task text: "Add an inventory: items defined as data, stackable consumables, an equipment slot, drag-and-drop UI, saved with the game. Then add a new item type 'fire potion' without changing any code."
Output: $R/rp_k_inventory_data.md; code in $R/rp_k_work/.
```

---

### Synthesis prompts

**RP.Z1 Pattern pack assembly**
```
[SHARED RULES + ROUND P EXTRA]
Read first: all $R/rp_*.md; $R/r2_6_claude_code.md; $R/r3_1_summary.md if done (else $R/r2_1_core_harness.md).
Task: Assemble the pattern pack into $R/rp_z1_pack/ as a drop-in for the R3.1 deliverable:
- .claude/skills/godot-patterns/SKILL.md: an index of <=80 lines (pattern -> card -> reference -> check id) + patterns/Pxx_*.md cards, consolidated from the topic agents' drafts.
- tools/harness additions: `h pattern-check [Pxx|all]` (<=15 lines of output), `h ref Pxx`, `h new level|enemy|item|ui-screen`, `h digest --project`.
- tools/refs/refs.yaml + a fetch script (pinned commits).
- The game template (from RP.F).
- test/patterns/ + scenarios/patterns/ (visible tests).
- hidden_tests/ (parameter/level variants), kept outside the pack for RP.Z2.
- A CLAUDE.md "Game architecture" block + the R-SCALE tier line.
- A Stop-hook JSON that runs pattern-check for the patterns touched (per R2.6).
Verify: every check passes on the reference implementations [Run]; every trap recorded by the topic agents is caught by at least one check (a trap-detection matrix).
Output: $R/rp_z1_pack.md: file tree, install steps, trap matrix, total runtime, gaps (weak tests, human-gated items).
```

**RP.Z2 Pattern benchmark (extends R3.2)**
```
[SHARED RULES + ROUND P EXTRA]
Read first: $R/r3_2_eval.md, $R/rp_1_baseline.md, $R/rp_z1_pack.md, $R/rp_0_mcp_handson.md.
Task: Build GodotPatternBench in $R/rp_z2_work/ by extending R3.2's runner.
Tiers:
  T1 = 10 single-pattern tasks on the template;
  T2 = 6 integrate-into-messy-project tasks (start from the RP.1 output projects);
  T3 = 2-4 vertical-slice compositions (C1), from blank and from the template.
Conditions:
  A plain Claude Code + Godot binary;
  B core harness (C1-C7);
  C B + pattern pack;
  C-ref (no reference library);
  C+mcp (only if RP.0 recommends adoption).
Scoring is automatic, done by the orchestrator, never by the agent: h check clean; HIDDEN acceptance variants pass; structural lint score; no regressions; plus tokens, wall time, turns and interventions, as a CSV.
Pilot: 4 tasks x {A, C} x 2 runs with claude -p [Run]; report n honestly.
Prepare (do not run) the human blind-preference kit for 5 feel tasks: anonymised --write-movie clips from an identical input script, plus a scoring sheet (pairwise + 1-5 "would ship").
Proposed success bar: C beats A by >=25 pp on hidden pass overall and >=15 pp on T3, and C >= A on human preference. Keep the reference library only if C-ref loses >=10 pp.
Output: $R/rp_z2_bench.md: design, cost/time estimate, pilot table, validity threats (overfitting to visible tests, variance, leakage), go/no-go.
```

---

## P4. Dependencies and scheduling

```
Wave P0, in parallel with Round 1 (needs only the Godot binary):
   RP.0 MCP hands-on   (run INSTEAD of R1.2 if R1.2 has not started; then R2.2 and R2.6 read rp_0)
   RP.1 baseline study (ideally after R1.1, for exact CLI commands; can start immediately)
   RP.2 reference census
Wave P1, after RP.1 + RP.2 (+ the noted Round 1/2 files where present; each prompt falls back to stand-ins):
   RP.A 2D controller  ← R2.4 (or R1.8)
   RP.B 3D controller
   RP.D camera/juice   ← R1.7
   RP.E levels         ← R1.4, R2.1
   RP.G persistence/input
   RP.I combat
   RP.J UI             ← R1.7
   RP.K inventory/data ← R2.3
Wave P2, after their partner from P1 (they can start early and read partial results):
   RP.C FSM/animation ← RP.A
   RP.F full game     ← RP.E, R2.2
   RP.H AI/nav        ← RP.C, R2.2
Wave P3:
   RP.Z1 pack  ← all RP.*, R2.6 (+R3.1)
   RP.Z2 bench ← RP.Z1, R3.2
```

Orchestrator notes:
- **Throttle the topic agents by RP.1 results.** Run the patterns RP.1 ranks highest at full depth, and drop sections 3 and 5 (agent trials) for the lowest-ranked ones to save budget.
- **Shared clones.** RP.2 leaves clones in `scratchpad/dl/refs/`. Tell topic agents to reuse them, not re-clone.
- **Nested agent trials are the main cost.** Each topic agent runs at least 3 `claude -p` trials (2 baseline + 1 improved). Cap turns and time.
- **Small amendments to existing prompts** (no rewrite):
  - R2.2 and R2.6 "Read first": add `$R/rp_0_mcp_handson.md`.
  - R2.4: "align metric names with RP.A/RP.D".
  - R3.1: "include `$R/rp_z1_pack/` and the Game-architecture CLAUDE.md block; tier B/C adoption".
  - R3.2: "RP.Z2 extends this".
- **Human decisions after Wave P0:**
  - project tier (jam/small/large),
  - target genre(s), to prune RP.B vs RP.A and RP.H vs RP.K,
  - whether to adopt an MCP (RP.0),
  - whether to base on an existing template (RP.F),
  - addon adoption (LimboAI / Beehave / Phantom Camera / GLoot),
  - initial feel targets, or "use RP.A/RP.D defaults".

## P5. Act now (before Round P finishes)
1. Put a short "Game architecture" conventions block and an explicit project tier into today's CLAUDE.md:
   - only a SceneManager changes scenes,
   - the player is spawned by the game,
   - spawned entities go into a level container,
   - tunables live in `.tres`,
   - named collision layers,
   - InputMap actions only,
   - versioned JSON saves,
   - UI = Containers + Theme,
   - gameplay drives animation.
2. Rule: **no pattern is done without a scenario that proves it.** The agent shows measured coyote/apex numbers, the flow loop and the save round-trip; it does not claim them.
3. Start games from a template with the flow already working, not from scratch. Composition is the expected worst case **[U, RP.1 to confirm]**.
4. Point the agent at godot-demo-projects (pinned 4.7-compatible commit) before it implements a pattern.
