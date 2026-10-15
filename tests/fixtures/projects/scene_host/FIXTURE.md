scene_host: host for A2 (digest, scene-gen, scene-edit); scenes hand-written per r1_4 section 3, specs/ hold *.scene.json.
Owner: A2/T2. Expected `h check`: PASS (editor_style.tscn uid values verified by `h check` on a fresh copy).
Specs save under res://gen/ (child2, inherited, shapes) or to paths that do not exist yet; ov/child/main specs target scenes/ copies in tests.
Broken inputs (r1_4 c08, c10-c13, c18, c23) live in tests/fixtures/r1_4_cases/ and selftest/faults/*/files/, never here.
Never import the repo copy (B3).
