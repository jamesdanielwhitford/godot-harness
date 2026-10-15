area: A3 lint      phase: plan      state: done
spec: .claude/plans/specs/03_lint.md @ uncommitted
tests: 0 total (spec only; 28 ACs, 27 faults (25 must, 2 nice) + 3 clean entries for T3)      lock: n/a
updated: 2026-10-15 by planner (claude-opus-5-5)
done:
- 03_lint.md (448 lines): `h lint` (full/--hook/--changed/--godot3-oracle), `h lsp start|status|stop|diag`,
  python API run_lint/lsp_diag for A1/A8, rules JSON schema, [lint] config, suppression, 15 new lint.* rules
  (input-action, signal-name, indent-mixed, det-*, sim-node, raw-keycode, g3-project, lsp, g3-oracle)
- r1_5 32-case corpus embedded verbatim in spec section 6.1 with exact expected findings (scratchpad copy is ephemeral)
- spikes [Run]: anchor prefilter 290-408 ms -> 34-39 ms wall per file, identical hits on 992 demo files;
  0 error hits on demos; validate-conversion-3to4 behaviour; LSP daemon with sequential clients; 91 built-in actions
next:
- spec reviewer: settle section 8.3 deviations (new godot kinds oracle/lsp_start + godot.spawn; tests reading rules JSON)
  and 8.2 Q1 (default replay_dirs)
- T3 writes tests/fixtures godot3_scripts, lint_base, lint_clean_demo (dodge_the_creeps @b761b4c, MIT) + faults
blockers:
- none
disputes: 0 open
