area: A5 scenario      phase: plan      state: done (v2, REVIEW B16 + N07/N15/N17 applied)
spec: .claude/plans/specs/05_scenario.md @ uncommitted
tests: 0 total (spec only; 28 ACs, 12 faults (10 must, 2 nice) + 2 clean entries for T5)      lock: n/a
updated: 2026-10-15 by planner re-run (claude-opus-5-5)
done:
- v1: `h run` CLI + output, scenario schema, Harness/Rng/CommandBus APIs, artifacts + hashing, goldens, `--twice`
  diagnosis, runner algorithm, faults, fixtures; 6 spikes [Run] in scratchpad a5/
- v2 (REVIEW B16): R-18 `tick_completed(0)` (§2.3, §3.2 step 2; fixture metric `tick_signals == 121` in AC-05.2);
  R-19 new `replay.py` `run_scenario(...)` + public `scenario.py` API (§2.7, §3.1, §3.3); R-20 `handle` replaces,
  `unhandle` added (§2.3, AC-05.26 = N07); R-15 A5 owns `scenario.gd` incl. `--shot-at` block (§3.1, §3.2 step 6);
  R-34 runner not-synced -> error + `done` rc 1 (§2.1, §3.2 step 1); N15 open Q2 closed by A6 K9; N17 §8
  deviations marked with R-ids (D-a R-01, D-b R-48)
next:
- T5 writes fixtures scenario_min (+ level.gd `tick_signals` metric) + scenario_noautoload, ACs 05.1-05.28,
  FAULT-A5-01..12, CLEAN-A5-01..02
- B5 builds replay.py and the `--shot-at` block; A6 AC-06.25 verifies the latter after B6
blockers:
- none
disputes: 0 open
