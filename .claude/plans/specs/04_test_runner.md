# 04 Test runner (A4, C5)

Status: spec v2, 2026-10-15, Opus planner P4 re-run (applies REVIEW.md v1 N01, N02, N17; R-01, R-24, R-31, R-39
consistency). Conforms to `00_contract.md` (cited as "contract §x"); deviations are listed in §8. Tags: [Run]
verified in this spec's spikes (§3.7) or cited research, [U] unverified.

## 1. Purpose and failure modes covered

`h test` is the one way an agent runs GDScript tests. It wraps gdUnit4 v6.2.2 `GdUnitCmdTool.gd` so that the result
is a trustworthy verdict plus a short list of `res://file:line` failures, and so that gdUnit4's traps cannot produce a
false PASS.

| Failure mode | Source | How A4 covers it |
|---|---|---|
| F5 / exit codes lie: a bad `-a` path or an empty selection exits 0 with nothing run | S4 [Run], §3.7 K3 | Targets are resolved and checked by the harness before Godot runs; 0 tests = FAIL `[test.no-tests]` |
| Parse error in a test file aborts the run (rc 105) with no XML report | R1.3, K5 | rc 105 = FAIL; parse errors come from the protected log-scan rules with `res://path:line` |
| Fresh clone / new `class_name` not in the cache: CmdTool itself fails to parse (rc 1) or the suite fails (rc 105) | R1.3, K6, K7 | contract §2.8.7 auto-import before every run; rc 1 = FAIL with a hint |
| Fail-fast default hides later failures | R1.3 | always `-c` |
| Headless refusal (rc 103) | R1.3, K9 | always `--ignoreHeadlessMode`; 103/104 = ERROR rc 4 |
| Orphan nodes (rc 101) treated as a crash or ignored | R1.3, K4 | WARN `[test.orphans]` by default; policy in `[test] orphans` |
| Infinite loop in a test hangs the run | K8 | contract timeout (kind `test`); the hung test is named from the console |
| Runtime error in game code under test reported at the wrong file | K10 | location taken from the failure body, not the XML `message` |
| `push_error` from game code passes silently in gdUnit4 | K11 | log scan `godot.error`, downgraded to WARN (policy `[test] push_error`) |
| F11 noisy output (gdUnit4 prints ~180 lines for 50 tests) | R1.3 | <= 15 stdout lines; full log + XML/HTML report in the run dir |
| D1 C# | plan §2.1 | `--dotnet` stub only |

## 2. Interfaces

### 2.1 CLI

```
h test [TARGET ...] [--filter SUBSTR] [--changed] [--dotnet] [--project DIR] [--strict] [-h]
```
Common flags, project resolution, env vars: contract §2.2. Needs a project.

| TARGET form | Meaning |
|---|---|
| (none) | every suite under `[harness] test_dir` (default `res://tests`) |
| `res://dir/` or `res://x.gd` | a directory (recursive) or one suite file |
| a filesystem path (`tests/sim`, `/abs/proj/tests/x.gd`) | resolved against cwd (contract §2.1); must lie inside the project |
| `test_counter` (no `/`, no `.gd`) | suite by file stem, searched under `test_dir`; must match exactly one file |
| `<suite-form>::<test_name>` | one test function of one suite (all rows if parameterised) |

- Several TARGETs are unioned (deduplicated by suite path, then test name).
- `--filter SUBSTR`: within the selected suites keep only tests whose name contains SUBSTR (case-sensitive). Suites
  with no matching test are dropped.
- `--changed`: replaces TARGETs (both given -> rc 2). Selects (a) suite files under `test_dir` that `git status
  --porcelain --untracked-files=all` (run in the project dir) reports as modified, added, renamed or untracked, plus
  (b) for every such changed non-test `X.gd`, any suite named `test_X.gd` under `test_dir`. Not a git work tree -> rc 2.
  Nothing selected -> PASS rc 0, `selected: 0 suites (--changed: no changed tests)`, no Godot invocation. This is
  the one case where 0 tests is not a failure (it is the A8 Stop-hook path).
- `--dotnet`: rc 2, `ERROR test --dotnet is disabled in v0 (D1: GDScript only)`. No Godot run.
- Usage errors (rc 2, contract §2.3 line 1 `ERROR test <reason>`): target path does not exist (`no such test path:
  <t>`), path outside the project, suite stem unknown (`unknown suite '<s>'` + ` (did you mean '<y>'?)` at edit distance
  <= 2) or ambiguous (`suite '<s>' is ambiguous: <p1>, <p2>`), `::` after a directory, unknown test name in a suite
  (`no test '<n>' in <res path>` + did-you-mean), file that is not a `.gd`.

### 2.2 Stdout (contract §2.3, plus a stricter A4 cap)

`h test` prints **at most 15 lines** (verb-local cap, R-02; the contract's 40-line limit still applies and is checked
by `assert_contract`): verdict, up to **5** stat lines (`project`, `import`, `gdunit4`, `tests`, `selected`), finding
lines (contract order: errors, then warnings, then info) up to **8**, or **7** when the `selected:` stat is shown, the
truncation line if needed, the log line (1 + 5 + 7 + 1 + 1 = 15). All findings go to `findings.jsonl`.

Verdict reasons (counts always shown in this order, zero parts omitted except `passed`):
`<f> failed, <e> errors, <o> orphan warnings, <p> passed of <n> tests (<t>s)`; when gdUnit4 never ran tests:
`tests not run: <why> (<t>s)`.

Stat lines, in this order: `project:`, `import:` (contract §2.8.7), `gdunit4:` (`v6.2.2 ` + the string returned by
`sync.install_gdunit4`, i.e. `present` | `installed (was missing)`; on rc != 0 from gdUnit4 append `, rc <N>`), `tests:` (`<n> total, <p> passed, <f> failed, <e> errors,
<s> skipped, <o> orphans` | `not run`), and `selected:` (`<k> suites, <m> tests (<targets or test_dir>)`) only when
TARGETs/`--filter`/`--changed` were given.

```
$ tools/harness/h test --project /tmp/h/gd_tests
FAIL test 2 failed, 1 error, 58 passed of 61 tests (2.4s)
project: /tmp/h/gd_tests
import: fresh
gdunit4: v6.2.2 present, rc 100
tests: 61 total, 58 passed, 2 failed, 1 error, 0 skipped, 0 orphans
res://scripts/buggy.gd:6: [test.error] error: test_buggy::test_runs: Godot Runtime Error ! 'Cannot call method 'call' on a null value.'
res://tests/test_math.gd:6: [test.failed] error: test_math::test_bad: Expecting: 3 but was 2
res://tests/test_math.gd:8: [test.failed] error: test_math::test_bad_str: Expecting: 'hello world' but was 'hello <LF>world'
log: /tmp/h/gd_tests/.harness/out/20261015T150102Z-test-4c1e/

$ tools/harness/h test test_counter::test_add --project /tmp/h/gd_tests
PASS test 1 passed of 1 tests (1.6s)
project: /tmp/h/gd_tests
import: ran (no .godot/)
gdunit4: v6.2.2 installed (was missing)
tests: 1 total, 1 passed, 0 failed, 0 errors, 0 skipped, 0 orphans
selected: 1 suites, 1 tests (test_counter::test_add)
log: /tmp/h/gd_tests/.harness/out/20261015T150210Z-test-9a07/

$ tools/harness/h test --project /tmp/h/broken
FAIL test tests not run: script errors in test discovery (1.5s)
project: /tmp/h/broken
import: fresh
gdunit4: v6.2.2 present, rc 105
tests: not run
res://tests/test_broken.gd:3: [godot.parse-error] error: Expected expression after "+" operator.
res://tests/test_broken.gd: [godot.script-load-failed] error: Failed to load script "res://tests/test_broken.gd" with error "Parse error".
log: /tmp/h/broken/.harness/out/20261015T150300Z-test-11aa/
```

### 2.3 Rule ids (prefix `test.`, contract §2.7) and the findings they produce

| Rule | Severity | Location | Message |
|---|---|---|---|
| `test.failed` | error | §3.4 location rule | `<suite>::<test>[:<row>]: <collapsed failure text>` |
| `test.error` | error | §3.4 location rule | same, for XML `<error>` (runtime error, type ABORT) |
| `test.orphans` | warning (policy) | `res://<suite>.gd:<line of func>` | `<suite>::<test>: <N> possible orphan node(s)` hint `free() nodes you create or wrap them in auto_free()` |
| `test.no-tests` | error | `-` or the target | `no tests selected` / `gdUnit4 ran 0 tests` (hint names the targets). Always an error, so the 0-test FAIL keeps the contract §2.3 invariant; the only 0-test PASS is `--changed` with nothing selected (§2.1), which emits no finding (PASS = no error/warning, contract §2.4) |
| `test.report-missing` | error | `-` | `gdUnit4 exited <rc> but wrote no results.xml` |
| `harness.hang` | error | `res://<suite>.gd:<line of func>` of the last `STARTED` test without an end line, else `-` | contract §2.8.3 message + ` in test '<suite>::<test>'` |
| `harness.rc` | error | `-` | `gdUnit4 exited <rc>` + hint for rc 1: `GdUnitCmdTool failed to load (see log; try h import, h sync)` |
| `godot.*` scan rules | contract §2.8.4 | contract | contract; policy in §2.5 |

### 2.4 Exit-code map (gdUnit4 rc -> verdict; merged with the scan per contract §2.8.6)

| gdUnit4 rc | Meaning [Src v6.2.2 GdUnitTestSessionRunner.gd:19-24] | Verb result |
|---|---|---|
| 0 | all passed | PASS, unless 0 tests ran -> FAIL `[test.no-tests]`; scan findings still count |
| 100 | failures or errors | FAIL; findings from `results.xml`; none parsed -> `[test.report-missing]` |
| 101 | orphans only | `[test.orphans]` per test, severity per `[test] orphans` (default WARN rc 5) |
| 103 | headless refused | ERROR rc 4 `gdUnit4 refused headless mode` (cannot happen with our flags) |
| 104 | Godot version unsupported | ERROR rc 4 `gdUnit4 does not support this Godot version` |
| 105 | script errors during discovery | FAIL, `tests: not run`; findings come from the protected scan rules |
| 1 | CmdTool did not load (engine rc) | FAIL `[harness.rc]` + scan findings |
| 124 / >= 128 | hang / crash | FAIL `[harness.hang]` / `[harness.crash]` (contract §2.8.3) |
| other | | FAIL `[harness.rc]` |
Expected rc set for kind `test` (contract §2.8.6): {0, 100, 101, 105}; 103/104 are handled before the merge.

### 2.5 Config: `[test]` table in `harness.toml` (contract §2.6; `CONFIG_TABLE = "test"`)

```toml
[test]
orphans = "warn"       # warn | fail | ignore   -> severity of test.orphans (ignore = info)
push_error = "warn"    # warn | fail            -> severity of godot.error / godot.warning findings in h test
```
Test root comes from `[harness] test_dir` (contract §2.6), timeout from `[timeouts] test` (default 300 s). Scan
downgrade policy declared here (contract §2.8.4): in `h test` only, non-protected `godot.error` becomes `warning`
when `push_error = "warn"`; `godot.warning` stays warning; protected rules are never touched. `--strict` turns every
WARN into FAIL (contract §2.2).

### 2.6 Run-dir artefacts (contract §2.5; `artifacts/` is verb-owned)

- `artifacts/gdunit/results.xml` and `artifacts/gdunit/index.html` (+ its asset dirs): gdUnit4's report, moved out of
  the project after the run. Absent when gdUnit4 wrote none (rc 105, hang, rc 1).
- `artifacts/tests.json`:
```json
{"type":"object","required":["schema","gdunit_rc","selected","tests"],
 "properties":{"schema":{"const":"harness.tests/1"},"gdunit_rc":{"type":["integer","null"]},
  "selected":{"type":"object","required":["suites","targets","filter","changed"],
   "properties":{"suites":{"type":"array","items":{"type":"string"}},"targets":{"type":"array","items":{"type":"string"}},
    "filter":{"type":["string","null"]},"changed":{"type":"boolean"}}},
  "tests":{"type":"array","items":{"type":"object","required":["suite","name","status","duration_s","path","line","message"],
   "properties":{"suite":{"type":"string","pattern":"^res://.*\\.gd$"},"name":{"type":"string"},
    "status":{"enum":["passed","failed","error","skipped","orphans","hung"]},"duration_s":{"type":"number"},
    "path":{"type":["string","null"]},"line":{"type":["integer","null"]},"message":{"type":["string","null"]}}}}}}
```
- `run.json` `extra`: `{"gdunit_rc": int|null, "total": int, "passed": int, "failed": int, "errors": int,
  "skipped": int, "orphans": int, "suites": int}`.
- The Godot invocation has `kind: "test"`; its `argv` contains `-s res://addons/gdUnit4/bin/GdUnitCmdTool.gd
  --ignoreHeadlessMode -c -rd res://.harness/gdunit/<run-id>` followed by the `-a`/`-i` arguments.

### 2.7 Test layout convention (what projects, the sample and the A8 `godot-test` skill follow)

- Tests live in `res://tests/`, mirroring the source tree: `tests/sim/test_<module>.gd` for node-free simulation code,
  `tests/scenes/test_<scene>.gd` for scene tests. File stem `test_*`, `extends GdUnitTestSuite`, test functions
  `func test_<what>() -> void:`. gdUnit4 discovers any script extending `GdUnitTestSuite` and methods starting `test_`.
- Sim test (pure `RefCounted`, no tree, fastest; the default for game rules, R1.6):
```gdscript
extends GdUnitTestSuite
func test_add_accumulates() -> void:
	var c := Counter.new()
	c.add(2)
	assert_int(c.add(3)).is_equal(5)
func test_add_table(a: int, b: int, expected: int, test_parameters := [[1, 2, 3], [2, 2, 4]]) -> void:
	assert_int(Counter.new().add(a) + b).is_equal(expected)
```
- Scene test (`scene_runner` + input actions + frame stepping; works under `--headless` [Run K12]):
```gdscript
extends GdUnitTestSuite
func test_jump_counts_once() -> void:
	var runner := scene_runner("res://scenes/jumper.tscn")
	runner.simulate_action_press("jump")
	await runner.simulate_frames(2)
	runner.simulate_action_release("jump")
	await runner.simulate_frames(2)
	assert_int(runner.get_property("jumps")).is_equal(1)
```
- Rules for the skill: one behaviour per test; use input *actions* (not raw key/mouse events: InputEvents are not
  transported headless, gdUnit4 warning text); create nodes with `auto_free(...)` or free them (orphan policy);
  expect errors with `assert_error`/`assert_failure` instead of letting `push_error` leak; no `await get_tree()
  .create_timer()` waits in sim tests; autoloads are available in tests [Run K13].
- Orphan policy: orphans are a WARN (rc 5) by default because they are usually test hygiene, not game bugs; projects
  that want them fatal set `[test] orphans = "fail"`; the sample sets nothing (default).

## 3. Design

### 3.1 Files (A4 builder)
- `tools/harness/harness/verbs/test.py`: argparse, `CONFIG_TABLE`/`CONFIG_KEYS`, orchestration.
- `tools/harness/harness/gdunit.py`: target resolution, test-name listing, argv building, `results.xml` and console
  parsing, failure-text collapsing, rc map. **Public to unit tests (closed list, contract §2.12 / R-01): only
  `parse_results(xml_text: str) -> list[dict]` (keys suite, name, status, duration_s, path, line, message) and
  `parse_console(log_text: str) -> dict` (keys counts, hung, orphans, ansi-stripped lines).** Both are pure and
  stdlib-only; so `gdunit.py` imports no other `harness.*` module at top level (selection/argv helpers that need
  `project`/`godot` import them inside functions). Everything else in `gdunit.py` is private.
- No GDScript files; no runner (gdUnit4's CmdTool is the runner). No edits to A1 files: it calls
  `godot.ensure_imported`, `godot.run`, `out.Run`, `config.load`, and `sync.install_gdunit4` (R-33, §8 A-1).
- Port: `.claude/research/scripts/r1_3_testing/summarize_junit.py` (XML walk) into `gdunit.parse_results`.

### 3.2 Flow of `h test`
1. Parse args; `--dotnet` -> rc 2. Resolve project and config (contract).
2. `sync.install_gdunit4(run, project) -> str` (A1, R-33); A4 does not inspect the addon itself. Behaviour A4 relies
   on: addon missing -> copy `$HARNESS_CACHE/gdunit4` minus `test/` and `*.uid` (K17), returns `installed (was
   missing)`; `plugin.cfg` version equals the pin -> `present`; another version -> overwritten only if
   `.sync.json.gdunit4_commit` is non-null (harness-installed), else rc 4 `gdUnit4 <v> in project, harness pins 6.2.2
   (run h sync)` (a user's own copy is never overwritten); cache missing -> rc 4 `gdUnit4 not found in <cache> (run
   tools/bootstrap.sh)`. A4 does not call `ensure_synced` (gdUnit4 tests need no harness autoloads; projects that
   declare them use `h sync`, R-39).
3. Resolve the selection (§3.3) without Godot. Usage problems -> rc 2. Empty -> FAIL `[test.no-tests]`
   (`--changed` exception, §2.1). No Godot run in either case.
4. `godot.ensure_imported` (contract §2.8.7).
5. `godot.run(kind="test", args=[-s res://addons/gdUnit4/bin/GdUnitCmdTool.gd, --ignoreHeadlessMode, -c, -rd
   res://.harness/gdunit/<run-id>, -a <suite>..., -i <suite>:<test>...])`. Absolute `-rd` paths are rewritten by
   gdUnit4 to `res://` (K2), so the report dir must be a `res://` path; `.harness/` is hidden, so never imported.
6. Move `res://.harness/gdunit/<run-id>/report_1/*` to `artifacts/gdunit/`, delete the temp dir (also on failure).
7. Parse (§3.4), apply the rc map (§2.4), policies (§2.5), dedup (§3.4) over `inv.findings` (the returned
   `Invocation` does not add them, R-31) plus the XML findings, `run.add_findings(...)`, write `tests.json`, finish.

### 3.3 Selection algorithm
- Suite discovery for names/dirs: walk the dir for `*.gd` whose text has a line matching `^extends\s+GdUnitTestSuite\b`
  (or `^extends\s+"res://addons/gdUnit4/src/GdUnitTestSuite.gd"`); skip `.godot/`, `.harness/`, `addons/`.
- Test names of a suite: `^func\s+(test_\w+)\s*\(` (1-based line kept for locations).
- `-a` gets each selected suite as a `res://` file path (never a dir, never a non-existent path: K3 shows gdUnit4
  exits 0 on those). Whole suites need no `-i`.
- Single test / `--filter`: `-a <suite>` plus `-i <res path>:<other test>` for every other test of that suite. Use
  the full `res://` path (gdUnit4 strips `res://` and matches `source_file.contains(...)`, so bare stems such as
  `test_a` would also hit `test_ab.gd`) [Src GdUnitTestCIRunner.gd `is_skipped`]. 50 `-i` args work [S4 Run].
- A parameterised test is one name; `-i` on it removes all rows; selecting it runs all rows (K1).

### 3.4 Parsing
- ANSI stripping for console lines: `\x1b\[[0-9;]*[A-Za-z]` (gdUnit4 colours its own lines; engine lines are plain, K14).
- `results.xml`: for each `<testsuite package=P name=N>` the suite is `res://P/N.gd` (K15); each `<testcase>` is passed,
  `<failure>` -> `test.failed`, `<error>` -> `test.error`, `<skipped>` -> skipped. Parameterised rows appear as
  `name:<row>` [U on exact XML name; take it verbatim].
- **Location rule** for failed/error: the last `at '<fn>' in (res://[^:\s]+):(\d+)` in the CDATA body; else the
  `res://F:L` in the `message` attribute; else the suite path + the test's func line. The body wins because for a
  runtime error in game code the `message` names the test file with the game file's line number (K10).
- **Collapsed text**: CDATA lines, minus lines matching `^\s*at '.*' in res://`, stripped, joined with one space,
  whitespace runs collapsed; the finding line is cut to 240 chars per contract.
- Console (`godot/01-test.log`, ANSI-stripped): `Overall Summary: <n> test cases | <e> errors | <f> failures | ... |
  <o> orphans` (sum of `Statistics:` lines when absent) gives counts used when XML is missing and as a cross-check
  (mismatch -> keep XML, add an `info` finding `[test.count-mismatch]`); `^\s*(res://\S+) > (\S+) STARTED` /
  `... (PASSED|FAILED|ERROR|SKIPPED)` pairs find the hung test; `WARNING: Detected (\d+) possible orphan nodes`
  following a test's end line attributes orphans to that test (XML has no orphan data, K4).
- Log scan: `logscan.scan` on the whole log (contract §2.8.4) with the §2.5 policy. Dedup: drop a scan finding whose
  (path, line) equals the location of a `test.failed`/`test.error` finding (gdUnit4 already reported it, K10/K11).
  `godot.leak` at exit stays `info`.

### 3.5 Timeouts and budgets
Kind `test` default 300 s (contract table). Budgets [Run K1, K16]: harness overhead <= 0.5 s over the raw gdUnit4
run; 50 trivial tests <= 5 s wall warm (measured 1.8 s raw); a one-suite run <= 3 s warm; first run on a fresh copy
adds the import (5-7 s with gdUnit4 in the project).

### 3.6 Why these choices
- Pre-resolving targets in Python is the only way to make a typo fail loudly (gdUnit4 exits 0, K3). Grep-listing
  test names costs ~1 ms per file and avoids a second Godot run for discovery.
- XML over console as the primary source: stable structure, full failure text; console only for what XML lacks
  (orphans, hang, counts when no report).
- `push_error` = WARN not FAIL: tests of error paths legitimately trigger it, and gdUnit4 offers `assert_error` for
  the strict form; script errors (protected) always FAIL.
- Auto-install of gdUnit4 mirrors auto-import: a fixture or fresh clone never carries `addons/gdUnit4/` (contract
  §2.11), and `h test` must work there without a manual step (plan AC "fresh copy works").

### 3.7 Spikes ([Run], scratchpad `a4/`, Godot 4.7.stable.official.5b4e0cb0f, gdUnit4 v6.2.2 copied into the project,
plugin not enabled; command: `timeout -k 3 60 godot --headless --path P -s res://addons/gdUnit4/bin/GdUnitCmdTool.gd
--ignoreHeadlessMode -c -rd <rd> <args>`)
- K1 pass: `-a res://tests/test_sim.gd` (2 tests + 1 parameterised with 2 rows) -> `Statistics: 4 test cases | 0 errors
  | 0 failures | 0 flaky | 0 skipped | 0 orphans | PASSED`, rc 0, 1.5 s. Rows print as `test_params:0 (1, 2, 3)`.
  `-a res://tests/test_many.gd` (50 tests) -> rc 0, 1.78 s wall, 180 log lines.
- K2 `-rd /abs/out` wrote to `<project>/abs/out/...` (`make_qualified_path`: `/x` -> `res://x`); `-rd res://.harness/gd/x`
  -> `.harness/gd/x/report_1/{results.xml,index.html}`.
- K3 `-a res://tests/nope.gd` -> `Given directory or file does not exists: res://tests/nope.gd`, `No test cases found,
  abort test run!`, `Exit code: 0`, rc 0, no report dir.
- K4 orphan (`var n := Node.new()` never freed) -> test `PASSED`, then `  Report:` / `  WARNING: Detected 1 possible
  orphan nodes.` (indented, so `^WARNING:` scan rules do not match), rc 101; XML has no orphan info; at exit
  `WARNING: 1 ObjectDB instance was leaked at exit` (-> `godot.leak` info).
- K5 parse error in `tests/test_parse.gd:3` with `-a res://tests` -> `SCRIPT ERROR: Parse Error: Expected expression after
  "+" operator.` / `at: GDScript::reload (res://tests/test_parse.gd:3)`, `Script errors were detected during test
  discovery!`, `Abnormal exit with 105`, rc 105, no report written, no test of any suite ran.
- K6 fresh copy without `.godot/` -> `SCRIPT ERROR: Parse Error: Could not find type "GdUnitTestCIRunner"` at
  `res://addons/gdUnit4/bin/GdUnitCmdTool.gd:5`, rc 1, 0.19 s.
- K7 imported project, then new `sim/dice.gd` (`class_name Dice`) + a test using it, no re-import -> `Identifier "Dice"
  not declared in the current scope` at `res://tests/test_dice.gd:3`, rc 105.
- K8 `while true: i += 1` in a test, `timeout 8` -> rc 124 at 8.0 s; last log line `res://tests/test_loop.gd >
  test_forever STARTED`.
- K9 without `--ignoreHeadlessMode` -> rc 103.
- K10 scene under `scene_runner` whose `_physics_process` calls a method on null; test asserts only `true` -> test
  FAILED, rc 100; XML `<error message="ERROR: res://tests/test_buggy.gd:6" type="ABORT">` but body `at
  '_physics_process' in res://scenes/buggy.gd:6` (the test file has 5 lines: `message` mixes file and line).
- K11 test calling `o.call("foo")` on null -> `<error type="ABORT">` body `Godot Runtime Error ! 'Cannot call method
  'call' on a null value.' at 'test_null_call' in res://tests/test_errnoassert.gd:4`; log also has `SCRIPT ERROR: ...`
  at the same loc. Test calling only `push_error("boom from test")` -> test PASSED (no XML failure), log `ERROR: boom
  from test` with backtrace `[0] test_push_error (res://tests/test_errnoassert.gd:6)`.
- K12 `scene_runner` + `simulate_action_press("jump")` + `simulate_frames(2)` on a generated scene: PASSED headless.
- K13 an autoload declared in `project.godot` is reachable by name from a test under `-s CmdTool`: PASSED.
- K14 raw log: gdUnit4 lines carry 24-bit ANSI colour codes (`\x1b[38;2;...m`); engine `SCRIPT ERROR:`/`ERROR:`/
  `WARNING:` lines start at column 0 without codes. A clean run has no `^(ERROR|WARNING|SCRIPT ERROR):` line.
- K15 XML: `<testsuite name="test_fail" package="tests/sim">` for `res://tests/sim/test_fail.gd`; two suites with the
  same stem in different dirs are distinguished only by `package`. Failure: `<failure message="FAILED:
  res://tests/test_fail.gd:6" type="FAILURE">` + CDATA `Expecting:\n 3\n but was\n 2\n\tat 'test_bad' in
  res://tests/test_fail.gd:6`.
- K16 `-a suite -i res://tests/test_sim.gd:test_add_twice -i res://tests/test_sim.gd:test_params` -> only `test_add`
  ran (`Statistics: 1 test cases`); both parameterised rows were excluded.
- K17 import time with the full addon 5.8 s vs 5.3 s without `addons/gdUnit4/test/` (561 of 1078 files); enabling the
  editor plugin in `project.godot` changes nothing for CLI runs (rc 0, same output); `project.godot` was not modified
  by test runs.

## 4. Acceptance criteria (T4 writes these under `tests/{unit,contract}/a4/`; all contract tests copy fixtures to
`$HARNESS_TMP` first (B3) and call `assert_contract` on every result)

- AC-04.1 Fresh copy of `gd_tests` (no `.godot/`, no `addons/gdUnit4/`), `h test --project <copy>` -> rc 0, `PASS
  test`, stats `import: ran`, `gdunit4: v6.2.2 installed (was missing)`, `tests: <N> total, <N> passed` with N = the
  fixture's documented count. A second run -> `import: fresh`, `gdunit4: v6.2.2 present`. [contract]
- AC-04.2 Failing assert (FAULT-A4-01 setup): rc 1; a line matching `^res://tests/test_math\.gd:6: \[test\.failed\]
  error: test_math::test_bad: Expecting: 3 but was 2$`; the whole failure is on that one line. [contract]
- AC-04.3 Runtime error in game code called from a test (FAULT-A4-05 setup): rc 1; finding `^res://scripts/buggy\.gd:6:
  \[test\.error\] error: `; no other finding line has loc `res://scripts/buggy.gd:6` (dedup). [contract]
- AC-04.4 Parse error in a test file (FAULT-A4-02 setup): rc 1, `gdunit4: v6.2.2 present, rc 105`, `tests: not run`,
  finding `^res://tests/test_broken\.gd:3: \[godot\.parse-error\]`; verdict reason starts `tests not run`. [contract]
- AC-04.5 Orphans (FAULT-A4-03 setup): rc 5, `WARN test`, finding `^res://tests/test_leak\.gd:\d+: \[test\.orphans\]
  warning: test_leak::test_leaks_node: 1 possible orphan`; with `--strict` rc 1; with `[test] orphans = "fail"` rc 1
  and severity `error`; with `orphans = "ignore"` rc 0. [contract]
- AC-04.6 Hang (FAULT-A4-04 setup, `[timeouts] test = 10`): rc 1, finding `^res://tests/test_hang\.gd:2: \[harness\.hang\]`
  naming `test_hang::test_forever`; run.json invocation `timed_out: true`, `rc: 124`; wall <= 20 s; no surviving
  process whose cmdline contains the copy path. [contract]
- AC-04.7 `push_error` only (FAULT-A4-06 setup): rc 5, finding `^res://scripts/noisy\.gd:\d+: \[godot\.error\] warning:
  `; with `[test] push_error = "fail"` rc 1 and severity `error`. [contract]
- AC-04.8 Selection on `gd_tests` (counts from the fixture's FIXTURE.md): `h test res://tests/sim/test_counter.gd`,
  `h test tests/sim/test_counter.gd` (cwd = copy), `h test test_counter` give the same `tests:` total = that suite's
  test count and stat `selected: 1 suites`; `h test test_counter::test_add` -> `tests: 1 total`; `h test
  test_counter::test_table` -> total = its row count; `h test --filter add` -> total = number of tests whose name
  contains `add`; two targets -> the sum. [contract]
- AC-04.9 Bad targets, each rc 2 with no Godot invocation in run.json: `res://tests/nope.gd` (`no such test path`),
  `test_countr` (`unknown suite 'test_countr' (did you mean 'test_counter'?)`), `test_counter::test_ad` (`no test
  'test_ad'`), `/tmp` (outside the project), `res://tests/sim::test_add` (`::` after a dir), `--changed` together with a
  TARGET. [contract]
- AC-04.10 Zero tests: `--filter zzz` -> rc 1 `[test.no-tests]`, run.json `invocations` empty; a copy whose `tests/`
  holds only a suite with no `test_` function -> rc 1 `[test.no-tests]`; a copy without `tests/` -> rc 1. [contract]
- AC-04.11 gdUnit4 problems: `addons/gdUnit4/plugin.cfg` with `version="6.1.0"` and no `.sync.json` -> rc 4 `ERROR test gdUnit4
  6.1.0`, the file is not overwritten (user copy, R-33); `HARNESS_CACHE=<empty dir>` on a copy without the addon -> rc 4 `gdUnit4 not found`. [contract]
- AC-04.12 Performance: on a warm copy (imported, addon present), `h test res://tests/perf/test_many.gd` (50 trivial
  tests) -> rc 0, `tests: 50 total`, wall <= 5 s; `h test test_counter` wall <= 3 s. [contract, godot]
- AC-04.13 Output cap: FAULT-A4-08 setup (30 failing tests, target given so `selected:` is shown) -> rc 1, exactly 5
  stat lines, <= 15 stdout lines, 7 finding lines, truncation line `... 23 more findings (23 errors, 0 warnings) in
  findings.jsonl`; `findings.jsonl` has 30 `test.failed`. Same setup run with no TARGET (whole `test_dir`, other
  suites pass) -> 4 stat lines, 8 finding lines, `... 22 more findings`. [contract]
- AC-04.14 Artefacts: after AC-04.2's run, `artifacts/gdunit/results.xml` and `artifacts/gdunit/index.html` exist in the
  run dir; `artifacts/tests.json` validates against §2.6 and lists every test with `status`; the copy has no
  `.harness/gdunit/` dir and no `reports/` dir; `project.godot` is byte-identical before and after. [contract]
- AC-04.15 run.json: the invocation has `kind: "test"`, `timeout_s: 300` (default scale), argv contains
  `--ignoreHeadlessMode`, `-c`, `-rd`, `res://addons/gdUnit4/bin/GdUnitCmdTool.gd`; `extra` has the §2.6 keys with
  counts equal to the `tests:` stat. [contract]
- AC-04.16 `--changed` (test makes the copy a git repo and commits it): no change -> rc 0, `selected: 0 suites`,
  `invocations` empty, wall <= 1 s; touching `sim/counter.gd` -> runs exactly `res://tests/sim/test_counter.gd`; a new
  untracked suite file -> runs it; a copy that is not a git work tree -> rc 2. [contract]
- AC-04.17 `h test --dotnet` -> rc 2, line 1 `^ERROR test --dotnet is disabled in v0 \(D1`. [contract]
- AC-04.18 Stale class cache: on a warm copy, add `sim/dice.gd` (`class_name Dice`) and `tests/sim/test_dice.gd` using it,
  run `h test test_dice` -> rc 0, `import: ran (stale class cache (` (new class not in the cache, contract §2.8.7 / R-24). [contract]
- AC-04.19 Parser units on recorded inputs (§6 `tests/fixtures/gdunit/`): `gdunit.parse_results(xml)` gives the
  expected (suite, name, status, path, line, message) tuples for `fail.xml`, `runtime_error.xml` (location from the body:
  `res://scenes/buggy.gd:6`), `nested.xml` (`package` -> `res://tests/sim/test_fail.gd`); `gdunit.parse_console(log)`
  finds the hung test in `hang.log`, orphan counts in `orphan.log`, summary counts in `all.log`, and strips ANSI. [unit]
- AC-04.20 `h selftest --area A4` -> rc 0, all FAULT-A4 entries CAUGHT, both CLEAN-A4 entries PASS, wall <= 180 s. [contract, slow]
- AC-04.21 `h test --help` <= 40 lines, rc 0; `h test --bogus` -> rc 2 (contract AC-00.3/4 also cover this). [contract]
Untestable automatically: none.

## 5. Seeded faults (fixture `gd_tests` unless noted; verb `test`; all `must` unless noted)

| ID | Planted (apply ops) | Args | Expect |
|---|---|---|---|
| FAULT-A4-01 | write `tests/test_math.gd`: suite with `test_ok` (passes) and `test_bad` whose line 6 is `assert_int(x).is_equal(3)` with `x := 2` (and `test_bad_str` line 8 as in K15) | `["test_math"]` | rc 1 FAIL, `^res://tests/test_math\.gd:6: \[test\.failed\] error: test_math::test_bad: Expecting: 3 but was 2`, <= 60 s |
| FAULT-A4-02 | write `tests/test_broken.gd` with `var a := 1 +` on line 3 | `[]` | rc 1 FAIL, `gdunit4: .*rc 105`, `^res://tests/test_broken\.gd:3: \[godot\.parse-error\]`, <= 60 s |
| FAULT-A4-03 | write `tests/test_leak.gd`: `test_leaks_node` does `var n := Node.new()` and asserts it is not null | `["test_leak"]` | rc 5 WARN, `\[test\.orphans\] warning: test_leak::test_leaks_node`, <= 60 s |
| FAULT-A4-04 | write `tests/test_hang.gd` (`func test_forever() -> void:` on line 2, `while true:` loop), `harness.toml` `[timeouts]\ntest = 10\n` | `["test_hang"]` | rc 1 FAIL, `^res://tests/test_hang\.gd:2: \[harness\.hang\].*test_forever`, <= 45 s |
| FAULT-A4-05 | write `scripts/buggy.gd` (Node2D; line 6 calls a method on a null `Object` in `_physics_process`), `scenes/buggy.tscn` (root Node2D with it), `tests/test_buggy.gd` (scene_runner, `simulate_frames(3)`, asserts only `true`) | `["test_buggy"]` | rc 1 FAIL, `^res://scripts/buggy\.gd:6: \[test\.error\]`, not_regex `^res://tests/test_buggy\.gd:6:`, <= 60 s |
| FAULT-A4-06 | write `scripts/noisy.gd` (`class_name Noisy`, `func run() -> int:` that `push_error("noisy")` and returns 1), `tests/test_noisy.gd` asserting `Noisy.new().run() == 1` | `["test_noisy"]` | rc 5 WARN, `^res://scripts/noisy\.gd:\d+: \[godot\.error\] warning: noisy`, <= 60 s |
| FAULT-A4-07 | none | `["res://tests/sim/test_countr.gd"]` | rc 2 ERROR, `no such test path`, <= 10 s |
| FAULT-A4-08 | write `tests/test_many_fail.gd` with 30 tests `test_f00`..`test_f29`, each `assert_int(0).is_equal(1)` | `["test_many_fail"]` | rc 1 FAIL, `^\.\.\. 23 more findings`, <= 60 s (contract caps lines at 40; A4's 15-line cap is checked by AC-04.13) |
| FAULT-A4-09 | write `tests/test_empty.gd` (`extends GdUnitTestSuite`, a helper `func make() -> int:` only) | `["test_empty"]` | rc 1 FAIL, `\[test\.no-tests\]`, <= 10 s |
| FAULT-A4-10 | write `addons/gdUnit4/plugin.cfg` with `version="6.1.0"` | `[]` | rc 4 ERROR, `gdUnit4 6\.1\.0`, <= 10 s |
| FAULT-A4-11 | replace in `tests/sim/test_counter.gd` the `is_equal(5)` of `test_add_twice` with `is_equal(6)` | `["--filter", "add_twice"]` | rc 1 FAIL, `\[test\.failed\] error: test_counter::test_add_twice`, `^selected: 1 suites, 1 tests`, <= 60 s |
| CLEAN-A4-01 | none | `[]` | rc 0 PASS, `^import: ran`, `^gdunit4: v6\.2\.2 installed`, `^tests: \d+ total, \d+ passed, 0 failed, 0 errors` |
| CLEAN-A4-02 | none | `["test_counter::test_add"]` | rc 0 PASS, `^tests: 1 total, 1 passed` |

Fault `files/` hold the exact test/script/scene texts; `.tscn` files follow r1_4 §3 (no `uid=` needed).

## 6. Fixtures needed (T4)
- `tests/fixtures/projects/gd_tests/` (contract §2.11 minimum + `FIXTURE.md` stating suite and test counts):
  `project.godot` with an InputMap action `jump` (no events) and no `[editor_plugins]`; `sim/counter.gd` (`class_name
  Counter extends RefCounted`, `add(k: int) -> int`); `scenes/jumper.gd` (counts `is_action_just_pressed("jump")` in
  `_physics_process`) and `scenes/jumper.tscn` (root Node2D with that script, hand-written per r1_4 §3);
  `tests/sim/test_counter.gd` (`test_add`, `test_add_twice`, `test_table` parameterised with 2 rows: §2.7 example);
  `tests/scenes/test_jumper.gd` (§2.7 example); `tests/perf/test_many.gd` (50 tests `test_t00`..`test_t49`, each one
  `assert_int(i).is_equal(i)`). Expected `h test`: PASS, 55 tests (4 counter cases, since gdUnit4 counts each
  parameter row (K1), + 1 jumper + 50 perf); T4 confirms the count by a run and records it in FIXTURE.md.
- `tests/fixtures/gdunit/` (recorded, for AC-04.19): `fail.xml`, `runtime_error.xml`, `nested.xml`, `hang.log`,
  `orphan.log`, `all.log`; produce them by running gdUnit4 on throwaway copies (§3.7 commands), keep ANSI codes in logs.
- `selftest/faults/FAULT-A4-01..11/`, `selftest/clean/CLEAN-A4-01..02/` per §5 and contract §2.10.
- `tests/fixtures/projects/gd_host` and `tests/helpers/gd.py` are T1's (R-39, contract §2.12), not A4's; the `[gd]`
  layer runs them through `h test --project <copy> res://tests/<area>/` like any project.

## 7. Build order (A4 builder; after A1's step 0 and A1's `sync`)
1. `verbs/test.py` skeleton: args, `--dotnet`, `[test]` config keys, gdUnit4 presence/version/auto-install -> AC-04.11,
   17, 21.
2. `gdunit.py` selection (suite discovery, names, `::`, `--filter`, did-you-mean, path rules) with no Godot -> AC-04.9,
   10 (selection part).
3. Godot invocation + report move + `parse_results` + location rule + collapse -> AC-04.1, 2, 3, 8, 14, 15, 19 (xml).
4. rc map, `parse_console` (orphans, hang, counts), scan policy and dedup -> AC-04.4, 5, 6, 7, 10, 18, 19.
5. Output cap (15 lines), `tests.json`, `--changed` -> AC-04.12, 13, 16.
6. `h selftest --area A4` green -> AC-04.20; then `tools/dev/ci.sh --quick`.

## 8. Out of scope, open questions, assumptions

Out of scope (v0): C# (`--dotnet` stub, D1); GUT; coverage; parallel/sharded runs; flaky-test retries; printing the
HTML report; running tests under Xvfb for UI tests that need real InputEvents (actions work headless; a later
`--display xvfb` flag would reuse contract §2.8.2) [deferred]; `-conf` runner config files.

Deviations from the contract (status per REVIEW.md v1):
- D-1 **Accepted (R-01)**, now in contract §2.12: unit tests may import `harness.gdunit` (`parse_results`,
  `parse_console` only, §3.1). Reason: XML/console edge cases (collapsing, K10 location rule, ANSI) are cheap and
  precise to test on recorded inputs and slow to stage through Godot.
- D-2 **Accepted (R-02)** as a verb-local cap: stdout <= 15 lines with up to 5 stat lines and 7-8 finding lines
  (§2.2); the contract's 40-line limit still applies. Plan AC "summary <= 15 lines".
- D-3 Not a deviation (REVIEW v1 raised no item): `h test --changed` with nothing selected is PASS with 0 tests and no
  finding (contract §2.4: PASS = no error/warning). Every other 0-test case is FAIL `[test.no-tests]` (error).
- Resolved assumptions: A-1 by R-33 (`sync.install_gdunit4`, overwrite policy, §3.2 step 2); A-2 by R-31/R-32 and
  REVIEW §4 (kind expected-rc override {0,100,101,105}; explicit `ensure_imported`; `Invocation` return).

Open questions [U]:
1. Exact XML `name` of parameterised rows (`test_params:0`?) and of `<skipped>` cases; take verbatim (AC-04.19 records).
2. Tests inherited from a base suite are not seen by the grep listing, so `::`/`--filter` cannot exclude them (they
   would also run). Rare; documented in the skill.
3. A test that hangs inside `await` (signal never emitted) may hit gdUnit4's own per-test timeout before ours; message
   format not recorded.
4. 104 (Godot version unsupported) not observed on 4.7; mapping is from source.

Assumptions on other areas:
- A-1 (A1, settled by R-33) `harness/sync.py` exposes `install_gdunit4(run, project) -> str` returning `present` |
  `installed (was missing)`; copies the cache addon minus `test/` and `*.uid` (K17), never enables the editor plugin
  (not needed, K17), overwrites a differing version only when `.sync.json.gdunit4_commit` is non-null, else rc 4;
  rc 4 if the cache is missing [U: cache-missing wording is A4's expectation, A1 owns it]. `h sync`
  (`sync_project(..., gdunit=True)`) uses the same function.
- A-2 (A1/P0, settled by R-31/R-32) `godot.run(kind="test")` accepts a non-runner `-s res://...` script, takes A4's
  expected rc set {0,100,101,105}, returns an `Invocation` without adding findings; `godot.ensure_imported` is called
  explicitly by A4 (step 4). Autoloads load under `-s` (K13; contract §8 open (1) closed).
- A-3 (A8) the Stop hook calls `h test --changed`; the `godot-test` skill uses §2.7 (layout, two examples, rules).
- A-4 (A9) the sample keeps tests in `sample/tests/{sim,scenes}/` and passes `h test` with 0 orphans.
- A-5 (A5) scenario replays are `h run`, not gdUnit4 tests; A4 does not run scenarios.
- Plan defaults D1 (GDScript only), D5 and B4 (gdUnit4 pinned to v6.2.2, commit in pins.toml) are taken as given.
