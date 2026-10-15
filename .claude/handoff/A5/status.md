area: A5 scenario      phase: plan      state: done
spec: .claude/plans/specs/05_scenario.md @ uncommitted
tests: 0 total (spec only; 28 ACs, 12 faults (10 must, 2 nice) + 2 clean entries for T5)      lock: n/a
updated: 2026-10-15 by planner (claude-opus-5-5)
done:
- 05_scenario.md (449 lines): `h run` CLI + output, scenario JSON Schema (vars/sweeps, bind, inputs, commands,
  dumps, asserts), Harness/Rng/CommandBus GDScript APIs, artifacts + hashing, golden format/compare (B7),
  `--twice` with perturbation (fps 2x + global RNG reseed) and cause diagnosis, runner algorithm, faults, fixtures
- 6 spikes [Run] in scratchpad a5/: autoloads under -s; inject inputs from MainLoop _process (from _physics_process
  just_pressed is off by one); CharacterBody2D 3x identical hashes; 600 ticks 0.37 s; randf/idle-tween/_process-delta/
  unseeded-RNG faults all detected by the A/B perturbation (idle tween only via per-tick hashes)
next:
- spec reviewer: check deviations D-a (unit tests import harness.scenario) and D-b (runner drives ticks, not the
  Harness autoload) and the A1 assumption `sync.ensure_synced`
- T5 writes tests/fixtures scenario_min + scenario_noautoload, ACs 05.1-05.28, FAULT-A5-01..12, CLEAN-A5-01..02
- A6/A7/A9 planners: use `run_scenario()` helper, `Harness.tick_completed`, entity/command conventions (§8)
blockers:
- none
disputes: 0 open
