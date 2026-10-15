gd_host: host project for in-engine gdUnit4 suites of addons/harness; no tests of its own. Owner: P0/T1 (R-39).
Declares the 4 harness autoloads; `h sync` must run before anything loads it (used only through tests/helpers/gd.py).
Expected `h check` before sync: FAIL (autoload files missing); after `h sync`: PASS.
