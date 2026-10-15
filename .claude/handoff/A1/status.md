area: A1 core_cli      phase: plan      state: done
spec: .claude/plans/specs/01_core_cli.md @ uncommitted
tests: 0 total / 0 pass / 0 fail (n/a)      lock: n/a
updated: 2026-10-15 by planner (Opus)
done:
- spec v1 written: 30 ACs (AC-01.1-30), 20 faults (FAULT-A1-01..20, 1 nice) + 4 clean entries, fixtures, 7-step build order
- spikes [Run]: batch load-check (0.29 s / 52 files) beats per-file --check-only (2.8 s x4 parallel, 10.3 s serial), same findings on 35 r1_5 cases -> batch chosen with begin/end records + resume after hang
- --doctool gap root-caused: target dir must exist (rc 1); dump with --path aborts rc 134 after writing; fix = h api --rebuild (no --path), bootstrap step 8 delegates to it
- autoloads run after a -s runner's _init and can override its exit code (rc 1 -> 0); FAULT-P0-06 premise does not hold
- r1_5 snippet sources (only in the ephemeral scratchpad) copied into spec §6
next:
- spec reviewer: check §8.3 contract deviations D-a..D-e and §8.4 assumptions (A2 reuses load_check.gd; A3 harness.lint.check_files API)
- T1 writes tests/contract/a1, tests/unit/a1, tests/gd/a1, fixtures scene_cases + gd_cases + harness_trees/sync_src, selftest FAULT-A1-*/CLEAN-A1-*
blockers:
- none
disputes: 0 open
