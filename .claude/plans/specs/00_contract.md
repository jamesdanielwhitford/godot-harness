# 00 Interface contract (P0)

Status: spec v1, 2026-10-15, Opus planner P0. Every area spec (01-10) must conform to this file; where a spec needs to
deviate, it says so in its §8 and the spec reviewer decides. Tags: [Run] verified here (§3.4), [U] unverified,
Δ = change to code that already exists (§3.2). This contract supersedes plan §3.1/§10 on two points: runtime data
files are TOML/JSON, not YAML (`fault.toml`, not `fault.yaml`), and there is no committed `expected_matrix.yaml`.

## 1. Purpose and failure modes covered

One shared surface for all `h` verbs, so 9 parallel planners and builders produce parts that fit, and so tests can be
written black-box from specs alone. Covers:
- **Exit codes lie** (R1.1 #4, R1.5 #2, S2): one invocation path (`godot.py`) with timeout, full log, log scan as the
  authoritative signal, rc only as an extra failure signal; rc=0 proves nothing; rc 124 = hang.
- **F11 noisy logs**: <=40 stdout lines, first line is the verdict, full logs on disk.
- **F7 class cache** (R1.1 #3): the auto-import rule (§2.8.6).
- Build-process risks (plan §12): spec drift (this file), parallel collisions (B2 discovery, B3 temp copies), builders
  loosening tests (lock, pathguard), lost work after a reset (handoff format).

## 2. Interfaces

### 2.1 Shim and dispatcher (B1, B2)
- `tools/harness/h` runs `python3 -I` (stdlib only, Python >= 3.11 for `tomllib`) with `harness.cli.main(argv)`. It
  exports `HARNESS_REPO` (the harness repo root). Δ It must **not** `cd`: relative paths (`--project sample`, spec
  files) resolve against the caller's cwd.
- Verb discovery: every module `tools/harness/harness/verbs/<name>.py` whose name does not start with `_` is a verb.
  The CLI name is the module name with `_` -> `-` (`scene_gen.py` -> `h scene-gen`). No registry file.
- Each verb module exports `HELP: str` (one line, <= 70 chars) and `run(argv: list[str]) -> int`. Optional:
  `CONFIG_TABLE: str` + `CONFIG_KEYS: dict[str, type]` (§2.6). Subcommands (`baseline propose`, `lsp start`) are
  parsed by the verb itself; line 1 still uses the verb name.
- `h --help`: rc 0, `usage: h <verb> [args]` then one line per verb `  <verb>  <HELP>`. `h` with no args: same text,
  rc 2. `h <unknown>`: exactly one stdout line `ERROR h unknown verb '<x>'` (+ ` (did you mean '<y>'?)` when edit
  distance <= 2), rc 2. These three are the only outputs without a run dir.
- `h <verb> --help` / `-h`: usage text <= 40 lines, rc 0, no run dir.
- v0 verb list is closed (plan §3.2): `doctor sync import api check lint digest scene-gen scene-edit test run trace
  shot baseline lsp selftest init`. A new verb needs a planner + reviewer note.

### 2.2 Common flags, project resolution, environment
Every verb accepts these flags (argparse parent parser `out.common_parser()`):
| Flag | Meaning |
|---|---|
| `--project DIR` | Godot project dir (contains `project.godot`). Relative to cwd. |
| `--strict` | Warnings count as errors: a would-be WARN becomes FAIL, rc 1. |
| `-h`, `--help` | Usage, rc 0. |
Argument errors print `ERROR <verb> usage: <message>` (not argparse's stderr text) and give rc 2.

Project resolution for verbs that need one (all but `doctor`, `selftest`, `api`, `lsp stop`): `--project` >
`$HARNESS_PROJECT` > nearest ancestor of cwd containing `project.godot`. None found, or the dir has no
`project.godot`: rc 2, `ERROR <verb> no Godot project (pass --project DIR)`.

| Env var | Default | Meaning |
|---|---|---|
| `HARNESS_REPO` | set by shim | harness repo (runners, rules, selftest/) |
| `HARNESS_CACHE` | `~/.cache/godot-harness` | pinned tools, API index (exists, `pins.cache_dir()`) |
| `HARNESS_GODOT` | unset | Godot binary; beats harness.toml and `$HARNESS_REPO/tools/bin/godot` |
| `HARNESS_PROJECT` | unset | project dir fallback |
| `HARNESS_OUT` | unset | out root override (else §2.5) |
| `HARNESS_TMP` | `${TMPDIR:-/tmp}/godot-harness` | temp copies (selftest, tests) |
| `HARNESS_TIMEOUT_SCALE` | `1.0` | multiplies every default timeout; 0.1-10, else rc 2 |
| `HARNESS_ROOT` | unset | dev tools only (`tools/dev/_common.sh`) |
No other env var may change verb behaviour (builder rule: no test-detection branches).

### 2.3 Stdout format (all verbs)
Grammar, one item per line, in this order; nothing is printed to stderr by a verb:
1. **Verdict line** (always): `^(PASS|FAIL|WARN|ERROR) <verb> <reason>$`, reason 1-100 chars, e.g.
   `2 errors, 1 warning in 14 files (3.4s)`.
2. **Stat lines** (0+): `^[a-z][a-z0-9_-]*: <value>$`, value not starting with `[`. Project verbs print
   `project: <abs path>` first. Verbs that may import print `import: ran (<why>)|fresh|skipped`.
3. **Check lines** (0+): `^(OK|FAIL|SKIP|WARN) +<name>: <detail>$` (doctor, selftest, per-item tables).
4. **Finding lines** (0+): `^<loc>: \[<rule>\] (error|warning|info): <message>( \(hint: <hint>\))?$`
   - `<loc>` = `res://path:LINE` | `res://path` for project files; a cwd-relative or absolute path (with optional
     `:LINE`) for files outside the project; `-` when there is no file. Lines are 1-based.
   - Order: errors, warnings, info; then path, line. Identical (loc, rule, message) collapse into one line with
     ` (xN)` appended. Info lines are shown only if room is left.
5. **Truncation line** (if needed): `... <K> more findings (<e> errors, <w> warnings) in findings.jsonl`.
6. **Log line** (always, last): `log: <run dir>/` (cwd-relative if under cwd, else absolute; trailing `/`).
Limits: <= 40 lines total; each line <= 240 chars (cut with `...`). Exempt: `--help` output.
Invariants (tested on every invocation by the test helper): FAIL => at least one `error` finding or `FAIL` check
line; WARN => at least one `warning` finding/`WARN` check line and no error; PASS => no error/warning findings.

Literal examples (paths shortened only where marked `...`):
```
$ tools/harness/h check --project sample
FAIL check 2 errors, 1 warning in 14 files (3.4s)
project: /home/user/godot-harness/sample
import: fresh
files: 11 .gd, 3 .tscn
res://player/player.gd:12: [godot.parse-error] error: Expected expression after "+" operator.
res://levels/l1.tscn: [godot.parent-vanished] error: Parent path './Root/A' for node 'B' has vanished (hint: parent= never includes the root name)
res://ui/hud.gd:40: [syn-yield] warning: yield() was removed in Godot 4 (hint: await <signal>)
log: sample/.harness/out/20261015T142233Z-check-a3f9/

$ tools/harness/h check --project /tmp/h/clean_min
PASS check 0 findings in 2 files (9.1s)
project: /tmp/h/clean_min
import: ran (no .godot/)
files: 1 .gd, 1 .tscn
log: /tmp/h/clean_min/.harness/out/20261015T142301Z-check-0c1d/

$ HARNESS_GODOT=/nonexistent/godot tools/harness/h check --project /tmp/h/clean_min
ERROR check godot binary not found: /nonexistent/godot (run tools/bootstrap.sh)
project: /tmp/h/clean_min
log: /tmp/h/clean_min/.harness/out/20261015T142340Z-check-77b0/

$ tools/harness/h doctor
PASS doctor 6/6 checks ok
OK   godot: 4.7.stable.official.5b4e0cb0f
OK   gdunit4: v6.2.2 0127a55f4543
OK   odiff: .../odiff/node_modules/@odiff/linux-x64/odiff
OK   venv: .venv ok
OK   xvfb-run: /usr/bin/xvfb-run
OK   compare: /usr/bin/compare
log: .harness/out/20261015T142400Z-doctor-19ce/
```

### 2.4 Verdicts and exit codes
| rc | Verdict | When |
|---|---|---|
| 0 | PASS | no error/warning findings |
| 1 | FAIL | >= 1 error finding (or warning under `--strict`) |
| 2 | ERROR | usage/config: bad flag, bad `harness.toml`, no project, input file fails its schema |
| 3 | ERROR | harness internal error: uncaught exception (traceback in `traceback.txt`), harness runner rc 2/3 |
| 4 | ERROR | environment: Godot missing or wrong version, xvfb-run/odiff/gdUnit4 missing, `--headless` for shot |
| 5 | WARN | warnings only, `--strict` off |
ERROR conditions stop the verb at once (first one wins). A hang or crash of Godot is a **finding** (FAIL), not ERROR,
because project code usually causes it. Δ `tools/dev/ci.sh` treats rc 5 from an `h` layer as PASS (warnings).

### 2.5 Run directory
- Out root: `$HARNESS_OUT` > `<project>/.harness/out` (project verbs) > `$HARNESS_REPO/.harness/out`. The verb
  creates `<out root>/../.gdignore` (empty) so Godot never imports run outputs (hidden dirs are skipped anyway [Run]).
- Run id: `^\d{8}T\d{6}Z-<verb>-[0-9a-f]{4}$` (UTC start time, random suffix). `<out root>/latest` is a symlink to
  the newest run dir, replaced atomically. Retention: at start, prune to the newest 50 run dirs, never one < 10 min old.
- Contents (reserved names; verbs put their own artefacts under `artifacts/`):
  `run.json`, `summary.txt` (byte-identical to stdout), `findings.jsonl` (all findings, uncapped),
  `godot/NN-<kind>.log` (combined stdout+stderr per Godot invocation, NN from 01), `godot/NN-<kind>.runner.jsonl`
  (runner `@@H` records), `traceback.txt` (rc 3 only), `artifacts/`.

`run.json` (JSON Schema, draft 2020-12; additional properties allowed for verb extras under `extra`):
```json
{"type":"object","required":["schema","run_id","verb","argv","cwd","project","started_at","duration_s","rc",
 "verdict","reason","counts","findings_total","truncated","invocations"],
 "properties":{
  "schema":{"const":"harness.run/1"}, "run_id":{"type":"string"}, "verb":{"type":"string"},
  "argv":{"type":"array","items":{"type":"string"}}, "cwd":{"type":"string"},
  "project":{"type":["string","null"]}, "started_at":{"type":"string","format":"date-time"},
  "duration_s":{"type":"number"}, "rc":{"enum":[0,1,2,3,4,5]},
  "verdict":{"enum":["PASS","FAIL","WARN","ERROR"]}, "reason":{"type":"string"},
  "counts":{"type":"object","required":["error","warning","info"],
            "properties":{"error":{"type":"integer"},"warning":{"type":"integer"},"info":{"type":"integer"}}},
  "findings_total":{"type":"integer"}, "truncated":{"type":"boolean"},
  "godot":{"type":["object","null"],"properties":{"path":{"type":"string"},"version":{"type":"string"}}},
  "invocations":{"type":"array","items":{"type":"object",
    "required":["n","kind","argv","timeout_s","rc","timed_out","duration_s","log","scan_verdict"],
    "properties":{"n":{"type":"integer"},"kind":{"type":"string"},"argv":{"type":"array","items":{"type":"string"}},
      "timeout_s":{"type":"number"},"rc":{"type":"integer"},"timed_out":{"type":"boolean"},
      "duration_s":{"type":"number"},"log":{"type":"string"},
      "scan_verdict":{"enum":["PASS","WARN","FAIL"]},"runner_rc":{"type":["integer","null"]},
      "retried":{"type":"boolean"}}}},
  "extra":{"type":"object"}}}
```
`findings.jsonl`, one object per line: `{"path": "res://a.gd"|null, "line": 3|null, "rule": "godot.parse-error",
"severity": "error"|"warning"|"info", "message": "...", "hint": "..."|null, "source": "scan"|"runner"|"verb",
"invocation": 1|null}`.

### 2.6 `harness.toml` (project root, optional)
Missing file = all defaults. Invalid TOML, an unknown table, an unknown key or a wrong type: rc 2 with a finding
`res://harness.toml: [harness.config] error: <what>`. Precedence: CLI flag > env > harness.toml > default.
```toml
[harness]
schema = 1
godot = ""                    # binary path, relative to the project dir; HARNESS_GODOT wins
godot_version = "4.7.stable.official.5b4e0cb0f"   # must equal `godot --version`, else rc 4
tick_rate = 60                # physics ticks per second (A5, A7, A9 template)
renderer = "gl_compatibility" # only value accepted in v0 (A6)
autoloads = ["Harness", "Rng", "CommandBus"]      # autoloads `h sync` enables (A1/A5)
sim_dirs = ["res://sim"]      # determinism-lint scope (A3, A9)
test_dir = "res://tests"      # gdUnit4 root (A4)
[timeouts]                    # seconds per invocation kind (§2.8.2); before HARNESS_TIMEOUT_SCALE
[scan]
ignore = []                   # extra regexes for benign log lines; may not match protected rules (§2.8.4)
```
Other tables belong to areas: a verb module declares `CONFIG_TABLE = "lint"` and `CONFIG_KEYS = {"severity": dict}`;
`config.py` collects them by discovery (no shared registry). Reserved table names: `lint` (A3), `scene` (A2),
`test` (A4), `run` (A5), `shot` (A6), `feel` (A7), `hooks` (A8).

### 2.7 Rule ids
`[a-z0-9][a-z0-9._-]*`, globally unique. Dotted prefixes per owner: `godot.` and `harness.` (P0/A1), `check.` (A1),
`scene.` (A2), `lint.` (A3 project-aware checks), `test.` (A4), `run.` (A5), `shot.` (A6), `feel.` (A7), `hook.` (A8),
`sim.` (A9), `selftest.` (A1). The r1_5 rule ids (`syn-*`, `fn-*`, `prop-*`, `tscn-*` ...) stay undotted; any new
rule must be dotted. Core ids defined here: `harness.hang`, `harness.crash`, `harness.rc`, `harness.runner-incomplete`,
`harness.config`, `harness.godot-version`, `harness.internal`, plus the `godot.*` scan rules in §2.8.4.

### 2.8 Godot invocation contract (`tools/harness/harness/godot.py`)
All Godot processes are started by `godot.run()`; no verb calls `subprocess` on Godot directly (A6's `xvfb-run` and
odiff calls also go through `godot.run(..., display="xvfb")` / `proc.run()` respectively).

**2.8.1 Binary.** `HARNESS_GODOT` > harness.toml `godot` > `$HARNESS_REPO/tools/bin/godot`. Missing/not executable:
rc 4 `godot binary not found: <path> (run tools/bootstrap.sh)`. `--version` (last stdout line) must equal
`godot_version` (default = pins.toml `godot_version_string`), else rc 4 with finding `[harness.godot-version]`. The
result is cached in `$HARNESS_CACHE/godot_version.json` keyed by (realpath, mtime, size).

**2.8.2 Command line.** `[godot] + display flags + ["--path", <abs project>] + kind args (+ ["--", user args])`,
stdin `/dev/null`, stdout+stderr combined into one log file, cwd = project dir, own process group.
Display `headless` -> `--headless`. Display `xvfb` -> prefix `xvfb-run -a -s "-screen 0 1920x1080x24"` and add
`--rendering-method gl_compatibility --audio-driver Dummy`; never together with `--headless` (A6 refuses: rc 4).
Default timeouts (s), scaled by `HARNESS_TIMEOUT_SCALE`, overridable per kind in `[timeouts]`:
| kind | version | import | check_only | runner | smoke | test | scenario | shot | movie | doctool |
|---|---|---|---|---|---|---|---|---|---|---|
| s | 20 | 180 | 30 | 60 | 30 | 300 | 120 | 60 | 300 | 120 |
Runner-style kinds (`runner`, `smoke`, `scenario`, `shot`) take `-s <abs path of runner>`; `check_only` adds
`--check-only -s res://<file>`.

**2.8.3 Timeout and rc.** At T: SIGTERM to the group; T+3 s: SIGKILL. Recorded rc 124, `timed_out: true`, finding
`<loc>: [harness.hang] error: no exit within Ts (last log line: <...>)`, loc = runner/scene target if known else `-`.
`godot.run()` returns by T+5 s. Signal deaths are normalised to 128+N (SIGABRT -> 134, [Run]) and give
`[harness.crash] error`. `import` is retried once on rc 134 (R1.4 §4), `retried: true`, both logs kept.

**2.8.4 Log scan (`logscan.py`, public to unit tests).** Lines starting `@@H ` and the built-in benign list are
skipped. Rules, first match wins, in this order:
| id | regex (Python, per line) | severity | location |
|---|---|---|---|
| `godot.parse-error` * | `^SCRIPT ERROR: Parse Error: (.*)` | error | next `(res://F:L)` |
| `godot.script-error` * | `^SCRIPT ERROR: (.*)` | error | next `(res://F:L)` |
| `godot.script-load-failed` * | `^ERROR: Failed to load script "(res://[^"]+)"` | error | the quoted path, no line |
| `godot.crash` * | `^(handle_crash: Program crashed\|Aborted\|Segmentation fault)` | error | - |
| `godot.load-failed` | `^ERROR: (Failed loading resource\|Failed to load resource\|Cannot load\|No loader found)(.*)` | error | `res://` path in the line |
| `godot.parent-vanished` | `^WARNING: Parent path .* has vanished` | error | - |
| `godot.vanished` | `^WARNING: .*has vanished` | error | - |
| `godot.leak` | `^WARNING: \d+ ObjectDB instances? (was\|were) leaked at exit` | info | - |
| `godot.error` | `^ERROR: (.*)` | error | next `(res://F:L)` |
| `godot.warning` | `^WARNING: (.*)` | warning | next `(res://F:L)` |
(`\|` in the table is the Markdown escape of `|`.) "Next `(res://F:L)`" = the first match of `\((res://[^():]+):(\d+)\)` in the matched line or the following 6 lines
before the next rule match; engine C++ locations (`(core/...cpp:N)`) are never used. `*` = protected: never
ignored, never downgraded. Built-in benign list: `^Godot Engine v\d`, `remote port number must be between 1 and
65535`, `Could not set V-Sync mode`, `^ALSA lib `, `cannot find card`. `[scan] ignore` regexes and a verb's declared
downgrade policy (in its spec) apply only to non-protected rules; an ignore regex that matches a sample line of a
protected rule (`SCRIPT ERROR: Parse Error: x`, `SCRIPT ERROR: x`, `ERROR: Failed to load script "res://x.gd"`) is
rejected with rc 2. API: `logscan.scan(text: str, extra_ignore: list[str] = []) -> list[dict]` (keys of
findings.jsonl minus `source`/`invocation`).

**2.8.5 Runner protocol.** Harness runners live in `$HARNESS_REPO/addons/harness/runners/<name>.gd` and are run by
absolute path with `--path <project>` (S1 [Run]), so one-shot checks need no `h sync`. Each runner is one
self-contained file (`extends SceneTree`, inner classes allowed, no `class_name`, no preload of other harness files).
In-game code (autoloads `Harness`, `Rng`, `CommandBus`, `Trace`, and gdUnit4) is installed by `h sync`.
Runners print records as single stdout lines `@@H <json>`: `{"t":"finding", path, line, rule, severity, message,
hint}`, `{"t":"stat","key":..,"value":..}`, `{"t":"data",...}` (verb-specific, saved in `.runner.jsonl`), and last
`{"t":"done","rc":N}` immediately followed by `quit(N)`. Runner rc: 0 clean, 1 findings, 2 bad args, 3 runner bug.
Runners check `load()` results with `can_instantiate()` before `.new()` and `quit(1)` themselves (S2).

**2.8.6 Verdict merge per invocation.** worst of: (a) scan verdict (error -> FAIL, warning -> WARN); (b) rc signal:
124 -> FAIL hang, >=128 -> FAIL crash, rc outside the kind's expected set (`check_only`: {0,1}; runner kinds: {0,1};
`import`: {0}; `test`: per A4 map) -> FAIL `[harness.rc]`; (c) runner: no `done` record -> FAIL
`[harness.runner-incomplete]` even when rc = 0; runner rc 2/3 -> verb rc 3. rc 0 never improves (a)-(c). Runner
findings win over scan findings with the same (path, line, message) (dedup). The verb's verdict is the worst over
its invocations and its own findings.

**2.8.7 Auto-import.** Before any kind other than `version`/`import`/`doctool`, `godot.ensure_imported(project)`
runs `import` when `.godot/` or `.godot/global_script_class_cache.cfg` is missing, or any `*.gd` containing
`class_name` is newer than that cache. It prints `import: ran (<why>)`, else `import: fresh`. Import findings count.

### 2.9 Core Python API for builders (not used by tests except `logscan`, `out.render`)
```python
# harness/out.py
class Run:            # with out.Run(verb, argv, project=None) as r: ...  -> creates run dir; on exception rc 3
    def finding(self, path, line, rule, severity, message, hint=None, source="verb"): ...
    def stat(self, key, value): ...
    def check(self, status, name, detail): ...           # status in OK FAIL SKIP WARN
    def error(self, rc, reason): ...                      # rc in 2,3,4: stop with ERROR
    def finish(self, reason) -> int: ...                  # render, write files, return rc
def common_parser() -> argparse.ArgumentParser: ...       # --project --strict; error() -> rc 2 contract line
def render(verb, verdict, reason, stats, checks, findings, log_dir, max_lines=40) -> list[str]: ...
# harness/project.py   resolve(arg: str|None) -> Path ; res_path(project, fs_path) -> "res://..."
# harness/config.py    load(project) -> dict  (validates §2.6 incl. discovered CONFIG_TABLEs)
# harness/godot.py     run(run, kind, project, args=[], user_args=[], runner=None, display="headless",
#                          timeout=None) -> Invocation ; ensure_imported(run, project) ; binary(run, project)
```

### 2.10 Seeded faults and `h selftest`
Layout: `selftest/faults/<ID>/fault.toml` (+ `files/`), `selftest/clean/<ID>/fault.toml`. ID
`^(FAULT|CLEAN)-(P0|A(10|[1-9]))-\d{2}$`, equal to the dir name. Format:
```toml
id = "FAULT-P0-02"
area = "P0"
title = "scene script hangs in _init during load-check"
fixture = "clean_min"          # tests/fixtures/projects/<name>, or "none" (empty dir)
severity = "must"              # must | nice   (CLEAN entries: always must)
source = "plan §7 P0"
[[apply]]                      # ordered; applied to the temp copy only
op = "write"                   # write {path, text | from (relative to the fault dir)}
path = "scenes/hang.tscn"
from = "files/hang.tscn"
[[apply]]
op = "write"
path = "harness.toml"
text = "[timeouts]\nrunner = 5\n"
# other ops: {op="replace", path, old, new, count=1} (must match exactly count times), {op="delete", path}
[run]
verb = "check"
args = []                      # "{project}" and "{fault_dir}" are substituted
env = {}                       # extra env for the verb
no_project = false             # true: do not add --project {project}
[expect]
rc = 1
verdict = "FAIL"
regex = ['\[harness\.hang\]']  # all must match (re.MULTILINE search over stdout); >= 1 for FAULT entries
not_regex = []
max_seconds = 30
```
`h selftest [--area A]... [--id GLOB] [--jobs N] [--keep] [--faults-dir DIR]` (`--faults-dir` defaults to
`$HARNESS_REPO/selftest`; it is how tests feed synthetic trees). Per entry: fresh dir
`$HARNESS_TMP/selftest-<run-id>/<ID>/proj` <- fixture (without `.godot/`, `.harness/`); apply ops; run
`$HARNESS_REPO/tools/harness/h <verb> [--project <copy>] <args>` with `HARNESS_OUT=<run dir>/entries/<ID>/out`, hard
kill at max_seconds + 30; save stdout to `<run dir>/entries/<ID>/stdout.txt`. Result: `CAUGHT` (rc, verdict, all
regex, no not_regex, time <= max_seconds, <= 40 lines), else `MISSED` / `SLOW` / `OVERFLOW` (> 40 lines) /
`BROKEN` (an op failed); CLEAN entries give `PASS` or `FALSEPOS`. Selftest rc: 2 if any fault.toml fails the schema
(finding `<path>: [selftest.bad-fault] error`); 1 if any must entry is not CAUGHT/PASS or any BROKEN/FALSEPOS;
5 if only nice entries missed; else 0. Output: stat lines `faults: <n> total, <c> caught, <m> missed (must <a>, nice
<b>), <s> slow, <o> overflow, <x> broken` and `clean: <n> total, <p> pass, <f> false-positive`, then one check line
per non-success (`FAIL FAULT-P0-02: MISSED expected FAIL rc=1 /\[harness\.hang\]/, got PASS rc=0 in 3.1s`).
`artifacts/matrix.json` lists every entry `{id, area, severity, expected{rc,verdict}, actual{rc, verdict, seconds,
first_line, lines}, result}`. Default `--jobs` = min(4, nproc); results must not depend on it. Temp copies are
deleted unless `--keep`.

### 2.11 Fixtures and the B3 temp-copy rule
- B3: no test, selftest entry or verifier ever runs a verb on a project inside the repo tree, except `sample/` by the
  bootstrap and the orchestrator. Copy first (excluding `.godot/`, `.harness/`). After the full suite,
  `git status --porcelain tests selftest` is empty.
- `tests/fixtures/projects/<name>/`, name `^[a-z0-9_]+$`. Minimum: `project.godot` with `config_version=5`,
  `[application] config/name="<name>"`, `config/features=PackedStringArray("4.7")`; `FIXTURE.md` (<= 5 lines:
  purpose, owner area, expected `h check` verdict). Never commit `.godot/`, `.harness/`, `addons/gdUnit4/`,
  `addons/harness/` (synced), `*.uid`. Text files only, <= 200 KB per fixture. Hand-written `.tscn` in fixtures and
  fault `files/` are allowed (they are inputs, often deliberately broken) and follow r1_4 §3 unless broken on purpose.
- Who imports: never the repo copy. The verb under test auto-imports the temp copy (§2.8.7), or a test calls
  `h import --project <copy>`. Tests may cache one imported "warm" copy per fixture per pytest session and copytree it.
- Fixtures are immutable once committed (pathguard): a test-writer that needs a variant creates a new fixture.

### 2.12 Test conventions (all areas)
- pytest only, run from `.venv`. Layers `tests/{unit,contract,gd,e2e}/<area>/`; test names `test_ac_<NN>_<k>_<slug>`.
- Shared helpers (written by T1, read-only for others): `tests/helpers/h.py` with `run_h(*args, cwd=None, env=None,
  timeout=120) -> Result(rc, stdout, lines, verdict, verb, reason, stats, checks, findings, log_dir)`,
  `copy_fixture(name, dest) -> Path`, `assert_contract(result)` (the §2.3 grammar, limits, invariants, run.json
  schema, `summary.txt == stdout`). It parses output itself and never imports `tools/harness/harness`.
  `tests/conftest.py` registers markers `godot`, `xvfb`, `slow` (> 30 s) and puts `tests/` on `sys.path`.
- Every contract test calls `assert_contract` on each `h` result. Tests never `skip`/`xfail` on a missing
  environment: a missing Godot yields rc 4 and the test fails (skips count as not passed, plan §5.2).
- Unit tests may import only `harness.logscan` and `harness.out` (`render`), via `sys.path` insert of
  `tools/harness`.

### 2.13 Role write allowlists (`tools/dev/pathguard.sh`; `<a>` = area id, lowercase; any role: `.claude/handoff/<a>/status.md`)
| Role | May write |
|---|---|
| orchestrator | `.claude/plans/build_and_test_plan.md`, `.claude/sessions/*`, `.claude/handoff/*`, `tests/LOCK.sha256`, `.gitignore`, `CLAUDE.md`, `README.md`; Δ `tools/dev/*` (small fixes only) |
| planner | `.claude/plans/specs/[0-9]*_*.md`, `.claude/research/r2_*_spike.md` |
| spec-reviewer | `.claude/plans/specs/REVIEW.md` |
| test-writer | `tests/{contract,unit,gd,e2e}/<a>/*`, new files under `tests/fixtures/*`, Δ `selftest/faults/fault-<a>-*`, Δ `selftest/clean/clean-<a>-*`, `.claude/handoff/<a>/test_notes.md`; Δ area `a1` also `tests/conftest.py`, `tests/helpers/*` |
| builder | `tools/harness/*`, `addons/harness/*`, `templates/*`, `sample/*`, `docs/*`, `.claude/handoff/<a>/{build_notes,test_disputes}.md`; Δ area `a1` also `tools/bootstrap.sh` |
| verifier | `.claude/handoff/<a>/verify_*.{md,json}` |
| adjudicator | `tests/{contract,unit,gd,e2e}/<a>/*`, `.claude/handoff/<a>/test_disputes.md` |
Δ `<area>` may be a comma list (`a1,p0,bootstrap`); a path passes if any listed area allows it. P0's tests and
faults are written by T1 with areas `a1,p0,bootstrap`.

### 2.14 Test lock (exists; unchanged except Δ prune)
`tests/LOCK.sha256`: one `<sha256>  <path>` line per file under `tests/` and `selftest/`, `LC_ALL=C` sorted, paths
repo-relative, excluding the lock, `__pycache__`, `.pytest_cache`, `.godot`, Δ `.harness`, `*.pyc`. Written only by
the orchestrator (`lock_tests.sh`, commit `[lock] <areas>`); `check_lock.sh` rc 0 ok / 1 changed / 3 no lock. An
adjudicated test change is re-locked by the orchestrator in its own commit.

### 2.15 Handoff `status.md` (every agent, before it returns)
```
area: <ID> <slug>      phase: plan|tests|build|verify      state: todo|in-progress|blocked|done
spec: <path> @ <commit|uncommitted>
tests: <N> total / <P> pass / <F> fail (<ids>)      lock: <sha12|n/a>
updated: <YYYY-MM-DD> by <role> (<model>)
done:
- <bullet>
next:
- <bullet>
blockers:
- none
disputes: <n> open
```
Keys are fixed and in this order; bullets start with `- `. A new session resumes from `next:`.

## 3. Design

### 3.1 Files (all built by the A1 builder B1 as its step 0; A1's spec must list them)
`tools/harness/harness/out.py` (Run, render, common_parser, run-dir management, retention, latest link),
`project.py`, `config.py`, `logscan.py`, `godot.py` (binary, version cache, run, timeouts, process groups, merge,
ensure_imported), `proc.py` (timeout-safe subprocess for non-Godot tools), `faults.py` (fault.toml loader +
validator), `verbs/selftest.py`; Δ `cli.py`, `verbs/doctor.py`, `h`.

### 3.2 Changes to existing code (Δ)
| # | File | Change | Who |
|---|---|---|---|
| C1 | `tools/harness/h` | drop `cd "$HERE"` | B1 |
| C2 | `harness/cli.py` | `_`->`-` names; `HELP` listing one per line; unknown verb to stdout + did-you-mean | B1 |
| C3 | `verbs/doctor.py` | use `out.Run`; verdict line; keep check lines; missing required tool -> rc 4 | B1 |
| C4 | `tests/unit/bootstrap/test_doctor.py` | `"doctor: ok"` -> first line `PASS doctor`; rc != 0 -> rc == 4 | T1 |
| C5 | `tools/dev/pathguard.sh` | comma-separated areas; `fault-<a>-*`/`clean-<a>-*`; a1 extras (§2.13) | orchestrator |
| C6 | `tools/dev/_common.sh` | also prune `.harness` in `lock_manifest` | orchestrator |
| C7 | `tools/dev/ci.sh` | rc 5 from `h` layers = PASS (warn); gd_host layer copies the fixture to `$HARNESS_TMP` first (B3) | orchestrator |
| C8 | `tools/bootstrap.sh` | step 9: `h sync --project sample`, `h import --project sample` | B1 |
| C9 | `tools/harness/requirements-dev.txt` | add `jsonschema` (test helper validates run.json) | B1 |
| C10 | `.gitignore` | add `sample/addons/gdUnit4/`, `sample/addons/harness/`, `reports/` | orchestrator |
| C11 | plan §3.1/§10 text | `fault.yaml` -> `fault.toml`; drop `expected_matrix.yaml`; `rules/lint_rules.yaml` ships as JSON (A3) | orchestrator |
C5-C7 and C10 are dev-tool edits of <= 20 lines each; the orchestrator applies them before Phase 2 (T1 needs C5).

### 3.3 Why these choices
TOML/JSON at runtime: B1 is stdlib-only and `tomllib` is stdlib. `res://` locations: identical across temp copies
(stable selftest regexes), match engine logs, map to files via `project:`. Runners outside the project: S1 [Run], so
`h check` needs no `addons/` in the project. Hang/crash = FAIL: the agent must fix its code; ERROR = fix harness/env.

### 3.4 Spikes (scratchpad `p0/proj`, Godot 4.7.stable.official.5b4e0cb0f)
- [Run] `-s res://ok.gd` prints only the banner `Godot Engine v4.7.stable.official.5b4e0cb0f - https://godotengine.org`,
  a blank line, then script output; rc 0. Banner goes in the benign list.
- [Run] leak: `var n=Node.new(); quit(0)` -> `WARNING: 1 ObjectDB instance was leaked at exit (run with `--verbose`
  for details).` + `   at: cleanup (core/object/object.cpp:2535)`, rc 0 -> `godot.leak` info, C++ location ignored.
- [Run] `push_warning("w1")`/`push_error("e1")` -> `WARNING: w1` / `ERROR: e1`, each followed by
  `GDScript backtrace (most recent call first):` and `[0] _init (res://pe.gd:3)` / `(res://pe.gd:4)`, rc 0.
- [Run] `--check-only -s res://bad.gd` -> `SCRIPT ERROR: Parse Error: Expected expression after "+" operator.` +
  `at: GDScript::reload (res://bad.gd:3)` + `ERROR: Failed to load script "res://bad.gd" with error "Parse error".`
- [Run] runtime null call: `SCRIPT ERROR: Invalid call. Nonexistent function 'foo' in base 'Nil'.` +
  `at: _init (res://rt.gd:4)`; process hangs; `timeout -k 2 5` -> rc 124 after 5.01 s with the log fully flushed.
- [Run] `OS.crash("boom")` -> `ERROR: boom`, process `Aborted`, rc 134.
- [Run] after `--import`, `vis/b.png` was imported, `.harness/out/a.png` was not (hidden dirs skipped); the
  `.gdignore` is belt and braces.

## 4. Acceptance criteria (T1 writes these under `tests/{unit,contract}/p0/`)
- AC-00.1 `h --help` rc 0, <= 40 lines, lists every `verbs/*.py` (hyphenated), wall <= 0.5 s. [contract]
- AC-00.2 `h nosuchverb` -> rc 2, stdout exactly 1 line `^ERROR h unknown verb 'nosuchverb'`; `h` alone -> rc 2. [contract]
- AC-00.3 For every verb listed by `h --help`: `h <v> --help` rc 0, <= 40 lines, no new run dir. [contract]
- AC-00.4 For every listed verb: `h <v> --no-such-flag` -> rc 2, line 1 `^ERROR <v> usage: `, last line `^log: `. [contract]
- AC-00.5 Every `h` result in the P0 and A1 contract suites passes `assert_contract` (§2.12). [contract]
- AC-00.6 `run.json` validates against the §2.5 schema; `summary.txt` == stdout; `findings.jsonl` count ==
  `findings_total`; run id matches the regex; `<out root>/latest` points to it; `.harness/.gdignore` exists. [contract]
- AC-00.7 `HARNESS_OUT=<dir>` puts the run dir under `<dir>`. [contract]
- AC-00.8 Project resolution: `--project` relative to a different cwd works; `HARNESS_PROJECT` works; cwd inside a
  subdir of the project works; none -> rc 2 `no Godot project`. [contract]
- AC-00.9 `harness.toml` with unknown key `[harness] tick_rat = 60` -> rc 2, finding
  `res://harness.toml: [harness.config] error:` naming `tick_rat`; invalid TOML -> rc 2; no file -> defaults. [contract]
- AC-00.10 `[scan] ignore = ["SCRIPT ERROR"]` -> rc 2 `[harness.config]`. [contract]
- AC-00.11 `HARNESS_GODOT=/nonexistent/godot h check` -> rc 4, `^ERROR check godot binary not found`, wall <= 2 s. [contract]
- AC-00.12 `HARNESS_GODOT=<fixture script printing 4.6.stable.official.x>` -> rc 4, `[harness.godot-version]`. [contract]
- AC-00.13 Hang (FAULT-P0-02 setup, `runner = 5`): rc 1, `[harness.hang]`; in run.json the invocation has
  `timed_out: true`, `rc: 124`, `duration_s <= 10`; no process whose cmdline contains the copy path survives. [contract]
- AC-00.14 Parse-broken script attached to a scene (FAULT-P0-03 setup; loading that scene alone exits 0, S2): rc 1,
  a finding at `res://scripts/broken.gd:4`. [contract]
- AC-00.15 `OS.crash` in a scene script (FAULT-P0-07 setup): rc 1, `[harness.crash]`, invocation rc 134. [contract]
- AC-00.16 `logscan.scan` on the §3.4 logs returns exactly: parse error -> (`godot.parse-error`, `res://bad.gd`, 3),
  plus (`godot.script-load-failed`, `res://bad.gd`, None); runtime -> (`godot.script-error`, `res://rt.gd`, 4);
  push_error -> (`godot.error`, `res://pe.gd`, 4); push_warning -> (`godot.warning`, `res://pe.gd`, 3); leak ->
  (`godot.leak`, None, None, info); banner, `@@H` lines and `ERROR: remote port number must be between 1 and 65535`
  -> nothing; no finding ever has a non-`res://` path. [unit]
- AC-00.17 `out.render` with 100 findings: <= 40 lines, errors before warnings, truncation line counts correct,
  lines <= 240 chars, duplicates collapsed with `(xN)`; `--strict` maps a warnings-only set to FAIL. [unit]
- AC-00.18 `out.Run` whose body raises -> rc 3, line 1 `^ERROR <v> internal: `, `traceback.txt` written. [unit]
- AC-00.19 `HARNESS_TIMEOUT_SCALE=0.5` halves `timeout_s` in run.json; `HARNESS_TIMEOUT_SCALE=50` -> rc 2. [contract]
- AC-00.20 Godot argv in run.json starts with the resolved binary, contains `--headless` and `--path <abs copy>`. [contract]
- AC-00.21 `h selftest --area P0` -> rc 0; stats show 8 faults all caught, 2 clean pass; `artifacts/matrix.json`
  has 10 entries; wall <= 120 s. [contract, slow]
- AC-00.22 `h selftest --faults-dir <synthetic>`: an unmeetable must fault -> rc 1 + `FAIL <id>: MISSED`; only a nice
  miss -> rc 5; a `replace` that matches 0 times -> `BROKEN`, rc 1; a clean entry that fails -> `FALSEPOS`, rc 1;
  missing `expect.rc` -> rc 2 `[selftest.bad-fault]`; max_seconds 0.001 -> `SLOW`; a verb flooding > 40 lines is
  not possible by contract, so OVERFLOW is unit-tested on the comparator. [contract + unit]
- AC-00.23 `--jobs 1` and `--jobs 4` give the same matrix results; fixture source trees are byte-identical
  before/after; temp dirs are gone without `--keep`, present with it. [contract, slow]
- AC-00.24 After the full contract suite, `git status --porcelain tests selftest` is empty (B3). [e2e]
- AC-00.25 `pathguard.sh test-writer a1,p0 working-tree` accepts `selftest/faults/FAULT-P0-01/fault.toml` and
  `tests/helpers/h.py`; `pathguard.sh test-writer a2 ...` rejects both. `check_lock.sh` ignores a new
  `tests/fixtures/x/.harness/` file. [unit, uses `HARNESS_ROOT` temp repos]
- AC-00.26 `h doctor` follows §2.3 (examples) and returns 4 when a required tool is missing (C3/C4). [contract]
Untestable automatically: handoff format (§2.15; checked by the orchestrator on read).

## 5. Seeded faults (fixture `clean_min`, verb `check` unless noted; all `must` unless noted)
| ID | Planted | Expect |
|---|---|---|
| FAULT-P0-01 | `run.env = {HARNESS_GODOT="/nonexistent/godot"}` | rc 4, ERROR, `godot binary not found`, <= 5 s |
| FAULT-P0-02 | write `scripts/hang.gd` (`extends Node` + `func _init(): while true: pass`), `scenes/hang.tscn` (root Node with that script), `harness.toml` `[timeouts] runner = 5` | rc 1, FAIL, `\[harness\.hang\]`, <= 40 s (incl. import) |
| FAULT-P0-03 | write `scripts/broken.gd` with a parse error on line 4, `scenes/uses_broken.tscn` attaching it (Godot loads the scene with rc 0, S2) | rc 1, FAIL, `^res://scripts/broken\.gd:4: \[`, <= 40 s |
| FAULT-P0-04 | write 60 files `scripts/bad_NN.gd`, each with a parse error | rc 1, FAIL, `^\.\.\. \d+ more findings`, <= 40 lines, <= 90 s |
| FAULT-P0-05 | write `harness.toml` = `[harness]\ntick_rat = 60\n` | rc 2, ERROR, `tick_rat`, <= 5 s |
| FAULT-P0-06 (nice) [U] | autoload `res://scripts/early_quit.gd` whose `_init` calls `Engine.get_main_loop().quit(0)` (assumes autoloads load under `-s`) | rc 1, FAIL, `\[harness\.runner-incomplete\]` |
| FAULT-P0-07 | scene script whose `_init` calls `OS.crash("boom")` | rc 1, FAIL, `\[harness\.crash\]` |
| FAULT-P0-08 | delete `project.godot` | rc 2, ERROR, `no Godot project`, <= 5 s |
| CLEAN-P0-01 | none | rc 0, PASS, `^import: ran` |
| CLEAN-P0-02 | fixture `none`, verb `doctor`, `no_project = true` | rc 0, PASS |

## 6. Fixtures needed (T1)
- `tests/fixtures/projects/clean_min/`: `project.godot` (§2.11; `run/main_scene="res://scenes/main.tscn"`),
  `scripts/hello.gd` (`class_name Hello extends Node2D`, typed, warning-free), `scenes/main.tscn` (root `Node2D` with
  that script, one `Sprite2D` child, hand-written per r1_4 §3), `FIXTURE.md`. Must PASS `h check` (CLEAN-P0-01).
- `tests/fixtures/bin/godot_wrong_version` (executable sh: prints `4.6.stable.official.deadbeef`, exit 0).
- `tests/fixtures/selftest_trees/{miss_must,miss_nice,broken_op,falsepos,bad_schema,slow}/` (AC-00.22; use
  `doctor` with `no_project` or `check` on `clean_min`).
- `tests/fixtures/logs/*.log`: the §3.4 excerpts verbatim (AC-00.16).

## 7. Build order (B1, step 0 of A1; each step ends green on the named ACs)
1. C1, C2, `out.py`, `project.py`, `config.py`, C3 doctor -> AC-00.1-4, 6-9 (with doctor and a stub-free
   `check` arriving in A1), 17, 18, 26.
2. `logscan.py` -> AC-00.16, 10.
3. `godot.py` + `proc.py` (needs A1's `check` + `load_check.gd` runner) -> AC-00.11-15, 19, 20.
4. `faults.py`, `verbs/selftest.py` -> AC-00.21-23.
5. C8, C9; orchestrator applies C5-C7, C10, C11 before Phase 2 -> AC-00.24, 25.

## 8. Out of scope, open questions, assumptions
Out of scope: Windows/macOS, a global `--json` stdout mode (verbs such as `digest --json` define their own), LSP
daemon lifecycle (A3), C# (`h test --dotnet` stub, D1), parallel runs against one project dir (B3 avoids it).
Open [U]: (1) autoloads are instantiated when running `-s` (FAULT-P0-06 is nice until A1 checks); (2) Godot output to
stdout vs stderr interleaving in one pipe keeps order per write, not strictly by time; (3) `xvfb-run` exit status
when Godot is killed by the group signal (A6 to confirm); (4) whether `.harness/` inside a project confuses
`--import` on 4.7.x patch releases (hidden-dir skip verified only on 4.7.0).
Assumptions for other areas: A1 owns `check`, `import`, `sync`, `doctor`, the `load_check`/`smoke` runners and step 0
above. A3 ships rules as JSON and maps r1_5 risk to severity. A4 maps gdUnit4 0/100/101/103/105 into §2.4 (103 ->
rc 4), adds `[test.no-tests]` FAIL when `Statistics` reports 0 tests (S4: bad `-a` path exits 0), and may downgrade
only non-protected scan rules. A6 uses `display="xvfb"` and refuses `--headless` with rc 4. A8 hooks read the `log:`
line and then `findings.jsonl`. Plan defaults D1-D5 and B1-B8 are taken as given; S6 -> single working branch.
