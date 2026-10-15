# 05 Scenario / replay runner (A5, planner P5; absorbs R2.2)

Status: spec v1, 2026-10-15, Opus planner P5. Conforms to `00_contract.md` (v1); deviations are listed in §8.
Tags: [Run] verified in §3.6 spikes (Godot 4.7.stable.official.5b4e0cb0f, scratchpad `a5/`), [U] unverified.

## 1. Purpose and failure modes covered

`h run` replays a scripted, seeded, fixed-tick scenario headless and reports state, events, metrics, assert results
and a determinism verdict, so the agent can prove behaviour ("the player reaches x >= 400 by tick 180") instead of
claiming it. It also lets the agent catch nondeterminism it introduced, which it cannot see by reading code.
- **C6** (plan): seeded fixed-step replay, addressable state, command stream; the article's core loop.
- **F10** physics behaviour (floor detection, tunnelling) is checked by scenario asserts on dumped state.
- **F2/D2** "it parses" is not evidence: asserts report measured values; `run.no-asserts` warns on empty scenarios.
- **Determinism (R1.8)**: global RNG, idle-mode Tween/Timer/AnimationPlayer, `_process` delta in gameplay,
  unseeded `RandomNumberGenerator`, wall-clock time: caught at run time by `--twice` with perturbation and a cause hint
  (static bans are A3's lint; this is the dynamic net).
- **B7**: golden = exact hash first, tolerance fallback; "hash differs, tolerance passes" = WARN.
- **R1.6**: commands address stable entity ids, never NodePaths; state is plain data (`run.state-nonserializable`).
- **Exit codes lie (R1.1, S2)**: runtime `SCRIPT ERROR`s during a replay fail the run even if every assert passes.

## 2. Interfaces

### 2.1 CLI
```
h run <scenario.json|dir>... [--project DIR] [--twice] [--record [--force]] [--seed N] [--ticks N]
      [--var NAME=INT]... [--strict]
```
- Positional: one or more scenario files or dirs; a path is cwd-relative, absolute, or `res://...` (resolved against
  the project). A dir expands to its `*.json` files (recursive, sorted, excluding `*.golden.json`). None found: rc 2.
- `--twice`: run each scenario twice with perturbation (§3.3) and compare per-tick hashes; on divergence, run up to two
  diagnosis runs to name the cause.
- `--record`: implies `--twice`; on success writes `<scenario stem>.golden.json` next to the scenario. If the golden
  exists: rc 2 `golden exists: <path> (use --force)` unless `--force`. A nondeterministic run never writes a golden.
- `--seed N` / `--ticks N` override `seed` / `ticks` (stat `golden: skipped (overrides)`). `--var NAME=INT` overrides
  a `vars` entry (§2.2); unknown name: rc 2.
- Exit codes per contract §2.4: 0 PASS, 1 FAIL, 2 bad scenario/flags/not synced, 3 internal or runner rc 2/3,
  4 environment, 5 WARN (drift, no-asserts, time-scale).

Stdout (contract §2.3). Single scenario, stat lines in this order: `project`, `import`, `sync`, `scenario`, `hash`,
`twice` (if run), `golden`, `asserts`, `events`. Literal examples:
```
$ tools/harness/h run res://scenarios/jump.json --project /tmp/h/scenario_min
PASS run 6/6 asserts, 120 ticks (0.7s)
project: /tmp/h/scenario_min
import: fresh
sync: fresh
scenario: res://scenarios/jump.json (seed 7, 120 ticks @ 60 Hz)
hash: 9f5738f56074cf60 chain 74edefdeff186eb9
golden: none
asserts: 6 total, 6 pass, 0 fail
events: 4 (jump_pressed x1, jump_released x1, teleported x1, landed x1)
log: /tmp/h/scenario_min/.harness/out/20261015T150102Z-run-1c2d/

$ tools/harness/h run res://scenarios/jump.json --twice --project /tmp/h/p
FAIL run nondeterministic: diverged at tick 1 (1.9s)
project: /tmp/h/p
import: fresh
sync: fresh
scenario: res://scenarios/jump.json (seed 7, 120 ticks @ 60 Hz)
hash: 0233681b940465eb chain 00fe2135b56a7bfe
twice: DIFFERENT (A 60 fps vs B 120 fps, global seed changed); cause: global-rng
golden: none
asserts: 6 total, 6 pass, 0 fail
events: 4 (jump_pressed x1, jump_released x1, teleported x1, landed x1)
res://scripts/player.gd: [run.nondeterministic] error: first divergence at tick 1 in entity 'player': position.x 0.000212 vs 0.000871 (hint: only the global RNG seed changed: use Rng.stream(...))
log: /tmp/h/p/.harness/out/20261015T150210Z-run-77aa/
```
A failed assert prints `res://scenarios/jump.json: [run.assert] error: asserts[2] player.position.x ge 400 @tick 100:
got 168.338 (short by 231.662)` with verdict `FAIL run 1 of 6 asserts failed, 120 ticks (0.7s)`.
Multiple scenarios: verdict line `<V> run <k>/<n> scenarios passed (<t>s)`, stats `project`, `import`, `sync`, then
one check line per scenario `OK   res://scenarios/a.json: 6/6 asserts, hash 9f5738f56074cf60` /
`FAIL res://scenarios/b.json: 1 assert failed` / `WARN ...: golden drift`, then findings, then `log:`.

Rule ids (all `run.`): `run.assert`, `run.nondeterministic`, `run.golden-mismatch`, `run.golden-drift` (warning),
`run.golden-stale`, `run.unknown-action`, `run.unknown-target`, `run.unknown-command`, `run.state-nonserializable`,
`run.bind`, `run.no-asserts`, `run.time-scale`, `run.state-large` (these three: warning), `run.tick-skipped`,
`run.scenario` (rc 2 schema/semantic errors), `run.not-synced` (rc 2). Finding locations: `run.assert`, `run.unknown-*`,
`run.bind`, `run.golden-*`, `run.scenario` -> the scenario file (res:// if inside the project, no line);
`run.state-nonserializable`, `run.nondeterministic` -> the entity's script path (`res://...gd`) if it has one, else the
scenario file. Assert messages always contain `got <measured>` and the expected op/value (§3.4).

### 2.2 Scenario file (JSON Schema, draft 2020-12; builder ships it as `tools/harness/schemas/scenario.schema.json`)
```json
{"$id":"harness.scenario/1","type":"object","additionalProperties":false,"required":["schema","scene","seed","ticks"],
 "$defs":{
  "int":{"oneOf":[{"type":"integer","minimum":0},
    {"type":"string","pattern":"^ *(\\d+|\\$[a-z_][a-z0-9_]*)( *[+-] *(\\d+|\\$[a-z_][a-z0-9_]*))* *$"}]},
  "id":{"type":"string","pattern":"^[A-Za-z0-9_:-]{1,64}$"},
  "when":{"oneOf":[{"required":["tick"]},{"required":["at_end"]},{"required":["during"]}]}},
 "properties":{
  "schema":{"const":"harness.scenario/1"}, "description":{"type":"string","maxLength":500},
  "scene":{"type":"string","pattern":"^res://.+\\.(tscn|scn)$"},
  "seed":{"type":"integer","minimum":0,"maximum":9007199254740991},
  "ticks":{"$ref":"#/$defs/int"}, "tick_rate":{"type":"integer","minimum":1,"maximum":1000},
  "vars":{"type":"object","propertyNames":{"pattern":"^[a-z_][a-z0-9_]*$"},"additionalProperties":{"type":"integer"}},
  "hash_every":{"type":"integer","minimum":1}, "golden_every":{"type":"integer","minimum":1},
  "golden_tol":{"type":"number","exclusiveMinimum":0},
  "bind":{"type":"object","propertyNames":{"$ref":"#/$defs/id"},"additionalProperties":{"type":"object",
    "additionalProperties":false,"required":["node","props"],"properties":{"node":{"type":"string","minLength":1},
    "props":{"type":"array","minItems":1,"items":{"type":"string","pattern":"^[A-Za-z_][A-Za-z0-9_]*(\\(\\))?$"}}}}},
  "inputs":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["tick","action"],
    "properties":{"tick":{"$ref":"#/$defs/int"},"action":{"type":"string","minLength":1},"pressed":{"type":"boolean"},
      "strength":{"type":"number","minimum":0,"maximum":1},"hold":{"$ref":"#/$defs/int"}},
    "oneOf":[{"required":["pressed"],"not":{"required":["strength"]}},{"required":["strength"],"not":{"required":["pressed"]}}]}},
  "commands":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["tick","type"],
    "properties":{"tick":{"$ref":"#/$defs/int"},"type":{"type":"string","pattern":"^[a-z][a-z0-9_]*$"},
      "target":{"$ref":"#/$defs/id"},"value":{}}}},
  "dumps":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["what"],
    "properties":{"tick":{"$ref":"#/$defs/int"},"at_end":{"const":true},"what":{"type":"array","minItems":1,
      "items":{"oneOf":[{"$ref":"#/$defs/id"},{"const":"*"}]}}},"oneOf":[{"required":["tick"]},{"required":["at_end"]}]}},
  "asserts":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["op"],
    "properties":{"tick":{"$ref":"#/$defs/int"},"at_end":{"const":true},
      "during":{"type":"array","minItems":2,"maxItems":2,"items":{"$ref":"#/$defs/int"}},
      "quant":{"enum":["all","any"]},"path":{"type":"string","pattern":"^[A-Za-z0-9_:-]+((\\.[A-Za-z_][A-Za-z0-9_]*)|(\\[\\d+\\]))*$"},
      "metric":{"type":"string","minLength":1},"op":{"enum":["eq","ne","lt","le","gt","ge","between","exists"]},
      "value":{},"tol":{"type":"number","minimum":0},"note":{"type":"string","maxLength":200}},
    "allOf":[{"$ref":"#/$defs/when"},{"oneOf":[{"required":["path"]},{"required":["metric"]}]}]}}}}
```
Semantic rules (checked in Python after the schema; violations -> rc 2, finding `[run.scenario] error: <json pointer>:
<what>`, e.g. `/asserts/3/tick: 700 > ticks 600`):
- Integer fields (`ticks`, `tick`, `hold`, `during[*]`) may be expressions over `vars`: `"$t0+$k"`, `"40-$k"`.
  `--var` overrides `vars`; an unknown `$name` or a result < 0 is an error. `ticks` 1..36000 after substitution.
- Ticks: tick 0 = state after the scene's `_ready`, before any physics step; tick k (1..ticks) = state after the
  k-th physics step. An **input or command at tick k is applied before physics step k** (between steps k-1 and k), so
  `Input.is_action_pressed` and `is_action_just_pressed` are both true during step k [Run §3.6 S2]. Inputs and
  commands need 1 <= k <= ticks; dumps/asserts 0 <= k <= ticks; `at_end` = tick `ticks`; `during [a,b]` needs
  a <= b and `quant` (default `all`). `hold: n` (n >= 1) = press at k, release before step k+n.
- `pressed: false` / `strength: 0` releases. Several entries on one tick apply in file order.
- `action` must exist in project.godot `[input]` or be a built-in `ui_*` action, else FAIL `[run.unknown-action]`
  (with did-you-mean, edit distance <= 2), checked before Godot starts.
- `op`: `eq`/`ne` with numbers compare with `tol` (default 0); with strings/bools/null/arrays/objects exactly.
  `lt le gt ge` need numbers. `between`: `value = [lo, hi]`, inclusive, `tol` widens both ends. `exists`: path
  resolves (value must be absent). `metric` asserts are end-of-run only (`at_end` required).
- `path`: `<entity id>` then `.key` / `[index]` segments into the entity's state (§2.4). `bind`/registered ids only.
- `scene` must exist in the project (else rc 2). Defaults: `tick_rate` = project.godot
  `physics/common/physics_ticks_per_second` (else 60); `hash_every` 1; `golden_every` = tick_rate;
  `golden_tol` = harness.toml `[run] golden_tol` (default 0.001).

### 2.3 In-engine APIs (autoloads installed by `h sync`; files in `addons/harness/`; no `class_name`)
```gdscript
# Harness  (addons/harness/harness.gd, extends Node). Dormant unless the scenario runner activates it.
signal tick_completed(tick: int)            # emitted by the runner after tick k's dumps/hashes (A6/A7 sample here)
func is_active() -> bool                    # true only under `h run` / `h trace` / `h shot <scenario>`
func tick() -> int                          # completed ticks under the runner; else Engine.get_physics_frames()
func register(id: Variant, obj: Object) -> bool  # id: int|String -> str(id), must match ^[A-Za-z0-9_:-]{1,64}$;
    # obj must have `_harness_state() -> Dictionary`. Duplicate live id or bad id: push_error, return false.
    # Nodes auto-unregister on tree_exiting. RefCounted objects (sim worlds) are held until unregister().
func unregister(id: Variant) -> void
func has_entity(id: Variant) -> bool
func get_entity(id: Variant) -> Object
func event(type: String, data: Dictionary = {}) -> void    # -> events.jsonl; no-op cost when dormant
func metric(name: String, value: float, mode: String = "set") -> void   # mode: set|add|max|min
# Rng  (addons/harness/rng.gd, extends Node). The only RNG gameplay code may use (A3 lint enforces).
func seed_all(seed: int) -> void            # resets every stream; the runner calls it before the scene loads
func get_seed() -> int                      # unseeded game start: seeded once from Time + OS.get_unique_id() hash
func stream(name: StringName = &"default") -> RandomNumberGenerator
    # stream seed = PackedByteArray(("%d:%s" % [root_seed, name]).sha256_buffer()).decode_s64(0); independent of
    # creation order; same object for the same name until seed_all()
func randi_range(lo: int, hi: int) -> int   # on stream("default"); also randf(), randf_range(lo, hi)
func pick(arr: Array, stream_name: StringName = &"default") -> Variant   # arr[randi_range(0, size-1)]; empty -> null
func shuffle(arr: Array, stream_name: StringName = &"default") -> void
    # in place, Fisher-Yates: for i in range(size-1, 0, -1): j = randi_range(0, i); swap(i, j)
func save() -> Dictionary                   # {"seed": int, "streams": {name: {"seed": int, "state": int}}}
func restore(d: Dictionary) -> void         # seed first, then state (R1.8)
# CommandBus  (addons/harness/command_bus.gd, extends Node)
signal events_emitted(cmd: Dictionary, events: Array)
func handle(type: String, handler: Callable) -> void    # handler(cmd: Dictionary) -> Array (events); one per type
func set_resolver(resolver: Callable) -> void           # resolver(target: String) -> bool; default Harness.has_entity
func submit(cmd: Dictionary) -> Array       # cmd = {type, target?, value?}; adds "seq" (1-based) and "tick".
    # No handler -> push_error("CommandBus: unknown command '<type>'"), returns [].
    # target given and resolver false -> push_error("CommandBus: unknown target '<id>'"), returns [], handler not called.
    # Events: each a Dictionary with "type": String, or an Object with to_dict() returning one. Each event is
    # logged via Harness (src "command", cmd seq) and emitted once via events_emitted.
```
Entity state (`_harness_state()` and `bind` props) is normalised to JSON before hashing:
bool/int/String/StringName as is; float as is (NaN/Inf: error); Vector2/2i/3/3i/4/4i -> `{"x","y"[,"z","w"]}`;
Color -> `{"r","g","b","a"}`; Rect2(i) -> `{"position":{..},"size":{..}}`; Transform2D -> `{"x","y","origin"}`;
Basis/Quaternion/Transform3D -> nested dicts by component; Array and Packed*Array -> array; Dictionary -> object
(keys via `str()`). Object, Node, NodePath, RID, Callable, Signal, or NaN/Inf -> runner finding
`[run.state-nonserializable] error: entity '<id>' <path>: <Type> is not plain data (hint: store an entity id/int,
never a Node or NodePath)`; the value is replaced by `null` and the run continues.

### 2.4 Output files (`<run dir>/artifacts/`; with `--twice`: `A/`, `B/`, and `diag-*/` for diagnosis runs)
- `scenario.resolved.json`: the scenario after defaults, `--var`, `--seed`, `--ticks`.
- `state.json`: `{"schema":"harness.state/1","tick":N,"hash":"<64 hex>","chain":"<64 hex>","meta":{...},
  "entities":{id: state}}`; `meta` = `{godot, arch, cpu, tick_rate, fps, seed, physics_2d, physics_3d}`.
- `states.jsonl`: one `{"tick":k,"entities":{...}}` per dump/assert tick (only entities referenced; `*` = all),
  and every tick of each `during` range.
- `ticks.jsonl`: one `{"tick":k,"hash":"<64 hex>","entities":{id:"<16 hex>"}}` per hashed tick.
- `events.jsonl`: `{"tick":k,"seq":n,"type":"...","src":"harness"|"command","cmd":<seq>|null,"data":{...}}`.
- `metrics.json`: `{"schema":"harness.metrics/1","ticks":N,"metrics":{name:number}}` with built-ins `ticks`,
  `events_total`, `events.<type>`, `commands_total`, `wall_s`, plus `Harness.metric()` values.
- `asserts.json`: `[{"index":i,"path"|"metric":..,"op":..,"value":..,"tick"|"during"|"at_end":..,"pass":bool,
  "got":<value or null>,"at_tick":k|null}]`.
- Hashes: entity hash = `JSON.stringify(normalised, "", true, true).sha256_text()` (sorted keys, full precision);
  tick hash = sha256 of `"<id>\t<entity hash>\n"` lines in sorted id order; `chain` = sha256 of the tick hashes
  joined by `\n`. `hash:` on stdout = first 16 hex of `state.json.hash`, then `chain` + first 16 hex.

### 2.5 Golden file `<scenario stem>.golden.json` (next to the scenario; committed by the user)
`{"schema":"harness.golden/1","scenario_sha256":"<sha256 of the scenario file bytes>","recorded_at":"<iso>",
"meta":{...as state.json},"final_hash":"<64 hex>","chain_hash":"<64 hex>","tol":0.001,
"checkpoints":[{"tick":k,"hash":"<64 hex>","entities":{...}}]}`. Checkpoints: tick 0, every `golden_every` ticks,
each dump/assert tick, and `ticks`. Compare (§3.4): stat `golden: match|drift (<n> values within tol)|MISMATCH|stale|
none|skipped (<why>)`. Goldens are regression records, not human judgements (D4 does not apply).

### 2.6 Config (`harness.toml`, `CONFIG_TABLE = "run"`)
`[run] golden_tol = 0.001` (float > 0), `hash_every = 1` (int >= 1), `required_autoloads = ["Harness","Rng",
"CommandBus"]` (list of str). Timeout: contract kind `scenario` (120 s, `[timeouts] scenario`), per Godot invocation.

## 3. Design

### 3.1 Files (builder B5 writes exactly these)
- `tools/harness/harness/verbs/run.py` (CLI, orchestration, output), `tools/harness/harness/scenario.py` (stdlib
  only: load + validate + substitute + semantic checks, path resolution, assert eval, golden read/write/compare,
  state diff), `tools/harness/schemas/scenario.schema.json` (§2.2 verbatim).
- `addons/harness/{harness,rng,command_bus}.gd`, `addons/harness/runners/scenario.gd`. Nothing to port verbatim;
  `research/scripts/r1_8_determinism/main.gd` shows the fixed-tick loop and hashing (here: sorted JSON, §3.6 S6).

### 3.2 Runner `addons/harness/runners/scenario.gd` (extends SceneTree, self-contained, contract §2.8.5)
User args: `--scenario=<abs resolved json> --out=<abs dir> --fps=<int> --global-seed=<int> [--dump-ticks=a,b,..]`.
1. `_initialize()`: parse args (bad -> `done` rc 2). Find `/root/Harness`, `/root/Rng`, `/root/CommandBus`
   (`root.get_node_or_null`, no preload). Missing -> finding `[run.not-synced]`, rc 2. Set
   `Engine.physics_ticks_per_second = tick_rate`; `seed(global_seed)` (global RNG poisoning, §3.3);
   `Rng.seed_all(seed)`; activate Harness. `load(scene)`; `can_instantiate()` check (S2) else finding + `quit(1)`;
   instantiate, `root.add_child`, `current_scene = it`. Connect `root.ready` (one-shot) to `_begin`: at
   `_initialize` the root is not in the tree yet and `_ready` has not run [Run S1].
2. `_begin()`: register `bind` entities (node path relative to the scene root; missing node or prop -> `[run.bind]`
   error, quit 1); record tick 0 (hash, dumps); apply inputs/commands for tick 1; `base = Engine.get_physics_frames()`.
3. `_process(delta) -> bool` (MainLoop virtual; runs after the frame's physics steps): `c = physics_frames - base`.
   `c == done` -> return. `c > done + 1` -> finding `[run.tick-skipped]` error, quit 1 (fps < tick rate; cannot
   happen with the verb's fps values). Else `done = c`: record tick `done` (entity hashes every `hash_every`,
   states for dump/assert/during ticks, `Engine.time_scale != 1.0` -> one `[run.time-scale]` warning), emit
   `Harness.tick_completed(done)`; if `done == ticks` -> finish; else apply inputs/commands for tick `done+1`.
   Never inject from `_physics_process` (off-by-one `just_pressed`, [Run S2]).
4. Inputs: `InputEventAction` (`action`, `pressed`, `strength`) via `Input.parse_input_event`, then
   `Input.flush_buffered_events()`. This updates polling state and delivers `_input`/`_unhandled_input` [Run S2].
   Holds are expanded by Python into explicit releases. Commands: `CommandBus.submit(cmd)`; the runner checks the
   handler and target first and reports `[run.unknown-command]` / `[run.unknown-target]` (`commands[i] target
   'ghost' is not a registered entity at tick 10`) instead of submitting.
5. Finish: write the §2.4 runner files to `--out`, print `@@H` stats (`ticks`, `hash`, `chain`, `events`), then
   `{"t":"done","rc":N}` and `quit(N)` (0 clean, 1 runner findings); no `done` = incomplete output.

### 3.3 Verb flow (`run.py`) and `--twice`
1. Resolve project, config, scenario paths; `scenario.load()` (schema, vars, semantics, unknown actions). Check that
   `required_autoloads` are declared in project.godot `[autoload]`: missing -> rc 2 `[run.not-synced]`
   `Harness autoload not declared in project.godot (run h sync)`. Then `sync.ensure_synced(run, project)` (A1, §8)
   prints `sync: fresh|ran (<why>)`; `godot.ensure_imported()` prints `import:`.
2. Run A: `godot.run(kind="scenario", runner=$HARNESS_REPO/addons/harness/runners/scenario.gd, args=["--fixed-fps",
   str(tick_rate)], user_args=[..., "--fps=<tick_rate>", "--global-seed=<g(seed,'A')>"])`, g = first 8 bytes of
   sha256(f"{seed}:{tag}") as int. Verdict merge per contract §2.8.6 (scan + rc + runner).
3. Evaluate asserts from run A's `states.jsonl`/`metrics.json` (§3.4); write `asserts.json`.
4. `--twice`: run B with fps = 2 x tick_rate and global seed g(seed,'B'). Physics results do not depend on the render
   frame rate and B still sees one tick per frame boundary [Run S3]. Compare `ticks.jsonl` line by line; first
   differing tick k and the entities whose hashes differ. If they differ, run up to two diagnosis runs with
   `--dump-ticks=k`: `diag-A2` (= A's config) and, if A2 == A at k, `diag-C` (A's fps, B's global seed). Cause:
   A2 != A -> `identical-runs` (hint: wall clock, unseeded RandomNumberGenerator.new(), threads, Time.get_ticks_*);
   C != A -> `global-rng` (hint: use Rng); else -> `frame-rate` (hint: `_process` delta or idle-mode
   Tween/Timer/AnimationPlayer; set TWEEN_PROCESS_PHYSICS / TIMER_PROCESS_PHYSICS / ANIMATION_CALLBACK_MODE_PROCESS_PHYSICS).
   The finding names up to 3 differing paths with both values (from the dumps of the two disagreeing runs at k).
5. Golden: if `<stem>.golden.json` exists and no `--seed/--ticks` override: compare (§3.4). `--record`: after a
   clean `--twice`, write the golden (stat `golden: recorded <path>`).
6. Verdict: worst of invocations, runner findings, asserts, twice, golden; `run.no-asserts` if no asserts and no golden.

### 3.4 Assert and golden algorithms (`scenario.py`, pure Python, unit-tested)
- `resolve(state, path)`: walk entity -> keys/indices; missing -> `None` with reason (`entity 'x' not present at
  tick 40` / `key 'vel' not in player`); a missing path fails every op, including `exists`.
- Assert message: `asserts[i] <path|metric> <op> <value>[ tol <t>] @<tick k|end|ticks a..b (all|any)>: got <v>`,
  plus ` (short by d)` / ` (over by d)` for numeric ops. For `during`/`all`, `got` is the first failing tick's value
  (`at tick k`); for `any`, the closest value and its tick. Numbers print with up to 6 significant decimals.
- Golden compare: `scenario_sha256` differs -> FAIL `[run.golden-stale]` (hint: scenario changed; re-record with
  `--record --force`). Else `final_hash == state.hash` and `chain_hash == chain` -> `match`. Else compare each
  checkpoint's entities with the run's dumps at the same tick: ints/bools/strings/null/keys/array lengths exact;
  floats `|a-b| <= tol` -> all equal: WARN `[run.golden-drift]` (`hash differs but all <n> values within tol
  <t>; environment changed? (golden: <arch/cpu/godot>, now: ...)`); else FAIL `[run.golden-mismatch]` naming
  the earliest checkpoint tick and up to 3 paths `golden 599 vs now 600`. The runner dumps all checkpoint ticks.

### 3.5 Budgets and error patterns
- 600-tick scenario with <= 10 small entities: `h run` <= 3 s wall warm (Godot process ~0.4 s [Run S4]);
  `--twice` <= 5 s; diagnosis adds <= 2 s. `states.jsonl` > 50 MB -> warning `[run.state-large]`, dumps stop.
- Log scan: contract §2.8.4 unchanged; runner messages are `@@H` records, never `ERROR:` lines.

### 3.6 Spikes [Run] (scratchpad `a5/proj`: CharacterBody2D player on a StaticBody2D floor, `-s` runner by absolute
path, `--headless --fixed-fps N`)
- **S1 autoloads and timing.** `-s /abs/runners/run.gd` + project autoload: `autoload Harness present: true`. In
  `_initialize`: `root.is_inside_tree=false entities=0`; via `root.ready` one-shot: `in _begin: entities=["player"]
  pf=0`. A runner `SCRIPT ERROR ... on a null instance` in `_initialize` did NOT stop the run (scan, not rc).
- **S2 input injection.** From the runner's `_physics_process` or `physics_frame` at tick 40 (runner runs before
  nodes, `player_last_pf=39`): `player sees pressed at pf=40 just=false`, `jp_ticks=[41]` (off by one), for both
  `action_press` and `parse_input_event`. From `_process` after tick 39: `pressed at pf=40 just=true`, `jp_ticks=[40]`;
  `parse_input_event` also gave `unhandled_input jump at pf=39 in_phys=false`. Decision: `_process` + parse + flush.
- **S3 repeatability (the required 3x CharacterBody2D run).** 120 ticks, jump at 40, right 0.5: fps 60 / fps 60 /
  fps 120 (global seed 111/111/222) -> `HASH eeac768da177db8b chain=c219efcb2ce5b2a4` all three. 600 ticks x3:
  `HASH 1f9d41f5e9553c1e chain=02b26d430cca6339` x3. `--fixed-fps 30` (< tick rate): `skipped=60`, jump never seen
  -> fps must be >= tick rate (B uses 2x).
- **S4 timing.** 600 ticks: process wall 0.367 / 0.367 / 0.398 s; in-runner 120-131 ms incl. per-tick hashing.
- **S5 fault detection (A = fps 60 seed 111 twice, B = fps 120 seed 222; final / chain):** clean: equal / equal.
  global `randf()` in `_physics_process`: A `0233681b...`, B `a95e88fe...` (differ). idle-mode Tween on a state
  field (1.3 s): final EQUAL `64ac2ff3...` but chain differs `86c5be68...` vs `8dbdd259...` -> per-tick hashes are
  required. `_process` delta: `9f5fca4e...` vs `8510a446...`. Physics-mode Tween: equal. Unseeded
  `RandomNumberGenerator.new()` (same fps+seed) x3 and unseeded global `randf()` x3: three different hashes each.
- **S6 JSON.** `JSON.stringify(d, "", true, true)` -> `{"a":0.10000000149011612,"b":0.1,"big":1e+300,"f":3.0,
  "i":3,"neg0":0.0}` (sorted, full precision; float32 widened exactly). A `NodePath` is silently written as
  `"A/B"` and `INF` as `1e99999`, so the runner must type-check before stringify (§2.3).
  `("7:default").sha256_buffer().decode_s64(0)` = 7278379237195912242.

## 4. Acceptance criteria (fixture `scenario_min` copied per B3 unless stated; every result passes `assert_contract`)
- AC-05.1 `h run res://scenarios/jump.json` -> rc 0, `PASS run`, stats in §2.1 order, `asserts: 6 total, 6 pass,
  0 fail`, `golden: none`, `hash: [0-9a-f]{16} chain [0-9a-f]{16}`. [contract]
- AC-05.2 Artifacts exist and parse: `state.json` (`schema`, 64-hex `hash` whose first 16 hex equal the stdout
  value, `entities.player`, `meta.tick_rate == 60`), `states.jsonl`, `ticks.jsonl` (121 lines for 120 ticks),
  `events.jsonl` (has `jump_pressed` at tick 40), `metrics.json` (`metrics.ticks == 120`, `events.jump_pressed == 1`),
  `asserts.json` (6 entries), `scenario.resolved.json`. [contract]
- AC-05.3 Two separate `h run` of jump.json give identical `state.json.hash` and `chain`. [contract]
- AC-05.4 `--twice` on jump.json and mover.json -> rc 0, stat `twice: identical (A 60 fps vs B 120 fps, global seed
  changed)`, artifacts `A/` and `B/`. [contract]
- AC-05.5 Input timing: jump at 40 `hold: 3` -> `events.jsonl` has `jump_pressed` `{"just":true,"pressed":true}` at
  tick 40, `jump_released` at tick 43; state `player.input_events` (`_unhandled_input`) == 1. [contract]
- AC-05.6 A failing assert (`player.position.x ge 400 @tick 100`) -> rc 1, finding `^res://scenarios/\S+\.json:
  \[run\.assert\] error: asserts\[\d+\] player\.position\.x ge 400 @tick 100: got -?[0-9.]+`; `asserts.json` has
  `pass: false` and numeric `got`. [contract]
- AC-05.7 Assert semantics on synthetic states: eq/ne with and without tol, lt/le/gt/ge, between (inclusive, tol
  widens), exists, during all/any (first failing tick; closest value), missing entity/key messages, metric at_end,
  vector `.x` paths, array `[i]` paths. [unit, `harness.scenario`]
- AC-05.8 Schema/semantic errors each give rc 2 and `[run.scenario]` with a JSON pointer: missing `scene`; unknown
  top-level key; `tick` > `ticks`; input with both `pressed` and `strength`; metric assert with `tick`; `op` not in
  enum; `between` value not a pair; unknown `$var`; scene file absent. No Godot invocation in `run.json`. [contract]
- AC-05.9 `--var k=5` on sweep.json moves the jump press to tick 45 (events.jsonl); `--var nope=1` -> rc 2. [contract]
- AC-05.10 Commands: teleport at tick 90 to (500, 100) -> dump at tick 89 has `player.position.x < 500`, at tick 90
  `between [500, 502]` (applied before step 90); `events.jsonl` has `teleported`, `src:"command"`, `cmd: 1`. [contract]
- AC-05.11 Unknown target -> rc 1, `[run.unknown-target]` naming `commands[0]` and the id; unknown type ->
  `[run.unknown-command]`. [contract]
- AC-05.12 Unknown input action `jmup` -> rc 1, `[run.unknown-action]` with `did you mean 'jump'`; no Godot
  scenario invocation (only import, if any). [contract]
- AC-05.13 Autoload `Harness` not declared in project.godot -> rc 2, `[run.not-synced]`, message contains `h sync`.
  Declared but `addons/harness/` absent (fresh fixture copy) -> run proceeds, stat `sync: ran`. [contract]
- AC-05.14 Seeds: `dice.json` with `--seed 1` twice -> equal `dice.sum`; `--seed 2` -> different; scenario seed is
  used when no flag; `golden: skipped (overrides)` with `--seed`. [contract]
- AC-05.15 `bind`: bind.json binds `box` -> node `Box` props `position`, `visible`, and `player2` -> `Player`
  props `is_on_floor()`; state.json has `box.position.x == 50` and a bool `player2.is_on_floor()` key; a
  wrong node path -> rc 1, `[run.bind]`. [contract]
- AC-05.16 `--record` on mover.json writes `scenarios/mover.golden.json` (§2.5; checkpoints 0, 60, ..., 600); rerun
  -> `golden: match`, rc 0; `--record` again -> rc 2 `golden exists`; with `--force` -> rc 0. [contract]
- AC-05.17 `--record` on a nondeterministic fixture variant (FAULT-A5-01 setup) -> rc 1 and no golden file. [contract]
- AC-05.18 Golden with off-by-one `mover.n` at checkpoint 600 -> rc 1 `[run.golden-mismatch]` naming tick and
  `mover.n`, values `599 vs 600`. Golden with bogus hashes but exact values -> rc 5 `[run.golden-drift]`; with
  `--strict` rc 1. Golden whose `scenario_sha256` mismatches -> rc 1 `[run.golden-stale]`. [contract]
- AC-05.19 Scenario with no asserts and no golden -> rc 5 `[run.no-asserts]`. [contract]
- AC-05.20 Runtime `SCRIPT ERROR` in the player at tick 50 (all asserts pass) -> rc 1, finding
  `^res://scripts/player\.gd:\d+: \[godot\.script-error\]`. [contract]
- AC-05.21 Player loops forever after tick 30, `[timeouts] scenario = 5` -> rc 1 `[harness.hang]`, wall <= 12 s. [contract]
- AC-05.22 NodePath returned from `_harness_state` -> rc 1 `[run.state-nonserializable]` naming `player` and the
  key, location `res://scripts/player.gd`; the run still completes (`state.json` exists). [contract]
- AC-05.23 Perf: `h run res://scenarios/mover.json` (600 ticks) <= 3 s wall, `--twice` <= 5 s (warm copy,
  median of 3). [contract, slow]
- AC-05.24 Dir/multi: `h run res://scenarios/clean/` (jump.json + mover.json) -> rc 0, `PASS run 2/2 scenarios
  passed`, 2 `OK` check lines, `*.golden.json` not treated as scenarios; adding a failing scenario -> rc 1. [contract]
- AC-05.25 Rng (gdUnit4, `tests/gd/a5/`): after `seed_all(7)`, `stream(&"a").randi()` is the same whether `&"b"` was
  created first; stream seed = §2.3 derivation; `save()`/`restore()` continues identically; `shuffle([1..10])` equals
  a Fisher-Yates reference on a fresh stream; `pick([])` -> null. [gd]
- AC-05.26 Harness/CommandBus (gdUnit4): register bad/duplicate id -> false + error; node auto-unregisters on free;
  `is_active()` false outside the runner; `submit` with no handler -> [] and push_error; unknown target -> handler
  not called; handler events get `seq`; Object events with `to_dict()` accepted. [gd]
- AC-05.27 `Engine.time_scale = 2.0` set by the game -> rc 5 `[run.time-scale]` (once). [contract]
- AC-05.28 `h selftest --area A5` -> all must faults CAUGHT, CLEAN-A5-* PASS, wall <= 120 s. [contract, slow]

## 5. Seeded faults (fixture `scenario_min`; verb `run`; args use `res://`; `must` unless noted)
Fixture hook lines (exact text in `scripts/player.gd`, one each): `	pass # HOOK-PHYS` (end of `_physics_process`),
`	pass # HOOK-PROCESS` (in `_process`), `	pass # HOOK-READY` (end of `_ready`), `	var extra := {} # HOOK-STATE`
(first line of `_harness_state`, merged into the returned dict).
| ID | Planted (replace op on the hook line unless noted) | Args | Expect |
|---|---|---|---|
| FAULT-A5-01 | PHYS -> `	position.x += randf() * 0.01` | `res://scenarios/jump.json --twice` | rc 1, `\[run\.nondeterministic\]`, `global-rng`, <= 30 s |
| FAULT-A5-02 | READY -> `	create_tween().set_process_mode(Tween.TWEEN_PROCESS_IDLE).tween_property(self, "tw_x", 100.0, 1.3)` | same | rc 1, `\[run\.nondeterministic\]`, `frame-rate` |
| FAULT-A5-03 | write `scenarios/wrong.json` = jump.json + assert `player.position.x ge 400 @tick 100` | `res://scenarios/wrong.json` | rc 1, `\[run\.assert\].*got ` |
| FAULT-A5-04 | write `scenarios/ghost.json` with command `teleport` target `ghost` | `res://scenarios/ghost.json` | rc 1, `\[run\.unknown-target\].*ghost` |
| FAULT-A5-05 | PHYS -> `	if Harness.tick() > 30:\n		while true: pass`; write harness.toml `[timeouts]\nscenario = 5\n` | jump.json | rc 1, `\[harness\.hang\]`, <= 40 s |
| FAULT-A5-06 | STATE -> `	var extra := {"target": NodePath("../Box")}` | jump.json | rc 1, `\[run\.state-nonserializable\].*player` |
| FAULT-A5-07 | PHYS -> `	if Harness.tick() == 50:\n		var n = null\n		n.foo()` | jump.json | rc 1, `\[godot\.script-error\]` |
| FAULT-A5-08 | PROCESS -> `	tw_x += delta * 3.0` | jump.json `--twice` | rc 1, `\[run\.nondeterministic\]`, `frame-rate` |
| FAULT-A5-09 | write `scenarios/mover.golden.json` (files/, hand-written, checkpoint 600 has `mover.n = 599`, correct `scenario_sha256`) | `res://scenarios/mover.json` | rc 1, `\[run\.golden-mismatch\].*mover\.n` |
| FAULT-A5-10 | write `scenarios/typo.json` = jump.json with action `jmup` | `res://scenarios/typo.json` | rc 1, `\[run\.unknown-action\].*jump` |
| FAULT-A5-11 (nice) | PHYS -> `	position.x += own_rng.randf() * 0.01` (`own_rng` = unseeded `RandomNumberGenerator.new()` field in the fixture) | jump.json `--twice` | rc 1, `identical-runs` |
| FAULT-A5-12 (nice) | READY -> `	Engine.time_scale = 2.0` | mover.json | rc 5, `\[run\.time-scale\]` |
| CLEAN-A5-01 | none | `res://scenarios/clean/ --twice` | rc 0, `^PASS run 2/2 scenarios passed` |
| CLEAN-A5-02 | none | `res://scenarios/jump.json` | rc 0, PASS, `^asserts: 6 total, 6 pass` |

## 6. Fixtures needed (test-writer T5)
`tests/fixtures/projects/scenario_min/` (hand-written, no `addons/`; FIXTURE.md: owner A5, `h check` PASS after `h sync`):
- `project.godot`: contract minimum + `run/main_scene="res://scenes/level.tscn"`; `[autoload]` `Harness`, `Rng`,
  `CommandBus` = `"*res://addons/harness/{harness,rng,command_bus}.gd"`; `[input]` `jump`, `left`, `right` with
  `"events": []`; `[physics] common/physics_ticks_per_second=60`, `common/physics_jitter_fix=0.0`.
- `scenes/level.tscn`: root `Node2D` "Level" with `scripts/level.gd`; child `Node2D` "Box" at (50, 60) (no script).
- `scripts/level.gd`: `_ready` builds a `StaticBody2D` floor (4000x40 at y 300), `CharacterBody2D` "Player" (capsule,
  at (0, 200), player.gd), `Node` "Mover" (mover.gd), `Node` "Dice" (dice.gd).
- `scripts/player.gd`: `_ready` registers "player", `CommandBus.handle("teleport", ...)` (sets position from
  `value.x/y`, returns `[{"type":"teleported"}]`), hook lines (§5); `_physics_process`: gravity 980, jump -400 when
  `is_action_just_pressed("jump")` and on floor, `velocity.x = 200 * (strength(right) - strength(left))`,
  `move_and_slide()`, `Harness.event("jump_pressed", {"just": true, "pressed": Input.is_action_pressed("jump")})`
  on just-pressed, `jump_released` on just-released, `landed` on floor entry; `_unhandled_input` counts `jump`
  events into `input_events`; fields `tw_x := 0.0`, `own_rng := RandomNumberGenerator.new()`; `_harness_state()`
  -> `{position, velocity, on_floor, input_events, tw_x}` merged with `extra`.
- `scripts/mover.gd`: registers "mover"; per physics tick `n += 1; x += 1.5` (exact: `n = k`, `x = 1.5 k`).
- `scripts/dice.gd`: registers "dice"; per tick `sum += Rng.stream(&"dice").randi_range(1, 6)`.
- `scenarios/jump.json` (seed 7, 120 ticks: right strength 0.5 from tick 1, jump at 40 hold 3, teleport at 90,
  6 passing asserts incl. one `during` any and one metric), `scenarios/mover.json` (600 ticks, 2 asserts),
  `scenarios/clean/{jump,mover}.json` (copies), `scenarios/sweep.json` (`vars {"k":0}`, jump at `"40+$k"`),
  `scenarios/dice.json`, `scenarios/bind.json`, `scenarios/noasserts.json`.
- Golden fixtures for AC-05.18 live in the test or fault `files/` (hand-written from the exact mover values).
- A variant `scenario_noautoload/` (same minus `[autoload]`) for AC-05.13.

## 7. Build order (B5; each step ends green on the named ACs)
1. `scenario.py` load/validate/vars/semantics + schema -> AC-05.7, 8, 9 (rc 2), 12. 2. Autoloads -> AC-05.25, 26.
3. Runner `scenario.gd` + `run.py` single run (inputs, commands, dumps, hashes, events, metrics) -> AC-05.1-3, 5, 6,
   10, 11, 13-15, 19-22, 27.
4. `--twice` + diagnosis -> AC-05.4; FAULT-A5-01/02/08/11.
5. Golden record/compare -> AC-05.16-18. 6. Multi/dir + perf -> AC-05.23, 24. 7. Selftest -> AC-05.28.

## 8. Out of scope, open questions, assumptions
Out of scope (v0): recording human play into a scenario (`h run --capture`, Dreams-style input log; v0.1);
rewind/scrubber and rollback; live MCP stepping (D3); cross-machine golden equality (only drift WARN); 3D-specific
state helpers; parallel A/B runs (sequential to avoid shared `.godot/` writes [U]).
Open [U]:
1. RigidBody node transforms may lag the physics server by one tick at the `_process` sample point (deterministic).
2. `parse_input_event` + flush was verified headless only, not under Xvfb (A6 `h shot <scenario>`).
3. Per-tick hashing cost for large states (100+ entities); `hash_every` is the escape hatch.
4. A scene that changes scenes itself (`change_scene_to_file`) keeps running; entities re-register; untested.
5. FAULT-A5-11 relies on time-seeded default RNG instances differing across processes (3/3 in S5).
Deviations from 00_contract (for the reviewer):
- D-a: unit tests may import `harness.scenario` (pure functions: `load`, `eval_asserts`, `compare_golden`,
  `resolve`), in addition to `logscan`/`out`. Reason: assert/tolerance semantics need many cases (AC-05.7).
- D-b: the plan's A5 block says the `Harness` autoload "drives ticks"; per contract §2.8.5 the `-s` runner drives
  and the autoload is a dormant registry/event/metric API. Plan field names changed: `physics_ticks` -> `tick_rate`,
  asserts `frame|expr` -> `tick|at_end|during` + `path|metric`.
Assumptions on other areas:
- A1: provides `harness.sync.ensure_synced(run, project) -> str` (copies `addons/harness/` into the project when
  project.godot declares a harness autoload and the files are missing or older; returns `fresh` or `ran (<why>)`)
  and `h sync` adds the three autoloads. If A1 declines, B5 implements it inside `run.py` with the same output.
- A3: lint bans global RNG / idle-mode Tween/Timer/AnimationPlayer / `Time.get_ticks_*` statically; `Rng` is the
  sanctioned API (`rng.gd` exempt).
- A6/A7: reuse `runners/scenario.gd` by passing extra user args they own (`--shot-at=`, `--trace=`), sampling on
  `Harness.tick_completed`; they call `scenario.load()` and a `run.py` helper `run_scenario(run, project, scenario,
  fps, global_seed, extra_user_args, display) -> RunResult` (paths of the artifacts). A6 runs it with
  `display="xvfb"`. A7's sweeps use `vars` + `--var`.
- A8: skill `godot-scenario` documents the schema and "no feature claim without a passing scenario"; may hook
  `h run --record --force`.
- A9: sim worlds register as one entity (`Harness.register("world", world)`; `_harness_state()` = `to_dict()`),
  commands go through `CommandBus.handle(type, func(cmd) -> Array)`, events are Dictionaries with `type` (or objects
  with `to_dict()`), RNG only via `Rng.stream(name)`; the sample's scenarios use this schema.
- Plan defaults D1 (GDScript only), D2 (2D platformer + grid tactics), B7 (hash then tolerance, drift = WARN).
