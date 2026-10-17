# A3 build notes (builder B3, Sonnet, 2026-10-17)

## Built
- `tools/harness/harness/verbs/{lint,lsp}.py`; package `harness/lint/` with `__init__` (run_lint, lsp_diag), `rules`, `scan`,
  `project`, `checks`, `suppress`, `oracle`, `lsp_client`, `lsp_daemon`.
- `tools/harness/rules/{lint_rules.json,native_classes.json,builtin_actions.json,build_lint_data.py}` (1219 regex rules =
  1213 r1_5 + 6 lint.*; code-only rules (input-action, signal-name, indent-mixed, det-idle-*) live in `rules.CODE_RULES`;
  `rules:` stat counts all ids incl. lsp/oracle ids = 1230).
- Touched A1 file `out.py` (unavoidable): `finding_line` now turns hint newlines into ` / ` and cuts stdout hints to 100 chars
  (`...`), findings.jsonl keeps them whole (AC-03.9). A1/A2/P0 tests still pass.

## Choices
- Regex pass: anchor index by identifier set plus a whole-text MULTILINE prefilter before the per-line search (speed).
- Det rules: file in sim_dirs -> error, in replay_dirs -> warning, else skipped; exemptions checked before scope.
- Unknown lint-ignore ids -> lint.bad-suppress; suppressed findings kept as info `suppressed: ...`.
- LSP: one TCP connection per file; state file under `$HARNESS_CACHE/lsp`; start via `godot.spawn`.
- Oracle copies files to `$HARNESS_TMP/oracle-<run id>/f<i>_<name>`; line found by matching the old text.

## Not verified
- Performance of AC-03.7 passes here (macOS), budgets are machine dependent. Disputes: see test_disputes.md (D-1, D-2).
