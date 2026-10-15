# godot-harness

Goal: build a harness that makes an LLM coding agent (Claude Code) work as well as possible on Godot 4.x games, based on the "game as harness" idea (Kyle Kukshtel, "Your Game Is A Harness"). Make the game and project readable and drivable by text and commands, verify with scripts, and keep the LLM away from what it is bad at (judging feel and visuals, hand-editing scenes, trusting exit codes).

Target engine: **Godot 4.7 stable** (`4.7.stable.official.5b4e0cb0f`).

## Status
Phase 0 done (bootstrap, `h doctor`, dev tools); contract and specs A1-A9 written; spec review G1 not yet passed. Current status and the next-session checklist: `.claude/sessions/overview.md`.

## Start of every session
1. Read `.claude/sessions/overview.md` first, then the latest `.claude/sessions/session-NNN-YYYY-MM-DD.md` (handoff, open decisions, detailed next steps).
2. Read `.claude/plans/build_and_test_plan.md` §0 (status board) and the plan sections the next step needs.
3. Research lives in `.claude/research/` (`r1_*.md`, `r2_spikes.md`, `rp_*.md`, with tested scripts under `research/scripts/`). Read the relevant report before building on its topic.
4. At the end of a session, write `.claude/sessions/session-NNN-YYYY-MM-DD.md` (NNN = highest + 1), update `overview.md` and plan §0. Commit and push.

## Layout
- `.claude/sessions/`: `overview.md` (bounded snapshot) and `session-NNN-YYYY-MM-DD.md` notes, one per session.
- `.claude/plans/`: harness plan, patterns addendum, build and test plan; `specs/` holds area specs and `REVIEW.md`.
- `.claude/handoff/<area>/status.md`: per-area status; `.claude/agents/`: role definitions.
- `tools/`: `bootstrap.sh`, `harness/` (the `h` CLI), `dev/` (pathguard, lock, ci, fresh-clone verify).
- `.claude/research/`: Round 1, spikes and Round P findings plus the scripts that produced them.
- `.claude/sources/`: summaries of source material (the article).

## Working rules (from the research)
- Never trust Godot exit codes for script/scene checks: parse errors and runtime script errors can exit 0. Grep output for `SCRIPT ERROR`, `Parse Error`, `Failed to load script`, and wrap runs in `timeout`. Only `SceneTree.quit(N)` sets a code. See `r1_1_cli.md`, `r1_5_failure_lint.md`.
- Run `godot --headless --path . --import` once on a fresh clone before anything that uses `class_name`, tests or UIDs.
- Do not hand-edit `.tscn`/`.tres`. Generate scenes with the engine from a spec and verify with a log-capturing load-check (many broken scenes load silently). See `r1_4_scene_format.md`.
- Screenshots need Xvfb plus the OpenGL (`gl_compatibility`) renderer, not `--headless`. See `r1_7_visual.md`.
- Test framework: gdUnit4 (v6.2.2+) for GDScript. GUT exit codes are untrustworthy. See `r1_3_testing.md`.
- Determinism holds on the same binary and machine class; use exact hashes there and tolerances for physics floats across machines. Tween, Timer and AnimationPlayer are deterministic only in physics process mode. See `r1_8_determinism.md`.
- Keep game rules in a node-free simulation (`apply(state, command) -> events`), with nodes as the view. See `r1_6_talks.md`.
- The agent never judges game feel or visuals itself. It measures against targets a human approved.
- MCP servers are an optional live layer, not the core. All of them run project GDScript with the user's permissions. See `r1_2_mcp.md`.

## Environment notes (Claude Code on the web)
- The Godot binary is not in the repo. Run `tools/bootstrap.sh` (downloads and sha256-checks the pinned zip into `~/.cache/godot-harness/`, symlinks `tools/bin/godot`), then `tools/harness/h doctor`. Xvfb is installed.
- github.com web pages and api.github.com are blocked; `git clone`, raw.githubusercontent.com, release downloads, docs.godotengine.org, npm and pypi work. `gh` auth was invalid at last check.
- Subagents write findings to files; do not paste large transcripts into chat.

## Conventions
- Commit small, push to the working branch. Do not open a PR unless asked.
- Mark uncertain facts `[U]` and verified runs `[Run]` in notes and research.
