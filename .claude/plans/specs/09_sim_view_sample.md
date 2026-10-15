# 09 Simulation/view template, project template and sample game (A9, planner P9; absorbs R2.3)

Status: spec v1, 2026-10-15, Opus planner P9. Conforms to `00_contract.md` ("C §x"); deviations in §8.3. Uses verbs
of 01-05 as specified there and of 06/07 as plan §3.2 defines them. Tags: [Run] verified in §3.5 spikes (Godot
4.7.stable.official.5b4e0cb0f, scratchpad `a9/`), [U] unverified.

## 1. Purpose and failure modes covered
A9 adds no verb. It ships GDScript that the verbs act on: (a) `templates/sim_view/`, a node-free simulation core
(`apply(world, cmd) -> events`, stable int ids, versioned snapshots) plus a view core that reconciles from events
and rebuilds from a snapshot; (b) `templates/project/`, a new-project template with the determinism settings,
named layers, InputMap actions and the "small" tier autoload set; (c) `sample/`, a two-scene game (D2) that is the
dogfood of A2 (every scene generated), A4 (tests), A5 (scenarios), A6 (shots) and A7 (traces).
- **R1.6 sim/view split**: rules in RefCounted under `res://sim` (A3 `lint.sim-node` and `lint.det-*` at error
  severity there), commands in through `CommandBus`, events out, view = disposable nodes keyed by int id.
- **R1.8 determinism**: one seeded RNG inside the world, saved as seed+state; fixed ticks; physics-mode tweens; no
  wall clock in sim; the 64-bit RNG state is lossy through JSON numbers [Run S2], so the codec stores it as a string.
- **Lossy saves (P13)**: JSON numbers come back as float; typed `int` fields silently truncate `3.5` -> 3 and
  untyped dicts keep `2.0` [Run S3]. A strict codec (`SimCodec`) rejects non-integral values; round-trip is
  checked by text equality, not by `==` alone.
- **rp_1 traps**: (1) scene-change guard that drops requests (P10, D7) -> `SceneManager.goto` never drops;
  (2) claimed-but-untested timing windows (P01, D2) -> coyote/buffer/apex are pure-motor tests and scenarios;
  (3) gameplay bound to `ui_*` or code-registered actions (P15, D8) -> named actions in project.godot only.
- **P01, P08, P10, P11** (addendum rows): tunables in `.tres`, asymmetric gravity, coyote/buffer, fps-independent;
  levels are generated scenes with Spawn/Exit, the player is spawned by the game; one SceneManager; <= 3 game
  autoloads besides the 3 dormant harness autoloads.
- **Solium/Cronin view rules**: events carry end state; the view snaps to it after animating, so a missed or wrong
  handler cannot leave the view wrong (snap-to-end); rejections are events (problems and events unified).

## 2. Interfaces

### 2.1 Verbs used (all from other areas; A9 adds none)
`h scene-gen --force sample/specs/*.scene.json` (A2) builds every sample scene. `h check`, `h lint`, `h test`,
`h run [--twice|--record]`, `h digest`, `h shot`/`h baseline propose` (A6), `h trace` (A7) must PASS on the sample.
Rule ids: the `sim.` prefix (C §2.7) stays unused in v0; A9 relies on `lint.sim-node`, `lint.det-*` (A3),
`run.*` (A5), `test.*` (A4).

### 2.2 Sim core (`templates/sim_view/sim/`, copied verbatim to `sample/sim/core/`)
```gdscript
class_name SimThing extends RefCounted       # sim_thing.gd
var id: int = 0                              # assigned by SimWorld.spawn; never reused
var kind: String = ""
func to_dict() -> Dictionary                 # {"id", "kind"} merged with _fields_to_dict()
func load_dict(d: Dictionary) -> Error       # strict (SimCodec); then _fields_from_dict(d)
func _fields_to_dict() -> Dictionary         # virtual, default {}
func _fields_from_dict(d: Dictionary) -> Error   # virtual, default OK

class_name SimWorld extends RefCounted       # sim_world.gd
var tick: int = 0                            # turns (turn-based) or ticks (real-time) applied by the rules
var next_id: int = 1
var things: Dictionary[int, SimThing] = {}
var rng := RandomNumberGenerator.new()       # the ONLY randomness rules may use
var last_error: String = ""                  # set by load_dict on failure: "<json pointer>: <what>"
func setup(seed: int) -> void                # rng.seed = seed (resets state); tick 0; next_id 1; things {}
func spawn(thing: SimThing) -> int           # thing.id = next_id; next_id += 1; store; return id
func despawn(id: int) -> bool
func get_thing(id: int) -> SimThing          # null if absent
func has_thing(id: int) -> bool
func ids() -> Array[int]                     # ascending; the only iteration order rules and views may use
func to_dict() -> Dictionary                 # §2.5
func load_dict(d: Dictionary) -> Error       # OK | ERR_INVALID_DATA (schema, version, type, missing key)
func clone() -> SimWorld                     # same script, load_dict(to_dict()); previews and AI lookahead
func state_hash() -> String                  # JSON.stringify(to_dict(), "", true, true).sha256_text()
func _harness_state() -> Dictionary          # == to_dict() (A5 entity protocol)
func schema_name() -> String                 # virtual, default "sim.world"
func schema_version() -> int                 # virtual, default 1
func migrate(d: Dictionary, from_version: int) -> Dictionary   # virtual; default returns d unchanged
func _make_thing(kind: String) -> SimThing   # virtual factory used by load_dict; default SimThing.new()
func _data_to_dict() -> Dictionary           # virtual world-level fields -> "data"
func _data_from_dict(d: Dictionary) -> Error # virtual

class_name SimRules extends RefCounted       # sim_rules.gd
func commands() -> PackedStringArray         # virtual: command types this rules object handles
func validate(world: SimWorld, cmd: Dictionary) -> String      # virtual: "" ok, else a reason code
func apply(world: SimWorld, cmd: Dictionary) -> Array          # events (Array of Dictionary)
    # apply = validate first; on a reason returns [{"type":"rejected","cmd":<type>,"reason":<code>}] and the world
    # is unchanged (state_hash equal); else _execute(world, cmd). Unknown type -> reason "unknown_command".
func _execute(world: SimWorld, cmd: Dictionary) -> Array       # virtual; mutates, returns events

class_name SimCodec extends RefCounted       # sim_codec.gd; static helpers, all return null + set err on failure
static func int_of(d: Dictionary, key: String, err: Array) -> Variant      # int or float with no fraction -> int
static func str_of(d, key, err) -> Variant ; static func bool_of(d, key, err) -> Variant
static func cell_of(d, key, err) -> Variant  # [x, y] ints -> Vector2i ; static func cell_to(v: Vector2i) -> Array
static func int_dict_of(d, key, err) -> Variant   # {"k": int} with every value strict-int
static func big_to_str(v: int) -> String ; static func str_to_big(s: String) -> int   # 64-bit exact (RNG)
    # err: Array[String] collector; message "<key>: expected int, got 3.5"

class_name SimSnapshot extends RefCounted    # sim_snapshot.gd
static func to_text(world: SimWorld) -> String     # JSON.stringify(to_dict(), "\t", true, true) + "\n"
static func from_text(text: String, into: SimWorld) -> Error
    # parse (ERR_PARSE_ERROR); version < into.schema_version(): into.migrate(d, v) stepwise; version > current or
    # schema_name differs: ERR_INVALID_DATA; then into.load_dict(d). into.last_error explains every failure.
static func save_file(world: SimWorld, path: String) -> Error   # write path+".tmp", then DirAccess.rename_absolute
static func load_file(path: String, into: SimWorld) -> Error
```
Event convention: a Dictionary with `"type"` (snake_case String) and plain-data payload (int, String, bool,
`[x, y]` cells); every event that changes something a view shows carries the **end state** (`"to"`, `"hp"`).
Command convention = A5 CommandBus: `{"type", "target"?: "<int id as string>", "value"?}`.

### 2.3 View core (`templates/sim_view/view/`, copied verbatim to `sample/view/core/`)
```gdscript
class_name ThingView extends Node2D          # thing_view.gd
var thing_id: int = 0
func sync_from(thing: SimThing) -> void      # virtual: snap every shown fact to the thing's state, no animation
func digest() -> Dictionary                  # virtual; default {"id", "pos": [roundi(x), roundi(y)], "visible"}

class_name SimView extends Node2D            # sim_view.gd
signal events_applied(count: int)
var world: SimWorld                          # read-only by contract: views never write to it (AC-09.14)
func bind(w: SimWorld) -> void               # world = w; rebuild()
func apply_events(events: Array) -> void     # for each: _on_event(ev) (animation only); then _reconcile():
    # free views whose id is not in world.ids(); create views for new ids; sync_from() every remaining view
func rebuild() -> void                       # free all thing views; one _make_view() per world.ids(); sync_from
func view_of(id: int) -> ThingView
func view_digest() -> Dictionary             # {"t<id>": view.digest()} for every view, keys sorted
func finish_animations() -> void             # every running tween of the view jumps to its end
func _make_view(thing: SimThing) -> ThingView   # virtual
func _on_event(ev: Dictionary) -> void       # virtual; tweens via create_tween().set_process_mode(TWEEN_PROCESS_PHYSICS)

class_name SimHost extends Node              # sim_host.gd: the only glue between input, CommandBus, sim, view
@export var view: SimView
var world: SimWorld
var rules: SimRules
signal events(events: Array)
func start(w: SimWorld, r: SimRules) -> void
    # Harness.register("world", w); CommandBus.handle(t, _handle) for t in r.commands();
    # CommandBus.set_resolver(func(t): t.is_valid_int() and world.has_thing(t.to_int())); view.bind(w)
func submit(cmd: Dictionary) -> Array        # = CommandBus.submit(cmd); input code calls ONLY this
func save_to(path: String) -> Error          # SimSnapshot.save_file
func load_from(path: String) -> Error        # into a fresh world of the same script; on OK swap + view.bind()
```
`_handle(cmd)` = `rules.apply(world, cmd)`, then `view.apply_events(evs)`, emit `events`, return `evs`.

### 2.4 Project template (`templates/project/`) and the "small" tier
Files: `project.godot`, `harness.toml`, `autoloads/scene_manager.gd`, `.gitignore` (`.godot/`, `.harness/`,
`addons/gdUnit4/`, `addons/harness/`), `README.md` (<= 30 lines: folder layout and the §2.8 rules).
`project.godot` keys (tests read them as text):
| Key | Value |
|---|---|
| `config_version` / `config/features` | `5` / `PackedStringArray("4.7")` |
| `physics/common/physics_ticks_per_second` | `60` |
| `physics/common/physics_jitter_fix` | `0.0` |
| `rendering/renderer/rendering_method` (+ `.mobile`) | `"gl_compatibility"` |
| `display/window/stretch/mode` | `"canvas_items"` |
| `layer_names/2d_physics/layer_1..6` | `world`, `player`, `enemy`, `hazard`, `pickup`, `trigger` |
| `[input]` | `move_left`, `move_right`, `move_up`, `move_down`, `jump`, `confirm`, `cancel`, `pause`: physical keys (A/D/W/S + arrows, Space, Enter, Escape, Escape/P) and a joypad event each, written by the engine (ProjectSettings.save) not by hand |
| `[autoload]` | `Harness`, `Rng`, `CommandBus` (`*res://addons/harness/<snake>.gd`, A5) then `SceneManager="*res://autoloads/scene_manager.gd"` |
Tier "small" (D5): at most 3 **game** autoloads (SceneManager plus up to 2 single-purpose ones, e.g. Settings,
Save); the 3 harness autoloads are dormant outside `h run` and do not count. `harness.toml`: `[harness]` with
`tick_rate = 60`, `sim_dirs = ["res://sim"]`, `test_dir = "res://tests"`, defaults otherwise (C §2.6).
```gdscript
# autoloads/scene_manager.gd (extends Node; no class_name; P10)
signal transition_started(path: String)
signal transition_finished(path: String)
@export var fade_ticks: int = 12             # physics ticks per half fade; tween in TWEEN_PROCESS_PHYSICS
func set_slot(slot: Node) -> void            # scenes are swapped as the only child of slot (no change_scene_to_*)
func goto(path: String) -> void              # NEVER drops: while busy, stores path as pending (latest wins) and
                                             # runs it right after the current transition finishes
func is_busy() -> bool ; func current_path() -> String ; func pending_path() -> String
func stats() -> Dictionary                   # {"requests": int, "completed": int, "dropped": 0 always, "busy": bool}
```
Each finished transition calls `Harness.event("scene_changed", {"path": p})` (no-op when Harness is dormant).

### 2.5 Snapshot format (`SimWorld.to_dict()`; JSON Schema 2020-12; T9 ships it as test data)
```json
{"$id":"harness.sim-snapshot/1","type":"object","additionalProperties":false,
 "required":["schema","version","tick","next_id","rng","things","data"],
 "properties":{"schema":{"type":"string","pattern":"^[a-z][a-z0-9_.]*$"},"version":{"type":"integer","minimum":1},
  "tick":{"type":"integer","minimum":0},"next_id":{"type":"integer","minimum":1},
  "rng":{"type":"object","additionalProperties":false,"required":["seed","state"],
   "properties":{"seed":{"type":"string","pattern":"^-?\\d+$"},"state":{"type":"string","pattern":"^-?\\d+$"}}},
  "things":{"type":"object","propertyNames":{"pattern":"^t[1-9][0-9]*$"},"additionalProperties":{"type":"object",
   "required":["id","kind"],"properties":{"id":{"type":"integer","minimum":1},"kind":{"type":"string"}}}},
  "data":{"type":"object"}}}
```
Keys `t<id>` make A5 paths readable (`world.things.t3.hp`). `things.t<id>.id == <id>`, every id < `next_id`.

### 2.6 Sample: tactics (turn-based, full split)
`TacticsWorld extends SimWorld` (`sample/sim/tactics/tactics_world.gd`): `schema_name() "sample.tactics"`,
`schema_version() 1`; data fields `width 8`, `height 8`, `team_to_move` (0|1), `wave` (int), `blocked`
(`[[3,3],[4,4]]`), `stats` (`{"kills": int, "spawned": int}`, an int dict). `static func create(seed: int) ->
TacticsWorld`: ids 1-3 team 0 at (0,1) (0,3) (0,5); ids 4-6 team 1 at (7,2) (7,4) (7,6); `team_to_move` 0.
`Unit extends SimThing` (`unit.gd`, kind `"unit"`): `team`, `cell: Vector2i`, `hp` 10, `max_hp` 10, `atk` 3,
`move` 3, `acted: bool`. `TacticsRules extends SimRules` (`tactics_rules.gd`) commands and reasons:
| type | target / value | Effect, events | Reasons (rejected, world unchanged) |
|---|---|---|---|
| `move` | unit id / `[x, y]` | `unit_moved {id, from, to}`; sets acted | `no_such_unit`, `not_your_turn`, `already_acted`, `out_of_bounds`, `blocked` (blocked or occupied), `out_of_range` (Manhattan > move), `bad_args` |
| `attack` | unit id / target unit id (int) | damage = atk + rng.randi_range(0, 1); `unit_attacked {id, target, damage}`, `unit_damaged {id, amount, hp}`, at hp <= 0 `unit_died {id}` + despawn, `stats.kills += 1` | as move, plus `not_adjacent`, `friendly_fire` |
| `end_turn` | - | `tick += 1`, flip `team_to_move`, clear `acted`; empty team -> respawn 3 units at its start cells (next free cell down the column), `wave += 1`, `stats.spawned += 3`, `wave_started {team, wave}` + `unit_spawned {id, team, cell, hp}`; then `turn_ended {tick, team_to_move}` | - |
| `ai_turn` | - | units of `team_to_move` in id order: attack the adjacent enemy with lowest hp (tie: lowest id), else move to the reachable free cell nearest the nearest enemy (ties: `rng`), then attack if adjacent; then `end_turn` | - |
| `autoplay` | - / n (1..100000) | n x `ai_turn`; events concatenated | `bad_args` |
A rejection leaves the world byte-identical (no counters); scenarios count rejections with A5's built-in metric
`events.rejected`. Invariants after any command: no two units share a cell; cells in bounds and
not blocked; `0 < hp <= max_hp`; ids unique and < `next_id`.
View: `TacticsView extends SimView` (`sample/game/tactics/tactics_view.gd`, 32 px cells), `UnitView extends
ThingView` (`unit_view.gd`; digest adds `"team"`, `"hp"` label text); `TacticsHost extends SimHost`
(`tactics_host.gd`): `_ready` -> `start(TacticsWorld.create(seed), TacticsRules.new())`, seed = `Rng.get_seed()`;
input via actions `move_*` (cursor), `confirm`, `cancel` -> `submit()` only; debug command `snapshot_roundtrip`
(save to `user://tactics_rt.json`, load back, event `snapshot_roundtrip {equal: bool}`).
Scenes: `res://scenes/tactics/tactics.tscn` (root `Node2D` "Tactics" + `TacticsHost` "Host" + `TacticsView` "View",
`Host.view` = `{"$node": "View"}`), `res://scenes/tactics/unit_view.tscn`.

### 2.7 Sample: platformer (real-time physics, motor split only; §2.8 rule 2)
```gdscript
class_name MovementTuning extends Resource   # res://tuning/movement_tuning.gd; values = rp_1 T1 targets
@export var max_speed := 220.0 ; @export var accel_time := 0.10 ; @export var decel_time := 0.08   # px/s, s
@export var air_control := 0.65 ; @export var jump_height := 48.0 ; @export var time_to_apex := 0.38  # -, px, s
@export var fall_gravity_mult := 1.6 ; @export var jump_cut_mult := 0.5 ; @export var max_fall_speed := 600.0
@export var coyote_time := 0.10 ; @export var buffer_time := 0.10                                     # s

class_name PlayerMotor extends RefCounted    # res://sim/platformer/player_motor.gd (pure, sim scope)
var tuning: MovementTuning ; var tick_rate: int = 60
var velocity := Vector2.ZERO ; var ticks_since_floor: int = 0 ; var buffer_left: int = 0
var rising: bool = false ; var jumps: int = 0 ; var last_jump_coyote := false ; var last_jump_buffered := false
func gravity() -> float                      # 2 h / t^2 ; fall uses * fall_gravity_mult
func jump_velocity() -> float                # -2 h / t
func coyote_ticks() -> int                   # roundi(coyote_time * tick_rate)   (6 at 60 Hz)
func buffer_ticks() -> int                   # roundi(buffer_time * tick_rate)   (6 at 60 Hz)
func step(axis: float, jump_pressed: bool, jump_held: bool, on_floor: bool) -> Vector2
    # one physics tick BEFORE move_and_slide: horizontal accel/decel toward axis*max_speed; coyote: a jump is
    # allowed while ticks_since_floor <= coyote_ticks(); buffer: a press is remembered buffer_ticks(); jump cut:
    # releasing while rising multiplies velocity.y by jump_cut_mult once; half the tick's gravity is applied here
    # (midpoint integration, §3.3); returns the velocity to move with
func post_move(actual_velocity: Vector2, on_floor: bool) -> void   # second gravity half; contact feedback
func to_dict() -> Dictionary
```
`Player extends CharacterBody2D` (`res://game/platformer/player.gd`, class_name `Player`): `@export var tuning:
MovementTuning`; `_physics_process`: axis from `Input.get_axis("move_left", "move_right")`, jump from
`is_action_just_pressed/pressed("jump")`, `velocity = motor.step(...)`, `move_and_slide()`, `motor.post_move(...)`;
registers Harness entity `"player"`; `_harness_state()` = `{position, velocity, on_floor, jumps, apex_px,
coyote_jumps, buffered_jumps}` where `apex_px` = takeoff y minus the minimum y of the last jump (float px).
Events: `jumped {coyote, buffered}`, `landed`. `PlatformerGame` (`res://game/platformer/platformer_game.gd`,
root of `res://scenes/platformer/platformer_game.tscn` with `%LevelSlot`, `%Fade` ColorRect on a CanvasLayer):
calls `SceneManager.set_slot(%LevelSlot)`, `goto("res://scenes/platformer/level_1.tscn")`; on
`transition_finished` instantiates `res://scenes/platformer/player.tscn` at the level's `%Spawn`; a level's `%Exit`
(Area2D, layer `trigger`, mask `player`) calls `SceneManager.goto(<level's next_level export>)`. Entity `"game"`:
`{"level": <scene file stem>, "levels_completed": int, "sm": SceneManager.stats()}`. Debug command `goto_level`
(value: stem) -> `SceneManager.goto(...)`. `level_2` has `next_level = ""` (end).
Levels `level_1.tscn`, `level_2.tscn` (root `Node2D` + `level.gd`, `@export var next_level: String`): StaticBody2D
blocks with `$new` RectangleShape2D (`collision_layer` `$layers ["world"]`), ColorRect visuals, `%Spawn` Marker2D,
`%Exit`, one `Hazard` Area2D (layer `hazard`). level_1: flat floor >= 600 px right of Spawn, a 64 px ledge drop at
x = Spawn + 320, Exit at x = Spawn + 560. `player.tscn`: CharacterBody2D + player.gd (`tuning` =
`{"$res": "res://tuning/player_movement.tres"}`), CollisionShape2D (capsule), Polygon2D visual, Camera2D
(`process_callback` physics).
Data files (hand-written property lines are allowed for data `.tres`, §8.3 D-3): `res://tuning/player_movement.tres`
(MovementTuning, the defaults above), `res://tuning/feel_targets.tres` (A7 FeelTargets schema; v0 metrics and
ranges: apex 44-52 px, time to apex 0.35-0.41 s, ticks to max speed 3-8, coyote 5-7 ticks, buffer 5-7 ticks;
`approved_by = "provisional-default"`; metric names per A7, §8.4).
Menu: `res://scenes/main.tscn` (main scene; root `Control` + `main.gd`, two Buttons "Platformer"/"Tactics" whose
`pressed` -> `SceneManager.goto`; `%Slot` for the game scenes).

### 2.8 Decision rules: when to split (text A8 puts in the CLAUDE.md Game-architecture block, <= 12 lines)
1. Turn-based or discrete rules (board, cards, tactics, inventory, economy, quests, dialogue state): full split.
   State in `res://sim` RefCounted, commands in, events out, view reconciles; tests are sim tests.
2. Real-time on engine physics (platformer, physics props): no full split. Keep bodies in nodes; move the per-tick
   decisions (accel, jump windows, cooldowns, AI choice) into a pure motor `step(state, input, contacts)` under
   `res://sim`, tunables in a `.tres`; verify with motor tests + `h run` scenarios on the real scene.
3. Real-time without engine collisions (waves, economy, bullet patterns, RTS orders): split with a fixed-tick
   `apply(world, {"type": "tick", "inputs": ...})`; the view interpolates.
4. Split from day one if the game needs any of: save mid-match, undo, previews, AI lookahead, replays, netcode.
   Retrofitting determinism is the Monster Train lesson; for a throwaway prototype rule 2 is enough.
5. Never in sim: UI layout, camera, particles, audio, animation, scene changes. If rule code wants `get_tree()`,
   a signal from a node or a NodePath, it is in the wrong layer.
6. One iteration order (`ids()`), one RNG (`world.rng`, saved), int ids, no floats in turn-based state.

## 3. Design

### 3.1 Files (B9a: templates + tactics sim, no scenes; B9b: scenes, platformer, scenarios, baselines)
- B9a: `templates/sim_view/sim/{sim_thing,sim_world,sim_rules,sim_codec,sim_snapshot}.gd`,
  `templates/sim_view/view/{thing_view,sim_view,sim_host}.gd`, `templates/sim_view/README.md` (<= 40 lines: how to
  copy, rename, add a command); `templates/project/*` (§2.4); `sample/project.godot`, `sample/harness.toml`,
  `sample/autoloads/scene_manager.gd`, `sample/sim/core/*` and `sample/view/core/*` (byte copies),
  `sample/sim/tactics/{tactics_world,unit,tactics_rules,tactics_ai}.gd`, `sample/sim/platformer/player_motor.gd`,
  `sample/tuning/{movement_tuning.gd,player_movement.tres}`, `sample/tests/sim/{test_sim_core,test_tactics_rules,
  test_snapshot,test_player_motor}.gd`.
- B9b: `sample/game/{main.gd,tactics/{tactics_host,tactics_view,unit_view}.gd,platformer/{player,platformer_game,
  level,exit,hazard}.gd}`, `sample/specs/<scene stem>.scene.json` (one per scene: main, tactics, unit_view,
  platformer_game, player, level_1, level_2), the generated `sample/scenes/**.tscn`, `sample/tuning/feel_targets.tres`,
  `sample/scenarios/**` (§3.4) + `sample/scenarios/tactics/autoplay.golden.json` (recorded with `h run --record` on
  a temp copy, then copied in), `sample/tests/scenes/{test_tactics_view,test_player_scene,test_scene_manager}.gd`,
  `sample/baselines/**` via `h baseline propose` (A6), `sample/README.md` (<= 40 lines).
- Never committed: `sample/.godot/`, `sample/.harness/`, `sample/addons/{harness,gdUnit4}/` (synced). `.uid`
  files are committed (B5).
- Hook lines (exact text; faults in §5 replace them; each occurs once in its file):
  `sim/tactics/tactics_world.gd`: `var debug_note: String = "" # HOOK-SIM-FIELD` (not in to_dict);
  `sim/tactics/tactics_rules.gd`: `	pass # HOOK-RULES-APPLY` (first line of `_execute`) and
  `	var bonus := world.rng.randi_range(0, 1) # HOOK-DAMAGE-RNG`;
  `sim/tactics/tactics_world.gd`: `	var st = SimCodec.int_dict_of(d, "stats", err) # HOOK-STATS-LOAD`;
  `sim/core/sim_world.gd` (and the template): `		"version": schema_version(), # HOOK-VERSION`;
  `view/core/sim_view.gd` (and the template): `	_reconcile() # HOOK-VIEW-RECONCILE`;
  `game/tactics/tactics_view.gd`: `	pass # HOOK-VIEW-EVENT` (first line of `_on_event`);
  `autoloads/scene_manager.gd` (and the template): `		_pending = path # HOOK-PENDING`;
  `game/platformer/player.gd`: `	var axis := Input.get_axis("move_left", "move_right") # HOOK-INPUT-AXIS`;
  `sim/platformer/player_motor.gd`: `	return roundi(tuning.coyote_time * tick_rate) # HOOK-COYOTE`.

### 3.2 Algorithms
- **Validate then mutate**: `SimRules.apply` never mutates on a rejection; `_execute` may assume a valid command.
  AI and previews run `apply` on `world.clone()` (2 ms per 100 clones of a 6-unit world [Run S1]).
- **Codec**: `to_dict` writes ints as ints, cells as `[x, y]`, RNG seed/state as decimal strings; `load_dict`
  reads only through `SimCodec` (strict int: float allowed only when integral) and collects errors into
  `last_error`; it never partially loads (build into locals, then assign).
- **Hash**: sorted-key full-precision JSON (A5 §2.4 uses the same normalisation), so `state_hash()` equals what A5
  hashes for entity `world` modulo A5's own wrapping.
- **Reconcile / snap-to-end**: `_on_event` only starts physics-mode tweens; `_reconcile()` (end of every
  `apply_events`) creates, frees and `sync_from()`s views from `world`, killing tweens of freed views. So
  `view_digest()` after `finish_animations()` is a pure function of `world`, and equals a fresh `rebuild()`.
- **Motor midpoint gravity**: `v.y += g dt / 2` before the move and again after; apex error vs designer intent is
  0.06 px at 30 Hz and 0.00 px at 60/120 Hz, against 4.1/2.1/1.1 px for plain semi-implicit Euler [Run S4].
- **SceneManager**: state machine idle -> fading_out (fade_ticks) -> swap (free old child, add new, 1 tick) ->
  fading_in (fade_ticks) -> idle; on idle, if `_pending` non-empty, start it. Ticks counted in `_physics_process`;
  the fade tween is physics-mode; `stats().dropped` stays 0 by construction.
- **Input glue**: only named actions; no `ui_*`, no `InputMap.add_action`, no `KEY_*` outside remap code (A3).

### 3.3 Sample `harness.toml` and autoloads
`[harness]` as §2.4; no `[lint]` overrides (sample must PASS A3 defaults, incl. `replay_dirs = ["res://"]`). The
sample's `project.godot` already declares all four autoloads, so `h sync` leaves it byte-identical.

### 3.4 Required scenarios (`sample/scenarios/`, A5 schema; required asserts; builders may add more)
| File | Scene, seed, ticks | Inputs / commands | Required asserts |
|---|---|---|---|
| `platformer/run.json` | platformer_game, 1, 120 | `move_right` strength 1 from tick 31 (after fade-in) | `player.velocity.x` lt 219 @tick 32; ge 219.9 @tick 40; `player.position.x` gt <Spawn x + 100> @tick 90 |
| `platformer/jump.json` | platformer_game, 1, 150 | `jump` at 40 hold 40 | `player.apex_px` between [46, 50] at_end; `player.jumps` eq 1 at_end |
| `platformer/tap.json` | same | `jump` at 40 hold 2 | `player.apex_px` lt 30 at_end; `player.jumps` eq 1 |
| `platformer/level_complete.json` | platformer_game, 1, 900 | `move_right` from 31 to end; `jump` at the ledge as needed | `game.level` eq `"level_2"` at_end; `game.sm.dropped` eq 0 |
| `flow/fade_request.json` | platformer_game, 1, 120 | command `goto_level` value `"level_2"` at tick 3 (inside the first fade-in) | `game.level` eq `"level_2"` at_end; `game.sm.completed` eq 2 at_end |
| `tactics/moves.json` | tactics, 7, 6 | `move` t1 -> [2,1] @2; `move` t4 -> [6,2] @3 (not your turn); `attack` t1 -> 4 @4 (not adjacent) | `world.things.t1.cell` eq [2, 1] at_end; metric `events.rejected` eq 2; metric `events.unit_moved` eq 1 |
| `tactics/autoplay.json` | tactics, 42, 3 | `autoplay` value 1000 @1; `snapshot_roundtrip` @2 | `world.tick` eq 1000 at_end; metric `events.snapshot_roundtrip` eq 1; golden committed |
Every scenario passes `h run --twice`; `autoplay.golden.json` matches on the recording machine class (B7).

### 3.5 Spikes ([Run], scratchpad `a9/proj`, prototype sim of §2.6 in plain RefCounted GDScript)
- **S1 1000 turns.** `ai_turn` x1000 on an 8x8 grid, 8 units, waves: `HASH1000 17374af6df26de46 events=3480
  next_id=230`, identical in 3 separate processes; seed 43 -> `3a42422d84c93279`; 17-37 ms per 1000 turns;
  100 clones via `from_dict(to_dict())` 2-4 ms.
- **S2 RNG through JSON.** First version stored `rng.state` as a JSON number: `rng state=-7005975484781632525`,
  after parse `-7005975484781631488.0` (`exact=false`), so 500 turns + save/load + 500 turns gave
  `e91534f7...` vs straight `a105484e...`. With seed/state as strings (`String.to_int()` exact): round-trip text
  equal, split hash == straight hash. Also: `rng.seed = s` after `rng.state = x` resets state (seed first).
- **S3 JSON types.** `JSON.parse_string` turns every number into float (`typeof(turn) == TYPE_FLOAT`);
  `{"hp":3}` vs `{"hp":3.0}` stringify differently and `==` is false; a typed `var hp: int` silently accepts 3.5
  as 3; an untyped dict copy keeps `{"kills":2.0}`. `str_to_var(var_to_str(d))` keeps types but is not JSON.
- **S4 apex vs integration** (h = 48 px, t = 0.38 s): semi-implicit Euler apex 43.88 / 45.91 / 46.95 px at
  30/60/120 Hz; midpoint 47.94 / 48.00 / 48.00 px, apex tick 12 / 23 / 46.
- **S5 .tres header.** `ResourceSaver.save` of a class_name Resource writes `[gd_resource type="Resource"
  script_class="MovementTuning" format=3]`, one `[ext_resource type="Script" path=... id="1_x"]`, `[resource]`,
  `script = ExtResource("1_x")`, then only non-default props. `ClassDB.class_exists("MovementTuning")` is false, so
  A2's `$new` cannot build script-class resources (hence separate `.tres` + `$res`).

## 4. Acceptance criteria
Layers: [gd] = gdUnit4 suites T9 writes in `tests/gd/a9/`, copied into a B3 copy of `sample/` at
`res://tests/a9/` and run with `h test --project <copy> res://tests/a9/` (they name only §2 classes/methods);
[contract] = `h` verbs on a copy of `sample/` (or of a template) with `assert_contract`; [e2e]; [data] = Python
reading files. "copy" = `sample/` without `.godot/ .harness/ addons/harness/ addons/gdUnit4/`.
- AC-09.1 [data] `sample/sim/core/*.gd` and `sample/view/core/*.gd` are byte-identical to `templates/sim_view/
  {sim,view}/*.gd`; `sample/autoloads/scene_manager.gd` to the template's.
- AC-09.2 [data] `templates/project/project.godot` and `sample/project.godot` have every §2.4 key/value; the 8
  actions each with >= 1 key and 1 joypad event; no `.gd` under `sample/` (excluding `tests/a9`) contains `"ui_`,
  `InputMap.add_action` or `KEY_`; `[autoload]` lists exactly Harness, Rng, CommandBus, SceneManager in that order.
- AC-09.3 [contract] `h check` on a copy: rc 0 PASS (auto-import), wall <= 60 s; `h lint`: rc 0 PASS, 0 findings
  (no warnings either).
- AC-09.4 [contract] Every `.tscn` under `sample/` (outside `addons/`) has exactly one spec in `sample/specs/`
  whose `save` names it; `h scene-gen --force` of all specs (main last) on a copy: rc 0, every check line `OK`, and
  each regenerated scene's `digest.json` (`h digest --json`) equals that of the committed file.
- AC-09.5 [contract] `h digest scenes/platformer/player.tscn` rc 0 and no `more:` stat (fits 40 lines);
  `h digest --project-summary` lists 4 autoloads, 8 actions, `layers-2d_physics: 1=world 2=player 3=enemy 4=hazard
  5=pickup 6=trigger`.
- AC-09.6 [contract] `h test` on a copy (sample's own tests): rc 0, >= 4 sim suites and >= 3 scene suites ran,
  >= 30 tests, 0 orphans, wall <= 90 s.
- AC-09.7 [contract] `h run res://scenarios/ --twice` on a copy: rc 0, `PASS run 7/7 scenarios passed` (or more),
  each §3.4 required assert present in its file (JSON read by the test) and passing in `asserts.json`;
  `tactics/autoplay.json` stat `golden: match`. Wall <= 90 s.
- AC-09.8 [gd] `TacticsWorld.create(42)`, `autoplay` 1000 -> `tick == 1000`; a second world with seed 42 gives the
  same `state_hash()`; seed 43 differs; the run takes <= 2 s inside the test.
- AC-09.9 [gd] Split run: create(42), autoplay 500, `SimSnapshot.to_text` -> `from_text` into a new TacticsWorld,
  autoplay 500 -> hash equals the straight 1000-turn hash (S2).
- AC-09.10 [gd] Round-trip: after 300 autoplay turns, `to_text(w) == to_text(loaded)` (type-strict text), `stats`
  values are `TYPE_INT` after load, `rng.state` equal; `save_file`/`load_file` to `user://a9_rt.json` round-trips
  and leaves no `.tmp` file.
- AC-09.11 [gd] Strict load: text with `"hp": 3.5` -> `ERR_INVALID_DATA`, `last_error` contains `hp`; missing
  `version` -> `ERR_INVALID_DATA`; `version` 2 (newer) -> `ERR_INVALID_DATA`; `schema` `"other"` -> same;
  `"hp": 3.0` loads as int 3; a failed load leaves the target world unchanged (hash before == after).
- AC-09.12 [gd] Migration: a TacticsWorld subclass in the test with `schema_version() 2` and a `migrate` that adds
  a field loads a v1 text; `to_dict().version == 2`.
- AC-09.13 [gd] Rules: each rejection reason of §2.6 (one command each from `create(7)`) returns exactly one
  `rejected` event with that reason and leaves `state_hash()` unchanged; a legal move emits `unit_moved` with
  `to`; attack damage in {3, 4}; a kill emits `unit_died`, despawns, and the id is never reused (next spawn id =
  previous `next_id`); the §2.6 invariants hold after each of 1000 autoplay turns; `ids()` ascending.
- AC-09.14 [gd] View is read-only and rebuildable: `tactics.tscn` via `scene_runner`; host submits `autoplay` 60;
  `finish_animations()`; world hash equal to that of a headless clone that ran the same commands without a view
  (the view never mutates); a second `TacticsView` bound to `world.clone()` has `view_digest()` equal to the live
  one; after `host.load_from()` of an earlier save the digest equals a fresh rebuild.
- AC-09.15 [gd] `apply_events([])` then `_reconcile` behaviour: freeing a unit in the world without any event and
  calling `apply_events([])` removes its view (snap-to-end covers missed events).
- AC-09.16 [gd] Motor, pure: apex over free air (`post_move(v, false)`) within 1 px of `jump_height` at 30, 60 and
  120 Hz; time to apex = `roundi(time_to_apex * rate) +/- 1` ticks; ticks from 0 to `max_speed` on floor =
  `ceili(accel_time * 60) +/- 1` and > 1; a jump press at k ticks after leaving the floor is accepted for
  k <= 6 and refused at k = 7 (60 Hz defaults); a press k ticks before landing jumps on landing for k <= 6, not
  at 7; release after 2 ticks gives apex < 0.5 x hold apex; no second jump in the air.
- AC-09.17 [gd] SceneManager: with a test slot, `goto(A)` then `goto(B)` 3 ticks later and `goto(C)` 5 ticks
  later -> after the transitions `current_path() == C`, `stats().completed == 2` (A, then C; B superseded),
  `dropped == 0`; `goto` while idle starts immediately; `transition_finished` is emitted once per completed path.
- AC-09.18 [gd] Player scene: `scene_runner(platformer_game.tscn)`, after 40 frames `simulate_action_press
  ("move_right")` for 30 frames -> player x increased > 100 px; `jump` press -> `jumps == 1`.
- AC-09.19 [contract] Template smoke: copy `templates/project/` to a temp dir, copy `templates/sim_view/sim` to
  `res://sim/core` and `view` to `res://view/core`, `h sync`, `h check`: rc 0; `h lint`: rc 0 with 0
  `lint.sim-node` and 0 `lint.det-*` findings.
- AC-09.20 [contract] Seeded-fault sanity: `h selftest --area A9` -> rc 0, all must faults CAUGHT, CLEAN-A9-*
  PASS, wall <= 600 s. [slow]
- AC-09.21 [e2e] Fresh clone: `tools/bootstrap.sh` then `h check --project sample`, `h test --project sample`,
  `h run --project sample sample/scenarios/ --twice` all rc 0 (bootstrap is the one allowed writer of
  `sample/.godot`), and `git status --porcelain sample` is empty afterwards.
- AC-09.22 [contract, xvfb] `h shot` of `tactics.tscn` and `platformer_game.tscn` at tick 60 compared with
  `sample/baselines/` (A6 semantics) -> PASS; baselines' meta `approved_by` is `provisional-default`. `h trace
  res://scenarios/platformer/jump.json` (A7) reports every metric of feel_targets.tres and PASSes.
- AC-09.23 [data] `sample/` and `templates/` hold no `.tscn` without a spec (AC-09.4), no `get_tree()`/`Node` use
  under `res://sim` (A3 covers it; this AC checks `h lint` output has no `lint.sim-node`), and game autoloads <= 3.
Untestable automatically (orchestrator review): the §2.8 text is accurate; the sample "reads well" as an example.

## 5. Seeded faults (`fixture = "@sample"`, §8.3 D-1; `must` unless noted; replace ops on §3.1 hook lines)
| ID | Planted | Verb + args | Expect |
|---|---|---|---|
| FAULT-A9-01 | HOOK-SIM-FIELD -> `var debug_ref: NodePath = NodePath("../View") # HOOK-SIM-FIELD` | `lint` | 1 FAIL `tactics_world\.gd:\d+: \[lint\.sim-node\]` |
| FAULT-A9-02 | HOOK-VIEW-EVENT -> `	if world.has_thing(1): world.get_thing(1).set("hp", 99)`; write `tests/a9f/test_view_readonly.gd` (files/) | `test res://tests/a9f/` | 1 FAIL `\[test\.failed\]` |
| FAULT-A9-03 | HOOK-VERSION line replaced by an empty line (sample copy only); write `tests/a9f/test_snapshot_version.gd` | `test res://tests/a9f/` | 1 FAIL `\[test\.failed\]` |
| FAULT-A9-04 | HOOK-RULES-APPLY -> `	var _t = get_tree()` | `lint` | 1 FAIL `tactics_rules\.gd:\d+: \[lint\.sim-node\]` |
| FAULT-A9-05 | HOOK-DAMAGE-RNG -> `	var bonus := Time.get_ticks_usec() % 2 # HOOK-DAMAGE-RNG` | `run res://scenarios/tactics/autoplay.json --twice` | 1 FAIL `\[run\.(nondeterministic\|golden-mismatch)\]` |
| FAULT-A9-06 | HOOK-STATS-LOAD -> `	var st = d["data"]["stats"].duplicate() # HOOK-STATS-LOAD` (floats survive); write `tests/a9f/test_roundtrip.gd` | `test res://tests/a9f/` | 1 FAIL `\[test\.failed\]` |
| FAULT-A9-07 | HOOK-PENDING -> `		return # HOOK-PENDING` (the rp_1 swallow guard) | `run res://scenarios/flow/fade_request.json` | 1 FAIL `\[run\.assert\].*game\.level` |
| FAULT-A9-08 | HOOK-INPUT-AXIS -> `	var axis := Input.get_axis("ui_left", "ui_right") # HOOK-INPUT-AXIS` | `run res://scenarios/platformer/run.json` | 1 FAIL `\[run\.assert\].*player\.velocity\.x` |
| FAULT-A9-09 | HOOK-COYOTE -> `	return 0 # HOOK-COYOTE`; write `tests/a9f/test_coyote.gd` (k sweep against 6 ticks) | `test res://tests/a9f/` | 1 FAIL `\[test\.failed\]` |
| FAULT-A9-10 | HOOK-VIEW-RECONCILE -> `	pass # HOOK-VIEW-RECONCILE`; write `tests/a9f/test_rebuild_digest.gd` | `test res://tests/a9f/` | 1 FAIL `\[test\.failed\]` |
| FAULT-A9-11 | write `sim/tactics/noise.gd` = `extends RefCounted\nfunc f() -> float:\n\treturn randf()\n` | `lint` | 1 FAIL `noise\.gd:3: \[lint\.det-global-rng\] error` |
| FAULT-A9-12 (nice) | HOOK-VIEW-EVENT -> `	create_tween().tween_property(self, "modulate:a", 1.0, 0.2)` | `lint` | 5 WARN `\[lint\.det-idle-tween\]` |
| CLEAN-A9-01 | none | `check` | 0 PASS |
| CLEAN-A9-02 | none | `run res://scenarios/ --twice` | 0 PASS `scenarios passed` |
| CLEAN-A9-03 | none | `test` | 0 PASS |
`max_seconds`: lint 15, run 120, test/check 180 (fresh copy imports + installs gdUnit4). Fault test suites in
`files/` use only §2 APIs and `extends GdUnitTestSuite`. Mutation hints for the verifier: make `SimCodec.int_of`
accept 3.5 (AC-09.11 red); drop `rng.state` from `to_dict` (AC-09.9, 10); store `"tick"` as float (AC-09.10).

## 6. Fixtures needed (T9)
- No new project fixture: the sample is the fixture (D-1). T9 writes `tests/gd/a9/*.gd` (copied into the sample
  copy by a pytest helper in `tests/contract/a9/conftest.py`), `tests/contract/a9/`, `tests/e2e/a9/`, the
  `tests/fixtures/a9/sim_snapshot.schema.json` (§2.5) and the fault suites under `selftest/faults/FAULT-A9-*/files/`.
- Text fixtures in `tests/fixtures/a9/`: `snap_v1.json` (valid create(7) snapshot, hand-derived from §2.6: ids 1-6,
  cells, hp 10, rng seed "7"; the state string is taken from a run, so AC-09.11 uses a loaded-then-edited copy
  instead), `snap_float_hp.json`, `snap_no_version.json`, `snap_v2.json`, `snap_other_schema.json` (edits of a text
  saved in-test are preferred; files only where the test needs a literal).
- Until B9a lands, the [gd] and [contract] tests are red with "no such class"/missing sample (the red check).

## 7. Build order
B9a (parallel with B5/B6, needs A1/A3/A4 green):
1. Sim core + codec + snapshot in `templates/sim_view/sim`, copied to `sample/sim/core`; `sample/project.godot`,
   `harness.toml`, `tests/sim/test_sim_core.gd` -> AC-09.1 (sim part), 11, 12; `h lint` clean.
2. Tactics sim (world, unit, rules, ai) + `test_tactics_rules.gd`, `test_snapshot.gd` -> AC-09.8-10, 13;
   FAULT-A9-01, 04, 06, 11.
3. View core + SceneManager + project template (no scenes) -> AC-09.1, 2, 19.
4. Motor + MovementTuning + `player_movement.tres` + `test_player_motor.gd` -> AC-09.16; FAULT-A9-09.
B9b (after B5 and A2 are green):
5. Specs + `h scene-gen` for unit_view, tactics, player, level_1, level_2, platformer_game, main -> AC-09.3-5.
6. Game scripts (host, view, player, levels, menu) + scene tests -> AC-09.6, 14, 15, 17, 18; FAULT-A9-02, 03, 10.
7. Scenarios + golden (`--record` on a temp copy) -> AC-09.7; FAULT-A9-05, 07, 08; CLEAN-A9-01..03.
8. After B6/B7: baselines (propose), feel_targets.tres, AC-09.22; then AC-09.20, 21, 23.

## 8. Out of scope, open questions, assumptions
### 8.1 Out of scope (v0)
C# template and xunit path (D1; the sim core avoids engine-only types except Vector2i/RandomNumberGenerator, so a
port is mechanical), 3D scene (D2), TileMapLayer levels (P08 via generated TileMapLayer data is A10/RP.E; v0 uses
StaticBody2D blocks), pathfinding in tactics (Manhattan only), networking/rollback, a scrubber UI, settings/remap
screen (P14), audio (P24), pause menu (P12), recording human play into scenarios (A5 v0.1), an `h new` generator.
### 8.2 Open questions [U]
1. A5 open question 4: SceneManager swaps children of a slot instead of `change_scene_to_*`, so the runner's
   `current_scene` never changes; not yet run under `scenario.gd` (S-spike pending for B9b step 6).
2. `Dictionary[int, SimThing]` typed dictionaries with subclasses (`Unit`) assigned: assumed fine on 4.7 [U].
3. Golden `autoplay.golden.json` holds only ints/strings, so it should match across machines (exact), unlike
   physics goldens; untested off this container.
4. gdUnit4 `scene_runner` frame stepping vs physics ticks for AC-09.18 (A4 K12 says action press works headless).
5. Whether A6 can store a `provisional-default` baseline without the human `approve` step (AC-09.22).
### 8.3 Deviations requested (spec reviewer)
- D-1 fault.toml `fixture = "@sample"` = `$HARNESS_REPO/sample` copied like a fixture (excluding `.godot/`,
  `.harness/`, `addons/harness/`, `addons/gdUnit4/`). Reason: the sample is the dogfood target; a duplicate fixture
  would drift. Fallback: the orchestrator snapshots `sample/` into `tests/fixtures/projects/sample_snapshot/` at
  lock time (then faults must be re-locked whenever the sample changes).
- D-2 [gd] suites live in `tests/gd/a9/` but run inside a sample copy at `res://tests/a9/` (copied by the test
  helper), since they need the sample's classes.
- D-3 Data-only `.tres` (tuning, feel targets) may be written as text in the §3.5 S5 shape (header + one script
  ext_resource + `[resource]` property lines); only scenes must come from scene-gen. A8's `.tscn/.tres` hook warns
  once on creation; editing property lines is the normal tuning workflow (A7).
- D-4 Plan §7 "1,000-turn seeded headless run" is satisfied in-process (AC-09.8) and through `h run` (AC-09.7);
  "Rebuilding the view from a snapshot matches the live view digest" uses `SimView.view_digest()`, not `h digest`
  (that one digests files, not live trees).
### 8.4 Assumptions about other areas
- A5: `Harness.register("world", <RefCounted>)` keeps the object until unregister; A5 path segments `.t3` work on
  dict keys; `CommandBus.handle` called again for a type replaces the handler (SimHost re-`start` after a scene
  swap); A5 metrics `events.<type>` count command events; `Rng.get_seed()` exists. If `handle` refuses duplicates,
  A5 adds `unhandle(type)` and SimHost calls it on `tree_exiting`.
- A3: `lint.sim-node`, `lint.det-*`, `lint.raw-keycode`, `lint.input-action` as in 03 §3.3; `rng_files` default
  exempts nothing in the sample (the sim uses `world.rng`, an instance RNG, which A3 does not flag).
- A2: `$res` to a script-class `.tres` and `$node` exports (Host.view) work; `--force` keeps uids; specs can save
  under `res://scenes/**`.
- A4: `h test <dir>` installs gdUnit4 into a fresh copy; scene suites can `scene_runner` a scene that uses autoloads.
- A6: `h shot <scene> --tick N` and a baseline store under `<project>/baselines/`; provisional baselines allowed.
- A7: FeelTargets `.tres` schema and metric names; A9 needs names for apex px, time to apex, accel ticks, coyote
  ticks, buffer ticks; `h trace` reads `res://tuning/feel_targets.tres` by default or via a flag.
- A8: `h init` copies `templates/project/` when the target has no `project.godot` and `templates/sim_view/` on
  request; the CLAUDE.md block quotes §2.8; skills cite the sample files as examples.
- Plan defaults: D1 GDScript only, D2 two 2D scenes, D4 targets/baselines provisional until a human approves, D5
  small tier, B5 commit `.uid`, B7 hash-then-tolerance.
