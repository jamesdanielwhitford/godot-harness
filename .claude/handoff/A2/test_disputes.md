# A2 test disputes (builder B2, 2026-10-17)

## D-1 AC-02.20: check-line names cannot be `res://...` paths (2 tests)
- Tests: `tests/contract/a2/test_a2_gen.py::test_ac_02_20_two_specs_second_instances_first` and
  `::test_ac_02_20_first_broken_second_skipped`.
- They compare the check-line name with `"res://gen/a.tscn"` (`{c[1] for c in ok} == {"res://gen/a.tscn", ...}`,
  `st.get("res://gen/a.tscn") == "FAIL"`).
- Why wrong: `helpers/h.py` parses check lines with `RE_CHECK = ^(OK|FAIL|SKIP|WARN) +([^:]+): (.*)$` (contract 2.3: "the
  name has no colon"). `res://gen/a.tscn` contains a colon, so a line `OK   res://gen/a.tscn: created` does not parse as a
  check line at all (it would fail `assert_contract` as an unknown line form), and `c[1]` can never equal a `res://` path.
  Spec 02_scene.md section 2.2 wrote `OK   <res path>: ...`, which contradicts the contract grammar.
- Implemented: the name is the project-relative path (`gen/a.tscn`), lines `OK   gen/a.tscn: created, 2 nodes`,
  `FAIL gen/a.tscn: 1 error, nothing written`, `SKIP gen/b.tscn: an earlier spec failed`. Behaviour (two OK lines, FAIL then
  SKIP, nothing written) is exactly what both tests intend.
- Proposed fix: compare `c[1]` with `"gen/a.tscn"` / `"gen/b.tscn"` (or `endswith`).

## D-2 AC-02.28: the diff assertion rejects the `-` side of engine `unique_id` additions (1 test)
- Test: `tests/contract/a2/test_a2_edit.py::test_ac_02_28_editor_style_uids_survive`.
- The loop `assert "unique_id=" in d or d[1:].startswith("position = ")` runs over both `+` and `-` diff lines. Godot 4.7
  adds ` unique_id=NNN` to every `[node ...]` header on any engine save (spec 8.2-1 accepts this noise). The original
  fixture has no `unique_id`, so the changed header lines appear as `-[node name="EditorStyle" type="Node2D"]` (no
  `unique_id=`) and `+[node ... unique_id=123]`. The `-` lines can never contain `unique_id=`.
- What does hold (verified by the test's own earlier asserts, which pass): header `uid=` unchanged, every ext `uid=`
  unchanged; the only other differences are the position line and `unique_id=` additions.
- Not implemented: stripping `unique_id` from the saved text. That would be a second text rewrite beyond the one R-21 allows
  and would change engine data.
- Proposed fix: strip ` unique_id=\d+` from both texts inside `_norm_ids` (or only look at `+` lines).

## Deviation (not a dispute): `scene.breaks-dependent` message
FAULT-A2-10 expects `\[scene\.breaks-dependent\].*ov\.tscn` on one line, i.e. the dependent path must appear after the rule id.
Spec 2.3 shows the dependent only in the location. The message is therefore
`<dependent> breaks, new after edit of <target>: <engine message>` (location unchanged).
