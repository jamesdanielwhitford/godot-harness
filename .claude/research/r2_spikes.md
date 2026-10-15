# R2 spikes S1-S6 (Phase 0)

Env: Godot 4.7.stable.official.5b4e0cb0f, Linux, run by a Sonnet 5.5 spike agent. Work dir: `$SCRATCH/sp/` (scratchpad). All [Run] unless marked [U].

## S1. `-s` on a script outside the project; `preload("res://...")`
Verdict: YES, works. The outside script runs with `res://` pointing at `--path` (or cwd if it holds `project.godot`).
- [Run] `godot --headless --path proj -s /abs/outside/ok.gd` (script does `preload("res://lib.gd")`, `load("res://lib.gd")`, `quit(7)`) printed `PRELOAD 42 hi from res`, `LOAD 42`, rc=7. A relative `-s ../outside/x.gd` also worked.
- [Run] Same without `--path`, cwd=proj: works. cwd=outside dir with no project.godot: `ERROR: Failed loading resource: res://lib.gd` then `SCRIPT ERROR: Invalid access ... 'null instance'`, and the process HUNG until `timeout` (rc=124) because `quit()` was never reached.
- Caveat: a runtime error in `_init` leaves the SceneTree running, so always wrap in `timeout` and pass `--path`.
Decision: runners may live outside the project if the harness always passes `--path <project>`. Keep the default (synced into `addons/harness/`) for simplicity and for `class_name` resolution [U, not tested]. No fallback needed.

## S2. Parse-error exit codes (reconciles r1_1 rc=1 vs r1_5 rc=0)
Verdict: both are right; the exit code depends on HOW the broken script is reached.
| Case | Command | rc | Log signal |
|---|---|---|---|
| `-s` on the broken script itself | `--headless --path proj -s res://bad.gd` | 1 | `SCRIPT ERROR: Parse Error: ...` + `Failed to load script "res://bad.gd" with error "Parse error"` |
| same, type error | `-s res://bad_run.gd` | 1 | same (script never runs) |
| `--check-only -s broken` | `--check-only -s res://bad.gd` / `bad2.gd` | 1 | same |
| `--check-only -s` valid | `--check-only -s res://quitrun.gd` | 0 | nothing printed, script not run |
| runner `load("res://bad.gd")` then `.new()` | `-s res://r_load.gd` | 124 (hang) | Parse Error + Failed to load; `load` returns a GDScript with `can_instantiate()==false`, `.new()` -> `SCRIPT ERROR: Invalid call. Nonexistent function 'new'`; `quit` never reached |
| runner `load(bad2).new()` | `-s res://r_load2.gd` | 124 | `load` returns non-null; `.new()` errors the same way |
| runner loads a scene whose script is broken | `-s res://r_scene.gd` (`quit(0)` at end) | 0 | Parse Error + Failed to load script; `load` of the scene SUCCEEDS and `instantiate()` returns a Node (script silently dropped) |
| main scene with broken script | `res://badscene.tscn --quit-after 2` and `--main-scene` | 0 | Parse Error + Failed to load script |
So: rc=1 only when the engine itself fails to load the `-s` script. Scene loads and runner `load()` give rc=0 (or a hang if the runner errors before `quit`). r1_5 saw rc=0 because its runner loaded the script via scene/`load` and then called `quit(0)`.
Also: `--check-only` without a script does not check the project; it only suppresses running.
Decision (matches the fallback): the log scan (`SCRIPT ERROR`, `Parse Error`, `Failed to load script`) is authoritative for `h check`; rc!=0 and rc=124 are extra failure signals, rc=0 proves nothing. A runner must also test `load(path)` result with `can_instantiate()` and call `quit(1)` itself on failure.

## S3. Agent/model selection and nested `claude -p`
(a) Per-spawn model selection. Verdict: NOT TESTABLE from this subagent; PARTIAL evidence.
- This spike agent's tool list has no `Agent` tool (only Bash/Read/Write/Edit/Glob/Grep/Skill/Artifact/ToolSearch/mcp). The parent session's `get_session` shows `Agent` in its tool list, and the lineage `depth 0, limit 8`, so subagent spawning exists in the main session. I could not try `subagent_type: builder` here. [U]
- [Run] `get_session` for this session: `configured_model` and `last_served_model` = `claude-sonnet-5-5`.
- `.claude/agents/{builder,planner,test-writer,verifier}.md` exist with frontmatter `name`, `model` (`sonnet`, `opus`, `sonnet`, `sonnet`), `tools`. [Run] The files parse.
- [Run] The CLI honours the definitions: from the repo dir, `claude -p "say ok" --agent planner --output-format json` -> `modelUsage` keys `['claude-opus-5-5']`; `--model opus` -> `claude-opus-5-5`; `--model sonnet` -> `claude-sonnet-5-5`. So the `model:` field in `.claude/agents/*.md` applies when the agent is selected through the CLI. [U] whether the in-session Agent tool lists them as `subagent_type` values and applies `tools:`; the orchestrator should test one tiny spawn.
(b) Nested `claude -p`. Verdict: WORKS and is authenticated.
- [Run] `timeout 60 /opt/node22/bin/claude -p "say ok"` -> output `ok`, rc=0, ~2 s. Also worked from `/tmp` and with `--model opus`. Auth is inherited from the session environment (ANTHROPIC_BASE_URL and CLAUDE_CODE_* vars present); I did not touch credentials. Note it reuses the same session id env (`77c17b82-...`) in its JSON output; it appeared in `claude agents --json` listings as other processes of the same session.
- Because I (a subagent) ran it, nested `claude -p` works inside a subagent.
Decision: put the model in each agent definition file (already done). Round P can use real `claude -p --agent <role> --model ...` runs; no "simulated baseline" needed. Dogfood can be done by a subagent. Cost/rate: each call is billed to the same account (session `rate_limit_info` showed `allowed_warning` at seven_day); keep trials bounded.

## S4. gdUnit4 single-test selection (v6.2.2)
Verdict: no "run only this test" flag exists, but a single test can be selected by excluding the rest; a single suite is selected by `-a <file>`.
- Source (`addons/gdUnit4/src/core/runners/GdUnitTestCIRunner.gd`): `-a` appends to `_included_tests` (passed to `scanner.scan(path)`: a dir or suite file); `-i` appends to `_excluded_tests`; `is_skipped()` matches `suite_name` or `source_file.contains(x)`, and for `x` containing `:` matches `suite:test_name`. Usage text says `-i <path of testsuite|testsuite_name|testsuite_name:test_name>`. `-conf` loads a runner config (JSON of GdUnitTestCase) as an alternative [U not run].
- [Run] `-a res://tests/test_many.gd` (50 tests) -> all pass. `-a res://tests/test_many.gd:test_t3` -> `Given directory or file does not exists: res://tests/test_many.gd:test_t3`, `Exit code: 0` (!). A bad path exits 0 with nothing run; harness must check the "Statistics: N test cases" line.
- [Run] `-a res://tests/test_many.gd -i res://tests/test_many.gd:test_t3` -> `Statistics: 49 test cases`, t3 absent.
- [Run] Run exactly one test: `-a res://tests/test_many.gd` plus `-i test_many:test_tK` for every other K -> `Statistics: 1 test cases ... PASSED`, only `test_t7` executed. 
- Invocation used: `godot --headless --path . -s -d res://addons/gdUnit4/bin/GdUnitCmdTool.gd --ignoreHeadlessMode -c -a ...` (from r1_3).
Decision: `h test <suite>` = `-a` file. `h test <suite>::<name>` = the harness lists the suite's `func test_*` names (grep) and passes `-i suite:other` for each other test (50 args worked). Always assert the Statistics count >= 1; a 0-test run is a failure. Fallback (suite level) is also available.

## S5. LSP diagnostics for unopened files; warm latency
Verdict: diagnostics are NOT pushed for unopened files, but `didOpen` with the file text returns them in single-digit ms from a warm daemon. Opt-in design stands, but latency is no obstacle.
- [Run] Daemon: `godot --headless --editor --path proj5 --lsp-port 54033` (random free port, after a prior `--editor --import`). TCP port accepted connections after about 5 s (10 polls of 0.5 s). `initialize` answered in 0.20 s.
- [Run] After `initialize`/`initialized`, 6 s idle with nothing opened: the only message was `gdscript/capabilities`; zero `publishDiagnostics` even though `bad.gd` has a parse error on disk (the daemon log shows it printing the parse error while loading the workspace, but not sending it to the client).
- [Run] `textDocument/didOpen` (text read from disk) for 5 files, then `didChange` twice more: every file got `publishDiagnostics` in 0.003-0.010 s, e.g. `bad.gd` -> `(line 4, severity 1) Expected expression after "+" operator.`; `bad2.gd` -> 2 errors `Cannot assign a value of type "String" as "int"`; `warn.gd` -> `(UNUSED_VARIABLE)` severity 2; `good.gd`/`lib.gd` -> `[]`. Cold vs warm made no visible difference.
- Daemon startup is the cost (~5 s plus import); a one-shot LSP check per command would pay it, so a hook design needs a persistent daemon.
- Script: `$SCRATCH/sp/scripts/lsp5.py` [not copied into the repo; the main session may copy it into `.claude/research/scripts/r2_spikes/`].
Decision: keep LSP as opt-in `h check --lsp` backed by a lazily started daemon, client sends `didOpen` for each changed file from disk. The `--check-only -s` loop (S2) stays the default, since it needs no daemon.

## S6. Push to non-default branch names
Verdict: CREATE works, DELETE is blocked (HTTP 403).
- [Run] `git push origin HEAD:refs/heads/spike-test` -> `* [new branch] HEAD -> spike-test`, rc=0. `git ls-remote --heads origin` lists it.
- [Run] `git push origin --delete spike-test` -> `error: RPC failed; HTTP 403 curl 22 The requested URL returned error: 403`, `fatal: the remote end hung up unexpectedly`. Branch still exists.
- [Run] Slash names also work: `git push origin HEAD:refs/heads/build/x-spike` created `build/x-spike`; its delete also failed with 403.
- Leftover remote branches (both at b7a1059, same commit as main, harmless): `spike-test`, `build/x-spike`. The user must delete them on GitHub (the proxy blocks ref deletion from here).
Decision: the `build/<area>` branch scheme is usable for creating branches; but branches cannot be cleaned up by agents, so each one is permanent. Prefer the single working branch plus pathguard (fallback), or accept leftover branches. Merging a branch would also need a PR/UI path that is blocked (github.com web and api are blocked per CLAUDE.md), so use feature branches only if the orchestrator can merge locally and push `main`.
