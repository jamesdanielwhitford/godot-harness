# "Your Game Is A Harness", applied to Godot 4.x: analysis, harness design and research plan

Status: planning document (round 0). Written from the article summary plus my own knowledge of Godot. Claims are tagged:
- **[K]**: well-established Godot 4 behaviour, high confidence.
- **[U]**: I believe this is true but it needs checking; usually version-sensitive.
- **[P]**: checked from this sandbox on 2026-10-15.

Environment facts **[P]**:
- docs.godotengine.org/en/stable now serves the **4.7** branch, and Godot master `version.py` reports **4.8-dev**. Target **Godot 4.7 stable**.
- Through the agent proxy:
  - `raw.githubusercontent.com` works.
  - `git clone https://github.com/...` works (ls-remote succeeded).
  - GitHub release asset downloads work (Godot 4.5 linux zip returned 206).
  - The `github.com` web UI and `api.github.com` return 403, and `gh` is not enabled for these repos.
  - YouTube returns 200; transcript extraction is untested.
  - `kylekukshtel.com` was blocked earlier.
- `Xvfb`/`xvfb-run` are installed. Godot and dotnet are not.

---

## 1. Verdict in one paragraph

Godot is one of the better engines for "game as harness":
- Scenes, resources and project settings are text.
- The editor binary is also a CLI that can run headless, run arbitrary scripts, dump its own exact API as JSON, and record deterministic fixed-FPS frame sequences.
- GDScript gives fast reload with no compile step.

The article's ideas map onto Godot, but the boundaries are in different places:
- **The "engine-free simulation DLL" only exists cleanly in C#.** In GDScript, the practical equivalent is "Node-free simulation classes run in a headless engine." That is about 0.3–1 s startup per run, not milliseconds. It is still fast enough for the inner loop.
- **The biggest Godot-specific risks are not visuals.** They are:
  - stale Godot 3 API knowledge,
  - hand-edited `.tscn`/`.tres`, with its ids, UIDs and node paths,
  - scene↔script drift: node paths, signal connections and exported references that only fail at runtime.

**So the highest-leverage harness pieces are cheap ones:**
- version-pinned API ground truth,
- a one-command "load everything and report" check,
- a scene-to-text digest,
- a headless test and scenario runner with seeded, fixed-step replays.

Screenshots/odiff and a live editor bridge come later and matter less.

---

## 2. Concept mapping: article → Godot

| Article idea | Godot mapping | Fit | Notes |
|---|---|---|---|
| Fixed random seed | One autoload `Rng` wrapping a `RandomNumberGenerator` with a seed from CLI args. Ban the global `randf()/randi()/randf_range()/shuffle()/pick_random()` with a lint (grep) **[K]** | Clean | `Array.shuffle()`/`pick_random()` use the global RNG **[K]**. Seeding the global with `seed()` also works but is fragile. |
| Deterministic state / exact save-load | Simulation state as `Resource` or plain typed `RefCounted` data → `var_to_str`/JSON/`ResourceSaver` `.tres` **[K]** | Good for logic, poor for physics | Godot Physics and Jolt are not guaranteed bit-deterministic across machines or builds. Same binary + same machine + fixed step is usually repeatable, but this is **[U]** and needs measuring. Variable `delta`, `Tween`, `AnimationPlayer`, `Timer` and threads all add nondeterminism unless driven at a fixed step. |
| Fat struct / single `Thing` | A `Thing` typed class (GDScript `class_name Thing extends RefCounted`, or C# struct/class) held in a `World` array; nodes are views | Workable, but against the grain | The Godot idiom is node-per-entity with scene inheritance, which is the hierarchy sprawl the article warns about. **Recommend a hybrid:** fat-struct sim for core game rules (turn-based, economy, combat resolution); keep nodes for presentation, physics bodies and UI. Don't fight Godot for real-time physics movement. |
| Command pattern | `Command` = Dictionary/JSON `{type, target, value}` or a typed class, processed by one `CommandBus` autoload. `target` = stable entity id, **never a NodePath** | Clean | Same command stream from input, replays, network and agent. |
| Blackbox simulation DLL | **C#:** separate `.csproj` class library + `dotnet test` (xUnit/NUnit), with no Godot types or only pure-struct GodotSharp math **[U]**. **GDScript:** `res://sim/` with a rule of no `Node`/`SceneTree`/`Input`/`get_tree()`, tested headless. **C++:** GDExtension (overkill for most) | C# clean; GDScript partial | Only C# gets the "VERY FAST no-engine" test loop. GDScript stays in-engine but headless. |
| Verifiable state without engine | GUT or gdUnit4 headless; `dotnet test` for C# | Good | Both GDScript frameworks run from the CLI headless **[K]**. gdUnit4 emits JUnit XML **[K]**; GUT has a JUnit export **[U]**. |
| Text-authored commands replayed on live game, no compile | GDScript itself is no-compile. Replays run as a **one-shot CLI run**: `godot --headless --path . -- --replay=cmds.json --seed=1 --frames=600 --dump=state.json` reading `OS.get_cmdline_user_args()` **[K]**. A live socket is optional | Very good | One-shot runs are stateless and reproducible, which suits agents better than a persistent session. |
| External data | `.tres` Resources with `@export` fields, or JSON/CSV loaded at runtime. Godot CSV import is for translations only, so load your own CSV/JSON **[K]** | Clean | `.tres` is agent-readable and editor-editable, which suits both. |
| Screenshots + layer toggles + odiff | `get_viewport().get_texture().get_image().save_png()` after `await RenderingServer.frame_post_draw` **[K]**. Layer toggles: `CanvasLayer.visible`, `VisualInstance3D.layers` + `Camera3D.cull_mask`, `CanvasItem.visibility_layer` **[K]** | Good, needs a display | `--headless` uses the dummy renderer, so **no images** **[K]**. Use `xvfb-run` + `--rendering-driver opengl3` (Compatibility renderer, works with Mesa llvmpipe) **[U]**, or Movie Maker `--write-movie out.png --fixed-fps 60 --quit-after N`, which writes numbered PNGs at a fixed step **[K/U]** for flags and behaviour in 4.7. |
| Text profiler (samply) | `Performance.get_monitor()` + `Performance.add_custom_monitor()` dumped to CSV **[K]**; `--print-fps` **[K]**; `--benchmark`/`--benchmark-file` (startup timing) **[U]**; samply on the Godot binary sees native frames only, not GDScript functions **[U]** | Partial | GDScript-level profiling is only via the editor debugger (GUI). Instrument with `Time.get_ticks_usec()` scopes. Possible Tracy/Perfetto integration in recent versions **[U]**. |
| Impact assessment / fixed scenarios | Scenario = `{scene, seed, command file, frames, assertions}` run by the same CLI runner; outputs metrics JSON | Clean | |
| "Talk to the game" | (1) one-shot CLI runs; (2) optional debug-only TCP/WebSocket JSON-RPC autoload (`TCPServer`, `WebSocketPeer`) **[K]**; (3) the `EngineDebugger`/`EditorDebuggerPlugin` message channel **[K]**; (4) existing Godot MCP servers **[U]** on their quality | Many options | Recommend (1) as the default and (2)/(4) only for live inspection. |

### What breaks or needs care (Godot-specific)
1. **Physics determinism.** Fixed-step replays will diverge across machines, and possibly across Jolt and Godot Physics. Assertions should check **tolerances and invariants** ("player reaches x≥400 by frame 180 ±3"), not exact equality, unless the sim is kinematic or owned by your own code.
2. **Editor-owned state.** Editor-owned files are opaque or semi-opaque:
   - the `.godot/` cache (`imported/`, `uid_cache.bin`, `global_script_class_cache.cfg`),
   - `.import` files,
   - `.uid` sidecar files (4.4+) **[K]**,
   - `ExtResource`/`SubResource` ids.

   `class_name` registration and imports need an editor import pass:
   - `godot --headless --editor --quit`, or
   - `--import` (added around 4.2–4.3) **[U]**.

   Fresh clones and newly added `class_name` scripts will fail to resolve until this runs. **The harness must run the import step itself.**
3. **Scene↔script coupling.** Typed `$Path`/`get_node()` strings, `[connection]` entries in `.tscn`, and `@export` NodePaths are checked only at runtime. They are invisible to the GDScript parser.
4. **Headless ≠ rendered.** No screenshots and no GPU paths in headless. Shader errors may not show up headless **[U]**.
5. **C# trade-offs.** C# gives the cleanest blackbox, but:
   - web export is unsupported or limited in 4.x **[U, check 4.7]**,
   - it needs the .NET build of Godot plus the dotnet SDK.

---

## 3. What LLMs are bad at in Godot work, and the mitigations

| # | Failure mode | Why it happens | Harness mitigation (component ids from §4) |
|---|---|---|---|
| F1 | **Godot 3 API / syntax**: `yield`, `onready var`, `export var`, `connect("sig", self, "m")`, `instance()`, `KinematicBody2D`, `Spatial`, `move_and_slide(vel)`, `Tween` node, `rand_range`, `File`, `deg2rad`, `stepify`, `rect_*` props, `setget`, `PoolStringArray`, `change_scene` | Training data is dominated by Godot 3 tutorials | **C1** version-pinned API ground truth (`--dump-extension-api` JSON + `--doctool` XML + docs checkout) and a grep-able lookup skill. **C3** Godot-3-idiom lint as a PostToolUse hook. **C2** load-check catches the rest. |
| F2 | **Drift between 4.x minors**: APIs added or renamed between 4.0 and 4.7, e.g. `.uid` files (4.4), typed dictionaries (4.4), Jolt integration, physics interpolation, `@abstract`, variadic args **[U on exact versions]** | Training mixes 4.0–4.x | C1 (the exact engine dump is the authority), and CLAUDE.md pins the version. |
| F3 | **Hand-editing `.tscn`/`.tres`**: wrong `ExtResource` ids, duplicate ids, a stale `load_steps`, bad `uid://`, wrong `parent=` paths, invalid property names or value syntax, sub-resource ordering | The format is text but editor-generated, with cross-references | **C4** scene digest (read) plus **scene-by-script** (write: a generator `--script` builds nodes and saves with `PackedScene.pack()` + `ResourceSaver.save()`, so the engine writes valid files). **C2** loads every scene and reports errors. Rule: small property edits by hand are fine; structural edits go through a generator or MCP tool. |
| F4 | **Node paths**: `$"../UI/HealthBar"` breaks after the tree is reorganised | Paths are in code, the tree is in `.tscn`; the model sees one or the other | **C4** digest gives real paths. Convention: `%UniqueName` + `@export var x: Type` typed refs. **C2b** "path lint" resolves every `$`/`get_node`/`%` literal against instantiated scenes. |
| F5 | **Signal wiring**: editor connections in `.tscn` that the model never sees, wrong signatures, Godot 3 string connects, double connects | Connections live in two places | Convention: connect in code (`_ready`) with Callables and typed signals. C4 digest lists `[connection]` entries. C2 reports "method not found". |
| F6 | **UID/resource refs**: moving or renaming files breaks `res://` paths or `uid://` refs; `.uid` files get forgotten | Only the editor's FileSystem dock refactors safely | Rule: rename and move only through a harness tool that calls the editor or updates references. Commit `.uid` files. C2 import + load check after any move. |
| F7 | **`class_name`/autoload resolution**: works after the editor scans, fails in a fresh headless run | Global class cache in `.godot/` | C2 always runs the import pass first. Document this in CLAUDE.md. |
| F8 | **Judging visuals**: layout, colour, "does it look right" | Vision is weak at change detection; whole screenshots pollute context | **C8** fixed-state screenshot + crop + odiff score. Images go into context only on explicit request. Human approves baselines. Prefer **numeric layout assertions** (Control `get_global_rect()`, overlap and on-screen checks) where possible. |
| F9 | **Feel and timing**: jump arcs, acceleration, coyote time, tween easing, hit-stop, camera smoothing | Not observable as text; subjective | **C7** numeric traces per physics tick (pos/vel/state/input) → computed metrics (apex height, time-to-apex, frames input→motion, settle time, overshoot) checked against **designer-set target ranges** in a `.tres`. Agent tunes numbers; **the human judges feel** from a `--write-movie` clip. The agent must never claim "it feels good". |
| F10 | **Physics behaviour**: tunnelling, collision layers/masks bitfields, `move_and_slide` floor detection, one-way platforms | Emergent, not visible in code | C7 traces + C6 scenario assertions. Digest (C4) prints layer/mask as named layers. |
| F11 | **Long, noisy logs** pollute context: Godot prints banners, Vulkan/driver warnings, leaked-instance spam at exit, import chatter | | Every harness tool emits a **compact summary** (pass/fail counts, first N unique errors with file:line). Full logs go to a file. Optionally a log-triage subagent reads them. |
| F12 | **Editor-only state**: import settings, project settings via GUI, the inspector-only workflow in tutorials, editor-only plugins (`@tool`) | Tutorials say "click X in the inspector" | Rule: everything goes through text files (`project.godot`, `.tres`, `.import`) or scripts. C1 docs lookup translates inspector instructions into property names. |
| F13 | **`@tool` scripts and editor plugins**: code runs in the editor and can corrupt scenes | Unexpected execution context | Rule: no `@tool` without explicit approval. C2 runs headless editor import, which will execute `@tool` code, so watch for errors there. |
| F14 | **Async/await and lifecycle order**: `_ready` order (children first), `await` across freed nodes, `queue_free` timing, `call_deferred` | Subtle runtime semantics | Tests with frame stepping (gdUnit4 scene runner / GUT `wait_frames`); C2 with `--verbose` orphan/leak reporting summarised. |
| F15 | **Performance claims** without measurement | No text profiler by default | **C9** monitor CSV over a fixed scenario with budgets. |

---

## 4. Candidate harness architecture

```
┌────────────────────── Claude Code ───────────────────────┐
│ CLAUDE.md (version pin, conventions, tool menu)           │
│ Skills: godot-api, godot-scene, godot-scenario, godot-visual, godot-feel │
│ Hooks: PostToolUse(*.gd|*.tscn|*.tres) → C3 lint + fast C2 │
│        Stop → C5 tests (summary only)                     │
│ Subagents: log-triage, api-lookup (keep main ctx clean)   │
└──────────────┬───────────────────────────────────────────┘
               │ shell (one entrypoint: `./h <verb>`; all output compact)
┌──────────────▼───────────────────────────────────────────┐
│ tools/harness/ (bash/python wrappers + GDScript runners)  │
│  h api <Class[.member]>    → C1 lookup in pinned dumps     │
│  h check [--full]          → C2 import + load-all + lint   │
│  h test [filter]           → C5 gdUnit4/GUT/dotnet summary │
│  h digest <scene.tscn>     → C4 tree/props/signals as text │
│  h scene-gen <spec.json>   → C4w build scene via engine    │
│  h run <scenario.json>     → C6 seeded fixed-step replay   │
│                               → state.json, metrics.json   │
│  h trace <scenario> <node> → C7 per-tick CSV + metrics     │
│  h shot <scenario> [crop]  → C8 xvfb render + odiff score  │
│  h perf <scenario>         → C9 monitor CSV + budget check │
│  h live <cmd>              → C10 optional JSON-RPC to game │
└──────────────┬───────────────────────────────────────────┘
               │ Godot CLI: --headless --path . --script / -- user args
┌──────────────▼───────────────────────────────────────────┐
│ Game project                                              │
│  autoload Harness: parses user args, seeds Rng, fixed     │
│     step, plays CommandBus stream, dumps state/trace, quits│
│  autoload Rng, CommandBus                                 │
│  res://sim/  Node-free rules + Thing/World data (or C# lib)│
│  res://view/ scenes = dumb views reconciling sim state    │
│  res://data/*.tres  tunables + feel targets               │
│  res://test/ unit (sim) + scene tests                     │
└───────────────────────────────────────────────────────────┘
```

Key design decisions (recommendations):
1. **One-shot CLI runs are the main transport.** Each `h run` is seed + commands in, JSON out, then the process exits. A live socket is optional and debug-only.
2. **Pin the engine binary in the repo toolchain**, e.g. `tools/godot/VERSION` + a download script. The API dumps are generated from that exact binary.
3. **Every tool prints at most about 40 lines.** It writes full artifacts to `.harness/out/<run-id>/`, and the agent opens those only when needed.
4. **The engine writes structural scene changes; the agent writes specs.**
5. **A human owns baselines and feel targets.** The agent may propose new baselines but not approve them.
6. **Typed GDScript is enforced.** Set `untyped_declaration` and the `unsafe_*` warnings to error in `project.godot` **[U for exact setting names in 4.7]**, so the parser catches more errors before runtime.

### Components ranked by leverage (value ÷ build cost)

| Rank | Component | Why | Rough cost |
|---|---|---|---|
| 1 | **C1 API ground truth**: `godot --dump-extension-api` (+`--dump-extension-api-with-docs` **[U]**) and `--doctool` XML from the pinned binary, a `godot-docs` checkout at the matching branch, and an `h api` lookup that prints signatures + a short description; plus the CLAUDE.md version pin | Kills F1/F2, the most common failure, at near-zero cost | Hours |
| 2 | **C2 load-check**: import pass, then a `--script` that `load()`s every `.gd/.tscn/.tres` (and instantiates scenes) and reports parse/load errors as `file:line: msg`; warnings-as-errors config; optional `gdlint` (gdtoolkit) | Catches F3–F7 and F13 in seconds | ~1 day |
| 3 | **C3 Godot-3-idiom lint**: regex list (`yield(`, `onready var`, `export var`, `.instance()`, `KinematicBody`, `connect("`, `rand_range`, global `randf(`…) run as a PostToolUse hook | Instant feedback before any run | Hours |
| 4 | **C5 headless test runner wrapper**: gdUnit4 (default choice, pending R1.3) or GUT, plus `dotnet test` for C#; summary output | The article's "verifiable state" | ~1 day |
| 5 | **C4 scene digest + scene-gen**: tree with types, scripts, unique names, key overridden props, groups, signal connections, collision layers by name; generator from a JSON spec via the engine | Fixes F3–F5, the main Godot-specific opacity | 1–2 days |
| 6 | **C6 scenario/replay runner**: `Harness` autoload + `Rng` + `CommandBus`, `--fixed-fps`, state dump, metric assertions | Article's core (determinism + addressable state) | 2–4 days, plus architecture discipline |
| 7 | **C7 feel traces**: per-tick CSV + metrics vs target ranges in `.tres`; `--write-movie` clip for the human | Turns F9/F10 into numbers | 1–2 days |
| 8 | **C8 visual check**: xvfb + Compatibility renderer, fixed camera/state, layer toggles, crop, odiff % vs a human-approved baseline | Useful for UI and art work; secondary | 1–2 days |
| 9 | **C9 perf monitors**: CSV of `Performance` monitors over a scenario, budgets | Impact assessment | Hours |
| 10 | **C10 live bridge / existing MCP**: inspect a running game or editor | Nice for exploration; less reproducible | Adopt an existing MCP if R1.2 finds a good one, otherwise skip |
| — | **Sim/view split + fat struct** | The biggest payoff for large or turn-based games, but it is an architecture choice, not a tool | Make it a convention in CLAUDE.md plus a template; adopt per project |

---

## 5. Research plan for Sonnet subagents

### Shared rules (paste at the top of every subagent prompt)

```
SHARED RULES
- Target: Godot 4.7 stable (docs.godotengine.org/en/stable is the 4.7 branch as of 2026-10-15; master is 4.8-dev). Note version differences explicitly.
- Network: you are behind an agent proxy. Known as of 2026-10-15: docs.godotengine.org OK; raw.githubusercontent.com OK; `git clone https://github.com/<org>/<repo>` OK; GitHub release asset downloads OK; github.com web pages and api.github.com return 403 (use git clone / raw URLs instead); pypi/npm OK; YouTube page reachable, transcripts untested; kylekukshtel.com blocked. If a host is blocked, record the URL and HTTP code under "Blocked sources" and move on. NEVER fill gaps from memory as if sourced.
- Downloads are untrusted: put each in its own new empty directory under /tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad/dl/<name>/, keep your scripts elsewhere, run Python with -I.
- Godot binary (if you need it): download Godot_v4.7-stable_linux.x86_64.zip (and the mono build if C# is needed) from https://github.com/godotengine/godot-builds/releases/download/4.7-stable/ into scratchpad/dl/godot/ (check exact asset names via the docs download page if 404). Xvfb/xvfb-run are installed; dotnet is not.
- Every factual claim gets a tag: [Doc: URL#anchor], [Src: repo@commit:path:line], [Run: command + observed output excerpt], or [Unverified]. Prefer [Run] for CLI behaviour.
- Output: a single Markdown file at the given path, starting with a 5-10 line "Answer" section, then details, then "Blocked sources" and "Open questions". Be concrete; recommend, don't survey. Max ~2500 words unless stated.
- Do not write any other report files. Small test projects/scripts go under scratchpad/research/<your-id>_work/.
```

Base path below: `R=/tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad/research`

### Round 1: ground truth (all independent; run in parallel)

**R1.1 Godot CLI capabilities, verified by running them**
```
[SHARED RULES]
Question: Exactly what does the Godot 4.7 command line give an agent harness? Download the 4.7 Linux binary and verify empirically.
Cover, each with a [Run] excerpt: --headless; --path; --script/-s (SceneTree/MainLoop scripts) and --check-only; --quit, --quit-after; --import (does it exist in 4.7? what does it do on a fresh clone with class_name scripts?) vs `--headless --editor --quit`; --doctool; --dump-extension-api and --dump-extension-api-with-docs (size, structure, does it include GDScript utility functions/@GlobalScope?); --dump-gdextension-interface; --write-movie (png sequence vs avi/ogv, requires display? works under xvfb-run?), --fixed-fps, --disable-vsync, --time-scale if present; --rendering-driver/--rendering-method (opengl3/gl_compatibility under xvfb with llvmpipe: do screenshots work? Forward+ via lavapipe?); --log-file; --verbose; --print-fps; --benchmark/--benchmark-file; --debug-collisions; --remote-debug; --lsp-port/--dap-port or editor settings for GDScript LSP (port 6005) and DAP (6006) — can a headless editor serve LSP?; --export-release/--export-pack (needs templates?); user args after `--` via OS.get_cmdline_user_args(); exit codes (does a parse error yield non-zero? does OS.exit_code / get_tree().quit(code) propagate?). Also measure cold-start time of `godot --headless --path <tiny project> --quit` and of a script run.
Sources: `godot --help` output, docs "Command line tutorial", "Creating movies", "Running code in the editor", godot source main/main.cpp via git clone (shallow).
Output: $R/r1_1_cli.md with a table: flag | exists in 4.7 | verified behaviour | harness use | gotchas. Plus a minimal working recipe for: (a) headless script run with exit code, (b) screenshot PNG under xvfb, (c) 120-frame PNG sequence at fixed fps.
```

**R1.2 Existing Godot MCP servers and AI tooling**
```
[SHARED RULES]
Question: Which existing Godot MCP servers / AI-agent integrations are worth adopting or copying for a Claude Code harness, and what do they actually implement?
Find candidates via npm search (registry.npmjs.org is reachable), PyPI, Godot Asset Library (godotengine.org/asset-library), web search, awesome lists via raw.githubusercontent. Known names to check (unverified): Coding-Solo/godot-mcp, ee0pdt/Godot-MCP, bradypp/godot-mcp, "GDAI MCP", any Godot editor plugin exposing scene tree/screenshots/run controls; also Godot's own LSP/DAP as agent interfaces. For each top candidate, shallow-clone and READ the tool list in source (don't trust READMEs): tools exposed, transport (stdio↔editor plugin websocket? spawns godot CLI?), needs running editor?, Godot version support, screenshots?, scene editing method (raw text vs engine API), maintenance (last commit date from git log), license, security concerns (arbitrary eval?).
Output: $R/r1_2_mcp.md: capability matrix (rows = servers, cols = run game, capture output, scene read, scene write via engine, screenshot, input injection, eval GDScript, needs editor, last commit, license), then a recommendation: adopt X / borrow Y's approach / build own, with reasons tied to the harness components C1–C10 in godot_harness_plan.md (read /tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad/godot_harness_plan.md §4 first).
```

**R1.3 Test frameworks: gdUnit4 vs GUT vs C# options**
```
[SHARED RULES]
Question: Which test framework should the harness standardise on for Godot 4.7, and exactly how is it run headless with machine-readable output?
Compare gdUnit4 (MikeSchulze/gdUnit4), GUT (bitwes/Gut), and for C#: gdUnit4Net, Chickensoft GoDotTest/GodotTestDriver, plain `dotnet test` on a Godot-free class library (can it use GodotSharp structs like Vector2 without the engine running?). Clone repos and read source/docs; if feasible, install each into a tiny 4.7 project and run one passing and one failing test headless [Run].
For each: 4.7 compatibility, install method (addon copy; any editor import needed first?), exact headless command, exit code on failure, report formats (JUnit XML? JSON?), console noise level, scene runner / input simulation / frame stepping (simulate_frames, wait_frames, simulate_action_pressed), mocking/spying, parameterised tests, orphan-node detection, speed (time for 50 trivial tests), C# support.
Output: $R/r1_3_testing.md: comparison table, recommendation with justification, copy-paste commands, and a ~20-line Python/bash snippet sketch that turns the report into a ≤15-line summary (pass/fail counts + first failures with file:line).
```

**R1.4 .tscn/.tres format, UIDs and safe scene writing**
```
[SHARED RULES]
Question: What are the precise rules of Godot 4.7 text scene/resource files, what breaks when an LLM hand-edits them, and what is the safest programmatic way to create/modify scenes?
Sources: docs "TSCN file format" page, docs on UIDs (4.4 `.uid` files), godot source (scene/resources/resource_format_text.cpp, core/io/resource_uid.cpp) via shallow git clone, godot-proposals/issues via raw/clone if needed.
Cover: header fields (format=3/4?, load_steps still present or removed in which version?, uid), ext_resource/sub_resource id format and whether ids must be unique/ordered, node `parent=` path rules, instance/inheritance overrides, `[connection]` and `[editable]` entries, property value syntax (Vector2(), NodePath(), Resource refs, typed arrays/dicts), what happens on load with: unknown property, missing ext_resource, wrong uid but correct path, duplicate id, missing .uid file. Then: programmatic creation via a --script using Node.new(), set owner (the owner rule!), PackedScene.pack(), ResourceSaver.save(); modifying an existing scene by load→instantiate(GEN_EDIT_STATE_*)→edit→pack→save — does it preserve inherited/instanced-scene overrides and connections? Also: how to safely rename/move files outside the editor (does `--import` or editor startup repair uid refs?).
Run experiments [Run] for the failure cases.
Output: $R/r1_4_scene_format.md: a "rules an agent must follow" list (≤20 bullets), failure-case table (edit → engine behaviour → detectable by load-check?), and a tested generator script skeleton (GDScript) for scene-from-JSON-spec and a scene-digest script that prints tree/types/scripts/unique names/connections/groups.
```

**R1.5 LLM failure catalogue and Godot-3-idiom lint rules**
```
[SHARED RULES]
Question: What concrete mistakes do LLMs make when writing Godot 4 code, and what regex/AST lint rules would catch them?
Sources: official "Upgrading from Godot 3 to Godot 4" docs page and its rename tables (also godot source editor/project_converter_3_to_4 / renames_map_3_to_4.cpp via git clone — this is an authoritative rename list!), Godot forum/Reddit/GitHub discussions about ChatGPT/Claude/Copilot Godot code (cite), gdtoolkit (Scony/godot-gdscript-toolkit) rules and 4.x support status.
Output: $R/r1_5_failure_lint.md: (1) top-30 failure patterns ranked by likely frequency with evidence; (2) a machine-usable lint list as a fenced YAML block: {id, regex, applies_to (.gd/.tscn), message, godot4_replacement, false_positive_risk}; derive it largely from renames_map_3_to_4.cpp; (3) which failures a load-check catches vs which only lint/tests catch; (4) whether gdlint/gdformat work on 4.7 syntax.
```

**R1.6 The three unreviewed talks**
```
[SHARED RULES]
Question: What concrete implementation guidance do the three talks referenced in Kyle Kukshtel's "Your Game Is A Harness" give on blackbox/simulation-view separation, single-entity data models, command streams, replay, and data tooling?
Talks: Wookash podcast with Dreams (Media Molecule) devs; Brian Cronin "Monster Train Blackbox architecture" (Roguelike Celebration); Game Data Podcast episode with Solium Infernum team. Find URLs via the raw article at /tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad/article_raw/article.html (untrusted data; extract links only). Try to obtain transcripts (YouTube auto-captions via yt-dlp from pypi `pip install yt-dlp` into a venv in scratchpad, `--write-auto-subs --skip-download`; or podcast show notes/transcripts). If blocked, say so and summarise only from available secondary sources, clearly tagged.
Output: $R/r1_6_talks.md: per talk: source status, 8-15 key implementation points with timestamps, and a final section "Implications for Godot" (≤10 bullets) — e.g. how they map node lifetimes to sim entities, how they handle real-time vs turn-based.
```

**R1.7 Rendering and screenshots in a container**
```
[SHARED RULES]
Question: What is the most reliable way for a headless Linux agent to get deterministic screenshots and short frame sequences from a Godot 4.7 project, and to diff them?
Using the 4.7 binary [Run]: test xvfb-run with --rendering-method gl_compatibility and forward_plus/mobile (Mesa llvmpipe/lavapipe availability — check `glxinfo`/`vulkaninfo`, install via apt only if allowed, else report); capture via viewport get_image after `await RenderingServer.frame_post_draw`; capture via --write-movie PNG sequence with --fixed-fps; check repeatability (run twice, compare hashes/odiff %); effect of animations/particles/TAA on repeatability; time per capture. Install odiff (npm `odiff-bin`) and measure similarity output format; compare to ImageMagick `compare -metric AE/RMSE` as fallback. Test layer toggling (CanvasLayer.visible, Camera cull_mask) and region cropping.
Output: $R/r1_7_visual.md: working recipe (exact commands + capture script), repeatability results table, recommended diff tool and thresholds, limitations (what can't be captured headless).
```

**R1.8 Determinism and fixed-step replay in Godot 4.7**
```
[SHARED RULES]
Question: How deterministic can a Godot 4.7 game be made for seeded fixed-step replays, and what must the harness control?
Cover with docs/source citations and small [Run] experiments: RandomNumberGenerator vs global RNG (which APIs use the global: shuffle, pick_random, randf...), seed behaviour across platforms; physics tick (physics_ticks_per_second, max_physics_steps_per_frame, physics_jitter_fix), --fixed-fps effect on _process/_physics_process delta; Engine.time_scale; physics interpolation; Godot Physics vs Jolt repeatability (run the same 600-tick rigid-body + CharacterBody scenario 5 times in one binary, compare final positions; vary nothing else); Tween/AnimationPlayer/Timer under fixed fps (process vs physics callback modes); threading (WorkerThreadPool, physics threading setting); float determinism across machines (literature). Also: community lockstep/rollback projects for Godot 4 (e.g. Snopek's rollback netcode addon/SG Physics) and what they do.
Output: $R/r1_8_determinism.md: a "determinism checklist" for project settings + code conventions, experiment results table, and a recommendation on exact-match vs tolerance assertions per subsystem.
```

### Round 2: design and prototypes (depends on Round 1)

Each prompt says "Read first:" and lists the Round 1 files it needs. If an input file is missing or reports blocks, the agent must state which assumptions it is making as a result.

**R2.1 Core harness prototype: C1, C2, C3, C4, C5**
```
[SHARED RULES]
Read first: $R/r1_1_cli.md, $R/r1_3_testing.md, $R/r1_4_scene_format.md, $R/r1_5_failure_lint.md, and §4 of /tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad/godot_harness_plan.md.
Task: Build and test a working prototype in $R/r2_1_work/ consisting of: a tiny Godot 4.7 sample project (one player scene, one UI scene, one sim class, 5 tests incl. 1 failing), and `tools/harness/h` with verbs `api`, `check`, `lint`, `test`, `digest`, `scene-gen`. Use Round-1 recommended commands. Each verb must: exit non-zero on failure, print ≤40 lines, write full logs to .harness/out/. Seed deliberate faults (Godot-3 syntax, broken ext_resource id, bad $path, missing signal method, untyped var) and record which verb catches each and how fast.
Output: $R/r2_1_core_harness.md: design notes, fault-detection matrix (fault × verb → caught? time), timings, and the source of each tool inline (or path to files in r2_1_work). Flag anything that required the editor GUI.
```

**R2.2 Command/replay runner and transport (C6, C10)**
```
[SHARED RULES]
Read first: $R/r1_1_cli.md, $R/r1_2_mcp.md, $R/r1_8_determinism.md, $R/r1_6_talks.md.
Task: Design and prototype (in $R/r2_2_work/, may copy r2_1_work's sample project if present) a `Harness` autoload + `Rng` + `CommandBus` that runs: `godot --headless --path . -- --scenario=res://scenarios/x.json` where the scenario = {scene, seed, fixed_fps, frames, commands:[{frame, type, target, value}], dumps:[{frame, what}], asserts:[{frame, expr|metric, op, value, tol}]} and writes state.json/metrics.json and exits with a code. Decide how `target` addresses entities (stable ids registry, not NodePaths) and how input actions are injected (Input.parse_input_event vs action_press vs sim commands). Then evaluate the live options: (a) adopt the MCP from R1.2, (b) a debug-only WebSocket JSON-RPC autoload, (c) EngineDebugger message captures — recommend one for "inspect running game" only. Run the scenario 3× and report repeatability.
Output: $R/r2_2_replay.md: schema (JSON Schema block), autoload code, recommendation on live transport, repeatability results, limitations.
```

**R2.3 Sim/view split templates for GDScript and C#**
```
[SHARED RULES]
Read first: $R/r1_6_talks.md, $R/r1_8_determinism.md, $R/r1_3_testing.md.
Question: What are the concrete, minimal project templates that give Godot the article's "blackbox simulation + dumb view + fat struct + commands" — (a) pure GDScript, (b) C# with a Godot-free class library + dotnet test — and when should a project NOT use them (real-time physics-heavy games)?
Sources: Chickensoft (chickensoft.games, GitHub via clone: GameDemo, LogicBlocks, AutoInject), community ECS/data-oriented Godot projects, Godot docs on C# project setup and export limitations (web export for C# in 4.7?). Sketch file layout, the Thing/World/Command types, view reconciliation (spawn/despawn nodes from state diffs, id→node map), save/load path, and the test command. Measure (if dotnet installable from Microsoft feeds through the proxy; else mark unverified) test loop time C# lib vs GDScript headless.
Output: $R/r2_3_architecture.md: decision table by game type (turn-based, tactics, deckbuilder, platformer, physics sandbox, UI-heavy), both templates as code skeletons, migration notes for existing node-centric projects.
```

**R2.4 Feel and timing as numbers (C7)**
```
[SHARED RULES]
Read first: $R/r1_8_determinism.md, $R/r1_7_visual.md, $R/r1_3_testing.md.
Question: Which game-feel properties can be turned into numeric metrics from per-tick traces in Godot, and how should targets be expressed so an agent can tune parameters without judging feel itself?
Sources: game-feel literature (Steve Swink "Game Feel", GDC talks on platformer jump design e.g. "Math for Game Programmers: Building a Better Jump" — cite), Godot docs on CharacterBody2D, Tween easing, AnimationPlayer. Define metrics for: jump (apex height, time-to-apex, air time, coyote/buffer frames), run (accel/decel frames to max), camera (lag, overshoot, settle time), tweens/UI (duration, easing curve sampled), hit-stop/screenshake (frames, amplitude). Prototype a trace recorder autoload (CSV per physics tick of selected node properties) and a Python metrics script on the R2.1/R2.2 sample if present.
Output: $R/r2_4_feel.md: metric catalogue table (metric, formula from trace, typical ranges with source, Godot properties that drive it), a `FeelTargets` .tres schema, trace recorder code, and the human-in-the-loop protocol (agent produces --write-movie clip + metric table; human approves).
```

**R2.5 Text profiling and impact assessment (C9)**
```
[SHARED RULES]
Read first: $R/r1_1_cli.md.
Question: What text-only profiling is available for Godot 4.7 (GDScript and C#), and what should `h perf` do?
Cover [Run where possible]: Performance.get_monitor list + custom monitors dumped to CSV per frame; --benchmark outputs; samply (cargo/prebuilt) on the godot binary — does it resolve symbols with official builds? GDScript visibility?; Tracy/Perfetto integration in recent Godot versions (find PRs/docs; is it in 4.7 official builds or compile-only?); dotnet-trace/dotnet-counters for C#; the editor debugger's profiler protocol (could a script capture GDScript function timings via EngineDebugger profiler API?).
Output: $R/r2_5_perf.md: recommended `h perf` design (inputs, CSV columns, budget file format, summary output), plus what is impossible without the editor.
```

**R2.6 Claude Code integration mechanics**
```
[SHARED RULES]
Read first: $R/r1_2_mcp.md and §4 of the plan file.
Question: How exactly should the harness be wired into Claude Code (current version) — CLAUDE.md structure, skills (SKILL.md format, progressive disclosure), hooks (PostToolUse matchers on file globs, Stop hooks, exit-code semantics for blocking/feedback), subagents (.claude/agents/*.md) for log triage and API lookup, permissions allowlist for `tools/harness/h *` and godot, MCP config (.mcp.json) if adopting one, SessionStart hook to download/pin the Godot binary in cloud sessions.
Sources: official Claude Code docs (docs.anthropic.com / code.claude.com — report if blocked), anthropics GitHub examples via clone.
Output: $R/r2_6_claude_code.md: concrete file tree of .claude/ for a Godot project with each file's purpose, hook JSON examples, and guidance on keeping tool output small. Cite doc pages for every mechanism.
```

### Round 3: synthesis and evaluation (depends on Round 2)

**R3.1 Draft harness deliverable (the end state)**
```
[SHARED RULES]
Read first: every file in $R/ (r1_* and r2_*), plus the plan file.
Task: Produce the end-state draft, as files under $R/r3_1_deliverable/:
  1. HARNESS_SPEC.md — components C1–C10 final design, each with: purpose, failure modes mitigated (F-ids from plan §3), CLI contract (args, output format, exit codes), implementation status (prototyped in R2.x / design only).
  2. CLAUDE.md — the project template an agent would read: version pin, golden rules (≤15), tool menu (`h` verbs + when to use), conventions (typed GDScript, %UniqueName, code-connected signals, no hand structural tscn edits, Rng only, commands for state changes), what to ask the human (feel, baselines, @tool).
  3. .claude/skills/{godot-api,godot-scene,godot-scenario,godot-visual,godot-feel}/SKILL.md
  4. .claude/settings.json hooks + permissions; .claude/agents/log-triage.md
  5. tools/harness/ — consolidated working scripts from R2.1/R2.2/R2.4/R2.5.
  6. ADOPTION.md — 3 adoption tiers: (A) any existing project in 1 day (C1-C5), (B) +scenarios/feel (C6-C7), (C) full sim/view architecture for new projects.
Mark every unverified element. Output summary: $R/r3_1_summary.md (≤800 words, list of files, known gaps).
```

**R3.2 Evaluation protocol (can run in parallel with R3.1 once Round 2 is complete)**
```
[SHARED RULES]
Read first: $R/r2_1_core_harness.md, $R/r2_2_replay.md, $R/r2_4_feel.md, plan §3.
Task: Design a small benchmark to measure whether the harness improves Claude Code on Godot work: 10-12 tasks on the sample project covering F1-F15 (e.g. "add a dash with 0.15s cooldown and i-frames", "move HealthBar into a new HUD CanvasLayer without breaking refs", "port this Godot 3 snippet", "make jump apex 3 tiles at 0.4s", "fix flaky test", "add an enemy type via data only"). For each: starting state, success check that is automatic (h check/test/run assertions), and metrics (success, turns, tokens, wall time, human interventions). Define baseline (plain Claude Code + Godot binary only) vs harness conditions. If time permits, run 2-3 tasks in each condition using `claude -p` and report.
Output: $R/r3_2_eval.md.
```

### Round 4 (optional): iterate
Run only after a human has reviewed R3.1 and R3.2. Run the full eval, fix the three weakest components, and update the deliverable. One subagent per weak component. Each subagent prompt is built from that component's R3.2 failure notes.

### Dependency summary
- **R1.x** are all independent.
- **R2.1** ← R1.1, R1.3, R1.4, R1.5
- **R2.2** ← R1.1, R1.2, R1.6, R1.8
- **R2.3** ← R1.3, R1.6, R1.8
- **R2.4** ← R1.3, R1.7, R1.8 (and the R2.1/R2.2 sample if present)
- **R2.5** ← R1.1
- **R2.6** ← R1.2
- **R2.x scheduling.** R2.2 and R2.4 benefit from R2.1's sample project. Options:
  - run R2.1 first, or
  - let R2.2 and R2.4 build their own minimal sample.

  Recommended: start R2.1, R2.3, R2.5 and R2.6 in parallel; start R2.2 and R2.4 once R2.1 finishes.
- **R3.1/R3.2** ← all of R2. **R4** ← a human review.

### Practical constraints and orchestration notes
- **Proxy.**
  - github.com web pages and api.github.com are blocked. Use `git clone --depth 1`, raw URLs and release downloads instead.
  - If a subagent finds another block, it logs it. The orchestrator collects the "Blocked sources" sections after each round and decides whether to ask the user to allowlist hosts.
- **Running the binary.** Round 1 agents that run Godot each download about 60–70 MB. Pre-download once to `scratchpad/dl/godot/` before launching Round 1 and tell agents the path, to avoid duplicate downloads and races.
- **Citations.** Uncited claims are treated as unverified at synthesis time. R3.1 must keep [Unverified] tags rather than smoothing them over.
- **Context hygiene for the orchestrator.**
  - Read each round's "Answer" sections first, and full files only where decisions depend on them.
  - Keep each file under about 2,500 words, so a full round fits in the context for synthesis.
- **Human decisions to collect after Round 1:**
  - GDScript vs C# (or both),
  - the target game genre(s),
  - whether to adopt an external MCP,
  - acceptance of the "agent never judges feel" rule.

---

## 6. Recommendations to act on now (before research finishes)
1. Pin Godot 4.7 and generate `extension_api.json` + doctool XML from that binary. Add a CLAUDE.md line: "Godot 4.7 only; Godot 3 syntax is a bug; look up APIs with `h api` before using unfamiliar members."
2. Add the Godot-3-idiom grep as a PostToolUse hook. The rename map in the Godot source (`editor/renames_map_3_to_4.cpp` **[U path]**) is the authoritative list.
3. Make "import, then load every resource" a single command, and run it after every structural change.
4. Set conventions:
   - typed GDScript with warnings as errors,
   - `%UniqueName` + typed `@export` refs,
   - signals connected in code,
   - one seeded `Rng` autoload,
   - state changes through commands for anything you will want to replay.
5. Treat feel and visuals as human-approved targets that the agent measures against, never as the agent's own judgement.
