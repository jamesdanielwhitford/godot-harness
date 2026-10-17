area: A2 scene      phase: build      state: done
spec: .claude/plans/specs/02_scene.md @ uncommitted (v2)
tests: 99 total / 96 pass / 3 fail (AC-02.20 x2, AC-02.28; all disputed, see test_disputes.md)      lock: n/a
updated: 2026-10-17 by builder B2 (claude-sonnet-5-5)
done:
- verbs digest, scene-gen, scene-edit; scenes/{schema,model,pipeline}.py; runners scene_digest/gen/edit + _scene_lib.gd
- h selftest --area A2: 18/18 (15 faults caught, 3 clean pass)
- unit/a2 7/7, contract/a2 digest 18/18, gen 31/33, edit 34/35, slow 6/6, e2e 1/1
next:
- adjudicator: D-1 and D-2 in test_disputes.md
- tools/dev/ci.sh --quick not run by B2
blockers:
- none
disputes: 3 open (D-1 covers 2 tests, D-2 covers 1)
