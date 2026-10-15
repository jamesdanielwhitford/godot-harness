area: A1 core_cli      phase: plan (re-run after G1 review)      state: done
spec: .claude/plans/specs/01_core_cli.md v1.1 @ uncommitted
tests: 0 total / 0 pass / 0 fail (n/a)      lock: n/a
updated: 2026-10-15 by planner re-run (Opus)
done:
- spec v1: 30 ACs, 20 faults (1 nice) + 4 clean, fixtures, 7-step build order; spikes [Run] in §3.6
- v1.1 applied REVIEW B08-B13 + N04/N16/N17/N19:
  - B08 R-29: §3.2 step 9 calls harness.lint.run_lint(run, project, None|files, "full"); §8.4 updated
  - B09 R-26: §2.4 --exists FAIL = 3 lines; AC-01.21
  - B10 R-27: CLEAN-A1-01 args ["--smoke","--no-lint"]
  - B11 R-28/R-39: AC-01.16 rewritten (phases regex); AC-01.27 [contract] via run_godot
  - B12 R-33/R-16: §2.3 + §3.1 sync.py library (ensure_synced, install_gdunit4, sync_project), autoload insertion, gdUnit4 overwrite policy; AC-01.18 extended; fixture harness_trees/gdunit_cache
  - B13 R-30/R-25/R-14: public checkrun.load_check (§3.1); runner-incomplete attribution (§3.2 step 5) + AC-01.31; new §3.8 xvfb handling
  - N04/N17: §8.3 deviations marked with R-ids; §8.2-2 closed; N16: sync.py in build step 1; N19: §8.2-7
next:
- spec reviewer: confirm B08-B13 closed; one extra return value `installed (pin changed)` in install_gdunit4 (§8.3 D-g)
- T1 writes tests/contract/a1, tests/unit/a1, fixtures scene_cases + gd_cases + harness_trees/{sync_src,gdunit_cache}, selftest FAULT-A1-*/CLEAN-A1-*
blockers:
- none
disputes: 0 open
