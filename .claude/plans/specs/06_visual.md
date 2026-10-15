# 06 Visual / screenshot check (A6, C8; planner P6)

Status: spec v1, 2026-10-15, Opus planner P6. Conforms to `00_contract.md` v1 (cited "C §x"); deviations in §8.3.
Tags: [Run] verified in §3.7 spikes (Godot 4.7.stable.official.5b4e0cb0f, Xvfb + llvmpipe, Mesa 25.2.8, odiff 4.5.0,
scratchpad `a6/`), [U] unverified. Also answers contract open question (3) (§3.5).

## 1. Purpose and failure modes covered

An LLM cannot judge pixels (D4), and it must not be asked to. A6 turns visuals into numbers that a human-approved
baseline anchors: `h shot` captures deterministic PNGs of a scene or an A5 scenario tick, compares them with approved
baselines and says how many pixels changed; `h shot --layout` checks UI geometry numerically at several window sizes;
`h baseline` keeps "agent proposes, human approves" mechanical.
- **D4** agent never judges visuals: verdicts are pixel counts against an `approved_by` baseline; approval needs a
  human at a TTY (+ A8 hook). Images are never printed or read into context; stdout gives paths only.
- **R1.7** no `--headless` images (dummy renderer, `frame_post_draw` never fires -> hang [Run]); Xvfb +
  gl_compatibility; GL and Vulkan baselines never mixed; odiff gotchas (`--fail-on-layout`, lenient default `-t`).
- **Nondeterminism**: unseeded particles and wall-clock visuals. `--fixed-fps` alone was NOT enough for unseeded
  CPUParticles2D (48 px differ, §3.7 K2); the runner also seeds the global RNG, which made 3/3 runs byte-identical.
  `--twice` proves a shot is stable before it becomes a baseline.
- **F11 noisy output / exit codes lie**: contract grammar; runtime `SCRIPT ERROR` during a capture FAILs even when a PNG
  was written; hang = FAIL `harness.hang`; display failure = rc 4.
- **UI breakage across aspect ratios** (RP.J): off-screen, clipped, overflowing and overlapping Controls at
  1280x720, 1920x1080, 2560x1080, 800x1280, computed headless in one process (§3.7 K6).

## 2. Interfaces

### 2.1 `h shot` (capture, compare, stability, movie)
```
h shot TARGET [--tick N[,N...]] [--name NAME] [--size WxH] [--crop X,Y,W,H | --node NODE]
       [--hide NODE]... [--hide-layer L]... [--seed N] [--twice] [--movie] [--compare [--name NAME]]
h shot TARGET --layout [--sizes WxH[,WxH...]]
```
- `TARGET`: a `.tscn`/`.scn` (scene mode) or an A5 scenario `.json` (scenario mode); cwd-relative, absolute or
  `res://`; must be inside the project (else rc 2). Common flags `--project`, `--strict` (C §2.2).
- `--tick`: physics ticks after the scene's `_ready` at which to capture; each 1..36000; up to 8 values. Tick 0 cannot
  be drawn (physics runs before the first draw, §3.7 K4). Default: scene mode 1, scenario mode the scenario's `ticks`;
  scenario mode requires every N <= `ticks` (rc 2). The image at tick k shows the state after physics step k.
- `--name`: `^[a-z0-9][a-z0-9_.-]{0,63}$`. Shot name = NAME (one tick) or `NAME-t<k>` (several); default
  `<target stem>-t<k>` (`main-t30`).
- `--size WxH` (16..4096 each): window size (`--resolution`). The PNG is the root viewport texture, so its size follows
  the project's stretch settings (640x360 base, `canvas_items` + `keep` at 800x1280 -> 800x450 [Run]).
- `--crop X,Y,W,H` (image pixels) or `--node NODE` (crop to a Control's rect or a CanvasItem's `get_rect()`, mapped
  through `root.get_final_transform() * get_global_transform_with_canvas()`, clamped to the image [Run K5]).
  `NODE` = `%UniqueName` or a path relative to the scene root. Mutually exclusive.
- `--hide NODE` (repeatable): `visible = false` before capture (CanvasItem, CanvasLayer, Node3D).
  `--hide-layer L` (1..20, repeatable): clears bit L in `root.canvas_cull_mask` and in every Camera3D `cull_mask`.
- `--seed N` (default 0): global RNG seed in scene mode (`seed(N)` before the scene loads). Scenario mode uses the
  scenario's seeds (A5); `--seed` there is rc 2.
- `--twice`: capture every shot in two separate processes; any pixel difference -> FAIL `[shot.unstable]`.
- `--movie`: also record every frame (`--write-movie <artifacts>/movie/frame.png`) until the runner quits (scene
  mode: max tick; scenario mode: `ticks`). Stat `movie: <n> frames <dir>`. For the human gate and A7; never compared.
- `--compare`: re-capture every approved baseline of TARGET (§2.3) with the settings stored in its meta and compare.
  `--name` selects one baseline. Any capture flag (`--tick --size --crop --node --hide --hide-layer --seed`) together
  with `--compare` is rc 2 (`--compare takes capture settings from the baseline`). TARGET with no baselines at all:
  FAIL `[shot.no-baseline]` (hint: `h baseline propose`).
- `--layout`: no image; runs §3.4 headless. `--sizes` default from `[shot] layout_sizes`. Scene mode only (rc 2 for a
  scenario). Incompatible with every capture/compare flag (rc 2).
- `--headless` is a declared flag that always gives rc 4: `ERROR shot --headless cannot render images (Xvfb +
  gl_compatibility required)`. rc 4 also for: `xvfb-run` not on PATH, odiff missing (only with `--compare`/`--twice`),
  display start failure after one retry (`[shot.no-display]`), runner reporting a headless display.

Stdout (C §2.3). Stat lines in order: `project`, `import`, `target`, `env`, `twice` (if run), `movie` (if run);
then one check line per shot; then findings; then `log:`. Literal examples:
```
$ tools/harness/h shot res://scenes/main.tscn --tick 30 --project /tmp/h/shot_min
PASS shot 1 shot captured (0.9s)
project: /tmp/h/shot_min
import: fresh
target: res://scenes/main.tscn (scene, ticks 30, 60 fps, seed 0)
env: gl_compatibility | llvmpipe (LLVM 20.1.2, 256 bits) | 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
OK   main-t30: 640x360 /tmp/h/shot_min/.harness/out/20261015T160102Z-shot-1a2b/artifacts/shots/main-t30.png
log: /tmp/h/shot_min/.harness/out/20261015T160102Z-shot-1a2b/

$ tools/harness/h shot res://scenes/main.tscn --compare --project /tmp/h/shot_min
FAIL shot 1 of 1 shots differ from baseline (1.0s)
project: /tmp/h/shot_min
import: fresh
target: res://scenes/main.tscn (scene, 1 baseline)
env: gl_compatibility | llvmpipe (LLVM 20.1.2, 256 bits) | 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
FAIL main-t30: 1650 px (0.72%) differ, exact mode, diff .../artifacts/shots/main-t30.diff.png
res://baselines/scenes/main/main-t30.png: [shot.diff] error: main-t30: 1650 px (0.72%) differ from the approved baseline (exact mode) (hint: if the change is intended, h baseline propose; a human approves)
log: /tmp/h/shot_min/.harness/out/20261015T160140Z-shot-9c0d/

$ tools/harness/h shot res://scenes/hud.tscn --layout --sizes 1280x720,640x360 --project /tmp/h/shot_min  # FAULT-A6-03+08 planted; numbers illustrative
FAIL shot layout: 2 errors, 0 warnings at 2 sizes (0.4s)
project: /tmp/h/shot_min
import: fresh
target: res://scenes/hud.tscn (layout, 8 controls)
FAIL 1280x720: visible 1280x720, 1 error
FAIL 640x360: visible 640x360, 1 error
res://scenes/hud.tscn: [shot.layout-offscreen] error: Health @1280x720: rect (1300,600 54x23) extends 74 px past the right edge
res://scenes/hud.tscn: [shot.layout-clipped] error: Title @640x360: text needs 851 px, has 600 px (hint: autowrap, shorter text or a Container)
log: /tmp/h/shot_min/.harness/out/20261015T160201Z-shot-77aa/
```
Verdict reasons: `<n> shot(s) captured`, `<k> of <n> shots differ from baseline`, `<n> shots stable (twice)`,
`layout: <e> errors, <w> warnings at <s> sizes`; each suffixed ` (<t>s)`. With `--compare` a matching shot prints
`OK   main-t30: identical (exact mode)` or `WARN main-t30: 12 px (0.01%) within 0.1% (tolerant mode, env differs)`.

### 2.2 Rule ids (prefix `shot.`, C §2.7)
| id | sev | loc | when |
|---|---|---|---|
| `shot.diff` | error | baseline PNG | exact mode: >= 1 px differs; tolerant mode: diff% > `threshold_pct` |
| `shot.drift` | warning | baseline PNG | tolerant mode, 0 < diff% <= `threshold_pct` (B7 analogue) |
| `shot.size-mismatch` | error | baseline PNG | capture size != baseline size (odiff rc 21) |
| `shot.renderer-mismatch` | error | baseline meta | baseline `env.renderer` != `gl_compatibility`; no diff is run |
| `shot.no-baseline` | error | target | `--compare` and no approved baseline for TARGET/NAME |
| `shot.baseline-unapproved` | error | baseline meta | only a proposal exists, or meta `status` != approved / empty `approved_by` |
| `shot.baseline-tampered` | error | baseline PNG | sha256 of the PNG != meta `image.sha256` |
| `shot.bad-baseline` | error (rc 2) | baseline meta | meta fails the §2.3 schema |
| `shot.unstable` | error | target | `--twice` captures differ (`<n> px`) |
| `shot.node-not-found` | error | target | `--node`/`--hide` NODE missing (runner finding, rc 1) |
| `shot.crop-outside` | error | target | crop rect has no overlap with the image |
| `shot.no-display` | error (rc 4) | - | `Unable to create DisplayServer` / `Xvfb failed to start` after one retry |
| `shot.headless` | error (rc 4) | - | runner saw `DisplayServer.get_name() == "headless"` |
| `shot.layout-offscreen` | error | scene | visible Control extends > 1 px outside the visible rect |
| `shot.layout-clipped` | error | scene | Label/Button text does not fit (§3.4) |
| `shot.layout-overflow` | warning | scene | Control extends > 1 px outside its parent Control |
| `shot.layout-overlap` | warning | scene | two sibling content Controls intersect (> 4 px^2) outside a Container |
| `shot.approve-needs-tty` | error (rc 2) | - | `h baseline approve` without `/dev/tty` |

### 2.3 Baseline store and `h baseline`
Store (project files; committed by the user): `<project>/<baseline_dir>/<key>/<name>.png` + `<name>.json` (approved),
`<name>.proposed.png` + `<name>.proposed.json` (pending). `<key>` = TARGET's res path without `res://` and extension
(`scenes/main`, `scenarios/jump`). The verb creates `<project>/<baseline_dir>/.gdignore` so Godot never imports
baseline PNGs. Meta JSON Schema (`tools/harness/schemas/baseline.schema.json`):
```json
{"$id":"harness.baseline/1","type":"object","additionalProperties":false,
 "required":["schema","name","target","tick","capture","image","env","status","proposed_at","proposed_by"],
 "properties":{"schema":{"const":"harness.baseline/1"},"name":{"type":"string"},
  "target":{"type":"string","pattern":"^res://"},"tick":{"type":"integer","minimum":1},
  "capture":{"type":"object","additionalProperties":false,"properties":{"size":{"type":["array","null"]},
    "crop":{"type":["array","null"]},"node":{"type":["string","null"]},"hide":{"type":"array"},
    "hide_layers":{"type":"array"},"seed":{"type":["integer","null"]},"fps":{"type":"integer"}}},
  "image":{"type":"object","required":["w","h","sha256"],"properties":{"w":{"type":"integer"},"h":{"type":"integer"},
    "sha256":{"type":"string","pattern":"^[0-9a-f]{64}$"}}},
  "env":{"type":"object","required":["godot","renderer","adapter","api"],"properties":{"godot":{"type":"string"},
    "renderer":{"type":"string"},"adapter":{"type":"string"},"api":{"type":"string"}}},
  "ignore":{"type":"array","items":{"type":"array","minItems":4,"maxItems":4,"items":{"type":"integer"}}},
  "threshold_pct":{"type":"number","minimum":0,"maximum":100},
  "status":{"enum":["proposed","approved"]},"proposed_at":{"type":"string"},"proposed_by":{"type":"string"},
  "approved_at":{"type":["string","null"]},"approved_by":{"type":["string","null"]},"note":{"type":"string"}}}
```
`env.godot` = the full version string from `godot.py` (`4.7.stable.official.5b4e0cb0f`), `adapter`/`api` from the
runner (`RenderingServer.get_video_adapter_name()` / `_api_version()`, the api string carries the Mesa version [Run]).
`ignore` = rectangles `[x1,y1,x2,y2]` passed to odiff `-i` (humans add them in the meta before approving).
```
h baseline propose TARGET [shot capture flags]    # agent or human
h baseline approve TARGET [--name NAME]           # human only
h baseline list [TARGET]
```
- `propose`: runs the capture with `--twice` semantics; unstable -> FAIL `[shot.unstable]`, nothing written. Else
  writes `<name>.proposed.png/.json` (`status: proposed`, `proposed_by` = `$USER` or `unknown`, `approved_*` null),
  overwriting an older proposal, never touching the approved pair. Check line per shot `OK   main-t30: proposed
  <path> (awaiting human approval: h baseline approve res://scenes/main.tscn)`. Verdict PASS rc 0.
- `approve`: needs a controlling terminal: opens `/dev/tty` for the prompt and the answer (stdout keeps the C §2.3
  grammar). No `/dev/tty` -> rc 2, finding `-: [shot.approve-needs-tty] error: approval needs a human at a terminal`,
  nothing changed. For each pending proposal it writes to the TTY the proposed and current PNG paths and the diff
  count vs the current approved PNG, then reads one line; only `yes` approves (anything else skips). Approve = rename
  `.proposed.*` over the approved pair, set `status: approved`, `approved_by` = `git config user.name` (fallback
  `$USER`), `approved_at` = UTC ISO time. Check lines `OK   main-t30: approved by <who>` / `SKIP main-t30: declined`.
  No proposals: `WARN baseline nothing to approve`, rc 5. The A8 hook additionally blocks this command for agents.
- `list`: one check line per baseline: `OK <key>/<name>: approved by <who> <date>`, `WARN ...: proposal pending`,
  `FAIL ...: tampered|unapproved|bad meta`. Verdict WARN when only pending proposals exist.

### 2.4 Config (`harness.toml`, `CONFIG_TABLE = "shot"`)
`[shot] baseline_dir = "baselines"` (str, project-relative), `threshold_pct = 0.1` (float 0..100, tolerant mode),
`color_threshold = 0.1` (float 0..1, odiff `-t` in tolerant mode), `layout_sizes = ["1280x720", "1920x1080",
"2560x1080", "800x1280"]`. Timeouts: contract kinds `shot` (60 s, per capture process), `movie` (300 s), `runner` (layout).

### 2.5 Runner protocol (C §2.8.5) and the shot plan
The verb writes `<run dir>/artifacts/plan.json` and passes `--plan=<abs path>` (scene mode, layout) or
`--shot-at=<abs path>` (scenario mode, to A5's runner, §8.4):
```json
{"schema":"harness.shotplan/1","scene":"res://scenes/main.tscn","seed":0,"out_dir":"/abs/.../artifacts/shots",
 "capture_script":"/abs/harness/addons/harness/runners/_capture.gd","last_tick":30,
 "shots":[{"name":"main-t30","tick":30,"hide":["%HUD"],"hide_layers":[2],"crop":null,"node":"%Score"}],
 "layout_sizes":[[1280,720],[800,1280]]}
```
Runner records (in addition to C §2.8.5 `finding`/`done`): first
`@@H {"t":"data","ev":"env","display":"X11","renderer":"gl_compatibility","adapter":"...","api":"..."}`, then per shot
`{"t":"data","ev":"shot","name":"main-t30","tick":30,"path":"/abs/...png","w":640,"h":360}`, per layout size
`{"t":"data","ev":"layout","size":[800,1280],"visible":[800,1280],"controls":14}`.
`_capture.gd` (extends Node, no `class_name`, loaded at run time by absolute path, §3.2) API:
`func start(plan: Dictionary, tick_source: Object) -> void` (connects `tick_source.tick_completed(tick)` for scenario
mode; scene mode calls `on_tick(k)` itself), `func on_tick(tick: int) -> void`, `func pending() -> int`.

### 2.6 Python API (for A7 and A8; not used by tests)
`harness.visual.capture(run, project, target, shots, movie=False, twice=False) -> list[Shot]` (Shot = name, tick,
path, w, h, env) and `harness.visual.compare(run, png, baseline_meta_path) -> CompareResult` (mode, px, pct, verdict,
diff_png). A7's `h trace --movie` calls `capture(..., movie=True)` with its scenario.

## 3. Design

### 3.1 Files (builder B6 writes exactly these)
`tools/harness/harness/verbs/shot.py`, `tools/harness/harness/verbs/baseline.py`, `tools/harness/harness/visual.py`
(plan building, capture orchestration, odiff wrapper via `proc.run()`, compare, baseline store, meta validation),
`tools/harness/schemas/baseline.schema.json`, `addons/harness/runners/shot.gd` (scene mode),
`addons/harness/runners/layout.gd` (headless layout), `addons/harness/runners/_capture.gd` (capture library, also used
by A5's runner); the scenario hook block in `addons/harness/runners/scenario.gd` (§8.4); `docs/visual.md` (<= 80 lines,
for the A8 `godot-visual` skill). Port: `research/scripts/r1_7_visual/proj/main.gd` (capture after
`frame_post_draw`, `get_region` crop, layer toggles) and `run.sh` (flags).

### 3.2 Capture flow
1. Parse args; `--headless` -> rc 4. Resolve project, TARGET, mode. `shutil.which("xvfb-run")` else rc 4. With
   `--compare`/`--twice`: odiff at `$HARNESS_CACHE/odiff/node_modules/@odiff/linux-x64/odiff` else rc 4.
   `--compare`: load + schema-check every `<key>/*.json` (not `.proposed.json`); build shots from their `capture`.
2. `godot.ensure_imported()`; scenario mode: A5 `scenario.load()` and `sync.ensure_synced()` (via `run_scenario`).
3. Group shots by process settings (size, seed); one Godot process per group (<= 8 shots each). Scene mode:
   `godot.run(run, kind="shot", runner=shot.gd, display="xvfb", args=["--fixed-fps", fps] + (["--resolution", WxH])
   + (["--write-movie", <abs>/movie/frame.png] if movie), user_args=["--plan=<abs>"])`, fps = project.godot
   `physics/common/physics_ticks_per_second` (default 60), so one frame = one physics tick. Scenario mode:
   `scenario.run_scenario(..., display="xvfb", extra_args=[...size/movie], extra_user_args=["--shot-at=<abs>"])`.
4. `shot.gd`: `_initialize`: parse `--plan`; emit `env` record; if `DisplayServer.get_name() == "headless"`: finding
   `[shot.headless]`, `done` rc 1 (verb maps to rc 4). `seed(plan.seed)`; `load(scene)`, `can_instantiate()` check
   (S2), instantiate, `root.add_child`, `current_scene`; `cap = load(plan.capture_script).new()`, `root.add_child(cap)`,
   `cap.start(plan, null)`. Connect `root.ready` one-shot -> `base = Engine.get_physics_frames()`.
   `_process()`: `c = physics_frames - base`; for every new c call `cap.on_tick(c)`; when `c >= last_tick` and
   `cap.pending() == 0`: `done` and `quit(rc)`. At 60 fps with `--fixed-fps 60` c advances by exactly 1 per frame
   [Run K4]; a skipped tick is a runner bug (`done` rc 3).
5. `_capture.gd.on_tick(k)`: for each shot with tick k: apply `hide`/`hide_layers` (node lookup failure ->
   `[shot.node-not-found]` finding, shot skipped), connect `RenderingServer.frame_post_draw` one-shot, then in the
   callback: `img = root.get_texture().get_image()`; crop (`--crop` rect or node rect, intersected with the image;
   empty -> `[shot.crop-outside]`); `img.save_png(out_dir/<name>.png)`; emit the `shot` record; restore visibility.
   `quit()` in the same `_process` still lets that frame draw and save [Run K4].
6. Merge per C §2.8.6 (log scan, rc, runner). Display failure in the log (`Unable to create DisplayServer`,
   `Xvfb failed to start`, `xvfb-run: error`) -> retry once (`retried: true`), then rc 4 `[shot.no-display]`.
   A shot listed in the plan with no `shot` record and no finding -> `[harness.runner-incomplete]`.
7. `--twice`: run step 3 again into `shots_b/`; per shot `odiff -t 0 --fail-on-layout --parsable-stdout A B` ->
   count > 0 or rc 21 -> `[shot.unstable] error: <name>: <n> px differ between two identical runs (hint: seed
   particles/RNG, avoid Time/OS clocks and real delta in visuals; the harness already passes --fixed-fps and seed())`.
8. Output: PNG paths only. Never print image data; never write images outside the run dir except `h baseline`.

### 3.3 Compare algorithm (`visual.compare`, per approved baseline)
1. Meta schema, `status == approved` and non-empty `approved_by` (else `shot.baseline-unapproved`); a `.proposed.json`
   with no approved pair also gives `shot.baseline-unapproved`. sha256(PNG) == `image.sha256` (else `tampered`).
   `env.renderer != "gl_compatibility"` -> `shot.renderer-mismatch` (no diff). Capture size != `image.w/h` ->
   `shot.size-mismatch`.
2. Mode: **exact** when `env.godot`, `renderer`, `adapter`, `api` all equal the current run's env; else **tolerant**.
3. sha256 of capture == baseline sha -> identical. Else run odiff (timeout 30 s, stdin `/dev/null`, `proc.run`):
   exact: `odiff -t 0 --fail-on-layout --parsable-stdout base cur diff.png [-i ignore]`; tolerant: `odiff -t
   <color_threshold> --aa --fail-on-layout --parsable-stdout ...`. Parse `<px>;<pct>` or `0`; rc 0 same, 22 differs,
   21 layout, other -> rc 3 internal. Exact: px > 0 -> `shot.diff`. Tolerant: pct > `threshold_pct` (baseline value
   if set) -> `shot.diff`; 0 < px and pct <= threshold -> `shot.drift` warning.
4. Diff PNG goes to `artifacts/shots/<name>.diff.png`. Per-shot results also go to `artifacts/compare.json`
   `[{name, mode, px, pct, verdict, baseline, diff}]`.

### 3.4 Layout algorithm (`layout.gd`, display `headless`, kind `runner`)
Instantiate the scene once under `root`. For each size: `root.size = Vector2i(w, h)`; await 2 `process_frame`;
`vis = root.get_visible_rect()` (respects stretch mode/aspect [Run K6]). Walk Controls with `is_visible_in_tree()` and
area > 0; skip descendants of `ScrollContainer` and of Controls with `clip_contents`. Rect R = node rect through
`get_global_transform_with_canvas()`.
- offscreen: R not inside `vis` by > 1 px -> error, message names the edge and overshoot.
- overflow: R not inside the parent Control's R by > 1 px (parent not a Container that clips) -> warning.
- overlap: siblings, both of `Label | BaseButton | LineEdit | RichTextLabel | TextureRect`, parent not a `Container`,
  intersection area > 4 -> warning.
- clipped: `Label` with non-empty text: autowrap off -> width = `font.get_multiline_string_size(text, align, -1,
  font_size).x`, available = `size.x` minus the `normal` stylebox horizontal margins; width > available + 1 -> error
  ("text needs W px, has A px"); autowrap on -> `get_line_count() > get_visible_line_count()` -> error. `Button` with
  `clip_text`: same width test against `size.x` minus stylebox margins and icon width.
Message form: `<path from scene root> @<W>x<H>: <detail>`. Findings sorted by size order, then node path. Fonts and
layout match between headless and Xvfb (text width 551 in both [Run K6]), so layout needs no Xvfb.

### 3.5 Xvfb process handling (answers contract open question (3)) [Run K3]
- `xvfb-run -a` returns Godot's own exit status: `quit(7)` -> 7, `OS.crash` -> 134. So C §2.8.3/2.8.6 work unchanged.
- SIGTERM to the process group (C §2.8.3 at T): xvfb-run's trap stops Xvfb and removes its lock; the whole group
  (xvfb-run, Xvfb, godot) is gone within 0.3 s; Popen rc = -15 (the shell itself died). `godot.run` records rc 124.
- SIGKILL to the group (T+3 s path): the group dies but `/tmp/.X<n>-lock` and `/tmp/.X11-unix/X<n>` stay; the next
  `-a` silently moves to `:<n+1>`. Δ request to A1 `godot.py` (display `xvfb` only): after a SIGKILL, remove lock
  files created after the invocation started whose PID (lock content) is not alive, plus the matching socket.
- Six parallel `xvfb-run -a` captures x 2 rounds: 12/12 rc 0, no display collision [Run]; the retry in §3.2.6
  covers the rare race [U].
- Xvfb unusable: Godot logs `ERROR: Unable to create DisplayServer, all display drivers failed.`, rc 1 [Run].

### 3.6 Budgets and timeouts
One capture at 640x360: <= 3 s wall (measured 0.78-0.84 s, in-runner 120-136 ms for 30 ticks). `--compare` adds
<= 0.2 s per shot (odiff 3-11 ms at 320x240, R1.7). `--twice` <= 2x. Layout at 4 sizes <= 2 s (0.27 s for 3 sizes
[Run]). Movie 60 frames <= 3 s. Timeouts: kinds `shot` 60 s, `movie` 300 s, layout `runner` 60 s (C §2.8.2).

### 3.7 Spikes [Run] (scratchpad `a6/`; project 640x360, `canvas_items`, ColorRect bg, orange Box +1 px per physics
tick from x=20, CanvasLayer HUD Label, CPUParticles2D 50 unseeded)
- K1 timing: `xvfb-run -a -s "-screen 0 1920x1080x24" godot --path proj --rendering-method gl_compatibility
  --audio-driver Dummy --fixed-fps 60 -s shot.gd -- --tick=30`: wall 0.78-0.84 s; log = banner, `WARNING: Could not
  set V-Sync mode` (benign list), `OpenGL API 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4 - Compatibility - Using
  Device: Mesa - llvmpipe (LLVM 20.1.2, 256 bits)`; nothing else, so a clean capture scans clean.
- K2 determinism: unseeded particles + `--fixed-fps 60`, 3 runs: 3 different md5s (odiff `48;0.02`, IM AE 48). With
  `seed(12345)` in the runner's `_initialize`: 3/3 identical md5 `33cc054d...`. (R1.7 saw 30/30 without seed; this
  setup differs, so the runner always seeds.)
- K3 xvfb-run exit status: §3.5 (python Popen `start_new_session=True`, `os.killpg`; group listed via /proc stat).
- K4 tick semantics: capture when `c = physics_frames - base` reaches N via the SceneTree `_process` + one-shot
  `frame_post_draw`: N=30 -> Box drawn at x=50 (exact), N=0 -> first `_process` already has c=1 (x=21). Calling
  `quit(0)` before `frame_post_draw` still saved the PNG.
- K5 odiff 4.5.0: 20 px shift -> `1650;0.72` rc 22 at `-t 0.1`, `-t 0` and `--aa`; HUD hidden -> `593;0.26` (`-t 0.1`)
  vs `2365;1.03` (`-t 0`); size 640x360 vs 320x180 with `--fail-on-layout` -> stdout `layout`, rc 21. `--node %Score`
  crop: 101x23 at 640x360, 202x46 at 1280x720, 404x92 at 2560x1440 (scale 1/2/4 from `get_final_transform()`);
  `--resolution 2560x1440` works on a 1920x1080 Xvfb screen. `--resolution 800x1280` with `keep` aspect -> 800x450.
  `canvas_cull_mask = 0` hides all 2D (99.96%).
- K6 layout: `root.size = (w,h)` in a `-s` runner works under `--headless` and Xvfb with identical rects; with
  `aspect=expand`, 800x1280 -> visible 640x1024, 2560x1080 -> 853x360; with `keep`, always 640x360. Label text width
  551 px headless and Xvfb. Controls built in `_ready` need `set_anchors_and_offsets_preset` (with
  `set_anchors_preset` the root Control stayed 0 wide), relevant for fixture code.
- K7 `--write-movie f.png --quit-after 30` with a `-s` runner: 30 PNGs + `f.wav`, wall 0.99 s.
- K8 `load("/abs/path/_capture.gd").new()` from a `-s` runner with `--path proj`: loads, `can_instantiate()` true.
- K9 input injection under Xvfb (A5 open question 2): `parse_input_event` + `flush_buffered_events` in `_process` at
  c=9 -> `is_action_just_pressed` true at physics frame 10, same as headless.
- K10 env: `RenderingServer.get_current_rendering_method()` = `gl_compatibility`, `DisplayServer.get_name()` = `X11`
  (Xvfb) / `headless`; `Engine.get_version_info().string` = `4.7-stable (official)` (short; use godot.py's string).
- K11 `--headless` + `frame_post_draw` capture: hangs, `timeout 8` -> rc 124 (confirms R1.7).

## 4. Acceptance criteria (fixture `shot_min` copied per B3; every `h` result passes `assert_contract`)
- AC-06.1 `h shot res://scenes/main.tscn --tick 30` -> rc 0, `PASS shot`, stats `project, import, target, env` in
  order, check line `^OK +main-t30: 640x360 \S+main-t30\.png$`; the PNG exists, is 640x360. [contract, xvfb]
- AC-06.2 Two separate captures of AC-06.1 are byte-identical (sha256); `--twice` -> rc 0, `twice: identical`. [contract]
- AC-06.3 Tick semantics: capture at `--tick 30` has an orange pixel (255,165,0) at (50,120) and background at
  (49,120); `--tick 1` at (21,120). (Pixel reads via a tiny PNG decoder in the test helper or ImageMagick.) [contract]
- AC-06.4 One capture (AC-06.1) takes <= 3 s wall warm (median of 3). [contract, slow]
- AC-06.5 Stdout never contains image bytes or base64; every line <= 240 chars; PNGs live only under the run dir. [contract]
- AC-06.6 `--headless` -> rc 4, first line `^ERROR shot --headless cannot render images`; no Godot invocation in
  run.json. [contract]
- AC-06.7 `PATH` without `xvfb-run` (test builds a PATH dir with symlinks to everything else needed) -> rc 4. [contract]
- AC-06.8 `--compare` against the fixture's approved baseline -> rc 0, `OK   main-t30: identical`; with FAULT-A6-01
  planted -> rc 1, `[shot.diff]` with `\d+ px \([0-9.]+%\)`, `compare.json` px > 0, `.diff.png` exists. [contract]
- AC-06.9 Tolerant mode: copy of the baseline meta with `env.api` changed to `other Mesa` -> HUD shift still FAILs
  (0.72% > 0.1%); clean scene -> rc 0 `identical` (sha equal) ; an `ignore` rect covering the shifted area -> rc 0. [contract]
- AC-06.10 Baseline with `env.renderer = "forward_plus"` -> rc 1 `[shot.renderer-mismatch]`, no odiff call
  (`compare.json` has no px). [contract]
- AC-06.11 Baseline PNG replaced by a 320x180 image with meta `image.{w,h,sha256}` updated to match -> rc 1
  `[shot.size-mismatch]` (not `tampered`). [contract]
- AC-06.12 `--compare` with a capture flag (`--tick 5`) -> rc 2 usage. `--compare` on `res://scenes/hud.tscn` (no
  baselines) -> rc 1 `[shot.no-baseline]`. [contract]
- AC-06.13 `--node %Score` -> PNG 101x23; `--crop 0,0,64,32` -> 64x32; `--node %Nope` -> rc 1
  `[shot.node-not-found]`; `--crop 900,900,10,10` -> rc 1 `[shot.crop-outside]`; `--crop` + `--node` -> rc 2. [contract]
- AC-06.14 `--hide %HUD` and `--hide-layer 1` each give a PNG that differs from the plain capture (odiff px > 0)
  and the plain capture afterwards is unchanged. [contract]
- AC-06.15 `--size 1280x720` -> 1280x720 PNG; `--size 800x1280` -> PNG size reported in the check line equals the file. [contract]
- AC-06.16 Unseeded CPUParticles2D (CLEAN-A6-02 setup) `--twice` -> rc 0; wall-clock visual (FAULT-A6-02) -> rc 1
  `[shot.unstable]`. [contract]
- AC-06.17 `--movie --tick 30` -> stat `^movie: (30|31) frames `, that many `frame*.png` in `artifacts/movie/`. [contract]
- AC-06.18 Runtime `SCRIPT ERROR` in `_ready` (FAULT-A6-09) -> rc 1 `[godot.script-error]` although the PNG exists. [contract]
- AC-06.19 Hang under Xvfb (FAULT-A6-10, `[timeouts] shot = 5`) -> rc 1 `[harness.hang]`, wall <= 12 s; afterwards no
  process with the copy path in its cmdline, no `Xvfb` child of the run, no `/tmp/.X*-lock` whose PID is dead. [contract]
- AC-06.20 Layout clean: `--layout --sizes 640x360,1280x720` on hud.tscn -> rc 0, 2 `OK` check lines. FAULT-A6-03 ->
  rc 1 `[shot.layout-clipped]` naming `Title` and the size; FAULT-A6-08 -> `[shot.layout-offscreen]` naming `Health`.
  Overlap variant (two Labels at the same position) -> rc 5 `[shot.layout-overlap]`. Layout run.json invocation argv
  contains `--headless` and no `xvfb-run`; wall <= 2 s for 4 sizes. [contract]
- AC-06.21 `h baseline propose res://scenes/main.tscn --tick 30` -> rc 0, writes `baselines/scenes/main/main-t30.
  proposed.{png,json}` (schema-valid, `status: proposed`), creates `baselines/.gdignore`, leaves the approved pair
  byte-identical; `--compare` afterwards still uses the approved pair. [contract]
- AC-06.22 `h baseline approve res://scenes/main.tscn` from a subprocess without a TTY (stdin `/dev/null`, new session)
  -> rc 2 `[shot.approve-needs-tty]`, files unchanged. Under `pty.fork()` answering `yes` -> rc 0, approved pair
  replaced, `approved_by` non-empty, `.proposed.*` gone; answering `no` -> `SKIP`, nothing changed. [contract]
- AC-06.23 Only a proposal exists -> `--compare` rc 1 `[shot.baseline-unapproved]`; PNG edited after approval ->
  rc 1 `[shot.baseline-tampered]`; meta missing `env` -> rc 2 `[shot.bad-baseline]`. [contract]
- AC-06.24 `h baseline list` -> one check line per baseline, WARN rc 5 with a pending proposal. [contract]
- AC-06.25 Scenario mode (needs A5): `h shot res://scenarios/jump.json --tick 40,90` on `scenario_min` -> 2 PNGs,
  rc 0; two runs byte-identical; `--tick 999` -> rc 2. [contract, after A5]
- AC-06.26 `h selftest --area A6` -> all must faults CAUGHT, CLEAN-A6-* PASS, wall <= 180 s. [contract, slow]
- AC-06.27 Unit (visual.py is not public; tested via the CLI only): odiff output parsing is covered through AC-06.8/9/11.
  Untestable automatically: that the A8 hook blocks `approve` for agents (A8's tests).

## 5. Seeded faults (fixture `shot_min`; verb `shot`; `must` unless noted)
Hook lines in the fixture (exact text, one each): `scripts/main.gd`: `	pass # HOOK-READY` (end of `_ready`),
`	pass # HOOK-PROCESS` (in `_process`); `scripts/hud.gd`: `	pass # HOOK-HUD` (end of `_ready`).
| ID | Planted | Args | Expect |
|---|---|---|---|
| FAULT-A6-01 | replace `panel.position = Vector2(10, 10)` -> `Vector2(30, 10)` in main.gd (HUD moved 20 px) | `res://scenes/main.tscn --compare` | rc 1, `\[shot\.diff\].* \d+ px`, <= 40 s |
| FAULT-A6-02 | HOOK-PROCESS -> `	$Box.position.y = 100 + Time.get_ticks_usec() % 50` | `res://scenes/main.tscn --tick 30 --twice` | rc 1, `\[shot\.unstable\]` |
| FAULT-A6-03 | HOOK-HUD -> `	$Title.text = "THE VERY LONG GAME TITLE THAT DOES NOT FIT ON SMALL SCREENS AT ALL, NOT EVEN CLOSE"` (~800 px) | `res://scenes/hud.tscn --layout --sizes 640x360` | rc 1, `\[shot\.layout-clipped\].*Title` |
| FAULT-A6-04 | replace `"renderer": "gl_compatibility"` -> `"forward_plus"` in `baselines/scenes/main/main-t30.json` | `res://scenes/main.tscn --compare` | rc 1, `\[shot\.renderer-mismatch\]` |
| FAULT-A6-05 | none | `res://scenes/main.tscn --headless` | rc 4, ERROR, `headless`, <= 5 s |
| FAULT-A6-06 | replace `"status": "approved"` -> `"status": "proposed"` in the baseline meta | `... --compare` | rc 1, `\[shot\.baseline-unapproved\]` |
| FAULT-A6-07 | write `baselines/scenes/main/main-t30.png` from `files/other.png` (a 640x360 PNG of another color) | `... --compare` | rc 1, `\[shot\.baseline-tampered\]` |
| FAULT-A6-08 | HOOK-HUD -> `	$Health.position = Vector2(1300, 600)` | `res://scenes/hud.tscn --layout --sizes 1280x720` | rc 1, `\[shot\.layout-offscreen\].*Health` |
| FAULT-A6-09 | HOOK-READY -> `	var n = null\n	n.foo()` | `res://scenes/main.tscn` | rc 1, `\[godot\.script-error\]` |
| FAULT-A6-10 | HOOK-PROCESS -> `	if Engine.get_physics_frames() > 5:\n		while true: pass`; write harness.toml `[timeouts]\nshot = 5\n` | `res://scenes/main.tscn --tick 30` | rc 1, `\[harness\.hang\]`, <= 40 s |
| FAULT-A6-11 | none | `res://scenes/main.tscn --node %Nope` | rc 1, `\[shot\.node-not-found\]` |
| FAULT-A6-12 (nice) | HOOK-READY -> `	get_window().content_scale_factor = 1.01` (sub-pixel blur) | `... --compare` | rc 1, `\[shot\.diff\]` |
| CLEAN-A6-01 | none | `res://scenes/main.tscn --compare` | rc 0, `^OK +main-t30: identical` |
| CLEAN-A6-02 | HOOK-READY -> unseeded `CPUParticles2D` (amount 50, spread 180, velocity 30-60) at (320,180) | `res://scenes/main.tscn --tick 30 --twice` | rc 0, `^twice: identical` |
| CLEAN-A6-03 | none | `res://scenes/hud.tscn --layout` | rc 0, PASS |

## 6. Fixtures needed (test-writer T6)
`tests/fixtures/projects/shot_min/` (FIXTURE.md: owner A6, `h check` PASS):
- `project.godot`: C §2.11 minimum, `run/main_scene="res://scenes/main.tscn"`, `[display] window/size/viewport_width=640`,
  `viewport_height=360` (stretch default `disabled`), `[rendering] renderer/rendering_method="gl_compatibility"`,
  `[physics] common/physics_ticks_per_second=60`.
- `scenes/main.tscn` (root Node2D "Main", script `scripts/main.gd`). `main.gd` `_ready` builds: ColorRect bg 640x360
  `Color(0.1, 0.2, 0.4)`; ColorRect "Box" 40x40 orange at (20, 100); CanvasLayer "HUD" (unique `%HUD`, owner = root)
  with PanelContainer `panel` at `panel.position = Vector2(10, 10)` holding Label "Score" (unique `%Score`, owner =
  root, text `SCORE 12345`); hook lines. `_physics_process`: `$Box.position.x += 1`. `_process(_d)`: HOOK-PROCESS.
- `scenes/hud.tscn` (root Control "HUD", `scripts/hud.gd`): `_ready` uses `set_anchors_and_offsets_preset` (K6):
  full rect root; Label "Title" top-wide, offsets 20/-20, `clip_text = true`, text `GAME TITLE`; Label "Score" top-right
  (offsets -150/-10, top 40); Label "Health" at (20, 300); HBoxContainer "Bar" bottom-left (offset_top -50, left 10)
  with 3 Buttons 150x40. Must give 0 layout findings at 640x360, 1280x720, 1920x1080, 2560x1080, 800x1280.
- `baselines/.gdignore`, `baselines/scenes/main/main-t30.png` + `.json` (approved, `approved_by: "fixture T6"`):
  produced by T6 with the reference capture script `tests/fixtures/tools/capture_ref.gd` (the §3.2 step 4-5 algorithm
  for one shot: seed(0), tick via `_process` count, one-shot `frame_post_draw`, `save_png`) under the §3.7 K1 command
  line; meta `env` from that run, written as `json.dumps(indent=2)` (so `"status": "approved"` and `"renderer":
  "gl_compatibility"` match the fault `replace` ops). Binary PNG <= 20 KB (§8.3 D-a); `files/other.png` likewise.
- Contract tests reuse `scenario_min` (A5) for AC-06.25.

## 7. Build order (B6; after A1 step 0 and A5's runner; each step ends green on the named ACs)
1. `shot.py` arg parsing, `--headless`/xvfb/odiff env checks, plan writing -> AC-06.6, 7, 12 (usage part), 13 (rc 2).
2. `shot.gd` + `_capture.gd` single shot, scene mode -> AC-06.1-5, 15, 18, 19.
3. Crop/node/hide/hide-layer, multi-tick, movie -> AC-06.13, 14, 17.
4. `visual.compare` + baseline store + schema -> AC-06.8-12, 23; `--twice` -> AC-06.2, 16.
5. `baseline.py` propose/approve/list -> AC-06.21, 22, 24.
6. `layout.gd` + `--layout` -> AC-06.20. 7. Scenario hook in A5's runner -> AC-06.25. 8. Selftest -> AC-06.26.

## 8. Out of scope, open questions, deviations, assumptions
### 8.1 Out of scope (v0)
Vulkan/forward_plus baselines (B6: GL only; `--with-vulkan` stays a bootstrap option), 3D-specific helpers beyond
`--hide-layer` on Camera3D, SubViewport capture, editor UI, perceptual metrics (SSIM), auto-generated contact sheets,
AVI movies (PNG frames only), audio, real-GPU or cross-Mesa exactness (tolerant mode only), screen readers / text
legibility judgments (human gate).
### 8.2 Open questions [U]
1. GPUParticles2D/3D, TIME shaders, AnimationPlayer in idle mode, MSAA/glow/SSAO under llvmpipe with seed + fixed fps
   (R1.7 untested). `--twice` is the per-scene guard.
2. Parallel `xvfb-run -a` display race: not observed in 12 runs; one retry covers it.
3. Layout clip test for `RichTextLabel` and `fit_content` labels is not defined (no finding emitted).
4. Fonts that load from the project (not the built-in default) render identically headless vs Xvfb: only the default
   font measured.
5. Whether `quit()` inside the capture callback ever loses the last PNG under heavy load (worked in K4).
### 8.3 Deviations from 00_contract (for the reviewer)
- D-a Fixture `shot_min` (and fault `files/`) contains binary PNGs (<= 20 KB each), against C §2.11 "text files only".
  Reason: the selftest needs an approved baseline before any verb runs. Contract tests also build baselines at run time
  (propose + pty approve), so only selftest depends on the committed PNG.
- D-b `_capture.gd` is loaded at run time by absolute path from both `shot.gd` and A5's `scenario.gd` (C §2.8.5 says no
  preload of other harness files). It is `load()` at run time, not `preload`, and keeps capture code in one file [Run K8].
- D-c `--layout` runs with `display="headless"` (kind `runner`); only image capture refuses headless. A user-passed
  `--headless` is rc 4 in every mode.
- D-d Δ to A1 `godot.py`: for display `xvfb`, (1) after a SIGKILL clean stale `/tmp/.X<n>-lock` + socket (§3.5),
  (2) accept extra Godot args per call (`--fixed-fps`, `--resolution`, `--write-movie`), (3) one retry when the log
  shows a display start failure, reported as `retried: true`.
- D-e Contract open question (3) is answered in §3.5: no change to rc normalisation is needed.
### 8.4 Assumptions on other areas
- A5: `run_scenario(run, project, scenario, fps, global_seed, extra_user_args, display, extra_args=[])` (adds
  `extra_args`, Godot-side args before `--`). `runners/scenario.gd` gains a delimited block (`# --- A6 capture ---`,
  <= 12 lines, written by B6 after B5): if `--shot-at=<abs>` is given, parse it, `cap = load(plan.capture_script).new()`,
  `root.add_child(cap)`, `cap.start(plan, Harness)`; before `quit`, wait while `cap.pending() > 0` (frames only, no
  more ticks are recorded). `Harness.tick_completed(k)` is emitted in `_process` after tick k (A5 §3.2.3), so a capture
  connected there shows the state after step k. The spec reviewer assigns the file ownership.
- A7: uses `harness.visual.capture(..., movie=True)` for `h trace --movie`; frames are named `frame%08d.png` by Godot.
- A8: the `godot-visual` skill (from `docs/visual.md`): never Read PNGs to judge them; use `h shot --compare` /
  `--layout`; propose, never approve. A PreToolUse hook blocks `h baseline approve` and Edit/Write under
  `<baseline_dir>/` for agents. `h doctor` already checks `xvfb-run`, `odiff`, `compare` (A1).
- A1: config discovery for `[shot]`; `[harness] renderer` validation (only `gl_compatibility`).
- A9: the sample's HUD scene gets an approved baseline by the human at Gate G3, not by an agent.
- Plan defaults: D4 (approval is human), B4 (odiff 4.5.0 pinned), B6 (GL + llvmpipe, Mesa recorded in meta).
