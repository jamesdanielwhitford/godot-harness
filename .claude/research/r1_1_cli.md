# R1.1 Godot 4.7 CLI capabilities for an agent harness (verified by running)

Binary: `Godot_v4.7-stable_linux.x86_64`, `--version` -> `4.7.stable.official.5b4e0cb0f` [Run: `godot --version`]. Source checkout used: godotengine/godot tag 4.7-stable, commit 5b4e0cb0fd279832bbdd69fed5354d4e5ad26f88 (matches the binary hash) [Run: `git rev-parse HEAD` in dl/godotsrc/src].
Machine: 4 cores, Xvfb present, Mesa 25.2.8 llvmpipe (GL 4.5 and Vulkan 1.4.318 lavapipe). Test projects: `.../research/r1_1_work/{proj,f1,f2,f3}`; helper `.../r1_1_work/tools/lsp_probe.py`.

## Answer

1. **Script runs and exit codes work and are cheap.** `godot --headless --path P -s res://x.gd -- args` starts and finishes in ~0.27-0.30 s. `quit(N)` in a `SceneTree` script propagates as the process exit code (observed rc=3). A parse error in the script yields rc=1. [Run: s_ok.gd with `quit(3)` -> `rc=3 .29s`; s_bad.gd -> `rc=1`]
2. **There is no `OS.set_exit_code` / `OS.exit_code` in GDScript in 4.7.** Both fail to parse. Use `get_tree().quit(code)` or `SceneTree.quit(code)` [Run: `Static function "set_exit_code()" not found in base "GDScriptNativeClass"`; `Cannot find member "exit_code" in base "OS"`]. The C++ `OS::set_exit_code` is documented as SceneTree-internal [Src: godot@4.7-stable:core/os/os.h:351-354].
3. **Biggest gotcha: a fresh clone has no `.godot/` and `class_name` types do not resolve.** `-s` and `--check-only` fail with `Identifier "Hero" not declared in the current scope` and rc=1 until the global class cache exists [Run: fresh copy f2]. Fix: run `godot --headless --path P --import` once (6.5-7.7 s, rc=0), which builds `.godot/global_script_class_cache.cfg` and `.uid` files. `--headless --editor --path P --quit` does the same (8.5 s, rc=0) [Run: f1, f3]. `--import` is real in 4.7 and is implemented as editor + `wait_for_import` + `quit_after=1` [Src: godot@5b4e0cb0f:main/main.cpp:1678-1682].
4. **A runtime error in `_init` does NOT stop or fail the process.** A script that calls a method on null prints `SCRIPT ERROR`, skips the rest of `_init`, never reaches `quit()`, and hangs forever (timeout rc=124). A harness must always wrap runs in `timeout` and grep stdout/stderr for `SCRIPT ERROR` / `ERROR:` rather than trust the exit code [Run: s_rt.gd -> rc=124 with `Invalid call. Nonexistent function 'foo' in base 'Nil'`].
5. **Screenshots and movies work under Xvfb with both Forward+ (lavapipe) and Compatibility (llvmpipe GL).** Pixel check of the saved PNG: red rect (255,0,0) and blue circle (0,0,255) at the expected coordinates in both renderers. They do NOT work in `--headless`: the screenshot recipe hangs (`await RenderingServer.frame_post_draw` never fires, rc=124) and `--write-movie` aborts with rc=134 (SIGABRT, `Parameter "t" is null`).
6. **`--fixed-fps` makes simulation time independent of wall time**: 3000 frames = exactly 50.0 s of delta ran in 0.47 s wall headless [Run]. `--write-movie x.png` gives a numbered PNG sequence plus a `.wav`; `.avi` (MJPEG) and `.ogv` (Theora) also work under Xvfb.
7. **A headless editor serves GDScript LSP** (`--headless --editor --path P --lsp-port 6005`). Verified with a raw JSON-RPC client: `initialize` returned 22 capability providers, `didOpen` of a broken script returned `publishDiagnostics` with the type error, and `documentSymbol` worked. The DAP port (6006) also accepted connections. Without `--editor` the LSP port is closed. Needs ~10 s startup. This is the strongest "GDScript analyser" hook for a harness.
8. **`--dump-extension-api(-with-docs)` and `--doctool` are offline and fast** (1-2 s) and give a complete API reference to grep (details below). `--export-pack` works without export templates; `--export-release/--export-debug` need templates and fail rc=1 without them.

## Flag table

Cold timings are wall-clock on this box. "exists" is from `godot --help` of the 4.7 editor build unless noted. [Run] tags abbreviate `godot --help` as `help`.

| Flag | Exists in 4.7 | Verified behaviour | Harness use | Gotchas |
|---|---|---|---|---|
| `--headless` | yes [Run: help] ("--display-driver headless --audio-driver Dummy") | Start+`--quit` of a tiny project: 0.19-0.36 s. No window, no GPU init; `RenderingServer.get_video_adapter_name()` is empty. | Default for all logic/unit runs. | No rendering: screenshots hang, `--write-movie` crashes (rc=134). `--print-fps` still reports (144 fps) because vsync is faked. |
| `--path DIR` | yes | Selects the project; invalid dir prints `Invalid project path specified: "/nonexistent", aborting.` rc=1 [Run]. | Always pass explicitly. | Shown availability `X` (editor/non-hardened builds). |
| `-s/--script FILE` | yes | Runs a `SceneTree`/`MainLoop` script instead of the main scene. 0.27-0.30 s. User args after `--` arrive via `OS.get_cmdline_user_args()`: `-- a b=1 --c` -> `["a","b=1","--c"]` [Run]. | One-shot checks, test runners, project scanners. | Script must `quit()` itself or it runs forever. Engine does not parse args after `--`. |
| `--check-only` | yes | With `-s`: parse only, quit. Good file rc=0 silent; syntax error rc=1 with `SCRIPT ERROR: Parse Error: ... at: GDScript::reload (res://s_bad.gd:4)`; type error rc=1 `Cannot assign a value of type String to variable "x" with specified type int.` [Run]. | Cheap per-file lint (0.3 s) after edits. | One script per invocation. On a fresh clone `class_name` references fail until `--import` (see Answer 3). Cannot lint scenes (.tscn) this way. |
| `--main-loop NAME` | yes [Run: help] | Not exercised. [Unverified beyond help text] | | |
| `--quit` / `--quit-after N` | yes | `--quit` = one iteration. `--quit-after 5` ran exactly 5 frames (`frames=5`). With `--write-movie` it equals the frame count: 120 -> 120 PNGs [Run]. | Bound every main-scene run. | Counts main-loop iterations, not seconds; with real-time pacing 300 frames took 2.4 s headless. |
| `--import` | yes (editor builds) | Fresh project: 7.6 s rc=0, creates `.godot/{global_script_class_cache.cfg,uid_cache.bin,imported,editor}` and `*.uid` files. Warm: 6.6 s. [Run]. Equivalent source: editor=true, wait_for_import, quit_after=1 [Src: main/main.cpp:1678-1682]. | First step after clone/new assets; run before any `-s` use. | Loads the full editor UI even headless (hence 6+ s even when nothing changed). Writes `.uid` files next to every script: commit them or `.gitignore` per team policy. |
| `--headless --editor --quit` | yes | Same effect as `--import` for the class cache: 8.5 s rc=0 on fresh project; creates `.gdignore` in `.godot`. [Run: f1] | Alternative to `--import`. | Slower than `--import`. |
| `--doctool [PATH]` | yes | `godot --headless --doctool .` ran 1.3 s rc=0, produced 7.1 MB: `doc/classes/*.xml` (810 files incl. `@GlobalScope.xml`, `EditorPlugin.xml`, `SceneTree.xml`), `modules/*/doc_classes`, `platform/*`. `@GDScript.xml` (under `modules/gdscript/doc_classes/`) holds the GDScript-only builtins: `Color8, assert, char, convert, dict_to_inst, get_stack, inst_to_dict, is_instance_of, len, load, ord, preload, print_debug, print_stack, range, type_exists` [Run: grep of `<method name=`]. Output said `Erasing old docs at: ./doc/classes`. | Offline XML API docs for grep/lookup. `--gdscript-docs PATH` generates docs from a project's `##` comments. | **Deletes and regenerates `./doc/classes` under the target dir**: run it only in a scratch dir. Implies headless [Src: main.cpp:1740]. |
| `--dump-extension-api` | yes | 1.1 s, `extension_api.json` 6.97 MB. Top keys: header, builtin_class_sizes, builtin_class_member_offsets, global_constants(11 ints), global_enums(22 incl. Key, MouseButton, Error), utility_functions(114), builtin_classes(38), classes(1036), singletons(41), native_structures(14). Header says `version 4.7.0 stable`. [Run: python json load] | Machine-readable class/method/signal/property/enum signatures; also good for a name-existence check (hallucinated API detector). | **Does not contain GDScript-only builtins** (`range, preload, len, assert, load, char, Color8` are absent from `utility_functions`; `print, lerp, randf, str, typeof` are present). Use `--doctool` `@GDScript.xml` for those. `KEY_A`-style constants are inside the `Key` enum, not `global_constants`. No descriptions. |
| `--dump-extension-api-with-docs` | yes | 2.3 s, 11.9 MB. Adds `brief_description` and `description` to classes and `description` to utility functions, e.g. `sin`: "Returns the sine of angle [param angle_rad] in radians." [Run] | Single-file reference with prose. Includes `@GlobalScope` utility functions (as `utility_functions`) but not `@GDScript` ones. | Too big to read whole; grep/`jq` it. |
| `--validate-extension-api FILE` | yes | Validated the 4.7 dump against itself: rc=0 [Run]. | Not relevant to an agent harness. | |
| `--dump-gdextension-interface` / `-json` | yes | Wrote `gdextension_interface.h` (142 KB) and `.json` (328 KB; keys `_copyright, $schema, format_version, types, interface`; 179 interface entries). rc=0 [Run]. | Only if the project builds a GDExtension. | |
| `--write-movie FILE` | yes | Under Xvfb: `f.png` -> `f00000000.png ... f00000119.png` (120 frames, 320x240 RGB) plus `f.wav`; 2.8 s for 120 frames with Forward+/lavapipe, 1.35 s with `--rendering-method gl_compatibility` at 60 fps. `f.avi` -> 1.13 MB "AVI, 320 x 240, 30.00 fps, video: Motion JPEG". `f.ogv` -> "Ogg data, Theora video". Prints `Movie Maker mode enabled, recording movie in 320x240 @ 30 FPS...` and `120 frames at 30 FPS (movie length: 00:00:04:00)` [Run]. | Visual regression, animation review, frame-by-frame artifacts. PNG sequence is easiest for an agent to inspect. | Needs a display: `--headless` aborts (rc=134, `Parameter "t" is null`). Number of frames is set by `--quit-after`; the filename stem gets an 8-digit counter appended. Forces fixed FPS. Output dir must already exist (I created it first; not tested otherwise). |
| `--fixed-fps N` | yes | 300 frames at 60 -> `sum_delta=5.0`, wall 0.54 s; first delta 0.016667. 3000 frames -> 50.0 s of sim in 0.47 s wall (with `--disable-vsync --max-fps 0`). [Run] | Deterministic, faster-than-real-time simulation. | Disables real-time sync, so wall-clock timers (`OS.get_ticks_msec`, real Timers using wall time) no longer match game time. |
| `--time-scale X` | yes | With `--fixed-fps 60 --time-scale 4`: `Engine.time_scale=4.0`, first delta 0.0667, 300 frames = 20.0 s of game time [Run]. | Speed up game logic per frame. | Scales delta per frame, so physics steps get coarse. |
| `--disable-vsync` | yes | Accepted; with Xvfb GL prints `Could not set V-Sync mode ... not supported by the graphics driver` (harmless warning) [Run]. | Pair with movie/fixed-fps runs. | |
| `--max-fps N` | yes | Accepted (0 = unlimited). | | |
| `--rendering-method` / `--rendering-driver` | yes | Under `xvfb-run`: default = `Vulkan 1.4.318 - Forward+ - Using Device #0: Unknown - llvmpipe (LLVM 20.1.2, 256 bits)`. `--rendering-driver opengl3` or `--rendering-method gl_compatibility` -> `OpenGL API 4.5 (Core Profile) Mesa 25.2.8 - Compatibility - Using Device: Mesa - llvmpipe`. Both produced correct pixels [Run]. | Pick `gl_compatibility` for speed/stability in CI; Forward+ works too via lavapipe. | The project setting `rendering/renderer/rendering_method` still reads `forward_plus` when you override with `--rendering-driver opengl3`, so do not use the setting to learn the active renderer; use the startup banner or `RenderingServer.get_video_adapter_name()`. ALSA noise unless `--audio-driver Dummy`. |
| `--audio-driver Dummy` | yes | Silences the ALSA `cannot find card '0'` error spam and "All audio drivers failed" warning under Xvfb [Run]. | Always add outside `--headless`. | |
| `--resolution WxH` | yes [Run: help] | Not separately tested; screenshots took project viewport size (320x240). | | |
| `--log-file F` | yes | Wrote 18 lines incl. banner and verbose lines to the file while stdout still received output [Run: `wc -l o.txt my.log` -> 22 / 18]. | Capture logs to a known path. | Path absolute or relative to project dir. |
| `-v/--verbose`, `--quiet`, `--no-header` | yes | `--verbose` adds TextServer/SDL/V-Sync lines [Run]. `--quiet` and `--no-header` exist [Run: help]; not separately exercised. | `--no-header` for clean parsing. | |
| `--print-fps` | yes | Headless 700 frames: `Project FPS: 144 (6.94 mspf)` printed [Run]. | Cheap perf signal. | Value reflects the faked vsync headless; not meaningful for GPU perf. |
| `--benchmark` / `--benchmark-file PATH` | yes (editor builds) | Requires editor: `--headless --editor --benchmark --quit` printed per-section startup timings (e.g. `[EditorHelp] Generate Documentation (Run 2): 3429 msec`); `--benchmark-file` wrote JSON (keys like `"[Startup] Main::Setup": 0.049203`) [Run]. | Measures engine/editor startup phases only. | Not a gameplay profiler. Path must be absolute. |
| `--debug-collisions`, `--debug-paths`, `--debug-navigation` | yes (D: editor/debug builds) | `--debug-collisions` accepted, scene ran 5 frames rc=0 [Run]. Effect is visual (shape overlays), so only useful with a display + `--write-movie`/screenshot. | Combine with screenshot recipe for physics review. | Not visually verified. |
| `--remote-debug URI` | yes | With nothing listening on `tcp://127.0.0.1:6007`: run still completed rc=0 but start took 3.3 s vs 0.4 s (connect timeout) [Run]. | Attach a custom debugger/profiler peer. | Delays startup if peer absent. Wire protocol not investigated. [Unverified] |
| `--debug-server URI` | yes (editor only) | Exists in help; not exercised. | | |
| `--lsp-port P` / `--dap-port P` | yes (editor only, E) | Headless editor served LSP on the port: `initialize` ok (22 capability keys incl. hover, completion, definition, references, rename, documentSymbol, workspaceSymbol, formatting), `publishDiagnostics` for broken script with `severity 1` and message `Cannot assign a value of type "String" as "int".`, `documentSymbol` returned `var f: int = 0`. DAP port 6006 accepted a TCP connection. Closed without `--editor`. Probe client: `r1_1_work/tools/lsp_probe.py`. Log also showed `ERROR: LSP: Failed to parse script: res://s_type.gd` [Run]. | Real analyser for GDScript: diagnostics, symbols, go-to-definition for an agent. | Needs an editor process kept alive (~10 s to be ready); one editor per project dir (lock). Default port 6005 comes from editor settings, not tested here. Only LSP and a DAP TCP connect were tested; DAP protocol exchange not tested. |
| `--export-release/--export-debug PRESET PATH` | yes | With no `export_presets.cfg`: rc=1 `This project doesn't have an export_presets.cfg file at its root.` With a preset but no templates: rc=1 `No export template found at the expected path: /root/.local/share/godot/export_templates/4.7.stable/linux_release.x86_64` [Run]. | Needs templates (not installed here). | 5 s overhead; reimports first. |
| `--export-pack PRESET PATH.pck` | yes | With a minimal Linux preset and no templates: rc=0, 12.6 MB `g.pck`; `godot --headless --main-pack g.pck --quit-after 3` ran the project rc=0 [Run]. | Build-pipeline smoke test without templates. | Printed an `ERROR: Can't open file ... f.wav-....sample` for a stray .wav not yet imported in my test project; rc stayed 0. Do not rely on rc alone. |
| `--convert-3to4`, `--build-solutions` | yes [Run: help] | Not relevant (no C#/3.x). | | `--build-solutions` needs a C# build [Src: main.cpp:5178-5186]. |

## Exit-code behaviour summary [Run unless noted]

| Situation | rc |
|---|---|
| `quit(3)` from SceneTree script `_init` | 3 |
| Parse/type error in `-s` script (run or `--check-only`) | 1 |
| Bad `--path` | 1 |
| Missing `--scene res://nope.tscn` | 1 (`Failed loading scene`) |
| Runtime script error in `_init` (null call) | process hangs; killed by timeout -> 124; no non-zero exit by itself |
| Main-scene run with `--quit-after N` | 0 |
| Parse error inside an unrelated script loaded later by the running game | not tested [Unverified] |
| Export failure | 1 |
| `--write-movie` in `--headless` | 134 (SIGABRT) |

## Minimal working recipes

Assume `G=/path/to/godot`, `P=/path/to/project`.

### Prerequisite (once per clone, and after adding a `class_name` file)
```
timeout 120 $G --headless --path $P --import      # ~7 s, rc=0; builds .godot/ class cache
```

### (a) Headless script run with exit code
`$P/tools/check.gd`:
```gdscript
extends SceneTree
func _init():
	var args := OS.get_cmdline_user_args()
	print("args=", args)
	var failed := false
	# ... do work, set failed ...
	quit(1 if failed else 0)   # ALWAYS reach quit(); a runtime error before it hangs the process
```
Run:
```
timeout 60 $G --headless --path $P -s res://tools/check.gd -- --foo bar > out.txt 2>&1; rc=$?
# rc: script's quit() value; 1 on parse error; 124 on hang. Also fail if out.txt contains "SCRIPT ERROR" or "ERROR:".
```
Observed: `ok args=["a", "b=1", "--c"] h=hi` rc=3 in 0.29 s.
Syntax-only: `$G --headless --path $P -s res://x.gd --check-only` (rc 0 or 1, 0.3 s).

### (b) Screenshot PNG under Xvfb
`$P/shot.gd` attached as a child node of the scene to capture (or autoload), tested at `r1_1_work/f3/shot.gd`:
```gdscript
extends Node
func _ready():
	await get_tree().process_frame
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	var err := img.save_png("res://shot_out.png")   # or an absolute path
	print("saved err=", err, " size=", img.get_size())
	get_tree().quit(0)
```
Run (works with default Forward+/lavapipe and with Compatibility):
```
timeout 60 xvfb-run -a $G --path $P --audio-driver Dummy --rendering-method gl_compatibility --scene res://shot.tscn
```
Observed: `saved err=0 size=(320, 240)`, valid PNG, correct pixels (255,0,0) and (0,0,255), rc=0. Never run this with `--headless` (hangs).

### (c) 120-frame PNG sequence at fixed fps
```
mkdir -p $P/out_frames
timeout 120 xvfb-run -a $G --path $P --audio-driver Dummy --rendering-method gl_compatibility \
  --write-movie $P/out_frames/f.png --fixed-fps 30 --disable-vsync --quit-after 120
```
Observed (Forward+ variant): `Movie Maker mode enabled, recording movie in 320x240 @ 30 FPS...`, `120 frames at 30 FPS (movie length: 00:00:04:00)`, files `f00000000.png ... f00000119.png` (120) plus `f.wav`, 2.8 s wall, rc=0. Use `.avi` instead of `.png` for a single MJPEG file. Use a fresh output dir per run (the engine does not clear it).

## Cold-start numbers [Run, wall clock]
| Command | Time |
|---|---|
| `--headless --path P --quit` (project with .godot present or not) | 0.19-0.36 s |
| `--headless -s res://x.gd` | 0.27-0.30 s |
| `--headless --path P --import` (fresh / warm) | 7.6 s / 6.6 s |
| `--headless --editor --path P --quit` (fresh) | 8.5 s |
| `--doctool .` | 1.3 s |
| `--dump-extension-api` / `-with-docs` | 1.1 s / 2.3 s |
| `xvfb-run ... --quit-after 3` (Forward+ lavapipe) | ~1.3 s (movie of 120 frames: 2.8 s; GL 60 fps: 1.35 s) |
| headless editor ready for LSP | ~10 s (probe succeeded after `sleep 12`; exact time not measured) |
| `--export-pack` | 4.8 s |

## Blocked sources
- Not attempted over the network beyond what was needed: godot source came from an existing shallow clone of `https://github.com/godotengine/godot` tag `4.7-stable` (already on disk in `scratchpad/dl/godotsrc/src`, commit verified identical to the binary). I did not fetch the docs pages ("Command line tutorial", "Creating movies", "Running code in the editor"); all behaviour above is from `--help`, running the binary and reading `main/main.cpp`. No source was blocked.

## Open questions
- `--main-loop`, `--quiet`, `--no-header`, `--resolution`, `--debug-server`, `--convert-3to4` were only confirmed from `--help`, not exercised.
- Default LSP port 6005 and DAP port 6006 as editor-setting defaults were not read from settings; I passed the ports explicitly. DAP protocol traffic (launch/breakpoints) not tested.
- Whether a parse error in a script loaded by the running main scene (not `-s`) changes the exit code was not tested.
- `--write-movie` into a non-existent directory was not tested.
- `--debug-collisions` visual output not inspected.
- No GPU path tested (only llvmpipe/lavapipe CPU rendering); timings and render fidelity will differ on real GPUs.
- `--remote-debug` protocol/peer implementation not explored.
