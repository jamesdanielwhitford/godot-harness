area: A0 bootstrap      phase: build      state: done
spec: plan §4.1/§3.1 (no spec; phase exempt from writer/builder split)
tests: 4 total / 4 pass (tests/unit/bootstrap/test_doctor.py)   lock: n/a
done: tools/bootstrap.sh (--quiet --with-vulkan --with-dotnet; vulkan/dotnet paths untested), tools/harness/{h,pins.toml,requirements-dev.txt},
  python pkg harness (cli with verb auto-discovery, pins.py, verbs/doctor.py), .gitignore additions (.venv/ .harness/ tools/bin/)
  pins: godot sha256 0b1a6c54...cb73c, gdUnit4 v6.2.2 = 0127a55f4543dfc24746f6e5c7ba6f94105d51f2
  verified: cold bootstrap with empty HARNESS_CACHE (real download) 22s, rc 0, 12 lines; warm rerun idempotent; h doctor ok
next: step 9 (h sync/import sample) is skipped until those verbs exist; bootstrap runs it automatically when `h --help` lists sync
blockers: none     disputes: 0
notes: HARNESS_CACHE env overrides ~/.cache/godot-harness (used for scratch verification). gdUnit4 cloned from MikeSchulze URL
  (godot-gdunit-labs URL listed first in pins; fallback worked). Godot binary runs fine headless; doctor requires tools/bin/godot symlink.
