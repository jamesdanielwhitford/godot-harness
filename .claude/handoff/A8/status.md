area: A8 claude-wiring      phase: plan      state: done
spec: .claude/plans/specs/08_claude_wiring.md @ uncommitted
tests: 0 total (spec only; 28 ACs, 15 faults (13 must, 2 nice) + 4 clean entries for T8)      lock: n/a
updated: 2026-10-15 by planner (claude-opus-5-5)
done:
- 08_claude_wiring.md (449 lines): `h init` (install, --new, --sim-view, --check template lint, --hook replay for
  selftest), literal settings.json, one hook dispatcher (pre/post/stop/session-start) with 14 hook.* rules, CLAUDE.md
  template with 15 golden rules + Game-architecture block, 8 skills, 2 subagents (log-triage, api-lookup; haiku),
  disabled MCP snippet, [hooks] config, manifest, dogfood plan (3 claude -p tasks)
- Current Claude Code docs fetched (code.claude.com/docs/en/*.md, reachable) and cited [Doc]
- Spikes [Run] with nested claude -p 2.1.300: SessionStart context, PreToolUse deny, PostToolUse decision:block
  (model fixed Godot-3 code), Stop block + stop_hook_active all work in -p; custom project subagent resolves and runs
  on its model
- Open question resolved: hook input carries agent_id/agent_type for subagent tool calls (general-purpose and custom
  names) [Doc+Run]; main-agent calls carry neither
next:
- spec reviewer: deviations D-a..D-d; A1 request (semantic class-cache staleness, ~4.6 s import per class_name edit
  otherwise); A3 may absorb hook.ui-action/code-action/scene-change/busy-drop
- orchestrator: fresh session + one `subagent_type: builder` spawn to re-test S3 (agents dir created mid-session is
  not watched [Doc]); if it resolves, live role pathguard via agent_type is possible
- T8 writes fixtures empty_47, hook_host, hook_inputs/*.json; ACs 08.1-08.28; FAULT-A8-01..15, CLEAN-A8-01..04
blockers:
- none (build needs G3: A1/A3/A4/A5/A6/A7/A9 verbs and templates)
disputes: 0 open
