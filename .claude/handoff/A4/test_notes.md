# A4 test notes (T4, Sonnet, 2026-10-15)

Written from spec 04_test_runner.md v2 + REVIEW.md (R-01, R-02, R-33, R-38, R-39, R-50, R-51). No tools/harness/**
or addons/harness/** source was opened.

## Files
- `tests/unit/a4/test_a4_gdunit_parsers.py` (AC-04.19, 14 tests; imports `harness.gdunit` lazily so a missing module fails per test, not at collection)
- `tests/contract/a4/{conftest.py,test_a4_h_test.py}` (AC-04.1-18, 20, 21; ~50 tests incl. parametrised)
- fixture `tests/fixtures/projects/gd_tests/` (counts verified by a raw gdUnit4 run: 55 cases = 4 + 1 + 50)
- recordings `tests/fixtures/gdunit/{fail,runtime_error,nested}.xml`, `{hang,orphan,all,broken}.log` (real gdUnit4 6.2.2 output, ANSI kept, scratch paths rewritten to /tmp/h/proj)
- `selftest/faults/FAULT-A4-01..11/` (11, all `must`), `selftest/clean/CLEAN-A4-01..02/`; fault `files/` texts were run raw through gdUnit4 for 01-06, 08 (line numbers and rc confirmed)

## AC coverage
All 21 ACs covered; none untestable. Test names `test_ac_04_<n>_<k>_...`. AC-04.20 is the slow selftest test.
Red-state run: all tests fail because verb `test` / module `harness.gdunit` do not exist (`unknown verb 'test'`, ImportError), collection has 0 errors (209 tests collected across tests/unit tests/contract at write time, others' areas included).

## Assumptions / [U]
- `parse_console` value shapes beyond the key list `counts, hung, orphans, lines` are [U]; the unit tests search a JSON dump for `test_forever`, `test_leaks_node`, `55` and only assert truthiness of `hung`/`orphans`. `lines` must be a list of ANSI-stripped strings.
- runtime_error.xml: the body names `res://scripts/buggy.gd:6` in this recording (the spec text says scenes/); the test accepts either dir but requires the game file, never the test file.
- `gdunit4:` stat on a warm copy is `v6.2.2 present, rc <N>` (AC-04.2/4); on the very first run of a fresh copy it is `installed (was missing)`.
- AC-04.16 copies are made git repos with a `.gitignore` of `.godot/ .harness/`; the wall <= 1 s bound includes Python start-up.
- AC-04.9 `/tmp` outside-project case relies on the pytest tmp dir being under /tmp (an ancestor of the project, not inside it).
- Session-scoped `gd_warm` runs a real `h test` once; if that fails every gdp-based test errors with a clear message.
