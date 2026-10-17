# A3 test disputes (builder B3)

## D-1 test_ac_03_15_inherited_native_signal_is_known and test_ac_03_15_unresolvable_base_is_skipped (AC-03.15)
Both assert rc == 0 for a file containing `emit_signal("pressed")` / `emit_signal("whatever")`. Spec 6.1 row c18 requires the
hand rule `syn-yield-signal-string-emit` (warning, regex `\bemit_signal\s*\(\s*"`) to fire on every string emit, so these files
give rc 5 (warning only). No lint.signal-name finding is produced (that part of the assertion holds). Proposed fix: assert
`not lint_findings(r, "lint.signal-name")` and `r.rc in (0, 5)` (or no error findings).

## D-2 test_ac_03_25_diag_finds_parse_error_and_clean_file_and_speed (AC-03.25)
The "5 clean files" include `scripts/base.gd` (`signal died`, never used). Godot's LSP reports the real GDScript warning
`(UNUSED_SIGNAL)` (severity 2), which spec 2.2 maps to a `lint.lsp` warning, so rc is 5, not 0. Everything else in the test
passes (bad.gd line 4, player.gd PASS, wall 0.3 s). Proposed fix: use files without unused signals, or assert rc in (0, 5)
and no error findings.
