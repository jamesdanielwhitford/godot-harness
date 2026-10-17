# A4 build notes (builder B4, Sonnet, 2026-10-17)

## Built
- `tools/harness/harness/verbs/test.py` (`h test`, `[test]` config), `tools/harness/harness/gdunit.py` (public:
  `parse_results`, `parse_console`; private: target resolution, suite listing, `--changed`, did-you-mean).
- Flow follows spec 3.2 except: selection (usage errors) runs before `sync.install_gdunit4`, so a typo never installs the addon.
- Orphan nodes counted from the console summary; hung test only recorded when the run timed out.

## Touched A1 files (unavoidable)
- `out.py`: `Run.max_lines` (default 40) passed to `render`; `h test` sets 15 (spec D-2).
- `sync.py`: cache-missing message is now `gdUnit4 not found in <cache> (run tools/bootstrap.sh)` (AC-04.11 wording, spec A-1).
- `godot.py` `project_classes`: regex accepts annotations before `class_name` (`@abstract class_name X`) and scans 200 lines
  instead of 50. gdUnit4 6.2.2 has such classes (class_name at line 52), which made import staleness report
  `stale class cache` on every run once the addon was installed.

## Not verified / known
- FAULT-A4-05 and test_ac_04_3_1 are flaky under load, see test_disputes.md D-1.
- Perf ACs (3 s for one suite, 5 s for 50 tests) pass on an idle machine; under full-suite load AC-04.12 was seen to take 4.5 s once.
