area: A7 feel      phase: plan      state: done (v2, REVIEW re-run)
spec: .claude/plans/specs/07_feel.md @ uncommitted (463 lines)
tests: 0 total (spec only; 24 ACs, 11 faults (10 must, 1 nice) + 2 clean entries for T7)      lock: n/a
updated: 2026-10-15 by planner re-run (claude-opus-5-5)
done:
- v1: `h trace` suite/scenario modes, tick convention, metric catalogue, trace formats, Trace autoload, FeelTarget(s),
  feel.* rules, 4 spikes [Run] (scratchpad a7/)
- v2 (REVIEW B18, N09, N17, N23):
  - R-37: FAULT-A7-01..06 not_regex = `^FAIL +(?!<metric>:)[a-z]+\.[a-z0-9_.]+:` (§5 header + rows; checked with
    python re: verdict line and `OK   more:` do not match); fold line `OK   more: <n> metrics in range` (§2.2)
  - R-19: §3.3 step 3 and §3.5 call `harness.replay.run_scenario(...)` (kind scenario / movie+xvfb+extra_args)
  - N09/R-42: A6 movie-helper clause dropped (§8); D-a..D-d marked accepted with R-ids (N17)
  - N23/R-36: §8 A9 bullet: suite at res://feel/player.feel.json on feel_arena.tscn
next:
- T7 writes fixture feel_min (+ feel_noautoload, feel_csv), ACs 07.1-07.24, FAULT-A7-01..11, CLEAN-A7-01..02
blockers:
- none. [U] whether replay.run_scenario adds findings to the Run itself; A7 assumes it returns them (§3.3), A5 v2 decides
disputes: 0 open
