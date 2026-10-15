area: A7 feel      phase: plan      state: done
spec: .claude/plans/specs/07_feel.md @ uncommitted
tests: 0 total (spec only; 24 ACs, 11 faults (10 must, 1 nice) + 2 clean entries for T7)      lock: n/a
updated: 2026-10-15 by planner (claude-opus-5-5)
done:
- 07_feel.md (449 lines): `h trace` suite/scenario modes, --rates/--movie/--propose/--approve (TTY only), feel suite
  JSON Schema, normative tick convention (row k = after step k; durations count steps; coyote/buffer windows as
  offsets from leave tick L / first grounded step G), 16-metric catalogue + derived ratios, trace CSV/meta/metrics/report
  formats, Trace autoload + FeelTarget(s) resources (approved_by/approved_on; unapproved never PASS), rule ids feel.*
- 4 spikes [Run] in scratchpad a7/: convention (press at p -> takeoff row p; row 0 floor=0); counter N=6 measures
  coyote 5|6 and buffer 5|4 by code order; time-based coyote 0.1 s = 3/6/12 ticks at 30/60/120 Hz vs counter 5 ticks
  everywhere; 0.35 s per replay; Camera2D smoothing works headless, idle callback is fps-dependent; --write-movie with
  an -s runner under Xvfb works (AVI, trace identical to headless, --resolution ignored)
next:
- spec reviewer: deviations D-a..D-d; A5 asks (tick_completed(0), run_scenario with resolved file + extra_args, no
  run.no-asserts); contract default autoloads + "Trace"; A8 hook patterns for targets/--approve; A9 sample targets
- T7 writes fixture feel_min (+ feel_noautoload, feel_csv synthetic traces), ACs 07.1-07.24, FAULT-A7-01..11,
  CLEAN-A7-01..02; records measured fixture values in test_notes.md
blockers:
- none (depends on A5 runner/helpers at build time)
disputes: 0 open
