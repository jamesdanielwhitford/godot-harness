area: A9 sim_view_sample      phase: plan      state: done (v2, REVIEW B19 applied)
spec: .claude/plans/specs/09_sim_view_sample.md @ uncommitted (473 lines)
tests: 0 total (spec only; 22 ACs, 12 faults (11 must, 1 nice) + 3 clean entries for T9)      lock: n/a
updated: 2026-10-15 by planner re-run (claude-opus-5-5)
done:
- v1: sim core, view core, project template + SceneManager, snapshot schema, tactics + platformer samples, split
  rules, scenarios, hook lines, faults; 5 spikes [Run] in scratchpad a9/
- v2 (REVIEW B19 + N11/N17/N21):
  - R-16: [autoload] = Harness, Rng, CommandBus, Trace, SceneManager (§2.4, AC-09.2); AC-09.5 "5 autoloads"
  - R-08: template + sample harness.toml set `[lint] replay_dirs = ["res://"]` (§2.4, AC-09.2)
  - R-36: feel_arena.tscn + res://feel/{run,jump,tap,coyote,buffer,camera}.json + player.feel.json (§2.7, §3.1, §7 step 8)
  - R-17: feel_targets.tres names/ranges per A7 §2.5 (§2.7 Data files)
  - R-35: AC-09.22 rc 5 WARN with only shot.baseline-unapproved / feel.unapproved; provisional baseline procedure
    (§7 step 8); §8.2-5 closed
  - N11: SimHost unhandle on tree_exiting (§2.3); §8.4 A5 assumption updated (R-20)
  - N17: §8.3 D-1..D-4 marked accepted (R-10, R-39, R-48, R-48)
  - N21: feel probes not counted in AC-09.7 (§2.7, AC-09.7)
next:
- T9 writes tests/gd/a9, tests/contract/a9, tests/e2e/a9, FAULT-A9-01..12, CLEAN-A9-01..03
- B9b builds feel arena/suite; records provisional baselines/targets and any widened bound in build_notes
blockers:
- none
disputes: 0 open
