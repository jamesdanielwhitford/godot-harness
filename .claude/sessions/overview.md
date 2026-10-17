# Sessions Overview

Read this first, then the newest `session-NNN-*.md`. Narrative detail lives in the session notes.

## Session log
| # | Date | Key outcomes |
|---|---|---|
| 001 | 2026-10-15 | Round 1 research; build plan; Phase 0 (bootstrap, h doctor, dev tools, spikes S1-S6, G0 passed); RP.1/RP.2; contract + specs A1-A9; REVIEW: G1 NOT passed (19 blocking) |
| 002 | 2026-10-15 | Orchestrator edits N12/N13; all planner re-runs; **G1 passed** (REVIEW §8, R-51..R-56); Phase 2 tests T1-T4 written and committed (not locked) |
| 003 | 2026-10-17 | Reconciled unrecorded work, moved to local Mac (bootstrap/doctor on darwin), built A2, A3, A4; adjudicated A2/A3 disputes; A4 dispute open |

## Current status
- **Environment: local Mac** (Godot 4.7 at /Applications/Godot.app, `.venv` and cache built, `tools/bootstrap.sh` and `h doctor` work on darwin). Screenshot decision for A6: real display, `gl_compatibility`, Mac-only baselines (session 003 note).
- Built: A0, A0b, A1 core, A2 (digest, scene_gen, scene_edit), A3 (lint, lsp), A4 (test). Specs 00-09 passed G1. Tests locked for P0, A1-A7, A9 (`tests/LOCK.sha256`). T8 (A8) not written.
- Not built: A5, A6, A7, A8, A9 (sim/view/sample). No `v0-core` tag, no G2 verifier run yet.
- Open: A4 dispute D-1 (FAULT-A4-05 fixture races a physics frame), A4 flakiness under load, ci.sh --quick red on unbuilt areas, spec 08 N10/N24 + N25-N29 + two small spec 02 notes (one planner pass).
- Process: agents never commit; orchestrator runs pathguard + check_lock then commits. Agents one at a time. Subagents resume with SendMessage after a rate limit.
- Publish: all on origin/main. Remote branches `spike-test`, `build/x-spike` still to delete; tag `specs-v1` local only.

## Next session checklist
- [ ] Read this file, `session-003-2026-10-17.md`, plan §0, then `git pull`; `tools/bootstrap.sh`.
- [ ] Adjudicate A4 dispute D-1 (fresh test-writer, no implementation access), relock, commit.
- [ ] G2: verifier agent on a fresh clone of pushed main (ci twice, selftest, 3 mutants, AC walk); fix real failures; tag `v0-core`.
- [ ] One Opus planner pass: spec 02 §2.2/§2.3 notes, spec 08 N10/N24, N25-N29. Then T8.
- [ ] Phase 5 builders in order: B5 (A5), B9a (A9), B6 (A6), B9b, B7 (A7); then G3 (James approves sample baselines/targets).
- [ ] Phase 6: B8 (A8), dogfood, G4 `v0`. Then Round P, A10, evaluation.
- [ ] James: delete remote branches `spike-test`, `build/x-spike`; try pushing tag `specs-v1`.
- [ ] End of session: new session note, update this file + plan §0 + CLAUDE.md status, commit, push.
