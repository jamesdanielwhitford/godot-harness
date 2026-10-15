area: A9 sim_view_sample      phase: plan      state: done
spec: .claude/plans/specs/09_sim_view_sample.md @ uncommitted
tests: 0 total (spec only; 22 ACs, 12 faults (11 must, 1 nice) + 3 clean entries for T9)      lock: n/a
updated: 2026-10-15 by planner (claude-opus-5-5)
done:
- 09_sim_view_sample.md (449 lines): sim core API (SimWorld/SimThing/SimRules/SimCodec/SimSnapshot), view core
  (ThingView/SimView with snap-to-end reconcile, SimHost glue), project template keys + SceneManager (never drops),
  snapshot JSON Schema, tactics sample (commands/reasons/events), platformer (MovementTuning, pure PlayerMotor,
  Player, PlatformerGame), split decision rules for the CLAUDE.md block, required scenarios, hook lines, faults
- 5 spikes [Run] in scratchpad a9/: 1000-turn sim hash stable x3 (17-37 ms); 64-bit RNG state lossy through JSON
  numbers (fixed by string encoding, split run == straight run); JSON int->float traps; midpoint gravity gives exact
  apex at 30/60/120 Hz; ResourceSaver .tres header shape / script classes not in ClassDB
next:
- spec reviewer: deviations D-1 (fault fixture "@sample"), D-2 (gd suites run inside a sample copy), D-3 (data-only
  .tres written as text), D-4; A5 assumption that CommandBus.handle replaces an existing handler
- T9 writes tests/gd/a9, tests/contract/a9, tests/e2e/a9, FAULT-A9-01..12, CLEAN-A9-01..03
- A6/A7/A8 planners: provisional baselines, FeelTargets metric names, h init use of templates/project + sim_view
blockers:
- none
disputes: 0 open
