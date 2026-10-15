# Build and test plan: Godot 4.7 agent harness v0

Status: plan written 2026-10-15 (Opus). No harness code exists yet. This file is the orchestration plan for a **main session** (Claude Code with the Agent tool) that runs the build with subagents.

Inputs: `CLAUDE.md`, `godot_harness_plan.md` (C1–C10, F1–F15), `godot_harness_plan_addendum_patterns.md` (Round P, P01–P24, D1–D10), `.claude/research/r1_*.md`.

Tags: **[U]** unverified or a judgement call; **[DEFAULT]** a proposed answer to an open user decision, which work proceeds on until the user overrides it; **[Run]** verified in Round 1.

---

## 0. Status board (update at the end of every session)

| Phase | Item | Status | Commit / date | Notes |
|---|---|---|---|---|
| 0 | Dev roles (`.claude/agents/*.md`), handoff dirs, pathguard, test-lock scripts | done | 048ad74, b7a1059 / 2026-10-15 | custom agent types do NOT resolve in the Agent tool here (S3); spawn `general-purpose` with `model:` and paste the role text |
| 0 | `tools/bootstrap.sh` + `h doctor` stub | done | 771a0ca / 2026-10-15 | fresh-clone G0 check passed (ci PASS, rest SKIPPED). Known gap: --doctool XML not cached |
| 0 | Spikes S1–S6 | done | d2ce008 / 2026-10-15 | see research/r2_spikes.md. Nested `claude -p` works; S6: branches can be pushed but not deleted, so stay on `main` |
| 0 | User decisions D1–D5 confirmed or defaults accepted | defaults | 2026-10-15 | user said work autonomously; defaults in force |
| 0 | RP.1 baseline study, RP.2 reference census | todo | | Round P wave P0 |
| 1a | P0 contract spec `specs/00_contract.md` | todo | | |
| 1b | Planner specs A1–A9 | todo | | |
| 1c | Spec consistency review `specs/REVIEW.md` | todo | | Gate G1 |
| 2 | Core tests written + locked (A1–A4) | todo | | |
| 3 | Core built (A1, then A2/A3/A4) | todo | | |
| 4 | Core verified from fresh clone, tag `v0-core` | todo | | Gate G2 |
| 5 | A5 scenario, A9 sim/view + sample, A6 visual, A7 feel | todo | | Gate G3 |
| 6 | A8 Claude Code wiring + dogfood | todo | | Gate G4 = harness v0 |
| 7 | Round P topic agents, RP.Z1, A10 pattern pack | todo | | v0.1 |
| 8 | Evaluation (R3.2 + RP.Z2 pilot) | todo | | |

Area status lives in `.claude/handoff/<area>/status.md` (see §5.4). Only the orchestrator edits this table.

---

## 1. Principles (what this plan optimises for)

1. **Specs before tests before code.** Opus planners write a spec with numbered acceptance criteria (AC) and a list of seeded faults. Sonnet test-writers turn the spec into tests *before any implementation exists*. Sonnet builders make those tests pass. A separate Sonnet verifier runs everything from a fresh clone. No agent grades its own work.
2. **Black-box contracts.** Almost all harness tests call `tools/harness/h <verb>` on a fixture project and check the exit code plus the output lines. This lets tests be written from the spec alone and keeps them independent of the code's shape.
3. **The harness must prove that it catches faults.** Every area adds seeded faults to `selftest/faults/`. `h selftest` applies each fault to a clean copy of a project and expects the named verb to flag it. The detection matrix is the main quality number.
4. **Round 1 facts are rules for the build** (§3.3). Exit codes are never the only signal. `--import` runs first. Load-checks capture logs. Scenes are generated, not hand-written. Tests use gdUnit4 with `-c`. Screenshots use Xvfb + gl_compatibility. Simulation uses fixed ticks and a seeded RNG.
5. **The repo is the only memory.** The container is ephemeral. Every agent writes its results to files in the repo. The orchestrator commits after every agent returns and pushes at every gate. A container reset should lose at most one agent's work.
6. **Round 2 is folded into the planners.** Instead of separate R2.x prototype rounds, each Opus planner may run time-boxed spikes in the scratchpad and record the results in its spec. R2.5 (perf) is deferred. R3.1 (deliverable) is replaced by this build, and R3.2 (eval) moves to Phase 8.

---

## 2. Decisions: blocking items, defaults, unverified items

### 2.1 User decisions (work proceeds on the defaults unless the user overrides them at Gate G0)

| ID | Decision | **[DEFAULT]** | Why | What changes if overridden |
|---|---|---|---|---|
| D1 | GDScript, C#, or both | **GDScript only for v0.** Design the sim template so it can later be a C# engine-free library tested with plain xunit (R1.3). `bootstrap.sh --with-dotnet` exists but is off. | gdUnit4 is solid on 4.7 [Run]. gdUnit4Net only exists as rc builds (R1.3). C# doubles test and build work. | A4 adds a `dotnet test` path; A9 adds a C# template. About +30% work in Phase 5. |
| D2 | Target genres | **2D action-platformer (real-time, physics) + 2D turn-based grid (sim-heavy).** The sample game has one scene of each. 3D is deferred to v0.1. | Covers both determinism regimes (R1.8) and the feel tracks (P01, P06), plus the sim/view split (R1.6). | Pick different sample scenes in A9. RP.B (3D) moves up if 3D is chosen. |
| D3 | Adopt an external MCP server | **No adoption in v0.** Ship a documented, disabled `.mcp.json` snippet for `@beremaran/godot-agent-loop@3.0.1` with `GODOT_MCP_ALLOWED_DIRS` set and privileged groups off (R1.2). | The core harness is one-shot CLI runs. MCP is not reproducible and runs project code. | A8 enables it and adds a skill section. No other area is affected. |
| D4 | Agent never judges feel or visuals itself | **Accepted.** Feel targets (`.tres`) and screenshot baselines carry `approved_by`. Agents can propose them but cannot approve them (enforced by a hook in A8). | It is the core idea of the plan. | — |
| D5 | Project scale tier | **"small"** (1–3 devs, under ~50 scenes, 3–6 autoloads). The template must not block growth. Round P (RP.F) writes the R-SCALE rule later. | Most likely first use. Larger tiers mainly add conventions, not tools. | The template's autoload set and folder layout (A9). |

### 2.2 Build decisions made by this plan (not blocking; recorded here)

| ID | Decision |
|---|---|
| B1 | `h` is a bash shim that runs `python3 -I -m harness` (stdlib only at runtime). The in-engine side is GDScript in `addons/harness/`. Python dev tools (pytest, gdtoolkit 4.5.0) live in `.venv/`, created by the bootstrap. |
| B2 | Verbs are auto-discovered from `tools/harness/harness/verbs/<verb>.py`, so parallel builders never edit a shared registry file. |
| B3 | Godot runs never touch the repo's own projects during tests. Tests copy a fixture to `$HARNESS_TMP/<test-id>/` first. This also makes parallel runs safe. |
| B4 | gdUnit4 is pinned to tag `v6.2.2` and fetched by the bootstrap, not vendored. odiff-bin is pinned to 4.5.0 via npm into `~/.cache/godot-harness/`. |
| B5 | Commit `.uid` files. `.godot/` stays ignored. |
| B6 | Screenshot baselines use the gl_compatibility renderer on Xvfb with llvmpipe. Each baseline records the Mesa version. GL and Vulkan baselines are never mixed (R1.7). |
| B7 | Replays assert an exact state hash first, then fall back to a tolerance check. "Hash differs but tolerance passes" is a WARN, not a pass (R1.8). |
| B8 | The working branch is whatever `git branch --show-current` says at session start (currently `main`). Feature branches are optional (§5.3). |

### 2.3 Spikes to run in Phase 0 (each ≤ 30 min, Sonnet, results go to `.claude/research/r2_spikes.md`)

| ID | Question | Blocks | Fallback if negative |
|---|---|---|---|
| S1 | Does `godot -s /abs/path/outside/project.gd` work, and can it `preload` `res://` files? | Where GDScript runners live (A1) | Runners are synced into `<project>/addons/harness/` (the default design anyway). |
| S2 | Parse-error exit codes: R1.1 saw rc=1 for `-s --check-only`, R1.5 saw rc=0 in its runner. Reproduce both cases. | A1 `check` semantics | Treat the log scan as authoritative; use the exit code only as an extra failure signal. |
| S3 | Can the Agent tool in this environment pick the model (opus/sonnet) per spawn, and do `.claude/agents/*.md` `model:`/`tools:` fields apply? Does a nested `claude -p` work inside a subagent? | Roles (§5), Round P trials, Phase 6 dogfood | Put the model in the agent definition files. If nested `claude -p` fails, Round P uses "simulated baseline" (addendum) and the dogfood step is done by the orchestrator. |
| S4 | gdUnit4 single-test selection on the CLI (R1.3 open question) | A4 `h test <filter>` | Filter at suite level only. |
| S5 | LSP: do `publishDiagnostics` arrive for a file that was not opened, and how long does a warm daemon take per file? | A3 LSP hook design | LSP stays an opt-in `h check --lsp`. |
| S6 | Does push work to non-default branch names here (`git push origin build/x`)? | §5.3 branch scheme | Single working branch plus pathguard only. |

### 2.4 Still unverified, carried into the specs as [U]
- Cross-machine determinism (R1.8): only same-binary, same-machine runs were tested. Golden hashes are valid per machine class.
- GPUParticles, TIME shaders, AnimationPlayer and MSAA screenshot repeatability (R1.7).
- Whether a parse error in a script loaded by the running main scene changes the exit code (R1.1).
- gdUnit4 upstream repo move (`godot-gdunit-labs/gdUnit4`). Pin by commit hash, not only by tag.
- Godot zip sha256: not recorded yet. Phase 0 records it in `tools/harness/pins.toml`.
- Whether Claude Code hook input identifies which subagent made a tool call. This decides whether role path limits can be enforced by a live hook or only by pathguard after the fact.

---

## 3. What gets built

### 3.1 Repo layout

```
tools/
  bootstrap.sh                 # idempotent env setup (§4)
  harness/
    h                          # bash shim -> python3 -I -m harness "$@"
    pins.toml                  # godot version+sha256, gdUnit4 tag+commit, odiff, gdtoolkit
    harness/                   # python package (stdlib only at runtime)
      __main__.py cli.py       # dispatcher, verb discovery
      godot.py                 # the ONE way to run godot: timeout, log file, error scan, rc merge
      logscan.py out.py        # error patterns; .harness/out/<run-id>/ + <=40-line summary
      verbs/                   # doctor import api check lint test digest scene_gen scene_edit
                               # run trace shot baseline sync selftest lsp (one file each)
    rules/lint_rules.json      # from research/scripts/r1_5_lint (curated + full, severity mapped)
  dev/                         # build-process tools (not shipped)
    ci.sh                      # local "CI": the full suite in order (§4.2)
    pathguard.sh               # fail if commits in a range touch paths outside a role's allowlist
    lock_tests.sh check_lock.sh  # sha256 lock over tests/ and selftest/
    verify_fresh_clone.sh      # clone pushed branch to scratch, bootstrap, run ci.sh
addons/harness/                # in-engine side, synced into projects by `h sync`
  harness.gd rng.gd command_bus.gd trace.gd capture.gd   # autoloads/helpers
  runners/ load_check.gd scene_gen.gd scene_edit.gd scene_digest.gd scenario.gd api_dump.gd smoke.gd
templates/
  claude/                      # what a GAME project gets: CLAUDE.md.tmpl, skills/, hooks/, agents/, settings.json
  sim_view/                    # GDScript sim/view template (A9)
  project/                     # minimal new-project template (project.godot with determinism settings)
sample/                        # the sample game (Godot 4.7), with platformer/ and tactics/ scenes, tests/
tests/
  unit/                        # pytest, pure python (log scan, summarisers, schema validation)
  contract/<area>/             # black-box: run `h <verb>` on fixtures, assert rc + output
  gd/                          # gdUnit4 suites for addons/harness (run inside a fixture project)
  e2e/                         # fresh-project end-to-end flows
  fixtures/projects/<name>/    # small Godot projects: clean_min, broken_scenes (r1_4 cases), godot3_scripts (r1_5 cases), ...
selftest/
  faults/<FAULT-ID>/fault.toml (+ files/ or patch)   # seeded faults
  (no committed expected matrix; see 00_contract)         # fault -> verb -> expected verdict (generated from fault.toml)
eval/                          # Phase 8 only: benchmark tasks and hidden tests (never installed into templates)
docs/ HARNESS.md ADOPTION.md verbs.md
.claude/
  plans/ build_and_test_plan.md, specs/NN_*.md
  handoff/<area>/ status.md, test_notes.md, build_notes.md, test_disputes.md, verify_<date>.md
  agents/ planner.md test-writer.md builder.md verifier.md   # dev roles for building THIS repo
.harness/                      # gitignored run outputs
```

`.gitignore` additions: `.harness/`, `.venv/`, `tools/bin/`, `sample/addons/gdUnit4/`, `sample/addons/harness/` (synced), `**/.godot/`, `reports/`.

### 3.2 The `h` verbs for v0 (owner area in brackets)

| Verb | Does | Area |
|---|---|---|
| `h doctor` | Checks godot binary + version, Xvfb, odiff, venv, addon sync, import state; ≤15 lines | A1 |
| `h sync [proj]` | Copies `addons/harness` (+ gdUnit4) into the project; enables autoloads per config | A1 |
| `h import` | `--import` with timeout, retry once on SIGABRT (R1.4), log scan | A1 |
| `h api <Class[.member]> / --search` | Lookup in the pinned `extension_api.json` + doctool `@GDScript.xml`; "did you mean"; existence check | A1 |
| `h check [paths] [--full] [--lsp]` | import-if-stale → `--check-only` per .gd → load+instantiate per .tscn/.tres with Logger capture → lint → optional 2-frame smoke run of scenes; merged verdict | A1 (+A3 lint, +A2 load-check runner) |
| `h lint [paths]` | Regex rules (Godot 3 idioms, `tscn-*`, determinism bans such as global `randf`), InputMap action existence, `emit_signal("x")` vs declared signals | A3 |
| `h digest <scene> [--all-props] / --project` | Tree, types, scripts, unique names, groups, connections, named layers, ext deps | A2 |
| `h scene-gen <spec.json>` / `h scene-edit <scene> <ops.json>` | Engine-written scenes (GEN_EDIT_STATE_MAIN round-trip), then automatic load-check + digest diff | A2 |
| `h test [suite|filter]` | gdUnit4 `--ignoreHeadlessMode -c`, maps 0/100/101/105, JUnit summary ≤15 lines | A4 |
| `h run <scenario.json>` | Seeded fixed-tick replay; state/metrics JSON; asserts; hash+tolerance | A5 |
| `h trace <scenario> [--nodes]` | Per-physics-tick CSV + metrics vs FeelTargets `.tres`; optional `--movie` clip for the human | A7 |
| `h shot <scenario|scene> [--crop] [--layers]` / `h baseline propose|approve` | Xvfb + gl_compatibility capture, odiff vs approved baseline; `approve` is human-only | A6 |
| `h lsp start|stop|diag <files>` | Headless editor LSP daemon (opt-in) | A3 |
| `h selftest [--area X]` | Runs the seeded-fault matrix | A1 (runner); faults from all areas |

Output contract for every verb (detailed in `00_contract.md`): at most 40 lines on stdout. The first line is `PASS|FAIL|WARN|ERROR <verb> <short reason>`. Then up to N unique findings as `path:line: [rule-id] message`, then `log: .harness/out/<run-id>/`. Exit codes: 0 pass, 1 findings (fail), 2 usage/config error, 3 harness internal error, 4 environment missing (e.g. no Xvfb), 5 warnings only (when `--strict` is off; still printed).

### 3.3 Round 1 findings → hard requirements for every spec

| Finding (source) | Requirement |
|---|---|
| Exit codes lie: runtime errors hang or exit 0; scenes with broken scripts "load" (R1.1, R1.5) | All Godot calls go through `godot.py`: `timeout` always; full log to file; scan for `SCRIPT ERROR`, `Parse Error`, `ERROR:`, `Failed to load`, `WARNING: Parent path`, `has vanished`; verdict = worst of (rc, scan, runner's own `quit(N)`). rc 124 → "hang" finding. |
| Fresh clone lacks class cache (R1.1, R1.3) | `h` auto-runs `h import` when `.godot/global_script_class_cache.cfg` is missing or older than any `class_name` script. |
| Broken scenes load silently (R1.4) | The load-check uses an `OS.add_logger` Logger subclass and instantiates scenes. Exit 3 = loaded with errors, treated as FAIL. `pack()`/`save()` returning OK is not trusted: compare digest node counts before and after. |
| Hand-editing .tscn is unsafe (R1.4 rules 1–20) | Only `scene-gen`/`scene-edit` write structure. The A8 hook warns on Edit/Write to `.tscn/.tres` structure lines (`[node`, `[ext_resource`, `[sub_resource`, `[connection`). |
| Godot 3 files and syntax load silently (R1.5) | `h lint` with 1,213 rules (low risk = error, medium/high = warning) is part of `h check` and of the PostToolUse hook. |
| gdUnit4: `--ignoreHeadlessMode`, `-c`, exit 101 = orphans warning (R1.3) | `h test` passes both flags and maps 101 → WARN. GUT is not supported. |
| Screenshots: Xvfb + gl_compatibility, never `--headless` (R1.7) | `h shot` refuses `--headless`, uses `xvfb-run -a`, `--audio-driver Dummy`, `--fixed-fps`, and odiff `--fail-on-layout`. |
| Determinism (R1.8) | The template sets `physics_jitter_fix=0` and pins ticks. Lint bans global RNG calls outside `rng.gd`, idle-mode Tween/Timer/AnimationPlayer in sim and replayed code, and `Time.get_ticks_*` in sim. Replays never use `Engine.time_scale` to speed up. |
| LSP from a headless editor works (R1.1) | Opt-in daemon (A3), not part of the default hook path until S5 says it is fast enough. |
| `--doctool` deletes `./doc/classes` (R1.1) | `api_dump` runs only in `~/.cache/godot-harness/api/<version>/`. |
| Sim/view (R1.6) | A9 template: `apply(state, command) -> Array[Event]`, stable int ids, no Node/NodePath in state, view rebuilt from a snapshot. |

---

## 4. Bootstrap and local commands (CI-free)

### 4.1 `tools/bootstrap.sh` (built in Phase 0 by a Sonnet builder straight from this section; no planner needed)

Behaviour (idempotent, about 1–2 min cold, under 5 s warm; prints at most 20 lines):
1. Read `tools/harness/pins.toml` (`godot_version = "4.7-stable"`, `godot_sha256`, `gdunit4_tag = "v6.2.2"`, `gdunit4_commit`, `odiff = "4.5.0"`, `gdtoolkit = "4.5.0"`).
2. Godot: if `~/.cache/godot-harness/godot/4.7-stable/Godot_v4.7-stable_linux.x86_64` is missing, download `https://github.com/godotengine/godot-builds/releases/download/4.7-stable/Godot_v4.7-stable_linux.x86_64.zip` into a fresh empty dir, check the sha256 (if `godot_sha256` is empty, print it and tell the user to pin it; Phase 0 pins it), unzip, chmod. Symlink `tools/bin/godot`. Check `godot --version` == `4.7.stable.official.5b4e0cb0f`.
3. gdUnit4: `git clone --depth 1 --branch v6.2.2` into `~/.cache/godot-harness/gdunit4/` and check that the commit matches the pin.
4. odiff: `npm i --prefix ~/.cache/godot-harness/odiff odiff-bin@4.5.0`. Use the native binary `node_modules/@odiff/linux-x64/odiff` and always call it with `timeout` and `</dev/null` (R1.7).
5. Python: `python3 -m venv .venv && .venv/bin/pip install pytest gdtoolkit==4.5.0 pyyaml` (pin versions in `tools/harness/requirements-dev.txt`).
6. Display: check `xvfb-run` and ImageMagick `compare`. `--with-vulkan` runs `apt-get update && apt-get install -y mesa-vulkan-drivers vulkan-tools mesa-utils` (R1.7). This is off by default; v0 needs only GL.
7. `--with-dotnet`: mono build zip + `dotnet-install.sh --channel 8.0` into `~/.cache` (R1.3). Off by default (D1).
8. API dumps: in `~/.cache/godot-harness/api/4.7/`, run `--dump-extension-api-with-docs` and `--doctool` (scratch dir only).
9. `h sync sample && h import sample`, then print `h doctor`.

The A8 wiring adds a Claude Code **SessionStart hook** for this repo and for game projects that runs `tools/bootstrap.sh --quiet` (use the `session-start-hook` skill when building it).

### 4.2 Local commands (no CI service; `tools/dev/ci.sh` is the CI)

| Command | Purpose | Time budget |
|---|---|---|
| `tools/bootstrap.sh` | Environment | ≤2 min cold |
| `tools/harness/h doctor` | Environment health | ≤5 s |
| `.venv/bin/pytest tests/unit -q` | Python units | ≤10 s |
| `.venv/bin/pytest tests/contract -q [-k area]` | Black-box verb tests | ≤5 min |
| `tools/harness/h test --project tests/fixtures/projects/gd_host` | gdUnit4 tests of `addons/harness` | ≤1 min |
| `tools/harness/h selftest` | Seeded-fault matrix | ≤10 min |
| `.venv/bin/pytest tests/e2e -q` | End-to-end flows | ≤5 min |
| `tools/dev/ci.sh [--quick]` | All of the above in order; writes `.harness/out/ci/<ts>/summary.md` | ≤20 min (quick: units + contract for changed areas) |
| `tools/dev/verify_fresh_clone.sh <branch>` | Clone from the remote into the scratchpad, bootstrap, run `ci.sh` | ≤25 min |

---

## 5. Roles and the test-writing / test-running separation

### 5.1 Roles

| Role | Model | Reads | Writes (allowlist enforced by pathguard) | Never |
|---|---|---|---|---|
| **Orchestrator** (main session) | Opus (main) | This plan, session notes, handoff `status.md`, agent summaries | `.claude/plans/build_and_test_plan.md` §0, `.claude/sessions/`, merges, commits, pushes, tags | Write harness code or tests itself (except trivial merge fixes). Read full transcripts. |
| **Planner** (per area) | Opus | Plan, research reports, scripts under `research/scripts/`, other specs (for consistency), may spike in the scratchpad | `.claude/plans/specs/NN_<area>.md`, `.claude/research/r2_<area>_spike.md` (optional) | Write repo code. |
| **Spec reviewer** | Opus | All specs | `.claude/plans/specs/REVIEW.md` | Edit specs (planners fix them on re-run). |
| **Test-writer** (per area) | Sonnet | Its spec, `00_contract.md`, research reports, fixtures. **Not** `tools/harness/**`, `addons/harness/**` (they do not exist yet in Phase 2; later rounds forbid reading them in the prompt) | `tests/contract/<area>/`, `tests/unit/<area>/`, `tests/gd/<area>/`, `tests/e2e/<area>/`, `tests/fixtures/**` (new fixtures only), `selftest/faults/<AREA>-*`, `.claude/handoff/<area>/test_notes.md` | Implement features. Edit another area's tests. |
| **Builder** (per area) | Sonnet | Its spec, contract, tests (read-only), research scripts (to port) | `tools/harness/**`, `addons/harness/**`, `templates/**`, `sample/**`, `docs/**` per the spec's file list, `.claude/handoff/<area>/build_notes.md`, `test_disputes.md` | Edit anything under `tests/` or `selftest/`. Skip, xfail, or loosen tests. Add `if testing:` branches. |
| **Verifier / test-runner** | Sonnet | Spec ACs, contract, its own fresh clone | `.claude/handoff/<area or phase>/verify_<date>.md` + `verify_<date>.json` only | Edit code or tests. Re-run selectively to hide flakes. Call anything "pass" that was skipped. |
| **Dispute adjudicator** | Sonnet (fresh test-writer) | Spec, the disputed test, the builder's dispute note, **not** the implementation | The disputed test (if wrong) + a resolution note in `test_disputes.md` | Change the AC (that needs a planner re-run). |

Agent definition files in `.claude/agents/` (`planner.md`, `test-writer.md`, `builder.md`, `verifier.md`) hold each role's `model:`, `tools:` and the role rules above, so every spawn gets them even if the prompt is short. If S3 shows these fields do not apply, the full role text is pasted into each prompt (§6 templates already contain it).

### 5.2 How the separation is enforced in practice

1. **Time order.** For each area, tests are written in a phase where no implementation exists (Phase 2 for core, the start of Phase 5 for the rest). Test-writers cannot shape tests to code that does not exist.
2. **Black-box surface.** Tests may only use: the `h` CLI, files in `.harness/out/`, fixture projects, the in-engine API **as named in the spec** (e.g. `Rng.seed_all(int)`), and the JSON schemas in the spec. Tests may not import from `tools/harness/harness/` except in `tests/unit/`, and only for the modules the spec names as public (`logscan`, `out`).
3. **Test lock.** After test-writers finish, the orchestrator runs `tools/dev/lock_tests.sh`, which writes `tests/LOCK.sha256` (hash per file under `tests/` and `selftest/`), and commits it. `check_lock.sh` runs first in `ci.sh` and in every verifier run. Any change by a builder is a hard FAIL.
4. **Pathguard.** After each agent returns, the orchestrator runs `tools/dev/pathguard.sh <role> <area> <base>..HEAD` (or on the uncommitted diff) before committing. Out-of-allowlist edits are reverted and the agent is re-run with a note.
5. **Red check.** Before any building, the verifier runs the new tests and confirms they fail for the right reason ("verb not found" / exit 2) and not because of collection errors. A test that passes with no implementation is reported as vacuous and goes back to the test-writer.
6. **Disputes, not edits.** A builder who believes a test is wrong writes `test_disputes.md` (test id, AC id, reasoning, a proposed fix) and carries on with the other tests. A fresh test-writer adjudicates without seeing the implementation. If the AC itself is wrong, the orchestrator re-runs the planner for that AC.
7. **Independent run.** The verifier always works in a **fresh clone of the pushed branch** in the scratchpad (`verify_fresh_clone.sh`). It runs the full suite twice (flakiness) and `h selftest`, and checks the lock. It reports the raw numbers. The orchestrator does not accept a builder's "all green" claim; gates use the verifier report only.
8. **Mutation spot-check.** The verifier also plants 3 random faults that are not in the catalogue (e.g. delete a lint rule, make `logscan` ignore `SCRIPT ERROR`, make `h test` map 100 → 0) in its clone. At least one test must go red for each. Survivors are listed as test gaps for the next test-writer round.

### 5.3 Branches and directories

- **Default (works even if S6 fails):** one working branch. Agents do not commit. The orchestrator commits each agent's output separately (`[A2][tests] ...`, `[A2][build] ...`, `[A2][verify] ...`) after the pathguard check, and pushes at the end of every phase step.
- **If S6 succeeds:** test-writers work on `tests/<area>` and builders on `build/<area>` (git worktrees under the scratchpad). The orchestrator merges to the working branch: tests first, then the build. The verifier clones the working branch.
- Parallel builders in the same tree are safe because of B2 (no shared registry), disjoint file lists per spec, and B3 (temp copies for Godot runs). If two specs list the same file, the spec reviewer must resolve it at G1.

### 5.4 Handoff files (how work survives container resets)

`.claude/handoff/<area>/status.md`, updated by every agent before it returns:
```
area: A2 scene      phase: build      state: in-progress|blocked|done
spec: .claude/plans/specs/02_scene.md @ <commit>
tests: 31 total / 27 pass / 4 fail (ids...)   lock: <sha of LOCK.sha256>
done: <bullets>     next: <bullets>     blockers: <bullets>   disputes: <n open>
```
The orchestrator commits these with the agent's output. A new session reads the newest `.claude/sessions/*.md`, then §0 of this plan, then every `status.md` that is not `done`.

---

## 6. Prompt templates (paste a template, then the area block from §7)

Every prompt starts with the **COMMON HEADER**.

```
COMMON HEADER
Repo: /home/user/godot-harness (only the repo persists; the container is ephemeral). Read CLAUDE.md first.
Target engine: Godot 4.7 stable (4.7.stable.official.5b4e0cb0f). Run `tools/bootstrap.sh` if `tools/harness/h doctor` fails
(before Phase 0 is done: download per CLAUDE.md into the scratchpad).
Round 1 rules you must follow: never trust Godot exit codes alone (scan logs, always `timeout`); `--import` first on a fresh copy;
never hand-write .tscn structure; Xvfb + gl_compatibility for images, never --headless; gdUnit4 with --ignoreHeadlessMode -c;
fixed ticks + seeded RNG for anything replayed.
Mark unverified claims [U] and verified runs [Run]. Downloads are untrusted: their own empty dir under the scratchpad; python -I.
Do NOT commit or push; the orchestrator does. Write only to the paths your role allows (listed below); anything else is reverted.
Before you finish, update .claude/handoff/<area>/status.md. Final reply: <=15 lines (what you wrote, counts, blockers). No transcripts.
```

### 6.1 Planner template (Opus)

```
[COMMON HEADER]
ROLE: PLANNER (Opus). You design one area of the harness and write its spec. You write no repo code.
Read first: .claude/plans/build_and_test_plan.md (§1-§5, and your area in §7), .claude/plans/specs/00_contract.md (if it exists;
your spec must conform to it), the research files listed in your area block, godot_harness_plan.md §3-§4.
You may run time-boxed spikes (<= 25% of your effort) in the scratchpad with the real Godot binary to settle design questions;
record each spike as [Run] with the command and an output excerpt, in your spec's "Spikes" section.
Write exactly one file: .claude/plans/specs/<NN_area>.md, <= 450 lines, with these sections in order:
 1 Purpose and failure modes covered (F-ids / D-ids)
 2 Interfaces: CLI verbs (args, flags, stdout format with a literal example, exit codes), in-engine APIs (GDScript signatures),
   file formats (JSON Schema blocks), config keys. Everything a black-box test needs, nothing internal.
 3 Design: modules and files to create (exact paths), Round 1 scripts to port (path in .claude/research/scripts/), algorithms,
   error patterns scanned, timeouts, performance budgets.
 4 Acceptance criteria: numbered AC-<NN>.<k>; each is observable from outside (command -> expected rc/output/file), states its
   test layer (unit/contract/gd/e2e/selftest) and needs no knowledge of internals.
 5 Seeded faults: FAULT-<AREA>-<k> entries {what is planted (exact file edit), on which fixture, verb that must catch it,
   expected verdict + output regex, must-catch or nice-to-catch}. At least the count stated in your area block.
 6 Fixtures needed: projects/files the test-writer must create (and which research cases to copy).
 7 Build order for the builder (small steps, each ending green on a named subset of ACs).
 8 Out of scope / deferred; Open questions [U]; assumptions taken from DEFAULTs in plan §2.
Prefer recommending over surveying. Keep the CLI surface small. If you need a decision from another area, write it as an
explicit assumption in §8 so the spec reviewer can reconcile it.
```

### 6.2 Test-writer template (Sonnet)

```
[COMMON HEADER]
ROLE: TEST-WRITER (Sonnet). You write tests from the spec. You must NOT open tools/harness/**, addons/harness/**, templates/**
or sample/** source (if they exist), so your tests are not shaped by an implementation.
Read: .claude/plans/specs/00_contract.md, your area spec <SPEC>, the research files it cites, existing tests/fixtures (for reuse).
Write only: tests/{unit,contract,gd,e2e}/<area>/, new fixtures under tests/fixtures/, selftest/faults/FAULT-<AREA>-*/,
.claude/handoff/<area>/test_notes.md and status.md.
Rules:
- One or more tests per AC; name each test after its AC id (test_ac_02_3_...). Every AC must be covered or listed as
  "untestable automatically" in test_notes.md with a reason.
- Black-box: call `tools/harness/h` via subprocess; copy fixtures to a tmp dir (B3) first; assert the exit code AND output lines.
  Do not assert exact wording beyond what the spec fixes (first-line verdict token, rule ids, path:line).
- Implement every FAULT entry of your spec as selftest/faults/<id>/fault.toml (+ files/patch), in the format of 00_contract.md.
- Include negative tests (a clean fixture must PASS: no false positives) and at least one timeout/hang case where the spec has one.
- Tests must run red now (the verbs do not exist). Run them once and record in test_notes.md that they fail for the right
  reason (exit 2 "unknown verb" or missing module), not collection errors.
- Use pytest only (.venv). gdUnit4 suites for in-engine APIs go in tests/gd/<area>/ (extends GdUnitTestSuite).
```

### 6.3 Builder template (Sonnet)

```
[COMMON HEADER]
ROLE: BUILDER (Sonnet). You implement your area so that its tests pass.
Read: 00_contract.md, your spec <SPEC> (follow its §7 build order), the tests for your area (read-only), the research scripts
your spec says to port, .claude/handoff/<area>/*.md.
Write only the files your spec §3 lists (under tools/harness/, addons/harness/, templates/, sample/, docs/), plus
.claude/handoff/<area>/build_notes.md, test_disputes.md and status.md.
Hard rules:
- Never edit tests/ or selftest/ (tests/LOCK.sha256 is checked; any change fails the gate). No skip/xfail, no special cases
  for test fixtures, no environment-detection branches that change behaviour under test.
- If a test seems wrong, write test_disputes.md (test id, AC id, why, proposed fix) and continue with the other tests.
- All Godot invocations go through tools/harness/harness/godot.py (timeout, log capture, scan). Output follows the contract (<=40 lines).
- After each build step run: .venv/bin/pytest tests/unit tests/contract/<area> -q, and `tools/harness/h selftest --area <AREA>`.
  Finish with tools/dev/ci.sh --quick. Report the exact pass/fail counts; do not round up.
```

### 6.4 Verifier template (Sonnet)

```
[COMMON HEADER]
ROLE: VERIFIER / TEST-RUNNER (Sonnet). You run, you do not fix. Honest numbers are the whole job.
Scope: <AREAS or PHASE>, branch <BRANCH> at commit <SHA>.
Steps:
1 tools/dev/verify_fresh_clone.sh <BRANCH> into the scratchpad (a fresh clone of the PUSHED branch; never the working tree).
2 tools/dev/check_lock.sh. If tests changed since the lock commit, report FAIL and stop.
3 Run tools/dev/ci.sh (full) TWICE. Record per layer: total/pass/fail/skip/error, wall time, and any test whose result
  differed between runs (flaky).
4 h selftest: the detection matrix (fault -> expected -> actual). Count must-catch misses and false positives on clean fixtures.
5 Mutation spot-check: in your clone, plant 3 faults NOT in selftest/ (e.g. disable one log-scan pattern; map gdUnit4 exit
  100 to 0; drop a lint rule that has a fault entry). Re-run the affected tests. List mutants that survived.
6 Walk the spec ACs: for each AC id, give the test id(s) that cover it and their result. ACs with no passing test = not met.
Write only .claude/handoff/<scope>/verify_<YYYY-MM-DD>.md (+ .json with the same numbers). Report skips as NOT PASSED.
Quote the last lines of every failing command. If you could not run something, write UNVERIFIED and why.
Verdict line at the top: GATE-PASS or GATE-FAIL with the reason. Do not edit any other file.
```

---

## 7. Build areas

Each block gives what to paste after the template, plus inputs, outputs and the acceptance bar. The **AC highlights** are minimums the planner must include; the planner adds more.

### P0. Interface contract (Opus planner, Phase 1a, runs alone)

Spec: `.claude/plans/specs/00_contract.md`

```
[PLANNER TEMPLATE] AREA: P0 contract. NN_area = 00_contract.
Read also: r1_1_cli.md, r1_3_testing.md (summariser), r1_4_scene_format.md §3, r1_5_failure_lint.md §3.
Define, for all areas: the `h` dispatcher and verb discovery (B2); the stdout format and exit codes (plan §3.2) with literal
examples; the .harness/out/<run-id>/ layout (run.json with argv, rc, scan verdict, durations; full logs); harness config
(`harness.toml` in a project: godot path, autoload names, lint severity overrides, renderer, tick rate); the godot.py
invocation contract (timeout defaults per kind, log scan patterns, verdict merge, rc 124 = hang); the fault.toml format and the
selftest runner semantics (apply to temp copy, run verb, compare verdict + regex, time limit); the fixture project conventions
(tests/fixtures/projects/<name>/ minimum files; who imports); the B3 temp-copy rule; the role path allowlists used by
pathguard.sh; the test-lock format; handoff status.md format. Seeded faults: >= 4 about the harness core itself (e.g. Godot
binary missing -> rc 4; a runner that hangs -> FAIL "hang" within timeout; log has SCRIPT ERROR but rc 0 -> FAIL).
```
Outputs: the spec only. Gate: the orchestrator reads it fully (it is the one spec read in full).

### A1. Core CLI, import, API lookup, load-check (C1, C2) — planner P1

Spec: `specs/01_core_cli.md` · Inputs: r1_1, r1_3 (fresh clone), r1_4 (`load_check.gd`, Logger capture), r1_5 §3, scripts `r1_4_scene_format/load_check.gd`, `probe*.gd`, `r1_5_lint/` (fixtures).

```
[PLANNER TEMPLATE] AREA: A1 core CLI. NN_area = 01_core_cli. Faults: >= 12.
Scope: h shim + python package skeleton per 00_contract; godot.py; logscan.py; verbs doctor, sync, import, api, check, selftest
(runner only). `h check` composes: stale-import detection; per-.gd `--check-only` (batch strategy: one godot process that
check-loads many scripts vs one per file; spike both and pick by time on ~50 files); load+instantiate of .tscn/.tres with Logger
capture (port r1_4 load_check.gd); call-out to `h lint` (A3) via its python API if present; optional `--smoke` that runs each
scene for 2 physics frames and scans stderr (R1.5 rec. 4). `h api`: index of extension_api.json + @GDScript.xml built once into
~/.cache; output signature + 1-line description; "not found, did you mean" with edit distance; `--exists Class.member` mode for
hooks. Resolve spike S1 (runner location) and S2 (exit codes) if Phase 0 left them open.
Fault ideas: r1_5 cases c01-c32 that are P/R class, r1_4 cases c03,c08,c10,c12,c13,c16,c18,c23 (hard/warn), broken script
attached to a scene (loads "ok"), runtime null-call in _ready (smoke), missing .godot (auto-import), class_name not imported.
```
AC highlights: `h check` on `clean_min` gives PASS in ≤15 s warm, and on a fresh copy it auto-imports. Each r1_4 "detectable" case gives FAIL with `path:line` where the engine gives a line. A script error inside a scene that "loads fine" gives FAIL. A runner hang gives FAIL "hang" before timeout+5 s. `h api Node2D.position` prints the signature. `h api KinematicBody2D` prints "not in 4.7" plus the suggestion `CharacterBody2D` (from the rename map). Every verb prints ≤40 lines.
Builds: `tools/harness/**` (core), `addons/harness/runners/{load_check,smoke,api_dump}.gd`, `tests/fixtures/projects/{clean_min,…}` (test-writer). Builder: one A1 builder, before the other core builders.

### A2. Scene generator, editor and digest (C4/C4w) — planner P2

Spec: `specs/02_scene.md` · Inputs: r1_4 (all), scripts `scene_gen.gd`, `scene_digest.gd`, `modify.gd`, `owner_test.gd`, `setuid.gd`, `spec_*.json`.

```
[PLANNER TEMPLATE] AREA: A2 scenes. NN_area = 02_scene. Faults: >= 10.
Scope: `h scene-gen spec.json` (port r1_4 scene_gen.gd: ClassDB.instantiate, add_child(n,true), owner rule, property
validation against ClassDB, $var/$res/$node value forms, instances, connections, groups, unique names, node_paths auto);
`h scene-edit <scene> ops.json` with a small op set (set_prop, add_node, remove_node, reparent, rename, connect, disconnect,
add_instance, set_script) using instantiate(GEN_EDIT_STATE_MAIN / _MAIN_INHERITED), with [editable] preserved; after every
write: load-check (A1 runner) + digest before/after + node-count/connection-count guard (pack() lies, R1.4 rule 14);
`h digest <scene>` and `--project` (scene list, autoloads, input actions, named layers) in a stable text format designed for
LLM reading and for diffing; `--json` variant. Decide the spec JSON schema (publish it as JSON Schema in the spec).
Decide if `scene-gen` should optionally assign a uid (ResourceSaver.set_uid then import) and when.
Fault ideas: typo'd property in spec (must fail, no file written), unknown type, op on inherited scene losing overrides
without [editable], duplicate sibling names, export node ref missing node_paths, hand-edited scene with bad parent= (digest
must show the vanished node).
```
AC highlights: a generated scene re-loads with zero logged warnings. Round-trip edits of `complex.tscn`/`inh.tscn` keep overrides, groups and connections (digest equal except the expected change). A bad spec gives exit 1 and writes no file. Digest output for the sample player scene is ≤60 lines.

### A3. Lint, Godot-3 hook, LSP (C3) — planner P3

Spec: `specs/03_lint.md` · Inputs: r1_5 (all), `scripts/r1_5_lint/{lint_rules_full.yaml,curated.yaml,scan.py,gen_rules.py}`, r1_8 checklist (determinism bans), r1_1 LSP notes, `scripts/r1_1_cli/lsp_probe.py`.

```
[PLANNER TEMPLATE] AREA: A3 lint. NN_area = 03_lint. Faults: >= 15.
Scope: `h lint [paths]` porting scan.py with the 1,213 rules (severity: low risk = error; medium/high = warning; per-project
overrides in harness.toml); rule families for .gd and .tscn/.tres; plus project-aware checks: InputMap action names used in
code vs project.godot; emit_signal("x")/connect("x") string names vs declared signals; determinism bans (global randf/randi/
shuffle/pick_random outside rng.gd; Time.get_ticks_* in sim dirs; Tween/Timer/AnimationPlayer not in physics mode in replayed
code); "no raw KEY_* outside remap code" (P15). Output contract per 00. A fast mode for hooks (<300 ms for one file, no Godot).
Optional `h fmt` wrapper for gdformat (off by default; R1.5 §4). `h lsp start|stop|diag` per spike S5; define when the hook may
use it (daemon already running). Also `--validate-conversion-3to4` as `h lint --godot3-oracle <file>` (R1.5 #7), never auto-convert.
Fault ideas: one per top-10 R1.5 pattern, a format=2 .tscn, rect_position in .tscn, global randf in sim/, idle Tween in sim,
unknown InputMap action, emit_signal typo. False-positive set: godot-demo-projects-style clean files (copy 10-20 small ones,
check licence) must give 0 errors.
```
AC highlights: the 32 r1_5 cases are flagged as documented in r1_5 §2 (minus the stated misses). 0 errors on the clean corpus. Single-file hook mode ≤300 ms. Every finding carries a rule id and a replacement hint.

### A4. Test runner (C5) — planner P4

Spec: `specs/04_test_runner.md` · Inputs: r1_3 (all), `scripts/r1_3_testing/summarize_junit.py`.

```
[PLANNER TEMPLATE] AREA: A4 test runner. NN_area = 04_test_runner. Faults: >= 8.
Scope: `h test [path|suite] [--filter]` wrapping gdUnit4 v6.2.2 GdUnitCmdTool.gd with --ignoreHeadlessMode -c -rd <out>;
exit mapping 0/100/101(WARN orphans)/103/105(broken suite) + log scan + timeout; summary <=15 lines (improve the r1_3
summariser: one-line collapsed failure text, res://path:line); auto-import; gdUnit4 install via `h sync`; test layout
convention res://tests/; how sim tests (pure RefCounted) and scene tests (scene_runner, simulate_frames, action press) are
written (examples for the CLAUDE.md skill); orphan policy. Resolve S4 (per-test filter). C#: design the `h test --dotnet` hook
only as a stub returning "disabled (D1)".
Fault ideas: failing assert, parse error in a test file (gdUnit4 105), test using an un-imported class_name on a fresh copy,
orphan node leak (101 -> WARN), infinite loop in a test (timeout), test that pushes SCRIPT ERROR but asserts nothing.
```
AC highlights: correct verdict for each exit code. Failure lines show `res://tests/x.gd:N`. A fresh copy with tests works without a manual import. 50 trivial tests take ≤5 s wall.

### A5. Scenario / replay runner (C6) — planner P5 (absorbs R2.2)

Spec: `specs/05_scenario.md` · Inputs: r1_8 (all), r1_6 (implications), r1_2 (satelliteoflove step/freeze design, input inside the step window), r1_1 (`--fixed-fps`, user args), scripts `r1_8_determinism/`.

```
[PLANNER TEMPLATE] AREA: A5 scenario/replay. NN_area = 05_scenario. Faults: >= 8.
Scope: in-engine autoloads Harness (parses user args; seeds; drives ticks; plays commands; dumps; asserts; quit(N)), Rng
(one root RandomNumberGenerator, derived sub-streams per name, save/restore seed+state), CommandBus (typed commands, target =
stable entity id, never NodePath); `h run scenario.json` -> state.json, metrics.json, events.jsonl, verdict. Scenario schema
(JSON Schema): {scene, seed, physics_ticks, ticks, inputs:[{tick, action, pressed|strength}], commands:[{tick, type, target,
value}], dumps:[{tick, what}], asserts:[{tick|at_end, path|metric, op, value, tol}]}. Decide input injection
(Input.action_press/parse_input_event at the right point of the physics tick so is_action_just_pressed works; spike it), the
entity id registry, the state-dump protocol (a `_harness_state()` method on registered nodes / sim state to_dict), golden
hash + tolerance policy B7, `h run --record` to produce a golden file and `--twice` to self-check determinism.
Spike: run one CharacterBody2D scenario 3x, report hashes [Run]. Coordinate with A9 (sim API) and A7 (trace hooks) via
explicit assumptions.
Fault ideas: global randf() in gameplay (twice-run hash differs -> FAIL nondeterministic), idle-mode Tween in replayed node,
wrong assert (metric outside tol), command targeting unknown id, scenario that never quits (timeout), NodePath stored in state.
```
AC highlights: the same scenario twice gives the same hash (same machine). A planted nondeterminism fault is caught by `--twice`. Asserts report the measured value against the expected value. 600 ticks headless finish in ≤3 s.

### A6. Visual / screenshot check (C8) — planner P6

Spec: `specs/06_visual.md` · Inputs: r1_7 (all), r1_1 recipes (b)(c), scripts `r1_7_visual/`.

```
[PLANNER TEMPLATE] AREA: A6 visual. NN_area = 06_visual. Faults: >= 6.
Scope: `h shot <scenario|scene> [--tick N] [--crop x,y,w,h | --node %Name] [--hide-layer ...] [--size WxH]` under
xvfb-run -a + gl_compatibility + --fixed-fps + --audio-driver Dummy; capture after frame_post_draw; output PNG path only (images
never printed or auto-read into context); `h shot --compare` vs baseline: exact (cmp) on the same env, else odiff
-t 0.1 --aa --fail-on-layout with the 0.1% default threshold (R1.7 §5); baseline store layout (baselines/<scene>/<name>.png +
meta.json {renderer, mesa, godot, size, approved_by, date}); `h baseline propose` (agent) vs `h baseline approve` (human only:
requires an interactive TTY confirmation and is blocked for agents by the A8 hook); numeric layout check `h layout <ui-scene>
--sizes 1280x720,1920x1080,2560x1080,800x1280` (controls off-screen, overlapping siblings, clipped labels) - spike whether it
works under --headless (RP.J question). `--movie N` for clips (write-movie PNG/AVI) used by A7 and the human gate.
Fault ideas: HUD element moved 20 px (diff FAIL), unseeded particles without fixed fps (should be stable WITH harness flags),
label clipped at 800x1280 (layout FAIL), baseline from a different renderer (refuse to compare), --headless forced (rc 4 with message).
```
AC highlights: two captures are byte-identical. A planted 20 px shift gives FAIL with the pixel count. `approve` is impossible from a non-TTY. One capture takes ≤3 s wall at 640x360.

### A7. Feel traces (C7) — planner P7 (absorbs R2.4; aligns with RP.A/RP.D metric names)

Spec: `specs/07_feel.md` · Inputs: r1_8, r1_7, addendum P01/P05/P06 rows and RP.A/RP.D prompts, A5 spec (if written; otherwise assume its schema).

```
[PLANNER TEMPLATE] AREA: A7 feel. NN_area = 07_feel. Faults: >= 6.
Scope: Trace autoload recording selected node properties per physics tick (pos, vel, on_floor, state name, input) to CSV;
`h trace scenario.json --nodes %Player[:props]`; a metrics library (python) with a catalogue for v0: jump apex height,
time-to-apex, air time, accel/decel ticks to max speed, coyote and buffer windows (via scenario sweeps k=0..10), camera
lag/overshoot/settle time, tween duration; FeelTargets .tres schema {metric, min, max, unit, approved_by, approved_on};
verdict per metric with measured value; `h trace --movie` makes the human clip + a metric table markdown (the human gate
artefact, D4); rule: the agent may edit tunables to hit targets, never the targets (A8 hook blocks writes to *targets*.tres
fields approved_by/min/max unless human). Units: px/s, ticks, seconds at the pinned tick rate. Include a 30/60/120 Hz
consistency sweep option.
Fault ideas: instant velocity (accel ticks = 0 < min), constant gravity (time-to-apex vs fall asymmetry fail), no coyote
(window 0), target file edited by agent without approval (hook test lives in A8 but the verdict reads approved_by).
```
AC highlights: the metrics match hand-computed values on synthetic CSVs (unit layer). The sample platformer reports all v0 metrics. Each planted feel fault fails exactly its metric.

### A8. Claude Code wiring: CLAUDE.md template, skills, hooks, agents, settings — planner P8 (absorbs R2.6)

Spec: `specs/08_claude_wiring.md` · Inputs: all other specs (verbs), r1_2 (MCP snippet), godot_harness_plan §3 (F-ids → mitigations), addendum §P5 (Game-architecture block), CLAUDE.md of this repo (style), official Claude Code docs (planner must fetch the current hooks/skills/subagents/settings docs and cite them; mark [U] if blocked).

```
[PLANNER TEMPLATE] AREA: A8 Claude Code wiring. NN_area = 08_claude_wiring. Faults: >= 8.
Scope (all under templates/claude/, installed into a game project by `h init`): CLAUDE.md.tmpl (<=120 lines: version pin,
<=15 golden rules, tool menu = h verbs and when, conventions, Game-architecture block, what to ask the human); skills
godot-api, godot-scene, godot-test, godot-scenario, godot-visual, godot-feel (+ godot-patterns index stub for Phase 7), each
SKILL.md <=100 lines with progressive disclosure; hooks: PostToolUse on Edit|Write of *.gd -> `h lint --hook` + `--check-only`
(fast path, <2 s, feedback via the documented blocking/feedback mechanism), on *.tscn|*.tres -> structural-edit warning +
load-check; PreToolUse deny for writes to baselines/ and approved target fields and for `h baseline approve`; Stop hook ->
`h check --changed` + `h test --changed` summary (time-capped); SessionStart -> bootstrap --quiet; subagents: log-triage,
api-lookup; settings.json permissions allowlist (h *, godot via h only); optional disabled .mcp.json (D3). Also `h init
<project>` (copies templates, writes harness.toml, syncs addons). Hooks are scripts (python -I) with unit tests that feed
recorded hook JSON on stdin. Plan the Phase 6 dogfood: 3 scripted `claude -p` tasks on the sample (if S3 says nested claude
works) checking that hooks fire and outputs stay small.
Fault ideas: Godot-3 code written via Edit (hook must give feedback), hand-written [node] block in .tscn (warning), agent
writes baseline (denied), agent edits approved target (denied), noisy hook output > 40 lines (fail), hook timing > budget.
```
AC highlights: hook scripts pass recorded-JSON tests. `h init` on an empty 4.7 project followed by `h check` gives PASS. CLAUDE.md.tmpl is ≤120 lines and passes a link and verb-name lint (every verb it mentions exists).

### A9. Simulation/view template + sample game — planner P9 (absorbs R2.3, GDScript only per D1)

Spec: `specs/09_sim_view_sample.md` · Inputs: r1_6 (implications), r1_8 checklist, r1_3 (sim tests), r1_4 (scene-gen for building the sample), A2/A5 specs, addendum P01/P08/P10/P11 rows.

```
[PLANNER TEMPLATE] AREA: A9 sim/view template + sample. NN_area = 09_sim_view_sample. Faults: >= 6.
Scope: templates/sim_view/: World/Thing typed RefCounted (or Resource) state, Command and Event types, apply(state, cmd) ->
Array[Event], stable int ids, snapshot to_dict/from_dict with version field, View node that reconciles from events and can
rebuild from a snapshot (snap-to-end-state, Solium), no Node/NodePath in state (lint rule id for A3). templates/project/:
project.godot with determinism settings (R1.8 checklist), named collision layers, InputMap actions, autoloads (Harness, Rng,
CommandBus, SceneManager stub) for tier "small" (D5). sample/: two scenes per D2 - (a) platformer: CharacterBody2D player with
MovementTuning.tres, a level built by `h scene-gen` from a spec, FeelTargets.tres with approved_by "provisional-default";
(b) tactics: grid sim using the template, view reconciling events, save/load round-trip. Scenarios for both (A5 format),
gdUnit4 tests (sim unit + one scene_runner test each), screenshot baselines (A6, marked provisional), traces (A7). Every
scene in sample/ must be generated (scene-gen spec files committed next to them) - the sample is the dogfood of A2.
Decide when NOT to use the sim/view split (real-time physics-heavy) and write it as decision rules for the CLAUDE.md block.
Fault ideas: NodePath stored in sim state, view mutating state, snapshot missing version, sim calling get_tree(), non-replayable
command (uses wall time), save round-trip lossy (int becomes float via JSON).
```
AC highlights: the sim's 1,000-turn seeded headless run has a stable hash. Save/load round-trip deep-equals. Rebuilding the view from a snapshot matches the live view digest. All sample scenes are generated and pass `h check`.

### A10. Pattern pack — planner P10 (Phase 7; consumes Round P)

Spec: `specs/10_pattern_pack.md` · Inputs: `rp_1_baseline.md`, `rp_2_references.md`, the topic reports `rp_*.md`, `rp_z1_pack.md`, specs A1–A9.

```
[PLANNER TEMPLATE] AREA: A10 pattern pack. NN_area = 10_pattern_pack. Faults: one per trap recorded by topic agents (cap 40).
Scope: turn RP.Z1's assembled pack into shippable harness parts: templates/claude/skills/godot-patterns/ (index + cards),
`h pattern-check [Pxx|all]`, `h ref Pxx` (pinned refs.yaml + fetch), `h new level|enemy|item|ui-screen` generators (built on
scene-gen), pattern scenarios/tests in templates, the game template from RP.F (or adoption of an existing one), R-SCALE rule
text. Keep eval hidden variants in eval/ (never installed). Prioritise by the RP.1 ranking; mark patterns deferred.
```
AC highlights: every pattern check passes on its reference implementation and fails on the recorded LLM-trap fixture.

### Areas not built in v0
- **C9 perf** (`h perf`): deferred to v0.1. Planner P11 runs after v0 with the R2.5 prompt as its input.
- **C10 live bridge:** D3 default, only a docs snippet in A8.
- **C# path:** D1 default, only the stub hooks.

---

## 8. Phased schedule

### 8.1 Phase table

| Phase | Session | Agents (parallel within a row) | Gate at end | Commit / push |
|---|---|---|---|---|
| **0 Setup** | 1 | Orchestrator writes `.claude/agents/*.md`, `.claude/handoff/` skeleton, `tools/dev/{pathguard,lock_tests,check_lock}.sh` (these are small; one Sonnet builder from §5 can do it). **Parallel:** Sonnet builder: `bootstrap.sh` + `pins.toml` + `h doctor` stub (§4.1); Sonnet spike agent: S1–S6 → `research/r2_spikes.md`; Round P: **RP.1** and **RP.2** (Sonnet, prompts in the addendum with the path amendments in §9.2). | **G0**: fresh-clone `bootstrap.sh && h doctor` passes; Godot sha256 pinned; spikes written; user has confirmed or accepted D1–D5 (ask once, then continue on the defaults) | Commit each output; push; session note |
| **1a Contract** | 2 | Opus **P0** alone | Orchestrator reads `00_contract.md` fully | Commit + push |
| **1b Specs** | 2 | Opus **P1–P9** in parallel (9 agents; split into two waves of 5+4 if concurrency is limited: P1–P4 + P5 first) | — | Commit each spec as it lands |
| **1c Review** | 2 | Opus **spec reviewer** → `REVIEW.md` (conflicts, overlapping files, missing ACs, unresolved [U]); re-run the affected planners with REVIEW items | **G1**: REVIEW has 0 open blocking items; every spec has ACs + faults ≥ the minimum | Push; tag `specs-v1` |
| **2 Core tests** | 3 | Sonnet test-writers **T1–T4** (A1–A4) in parallel | Verifier red check (tests fail for the right reason); `lock_tests.sh` | Commit tests + lock; push |
| **3 Core build** | 3–4 | Builder **B1** (A1) first. When A1's contract tests for `godot.py`/`check` are green: **B2, B3, B4** in parallel. **Meanwhile:** test-writers **T5, T9** (A5, A9) and **T6, T7** (A6, A7) in parallel, since they only need specs | Each builder: its area green in `ci.sh --quick`; disputes resolved | Commit per builder step; push after each builder |
| **4 Core verify** | 4 | Sonnet **verifier** (scope A1–A4) | **G2 v0-core**: GATE-PASS; must-catch faults 100% caught; 0 false positives on clean fixtures; 0 flaky tests; ≤1 surviving mutant | Push; tag `v0-core`; session note |
| **5 Runtime areas** | 5–6 | Lock tests for A5/A6/A7/A9 (written in Phase 3). Builders: **B5** (A5) ∥ **B9a** (A9 template + tactics sim, no scenes yet) ∥ **B6** (A6) → then **B9b** (sample scenes via scene-gen, scenarios) → **B7** (A7, needs A5 + the sample platformer). **Round P wave P1 starts here** (§9) | **G3**: verifier on A5/A6/A7/A9 + a regression run of A1–A4: GATE-PASS | Push per builder; tag `v0-runtime` |
| **6 Wiring** | 7 | Test-writer **T8** → builder **B8** (A8) → **dogfood** (3 `claude -p` tasks on the sample, or the orchestrator does them if S3 fails) → full verifier | **G4 = harness v0** (§11) | Push; tag `v0`; session note; update docs |
| **7 Patterns** | 8+ | Round P waves P1/P2 (topic agents, running since Phase 5) → RP.Z1 → Opus **P10** → T10 → B10 → verifier | **G5 v0.1** | Tag `v0.1` |
| **8 Eval** | 9+ | R3.2 + RP.Z2 pilot (Sonnet), human blind-preference kit | Human review | Report in `.claude/research/` |

### 8.2 Dependency summary
```
G0 ─► P0 ─► P1..P9 ─► REVIEW (G1)
        T1..T4 ─► lock ─► B1 ─► B2,B3,B4 ─► VERIFY core (G2)
        T5,T6,T7,T9 (during Phase 3) ─► lock ─► B5 ∥ B9a ∥ B6 ─► B9b ─► B7 ─► VERIFY (G3)
        T8 ─► B8 ─► dogfood ─► VERIFY (G4 = v0)
RP.1, RP.2 (Phase 0) ─► RP.A..K (from Phase 5, use real h verbs) ─► RP.Z1 ─► P10 ─► T10 ─► B10 ─► VERIFY (G5)
```

### 8.3 Session protocol (every session, including after a container reset)

Start (≤10 min):
1. `git pull`. Read `CLAUDE.md`, then the newest `.claude/sessions/*.md`, then §0 of this plan, then every `.claude/handoff/*/status.md` that is not `done`.
2. Run `tools/bootstrap.sh` (once it exists), then `h doctor`. Godot, odiff and the venv are re-created after a reset.
3. Pick the next row of §8.1 whose inputs are `done`. Never restart a `done` item. Resume `in-progress` items from their status.md `next:` list.

During:
- After each agent returns: run pathguard → `git add` that agent's paths → commit with an `[Area][role]` prefix → update §0 → push. (A reset should lose at most one agent's work.)
- Keep the orchestrator's context small. Read agents' ≤15-line replies and status files, not full specs (except `00_contract.md` and `REVIEW.md`).

End:
1. Write `.claude/sessions/YYYY-MM-DD[-N].md`: goal, what was done (with commits), gate results, decisions taken, open issues, the **exact next agents to spawn**.
2. Update §0. Commit and push both.

---

## 9. Round P (pattern research) as a parallel track

### 9.1 How it merges with the build

| Round P step | When | Uses from the build | Feeds into the build |
|---|---|---|---|
| RP.0 MCP hands-on | **Skip** (R1.2 already ran beremaran live). Run only if the user overrides D3. | — | A8 `.mcp.json` snippet |
| RP.1 baseline failure study | Phase 0 (parallel) | Godot binary only | Priorities for P9 (sample scenes) and A10; trap fixtures for selftest; `rp_1_work` messy projects (kept small, in the repo under `eval/rp1_projects/` if each is under 2 MB, else noted) |
| RP.2 reference census | Phase 0 (parallel) | Lint rules (quality grep) | `refs.yaml` draft → A10 `h ref`; clean false-positive corpus for A3 |
| RP.A–K topic agents | From Phase 5, after G2 | **Real `h` verbs** (`check`, `test`, `scene-gen`, `run`; `trace`/`shot` once G3 passes) instead of stand-ins | Pattern cards, metric definitions (aligned with A7 names), lint rules, generator sketches, trap fixtures |
| RP.Z1 pack assembly | After the topic agents | v0 harness | Input to planner P10 |
| RP.Z2 benchmark | Phase 8 | v0.1 | Go/no-go on the pattern pack |

Throttle the topic agents by the RP.1 ranking (addendum P4). With the D2 default, run full depth for RP.A, RP.D, RP.E, RP.F, RP.C. Run reduced depth (no agent trials) for RP.G, RP.I, RP.J, RP.K, RP.H. Skip RP.B (3D) until 3D is chosen.

### 9.2 Required amendments to the addendum prompts (apply when pasting them)
1. **Paths:** the scratchpad does not persist. Write reports to `.claude/research/rp_*.md` and small code to `.claude/research/scripts/rp_<id>/`. Large clones stay in the scratchpad and get re-cloned by pinned commit.
2. **Harness:** replace "write minimal stand-ins" with "use `tools/harness/h` verbs. If a needed verb is missing, write the stand-in under `scripts/rp_<id>/` and list it under 'merge requests for A10'".
3. **Nested trials:** follow S3. If `claude -p` is unavailable, use the "simulated baseline" label from the addendum.
4. **Metric names:** use the A7 catalogue names. New metrics are proposed in a "metrics to add" section, which A10 consumes.
5. **Cost caps:** at most 3 nested trials per topic, 40 turns each, 30 min each.

---

## 10. Seeded-fault suite and verification metrics

- **Format** (fixed in `00_contract.md`): `fault.toml` = `{id, area, fixture, apply: {copy|patch|replace: ...}, verb: "h check", expect: {verdict: FAIL, regex: "...", max_seconds: N}, severity: must|nice, source: "r1_5 c05"}`.
- **Minimum catalogue for v0:** at least 75 faults (P0 4, A1 12, A2 10, A3 15, A4 8, A5 8, A6 6, A7 6, A8 8, A9 6), plus clean-fixture checks that must PASS.
- **Gate metrics** (reported by the verifier):
  - must-catch detection = 100%; nice-to-catch ≥ 70%;
  - false positives on clean fixtures and on the sample = 0;
  - flaky tests across 2 full runs = 0;
  - surviving mutants ≤ 1 per gate;
  - each verb's median output ≤ 40 lines;
  - per-verb time budgets from the specs met (median over the selftest).
- **Regression:** every later gate re-runs the whole fault matrix, not only the new area.

---

## 11. Definition of done: harness v0 (Gate G4)

All of these must be true, as shown by a verifier report from a fresh clone of the pushed `v0` tag:
1. `tools/bootstrap.sh` on a fresh container reaches `h doctor` = PASS with no manual steps (network as in CLAUDE.md).
2. Verbs `doctor sync import api check lint digest scene-gen scene-edit test run trace shot baseline(propose) selftest init` exist and meet their spec ACs. `lsp` is optional.
3. All ACs of A1–A9 are covered by passing tests or listed in a signed-off "untestable" list (≤5 items in total).
4. The §10 gate metrics are met.
5. `sample/` has two scenes per D2. Every scene is generated from committed specs. `h check`, `h test`, `h run` (both scenarios, `--twice`), `h shot --compare` and `h trace` all pass on it. Its baselines and feel targets are marked `provisional-default` until the user approves them.
6. `h init` on an empty Godot 4.7 project installs CLAUDE.md, skills, hooks and settings. A dogfood run shows: a Godot-3 edit gets hook feedback within 2 s, a hand-written `[node]` block gets a warning, and a write to a baseline is denied.
7. `docs/HARNESS.md` (verb reference + workflows) and `docs/ADOPTION.md` (tier A: C1–C5 for an existing project in a day; tier B: + scenarios/feel; tier C: sim/view template) exist and only use verbs that exist (lint-checked).
8. A session note and §0 are up to date, and the `v0` tag is pushed.

Not required for v0: pattern pack (v0.1), perf, C#, 3D, MCP, cross-machine determinism.

---

## 12. Cost, effort and risks

### 12.1 Effort estimate [U: rough, from Round 1 agent sizes]

| Item | Agents | Tokens each (approx.) | Total |
|---|---|---|---|
| Phase 0 (bootstrap, dev tools, spikes) | 3 Sonnet | 0.3–0.6 M | ~1.5 M |
| RP.1 + RP.2 | 2 Sonnet (RP.1 runs nested trials) | 1–3 M | ~4 M |
| Planners P0–P9 + reviewer + re-runs | ~13 Opus | 0.2–0.5 M | ~5 M (Opus) |
| Test-writers T1–T9 + adjudications | ~11 Sonnet | 0.3–0.6 M | ~5 M |
| Builders B1–B9 (B9 split in two) | ~10 Sonnet | 0.6–1.5 M | ~10 M |
| Verifier runs (red checks + 4 gates + re-runs) | ~8 Sonnet | 0.2–0.4 M | ~2.5 M |
| Dogfood (Phase 6) | 3 nested runs | 0.3 M | ~1 M |
| **v0 total** | ~50 agent runs | | **~29 M tokens (~5 M Opus)**, 7 sessions |
| Round P topic agents + Z1 + A10 cycle | ~14 | 1–3 M (trials) | ~25 M, 2–3 sessions |

Wall clock: Godot runs are fast (0.3 s per script, about 7 s per import, about 1–3 s per capture), so agent reasoning dominates the time. The full `ci.sh` should stay under 20 min.

### 12.2 Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Nested `claude -p` unavailable in subagents (S3) | Medium | Round P trials and dogfood weaker | "Simulated baseline" label. The orchestrator runs dogfood tasks itself. Keep RP.Z2 for a human-run session. |
| Agent tool cannot choose a model per spawn | Medium | Role/model split is muddled | Model set in `.claude/agents/*.md`. If that also fails, run planners in an Opus main session and builders in a separate Sonnet session (the handoff files make this work). |
| Builders weaken or work around tests | Medium | False confidence | Test lock, pathguard, verifier mutation check, disputes protocol (§5.2). |
| Test-writers write tests that fit no sane implementation, or are vacuous | Medium | Wasted build cycles | Red check. Adjudicator. ACs are observable by construction (planner template §4). |
| Spec drift between areas (output format, file ownership) | High without P0 | Integration failures | P0 contract first, spec reviewer at G1, B2 verb discovery, disjoint file lists. |
| Godot or GitHub download blocked or slow after a reset | Low | Session cannot start | `pins.toml` with the exact URL and sha256; retry with backoff. If still blocked, ask the user to allowlist the host. Never vendor the binary into git. |
| gdUnit4 repo moves or tag disappears | Low–Medium | Bootstrap breaks | Pin the commit. Bootstrap tries both `MikeSchulze/gdUnit4` and `godot-gdunit-labs/gdUnit4` URLs. |
| Xvfb/llvmpipe flakiness or Mesa update changes pixels | Medium | Visual tests flap | Exact compare only when the env meta matches. Otherwise odiff threshold. The verifier's double run catches flaps. Baselines record the Mesa version. |
| Parallel Godot runs collide on `.godot/` import or ports (LSP) | Medium | Flaky tests | B3 temp copies. LSP uses a random free port. |
| The orchestrator's context fills up over a long session | High | Lost thread | ≤15-line agent replies, status files, one phase step per session, the session note. |
| Over-building (too many verbs and options) | Medium | Cost, worse agent UX | The v0 verb list is closed. New verbs need a planner plus a reviewer note. Output ≤40 lines is enforced by tests. |
| Push restricted to certain branch names (S6) | Low | Branch scheme unusable | The default single-branch scheme. |

---

## 13. How to launch this plan (first session, exact order)

1. **Orchestrator setup (no agents):** read §0–§5. Create `.claude/handoff/` and `.claude/plans/specs/` with README stubs. Write `.claude/agents/{planner,test-writer,builder,verifier}.md` from §5.1 + §6 (frontmatter `model: opus` for planner, `model: sonnet` for the others; tools: test-writer and builder get Read/Write/Edit/Bash/Glob/Grep; verifier gets the same, with its write limits stated in the prompt). Commit and push.
2. **Ask the user once** about D1–D5, showing the defaults from §2.1. Do not wait: continue on the defaults and record the answer when it arrives.
3. **Spawn in parallel (one message, 4 agents):**
   - a. *Sonnet builder:* "Phase 0 bootstrap": implement `tools/bootstrap.sh`, `tools/harness/pins.toml`, `tools/harness/h` (shim + `doctor` only), `requirements-dev.txt` and `.gitignore` additions per §4.1/§3.1. Download Godot once and record its sha256. Use the builder template with "AREA: A0 bootstrap; spec = plan §4.1".
   - b. *Sonnet builder:* "Phase 0 dev tools": `tools/dev/{pathguard.sh,lock_tests.sh,check_lock.sh,verify_fresh_clone.sh,ci.sh (skeleton running whatever exists)}` per §5.2–§5.3 and §4.2, each with a small self-test.
   - c. *Sonnet spike agent:* S1–S6 from §2.3 → `.claude/research/r2_spikes.md` (each with a verdict and the [Run] evidence).
   - d. *Sonnet:* **RP.2** reference census (addendum prompt + §9.2 amendments).
4. **Then spawn RP.1** (Sonnet, addendum prompt + §9.2). It is the costliest Phase 0 item, so start it once S3 says whether nested `claude -p` works (or right away with the "simulated baseline" fallback).
5. **Gate G0:** spawn a *Sonnet verifier* with scope "bootstrap" to run `verify_fresh_clone.sh` on the pushed branch. When it passes, update §0 and write the session note listing step 6 as next.
6. **Next session:** spawn Opus **P0** (contract). After it lands, spawn **P1–P5** together, then **P6–P9** (they can read the P1–P5 specs). Then run the **spec reviewer**. Then proceed with §8.1 Phase 2.
