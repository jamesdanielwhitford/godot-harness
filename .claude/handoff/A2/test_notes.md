# A2 test notes (T2, Sonnet, 2026-10-15)

Spec: `.claude/plans/specs/02_scene.md` v2. Pathguard area `a2`. No harness/addons/templates/sample source was opened.

## Files
- Fixture `tests/fixtures/projects/scene_host/` (project.godot, scripts/, scenes/{child,complex,inh,ov,player,editor_style}.tscn,
  res/item.tres, addons/demo/demo.tscn, specs/{child,main,ov,child2,inherited,shapes}.scene.json, FIXTURE.md).
  Verified [Run] with the r1_4 `load_check.gd` on an imported scratch copy: all scenes load with no engine message; the
  `uid://buyc5ao4n1j03` in editor_style.tscn equals the hero.gd uid a fresh `--import` produced in two separate copies. The
  scene header uid `uid://dk3w2h5n7ra4q` is invented (not registered until the editor saves it).
- `tests/contract/a2/{a2util.py,conftest.py,test_a2_digest.py,test_a2_gen.py,test_a2_edit.py,test_a2_slow.py}`
- `tests/unit/a2/test_a2_model.py` (AC-02.34), `tests/e2e/a2/test_a2_e2e.py` (AC-02.33). No gd layer (spec has none).
- `selftest/faults/FAULT-A2-01..15` (14 must, 15 nice) and `selftest/clean/CLEAN-A2-01..03`. r1_4 c10/c13/c23 copied verbatim into `files/`.
  Contract tests read the r1_4 case copies from `tests/fixtures/r1_4_cases/` (T1's fixture, read-only use).

## AC coverage (99 tests collected)
AC-02.1,2,3,4,5,6,7,8,9,10 -> test_a2_digest.py; 11-21 -> test_a2_gen.py (15 is parametrized over 16 bad specs);
22-30 -> test_a2_edit.py; 31, 32 -> test_a2_slow.py (marked slow); 33 -> e2e; 34 -> unit. Untestable automatically: none.

## Red check [Run]
`.venv/bin/pytest tests/unit/a2 tests/contract/a2 tests/e2e/a2` : collection fine (99 tests). Result now: 9 failed, 90 errors.
Contract/e2e tests error in the `mkwarm` fixture with "`h import` rc=2 ... unknown verb 'import'" (only `doctor` exists), the unit
tests fail with `ModuleNotFoundError: harness.scenes`. No collection errors.

## Interpretation choices and [U] items (builder: dispute rather than guess)
1. AC-02.2 "same stdout except log:": the verdict line carries a `(1.2s)` timing, so tests strip it before comparing.
2. AC-02.17 wall limit: spec says <= 1 s, test allows 1.5 s (process start on a loaded box).
3. AC-02.23 rename: the spec text says `target=@Bee` follows, but no node in complex.tscn points at B (B.target is `@A`). The test adds a
   first op `set_prop . target={"$node":"B"}` and expects the root line to show `target=@Bee` after the rename.
4. AC-02.15 `scene.not-stored`: uses `props: {"name": "Other"}` ([Run] spike: `name` has usage 0). [U] the generator might call this
   unknown-property instead. All AC-02.15 findings must start with a JSON pointer (`/...`, `/ops/...` for edits).
5. AC-02.3: c10 message must contain `Nope/A`; c11/c12 only the word `B`.
6. AC-02.28: ids (`id="..."`, `ExtResource("...")`) are normalised before diffing because the engine regenerates ids on save (r1_4 §1);
   other diff lines must be the position line or contain `unique_id=`.
7. AC-02.27 "already broken dependent": test writes `scenes/dep_broken.tscn` (instance of child + a node under missing parent `Nope`).
   For the rename case `complex.tscn` and `inh.tscn` also depend on child.tscn; the test only requires a finding for ov.tscn.
8. AC-02.34: spec gives only the names `render, diff, expected, compare`. Tests assume `expected(before_digest, effects) -> digest` and
   `compare(expected, after) -> list of findings with "rule"`; missing node/prop/editable -> `scene.lossy-save`, extra node and
   reordered siblings -> `scene.unexpected-change` [U]. `diff(a, b)` returns falsy when equal. If the real signatures differ the
   builder writes test_disputes.md and a fresh test-writer adjudicates.
9. Digest `node:` stat values start with the root-relative path; `--node` subtree prints `Hurtbox`, `Hurtbox/HurtShape`.
10. Relative scene args (`scenes/x.tscn`) are tested once with cwd = project; all other tests use `res://` paths.
11. AC-02.31 budgets use median of 3; the 50-scene summary test writes 50 trivial scenes into the temp copy.
12. Fault FAULT-A2-11 hang spec saves to `res://gen/hang.tscn`; cleans live in `selftest/clean/` (contract 2.10), not `faults/`.
