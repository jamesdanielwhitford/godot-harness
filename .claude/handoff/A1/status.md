area: A1 core_cli      phase: build      state: in-progress
spec: .claude/plans/specs/01_core_cli.md v1.1 @ uncommitted
tests: 301 own (p0+a1 unit/contract/e2e-p0, bootstrap, devtools) / 300 pass / 1 fail (test_ac_01_3_all_24_at_once, disputed)   lock: ok
updated: 2026-10-15 by builder B1 (Sonnet)
done:
- contract core (out, project, config, logscan, proc, godot, faults, cli, doctor, selftest) and A1 verbs check/import/sync/api, sync.py, checkrun.py, apiindex.py, load_check.gd, bootstrap C8/C9
- core-ready gate green; `h selftest --area P0` and `--area A1` all caught
next:
- orchestrator: adjudicate dispute D-1 (AC-01.3 truncation expectation), run AC-01.29 (e2e bootstrap, needs commit + network)
- xvfb handling (godot.py, A1 3.8) untested until A6
blockers:
- none
disputes: 1 open
