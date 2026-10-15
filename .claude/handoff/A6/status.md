area: A6 visual      phase: plan      state: done (re-run v1.1 after REVIEW)
spec: .claude/plans/specs/06_visual.md @ uncommitted (v1.1, 474 lines)
tests: 0 total / 0 pass / 0 fail (spec only; 27 ACs, 12 faults + 3 clean entries for T6)      lock: n/a
updated: 2026-10-15 by planner re-run (claude-opus-5-5)
done:
- v1: `h shot` (scene + scenario mode), `h shot --layout`, `h baseline propose|approve|list`, meta schema, exact vs tolerant compare; spikes K1-K11 [Run]
- v1.1 applied REVIEW B17: R-15 (scenario.gd dropped from §3.1, A5/B5 owns the --shot-at block; §3.2.6, §7 step 7, §8.4),
  R-35 (one human predicate, provisional -> `shot.baseline-unapproved` warning, rc 5; §2.2, §2.3, §3.3 step 1, §8.4 A9),
  R-19 (`replay.run_scenario(..., kind="shot", display="xvfb")`, `scenario.load`/`write_resolved`; §3.2 steps 2-3, §8.4 A5)
- v1.1 applied N08: R-42 (§2.6 A7 sentence removed, §2.1 --movie, §8.4 A7 independent AVI), R-47 (`WARN proposals: none pending`, §2.3, AC-06.24)
- N17: §8.3 D-a..D-d marked accepted R-11..R-14 (D-d closed, owned by A1 godot.py); N22: AC-06.9 + AC-06.23 provisional cases
next:
- T6 writes tests/contract/a6/, fixture shot_min (+ capture_ref.gd, approved baseline PNG), FAULT-A6-01..12, CLEAN-A6-01..03
- T6 starts after T5 has written scenario_min (AC-06.25 needs B5)
blockers:
- none. [U] whether A5's replay.run_scenario calls ensure_synced; A6 calls sync.ensure_synced itself (harmless if both do)
disputes: 0 open
