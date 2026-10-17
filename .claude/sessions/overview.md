# Sessions Overview

Read this first, then the newest `session-NNN-*.md`. Narrative detail lives in the session notes.

## Session log
| # | Date | Key outcomes |
|---|---|---|
| 001 | 2026-10-15 | Round 1 research; build plan; Phase 0 (bootstrap, h doctor, dev tools, spikes S1-S6, G0 passed); RP.1/RP.2; contract + specs A1-A9; REVIEW: G1 NOT passed (19 blocking) |
| 002 | 2026-10-15 | Orchestrator edits N12/N13; all planner re-runs; **G1 passed** (REVIEW §8, R-51..R-56); Phase 2 tests T1-T4 written and committed (not locked) |
| 003 | 2026-10-17 | Reconciled unrecorded work (B1 A1 core built, T5-T7/T9 tests written, tests locked e6b075e); moved to local Mac; B2-B4 never ran |

## Current status
- **Environment: local Mac since session 003** (Godot at /Applications/Godot.app, bootstrap is Linux-only, no .venv yet). See CLAUDE.md.
- **Progress since session 002 note**: B1 built (verbs api/check/doctor/import/selftest/sync), tests T5/T6/T7/T9 written, `tests/LOCK.sha256` exists (e6b075e). B2/B3/B4 and A5-A9 builders not run. Some handoff status.md files are stale; trust git log.
- Built: A0 `tools/bootstrap.sh` + `tools/harness/h doctor`; A0b dev tools `tools/dev/*.sh` (ci.sh gd layer now `pytest tests/gd`).
- Specs: contract + A1-A9 all re-run for REVIEW except A8 (`08_claude_wiring.md`, N10/N24 open before T8). **G1 passed** (REVIEW §8). Decisions R-51..R-56 apply ahead of spec edits. Tag `specs-v1` is local only (tag push 403); commit ec98abe.
- Phase 2 core tests written and committed (not locked): `tests/{unit,contract,e2e}/{p0,a1,a2,a3,a4}/`, helpers `tests/helpers/{h,gd}.py`, fixtures under `tests/fixtures/`, faults/clean under `selftest/`. ~615 tests collect, all red (no harness verbs beyond doctor). Red-check verifier report: `.claude/handoff/phase2/verify_2026-10-15_red.md` (if missing, rerun it).
- No harness code beyond `doctor`; no `tests/LOCK.sha256`; no `v0-*` tags.
- Round P: RP.1, RP.2 done; topic agents wait for G2.
- Plan: `.claude/plans/build_and_test_plan.md` (§0 current). Handoff: `.claude/handoff/*/status.md`, `test_notes.md`.
- Decisions: D1-D5 defaults; provisional-default baselines (WARN until G3 approval); `replay_dirs = []` user / `["res://"]` template+sample. User said: work autonomously, choose recommended options, notify when all work is done.
- Custom subagent types resolve by `subagent_type` (verified session 002). Agents never commit; orchestrator commits `[Area][role]` after pathguard (parallel agents share the tree, so pathguard with comma area list or commit by pathspec).
- Do not leave polling shell watchers running; rely on agent completion notices.
- Publish state: nothing published outside the repo. User must delete remote branches `spike-test`, `build/x-spike` (agents get 403).

## Next session checklist (session 002 completed items 1-8 of the old list: pull, bootstrap, verifier type test, user defaults, Waves 1-3, orchestrator edits, G1 re-check, Phase 2 tests)
- [ ] Read red-check report; fix helper/fixture bugs and vacuous passes via the owning test-writer; `tools/dev/lock_tests.sh`; commit `[phase2] lock tests`; push.
- [ ] Phase 3: B1 -> core-ready gate -> B2/B3/B4; T5/T9/T7 then T6. (Then continue with the original items below from Phase 3.)
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
