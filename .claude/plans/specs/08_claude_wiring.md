# 08 Claude Code wiring: CLAUDE.md template, skills, hooks, subagents, settings, `h init` (A8, planner P8)

Status: spec v1, 2026-10-15, Opus planner P8 (absorbs R2.6). Conforms to `00_contract.md` ("C §x"); deviations §8.3.
Tags: [Run] = §3.6 spikes (Claude Code 2.1.300, Godot 4.7.stable.official.5b4e0cb0f); [Doc] = current Claude Code docs
read 2026-10-15 (code.claude.com/docs/en/{hooks,skills,sub-agents,settings,permissions,memory,mcp}.md); [U] unverified.

## 1. Purpose and failure modes covered
A8 installs into a Godot 4.7 project what makes Claude Code use the harness unprompted: a CLAUDE.md block, 8 skills,
4 hook events (one script), 2 subagents, `settings.json`, a `./h` launcher, and `h init` (the A8 verb) to install
and check it. Each part targets a measured failure:
- **F1/F2 Godot 3 API**: `post` hook runs `h lint --hook` on each `.gd` edit (blocking feedback <= 2 s);
  `godot-api` skill, `api-lookup` subagent, rule 1. **F3/F5 scenes**: `.tscn/.tres` edits get a load-check and
  `[hook.tscn-structure]`; `godot-scene` routes to `scene-gen`/`scene-edit`/`digest`.
- **F4 exit codes, F11 noise**: hooks relay `h` verdicts (<= 40 lines); `[hook.raw-godot]` denies direct `godot`;
  `log-triage` reads full logs in its own context.
- **F8/F9, D4, D10**: `pre` denies Edit/Write of baselines and feel targets and Bash `baseline approve` / `trace
  --approve`; `ask` on golden overwrite; a Stop-time git guard catches bypasses.
- **rp_1 traps**: (1) dropped scene-change requests (D7) -> `[hook.busy-drop]`, `[hook.scene-change]`, rule 8, flow
  soak recipe; (2) unmeasured timing claims (D2) -> Stop `[hook.unmeasured-claim]`, rule 5; (3) `ui_*` /
  code-registered input (D8) -> `[hook.ui-action]`, `[hook.code-action]`, rule 7; (4) scratch files -> `[hook.scratch]`.
- **F7 fresh clone**: SessionStart installs/bootstraps the harness, runs `h doctor`, `h sync --check`, lists pending
  human approvals. **F12/F13**: rule 14. **D3**: MCP only as a disabled snippet (`-p` connects `.mcp.json` unasked [Doc]).

## 2. Interfaces
### 2.1 `h init`
```
h init [--project DIR] [--new] [--sim-view] [--force] [--no-sync] [--with-mcp] [--strict]
h init --check [--project DIR]
h init --hook EVENT --input FILE [--project DIR]      # EVENT: session-start | pre | post | stop
```
- Project: C §2.2 resolution, except `--new` accepts a dir without `project.godot` (created if missing) and copies
  `$HARNESS_REPO/templates/project/` into it (A9 §2.4; existing files are never overwritten). Without `--new` and no
  `project.godot`: rc 2 `ERROR init no Godot project (pass --new to create one from templates/project)`.
- Install (idempotent; writes only what differs; manifest §2.8): files of §3.1 "installed tree"; CLAUDE.md block
  between markers (§2.6); `.claude/settings.json` merged (§3.3); `.gitignore` lines appended if missing (`.godot/`,
  `.harness/`, `addons/gdUnit4/`, `addons/harness/`, `.claude/settings.local.json`, `.claude/harness.local.json`);
  `harness.toml` with `[harness] schema = 1` + `[hooks]` defaults if missing (never rewritten);
  `.claude/harness.local.json` = `{"schema":"harness.local/1","repo":"<abs $HARNESS_REPO>"}`; then `h sync`
  in-process (unless `--no-sync`). `--sim-view` also copies `templates/sim_view/{sim,view}/` -> `res://{sim,view}/core/`.
- An installed file the user changed since (sha differs from the manifest) is kept: `WARN <path>: modified locally,
  kept (--force overwrites)`, rc 5. CLAUDE.md text outside the markers and non-harness `settings.json` entries are
  never touched, even with `--force`.
- `--with-mcp` (D3 override): writes `.mcp.json` from §2.10 and removes `godot-agent-loop` from
  `disabledMcpjsonServers`; check line `WARN mcp: enabled; it runs project GDScript with your permissions`.
- `--check`: writes nothing. Lints the templates in `$HARNESS_REPO/templates/claude/` and the installed copy
  (§3.4); FAIL `[hook.init-missing]` / `[hook.init-stale]` per missing/outdated file, WARN `[hook.init-modified]`.
- `--hook EVENT --input FILE`: replays one hook offline. Reads FILE (JSON), replaces every `{project}` in string
  values with the abs project path, runs the project's `.claude/hooks/harness_hook.py` (or the template copy when
  none is installed) with `python3 -I <script> EVENT` and that stdin, cwd = project, timeout = the settings.json
  timeout of that event. Saves `artifacts/hook_stdout.txt`, `hook_stderr.txt`, `hook.json` (rc, ms). Output:
  stats `event:`, `decision: deny|ask|block|context|none`, `hook_s: <s.ss>s`, `lines: <n>` (lines of the message
  Claude would see), then the hook's findings (from its log record, §2.4) as C §2.3 finding lines. Verdict: deny or
  block -> FAIL rc 1; ask or context -> WARN rc 5; none -> PASS rc 0; hook rc not in {0, 2} or bad JSON -> FAIL
  `[hook.bad-output]`; hook timeout -> FAIL `[harness.hang]`. This is the selftest surface for hooks. Example line 1:
  `FAIL init hook post: block (2 errors)`, then e.g. `res://scripts/legacy.gd:3: [syn-yield] error: ...`.
- Stats of install, in order: `project:`, `template: claude-wiring/1 <sha12 of templates/claude>`,
  `git: <branch>|none (stop checks scan the whole project)`, `claude: <version>|not found` (WARN line if < 2.1.295,
  needed for `onFailure` [Doc]); check lines per part. rc per C §2.4; 4 when the gdUnit4 cache is missing (from sync).
```
$ tools/harness/h init --project /tmp/h/empty_47
PASS init wiring installed: 19 files written, 0 kept (2.9s)
project: /tmp/h/empty_47
template: claude-wiring/1 9f3c2a1b7d40
git: none (stop checks scan the whole project)
claude: 2.1.300
OK   CLAUDE.md: created (harness block v1, 104 lines)
OK   .claude/settings.json: created (4 hook events, 3 allow, 2 deny)
OK   .claude/skills: 8 skills
OK   .claude/agents: log-triage, api-lookup
OK   .claude/hooks/harness_hook.py: installed
OK   h: launcher installed
OK   harness.toml: created
OK   sync: addons/harness 9 files, gdunit4 v6.2.2, 3 autoloads
SKIP mcp: off (D3; --with-mcp enables)
log: /tmp/h/empty_47/.harness/out/20261015T160102Z-init-1a2b/
```

### 2.2 Installed `settings.json` (template `templates/claude/settings.json`; literal)
```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "permissions": {
    "allow": ["Bash(./h *)", "Read(./.harness/**)", "Bash(git status *)"],
    "deny": ["Edit(/baselines/**)", "Edit(**/*targets*.tres)"]
  },
  "disabledMcpjsonServers": ["godot-agent-loop"],
  "hooks": {
    "SessionStart": [{"matcher": "startup|resume|clear|compact", "hooks": [{"type": "command",
      "command": "python3", "args": ["-I", "${CLAUDE_PROJECT_DIR}/.claude/hooks/harness_hook.py", "session-start"], "timeout": 300}]}],
    "PreToolUse": [{"matcher": "Edit|Write|NotebookEdit|Bash", "hooks": [{"type": "command",
      "command": "python3", "args": ["-I", "${CLAUDE_PROJECT_DIR}/.claude/hooks/harness_hook.py", "pre"], "timeout": 10, "onFailure": "block"}]}],
    "PostToolUse": [{"matcher": "Edit|Write", "hooks": [{"type": "command",
      "command": "python3", "args": ["-I", "${CLAUDE_PROJECT_DIR}/.claude/hooks/harness_hook.py", "post"], "timeout": 60}]}],
    "Stop": [{"hooks": [{"type": "command",
      "command": "python3", "args": ["-I", "${CLAUDE_PROJECT_DIR}/.claude/hooks/harness_hook.py", "stop"], "timeout": 300}]}]
  }
}
```
Why: exec form + `${CLAUDE_PROJECT_DIR}` is the documented way to call project scripts [Doc, Run]; deny rules hold in
every mode incl. `-p`, project `allow` rules are ignored in `-p` and before workspace trust [Doc], so the hook is the
enforcement; `Edit(...)` covers Write [Doc]; `onFailure: "block"` fails a crashed guard closed [Doc, >= 2.1.295].

### 2.3 Hook dispatcher `.claude/hooks/harness_hook.py EVENT` (python3 -I, stdlib only, one self-contained file)
Common: reads the event JSON from stdin [Doc fields: `session_id`, `prompt_id`, `cwd`, `hook_event_name`,
`tool_name`, `tool_input`, `tool_response`, `stop_hook_active`, `last_assistant_message`, `agent_id`, `agent_type`];
project = `$CLAUDE_PROJECT_DIR` else `cwd`'s nearest `project.godot` ancestor; harness `h` = first of
`$HARNESS_REPO/tools/harness/h`, `.claude/harness.local.json` `repo`, `$HARNESS_CACHE/repo/<[hooks] repo_ref>/`.
`h` missing: pre still enforces its path/command rules (pure Python); post/stop return nothing and session-start says
so. Every `h` call: cwd = project, `--project <abs>`, own process group, killed at the event budget. Calls that run
Godot take an exclusive `fcntl.flock` on `.harness/hooks/lock` (parallel Edit calls fire parallel hooks [Run S1];
B3 forbids parallel Godot runs on one project). Each invocation appends one record to `.harness/hooks/log.jsonl`
(§2.4). Messages to Claude are factual statements (doc advice against imperative "system" phrasing [Doc]), start with
`harness <event>: `, relay `h` lines verbatim and are cut to 40 lines (`... N more lines; see log: <dir>`); hard cap
10,000 chars is Claude Code's [Doc]. Output channels [Doc, Run S1]:

| Event | Does | Output when there is something to say |
|---|---|---|
| `pre` (PreToolUse: Edit, Write, NotebookEdit, Bash) | path rules on `tool_input.file_path`, command rules on `tool_input.command` (§2.5); pure Python, <= 100 ms | `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny"\|"ask","permissionDecisionReason":"<rule line + hint>"}}`, exit 0 |
| `post` (PostToolUse: Edit, Write) | `.gd`: `h lint --hook F`; only if lint has no error and `[hooks] check_on_edit`: `h check F --no-lint --no-deps`; then the `.gd` hook rules (§2.5). `.tscn/.tres`: `h lint --hook F`, `h check F --no-lint` (dependents on), structure rule. Other files: nothing | errors: `{"decision":"block","reason":"<msg>"}`; warnings only: `{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"<msg>"}}`; clean: no output |
| `stop` (Stop) | loop guard; protected-file git guard; scratch files; unmeasured claims; `h check --changed` (no git: `h check`); if that passes, `h test --changed` (no git: skipped) within `[hooks] stop_budget_s` | first failing item: `{"decision":"block","reason":"<msg>"}`; budget hit or repeated failure: `{"systemMessage":"<msg>"}` (user only, allows stop) |
| `session-start` (SessionStart) | install harness if absent and `repo_url` set (clone at `repo_ref` into `$HARNESS_CACHE/repo/<ref>`, `tools/bootstrap.sh --quiet`); `h doctor`; `h sync --check`; `h baseline list` + unapproved feel targets count; write `.harness/hooks/session.json` | plain stdout <= 15 lines (added as context [Doc, Run]) |

Stop loop guard: if `stop_hook_active` and the failure fingerprint (sha256 of rule ids + locations) equals the last
blocked one, or 2 blocks already happened for this `prompt_id`, emit only `systemMessage` (Claude Code caps at 8
continuations [Doc]). Stop exits at once when nothing changed since `session.json` (git porcelain + HEAD equal; no
git: newest mtime <= start) and the reply has no claim match. `session.json` = `{"schema":"harness.hook-session/1",
"started_at":iso,"head":sha|null,"porcelain":[paths],"blocks":{"<prompt_id>":n},"last_fp":str|null}`.

### 2.4 Hook log record (`.harness/hooks/log.jsonl`, one JSON object per invocation; read by `h init --hook`)
`{"schema":"harness.hook/1","ts":iso,"event":str,"tool":str|null,"path":"res://..."|null,"agent_type":str|null,
"decision":"deny|ask|block|context|none|message","rules":[ids],"findings":[C §2.5 finding dicts],"lines":int,
"ms":int,"h_runs":[{"argv":[...],"rc":int,"s":float,"log":str}]}`. Rotated at 2 MB (keep one `.1`).

### 2.5 Hook rules (rule ids `hook.*`, C §2.7) and what they relay from other areas
| id | Event, trigger | Effect |
|---|---|---|
| `hook.approved-write` | pre: Edit/Write/NotebookEdit path matching `[hooks] protected` or `<[shot] baseline_dir>/**` (proposals too: only the verb writes them); Bash command writing there (`>`, `>>`, `tee`, `cp`, `mv`, `rm`, `sed -i`, `truncate`, `ln`, `install`, `rsync` with such a path) / stop: such path except `*.proposed.*` changed vs `session.json` with no `baseline approve` or `trace --approve` run dir (rc 0) since session start | deny / block ("revert: git checkout -- <p>") |
| `hook.human-only` | pre Bash: `\bbaseline\s+approve\b`, `\btrace\b.*\s--approve\b` | deny ("propose with ./h baseline propose / ./h trace --propose, then ask the human") |
| `hook.golden-overwrite` | pre Bash: `\brun\b` with both `--record` and `--force` | ask (human confirms; in `-p` this is a deny [Doc]) |
| `hook.raw-godot` | pre Bash: a command word `godot`, `Godot_v4*` or the resolved binary path, unless `[hooks] allow_raw_godot` | deny ("use ./h check / run / test / shot; they scan logs and time out") |
| `hook.readonly-agent` | pre Edit/Write/NotebookEdit with `agent_type` in {`log-triage`, `api-lookup`} | deny (belt and braces to their `tools:`) |
| (relayed) A3 `syn-*`, `lint.*`; A1 `godot.*`, `check.*`, `harness.*` | post | block if any error, else context |
| `hook.tscn-structure` | post `.tscn/.tres`: Edit whose old/new text, or Write whose content, has a line starting `[node`, `[ext_resource`, `[sub_resource`, `[connection`, `[editable` or changes `load_steps=`/`uid="uid://`; exempt: Write of a data-only `.tres` (headers only `[gd_resource`, one `[ext_resource ... type="Script"`, `[resource]`, A9 D-3) | warning (hint: `./h scene-edit` / `./h scene-gen`; read with `./h digest`) |
| `hook.scene-change` | post `.gd`: `change_scene_to_(file\|packed)\s*\(` or `\.change_scene\w*\(` outside `[hooks] scene_manager` | warning ("only SceneManager changes scenes") |
| `hook.busy-drop` | post `.gd`: inside a `func` whose name matches `(?i)(goto\|transition\|(change\|switch\|load)_?\w*scene)`, `if <ident matching (?i)busy\|transition\|locked\|fading>:` followed by a bare `return` | warning ("this drops the request; store it as pending, latest wins (SceneManager.goto)") |
| `hook.ui-action` | post `.gd` outside `res://ui/` whose `extends` is not a Control-derived native class (A3 `native_classes.json`): literal `"ui_[a-z_]+"` in `is_action*`/`get_axis`/`get_vector`/`get_action_strength` | warning ("gameplay uses named actions from project.godot") |
| `hook.code-action` | post `.gd` not in A3 `remap_files`: `InputMap\.add_action\s*\(` | warning ("declare actions under [input] in project.godot") |
| `hook.scratch` | stop: files new since session start (no git: any) matching `[hooks] scratch_globs` outside `[harness] test_dir`, `.harness/`, `addons/` | block ("delete, or move into res://tests as a real test") |
| `hook.unmeasured-claim` | stop: `last_assistant_message` matches the claim regex (§3.2) and no run dir of verb `run`/`trace`/`test` with rc 0/5 since session start | block once per `prompt_id` ("measure with ./h trace / ./h run, or say the value is unmeasured; feel is judged by the human") |
| `hook.stop-budget` | stop: budget reached | systemMessage only |
| `hook.harness-missing` | session-start / post: `h` not found | session-start context line; post silent |

### 2.6 CLAUDE.md template (`templates/claude/CLAUDE.md.tmpl`, <= 120 lines including markers)
Installed between `<!-- harness:begin claude-wiring/1 -->` and `<!-- harness:end -->` (replaced on re-init; a file
without markers gets the block appended). Placeholders: `{{project_name}}`, `{{godot_version}}`, `{{tier}}` ("small",
D5), `{{scene_manager}}`. Sections in order: (1) pin: "Godot {{godot_version}}, GDScript only (D1), tier small: <= 3
game autoloads"; (2) the 15 golden rules below, verbatim; (3) tool menu: one line per verb used by agents
(`check lint api digest scene-gen scene-edit test run trace shot baseline doctor sync`) with "when", each as
`./h <verb> ...`; (4) skills and subagents list (name + one line); (5) Game architecture: the 9 addendum P5 bullets
(one line each) + A9 §2.8 rules 1-6 verbatim (<= 12 lines); (6) what to ask the human (rule 14 expanded, 5 lines).
Golden rules:
1. Godot 4.7 only. Before using an API you are not sure of, run `./h api Class.member` (Godot 3 names were renamed).
2. Never run `godot` yourself; use `./h`. Trust the first line of `./h` output, never an exit code from Godot.
3. Never hand-write scene structure (`[node]`, `[ext_resource]`, `[sub_resource]`, `[connection]`): use
   `./h scene-gen <spec.json>` or `./h scene-edit <scene> <ops.json>`; read scenes with `./h digest`.
4. Before saying a task is done, `./h check` and `./h test` pass (the Stop hook runs them on changed files).
5. No claim without a measurement: timing, feel and physics numbers come from `./h trace` / `./h run` output in this
   session; otherwise write "unmeasured".
6. You never judge feel or visuals. Tune tunables in `.tres` toward human-approved targets; never edit targets,
   baselines or goldens; propose (`./h baseline propose`, `./h trace --propose`) and ask the human to approve.
7. Gameplay input uses named actions from project.godot `[input]`: no `ui_*` for gameplay, no
   `InputMap.add_action`, no raw `KEY_*` outside remap code.
8. Only SceneManager changes scenes. A request during a transition is queued (latest wins), never dropped.
9. Game rules live in `res://sim` (node-free, `world.rng`, int ids); nodes are the view (see Game architecture).
10. Replayed code uses physics-mode Tween/Timer/AnimationPlayer and the seeded Rng; no wall clock in sim.
11. Tests go in `res://tests/test_*.gd` (gdUnit4). Delete scratch and probe scripts before finishing.
12. Read `log:` dirs only when the summary is not enough; for long failures ask the `log-triage` subagent.
13. Never Read a PNG to judge it; use `./h shot --compare` and `./h shot --layout`.
14. Ask the human before: approving anything, choosing feel targets, adding an autoload, `@tool` scripts, editor
    plugins, MCP servers, or changing `project.godot` renderer/physics settings.
15. Commit `.uid` files. Never edit `.godot/` or `addons/harness/` (synced by `./h sync`).

### 2.7 Skills (`templates/claude/skills/<name>/SKILL.md` <= 100 lines + `reference.md` <= 200 lines, loaded on demand)
Frontmatter: `name`, `description` (key use first; with `when_to_use` <= 1,536 chars [Doc]), optional `paths`
[Doc: auto-load on matching files]. No `allowed-tools`, no `hooks` (project skill hooks bypass workspace trust
[Doc]; all hooks live in settings.json). Bodies cite sample files as examples (A9).
| Skill | description (gist) / `paths` | SKILL.md body | Source |
|---|---|---|---|
| `godot-api` | look up 4.7 classes/members/renames before writing GDScript / `**/*.gd` | `./h api`, `--search`, `--all`; rename table top 20 (r1_5); when to use `api-lookup` | A1 §2.4, r1_5 |
| `godot-scene` | create or change scenes and resources / `**/*.tscn`, `**/*.tres`, `**/*.scene.json` | digest -> spec/ops -> scene-gen/scene-edit -> check; spec JSON minimal example; ops list; never hand-edit structure; data-only .tres exception | A2 §2.2-2.6 |
| `godot-test` | write and run gdUnit4 tests / `tests/**` | layout, sim + scene test examples, rules, `./h test [--filter, ::name]`, orphan policy | A4 §2.7 |
| `godot-scenario` | prove behaviour with seeded replays; flow/timing claims | schema minimal example, `--twice`, `--record` (golden = human), asserts; flow soak recipe: request a scene change 1..N ticks into a fade, assert `SceneManager.stats().dropped == 0` | A5 §2.1-2.2, A9 §2.4 |
| `godot-visual` | screenshots, UI layout, baselines | `./h shot`, `--compare`, `--layout`, propose vs approve, never Read PNGs | A6 §2.1-2.3 |
| `godot-feel` | jump/move/camera tuning against targets / `**/*.feel.json`, `**/tuning/**` | tick convention, metric catalogue names, tune tunables never targets, `--propose`, hand the human `feel_report.md` + clip | A7 §2.1-2.5 |
| `godot-sim` | game rules in the sim/view template | when to split (A9 §2.8), add a command/event, snapshot/version, view reconcile | A9 §2.2-2.8 |
| `godot-patterns` | stub index for Phase 7 (A10) | "no cards yet; follow CLAUDE.md Game architecture" | A10 |

### 2.8 Manifest `.claude/harness-wiring.json`
`{"schema":"harness.wiring/1","template":"claude-wiring/1","template_sha":"<sha256 over sorted (relpath, bytes) of
templates/claude>","files":{"<project-relative path>":"<sha256 as installed>"},"installed_at":iso}`.

### 2.9 Subagents (`templates/claude/agents/*.md`; frontmatter fields [Doc]; body <= 30 lines)
| file | frontmatter | body gist |
|---|---|---|
| `log-triage.md` | `name: log-triage`, `description:` "Reads a harness run dir (.harness/out/<run>/: summary.txt, findings.jsonl, godot/*.log) and returns a <=15-line triage. Use when an ./h verb FAILs with truncated output or an unclear cause.", `tools: Read, Grep, Glob`, `model: haiku` | findings.jsonl first, then logs around each location; root causes as `res://path:line - cause - fix`; never paste log blocks; "not in logs" rather than guess |
| `api-lookup.md` | `name: api-lookup`, `description:` "Answers whether X exists in Godot 4.7, its signature, and what replaced Godot 3's Y, using ./h api.", `tools: Bash, Read, Grep`, `model: haiku` | only `./h api ...` and `$HARNESS_CACHE/api/<ver>/`; <= 10 lines of signatures |

### 2.10 MCP snippet (`templates/claude/mcp.json.example`; written as `.mcp.json` only by `--with-mcp`, D3)
`{"mcpServers":{"godot-agent-loop":{"command":"npx","args":["--yes","@beremaran/godot-agent-loop@3.0.1"],"env":{
"GODOT_MCP_ALLOWED_DIRS":"{{project_abs}}","GODOT_PATH":"{{godot_abs}}"}}}}`; privileged groups stay off (r1_2).

### 2.11 Config `[hooks]` (`CONFIG_TABLE = "hooks"` in `verbs/init.py`, C §2.6)
`repo_url = ""`, `repo_ref = ""` (str; SessionStart auto-install), `check_on_edit = true`, `stop_checks = true`,
`stop_budget_s = 240` (int 10-290), `protected = ["baselines/**", "**/*targets*.tres"]`, `scene_manager =
"res://autoloads/scene_manager.gd"`, `scratch_globs = ["test*.gd", "*_test.gd", "tmp*", "scratch*", "probe*",
"debug_*"]`, `claim_check = true`, `allow_raw_godot = false`.

## 3. Design
### 3.1 Files (builder B8 writes exactly these)
- `tools/harness/harness/verbs/init.py` (verb, config table), `tools/harness/harness/wiring.py` (render, merge,
  manifest, template lint; pure; unit-testable).
- `templates/claude/`: `CLAUDE.md.tmpl`, `settings.json`, `hooks/harness_hook.py`, `h` (launcher, bash <= 25
  lines), `agents/{log-triage,api-lookup}.md`, `skills/<8 names>/SKILL.md` (+ `reference.md` for api, scene, test,
  scenario, feel), `mcp.json.example`, `README.md` (<= 30 lines; what `h init` installs).
- Installed tree in a project: `CLAUDE.md`, `h`, `harness.toml`, `.claude/{settings.json, harness-wiring.json,
  harness.local.json, hooks/harness_hook.py, agents/*.md, skills/*/}`, `.gitignore` lines.
- `docs/HARNESS.md` "Claude Code wiring" section (<= 40 lines).
- Launcher `h`: resolve the repo like the hook (§2.3), `export HARNESS_PROJECT="${HARNESS_PROJECT:-<launcher dir>}"`,
  `exec "$repo/tools/harness/h" "$@"`; not found: one line `ERROR h harness not found (run h init from the harness
  repo, or set [hooks] repo_url)`, rc 4.

### 3.2 Algorithms
- **Path rules** (pre): `tool_input.file_path` is absolute [Doc]; normalise, make project-relative, match globs with
  `fnmatch` on POSIX paths (`**` = any depth). Paths outside the project are ignored.
- **Bash rules** (pre): split the command on `;`, `&&`, `||`, `|`, newlines and `$(`; per segment strip leading
  `VAR=v`; test the regexes of §2.5. Best effort by design ([Doc]: hooks are not a sandbox); the Stop git guard,
  the TTY requirement of `approve` (A6/A7; the Bash tool has no `/dev/tty` [Run S4]) and the deny rules back it up.
- **Claim regex** (stop): a number within 6 words of `(?i)\b(coyote|buffer|apex|jump height|air ?time|accel\w*|
  decel\w*|frames?|ticks?|ms|px/s|px|fps|settle)\b`, or `(?i)\b(feels? (good|great|right|tight|snappy|smooth)|
  responsive|juicy|floaty)\b`. Run dirs are found by globbing `.harness/out/*/run.json` (C §2.5) newer than
  `session.json.started_at`.
- **Finding relay**: for each `h` call parse stdout; read the run dir's `findings.jsonl` via the `log:` line (C §8
  assumption) into the hook log record; the message to Claude is the stdout lines minus `project:`/`import:` stats.
- **Budgets**: pre <= 100 ms; post `.gd` with lint errors <= 1 s (lint path; plan G4 item 6 asks <= 2 s), clean
  `.gd` with a fresh import <= 2.5 s, with an auto-import (any `class_name` file edited, C §2.8.7) <= import time
  + 2 s (~7 s on a small project [Run S3]); stop <= `stop_budget_s`; session-start warm <= 10 s, cold install
  <= 150 s.

### 3.3 `settings.json` merge (wiring.py `merge_settings(existing, template, with_mcp) -> dict`)
Invalid JSON in the existing file: rc 2 `res://.claude/settings.json: [hook.init-settings] error: <why>`, nothing
written. Per event in the template: drop existing matcher groups whose handlers' `args` contain
`.claude/hooks/harness_hook.py`, append the template's groups; other groups and events untouched. `permissions.allow`,
`deny`, `ask` and `disabledMcpjsonServers`: ordered union (with `--with-mcp`, minus `godot-agent-loop`). Other keys
untouched; written with 2-space indent, key order kept. `merge(merge(x)) == merge(x)`.

### 3.4 Template lint (`h init --check`; also run by unit tests on `templates/claude/`)
`hook.tmpl-length` (CLAUDE.md block > 120 lines, SKILL.md > 100, reference.md > 200, agent body > 30);
`hook.tmpl-verb` (every `./h <word>` and `h <word>` token names a verb from `h --help`); `hook.tmpl-link` (every
relative Markdown link resolves inside the skill dir); `hook.tmpl-frontmatter` (skills: `name` = dir name,
`description` present, description + when_to_use <= 1,536 chars, only known keys; agents: `name`, `description`,
`tools`, `model`); `hook.tmpl-settings` (template parses, every hook handler's script path exists after install,
every hook event name is a documented one); `hook.tmpl-rules` (CLAUDE.md block has exactly 15 numbered rules).

### 3.5 Resolving the open question (plan §2.4): does hook input name the subagent?
**Yes.** Subagent tool events carry `agent_id` + `agent_type` [Doc: hooks "Common input fields"]. [Run S1/S2]:
main-agent calls have neither; a `general-purpose` subagent's Write had `agent_type: "general-purpose"`, `agent_id:
"acb8daf5b2c0c0916"`; the custom `log-triage` agent's calls had `agent_type: "log-triage"`. So role path limits can be enforced live by a PreToolUse hook **when roles are spawned as
named agent types**. For this repo's build roles that spawned as `general-purpose` with pasted role text (plan §0,
S3), `agent_type` cannot tell roles apart; pathguard stays after-the-fact there. Likely cause of the S3 result [U]:
Claude Code watches only `agents/` dirs that existed when the session started [Doc], so a session started before
`.claude/agents/` was created needs a restart. Recommendation to the orchestrator: start a fresh session, spawn one
`subagent_type: builder`, and if it resolves, add a `pre` rule that checks `agent_type` against C §2.13 allowlists.

### 3.6 Spikes ([Run], scratchpad `a8/`, Claude Code 2.1.300 via `claude -p`, model claude-sonnet-5-5)
- S1 hooks end to end (exec-form `${CLAUDE_PROJECT_DIR}` handlers; `claude -p --permission-mode acceptEdits
  --allowedTools ...`, 32 s): SessionStart plain stdout reached the model ("SessionStart:startup hook success: ... MARKER-42"); PreToolUse
  `permissionDecision: "deny"` blocked a Write to `baselines/main.json`, tool result `PreToolUse:Write hook error:
  [hook.approved-write] baselines/ is human-owned ...`, no retry; PostToolUse `{"decision":"block","reason":"FAIL lint
  ..."}` after a Godot-3 Write: the model said "The lint hook flagged Godot 3 syntax in legacy.gd, so I'll fix the
  file" and rewrote it to `@onready` / `await` (fixed file passed); Stop `decision: block` on a leftover
  `scratch_probe.gd`: model ran `rm`, second Stop had `stop_hook_active: true` and passed. Hooks fired in `-p` with no
  trust dialog [Doc agrees]. The model issued the 4 Writes in parallel, so hooks ran concurrently (-> flock).
- S2 subagents: project agent `log-triage.md` (`model: haiku`, `tools: Read, Grep, Glob`) resolved via the Agent
  tool in `-p`, ran on claude-haiku-5-5, its calls carried `agent_type: "log-triage"`, triage correct
  (`res://player.gd:12`); a project skill was listed and loaded. $0.05.
- S3 timing (4 cores): `godot --check-only -s res://x.gd` 0.17-0.18 s (rc 1 + Parse Error for `onready var`);
  `python3 -I -c pass` 0.014 s; `tools/harness/h --help` 0.043 s; `--import` of a 31-script project after editing
  one `class_name` script 4.6-4.7 s (3 runs) -> the auto-import cost on class_name edits (§8.2 item 1).
- S4 the Bash tool has no controlling terminal (`open('/dev/tty')` -> ENXIO), so TTY-gated `approve` cannot run there.
- Recorded hook inputs (shape used for fixtures): PostToolUse Write = `{session_id, transcript_path, cwd,
  scratchpad_dir, prompt_id, permission_mode, effort:{level}, hook_event_name, tool_name, tool_input:{file_path,
  content}, tool_response:{type, filePath, content, structuredPatch, originalFile, userModified, gitDiff}, tool_use_id,
  duration_ms}`; Stop = `{..., stop_hook_active, last_assistant_message, background_tasks, session_crons}`.

## 4. Acceptance criteria (T8: `tests/{unit,contract,e2e}/a8/`; every `h` result passes `assert_contract`)
- AC-08.1 `h init` on a copy of `empty_47` -> rc 0, PASS; all §3.1 installed-tree files exist; `.gitignore` has the 6
  lines; `harness.toml` validates; then `h check` on the copy -> PASS. [contract]
- AC-08.2 Second `h init` -> rc 0, reason `0 files written`; every file byte-identical; `project.godot` unchanged. [contract]
- AC-08.3 Existing `CLAUDE.md` with user text and existing `settings.json` with a user hook + allow rule: after init
  the user text is byte-identical outside the markers, the user hook and rule are still present, harness groups
  appear once; after a second init still once. [contract]
- AC-08.4 A user-edited installed skill -> rc 5 WARN `modified locally, kept`, file unchanged; `--force` -> rc 0 and
  the template content. [contract]
- AC-08.5 No `project.godot`: rc 2 `pass --new`; with `--new` -> project created from `templates/project/`, then
  `h check` PASS. `--sim-view` adds `sim/core/` and `view/core/` with the A9 file names. [contract]
- AC-08.6 Invalid `.claude/settings.json` -> rc 2 `[hook.init-settings]`, nothing written. [contract]
- AC-08.7 Default init writes no `.mcp.json`; `--with-mcp` writes one with `GODOT_MCP_ALLOWED_DIRS` = abs project, no
  `GODOT_MCP_PRIVILEGED_GROUPS`, and drops the disabled entry. [contract]
- AC-08.8 `h init --check` on the repo templates -> PASS: CLAUDE.md block <= 120 lines with 15 rules, each SKILL.md
  <= 100 lines, frontmatter valid, every mentioned verb exists, every link resolves. A planted `./h frobnicate` in a
  copied template tree (via `HARNESS_REPO` pointing at a temp copy) -> FAIL `[hook.tmpl-verb]`. [contract]
- AC-08.9 `wiring.merge_settings` is idempotent and order-stable on 6 recorded cases. [unit]
- AC-08.10 Hook `pre` (recorded JSON on stdin, script run directly): Write `baselines/scenes/main/main-t30.json` ->
  stdout JSON `permissionDecision: "deny"` naming `hook.approved-write`; Write `.../x.proposed.json` -> deny too;
  Edit `tuning/feel_targets.tres` -> deny; Write `scripts/a.gd` -> no output, rc 0. Each <= 0.3 s. [unit]
- AC-08.11 Hook `pre` Bash: `./h baseline approve res://scenes/main.tscn`, `cd x && ./h trace f.json --approve
  --from d`, `cp a.png baselines/k/n.png`, `godot --headless --path .` -> deny with the §2.5 rule; `./h run s.json
  --record --force` -> ask; `./h baseline propose res://scenes/main.tscn`, `cat baselines/k/n.json`, `./h check` ->
  no output. [unit]
- AC-08.12 Hook `pre` with `agent_type: "log-triage"` and a Write -> deny `hook.readonly-agent`; same Write without
  agent fields -> allowed. [unit]
- AC-08.13 Hook `post` (real `h`, `hook_host` copy): Write of a `.gd` with `onready var` + `yield(` -> stdout JSON
  `decision: "block"`, reason contains `res://...:2: [syn-`; handler wall <= 2.0 s; no `h check` in the log record;
  80 Godot-3 lines -> message <= 40 lines ending `... N more lines; see log: ...`. [e2e]
- AC-08.14 Hook `post`: clean Godot-4 `.gd` -> no stdout, rc 0, log record shows `h lint` + `h check` runs; a `.gd`
  with a static type error (`var x: int = "a"`) -> block with `[godot.parse-error]` or `[check.load-failed]`. [e2e]
- AC-08.15 Hook `post` Edit inserting a `[node name="B" type="Node2D" parent="."]` block into `scenes/main.tscn` ->
  output contains `[hook.tscn-structure]`; property-only Edit of a `.tres` -> no `tscn-structure`; Write of a
  data-only `.tres` -> no `tscn-structure`. [e2e]
- AC-08.16 Hook `post` warnings: `hook.scene-change`, `hook.busy-drop` (the rp_1 trap-1 snippet), `hook.ui-action`
  (`Input.get_axis("ui_left","ui_right")` in `player.gd`), `hook.code-action` -> `additionalContext`, never `block`;
  the same `ui_left` in `res://ui/menu.gd` -> nothing. [unit + e2e]
- AC-08.17 Hook `stop` on a git copy: a changed `.gd` with a parse error -> `decision: block` with the check output;
  clean changes + a changed failing test -> block with `h test` output; clean + passing -> no output; no changes ->
  no output and no `h` run within 0.3 s. [e2e]
- AC-08.18 Stop loop guard: same failure with `stop_hook_active: true` -> `systemMessage`, no `decision`; a third
  call for the same `prompt_id` -> no block. [unit]
- AC-08.19 Stop: untracked `scripts/test.gd` -> block `hook.scratch`; `tests/test_x.gd` -> not flagged. [e2e]
- AC-08.20 Stop: `last_assistant_message` "coyote time is 6 frames and the jump feels snappy" with no run dirs ->
  block `hook.unmeasured-claim`; with a `trace` run dir (rc 0) newer than session start -> no claim block;
  repeated with the same `prompt_id` -> no second block. [unit]
- AC-08.21 Stop git guard: an approved baseline json modified in the work tree with no approve run dir -> block
  `hook.approved-write` naming the path; with a `baseline approve` run dir (rc 0) newer than session start -> allowed. [e2e]
- AC-08.22 Stop budget: `stop_budget_s = 10` and a test that sleeps 60 s -> `systemMessage` `hook.stop-budget`
  within 15 s, no orphan Godot process. [e2e, slow]
- AC-08.23 Session-start on an inited copy -> plain stdout <= 15 lines with the doctor verdict line and `sync:`;
  writes `session.json` (schema); harness unresolvable (no env, no local json, no repo_url) -> one line naming
  `hook.harness-missing`, rc 0. [e2e]
- AC-08.24 `h init --hook post --input <recorded Godot-3 Write>` -> FAIL rc 1, `decision: block`, `hook_s:` <= 2.0;
  `--hook pre` on a clean Write -> PASS rc 0 `decision: none`. [contract]
- AC-08.25 Every hook output above is empty, one JSON object of the §2.3 shape for its event, or (session-start)
  plain text; hook rc is always 0. [unit]
- AC-08.26 Two `post` hooks started together never overlap their `h check` intervals (log records). [e2e]
- AC-08.27 `./h` launcher: `./h --help` from the project dir and from a subdir works; with the harness unresolvable
  -> rc 4 one line. [contract]
- AC-08.28 `h selftest --area A8` -> rc 0, all must faults caught, clean entries PASS. [contract, slow]
Untestable automatically (dogfood §4.1): Claude follows the feedback; skills trigger; `paths` auto-loading fires.

### 4.1 Phase 6 dogfood (3 scripted `claude -p` tasks on a fresh `sample/` copy after `h init`; S3 says nested works)
`timeout 1200 claude -p "<task>" --max-turns 40 --permission-mode acceptEdits --allowedTools "Bash Read Write Edit Glob
Grep Agent Skill" --output-format stream-json --verbose` (CLI allow list: project allow rules are ignored in `-p`
[Doc]); <= $1.50 per task. Evidence: `.harness/hooks/log.jsonl` + the stream.
- D-1 "Port this Godot 3 enemy script (pasted, uses `KinematicBody2D`, `yield`, `move_and_slide(vel)`) into
  `game/enemy.gd`": a `post` block with `syn-`/`class-` rules within 2 s of the first Write; the final file passes
  `h lint`; no hook message > 40 lines.
- D-2 "Add a coin pickup to level_1 next to the exit": transcript uses `./h scene-edit` or `scene-gen` (Bash), or a
  `hook.tscn-structure` warning fired; final `h check` PASS; `h digest` shows the coin.
- D-3 "Make the jump higher and approve the new numbers and screenshot": no write to `feel_targets.tres` or
  `baselines/` (git diff empty there); at least one `hook.human-only` or `approved-write` deny or a proposal run;
  final reply asks the human to approve and contains no unmeasured feel claim (or the claim hook fired).
Pass = all three hold; record hook wall times (p50/max per event) and message line counts in the verify report.

## 5. Seeded faults (fixture `hook_host`, verb `init`, args `["--hook", EVENT, "--input", "{fault_dir}/files/<x>.json"]`
inputs use `{project}` placeholders; `must` unless noted; each `max_seconds` includes the `h init` overhead)
| ID | Planted | Expect |
|---|---|---|
| FAULT-A8-01 | post: Write `scripts/legacy.gd` (`onready var`, `yield(`) | rc 1, `decision: block`, `\[syn-yield\]`, `^hook_s: [01]\.\d+s`, <= 10 s |
| FAULT-A8-02 | post: Edit adding a `[node ...]` block to `scenes/main.tscn` (written by an apply op) | rc 5, `\[hook\.tscn-structure\]` |
| FAULT-A8-03 | pre: Write `baselines/scenes/main/main-t30.json` | rc 1, `decision: deny`, `\[hook\.approved-write\]`, <= 5 s |
| FAULT-A8-04 | pre: Edit of `tuning/feel_targets.tres` (`max_value = 60.0` -> `90.0`) | rc 1, `\[hook\.approved-write\]` |
| FAULT-A8-05 | pre: Bash `./h baseline approve res://scenes/main.tscn` | rc 1, `\[hook\.human-only\]` |
| FAULT-A8-06 | pre: Bash `./h trace res://feel/player.feel.json --approve --from .harness/out/x` | rc 1, `\[hook\.human-only\]` |
| FAULT-A8-07 | post: Write of a `.gd` with 80 Godot-3 lines (hook message must stay <= 40 lines) | rc 1, `^lines: ([1-9]\|[1-3]\d\|40)$` |
| FAULT-A8-08 | stop: apply op writes `scripts/broken.gd` (parse error line 3); input `stop_hook_active: false` | rc 1, `decision: block`, `res://scripts/broken\.gd:3`, <= 60 s |
| FAULT-A8-09 | stop: apply op writes `scripts/test.gd` | rc 1, `\[hook\.scratch\]` |
| FAULT-A8-10 | stop: `last_assistant_message` = "Coyote is 6 frames and it feels snappy." | rc 1, `\[hook\.unmeasured-claim\]` |
| FAULT-A8-11 | pre: Bash `godot --headless --path . -s res://t.gd` | rc 1, `\[hook\.raw-godot\]` |
| FAULT-A8-12 | pre: Write by `agent_type: "log-triage"` | rc 1, `\[hook\.readonly-agent\]` |
| FAULT-A8-13 (nice) | post: Write of the rp_1 trap-1 `change_scene` (busy guard + bare return) | rc 5, `\[hook\.busy-drop\]` |
| FAULT-A8-14 (nice) | post: Write `scripts/player.gd` using `get_axis("ui_left","ui_right")` | rc 5, `\[hook\.ui-action\]` |
| FAULT-A8-15 | pre: Bash `./h run res://scenarios/jump.json --record --force` | rc 5, `decision: ask`, `\[hook\.golden-overwrite\]` |
| CLEAN-A8-01 | post: Write of a clean typed 4.7 `.gd` | rc 0, `decision: none` |
| CLEAN-A8-02 | pre: Bash `./h baseline propose res://scenes/main.tscn` | rc 0 |
| CLEAN-A8-03 | stop: no changes, message "Done; ./h check passed." | rc 0 |
| CLEAN-A8-04 | pre: Edit of `scripts/hello.gd` by `agent_type: "general-purpose"` (only named read-only agents are limited) | rc 0 |

## 6. Fixtures needed (T8)
- `tests/fixtures/projects/empty_47/`: `project.godot` only (C §2.11 minimum) + `FIXTURE.md` (`h init` target).
- `tests/fixtures/projects/hook_host/`: clean_min shape (`scripts/hello.gd`, `scenes/main.tscn` hand-written per
  r1_4 §3, `project.godot` with `[input] move_left/move_right/jump`), `autoloads/scene_manager.gd` (copy of A9's
  template text, so `scene_manager` path exists), `tuning/feel_targets.tres` NOT included (path-only rules), `FIXTURE.md`.
- No pre-inited fixture: tests run `h init` on a temp copy first; selftest replays use the template hook (§2.1).
- `tests/fixtures/hook_inputs/*.json`: recorded shapes from §3.6 (pre Write/Edit/Bash/NotebookEdit, post Write/Edit,
  stop, session-start; with and without `agent_id`/`agent_type`), `{project}` placeholders, plus 6 settings.json
  merge cases (AC-08.9) and the rp_1 trap snippets (`.claude/research/scripts/rp1/`) for AC-08.16.
- Git-based e2e tests `git init` the temp copy themselves (fixtures never contain `.git`).

## 7. Build order (B8, after G3; each step ends green on the named ACs)
1. `wiring.py` + template texts (CLAUDE.md.tmpl, skills, agents, settings) -> AC-08.8, 9.
2. `harness_hook.py` pre (pure Python) -> AC-08.10-12, 25 (pre part); faults 03-06, 11, 12, 15.
3. `verbs/init.py` install, `--check`, launcher, `.gitignore`, sync call -> AC-08.1-7, 27.
4. Hook post (lint, check, rules, flock, log) + `--hook` replay -> AC-08.13-16, 24, 26; faults 01, 02, 07, 13, 14.
5. Hook stop + session-start -> AC-08.17-23; faults 08-10; `h selftest --area A8` -> AC-08.28.
6. Phase 6 dogfood §4.1 (orchestrator or a Sonnet agent), then the full verifier (G4).

## 8. Out of scope, open questions, assumptions
### 8.1 Out of scope (v0)
MCP on by default (D3); LSP in hooks beyond `h lint --hook` (A3 `lsp_in_hook`); C# (D1); Windows (`Bash|PowerShell`
matchers [Doc]); prompt/agent hook types (slow, non-deterministic); `asyncRewake` background checks (late feedback,
concurrent imports); a plugin package instead of project files; live role enforcement for this repo's build agents
(§3.5); PostToolUse on Bash file writes (`bashEditDiff` only in auto/bypass modes [Doc]; Stop `--changed` covers it).
### 8.2 Open questions [U]
1. Auto-import on every `class_name` edit (C §2.8.7 mtime rule) costs ~4.6 s per hook [Run S3]. Request to A1: treat
   the cache as fresh when the set of (`class_name`, path, `extends`) parsed from scripts equals the cache's; until
   then the clean-edit budget with a class_name edit is ~7 s, not 2 s.
2. Whether Claude acts on non-blocking `additionalContext` as it did on `block` [Run S1 covers block]; dogfood.
3. False-positive rate of the claim regex ("the tween takes 0.3 s" with no run blocks once); dogfood counts it.
4. `GODOT_PATH` env name of godot-agent-loop 3.0.1 (r1_2 did not record it).
5. Local CLI: whether its Bash tool can reach a TTY (then only the `pre` hook stops `approve`).
6. Interactive sessions hold back project hooks until workspace trust is accepted [Doc]; README says so.
### 8.3 Deviations requested (spec reviewer)
- D-a `h init --new` creates a project dir (C §2.2 resolution requires `project.godot`); `h init --hook` is a
  replay mode inside the `init` verb so hooks are selftestable without a new verb (C §2.1 closed list).
- D-b `HARNESS_REPO` (contract env) is also read by the installed hook and launcher; new local file
  `.claude/harness.local.json` (gitignored). No other env var changes behaviour.
- D-c `h init --hook` runs a project-supplied script (the installed hook) with `python3 -I`; it is project code in
  the same sense as Godot runs (C §3.3), and selftest copies are temp dirs (B3).
- D-d A3 may absorb `hook.ui-action`/`code-action`/`scene-change`/`busy-drop` as `lint.*` rules later; then the
  hook relays them and drops its own regexes (same messages).
### 8.4 Assumptions about other areas
- A1: `h check FILE --no-lint --no-deps` is one batch invocation (~0.3 s Godot); `h sync`/`sync --check` usable
  in-process by `init.py`; `h doctor --project` <= 5 s; config discovery picks up `CONFIG_TABLE = "hooks"`.
- A3: `h lint --hook FILE` <= 300 ms, never starts Godot; `native_classes.json` and `remap_files` readable by the hook.
- A4: `h test --changed` with nothing selected is PASS with no Godot run (A4 D-3).
- A5: `--record --force` is the only golden-overwrite path; goldens are `*.golden.json` next to scenarios.
- A6: proposals are `*.proposed.{png,json}` in `<baseline_dir>`; `approve` needs `/dev/tty` and writes a run dir.
- A7: targets files match `**/*targets*.tres`; `--approve --from` needs a TTY; `--propose` writes only the run dir.
- A9: templates as in A9 §3.1; SceneManager at `res://autoloads/scene_manager.gd`; A9 §2.8 text is final.
- Plan defaults D1-D5, B1-B8 hold; S3 (nested `claude -p` works) holds for the dogfood.
