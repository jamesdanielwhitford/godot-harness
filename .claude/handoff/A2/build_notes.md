# A2 build notes (builder B2, Sonnet, 2026-10-17)

## Built
- `tools/harness/harness/verbs/{digest,scene_gen,scene_edit}.py` (digest owns `CONFIG_TABLE = "scene"`, key `project_exclude`).
- `tools/harness/harness/scenes/{__init__,schema,model,pipeline}.py`.
  - `schema.py`: stdlib validator for specs (2.4) and ops (2.5); JSON syntax errors carry the line.
  - `model.py`: public `render, diff, expected, compare` (pure); also `parse_text` (header uid/format/ext uids/deps/editable from
    the file text), `verify_gen`, `change_lines`, `stale_names`.
  - `pipeline.py`: target resolution, digest runner calls + assembly, dependents scan, backup/rollback (`artifacts/backup`,
    `artifacts/rejected`), pre/post `checkrun.load_check` split, `emit_stats` (40-line cap with `more:` + full file in artifacts).
- `addons/harness/runners/{scene_digest,scene_gen,scene_edit}.gd` and the shared library `_scene_lib.gd` (REVIEW R-12 allows a
  `_`-prefixed library loaded with `load()` from an absolute path; the path is passed as `--lib`, because a `-s` runner's own
  `resource_path` is `res://../...` outside the project).

## Design choices worth knowing
- Value rendering (2.6) and layer names happen in GDScript (`_scene_lib.render*`), where the real Variants are; Python only formats.
- Header uid / ext uids / deps / `[editable]` come from the file text (SceneState does not expose editable instances).
- `is_default` of a set value is read from the packed state in memory after `pack()` (property absent = engine says default).
- Edit effects (`add/remove/move/set/conn+/conn-/group+/group-/editable+/script`) drive `model.expected`; compare is per-parent for
  sibling order. Empty override entries are normalised away on both sides (the engine does not write them).
- Ownership for `instance-internal`: `node.owner == root` and the path is not in the base-scene chain (MAIN_INHERITED gives
  inherited nodes `owner == root`).
- scene-edit does the only text rewrite (ext_resource `uid=` re-attach) inside the runner, after `ResourceSaver.set_uid`.
- Check-line names in multi-spec gen are project-relative (`gen/a.tscn`), see test_disputes D-1.
- `scene.breaks-dependent` message starts with the dependent path (FAULT-A2-10 regex needs it after the rule id).
- Runners treat an uncompilable `--lib` as rc 2 instead of hanging (`can_instantiate()` check); GDScript warnings are errors for
  runner files (`INFERENCE_ON_VARIANT`), so explicit types are required when calling into the lib.

## Not done / not verified
- Transitive dependents, `.tres` editing, binary scenes, new uids (spec 8.1 out of scope).
- Connections from/to nodes inside instances are not restricted; lossy-save would report a dropped one.
- `index` of `add_node` inside instance-internal parents is only approximated in the expected model (prev-sibling names).
- A1 files were not modified.

## Test status
See `status.md` for exact counts.
