# 07 Feel traces (A7, planner P7; absorbs R2.4)

Status: spec v2, 2026-10-15, Opus planner P7 re-run (REVIEW B18, N09, N17, N23 applied). Conforms to `00_contract.md`
(B01-B07) and builds on `05_scenario.md` (scenario schema, runner, `Harness`, `replay.run_scenario()`, REVIEW R-19);
deviations are in §8. Tags: [Run] verified in §3.7 spikes
(Godot 4.7.stable.official.5b4e0cb0f, scratchpad `a7/`), [U] unverified.

## 1. Purpose and failure modes covered

`h trace` turns "it feels right" into numbers: it replays A5 scenarios, records chosen node properties every physics
tick to CSV, computes a fixed catalogue of feel metrics with an exact tick convention, and compares them with targets
a **human** approved. The agent tunes the game's tunables until targets pass; it never sets, edits or approves targets
and never claims "feels good" (D4, addendum D10). The human gets a clip + metric table as the gate artefact.
- **D1** feel lives in time series (jump arc, camera lag), not code text. **D2** (RP.1 trap 2): coyote/buffer were
  claimed, never measured, and RP.1's probe had a +-1-2 frame convention error; §2.4 fixes one convention.
- **P01/P05/P06 traps**: instant velocity, constant (floaty) gravity, no coyote/buffer, no variable jump, frame-counter
  windows that change with the tick rate, camera smoothing in idle mode (frame-rate dependent, §3.7 S3).
- **D4**: targets carry `approved_by`/`approved_on`; unapproved or agent-attributed targets never yield PASS.
  **Exit codes lie (R1.1)**: every replay is log-scanned (contract §2.8.4); a script error fails the trace.

## 2. Interfaces

### 2.1 CLI
```
h trace <suite.feel.json> [--project DIR] [--rates R1,R2,..] [--movie [PROBE]] [--propose] [--strict]
h trace <suite.feel.json> --approve --from <run dir>                    # human only: TTY required
h trace <scenario.json> --nodes [ID=]PATH[:prop,prop..]... [--metric NAME[:k=v,..]]... [--var NAME=INT]...
```
- First positional: a feel suite (`*.feel.json`, §2.3) or one A5 scenario; cwd-relative, absolute or `res://`.
- `--nodes` (scenario mode only, repeatable, >= 1 required): node path relative to the scene root (`%Unique` allowed);
  `ID` defaults to the last path segment lower-cased without `%`; props default by class (§3.2).
- `--metric` (scenario mode): any non-window metric of §2.5 with params, e.g. `--metric jump.apex_px:action=jump`.
- `--rates 30,60,120`: rerun every probe at each tick rate with tick fields scaled (§3.4); metrics compared in
  seconds; the base rate (suite/scenario `tick_rate`) must be in the list, else rc 2. Ints 10..240.
- `--movie [PROBE]`: one extra Xvfb run per probe (or only PROBE) writing `artifacts/movie/<probe>.avi` (§3.5).
- `--propose`: write `artifacts/proposed_targets.json` (measured value +- `[feel] propose_margin`, `approved_by: ""`)
  and a "Proposed" table in the report. It never writes a targets file.
- `--approve --from <run dir>`: reads `<run dir>/artifacts/proposed_targets.json`, asks the human per target on the TTY
  (`y/n/e` = accept/skip/edit bounds), then writes the suite's targets file through Godot (§3.6) with `approved_by` =
  `git config user.name` (else `$USER`) and `approved_on` = today. stdin or stdout not a TTY: rc 2
  `[feel.approve-needs-tty]`, nothing written. The A8 hook denies this command to agents (§8).
- Exit codes per contract §2.4: 0 PASS, 1 FAIL, 2 usage/suite/targets schema, 3 internal, 4 env (Godot; `--movie`
  without xvfb-run), 5 WARN.

### 2.2 Stdout (contract §2.3)
Stat lines in order: `project`, `import`, `sync`, `suite` (or `scenario`), `targets`, `runs`, `report`. Then one check
line per measurement (`OK`/`FAIL`/`WARN`/`SKIP`), then findings, then `log:`. With > 20 measurements, `OK` lines after
the 10th fold into one check line `OK   more: <n> metrics in range` (name `more`, keeps the C §2.3 check-line
grammar; R-37). Literal examples:
```
$ tools/harness/h trace res://feel/player.feel.json --project /tmp/h/feel_min
FAIL trace 1 of 11 targets missed, 6 probes, 23 runs (12.4s)
project: /tmp/h/feel_min
import: fresh
sync: fresh
suite: res://feel/player.feel.json (seed 7, 60 Hz)
targets: res://feel/targets.tres (11 targets, 11 approved)
runs: 23 (6 probes, 2 sweeps)
report: /tmp/h/feel_min/.harness/out/20261015T160102Z-trace-5e1a/artifacts/feel_report.md
OK   run.max_speed: 220.0 px/s in [200, 240] px/s
OK   run.accel_time: 6 ticks (0.100 s) in [4, 8] ticks
FAIL jump.coyote_window: 0 ticks (0.000 s) not in [4, 8] ticks
res://feel/targets.tres: [feel.out-of-range] error: jump.coyote_window = 0 ticks, target [4, 8] ticks (approved by fixture-human 2026-10-01) (hint: tune the game's tunables (e.g. a MovementTuning .tres), never the targets)
log: /tmp/h/feel_min/.harness/out/20261015T160102Z-trace-5e1a/

$ tools/harness/h trace res://feel/jump.json --nodes Player --metric jump.apex_px:action=jump --project /tmp/h/feel_min
PASS trace 1 metric, 121 ticks (0.6s)
project: /tmp/h/feel_min
import: fresh
sync: fresh
scenario: res://feel/jump.json (seed 7, 120 ticks @ 60 Hz)
trace: .harness/out/20261015T160300Z-trace-0b2c/artifacts/traces/jump.csv (121 rows x 9 columns)
OK   jump.apex_px: 81.4 px (no target)
log: .harness/out/20261015T160300Z-trace-0b2c/
```
Verdict reason (suite): `<k> of <n> targets missed, <p> probes, <r> runs (<t>s)`; all pass: `<n>/<n> targets met, ...`.
Check-line detail: `<value> <unit>[ (<seconds> s)] in|not in [<min>, <max>] <target unit>` or `(no target)`;
undefined metrics: `FAIL <name>: undefined (<reason>)`.

### 2.3 Feel suite file (JSON Schema; builder ships `tools/harness/schemas/feel.schema.json`)
```json
{"$id":"harness.feel/1","type":"object","additionalProperties":false,"required":["schema","trace","probes"],
 "properties":{
  "schema":{"const":"harness.feel/1"}, "description":{"type":"string","maxLength":500},
  "targets":{"type":"string","pattern":"^res://.+\\.tres$"},
  "trace":{"type":"object","minProperties":1,"propertyNames":{"pattern":"^[A-Za-z0-9_:-]{1,64}$"},
    "additionalProperties":{"type":"object","additionalProperties":false,"required":["node"],"properties":{
      "node":{"type":"string","minLength":1},
      "props":{"type":"array","minItems":1,"items":{"type":"string","pattern":"^[A-Za-z_][A-Za-z0-9_]*(\\(\\))?$"}}}}},
  "marks":{"type":"array","items":{"type":"string","pattern":"^[a-z][a-z0-9_]*$"}},
  "probes":{"type":"array","minItems":1,"items":{"type":"object","additionalProperties":false,
    "required":["id","scenario","metrics"],"properties":{
      "id":{"type":"string","pattern":"^[a-z][a-z0-9_]*$"},
      "scenario":{"type":"string","pattern":"^res://.+\\.json$"},
      "vars":{"type":"object","additionalProperties":{"type":"integer"}},
      "sweep":{"type":"object","additionalProperties":false,"required":["anchor"],"properties":{
        "anchor":{"enum":["leave_floor","land"]}, "var":{"type":"string","default":"k"},
        "anchor_var":{"type":"string","default":"t0"}, "to":{"type":"integer","minimum":1,"maximum":30}}},
      "metrics":{"type":"array","minItems":1,"items":{"type":"object","additionalProperties":false,
        "required":["metric"],"properties":{"metric":{"type":"string"},"name":{"type":"string",
        "pattern":"^[a-z][a-z0-9_]*\\.[a-z0-9_.]+$"},"params":{"type":"object"}}}}}}},
  "derived":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["name","ratio"],
    "properties":{"name":{"type":"string"},"ratio":{"type":"array","minItems":2,"maxItems":2,"items":{"type":"string"}}}}}}}
```
Semantics (violations: rc 2, `[feel.suite] error: <json pointer>: <what>`): measurement names (`name` or else `metric`)
are unique across the suite; unknown metric -> `[feel.unknown-metric]` rc 2; window metrics (§2.5) need `sweep` and
non-window metrics forbid it; each probe scenario must pass A5's `scenario.load()` (its errors are re-reported as
`[run.scenario]`, rc 2); `derived.ratio` names must exist. A sweep scenario must declare `vars` `anchor_var` and `var`.

### 2.4 Tick convention (normative; every metric uses it)
Inherited from A5 §2.2 [Run §3.7 S1]: **row k** of a trace = state sampled after physics step k (row 0 = after `_ready`,
before any step). An input "at tick p" is applied before step p, so the game sees it (`just_pressed` true) during step
p and row p is the first row showing its effect. Column `in.<action>` at row k = strength the game saw during step k,
so the **press tick** p of an action = first k >= 1 with `in.a(k) > 0` and `in.a(k-1) == 0`; the **release tick** r =
first k > p with `in.a(k) == 0`. Row 0 reports `is_on_floor = 0` before the first `move_and_slide` [Run], so floor
events are searched from k >= 2.
- **Durations count physics steps**: "event at row t caused by an input at tick p" lasts `t - p + 1` ticks (the
  steps p..t). An instant response therefore measures **1**, never 0. Seconds = ticks / tick_rate.
- **Leave tick L** = first k >= 2 with `floor(k)=0, floor(k-1)=1` (the step in which the body walked off).
  **Land tick D** = first k > takeoff with `floor(k)=1, floor(k-1)=0`. **First grounded step G = D + 1** (the first
  step in which the game's `is_on_floor()` is true again).
- **Coyote window** C = the largest c >= 0 such that a fresh press at every tick L+1..L+c produces a jump (press at L
  is still a ground jump: the game sees the floor in step L). **Buffer window** B = the largest b >= 0 such that a
  fresh press at every tick G-1..G-b (while airborne) produces a jump at landing (press at G is a ground jump).
  "Produces a jump" is the acceptance test of §3.3 step 3 (vy against the offset-0 reference takeoff).
- Consequence [Run §3.7 S2]: a controller with a counter `N = 6` measures C = 5 or 6 and B = 4 or 5 depending on
  whether it decrements before or after its check. The harness does not "fix" this: humans set targets in measured
  units, so the number that ships is the number the player gets.

### 2.5 Metric catalogue v0 (pure Python, `harness.feel`; y is down in Godot, heights are reported up-positive)
Columns used: body `B` (param `body`, default `player`): `B.position.x/.y`, `B.velocity.x/.y`, `B.is_on_floor`;
camera `C` (param `camera`, default `camera`): `C.get_screen_center_position.x/.y`, `C.offset.x/.y`. Common params:
`action` (cause input; defaults per metric), `axis` (`x`|`y`, default `x`), `frac` (`[feel] reach_frac`, 0.95),
`eps` (`[feel] settle_eps_px`, 1.0). p = press tick of `action`, r = its release tick.
| Metric | Unit | Default action | Definition (undefined -> `feel.metric-undefined` with the reason) |
|---|---|---|---|
| `run.max_speed` | px/s | `right` | max abs(vx(k)) for k in [p, r-1] (r absent: to end) |
| `run.accel_time` | ticks | `right` | t* - p + 1, t* = first k >= p with abs(vx) >= frac x vref; vref = param `vmax` or run.max_speed |
| `run.decel_time` | ticks | `right` | t* - r + 1, t* = first k >= r with abs(vx) <= (1-frac) x abs(vx(r-1)); undefined if vx(r-1)=0 |
| `jump.takeoff_speed` | px/s | `jump` | -vy(T); T = first k in [p, p+3] with vy(k) < -1; none: undefined "no takeoff within 3 ticks of press" |
| `jump.apex_px` | px | `jump` | y(T-1) - min y(k), k in [T, D-1] |
| `jump.time_to_apex` | ticks | `jump` | A - T + 1; A = first k in [T, D-1] with y(k) = that min |
| `jump.fall_time` | ticks | `jump` | D - A |
| `jump.air_time` | ticks | `jump` | D - T + 1 (= time_to_apex + fall_time) |
| `jump.fall_rise_ratio` | ratio | `jump` | fall_time / time_to_apex |
| `jump.coyote_window` | ticks | `jump` | C of §2.4 (sweep, anchor `leave_floor`) |
| `jump.buffer_window` | ticks | `jump` | B of §2.4 (sweep, anchor `land`) |
| `camera.lag_px` | px | `right` | max abs(cam(k) - body(k)) on `axis`, k in [p, s]; s = last k with abs(body(k)-body(k-1)) > 1e-6 |
| `camera.settle_time` | ticks | `right` | t* - s; t* = first k >= s with abs(cam(j) - body(end)) <= eps for all j >= k; instant camera = 0 |
| `camera.overshoot_px` | px | `right` | max(0, max over k >= s of d x (cam(k) - body(end))), d = sign(body(end) - body(p-1)) |
| `camera.residual_offset_px` | px | none | length of `C.offset` at the last row (shake must decay to exactly 0) |
| `tween.duration` | ticks | param | column `col` (required); cause p = press of `action` or param `from_tick`; v1 = param `to` or col(end); t* = first k >= p with abs(col(j)-v1) <= eps for all j >= k; value t* - p + 1 |
`ticks` metrics show ticks and seconds; a target with unit `s` compares seconds. `derived` = `value(a) / value(b)`
(`ratio`; undefined if b = 0), e.g. `jump.cut_ratio` = tap apex / hold apex. Sweeps (§3.3): offset 0 must jump, else
`[feel.sweep] error: reference press at tick <p> did not jump`.

### 2.6 Trace files (`<run dir>/artifacts/traces/<probe>[_k<off>][_<rate>hz].csv` + `.meta.json`)
- CSV, header row then one row per tick 0..ticks. Columns: `tick`, then per trace id in suite order, per prop:
  `<id>.<prop>` (`()` dropped; Vector2/2i -> `.x`,`.y`; Vector3 -> `.x`,`.y`,`.z`; Color -> `.r..a`; bool -> 0/1; int;
  float `%.6f`; String/StringName raw with `,` `"` newlines replaced by `_`), then `mark.<name>` per declared mark
  (sample-and-hold, initial empty), then `in.<action>` per action used in the scenario's `inputs` (sorted).
- Meta (`harness.trace/1`): `{"schema","scenario","tick_rate","seed","ticks","rows","columns":[{"name","node","prop",
  "type"}],"vars":{..},"godot":..}`. Rows must equal ticks + 1, else `[feel.trace-incomplete] error`.
- `artifacts/metrics.json` (`harness.feel-metrics/1`): `{"rates":[60],"measurements":{name:{"metric","probe","value",
  "unit","seconds"|null,"by_rate":{"60":v},"target":{..}|null,"verdict":"pass|fail|warn|none|undefined","reason"}}}`.
- `artifacts/feel_report.md` (the human gate artefact, D4): suite, git commit if any, targets file + approvals, a table
  `| metric | measured | target | approved by | verdict | clip |`, the per-rate table when `--rates`, sweep tables
  (offset -> jumped y/n), "Proposed (needs human approval)" when `--propose`, and the line "The agent measured these
  numbers; it did not judge feel." Images and clips are linked by relative path, never printed.

### 2.7 In-engine APIs (installed by `h sync`; files in `addons/harness/`; no `class_name`, like A5)
```gdscript
# Trace  (addons/harness/trace.gd, extends Node, autoload "Trace"). Dormant unless --trace=<spec> is in user args.
func is_active() -> bool
func mark(channel: String, value: Variant) -> void   # game-reported channel, e.g. Trace.mark("state", "fall");
    # recorded in column mark.<channel> from the current tick on (sample-and-hold); undeclared channel or dormant: no-op
# FeelTarget  (addons/harness/feel_target.gd, extends Resource)
@export var metric: String          # measurement name, e.g. "jump.coyote_window"
@export var min_value: float        # inclusive; one-sided bounds use -1e9 / 1e9
@export var max_value: float
@export var unit: String            # px | px/s | ticks | s | ratio (must match the metric's unit family)
@export var approved_by: String     # human name; "" / provisional* / agent* / claude* / ai / bot = NOT approved
@export var approved_on: String     # YYYY-MM-DD
@export var note: String
# FeelTargets  (addons/harness/feel_targets.gd, extends Resource)
@export var tick_rate: int = 60     # rate the tick-unit targets were set at (converted via seconds otherwise)
@export var targets: Array[Resource] = []   # FeelTarget instances (sub-resources)
```
Approved iff `approved_by` matches none of `^$|^(?i:provisional|agent|claude|ai$|bot$)` and `approved_on` is
`YYYY-MM-DD`. Targets file errors (missing, not FeelTargets, duplicate metric, min > max, bad unit): rc 2
`res://feel/targets.tres: [feel.targets] error: <what>`.

### 2.8 Rule ids (`feel.`) and severities
`feel.out-of-range` (error if the target is approved, warning if not), `feel.unapproved` (warning, one per targets
file: `<n> of <m> targets not approved by a human`), `feel.no-targets` (warning: suite without `targets`),
`feel.no-target` (info), `feel.target-unmeasured` (warning), `feel.metric-undefined` (error), `feel.sweep` (error),
`feel.window-gap` (warning: a later offset jumped after an earlier one failed), `feel.rate-dependent` (error),
`feel.camera-idle` (warning: traced Camera2D not in physics process mode), `feel.bind` (error: node/prop missing or
freed), `feel.trace-incomplete` (error), `feel.not-synced` (rc 2), `feel.suite`, `feel.unknown-metric`,
`feel.targets`, `feel.approve-needs-tty` (rc 2). Locations: target verdicts -> targets file; `bind`/`sweep`/
`metric-undefined`/`window-gap` -> probe scenario; `camera-idle` -> camera's scene; rc 2 rules -> the file at fault.

### 2.9 Config (`harness.toml`, `CONFIG_TABLE = "feel"`)
`reach_frac = 0.95`, `settle_eps_px = 1.0`, `rate_tol = 0.10` (relative), `sweep_to = 10` (default sweep `to`),
`propose_margin = 0.10` (relative; ticks at least +-1). Timeout kinds: `scenario`, `movie`, `runner` (contract).

## 3. Design

### 3.1 Files (builder B7 writes exactly these)
`tools/harness/harness/verbs/trace.py` (CLI, orchestration, output), `tools/harness/harness/feel.py` (stdlib only:
trace reading, metric catalogue, windows, rate comparison, target judging, report rendering),
`tools/harness/schemas/feel.schema.json`, `addons/harness/{trace,feel_target,feel_targets}.gd`,
`addons/harness/runners/feel_targets.gd`. Nothing ported verbatim; `research/scripts/rp1/{plat_probe.gd,score_t1.py}`
show what this replaces (and the error to avoid: injecting from `_physics_process`).

### 3.2 Trace autoload (`trace.gd`)
`_ready`: scan `OS.get_cmdline_user_args()` for `--trace=<abs json>` (written by `trace.py`: `{"out","meta","ticks",
"tick_rate","columns":[{"id","node","props"}],"marks","actions"}`); absent -> dormant (no signal connections, `mark`
returns at once). Active: connect `Harness.tick_completed` (A5) and sample on every call k = 0..ticks:
1. At k = 0 resolve nodes relative to `get_tree().current_scene` (`get_node_or_null`, `%Name` ok). Missing node or
   prop -> print `@@H {"t":"finding","rule":"feel.bind","severity":"error",..}` naming id/path/prop; column stays empty.
   Props omitted: CharacterBody2D -> `position, velocity, is_on_floor(), is_on_wall()`; Camera2D ->
   `get_screen_center_position(), offset`; other Node2D -> `position`; else `[feel.bind]` "props required".
   A Camera2D with `process_callback == CAMERA2D_PROCESS_IDLE` -> `[feel.camera-idle]` warning (frame-rate dependent).
2. Value = `node.call(m)` for `m()` props, else `node.get(p)`; flatten per §2.6 with the type fixed at row 0 (a later
   type change -> empty cell + one `[feel.bind]` warning). A node freed later -> empty cells + one warning.
3. Write the row with `FileAccess` (opened at k = 0); at k = ticks write the meta JSON and close. Never print the
   `done` record, never call `quit()` (autoloads can override the runner's rc, A1 §3 spike).

### 3.3 Verb flow (`trace.py`)
1. Resolve project, config, suite (`feel.schema.json` + semantics) or scenario + `--nodes`. Check `Trace` (and A5's
   `required_autoloads`) are declared in project.godot `[autoload]`, else rc 2 `[feel.not-synced]` `Trace autoload not
   declared in project.godot (add "Trace" to [harness] autoloads, run h sync)`. `sync.ensure_synced`, `ensure_imported`.
2. Targets (suite with `targets`): one `runner` invocation of `runners/feel_targets.gd --mode=read --in=<res path>`
   -> `@@H data` with all fields; validate (§2.7).
3. Per probe, per rate: resolve the scenario (`scenario.load(path, vars=probe.vars)`), write
   `artifacts/scenarios/<probe>[_k][_hz].json` (`scenario.write_resolved`), call A5 `harness.replay.run_scenario(run,
   project, <resolved json>, fps=tick_rate, global_seed=g(seed,'A'), out_dir=<run dir>/artifacts/replays/<probe>..,
   extra_user_args=["--trace=<spec>"], kind="scenario")` (R-19); the verb adds `result.findings` to the Run (returned,
   not added, like `Invocation` R-31 [U until A5 v2 states it]). The helper evaluates no asserts/goldens and adds no
   `run.no-asserts`. Sweeps: (a) **anchor run** with the scenario's
   default vars; find L (`leave_floor`) or D (`land`, after the first takeoff) in its trace; missing, or not before
   the first probe-press tick -> `[feel.sweep]` error. (b) set `anchor_var` = L (coyote, presses at `$t0+$k`) or
   G = D+1 (buffer, presses at `$t0-$k`); run offsets 0, 1, ... `to`; stop 2 offsets after the first failure.
   Acceptance: coyote offset c jumps iff min vy over rows [p, p+3] <= 0.5 x vy_ref; buffer offset b iff min vy over
   rows [G, G+2] <= 0.5 x vy_ref; vy_ref = takeoff vy of offset 0. A buffer offset whose press tick is <= the anchor
   press's release tick is not run (sweep capped, info). Window = longest all-true prefix of offsets >= 1 (§2.4).
4. Compute metrics (`feel.measure`) per probe/rate; derived ratios; judge against targets (§3.6); `--rates`
   comparison (§3.4); write metrics.json + feel_report.md; `--propose`; `--movie` (§3.5).
5. Verdict: worst of invocations (contract §2.8.6; a runtime `SCRIPT ERROR` in any replay fails), runner findings,
   metric verdicts. Exactly one finding per failed/undefined measurement.

### 3.4 Rate sweep (`--rates`)
For rate R vs base rate R0: set scenario `tick_rate` = R; every resolved integer tick field (`ticks`, input/command
`tick`, `hold`, dump/assert ticks and `during`) -> `round_half_up(v x R / R0)`, minimum 1; sweep `to` -> `ceil(to x R /
R0)`; `from_tick` params likewise. Each measurement in seconds (ticks / R; px and px/s as is): spread =
`max(0, (max - min) - slack) / max(abs(v_R0), 1e-9)`, slack = `1 / min(R)` s for tick metrics, else 0. spread > `rate_tol` -> `[feel.rate-dependent] error: <name> 0.167 s @30 Hz, 0.083 s @60 Hz, 0.042 s @120 Hz (spread 200%)` (hint:
use seconds x delta, not per-tick counters). Targets are judged at the base rate only.

### 3.5 Movie (human gate clip)
Per probe (anchor run for sweeps): `replay.run_scenario(..., kind="movie", display="xvfb", extra_args=["--write-movie",
"<abs>/movie/<probe>.avi", "--fixed-fps", "<tick_rate>"], extra_user_args=[same --trace spec])` (R-19, R-42; A7's own
path, independent of A6 `--movie`). The movie trace must equal
the headless trace byte for byte (else `[feel.trace-incomplete]` warning "movie run diverged"); physics does not depend
on rendering [Run §3.7 S4]. Movie size = the project's window size (`--resolution` was ignored [Run]). No xvfb-run: rc 4.

### 3.6 Target judging and approval writing
Name match: measurement name == `FeelTarget.metric`. Units: same family required (`ticks`<->`s` convert via the
measured rate; `px`, `px/s`, `ratio` exact), else `[feel.targets]` rc 2. Inclusive bounds; values compared after
rounding to 6 decimals. Approved & out of range -> error; unapproved -> warning; plus one `[feel.unapproved]` per file
with any unapproved target. Measurement without target -> info, check line `(no target)`. Writing (`--approve`):
`runners/feel_targets.gd --mode=write --in=<abs json> --out=res://...` builds FeelTarget sub-resources and
`ResourceSaver.save`; the verb then re-reads the file with `--mode=read` and must get the same values (else rc 3).
Existing targets with other names are kept; same-name targets are replaced only if the human accepted them.

### 3.7 Spikes [Run] (scratchpad `a7/proj`: CharacterBody2D, floor or 60 px ledge, A5-style `-s` runner that records
row k after physics step k from MainLoop `_process` and injects the next tick's inputs with `parse_input_event` + flush)
- **S1 convention.** Press at 10: row 9 `vy 0 floor 1`, row 10 `y 277.26 vy -400 floor 0 jump 1`; row 0 `floor 0`.
- **S2 windows (60 Hz, N = 6, 13 offsets each).** decrement-then-check: coyote L=22, accepted 0..5 -> C = 5; buffer
  D=29, accepted 0..5 -> B = 5. check-then-decrement: C = 6, B = 4. No coyote/no buffer: offsets {0} -> 0 and 0.
  Time-based coyote 0.1 s: 3 / 6 / 12 ticks at 30 / 60 / 120 Hz = 0.100 s each; tick counter N = 6: 5 ticks at every
  rate = 0.167 / 0.083 / 0.042 s. ~90 replays in 32.2 s wall: **0.35 s per run**, a 13-offset sweep ~4.5 s.
- **S3 Camera2D headless.** `position_smoothing_speed 5`, physics callback: `get_screen_center_position().x` lags
  (t29 body 97.17 cam 60.90; t119 216.33 vs 216.06), identical at `--fixed-fps` 60 and 120 (md5 95e3b00e both).
  Idle callback: 57.60 at fps 60 vs 56.99 at fps 120 (md5 a10656d1 vs 3dd169ee) -> `feel.camera-idle`.
- **S4 movie.** `xvfb-run -a ... --rendering-method gl_compatibility --audio-driver Dummy --write-movie m.avi
  --fixed-fps 60 -s runner.gd`: rc 0, 3.4 s wall, 120 frames, 1.9 MB MJPEG AVI at 1152x648 although
  `--resolution 320x180` was passed; trace identical to headless (md5 2ec18cb5 both); only benign log lines.

### 3.8 Budgets
Fixture suite (7 probes, 2 sweeps, ~33 replays): <= 20 s warm; `--rates 30,60,120` <= 60 s; scenario mode <= 3 s;
`--movie` adds <= 6 s per probe. `feel.measure` on a 36,000-row trace <= 1 s. Replays run sequentially (A5 §8 [U]).

## 4. Acceptance criteria (fixture `feel_min` copied per B3 unless stated; every result passes `assert_contract`)
Unit layer (`harness.feel`, synthetic CSVs of §6, values hand-computed here):
- AC-07.1 `run_ramp.csv`: `run.max_speed` 220, `run.accel_time` 6 (0.1 s), `run.decel_time` 6. Same data with
  `frac` 0.5: accel 3. `vx` instant (row p = 220): accel 1. [unit]
- AC-07.2 `jump_arc.csv`: takeoff_speed 600, apex_px 30, time_to_apex 5, fall_time 5, air_time 10, fall_rise_ratio
  1.0; a copy with no takeoff -> undefined "no takeoff within 3 ticks of press". [unit]
- AC-07.3 Press/release ticks derive from `in.*` columns exactly per §2.4 (press at row 3 -> p = 3; never row 0). [unit]
- AC-07.4 `feel.window({0:T,1:T,2:T,3:T,4:F,5:F,6:F})` -> (3, gap False); `{0:T,1:F,2:F}` -> (0, False);
  `{0:T,1:T,2:F,3:T,4:F}` -> (1, True); `{0:F,...}` -> sweep error. [unit]
- AC-07.5 `camera_step.csv`: lag_px 40, settle_time 4, overshoot_px 2; `eps` 5 -> settle 2; camera equal to body ->
  settle 0, overshoot 0. `residual_offset_px` of offset (3, 4) at end = 5. [unit]
- AC-07.6 `tween.duration` on `tween.csv` (col 0 -> 100 linearly over ticks 5..14, cause tick 5) -> 10. [unit]
- AC-07.7 Rate comparison: {30:0.1, 60:0.1, 120:0.1} ok; {30:0.1667, 60:0.0833, 120:0.0417} rate-dependent;
  {30:3/30, 60:7/60, 120:12/120} ok only thanks to the 1/30 s tick slack. [unit]
- AC-07.8 Judging: ticks target at tick_rate 60 vs measurement at 120 Hz converts via seconds; unit mismatch
  (`px` vs `ticks`) -> targets error; approval detection for "", "provisional-default", "Claude", "agent-p7", "bot"
  (not approved) and "J. Whitford" + 2026-10-01 (approved); bounds inclusive after 6-decimal rounding. [unit]
Contract layer:
- AC-07.9 `h trace res://feel/player.feel.json` -> rc 0, `PASS trace 11/11 targets met`, stats in §2.2 order,
  12 `OK` check lines (one `jump.tap_apex_px ... (no target)`), `runs:` >= 20, `report:` file exists and contains every metric name and the agent-did-not-judge
  line; wall <= 20 s warm. [contract]
- AC-07.10 Artifacts: `metrics.json` validates (`harness.feel-metrics/1`), each measurement has `value` and `verdict
  pass`; `traces/run.csv` has `ticks+1` rows and columns `tick`, `player.position.x`, `player.velocity.x`,
  `player.is_on_floor`, `camera.get_screen_center_position.x`, `in.right`; meta rows == ticks+1. [contract]
- AC-07.11 Fixture measured values: `jump.coyote_window` in [5, 6] and `jump.buffer_window` in [4, 6] (0.1 s timers;
  the float edge at exactly 6 x 1/60 decides 5 vs 6 [Run S2]); sweep tables in the report list offsets 0..>= C+1 with y/n. [contract]
- AC-07.12 Two consecutive `h trace` runs give byte-identical `traces/*.csv` and `metrics.json` `measurements`. [contract]
- AC-07.13 Scenario mode: `h trace res://feel/jump.json --nodes Player --metric jump.apex_px:action=jump` -> rc 0,
  `OK   jump.apex_px: <v> px (no target)`, `trace:` stat names a CSV with 9 columns; no `--nodes` -> rc 2;
  `--metric jump.coyote_window` -> rc 2 (needs a suite). [contract]
- AC-07.14 `--rates 30,60,120` on the clean fixture -> rc 0, report has a per-rate table; with FAULT-A7-08 planted ->
  rc 1 `[feel.rate-dependent]` naming `jump.coyote_window` and all three rates. `--rates 30,120` (base missing) -> rc 2. [contract]
- AC-07.15 Suite errors -> rc 2, no Godot replay in run.json: unknown metric, duplicate name, window metric without
  sweep, sweep scenario lacking `t0`, missing targets file, a target with min > max (fixture variant). [contract]
- AC-07.16 Targets with `approved_by` "" on all entries -> rc 5, `[feel.unapproved]` `11 of 11`; with FAULT-A7-01
  also planted -> still rc 5 and `[feel.out-of-range] warning`; `--strict` -> rc 1. [contract]
- AC-07.17 `--propose` -> `artifacts/proposed_targets.json` with 11 entries, each `approved_by ""`, bounds containing
  the measured value; `feel/targets.tres` byte-identical before/after. [contract]
- AC-07.18 `--approve --from <dir>` with stdin from a pipe -> rc 2 `[feel.approve-needs-tty]`, targets unchanged.
  Under a pty (python `pty`) answering `y` to all: rc 0, re-read targets have `approved_by` == the git/`$USER` name,
  `approved_on` == today, bounds from the proposal. [contract (pty) / e2e]
- AC-07.19 `--movie run` under Xvfb -> `artifacts/movie/run.avi` exists (> 10 KB), report links it, stdout has no
  image data; `PATH` without xvfb-run -> rc 4. [contract, xvfb, slow]
- AC-07.20 Suite with `trace.player.node = "Playr"` -> rc 1 `[feel.bind]` naming `Playr`. Missing `Trace` in
  `[autoload]` -> rc 2 `[feel.not-synced]` containing `h sync`. [contract]
- AC-07.21 Runtime `SCRIPT ERROR` in player.gd at tick 50 of the run probe (all targets pass) -> rc 1
  `[godot.script-error]`. [contract]
- AC-07.22 gdUnit4 (`tests/gd/a7/`): Trace dormant without `--trace` (`is_active()` false, `mark` no-op, no file);
  FeelTargets save + load round-trip keeps all fields. [gd]
- AC-07.23 Each planted feel fault (FAULT-A7-01..06) fails exactly its metric: one `FAIL` check line, named as in §5,
  every other measurement `OK`. [selftest via `not_regex`]
- AC-07.24 `h selftest --area A7` -> must faults CAUGHT, CLEAN-A7-* PASS, wall <= 300 s. [contract, slow]
Untestable automatically: whether the targets are good taste (human, D10); that agents cannot edit targets (A8 hook).

## 5. Seeded faults (fixture `feel_min`, verb `trace`, args `res://feel/player.feel.json` unless noted; `must` unless noted)
Hook lines are exact text in `scripts/player.gd` / `feel/targets.tres` (§6); ops are `replace` count 1 unless noted.
FAULT-A7-01..06 each also carry `not_regex = ['^FAIL +(?!<its metric>:)[a-z]+\.[a-z0-9_.]+:']` (check lines only, so
the verdict line `FAIL trace ...` never matches; AC-07.23: exactly one metric fails; R-37).
| ID | Planted | Expect |
|---|---|---|
| FAULT-A7-01 | `	velocity.x = move_toward(velocity.x, dir * MAX_SPEED, ACCEL * delta) # FEEL-ACCEL` -> `	velocity.x = dir * MAX_SPEED # FEEL-ACCEL` (instant velocity) | rc 1, `^FAIL +run\.accel_time: 1 tick`, not_regex `^FAIL +(?!run\.accel_time:)[a-z]+\.[a-z0-9_.]+:`, <= 60 s |
| FAULT-A7-02 | `const FALL_GRAVITY := 1960.0 # FEEL-FALL` -> `const FALL_GRAVITY := 980.0 # FEEL-FALL` (constant gravity) | rc 1, `^FAIL +jump\.fall_rise_ratio:`, not_regex `^FAIL +(?!jump\.fall_rise_ratio:)[a-z]+\.[a-z0-9_.]+:` |
| FAULT-A7-03 | `const COYOTE_S := 0.1 # FEEL-COYOTE` -> `0.0` | rc 1, `^FAIL +jump\.coyote_window: 0 ticks`, not_regex `^FAIL +(?!jump\.coyote_window:)[a-z]+\.[a-z0-9_.]+:` |
| FAULT-A7-04 | `const BUFFER_S := 0.1 # FEEL-BUFFER` -> `0.0` | rc 1, `^FAIL +jump\.buffer_window: 0 ticks`, not_regex `^FAIL +(?!jump\.buffer_window:)[a-z]+\.[a-z0-9_.]+:` |
| FAULT-A7-05 | `const JUMP_CUT := true # FEEL-CUT` -> `false` (no variable jump) | rc 1, `^FAIL +jump\.cut_ratio:`, not_regex `^FAIL +(?!jump\.cut_ratio:)[a-z]+\.[a-z0-9_.]+:` |
| FAULT-A7-06 | `const CAM_SMOOTH := true # FEEL-CAM` -> `false` (camera snaps) | rc 1, `^FAIL +camera\.settle_time: 0 ticks`, not_regex `^FAIL +(?!camera\.settle_time:)[a-z]+\.[a-z0-9_.]+:` |
| FAULT-A7-07 | targets.tres: every `approved_by = "fixture-human"` -> `approved_by = "claude"` (count 11; agent self-approval) | rc 5, `\[feel\.unapproved\].*11 of 11` |
| FAULT-A7-08 | `const COYOTE_IN_TICKS := false # FEEL-COYOTE-TICKS` -> `true` (6-tick counter); args + `--rates 30,60,120` | rc 1, `\[feel\.rate-dependent\].*coyote`, <= 150 s |
| FAULT-A7-09 | write `feel/badbind.feel.json` = player.feel.json with node `Playr`; args `res://feel/badbind.feel.json` | rc 1, `\[feel\.bind\].*Playr` |
| FAULT-A7-10 (nice) | `const CAM_PHYSICS := true # FEEL-CAM-PROC` -> `false` (idle camera) | rc 5, `\[feel\.camera-idle\]` |
| FAULT-A7-11 | delete `feel/targets.tres` | rc 2, `\[feel\.targets\]` |
| CLEAN-A7-01 | none | rc 0, `^PASS trace 11/11 targets met` |
| CLEAN-A7-02 | none; args + `--rates 30,60,120` | rc 0, PASS |

## 6. Fixtures needed (test-writer T7)
`tests/fixtures/projects/feel_min/` (hand-written, no `addons/`; FIXTURE.md: owner A7, `h trace` PASS):
- `project.godot`: contract minimum; `[autoload]` `Harness`, `Rng`, `CommandBus`, `Trace` =
  `"*res://addons/harness/<snake>.gd"`; `[input]` `left`, `right`, `jump` (`"events": []`); `[physics]`
  `common/physics_ticks_per_second=60`, `common/physics_jitter_fix=0.0`; `harness.toml` `[harness] autoloads` with all 4.
- `scenes/flat.tscn` / `scenes/ledge.tscn`: root `Node2D` "Level" with `scripts/level.gd` (`@export var floor_end`;
  4000 / 60). `level.gd._ready` builds a StaticBody2D floor (top at y 300, from x -2000 to `floor_end`) and a
  CharacterBody2D "Player" (`unique_name_in_owner` not needed; 16x32 rect at (0, 284), `player.gd`) with a Camera2D
  child "Camera" (`make_current()` in `_ready`).
- `scripts/player.gd` (all hook lines verbatim, one tab indent inside functions):
  `const MAX_SPEED := 220.0`, `const ACCEL := 220.0 * 10.0` (6 ticks to 95% at 60 Hz), `const DECEL := 220.0 * 10.0`,
  `const JUMP_SPEED := 400.0`, `const RISE_GRAVITY := 980.0`, `const FALL_GRAVITY := 1960.0 # FEEL-FALL`,
  `const JUMP_CUT := true # FEEL-CUT` (release while rising clamps vy to >= -100), `const COYOTE_S := 0.1 # FEEL-COYOTE`,
  `const BUFFER_S := 0.1 # FEEL-BUFFER`, `const COYOTE_IN_TICKS := false # FEEL-COYOTE-TICKS` (`true`: counter 6,
  decrement-then-check), `const CAM_SMOOTH := true # FEEL-CAM` (`position_smoothing_enabled`, speed 5),
  `const CAM_PHYSICS := true # FEEL-CAM-PROC` (`process_callback`). `_physics_process(delta)`: read `is_on_floor()`
  once at the start; `dir = Input.get_axis("left","right")`; if `dir != 0`:
  `	velocity.x = move_toward(velocity.x, dir * MAX_SPEED, ACCEL * delta) # FEEL-ACCEL` else
  `	velocity.x = move_toward(velocity.x, 0.0, DECEL * delta)`; gravity (rise while vy < 0, else fall) when airborne;
  coyote timer refreshed on floor, `-= delta` in air; buffer timer set to `BUFFER_S` on `just_pressed` and `-= delta`
  after the check; jump when `just_pressed or buffer > 0` and `on_floor or coyote > 0`; then `move_and_slide()`;
  `Trace.mark("state", "ground"|"rise"|"fall")`. Constants must give the AC-07.11 windows; T7 records measured
  values in test_notes.md.
- `feel/run.json` (flat; right from tick 1, release at 60, 120 ticks), `feel/jump.json` (flat; jump at 10 hold 60),
  `feel/tap.json` (jump at 10 hold 2), `feel/coyote.json` (ledge; right from 1; `vars {"t0":200,"k":0}`; jump at
  `"$t0+$k"` hold 3; `ticks` `"$t0+$k+40"`), `feel/buffer.json` (flat; jump at 10 hold 3; jump at `"$t0-$k"` hold 1;
  `vars {"t0":200,"k":0}`, ticks `"$t0+40"`), `feel/camera.json` (= run.json, 200 ticks).
- `feel/player.feel.json`: trace `player` -> `Player`, `camera` -> `Player/Camera`; marks `["state"]`; probes `run`
  (run.max_speed, run.accel_time, run.decel_time), `jump` (jump.apex_px, jump.time_to_apex, jump.fall_rise_ratio),
  `tap` (jump.apex_px named `jump.tap_apex_px`, no target),
  `coyote` (sweep `leave_floor`, jump.coyote_window), `buffer` (sweep `land`, jump.buffer_window), `camera`
  (camera.settle_time, camera.lag_px); derived `jump.cut_ratio` = [`jump.tap_apex_px`, `jump.apex_px`]. 12 measurements, 11 targets.
- `feel/targets.tres` (hand-written text resource, FeelTargets with 11 FeelTarget sub-resources, every
  `approved_by = "fixture-human"`, `approved_on = "2026-10-01"`): run.max_speed [200, 240] px/s; run.accel_time [4, 8]
  ticks; run.decel_time [4, 8] ticks; jump.apex_px [70, 95] px; jump.time_to_apex [0.3, 0.5] s; jump.fall_rise_ratio
  [1.2, 3] ratio; jump.cut_ratio [0.05, 0.7] ratio; jump.coyote_window [4, 8] ticks; jump.buffer_window [3, 8] ticks;
  camera.settle_time [20, 120] ticks; camera.lag_px [0, 70] px (one-sided, so FAULT-A7-06 fails only settle_time). T7 adjusts a bound only if the clean fixture measures
  outside it, and records why.
- Variants: `feel_noautoload/` (no `Trace` autoload, AC-07.20); suite variants for AC-07.15 live in test tmp dirs.
- `tests/fixtures/feel_csv/` (AC-07.1-6; each CSV + `.meta.json` with `tick_rate` 60): `run_ramp.csv` (press right
  at tick 3, `vx(k) = min(220, 40(k-2))` for k >= 3, release at 20, then -40 per tick to 0 at 25),
  `jump_arc.csv` (floor 1 to row 9, press jump at 10; y rows 9..19 = 300,290,282,276,272,270,271,274,280,290,300;
  vy = 0,-600,-480,-360,-240,-120,60,180,360,600,0; floor 1 again at 19), `camera_step.csv` (press right at 1;
  body x = 10k to k = 10 then 100; cam x rows 1..15 = 0,5,12,20,28,36,44,52,56,60,80,95,102,100.5,100.2, then 100;
  offset (3,4) on the last row), `tween.csv` (col `box.position.x` 0 to row 4, 10(k-4) for k = 5..14, then 100;
  `from_tick` 5).

## 7. Build order (B7; each step ends green on the named ACs)
1. `feel.py` trace reading, press/release, catalogue, window, rate spread, judging -> AC-07.1-8.
2. `trace.gd`, `feel_target(s).gd`, `runners/feel_targets.gd` -> AC-07.22.
3. `verbs/trace.py` scenario mode -> AC-07.13, 20, 21.
4. Suite mode: schema, targets read, probes, sweeps, report -> AC-07.9-12, 15, 16, 23.
5. `--rates` -> AC-07.14. 6. `--propose`/`--approve` -> AC-07.17, 18. 7. `--movie` -> AC-07.19. 8. Selftest -> AC-07.24.

## 8. Out of scope, open questions, assumptions
Out of scope (v0): 3D (RP.B), slopes/platforms (P02), hit-stop/i-frames (P05; A5 warns `run.time-scale`), view-rect
and look-ahead (RP.D), auto tuning variants, animation consistency (RP.C), a git "targets changed" check, batched or
parallel replays.
Open [U]:
1. Sweeps assume deterministic replays (A5 `--twice`); a nondeterministic controller can give noisy windows. v0 does
   not re-check; the skill tells the agent to run `h run --twice` first.
2. Buffer acceptance uses rows [G, G+2]; a controller that delays the buffered jump by > 2 steps counts as "no jump".
3. `Input.get_action_strength` as the `in.*` source assumes A5 injects InputEventAction with strength (A5 §3.2).
4. `--write-movie` + `-s` was verified with a stand-in runner, not A5's. 5. No `class_name` on FeelTarget makes
   inspector creation clumsy; `--approve` is the main path.
Deviations from 00_contract / plan (all accepted by REVIEW; R-id given):
- D-a (accepted, R-01): unit tests import `harness.feel` (pure: `read_trace`, `measure`, `window`, `rate_spread`,
  `judge`, `is_approved`); it is on the R-01 closed list.
- D-b (accepted, R-48): plan fields `min`/`max` are `min_value`/`max_value` (`min`/`max` shadow GDScript built-ins).
- D-c (accepted, R-17, R-48): plan fault idea "instant velocity (accel ticks = 0)" measures 1 under §2.4 (durations
  count steps); §2.4 and §2.5 names are canonical for A9 and RP.A/RP.D.
- D-d (accepted, R-48): `--nodes` gains an optional `ID=` prefix; the Trace autoload samples on A5's
  `Harness.tick_completed`.
- Fold line `OK   more: <n> metrics in range` (R-37) and fault `not_regex` on check lines only (R-37): fixes, not
  deviations.
Assumptions on other areas (resolved by REVIEW):
- A5: (1) the runner emits `Harness.tick_completed(0)` in `_begin` after recording tick 0 (R-18; §3.2 needs row 0);
  (2) `harness.replay.run_scenario(run, project, resolved, *, fps, global_seed, out_dir, extra_user_args, extra_args,
  display, kind) -> RunResult` takes the resolved file, runs no asserts and adds no `run.no-asserts` (R-19);
  (3) `scenario.load(path, vars=None, seed=None, ticks=None)` and `scenario.write_resolved(d, path)` are public (R-19).
  Unknown `--x=` user args such as `--trace=` are ignored by `scenario.gd` (R-15).
- A1/P0: contract §2.6 default `autoloads` includes `"Trace"` (R-16); `sync.ensure_synced` (R-33) copies the
  `feel_*.gd` files. AC-07.22 [gd] runs through T1's `run_gd_suites("a7")` on `gd_host` (R-39).
- A3 (optional): a static lint for Camera2D `process_callback` idle complements `feel.camera-idle`.
- A6: approval predicate of §2.7 is shared with A6 baselines (R-35). A7's movie path (§3.5) is its own (R-42).
- A8: PreToolUse denies agent Edit/Write on `**/*targets*.tres` lines with `min_value|max_value|approved_by|approved_on`
  and Bash `h trace .*--approve`; skill `godot-feel` documents §2.4, the catalogue, "tune tunables, never targets",
  and "hand the human feel_report.md + clip, never claim it feels good".
- A9 (R-36, R-35, R-17, R-16): the sample's suite lives at `res://feel/player.feel.json` and its probes
  `res://feel/{run,jump,tap,coyote,buffer,camera}.json` run on `res://scenes/platformer/feel_arena.tscn` (level_1 +
  player at Spawn, no SceneManager, so `feel.bind` resolves at row 0); run.* metrics take `params {"action":
  "move_right"}`, trace `camera` -> `Player/Camera2D`. `targets.tres` uses the R-17 names/ranges with `approved_by =
  "provisional-default"`, so `h trace res://feel/player.feel.json` gives rc 5 (only `feel.unapproved` warnings) until
  a human approves at G3. `Trace` is in its `[autoload]`; its Camera2D uses physics process mode.
- RP.A/RP.D: adopt these names and §2.4; new metrics join the catalogue via a planner re-run.
- Plan defaults D1, D2, D4, B7 hold.
