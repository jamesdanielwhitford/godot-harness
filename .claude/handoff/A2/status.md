area: A2 scene      phase: tests      state: done
spec: .claude/plans/specs/02_scene.md @ uncommitted (v2)
tests: 99 total / 0 pass / 99 fail-or-error (9 failed, 90 errors: unknown verb 'import' in warm fixture, ModuleNotFoundError harness.scenes)      lock: n/a
updated: 2026-10-15 by test-writer (claude-sonnet-5-5)
done:
- fixture scene_host (verified load-clean with the r1_4 load_check), 6 specs
- tests: unit/a2 (AC-02.34), contract/a2 (AC-02.1-32), e2e/a2 (AC-02.33)
- selftest: FAULT-A2-01..15, CLEAN-A2-01..03
- test_notes.md with interpretation choices [U]
next:
- orchestrator: pathguard (a2), lock, commit
- builder: B2 after B1 step 2
blockers:
- none
disputes: 0 open
