# Sessions Overview

Read this first, then the newest `session-NNN-*.md`. Narrative detail lives in the session notes.

## Session log
| # | Date | Key outcomes |
|---|---|---|
| 001 | 2026-10-15 | Round 1 research; build plan; Phase 0 (bootstrap, h doctor, dev tools, spikes S1-S6, G0 passed); RP.1/RP.2; contract + specs A1-A9; REVIEW: G1 NOT passed (19 blocking) |

## Current status
- Built: A0 `tools/bootstrap.sh` + `tools/harness/h doctor` (pins in `tools/harness/pins.toml`); A0b dev tools `tools/dev/*.sh`.
- Specified only: `.claude/plans/specs/00_contract.md`, `01`-`09` (143 faults + 28 clean). No harness verbs beyond doctor, no tests/LOCK, no tags.
- G1 NOT passed: `.claude/plans/specs/REVIEW.md` lists B01-B19 (blocking) and N01-N24; REVIEW wins over specs until re-runs land.
- Phase 2 (core tests) not started; blocked on B01-B15 + orchestrator edits N12/N13.
- Round P: RP.1 and RP.2 done (`.claude/research/rp_1_baseline.md`, `rp_2_references.md`); topic agents wait for G2.
- Plan: `.claude/plans/build_and_test_plan.md` (§0 status board current). Handoff: `.claude/handoff/*/status.md`.
- Decisions: D1-D5 defaults in force (GDScript only, 2D platformer + grid, no MCP, agent never judges feel, small tier).
- Branch `main` only; agents never commit; orchestrator commits `[Area][role]` after pathguard.
- Env: scratchpad from session 001 is gone; bootstrap re-creates Godot/gdUnit4/odiff/.venv. github.com web/API blocked, git clone works.
- Custom subagent types unverified in a fresh session (`.claude/agents/*.md`).
- Publish state: nothing published outside the repo.
- User must delete remote branches `spike-test`, `build/x-spike` (agents get HTTP 403).

## Next session checklist
- [ ] Start: `git pull`; read CLAUDE.md, this file, `session-001-2026-10-15.md` (section "Next steps, in order"), plan §0, REVIEW.md in full.
- [ ] `tools/bootstrap.sh` then `tools/harness/h doctor` (Godot from bootstrap cache; re-clone research refs by pinned commit only if needed).
- [ ] Test one `subagent_type: "verifier"` spawn; if it resolves use role types (hooks can use `agent_type`), else general-purpose + `model` + pasted role text. Record in plan §0.
- [ ] Ask user once (do not wait): REVIEW §6 items 1-2 (defaults: provisional-default WARN until G3 approval; `replay_dirs = []`, template/sample strict); D1-D5 defaults; delete the 2 leftover remote branches.
- [ ] Wave 1: Opus P0 re-run on `00_contract.md` with B01-B07 + N03, N14, N17, N18. Pathguard, grep R-ids, commit `[P0][plan]`, push.
- [ ] Wave 2 (parallel): P1 (B08-B13 + N04, N16, N19), P2 (B14 + N05), P3 (B15 + N06, N20), optional P4 (N01, N02). Same check per spec.
- [ ] Wave 3 (parallel, may overlap Phase 2): P5 (B16 + N07, N15), P6 (B17 + N08, N22), P7 (B18 + N09, N23), P9 (B19 + N11, N21). P8 (N10, N24) before T8.
- [ ] Orchestrator edits: `tools/dev/ci.sh` gd layer -> `pytest tests/gd` (R-39) + plan §4.2 row; plan N12 text (§3.2 no `h check --lsp`; §7 A2 digest <= 40 lines + `more:`; A6 `h shot --layout`; gd_host owned by T1); §5.2 R-01 allowlist; §9.1 depth per RP.1.
- [ ] REVIEW re-check after B01-B19: mark applied, verdict "G1 passed", update §0, tag + push `specs-v1`.
- [ ] Phase 2: T1 first deliverable (conftest, helpers h.py/gd.py, clean_min, gd_host, P0 faults) -> commit -> T2/T3/T4 parallel; pathguard after each; verifier red check; `tools/dev/lock_tests.sh`; commit + push.
- [ ] Phase 3: B1 (step 0 + sync.py in step 1) -> core-ready gate -> B2/B3/B4 parallel; T5/T9/T7 then T6 in parallel.
- [ ] G2 verifier (fresh clone, ci x2, selftest, 3 mutants) -> tag `v0-core`; then Round P topic agents (full: RP.A, RP.B[3D deferred], RP.D, RP.E, RP.F, RP.I; reduced: RP.C, RP.G, RP.H, RP.J, RP.K) with plan §9.2 amendments.
- [ ] Phase 5 -> G3 `v0-runtime` (human approves sample baselines/targets); Phase 6 T8 -> B8 -> dogfood -> G4 `v0`; then RP.Z1 -> P10/A10 -> G5 `v0.1`; RP.Z2 in Phase 8.
- [ ] End of session: new `session-NNN-YYYY-MM-DD.md`, update this file + plan §0, commit, push.
