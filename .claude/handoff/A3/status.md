area: A3 lint      phase: tests      state: done
spec: .claude/plans/specs/03_lint.md @ uncommitted (v2)
tests: 126 collected (123 red, 3 green self-checks; ~90 test functions, parametrized) / 3 pass / 123 fail (all: unknown verb lint|lsp, missing rules/*.json)      lock: n/a
updated: 2026-10-15 by test-writer (claude-sonnet-5-5)
done:
- fixtures godot3_scripts, lint_base, lint_clean_demo (+ harness.toml, LICENSE)
- tests/unit/a3, tests/contract/a3 covering AC-03.1..28; FAULT-A3-01..27, CLEAN-A3-01..03
next:
- B3 builds A3 per spec section 7; orchestrator locks tests
blockers:
- none
disputes: 0 open
