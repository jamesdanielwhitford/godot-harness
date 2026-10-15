area: P0 contract      phase: plan      state: done
spec: .claude/plans/specs/00_contract.md @ uncommitted
tests: 0 total (spec only; 26 ACs, 8 faults + 2 clean entries for T1)      lock: n/a
updated: 2026-10-15 by planner (claude-opus-5-5)
done:
- 00_contract.md: dispatcher/discovery, stdout grammar + examples, rc 0-5, run dir + run.json schema, harness.toml,
  rule-id namespaces, godot.py invocation/timeout/log-scan/runner protocol/verdict merge, auto-import rule,
  fault.toml + selftest semantics, fixture + B3 rules, test helpers, pathguard allowlists, lock, status.md format
- 3 small spikes [Run] (log formats, hang/kill timing, OS.crash rc 134, hidden dir not imported)
next:
- orchestrator: read the spec in full; apply C5-C7, C10, C11 (spec §3.2) before Phase 2 (T1 needs the pathguard change)
- planners P1-P9 conform to §2; A1 spec includes the §3.1 files as B1 step 0
- T1 writes P0 ACs/faults with pathguard areas a1,p0,bootstrap
blockers:
- none
disputes: 0 open
