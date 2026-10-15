# A0b fixups notes
- C5 pathguard.sh: area arg may be a comma list; allowed() loops allowed_for() per area (lowercased).
  test-writer: selftest/faults/fault-<a>-*, selftest/clean/clean-<a>-* (matched on lowercased path);
  a1 only: tests/conftest.py, tests/helpers/*. builder: a1 only tools/bootstrap.sh.
- C6 _common.sh: lock_manifest prunes .harness.
- C7 ci.sh: run_layer treats rc 5 as PASS (detail notes warnings); gd_host copies fixture to
  ${HARNESS_TMP:-$ROOT/.harness/tmp}/gd_host_<ts> and runs h test --project on the copy.
- C10 .gitignore: added sample/addons/gdUnit4/, sample/addons/harness/, reports/.
- Tests: PathguardAreasTest (4 cases) + LockTest.test_harness_dir_ignored in tests/unit/devtools/test_devtools.py.
- Not committed.
