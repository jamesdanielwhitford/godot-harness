# R1.2 Existing Godot MCP servers and AI tooling

Date: 2026-10-15. Target: Godot 4.7 stable. All clones are shallow (`--depth 1`) under `/tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad/dl/mcp/<owner>_<repo>/`. "Last commit" is the HEAD commit date of that shallow clone. Code was read, not installed, except one sandboxed run of beremaran's published npm package (see "Dynamic test").

## Answer

- There is no official Godot MCP server. [Run: `curl registry.npmjs.org/-/v1/search?text=godot-mcp` returned about 25 unrelated community packages; Godot Asset Library API `filter=mcp` lists several community addons, e.g. asset 5375 "Godot MCP Toolkit", 5245 IvanMurzak "Godot-MCP", 5193 "Godot MCP Enhanced"]. Godot's own contribution is the editor LSP and DAP, which are usable as agent interfaces (below).
- The most relevant one for a "game as harness" loop is **beremaran/godot-agent-loop** (npm `@beremaran/godot-agent-loop` 3.0.1, MIT, last commit 2026-10-05). It declares Godot 4.7 as its compatibility floor, needs no editor, and covers run, observe, screenshot, input, scenario and tests. I ran it against Godot 4.7 under xvfb and it worked [Run, below].
- Close second, and best for deterministic stepping: **satelliteoflove/godot-mcp** (MIT, 2026-09-16, Godot 4.5+). It has freeze, step N ms or frames, `step_until`, inputs inside the step window, a runtime state digest, and exec. It needs a running editor plus an addon.
- Third: **Erodenn/godot-mcp-runtime** (MIT, 2026-09-29). It has no addon, headless scene editing, a runtime bridge, screenshots, input, `run_script`, a profiler, and a documented security gate.
- Recommendation: **do not make an MCP server the core harness**. Build the planned CLI one-shot harness (C1-C9). For C10 (the optional live bridge), adopt `godot-agent-loop` as-is, with privileged groups left off. Borrow `satelliteoflove`'s freeze/step/digest design when specifying C6/C7. Skip the large editor-plugin servers (300+ tools) and the cloud-default one.
- Godot's built-in LSP (6005) and DAP (6006) start from a headless editor in 4.7 [Run]. They are a cheap agent interface for diagnostics and breakpoints.
- Several packages' 4.7 claims are unverified. Only beremaran (documented floor 4.7, my run) and KeeVeeG (README "tested with 4.7") say anything explicit about 4.7. The others are [Unverified] for 4.7.

## Capability matrix

Legend: Y = present in source, P = partial or gated, N = absent. "Editor" = needs a running Godot editor plus an installed addon. Source evidence is in the per-server sections.

| Server (clone dir) | Run game | Capture output | Scene read | Scene write via engine API | Screenshot | Input injection | Eval GDScript | Needs editor | Last commit | License |
|---|---|---|---|---|---|---|---|---|---|---|
| beremaran/godot-agent-loop | Y (spawns godot, any display incl. xvfb) | Y (`game_get_logs`, `game_get_errors`) | Y (`game_get_scene_tree`, `game_get_node_info`, `game_get_ui`) | P (`editor_transaction` via EditorUndoRedoManager, only with attached editor; otherwise agent edits files) | Y (game window; needs display) | Y (hidden tools: click, key, gamepad, touch, drag; plus `game_scenario`) | P (`game_eval`, denied by default, needs `code-execution` group) | No (optional addon for scene edits) | 2026-10-05 | MIT |
| satelliteoflove/godot-mcp | Y (`godot_editor_edit run`, optionally frozen) | Y (`get_log_messages`, `get_stack_trace`) | Y (`godot_node_read`, `godot_runtime_state digest`) | Y (`godot_node_edit`, `godot_scene`, animation, tilemap tools) | Y (`screenshot_game`, `screenshot_editor`) | Y (`godot_input`: actions with strength, keys, joypad, mouse-look) | Y (`godot_exec`, guarded by an "accident guard") | Yes (addon over WebSocket) | 2026-09-16 | MIT |
| Erodenn/godot-mcp-runtime | Y (`run_project`, background window mode, `attach_project`) | Y (`get_debug_output`) | Y (`get_scene_tree`, `get_node_properties`, `get_ui_elements`) | Y headless (`godot_operations.gd` via `--headless --script`, `batch_scene_operations`) | Y (`take_screenshot`) | Y (`simulate_input`) | Y (`run_script`, tiered static filter) | No (injects `McpBridge` autoload at run time) | 2026-09-29 | MIT |
| Coding-Solo/godot-mcp | Y (`run_project`, windowed, `-d`) | Y (`get_debug_output`) | P (`get_project_info`, no scene tree read) | Y headless (`create_scene`, `add_node`, `save_scene`, via `--headless --script godot_operations.gd`) | N (README calls screenshot experimental; no tool in source) | N | N | No | 2026-04-16 | MIT |
| ee0pdt/Godot-MCP | N (no run tool) | N | Y (`list_nodes`, `get_current_scene`, `get_node_properties`) | Y (`create_node`, `update_node_property`, `create_script`) | N | N | Y (`execute_editor_script`) | Yes (addon, WebSocket 9080) | 2025-03-19 | MIT |
| bradypp/godot-mcp | Y (Coding-Solo derivative) | Y | P | Y headless | N | N | N | No | 2025-05-31 | MIT |
| HaD0Yun/Gopeak-godot-mcp (npm `gopeak`) | Y | Y | Y | Y (headless plus optional bridge) | Y (runtime addon) | Y (`inject_action`, `inject_key`, `inject_mouse_*`) | P | Optional (bridge port 6505) | 2026-05-14 | MIT |
| KeeVeeG/godot-mcp | Y | Y | Y | Y (undo-aware, editor) | Y (editor and game) | Y | Y (`execute_game_script`) | Yes (WebSocket 6505-6514) | 2026-07-12 | MIT |
| tomyud1/godot-mcp | Y (`run_scene`) | Y (`get_runtime_log`) | Y | Y (undo/redo) | Y (`take_screenshot`) | Y (`send_input`) | N seen | Yes (plugin connects to ws://127.0.0.1:6505) | 2026-08-24 | MIT |
| IvanMurzak/Godot-MCP | P | Y (`runtime-errors-get`, opt-in) | Y | Y (EditorInterface) | Y (README) | not checked | not checked | Yes (C# addon, .NET build of Godot) | 2026-10-12 | Apache-2.0 |
| youichi-uda/godot-mcp-pro | Y | Y | Y | Y | Y | Y | Y | Yes (WebSocket 6505) | 2026-09-25 | MIT (public repo has only the addon; the Node server is in a paid package) |

Notes on the matrix: rows for Gopeak, KeeVeeG, tomyud1, Ivan and youichi are based on tool names, READMEs and a partial read of the source. I did not trace every tool. Treat the cells for these five as [Unverified] beyond what the per-server sections cite.

## Per-server findings

### beremaran/godot-agent-loop (strongest fit)
- Architecture: Node MCP server over stdio. It spawns Godot itself and injects a transient autoload (`McpInteractionServer`) that listens on `127.0.0.1:9090` (random free port logic exists in `runtime-port.ts`). The bridge is token-authenticated. [Run: stop_project output showed "McpInteractionServer: Listening on 127.0.0.1:9090 ... authentication_succeeded"]. For editor attach, an optional addon `addons/godot_agent_loop` publishes a per-start token and loopback port in `.godot/godot_agent_loop/editor-session.json` [Doc: README "Interactive editor setup"].
- Tools: 16 advertised (`godot_catalog`, `godot_call`, `run_project`, `stop_project`, `editor_session`, `editor_transaction`, `game_screenshot`, `game_get_scene_tree`, `game_get_ui`, `game_get_node_info`, `game_get_errors`, `game_get_logs`, `game_scenario`, `game_wait_until`, `run_project_tests`, `verify_project`) and 40 hidden behind `godot_catalog`/`godot_call` (input primitives, performance, visual regression, node generics, export, .NET) [Src: beremaran/godot-agent-loop@967ef6d:docs/tools.md]. [Run: `tools/list` returned exactly the 16 names].
- Philosophy matches our plan: the authors removed file, scene-authoring and settings tools because "coding agents author .gd/.tscn/.tres with their own file tools" [Doc: docs/tools.md]. It runs GUT, gdUnit4 and native tests (`run_project_tests`).
- Dynamic test [Run: Godot 4.7.stable under `xvfb-run`, tiny project with gl_compatibility, llvmpipe]:
  - First `run_project` was refused: "Project path is outside the allowed roots (GODOT_MCP_ALLOWED_DIRS)". Setting that env var to the work dir fixed it. So there is a path allow-list.
  - `run_project` returned `runtime_connected: true, authenticated: true, observed_scene: res://main.tscn`.
  - `game_get_scene_tree` returned the real tree (node_count 9, including the injected McpInteractionServer nodes).
  - `game_screenshot` returned a PNG (base64 PNG header decodes to roughly 1152x648).
  - `game_get_errors` returned 17 lines, all engine noise (V-Sync warning, ALSA card errors). Gotcha: the "errors" stream is dominated by environment warnings, so an agent harness would need a filter.
  - `godot_call game_eval` was denied by default ("Privileged runtime command 'eval' is disabled"). With `GODOT_MCP_PRIVILEGED_GROUPS=code-execution` it returned `{"result": 89, "success": true}` for `get_tree().current_scene.n` (a frame counter), proving live state read.
  - Whole session including startup and shutdown took about 6 s wall.
  - The project dir was left with only the original files plus `.godot` cache; the transient bridge was removed on stop.
  - Strict schema validation: wrong argument names (`tool` instead of `toolName`, missing `name` in `game_scenario`) are rejected with field-path messages, which is agent-friendly.
- Determinism: no fixed-step or seeded replay. Only `Engine.time_scale` exists as an internal command [Src: src/scripts/mcp_runtime/system_domain.gd:16]. It runs the game in real time with frame-based waits. So it is a good observer and player, not a deterministic simulator.
- Rendering: needs a display. "display-less sessions fail fast with desktop/Xvfb remediation" [Doc: README support table]. `--headless` is used only for CLI jobs [Src: src/headless-mode.ts].
- Security: privileged groups (`reflection`, `code-execution`) are off by default; child processes get a sanitized environment; project roots allow-list; the doc says plainly that running a project executes its GDScript with the user's OS permissions, so run only trusted code [Doc: docs/tools.md]. Per-session token on the TCP bridge.
- Maintenance: HEAD 2026-10-05; package.json version 3.0.1 (SECURITY.md says "1.x" supported, a doc inconsistency). Single-maintainer project with heavy eval/CI scaffolding (evals/, baselines). Clone is shallow, so I cannot judge commit frequency [Unverified].
- Godot 4.7: documented floor and primary target, CI on 4.7 [Doc: README "Godot compatibility policy"]. Works in my run.

### satelliteoflove/godot-mcp (best deterministic stepping)
- Architecture: Node MCP server (stdio) to a WebSocket in an editor addon (`godot/addons/godot_mcp`, TCPServer + WebSocketPeer, bind mode defaults to localhost). A `game_bridge` autoload runs inside the game [Src: satelliteoflove/godot-mcp@c732865:godot/addons/godot_mcp/game_bridge/mcp_game_bridge.gd].
- Tools (20 action-multiplexed): `godot_editor_read` (get_state, get_log_messages, get_stack_trace, screenshot_game, screenshot_editor), `godot_editor_edit` (run, stop, restart, select, rescan), `godot_game_time` (freeze, step by duration_ms or frames, step_until expression, thaw, status), `godot_input` (get_map, sequence, type_text), `godot_runtime_state` (digest, watch_start/collect/stop), `godot_exec`, `godot_node_read/edit`, `godot_scene`, `godot_scene3d`, animation, tilemap, gridmap, resource, profiler, project, docs, `godot_validate_meshes` [Src: server/src/tools/*.ts].
- Relevant to our C6/C7: freeze the clock at frame 0, step exact slices, inputs ride inside the step window so `is_action_just_pressed` edges are not missed, `step_until` a GDScript condition, structured state digest instead of pixels [Doc: README "Why this one?"; Src: tools/game-time.ts:35-96]. This is the closest published design to "deterministic, addressable state".
- Needs the editor GUI session (the addon runs in the editor and launches the game). Headless operation is [Unverified]; the README only mentions headless Claude Code driving it for evals.
- Security: `godot_exec` runs GDScript with a guard that the source itself calls "an ACCIDENT GUARD, not a security boundary" [Src: game_bridge/mcp_exec_guard.gd:9].
- Godot: 4.5+ (needs the Logger class) [Doc: INSTALL.md]. 4.7 not stated. [Unverified for 4.7].
- Not run by me (needs an editor session).

### Erodenn/godot-mcp-runtime
- Architecture: Node stdio server. Scene ops use `godot --headless --path P --script godot_operations.gd` (derived from Coding-Solo [Doc: README Acknowledgments]). For runtime, it adds an `McpBridge` autoload to `project.godot` (reserved name; collisions are detected) with a TCP listener on `127.0.0.1` and a per-session token [Src: Erodenn/godot-mcp-runtime@0492500:src/scripts/mcp_bridge.gd:128; docs/security.md]. Cleanup on shutdown.
- 40+ tools (names from source): scene and node editing (`add_node`, `set_node_properties`, `batch_scene_operations`, `connect_signal`, ...), autoload management, `validate`, `run_project`, `attach_project` (bridge for a game started externally, e.g. by CI), `take_screenshot`, `simulate_input`, `get_ui_elements`, `run_script`, `profile_project`/`start_profiler`/`stop_profiler`.
- "Background mode" moves the window off-screen; it still needs a display (the CI workflow installs xvfb [Src: .github/workflows/ci.yml:107-119]).
- Security gate for `run_script` / `run_project`: three tiers (hard-block `OS.execute` etc., elicitation, warnings) and env switches `GODOT_MCP_STRICT`, `GODOT_MCP_DISABLE_SECURITY`; the doc says the scan is a best-effort filter, not a sandbox [Doc: docs/security.md]. Good transparency.
- Modifies `project.godot` at run time (autoload entry); a crash could leave it behind [Unverified; code has stale-owner handling].
- Godot: "Godot 4.x"; README examples use 4.4. [Unverified for 4.7].

### Coding-Solo/godot-mcp (the best-known one; limited)
- Node stdio server. 14 tools: `launch_editor`, `run_project`, `get_debug_output`, `stop_project`, `get_godot_version`, `list_projects`, `get_project_info`, `create_scene`, `add_node`, `load_sprite`, `export_mesh_library`, `save_scene`, `get_uid`, `update_project_uids` [Src: Coding-Solo/godot-mcp@1209744:src/index.ts:671-913].
- Scene editing is done by one big GDScript (`src/scripts/godot_operations.gd`, ~1100 lines) invoked with `--headless --path P --script ... <operation> <json>` using `execFile` with an argument array (no shell) [Src: src/index.ts:509-528]. So it uses the engine API, with no editor required.
- `run_project` is `godot -d --path P [scene]`, windowed, stdout/stderr captured. No screenshot, no input, no eval, no scene read. About 2,300 lines of TypeScript total, small enough to audit.
- Security: low. No eval. The only risk is that it runs the project's own scripts.
- Last commit 2026-04-16; npm 0.1.1 published 2026-02-03. Many forks exist (`godot-mcp-flash`, `@grinry/godot-mcp`, `bradypp`), which signals popularity more than a maintained core.
- Godot: the UID tools target 4.4+. [Unverified for 4.7].
- Value for us: the `godot_operations.gd` pattern is exactly our planned C4w "build scene via engine" runner. Copy the idea, not the server.

### ee0pdt/Godot-MCP (old)
- Editor addon with a WebSocket server on port 9080 plus a FastMCP Node server (`server/src/tools/*`): `create_node`, `delete_node`, `update_node_property`, `get_node_properties`, `list_nodes`, `create_scene`, `save_scene`, `open_scene`, `get_current_scene`, `create_resource`, `create_script`, `edit_script`, `get_script`, `create_script_template`, `execute_editor_script` [Src: ee0pdt/Godot-MCP@b7d08eb].
- `execute_editor_script` compiles arbitrary GDScript in the editor with no gate [Src: addons/godot_mcp/commands/editor_script_commands.gd:12-76].
- No run, no screenshot, no input. Last commit 2025-03-19, so effectively abandoned and pre-4.4 (uses older APIs; `.uid` files are present, so it was touched at 4.4). Not recommended.

### bradypp/godot-mcp
- A Coding-Solo derivative, last commit 2025-05-31, `src/core/GodotExecutor.ts`, `ProcessManager.ts`. Nothing to add over Coding-Solo. [Unverified: tool list not read in detail].

### HaD0Yun/Gopeak-godot-mcp (npm `gopeak`)
- Node server with a dynamic tool-group system (README: compact vs full profiles, paged `tools/list`; 123 distinct tool names in `src/`). It includes LSP and DAP clients (`src/lsp_client.ts`, `src/dap_client.ts`): `lsp_get_diagnostics`, `lsp_get_hover`, `lsp_get_symbols`, `lsp_get_completions`, `dap_set_breakpoint`, `dap_continue`, `dap_step_over`, `dap_get_stack_trace`, `dap_get_output`, plus `inject_action/key/mouse_*` and `run_project`. It uses a bridge on port 6505 (`DEFAULT_PORT` in `godot-bridge.ts`), and has a web "visualizer" server.
- README itself marks many groups "audit-required" (not fixture-tested). Last commit 2026-05-14.
- The LSP/DAP-as-tools idea is worth borrowing; in our setup the agent can call the LSP directly (see below) without this server.

### KeeVeeG/godot-mcp
- Node server to editor plugin over WebSocket with port scanning 6505-6514; claims 300+ tools in 40+ modules, including `execute_game_script` (`runtime/execute_script`), input recording, screenshots, assertions [Doc: README; Src: server/src/tools/runtime.ts:48-57]. README says the code was written with the help of several AI models (listed) and that it is "tested with 4.7".
- Same default port and architecture as the paid "Godot MCP Pro" (6505). I did not compare code, so any derivation is [Unverified].
- A 300-tool surface is bad for agent context unless filtered. Last commit 2026-07-12.

### tomyud1/godot-mcp
- 75 tools, editor plugin that connects to `ws://127.0.0.1:6505` (`mcp_client.gd:13`), with an interactive project visualizer, undo/redo, `run_scene`, `take_screenshot`, `send_input`, `get_runtime_log`, `query_runtime_node`, `batch_execute`. Installed via the AssetLib. Last commit 2026-08-24. Requires the editor.

### IvanMurzak/Godot-MCP
- C# editor addon (needs the Godot .NET build; `dotnet` is not available here, so I could not run it). 42 tools in 12 families (README). Default connection goes to the hosted `ai-game.dev` backend with OAuth device login; self-hosting is possible [Doc: README]. Runtime error capture is opt-in. Apache-2.0, last commit 2026-10-12, Godot 4.3+.
- Trust concern: a default cloud relay for editor operations. Not suitable for a reproducible, offline harness.

### youichi-uda/godot-mcp-pro
- The public repo has only the free addon. The Node.js server ships in a paid zip [Doc: README]. Closed, so not auditable or reproducible. Skip.

### Not examined
- GDAI MCP (closed, commercial, name from the plan list; not found in the npm search or cloned) [Unverified].
- Other npm packages found but not cloned or read: `@npgamedev/godot-mcp-server` (also on the Asset Library as "Godot MCP Toolkit"), `godot-mcp-bridge`, `@gikit/godot-mcp`, `godot-mcp-enhanced`, `@n24q02m/better-godot-mcp`, `@yanhuifair/godot-mcp` (claims 386 tools), `@tugcantopaloglu/godot-mcp` (165 tools), `@letsagents/godot-mcp`, `godot-safe-change-mcp`, `breakpoint-mcp`, `@srdarkx/godot-mcp`. Several were published within the last week (2026-10-13 and -14), which suggests a crowded, fast-churning field. I did not evaluate any of them, and quality or safety is [Unverified].

## Godot's own LSP and DAP as agent interfaces
- Flags exist in 4.7: `--lsp-port <port>` and `--dap-port <port>`, both marked editor-only [Run: `godot --help | grep -i "lsp\|dap"`].
- [Run: `godot --headless --editor --path proj --lsp-port 6005 --dap-port 6006`, then a TCP connect from Python after 12 s]: ports 6005 and 6006 both accepted connections. So a headless editor serves GDScript LSP and DAP in 4.7. This is a plain Godot feature with no addon.
- Use: LSP gives parse diagnostics, hover, symbols and completion (useful for C2/C3 beyond a regex lint); DAP gives breakpoints and stack traces. The cost is a long-lived editor process, and the first run imports the project and writes `.godot/`. I did not exercise LSP request/response content (did not send `initialize`), so diagnostics quality is [Unverified].
- Caveat from my run: the headless editor also created `main.gd.uid` in the project, because 4.4+ writes `.uid` files for scripts on scan. Harness runs that must keep the tree clean need to account for this.

## Recommendation, tied to harness components (plan section 4)

| Component | Recommendation |
|---|---|
| C1 API ground truth | Not served by any MCP server (satelliteoflove has a `godot_docs` tool, not verified). Build ours from `--dump-extension-api` and `--doctool` (R1.1). |
| C2 load-check | Build own (`--headless --script`). Optionally use the LSP diagnostics from a headless editor as an add-on. Coding-Solo's `validate`-style approach and beremaran's `scripts/validate_script.gd` are examples. |
| C3 Godot-3 lint | Build own. No server does this. |
| C4/C4w scene digest and generator | Build own, borrowing Coding-Solo's pattern (a single GDScript run with `--headless --script <op> <json>`, engine-API writes). Do not use ee0pdt or the editor-addon servers. |
| C5 tests | Standardise per R1.3. beremaran's `run_project_tests` already wraps GUT, gdUnit4 and native, which confirms the runner commands are scriptable; no need for MCP. |
| C6 scenario/replay, C7 feel traces | Build own for determinism (seed + fixed fps + command stream). Borrow satelliteoflove's freeze/step/step_until and "inputs inside the step window" semantics, because naive injection misses `just_pressed` edges. No existing server provides seeded, fixed-step headless replay. |
| C8 visual check | Own pipeline is fine (xvfb + screenshot). For an interactive check, `game_screenshot` in beremaran works in xvfb. |
| C9 perf | Own. beremaran (`game_performance`) and Erodenn (profiler) show the same Performance-monitor idea. |
| C10 live bridge | **Adopt beremaran/godot-agent-loop** as the optional interactive layer: no editor needed, transient autoload (no repo footprint), 16-tool surface (small context cost), token-authenticated loopback, privileged tools off by default, Godot 4.7 floor, verified working here. Run it with `GODOT_MCP_ALLOWED_DIRS` set. Keep `code-execution` and `reflection` off for unattended runs. |

Why not adopt more: a live MCP loop is not reproducible (real time, window needed for screenshots, noisy "errors"), and none of the servers offer seeded fixed-step execution, which is the core of the plan's article-derived design. They are good for exploration and for the interactive "see what it looks like" step, which is what C10 is for.

Trust summary for any of these: all of them execute project GDScript with the user's permissions. Treat the project as trusted code, run the agent in a container or VM, pin the npm version, and do not run unpinned `npx -y`. Those with `eval` (`beremaran`, `satelliteoflove`, `Erodenn`, `KeeVeeG`, `ee0pdt`) are remote-code-execution channels by design; only `beremaran` (default-deny groups) and `Erodenn` (tiered filter, self-described as best-effort) gate it at all. I did not audit npm dependency trees.

## Blocked sources
- github.com web pages and api.github.com were not used (known blocked); all repo data came from `git clone`. Star counts, issues and commit frequency are therefore not available (clones are shallow, so only the HEAD date is known).
- No other hosts were blocked. `registry.npmjs.org` and `godotengine.org/asset-library/api` worked. WebSearch worked.
- npm package install was done only for `@beremaran/godot-agent-loop@3.0.1` with `--ignore-scripts`, in `research/r1_2_work/bere`. No other server was installed or run.

## Open questions
- Does `godot-agent-loop`'s `game_scenario` plus `Engine.time_scale` give enough determinism, or must we layer our own `Harness` autoload? (I only confirmed real-time operation.)
- Can satelliteoflove run against a headless or xvfb editor, which would make its freeze/step API usable in CI? Not tested.
- LSP diagnostics content from the 4.7 headless editor (do parse errors arrive as `publishDiagnostics` without opening a document?). Not tested.
- Exact 4.7 compatibility for Erodenn, Coding-Solo, Gopeak, tomyud1: not tested.
- Dynamic test artifacts: `research/r1_2_work/mcp_client.py`, `mcp_client2.py` (stdio MCP client), `proj/` (tiny project), `bere/` (sandboxed npm install).
