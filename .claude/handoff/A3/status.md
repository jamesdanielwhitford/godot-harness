area: A3 lint      phase: plan      state: done (re-run after REVIEW v1)
spec: .claude/plans/specs/03_lint.md @ uncommitted (v2, 461 lines)
tests: 0 total (spec only; 28 ACs, 27 faults (25 must, 2 nice) + 3 clean entries for T3)      lock: n/a
updated: 2026-10-15 by planner re-run (claude-opus-5-5)
done:
- v1: `h lint` (full/--hook/--changed/--godot3-oracle), `h lsp start|status|stop|diag`, run_lint/lsp_diag API,
  rules JSON schema, [lint] config, suppression, lint.* rules, r1_5 corpus in §6.1, spikes [Run]
- v2 (REVIEW B15, N06, N17, N20):
  - R-08: §2.6 `replay_dirs` default `[]` (+ opt-in note); §6.3 lint_clean_demo ships harness.toml `replay_dirs = ["res://"]`;
    AC-03.16 writes that harness.toml first; FAULT-A3-13/17 gain a first harness.toml write op; §3.7 note; §8.2 Q1 closed
  - R-29: §2.2/§2.3 `h check --lsp` removed; run_lint canonical, A1 step 9 call shape; §8.4 updated
  - R-09: `h lsp start` uses `godot.spawn(..., "lsp_start", ...)`; §3.6 kinds point at C §2.8.2
  - N06/N17: §8.3 deviations marked accepted (R-09, R-01, R-48, R-38); §4 data layer accepted per R-01
  - N20: AC-03.5 wording "with harness.toml replaced by `[lint]\nreplay_dirs = []`"; CLEAN-A3-03 likewise
next:
- T3 writes fixtures godot3_scripts, lint_base, lint_clean_demo (+ its harness.toml) and faults
blockers:
- none
disputes: 0 open
