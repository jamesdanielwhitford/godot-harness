area: A0b dev tools      phase: build      state: done
spec: none (plan sections 4.2, 5)
tests: tests/unit/devtools/test_devtools.py, 14 total / 14 pass (unittest-style, runs under pytest or python3 -m unittest)   lock: n/a (tests/LOCK.sha256 not yet written)
done:
- tools/dev/{_common,pathguard,lock_tests,check_lock,ci,verify_fresh_clone}.sh
- pathguard.sh <role> <area> <range|working-tree>; roles: orchestrator planner spec-reviewer test-writer builder verifier adjudicator; area matched case-insensitively against handoff/tests dir names; test-writer may add but not modify existing tests/fixtures files
- check_lock exit 3 = no lock file; ci.sh reports that as SKIPPED unless CI_REQUIRE_LOCK=1
- ci.sh exit: 1 any FAIL, 3 if nothing passed (all SKIPPED), else 0. Layers: check_lock, unit, contract, gd_host (h test), e2e, selftest; --quick = unit+contract only
- verify_fresh_clone.sh <branch> [dir]; remote = $VERIFY_REMOTE or origin
next: orchestrator runs lock_tests.sh after test-writers finish
blockers: none. Unrelated: tests/unit/bootstrap::test_doctor fails here (gdunit4/odiff not installed in this container)
disputes: 0
