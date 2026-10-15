# A1 test disputes (builder B1)

## D-1 `test_ac_01_3_all_24_at_once` (tests/contract/a1/test_a1_check.py), AC-01.3

Claim in the test and spec: 24 parse-broken scripts "cannot fit" in 40 lines, so `r.trunc is not None` is required.

Observed [Run]: the 24 snippets (+ c20) give 30 distinct `godot.parse-error` findings (c05, c15, c24, d01 each produce
2-3 errors on the same line, e.g. `Invalid argument for "connect()" function ...` and `Cannot pass a value of type "String" as "int"`).
Output = verdict + `project:` + `import:` + `files:` + `phases:` + 30 finding lines + `log:` = 36 lines <= 40.
Contract C 2.3 truncates only when the lines do not fit, so a truncation line would be a contract violation here.
Everything else in the test passes (24 distinct error paths, no finding for c20, rc 1, wall <= 10 s, <= 40 lines).

Proposed fix: replace the last assertion by
`assert len(r.lines) <= 40` and `assert (r.trunc is not None) == bool(r.run_json()["truncated"])`
(or require truncation only when `findings_total` exceeds the room: `r.trunc is not None or len(r.lines) <= 40`).

Resolution: test fixed. Contract 2.3 prints a truncation line only "if needed"; 36 lines fit in 40, so none is correct. Last assertion now: len(lines) <= 40 and (trunc line present) == run.json truncated. AC text unchanged (its "with a truncation line" reads as conditional).
