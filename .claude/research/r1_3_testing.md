# R1.3 Test frameworks for Godot 4.7: gdUnit4 vs GUT vs C# options

Env: Godot 4.7-stable (`4.7.stable.official.5b4e0cb0f`) and the 4.7 mono build, Linux, headless, no display. Work dirs: `/tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad/research/r1_3_work/`. Versions tested: gdUnit4 v6.2.2, GUT v9.7.1, gdUnit4.api 5.1.0-rc5 + test.adapter 3.1.1, Chickensoft GoDotTest (repo HEAD 4a77210), .NET SDK 8.0.426 (installed via dotnet-install.sh; it was reachable).

## Answer

- **Standardise on gdUnit4 (v6.2.x) for GDScript.** It is the only one of the two whose exit code can be trusted. A parse error in a test file gives exit 105 [Run]. GUT gives exit 0 and silently skips the broken file [Run]. gdUnit4 also has a scene runner with frame and input simulation, built-in mock/spy, parameterised tests, orphan reporting, and XML+HTML reports. Its 4.7 support is stated in the README table [Doc].
- **GUT 9.7.1 is the fallback.** It is also 4.7-ready (a `godot_4_7` branch) [Doc] and is slightly faster and quieter. It has `-gjunit_xml_file` and exit 1 on failure [Run]. Its dangerous gotchas are exit 0 when test scripts do not parse and exit 0 when class_names are un-imported [Run]. If used, the wrapper must scan the log for `SCRIPT ERROR|Parse Error|GUT ERROR` and fail on a match.
- **Both need `godot --headless --path . --import` once on a fresh clone** (ignored `.godot/`), or class_name globals are missing [Run]. gdUnit4 then fails with exit 1 and a parse error. GUT prints an error but **exits 0** [Run].
- **gdUnit4 CLI needs `--ignoreHeadlessMode`.** Otherwise it refuses to run with exit 103 [Run]. Do not use `addons/gdUnit4/runtest.sh` headless. It does not pass `--headless`, so it needs a display and fails with "X11 Display is not available" under no X [Run].
- **gdUnit4 exit codes are 0 pass, 100 failure, 101 orphans only, 103 headless refused, 105 script errors in discovery** [Src: v6.2.2:GdUnitTestSessionRunner.gd:19-24] [Run: 100, 101, 103, 105 observed]. The harness must treat 101 as a warning, not a crash.
- **gdUnit4 is fail-fast by default.** The first failing test aborts the run unless you pass `-c` [Doc: documentation/doc/_advanced_testing/cmd.md]. Always pass `-c` for agent runs so one run lists all failures.
- **C#: use `dotnet test` with gdUnit4Net** (`gdUnit4.api` + `gdUnit4.test.adapter`, VSTest, trx/html loggers). It worked on 4.7 mono [Run]. The NuGet release lines are only rc5 (README table says rc1-rc5 target Godot 4.3-4.5, and master `5.1.0-rc6`, which is unreleased on NuGet, targets 4.6-4.7.2) [Doc]. Despite that, rc5 discovered and ran tests against 4.7 [Run], so the README table is conservative, not a hard block. GoDotTest also works on 4.7 [Run] but has no machine-readable report.
- **Pure-logic C# can be tested engine-free with plain xunit + `dotnet test`**, if it only uses GodotSharp structs and `Mathf` (`Vector2`, `Mathf`, `Colors` worked [Run]). Anything touching native-backed types (`StringName`, `Node`, `Godot.Collections.*`) **crashes the test host** ("Test host process crashed") [Run]. Keep sim logic on plain structs or your own types.

## Comparison table

| | gdUnit4 v6.2.2 (GDScript) | GUT v9.7.1 | gdUnit4Net (C#) | Chickensoft GoDotTest | plain xunit on Godot-free lib |
|---|---|---|---|---|---|
| 4.7 compat | README: v6.2.x lists 4.5-4.7.1; master v7.0.0 lists 4.7, 4.7.1, 4.8.dev7 [Doc README.md]. Ran on 4.7.0 [Run] | README table: 9.7.1 (`godot_4_7` branch) = 4.7.x; main = 4.6.x [Doc README.md:27-28]. Ran on 4.7.0 [Run] | README: master = 4.6, 4.6.3, 4.7.1, 4.7.2; rc1-rc5 = 4.3-4.5 [Doc]. rc5 ran on 4.7.0 mono [Run] | Its own test project uses `Godot.NET.Sdk/4.7.2` [Src: GoDotTest HEAD:Chickensoft.GoDotTest.Tests/*.csproj]. 47/47 passed on 4.7 mono [Run] | .NET 8, GodotSharp 4.7.2 NuGet [Run] |
| Install | Copy `addons/gdUnit4`. Enable plugin in `project.godot` (editor_plugins). `--import` once | Copy `addons/gut`; `--import` once. Plugin enable not needed for CLI [Run] | csproj: `Godot.NET.Sdk/4.7.0`, `gdUnit4.api`, `gdUnit4.test.adapter`, `Microsoft.NET.Test.Sdk`. `GODOT_BIN` env var [Doc vstest-adapter.md] | NuGet `Chickensoft.GoDotTest`; main scene must call `GoTest.RunTests` on `--run-tests` [Doc README] | `dotnet new xunit` + GodotSharp package |
| Headless cmd | see recipe below | see recipe below | `GODOT_BIN=... dotnet test --logger "trx;LogFileName=r.trx"` | `godot --headless --path . --run-tests[=Suite[.Method]] --quit-on-finish` | `dotnet test` |
| Exit on failure | 100 (101 orphans only, 105 parse errors) [Run] | 1 [Run]. **0 on parse-broken test script** and **0 if class_names un-imported** [Run] | 1 [Run] | 1 [Run], with or without `--coverage` | non-zero (Failed! line) [Run] |
| Reports | JUnit-style XML (`reports/report_N/results.xml`) + HTML (index.html); no JSON [Run] | JUnit XML via `-gjunit_xml_file=res://dir/x.xml`; **the dir must already exist** or "Could not create export file" [Run] | trx, html, console loggers [Doc] | console text only [Run]. Coverage via coverlet [Doc] | trx / junit logger |
| Console noise | High: 2 lines per test (STARTED/PASSED) plus a banner, about 182 lines/6.4 KB for 50 trivial tests. Plus an unavoidable `ERROR: remote port number must be between 1 and 65535` from the recommended `--remote-debug tcp://127.0.0.1:0` [Run] | Medium: 1 line/test, ~80 lines/1.2 KB for 50 tests [Run] | Medium | Medium-high: 2 lines/test + Godot ERROR spam at exit | Low |
| Time, 50 trivial tests (wall) | 2.06 s total (313 ms test time; ~1.3-1.8 s is engine start) [Run] | 1.38 s total (0.41 s test time) [Run] | 3.9 s `dotnet test` for 3 tests, excluding a 22 s first build [Run] | 0.93 s for 47 tests after build [Run] | ~5 s with build |
| Scene runner / input sim / frames | `scene_runner(path)`, `simulate_frames(n, delta_ms)`, `simulate_action_press/release`, key/mouse/touch, `await_signal`, `simulate_until_signal` [Src: GdUnitSceneRunnerImpl.gd:110-454]. Action press and frame stepping passed under `--headless` [Run]. README of the CLI warns InputEvents are not transported in headless mode, and that warning is the reason for the `--ignoreHeadlessMode` gate [Run output] | `simulate(obj, times, delta)`, `wait_frames`, `wait_physics_frames`, `wait_process_frames`, `wait_for_signal`, `wait_until`, `InputSender` (action_down etc.) [Src: gut@v9.7.1:addons/gut/test.gd:644,2436-2567]. `InputSender` + `wait_frames` passed headless [Run]. `wait_frames` prints a deprecation notice in favour of `wait_physics_frames` [Run] | Scene runner API in C# [Doc]. [Unverified] for scene-runner tests (only logic tests run) | Test scene node passed to ctor; you drive frames yourself [Doc] | none |
| Mock / spy | `mock()`, `spy()`, `do_return`, `verify(obj, times)`, `verify_no_interactions` [Src: GdUnitTestSuite.gd:285-319]. `mock(RefCounted)` ran [Run] | `double`, `partial_double`, `stub(...).to_return`, `assert_called`, `double_scene/script/inner` [Src: test.gd:2643-2857]. `stub` + `assert_called` passed [Run] | Moq-style mocks in the API [Doc] [Unverified] | LightMock / LightMoq are NuGet packages used by its own tests [Src: tests csproj] | BYO (Moq, NSubstitute) |
| Parameterised | `test_parameters := [[...],...]` arg; each row is its own result [Run] | `use_parameters([[...]])`; reported as one test with row list, a failing row is not named separately [Run (passes only)] | `[TestCase]` / `[DataPoint]` [Doc] | none built in [Unverified] | `[Theory]` |
| Orphan detection | Per-test warning "Detected N possible orphan nodes" and **exit 101** [Run] | Per-test list with node ids; `assert_no_new_orphans`; **does not change the exit code** [Run] | [Unverified] | none seen | n/a |
| Errors as failures | `push_error` as failure is OFF by default; script errors ON by default [Src: GdUnitSettings.gd:137-138] | `failure_error_types = ["engine","gut","push_error"]` default; flag `-gfailure_error_types` [Src: gut_config.gd:57] | n/a | n/a | n/a |
| C# | Via gdUnit4Net (separate project) | No | Yes | Yes | Yes (engine-free only) |

## Recipes

### gdUnit4 (GDScript), fresh clone
```bash
G=/path/to/godot
$G --headless --path . --import            # once per fresh clone; ~7-9 s with the addon present
$G --headless --path . -s res://addons/gdUnit4/bin/GdUnitCmdTool.gd --ignoreHeadlessMode -c \
   -a res://tests -rd res://reports > /tmp/t.log 2>&1 ; echo $?   # 0 ok / 100 failed / 101 orphans / 105 parse error
python3 -I summarize_junit.py "$(ls -dt reports/report_*/results.xml | head -1)"
```
- `-a` accepts a directory or a suite path; `-i` is *ignore*, not "only run". I did not verify a single-test selector, so for one test use a small suite file or `-a res://tests/test_x.gd` [Unverified for per-test].
- `-rd` sets the report directory and `-rc` the retained report count (default 20) [Run: --help-advanced]. Without `-rd` each run creates `reports/report_N/`, so pick the newest.
- `-s -d --remote-debug tcp://127.0.0.1:0` is what `runtest.sh` uses, to stop the interactive `debug>` loop on parse errors [Src: runtest.sh]. Without `-d` it also ran and gave the same exit codes [Run].
- Exit codes need `GdUnitCmdTool.gd`'s `get_tree().quit(code)` only (no OS.exit_code workaround) [Run].

### GUT
```bash
$G --headless --path . --import
mkdir -p out
$G --headless --path . -s addons/gut/gut_cmdln.gd -gdir=res://tests -gexit \
   -gjunit_xml_file=res://out/junit.xml -gdisable_colors > /tmp/g.log 2>&1 ; echo $?
# MANDATORY guard, because exit stays 0 on unparseable test files:
grep -E "SCRIPT ERROR|Parse Error|GUT ERROR|GUT WARNING\]:  Ignoring script|have not been imported" /tmp/g.log && exit 1
```
- Selectors: `-gselect=<file substring>`, `-ginner_class=`, `-gunit_test_name=` [Src: gut_cli.gd:126-128]. A `.gutconfig.json` is read from `res://` by default [Src: gut_cli.gd:91].
- `-gexit` is required or the process stays open; `-gexit_on_success` exits only when all pass [Src: gut_cli.gd:129-130].

### gdUnit4Net (C#), tested on 4.7 mono
```bash
export GODOT_BIN=/path/to/Godot_v4.7-stable_mono_linux.x86_64
dotnet build && dotnet test --logger "trx;LogFileName=r.trx" --logger "console;verbosity=normal"
```
Observed: `Passed: 2, Failed: 1`, exit 1, stack trace with `file.cs:line 8`, trx at `TestResults/r.trx`. The first build took 22 s. The adapter used the Godot binary only as needed ("Tests run without Godot runtime by default" [Doc README]).

### GoDotTest (C#)
`godot --headless --path . --run-tests=MyFailTest --quit-on-finish` printed `Test results: Passed: 1 | Failed: 1` and exited 1 [Run]. Output ends with many Godot `ERROR: Pages in use exist at exit ...` lines (harmless engine shutdown noise). Gotcha: running `godot --headless --import` on the C# project **rewrote the csproj `Sdk="Godot.NET.Sdk/4.7.2"` to `4.7.0` and left a `.csproj.old`**, which then broke `dotnet build` with NU1605. That `--import` also aborted with exit 134 [Run]. Tests still ran after rebuilding. For C# projects use `dotnet build` and do not rely on `--import`.

### Plain `dotnet test` on a Godot-free library
Package `GodotSharp 4.7.2` (NuGet, exists [Run]) referenced from an xunit project:
- Pass: `new Vector2(3,4).Length()==5`, `v*2`, `Colors.Red.R`, `Mathf.Clamp`.
- **Crash the host**: `new Node()`, `new StringName("x")`, `new Godot.Collections.Dictionary()` ("The active test run was aborted. Reason: Test host process crashed") [Run]. A crash in one test aborts the whole run (the first mixed run reported "Test Run Aborted"), so keep native-backed types out of such libraries.

## Report summariser (tested on both gdUnit4 `results.xml` and GUT junit, [Run])

```python
#!/usr/bin/env python3 -I
import sys, re, xml.etree.ElementTree as ET
path, cap = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 5
root = ET.parse(path).getroot(); tot = fail = skip = 0; fails = []
for tc in root.iter("testcase"):
    tot += 1
    f = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
    if tc.find("skipped") is not None: skip += 1
    if f is not None:
        fail += 1
        txt = (f.text or "") + " " + (f.get("message") or "")
        m = re.search(r"(res://\S+?:\d+)|at line (\d+)|line:?(\d+)", txt)  # gdUnit4: "FAILED: res://x.gd:7"; GUT: "at line 7"
        loc = (m.group(1) or ("line " + (m.group(2) or m.group(3)))) if m else "?"
        first = next((l.strip() for l in (f.text or f.get("message") or "").splitlines() if l.strip() and not l.strip().startswith("<![")), "")
        fails.append(f"{tc.get('classname')}.{tc.get('name')} @ {loc}: {first[:100]}")
print(f"{'FAIL' if fail else 'PASS'}: {tot-fail-skip} passed, {fail} failed, {skip} skipped, {tot} total")
for line in fails[:cap]: print("  -", line)
if len(fails) > cap: print(f"  ... {len(fails)-cap} more")
```
Sample outputs [Run]:
```
FAIL: 1 passed, 1 failed, 0 skipped, 2 total
  - test_fail.test_fail @ res://tests/test_fail.gd:7: Expecting:
FAIL: 1 passed, 1 failed, 0 skipped, 2 total
  - tests/test_fail.gd.test_fail @ line 7: [2] expected to equal [3]:  two is not three
```
Weakness: for gdUnit4 the first non-empty line is just "Expecting:"; showing the whole `<failure>` text collapsed to one line would be more informative. The summariser is XML-only, so it also needs the exit code (and the parse-error grep for GUT) and cannot detect a suite that never loaded under GUT, which is why gdUnit4 is preferred. GUT's `at line N` carries no file path, only the `classname` (the script path), so combine them as `classname:N`.

## Recommendation, tied to the harness
- Test layer for GDScript: **gdUnit4**, run via the `GdUnitCmdTool.gd` recipe above in a `tools/test` wrapper that: (1) runs `--import` if `.godot/` is absent, (2) passes `--ignoreHeadlessMode -c -rd`, (3) maps exit 100/101/105 to failed / warnings / broken-suite, (4) prints only the ≤15-line summary and the log path.
- Pin addon at `v6.2.2` (tag) or later 6.2.x for 4.7. `master` (v7.0.0) lists 4.7 and 4.8.dev but is not released as a tag as of this check (latest tags are v6.2.2 and v6.1.x) [Run: git ls-remote].
- If the sim/view split puts logic in plain C# classes, test those with plain xunit (fast, no engine), and use gdUnit4Net only for tests needing the engine. Keep GodotSharp types limited to structs and `Mathf`.
- Do not mix GUT and gdUnit4 in one project. gdUnit4 would try to scan GUT's `addons/gut/` only if it is under the scanned `-a` path, so keep tests in `res://tests`.

## Blocked sources
- github.com web pages / api.github.com were not used; all repos were obtained via `git clone` and `git ls-remote` (OK). `dot.net/v1/dotnet-install.sh` returned 301 and worked with `curl -L`; `builds.dotnet.microsoft.com` root returned 400 (not needed); api.nuget.org OK (200).
- Not fetched: docs sites (gdunit-labs/gut.readthedocs.io). Docs claims above come from in-repo docs at the tags.

## Open questions
- gdUnit4: no single-test selector verified on the CLI (`-a res://x.gd` selects a suite). Check `GdUnitCmdTool` options / `.cfg` (`-conf`) for a per-test filter.
- gdUnit4 upstream repo appears to be moving (README badge links point to `godot-gdunit-labs/gdUnit4`); the `MikeSchulze/gdUnit4` clone still works but the canonical URL may change.
- gdUnit4Net scene-runner and mock tests were not run on 4.7 (only logic tests). Whether `5.1.0-rc5` is fully correct on 4.7, as opposed to unreleased master, is unproven beyond the three trivial tests.
- GUT: confirm there is no CLI flag that fails the run on a script that fails to parse (none found in `gut_cli.gd` options listing; `-gerrors_do_not_cause_failure` only affects GUT internal errors).
- Parallel test execution and flaky-test handling were not measured for either framework.
