# 02 Scene generator, editor and digest (A2)

Status: spec v1, 2026-10-15, Opus planner P2. Conforms to `00_contract.md` (cited as "contract §x"); deviations are
listed in §8.3. Tags: [Run] verified in §3.7 spikes (Godot 4.7.stable.official.5b4e0cb0f), [U] unverified.

## 1. Purpose and failure modes covered
Make scenes readable as text and writable only through the engine, with every write verified.
- **F3** hand-editing `.tscn`: `h scene-gen` (spec -> engine-built scene) and `h scene-edit` (ops on a
  `GEN_EDIT_STATE_MAIN` round-trip) replace hand edits; R1.4 rules 1-20 are enforced by construction.
- **F4** node paths: `h digest` prints real root-relative paths (`A/Inner/Extra`, `%unique`).
- **F5** signal wiring: digest lists every `[connection]`; `connect` ops validate signal + method.
- **F6** uid refs: edits keep the scene uid and ext_resource `uid=` attributes that a script save drops [Run].
- **F10** layers: digest prints `collision_layer`/`collision_mask` as named layers.
- **F11** output: contract §2.3 (<= 40 lines), full digest on disk.
- **R1.4 silent group** (c01, c02, c15, c26, d06, own_a, d04, mod0): generator rejects unknown props, wrong value
  types, duplicate names; writes `node_paths`; owner rule; `[editable]`; MAIN edit states; and a post-write
  expected-vs-actual digest check, because `pack()`/`save()` return OK for lossy results (rule 14).
- **D4**: no visual judgement here; scenes are checked structurally only.

## 2. Interfaces

### 2.1 `h digest`
```
h digest [--project DIR] <scene.tscn|res.tres> [--node PATH] [--expand] [--json] [--strict]
h digest [--project DIR] --project-summary [--json]
```
- Target: `res://...` or a filesystem path inside the project (cwd-relative). Missing file, not `.tscn`/`.tres`,
  outside the project, or both a target and `--project-summary`: rc 2 `ERROR digest usage: ...`.
- `--node PATH` prints only that node and its subtree (`PATH` root-relative, or `%Name`); unknown: rc 2.
- `--expand` also prints nodes inside instances (from the instantiated tree), marked `(from <res://scene>)`.
- `--json` writes `artifacts/digest.json` (§2.7) and adds stat line `json: <path>`; stdout keeps the same grammar.
- Always writes `artifacts/digest.txt` (all lines, uncut) and `artifacts/digest.json`.
- rc: 0 clean; 1 load errors, vanished nodes or failed instantiate; 2 usage; 4 env; 5 warnings only.

Stat lines (contract §2.3 grammar, in this order): `project:`, `import:`, `scene:` (or `resource:`), `inherits:`
(inherited scenes only), one `node:` per node in file order, one `conn:` per connection, `editable:` (comma list,
if any), `deps:` (comma list). If content lines exceed the room left (40 minus verdict, fixed stats, findings, log),
the last kept stat is `more: <K> lines in <run dir>/artifacts/digest.txt`.
Node line: `node: <path> <kind>[ %unique][ groups=a,b][ script=res://x.gd][ <prop>=<value>]...[ !vanished]`
- `<path>`: `.` for the root, else root-relative (`A/Inner/Extra`), as accepted by `get_node()` from the root.
- `<kind>`: class name; `<res://child.tscn>` for an instance; `(override)` for an entry that only overrides an
  inner node of an instance or inherited base.
- Props: only those stored in the file (non-default), in file order; values per §2.6 rendering, each cut to 60
  chars with `...`; `collision_layer`/`collision_mask` (2D and 3D physics) render as `world|player|#5` using
  `layer_names/*` from `project.godot` (`#N` for an unnamed bit).
- Conn line: `conn: <from>.<signal> -> <to>.<method>[ flags=N][ binds=<var_to_str>]`, flags shown only if != 2.
`.tres` target: `resource: res://x.tres type=<Class>[ script_class=<Name>]` then `prop: <name>=<value>` lines.

`--project-summary`: stats `project:`, `name:`, `main_scene:`, `autoload: <Name> <res://path>` each,
`action: <name> <event as_text>, ...` for each key of the `[input]` section of `project.godot`,
`layers-<kind>: 1=world 2=player` for each non-empty `layer_names/<kind>/*` group, `scenes: <n>`, then
`scene: <res path> <root kind> nodes=<n>` per `.tscn` (sorted; excluding hidden dirs, `.godot/`, and
`[scene] project_exclude`), then `more:` if cut.

Literal examples (fixture `scene_host`, §6):
```
$ tools/harness/h digest --project /tmp/h/scene_host scenes/complex.tscn
PASS digest res://scenes/complex.tscn: 7 nodes, 2 connections (0.6s)
project: /tmp/h/scene_host
import: fresh
scene: res://scenes/complex.tscn format=3 uid=none
node: . Node2D script=res://scripts/hero.gd
node: A <res://scenes/child.tscn> position=Vector2(100, 0)
node: A/Sprite (override) position=Vector2(50, 50)
node: A/Inner/Extra Marker2D
node: B Node2D groups=g1,g2 script=res://scripts/hero.gd target=@A
node: Area Area2D groups=zone collision_layer=world|player
node: Area/Shape CollisionShape2D shape=RectangleShape2D{size=Vector2(10, 20)}
conn: A.hit -> B._on_hit
conn: Area.area_entered -> ._on_hit flags=3
editable: A
deps: res://scenes/child.tscn, res://scripts/hero.gd
log: /tmp/h/scene_host/.harness/out/20261015T150102Z-digest-1a2b/

$ tools/harness/h digest --project /tmp/h/x res://broken/bad_parent.tscn
FAIL digest res://broken/bad_parent.tscn: 1 vanished node (0.5s)
project: /tmp/h/x
import: fresh
scene: res://broken/bad_parent.tscn format=3 uid=none
node: . Node2D
node: Nope/A Node2D !vanished
res://broken/bad_parent.tscn: [scene.vanished-node] error: node 'Nope/A' is dropped at load: parent 'Nope' does not exist (hint: parent= is root-relative and never includes the root name)
-: [godot.parent-vanished] error: Parent path './Nope' for node 'A' has vanished when instantiating: 'res://broken/bad_parent.tscn'.
log: /tmp/h/x/.harness/out/20261015T150110Z-digest-77aa/
```

### 2.2 `h scene-gen`
```
h scene-gen [--project DIR] <spec.json>... [--force] [--strict]
```
Each spec (§2.4) is generated in the given order (so a later spec may instance an earlier one). Per spec: validate
(Python, no Godot) -> build in the engine -> save -> verify (§3.3) -> keep or roll back. The first failing spec stops
the run; later specs get `SKIP` check lines and are not written.
- Target exists and no `--force`: rc 2 `ERROR scene-gen usage: res://x.tscn exists (use --force)`, nothing written.
- With `--force` on an existing file: the old scene's uid is kept, output shows `change:` lines vs the old digest,
  and direct dependents are re-checked (§3.4).
- Stat lines: `project:`, `import:`, `saved: <res path>|none[ (rolled back)]`, `uid: kept <uid>|none`, then either
  `node:`/`conn:` lines of the new scene (new file) or `change:` lines (overwrite). With several specs: one check
  line per spec `OK   <res path>: created|replaced, <n> nodes` / `FAIL ...` / `SKIP ...`, and no node lines.
- rc: 0 all written and verified; 1 any semantic error or failed verification (that scene not written or restored);
  2 JSON/schema/usage error (no Godot run at all); 4 env; 5 written with warnings only.
```
$ tools/harness/h scene-gen --project /tmp/h/scene_host /tmp/specs/bad.scene.json
FAIL scene-gen 2 errors, nothing written (1.2s)
project: /tmp/h/scene_host
import: fresh
saved: none
/tmp/specs/bad.scene.json: [scene.unknown-property] error: /root/props/positoin: Node2D has no property 'positoin' (hint: position)
/tmp/specs/bad.scene.json: [scene.unknown-type] error: /root/children/0/type: unknown class 'Spirte2D' (hint: Sprite2D)
log: /tmp/h/scene_host/.harness/out/20261015T150200Z-scene-gen-0c1d/
```

### 2.3 `h scene-edit`
```
h scene-edit [--project DIR] <scene.tscn> <ops.json> [--strict]
```
Applies all ops (§2.5) in order to one instantiated copy (`GEN_EDIT_STATE_MAIN`, or `_MAIN_INHERITED` when the
scene has a base state), then saves once. All-or-nothing: any op error -> nothing written. Refuses an input scene
whose pre-check has any error finding (`scene.broken-input`), because MAIN-state instantiation silently re-parents
vanished nodes to the root as `Parent#Name` [Run]; fix such scenes by regenerating or by a minimal hand fix + digest.
- Stat lines: `project:`, `import:`, `saved: <res path>|none[ (rolled back)]`, `uid: kept <uid>|none`,
  `dependents: <n> checked`, then `change:` lines:
  `change: + <path> <kind>` / `change: - <path>` / `change: > <old> -> <new>` (reparent or rename) /
  `change: ~ <path> <prop>: <old> -> <new>` / `change: + conn <conn>` / `change: - conn <conn>` /
  `change: + group <path> <g>` / `change: - group <path> <g>` / `change: + editable <path>`.
- rc as `scene-gen` (rc 2 also for: scene missing or not `.tscn`, ops JSON/schema error).
```
$ tools/harness/h scene-edit --project /tmp/h/scene_host scenes/child.tscn /tmp/ops/rename.json
FAIL scene-edit 1 error, rolled back (2.9s)
project: /tmp/h/scene_host
import: fresh
saved: none (rolled back)
uid: none
dependents: 2 checked
change: > Sprite -> Body
res://scenes/ov.tscn: [scene.breaks-dependent] error: new after edit of res://scenes/child.tscn: Node './A/Sprite' was modified from inside an instance, but it has vanished.
log: /tmp/h/scene_host/.harness/out/20261015T150300Z-scene-edit-9e1f/
```

### 2.4 Scene spec (`*.scene.json`, JSON Schema draft 2020-12; Python validates it with stdlib code)
```json
{"$id":"harness.scene-spec/1","type":"object","required":["save","root"],"additionalProperties":false,
 "properties":{
  "schema":{"const":"harness.scene-spec/1"},
  "save":{"type":"string","pattern":"^res://(?!\\.godot/|\\.harness/)[^\\s\"]+\\.tscn$"},
  "root":{"$ref":"#/$defs/node"},
  "overrides":{"type":"object","additionalProperties":{"$ref":"#/$defs/props"}},
  "extra_nodes":{"type":"array","items":{"allOf":[{"$ref":"#/$defs/node"},{"required":["parent"]}]}},
  "connections":{"type":"array","items":{"$ref":"#/$defs/conn"}}},
 "$defs":{
  "name":{"type":"string","minLength":1,"pattern":"^[^./:@%\"]+$"},
  "path":{"type":"string","minLength":1},
  "node":{"type":"object","required":["name"],"additionalProperties":false,
   "properties":{"name":{"$ref":"#/$defs/name"},"type":{"type":"string","pattern":"^[A-Za-z_][A-Za-z0-9_]*$"},
    "instance":{"type":"string","pattern":"^res://.+\\.tscn$"},"parent":{"$ref":"#/$defs/path"},
    "script":{"type":"string","pattern":"^res://.+\\.gd$"},"props":{"$ref":"#/$defs/props"},
    "groups":{"type":"array","items":{"type":"string","minLength":1},"uniqueItems":true},
    "unique_name":{"type":"boolean"},"index":{"type":"integer","minimum":0},
    "children":{"type":"array","items":{"$ref":"#/$defs/node"}}},
   "oneOf":[{"required":["type"]},{"required":["instance"]}]},
  "props":{"type":"object","propertyNames":{"pattern":"^[A-Za-z_][A-Za-z0-9_/:]*$"},
   "additionalProperties":{"$ref":"#/$defs/value"}},
  "value":{"oneOf":[{"type":["boolean","number","string","null","array"]},
   {"type":"object","required":["$var"],"additionalProperties":false,"properties":{"$var":{"type":"string"}}},
   {"type":"object","required":["$res"],"additionalProperties":false,"properties":{"$res":{"type":"string","pattern":"^res://"}}},
   {"type":"object","required":["$node"],"additionalProperties":false,"properties":{"$node":{"$ref":"#/$defs/path"}}},
   {"type":"object","required":["$new"],"additionalProperties":false,
    "properties":{"$new":{"type":"string"},"props":{"$ref":"#/$defs/props"}}},
   {"type":"object","required":["$layers"],"additionalProperties":false,
    "properties":{"$layers":{"type":"array","items":{"type":["string","integer"]}}}}]},
  "conn":{"type":"object","required":["from","signal","to","method"],"additionalProperties":false,
   "properties":{"from":{"$ref":"#/$defs/path"},"signal":{"type":"string"},"to":{"$ref":"#/$defs/path"},
    "method":{"type":"string"},"flags":{"type":"integer","minimum":0},"binds":{"type":"array"}}}}}
```
Extra rules checked by the validator (rc 2, `[scene.spec-schema]`): `root` has no `parent`/`index`; `extra_nodes`
need `parent`; a root with `instance` makes an **inherited scene**; `save` must not equal any `instance` in the spec.
Paths (`$node`, `parent`, `overrides` keys, `from`/`to`) are root-relative like digest paths (`.` = root) or `%Name`.
`$node` paths are root-relative (the engine stores them relative to the owning node; the generator converts).

### 2.5 Ops file (JSON Schema draft 2020-12)
```json
{"$id":"harness.scene-ops/1","type":"object","required":["ops"],"additionalProperties":false,
 "properties":{"schema":{"const":"harness.scene-ops/1"},"ops":{"type":"array","items":{"oneOf":[
  {"type":"object","additionalProperties":false,"required":["op","node","props"],
   "properties":{"op":{"const":"set_prop"},"node":{"type":"string"},"props":{"$ref":"harness.scene-spec/1#/$defs/props"}}},
  {"type":"object","additionalProperties":false,"required":["op","parent","node"],
   "properties":{"op":{"const":"add_node"},"parent":{"type":"string"},"node":{"$ref":"harness.scene-spec/1#/$defs/node"},"index":{"type":"integer","minimum":0}}},
  {"type":"object","additionalProperties":false,"required":["op","parent","name","scene"],
   "properties":{"op":{"const":"add_instance"},"parent":{"type":"string"},"name":{"type":"string"},"scene":{"type":"string","pattern":"^res://.+\\.tscn$"},"props":{"$ref":"harness.scene-spec/1#/$defs/props"},"index":{"type":"integer","minimum":0}}},
  {"type":"object","additionalProperties":false,"required":["op","node"],"properties":{"op":{"const":"remove_node"},"node":{"type":"string"}}},
  {"type":"object","additionalProperties":false,"required":["op","node","parent"],
   "properties":{"op":{"const":"reparent"},"node":{"type":"string"},"parent":{"type":"string"},"index":{"type":"integer","minimum":0}}},
  {"type":"object","additionalProperties":false,"required":["op","node","name"],"properties":{"op":{"const":"rename"},"node":{"type":"string"},"name":{"type":"string"}}},
  {"type":"object","additionalProperties":false,"required":["op","from","signal","to","method"],
   "properties":{"op":{"const":"connect"},"from":{"type":"string"},"signal":{"type":"string"},"to":{"type":"string"},"method":{"type":"string"},"flags":{"type":"integer","minimum":0},"binds":{"type":"array"}}},
  {"type":"object","additionalProperties":false,"required":["op","from","signal","to","method"],
   "properties":{"op":{"const":"disconnect"},"from":{"type":"string"},"signal":{"type":"string"},"to":{"type":"string"},"method":{"type":"string"}}},
  {"type":"object","additionalProperties":false,"required":["op","node","script"],"properties":{"op":{"const":"set_script"},"node":{"type":"string"},"script":{"type":["string","null"]}}},
  {"type":"object","additionalProperties":false,"required":["op","node"],
   "properties":{"op":{"const":"groups"},"node":{"type":"string"},"add":{"type":"array","items":{"type":"string"}},"remove":{"type":"array","items":{"type":"string"}}}}]}}}}
```
Semantics: ops see the tree as left by earlier ops. `add_instance` = `add_node` with `instance`. Structural ops
(`remove_node`, `reparent`, `rename`, `set_script`, and `reparent` *into* an instance) are refused on nodes not
owned by the edited scene (inside an instance, or inherited from the base): `scene.instance-internal`. `set_prop` and
`add_node` under an instance's inner node are allowed and mark the instance editable (`set_editable_instance`).
`rename`/`reparent` rewrite every NodePath-typed property in the scene that pointed into the moved subtree (like the
editor). `remove_node` removes the subtree and its connections. Signals/methods are checked as in §2.6.

### 2.6 Values: input forms and rendering
| Spec value | Meaning | Check |
|---|---|---|
| bool/number/string/null/array | assigned to the property | type must match: int->float ok, float->int only if integral, string->StringName/NodePath ok, string -> enum int via hint name (case-insensitive); else `scene.bad-value` |
| `{"$var": "Vector2(1, 2)"}` | `str_to_var` | null result for non-`null` text, or type != property type: `scene.bad-value` |
| `{"$res": "res://x.png"}` | `load()` | load null or class not matching the property hint: `scene.missing-resource` / `scene.bad-value` |
| `{"$node": "A/B"}` | node ref, saved with `node_paths` | node missing: `scene.node-not-found`; property not Node-typed: `scene.bad-value` |
| `{"$new": "RectangleShape2D", "props": {...}}` | new sub-resource (props validated recursively) | unknown/abstract/not a Resource: `scene.unknown-type` |
| `{"$layers": ["world", 3]}` | bitmask from `layer_names/2d_physics` (3d if node is 3D) or bit numbers 1-32 | unknown name: `scene.bad-value` |
Property names: must exist on the node after its script is attached (`get_property_list`); unknown ->
`scene.unknown-property` with hint = most similar storable name (`String.similarity` >= 0.5). A property without
`PROPERTY_USAGE_STORAGE` is accepted only if setting it changes a stored property (e.g. `rotation_degrees`);
else `scene.not-stored` (e.g. `global_position` outside a tree). A plain string for a Node-typed export gives
`scene.bad-value` with hint `use {"$node": "<path>"}`.
Rendering (digest, `change:`): node refs and resolvable NodePaths -> `@<root-relative path>`; external resources ->
`res://path`; sub-resources -> `<Class>{k=v, ...}` (stored props, sorted); everything else `var_to_str` with
newlines replaced by spaces. Rendered values are valid `$var` inputs except `@`, `res://` and `{}` forms.

### 2.7 Digest JSON (`artifacts/digest.json`)
```json
{"$id":"harness.digest/1","type":"object","required":["schema","kind","path"],
 "properties":{"schema":{"const":"harness.digest/1"},"kind":{"enum":["scene","resource","project"]},
  "path":{"type":["string","null"]},"uid":{"type":["string","null"]},"format":{"type":["integer","null"]},
  "inherits":{"type":["string","null"]},
  "nodes":{"type":"array","items":{"type":"object","required":["path","kind","props","groups","unique","vanished"],
   "properties":{"path":{"type":"string"},"kind":{"enum":["node","instance","override"]},
    "type":{"type":["string","null"]},"instance":{"type":["string","null"]},"script":{"type":["string","null"]},
    "groups":{"type":"array","items":{"type":"string"}},"unique":{"type":"boolean"},
    "props":{"type":"object","additionalProperties":{"type":"string"}},"vanished":{"type":"boolean"},
    "from":{"type":["string","null"]}}}},
  "connections":{"type":"array","items":{"type":"object","required":["from","signal","to","method","flags"],
   "properties":{"from":{"type":"string"},"signal":{"type":"string"},"to":{"type":"string"},
    "method":{"type":"string"},"flags":{"type":"integer"},"binds":{"type":"string"}}}},
  "editable":{"type":"array","items":{"type":"string"}},"deps":{"type":"array","items":{"type":"string"}},
  "ext_uids":{"type":"object","additionalProperties":{"type":"string"}},
  "resource":{"type":["object","null"]},"project":{"type":["object","null"]}}}
```
`props` values use §2.6 rendering, uncut. `ext_uids` maps ext_resource path -> uid text as found in the file.
Output is deterministic: same file -> byte-identical JSON (sorted keys, nodes in file order, connections sorted).

### 2.8 Rule ids (prefix `scene.`, contract §2.7)
| id | sev | Raised by | Meaning |
|---|---|---|---|
| `scene.spec-schema` | error, rc 2 | gen/edit (Python) | JSON syntax (with line), schema, save path, exists w/o `--force` handled as usage |
| `scene.unknown-type` | error | gen/edit | class missing, abstract, not a Node (or not a Resource for `$new`); hint nearest class |
| `scene.unknown-property` | error | gen/edit | no such property (hint nearest) |
| `scene.not-stored` | error | gen/edit | property not saved in the file |
| `scene.bad-value` | error | gen/edit | value type mismatch / unparseable / unknown layer name |
| `scene.missing-resource` | error | gen/edit | `$res`, `instance`, `script` cannot be loaded |
| `scene.bad-script` | error | gen/edit | script loads but `can_instantiate()` is false (parse error) |
| `scene.duplicate-name` | error | gen/edit | sibling name collision (engine would rename to `Name2` silently [Run]) |
| `scene.node-not-found` | error | gen/edit | op target, `$node`, override key, extra parent, conn endpoint |
| `scene.bad-connection` | error | gen/edit | signal missing on source or method missing on target |
| `scene.instance-internal` | error | edit | structural op on a node not owned by the scene |
| `scene.broken-input` | error | edit | the input scene has load errors (listed as their own findings) |
| `scene.lossy-save` | error | gen/edit | saved file lacks an expected node/prop/connection/editable, or node count differs |
| `scene.unexpected-change` | error | edit, gen `--force` n/a | after-digest differs from before + expected effects |
| `scene.breaks-dependent` | error | gen `--force`/edit | a direct dependent has a new error finding after the write |
| `scene.no-effect` | warning | edit | an op changed nothing (same value, add existing group) |
| `scene.stale-ref` | warning | edit | a `.gd` attached in the scene contains `$Old`, `%Old` or `"Old"` after rename/remove |
| `scene.vanished-node` | error | digest | node in the file whose parent path does not resolve |
| `scene.load-failed` | error | digest | load returns null or instantiate fails (e.g. two roots, c13) |
Loc: spec/ops findings use the spec/ops file path (`res://` if inside the project, else cwd-relative) and put the
JSON pointer first in the message; scene findings use the scene `res://` path (no line).

### 2.9 Config (`harness.toml`, table `[scene]`, `CONFIG_TABLE="scene"`)
`project_exclude = ["res://addons"]` (list of res:// dir prefixes skipped by `--project-summary` and dependents
scan). No other keys in v0. Timeouts use kind `runner` (contract §2.8.2).

## 3. Design

### 3.1 Files (builder B2)
| Path | Content |
|---|---|
| `tools/harness/harness/verbs/digest.py` | args, target resolution, runner call, render (`HELP`, `run`, `CONFIG_TABLE`/`KEYS`) |
| `tools/harness/harness/verbs/scene_gen.py` | §3.3 pipeline for specs |
| `tools/harness/harness/verbs/scene_edit.py` | §3.3 pipeline for ops |
| `tools/harness/harness/scenes/__init__.py` | empty |
| `tools/harness/harness/scenes/schema.py` | stdlib validator for §2.4/§2.5 (+ JSON line numbers from `JSONDecodeError`) |
| `tools/harness/harness/scenes/model.py` | pure: digest render, diff -> `change:` lines, expected-effects model, compare |
| `tools/harness/harness/scenes/pipeline.py` | backup/rollback, dependents scan, uid header read, post-write verify |
| `addons/harness/runners/scene_digest.gd` | modes `scene`, `resource`, `project`; Logger capture; `@@H data` digest |
| `addons/harness/runners/scene_gen.gd` | port of r1_4 `scene_gen.gd` + §2.6 checks + inherited seed + effect records |
| `addons/harness/runners/scene_edit.gd` | ops on MAIN/MAIN_INHERITED instance + effect records + uid restore |
| `tests/schemas/` | none: schemas live in this spec; T2 copies them into `tests/contract/a2/schemas/*.json` |
Runners follow contract §2.8.5 (self-contained, `@@H` records, `done` then `quit(N)`, `can_instantiate()` before
`.new()`, free every node they create so no leak WARNING appears [Run: a failed r1_4 build leaked a CanvasItem RID]).

### 3.2 Ported from `.claude/research/scripts/r1_4_scene_format/`
`scene_gen.gd` (build, owner rule, `add_child(n, true)`, `set_editable_instance` for overrides/extra_nodes,
CONNECT_PERSIST), `scene_digest.gd` (SceneState walk), `load_check.gd` (Cap Logger class, copied into
`scene_digest.gd`), `modify.gd` (MAIN round-trip), `owner_test.gd` cases (become fault ideas), `setuid.gd`
(`ResourceSaver.set_uid` for uid restore). Fixes over r1_4: free root on failure; reject type coercion
(`type_convert("abc", TYPE_VECTOR2)` silently gives `(0, 0)` [Run]); detect renamed duplicates; GEN_EDIT_STATE_INSTANCE
for instances (kept); spec JSON `$new`/`$layers`; `spec_main.json` in r1_4 has a trailing `}`/comma bug, do not copy.

### 3.3 Pipelines
**digest**: `ensure_imported` -> one `runner` invocation `scene_digest.gd -- --mode scene <res path> [--expand]`.
The runner loads with `CACHE_MODE_IGNORE` under a Logger, walks `SceneState` (file view), marks a node `vanished` when
its parent path is neither the root nor another entry nor inside an instance entry, instantiates (default state) to
detect `load-failed`, reads `layer_names/*`, and emits one `{"t":"data","kind":"digest",...}` (§2.7 body). Python
renders. Engine log lines are still scanned by `godot.py` (contract §2.8.4); runner findings add the structural ones.

**scene-gen** (per spec): (1) Python: parse + validate (rc 2 stops before Godot); check `save` vs `--force`.
(2) `ensure_imported`. (3) If the target exists: digest-before (for diff and uid), copy file to
`artifacts/backup/<name>.tscn`, list dependents (§3.4) and load-check them (A1 `load_check.gd`). (4) `scene_gen.gd
-- --spec <abs> --out <res path> [--uid <uid>] [--seed <abs>]`: inherited root -> Python writes the 3-line seed
`[gd_scene format=3]` / `[ext_resource type="PackedScene" path="<base>" id="1"]` / `[node name="<root>"
instance=ExtResource("1")]` to `artifacts/seed.tscn`; the runner loads it (absolute path) and instantiates with
`GEN_EDIT_STATE_MAIN_INHERITED` [Run]. The runner collects every error, emits findings and exits 1 without saving if
any; else packs, saves (`DirAccess.make_dir_recursive` for the dir), restores `--uid` with `ResourceSaver.set_uid`,
and emits data `{"kind":"gen","live_nodes":N,"live_conns":C,"sets":[{"path","prop","value","is_default"}]}`.
(5) Verify: A1 `load_check.gd` on target + dependents (one invocation), then digest-after. Python checks: every spec
node exists with its kind/type/instance/script/groups/unique; every non-default set value equals the after-digest
value; spec connections present; `[editable]` for override/extra parents; after node entries == expected entries;
instantiated node count == `live_nodes` -> else `scene.lossy-save`. New dependent errors -> `scene.breaks-dependent`.
(6) Any error in (4)-(5), or a warning under `--strict`: restore backup or delete the new file, keep the rejected file
as `artifacts/rejected/<name>.tscn`, `saved: none (rolled back)`.

**scene-edit**: (1) validate ops (rc 2). (2) `ensure_imported`. (3) digest-before; any error finding ->
`scene.broken-input`, stop. Backup; dependents list + pre load-check. (4) `scene_edit.gd -- --scene <res> --ops
<abs> [--uid <uid>] [--ext-uids <abs json>]`: per op emits `{"kind":"op","i":k,"op":...,"effects":[...]}` where
effects are the resolved facts Python needs (`added` paths+kinds, `removed` paths, `moved` old->new, props set with
rendered value and `is_default`, NodePath props rewritten, conns added/removed, groups, `editable_added`, script
props dropped by `set_script`). Errors -> rc 1 before saving. After save: restore header uid; **ext uid reattach**:
for each `[ext_resource` header line whose path had a `uid=` in the input file (`--ext-uids` map from the
before-digest) and still resolves to that uid (`ResourceLoader.get_resource_uid`), re-insert `uid="..."`; this is the
only text rewrite, header attributes only, and is followed by the load-check. (5) Verify as gen, plus:
`model.expected(before, effects)` vs after-digest must be equal (nodes, props, groups, unique, sibling order,
connections, editable) -> else `scene.unexpected-change`/`scene.lossy-save`. (6) `scene.stale-ref` scan (Python
grep of scripts attached in the before-digest, after rename/remove). (7) rollback as gen.

### 3.4 Dependents, uid, rollback
Direct dependents = `.tscn`/`.tres` files (project walk, skipping hidden dirs, `.godot/`, `project_exclude`) whose
text contains `path="<target res path>"` or `uid="<target uid>"`. Transitive dependents: deferred. Only error
findings absent from the pre-check (key: path, rule, message) count. Uid: read from the target header by Python
(`uid="uid://..."`); a script save drops it and all ext `uid=` [Run]; restore makes `load("uid://...")` work
without re-import [Run]. v0 never assigns a new uid (decision; the editor adds uids on its first GUI save). Rollback
restores bytes exactly (`shutil.copy2`) and is reported in `run.json` `extra: {"saved": null, "rolled_back": true}`.

### 3.5 Error patterns and timeouts
Runner findings as §2.8; engine lines via contract §2.8.4 (no downgrades in A2). Each invocation uses kind `runner`
(60 s default). A spec script whose `_init` hangs gives `[harness.hang]` from `godot.py`; the target is not written
(the runner never reached save) and Python treats any non-PASS gen invocation as "no save".

### 3.6 Performance budgets (warm imported copy of `scene_host`, one core)
digest <= 2.0 s; `--project-summary` <= 3 s for 50 scenes; scene-gen (<= 30 nodes, new file) <= 5 s;
scene-edit (<= 10 ops, <= 3 dependents) <= 6 s. A headless runner invocation costs ~0.3 s [Run], so gen = 3 and
edit = 4-5 invocations.

### 3.7 Spikes (scratchpad `a2/proj`, [Run], Godot 4.7.stable.official.5b4e0cb0f)
- Runner cost: `-s scene_digest.gd` on a 4-node scene: 0.29/0.29/0.33 s wall, rc 0.
- Bad parent (c10/c11/c12): `SceneState` keeps the entry (`S ./Nope/A parent=./Nope`); default instantiate drops it
  with `WARNING: Parent path './Nope' for node 'A' has vanished`; `instantiate(GEN_EDIT_STATE_MAIN)` instead attaches
  it to the root as `Nope#A` (c11: `Root_A#B`) -> `scene.broken-input` rule.
- MAIN round trip of `main.tscn` with set_prop `A/Sprite.rotation` (+`set_editable_instance(A)`), rename B->Bee,
  add Holder, reparent Mesh->Holder, connect: output kept `node_paths`/`target = NodePath("../A")`, groups, both
  connections, added `[editable path="A"]`; rename of instance A in `ov.tscn` moved `[editable path="Ay"]` and the
  override parent. `Node.reparent()` printed `Adding 'Mesh' as child to 'Holder' will make owner 'Main'
  inconsistent` -> implement reparent as remove_child + add_child(n, true) + re-own.
- Inherited `inh.tscn` (`_MAIN_INHERITED`): set_prop Inner, rename own node, add under inherited Sprite -> correct
  `index=`/`parent=` entries. `remove` of inherited `Sprite` saved without error but only dropped its override; the
  node came back from the base -> `scene.instance-internal` + expected-effects check.
- uid: `set_uid` -> header `uid="uid://b81y0yt6ktkry"`; re-save from script -> header `[gd_scene format=3]` (uid
  dropped), also after load+resave; ext_resource `uid="uid://c8r8xvphd81hm"` dropped by a MAIN edit; restore via
  `set_uid` then `load("uid://b81y0yt6ktkry")` -> `res://scenes/u.tscn` without re-import.
- `add_child(n, true)` with a second `Dup` -> silently `Dup2`. `type_convert("abc", TYPE_VECTOR2)` -> `(0, 0)`;
  `str_to_var("Vector2(1,")` -> null. `$new` RectangleShape2D -> one `[sub_resource]`. `rotation_degrees`,
  `global_position`, `transform`: usage 0 (not stored); `motion_mode` enum hint `Grounded,Floating`.
- Inherited generation: `set_scene_inherited_state` is not exposed to GDScript (`Nonexistent function`, then hang
  until timeout); `instantiate(_MAIN_INHERITED)` of a normal scene + rename saves a flattened copy; the 3-line seed
  loaded from an absolute path + `_MAIN_INHERITED` saved `[node name="Enemy" instance=ExtResource(...)]` + `speed`
  override + `Eye` with `index="2"`.

## 4. Acceptance criteria (T2: `tests/{contract,unit,e2e}/a2/`; every `h` result passes `assert_contract`)
Digest
- AC-02.1 `digest scenes/complex.tscn`: rc 0; `node:` paths exactly `. A A/Sprite A/Inner/Extra B Area Area/Shape`;
  `A <res://scenes/child.tscn>`; `A/Sprite (override)`; `target=@A`; `collision_layer=world|player`;
  `conn: A.hit -> B._on_hit`; `conn: Area.area_entered -> ._on_hit flags=3`; `editable: A`. [contract]
- AC-02.2 Determinism: two digests of the same file have identical stdout (minus `log:`) and identical digest.json. [contract]
- AC-02.3 Bad parent (r1_4 c10, c11, c12 copied into a temp project): rc 1, a `!vanished` node line and
  `[scene.vanished-node]` naming the node. [contract]
- AC-02.4 c08 (forward sub ref), c23 (missing instance), c18 (missing script) -> rc 1 with >= 1 error finding;
  c13 (two roots) -> rc 1 `[scene.load-failed]`. [contract]
- AC-02.5 `--json`: `json:` stat line; file validates against §2.7. [contract]
- AC-02.6 `player.tscn` digest <= 40 lines without `more:`; an 80-node generated scene: <= 40 lines, `more: <K>
  lines in .../digest.txt`, digest.txt has 80 `node:` lines; `--node Body` prints only that subtree. [contract]
- AC-02.7 `--project-summary`: `name: scene_host`, `main_scene:`, `autoload: GameState res://scripts/game_state.gd`,
  `action: jump` containing `Space`, `layers-2d_physics: 1=world 2=player 3=hazard`, one `scene:` per non-excluded
  `.tscn` (none under `res://addons`); <= 3 s warm. [contract]
- AC-02.8 `.tres` digest: `resource:` with type, `prop:` lines. [contract]
- AC-02.9 Usage: missing file, a `.gd` target, a path outside the project, unknown `--node` -> rc 2. [contract]
- AC-02.10 `--expand` lists `A/Inner (from res://scenes/child.tscn)`. [contract]
Scene-gen
- AC-02.11 `specs/child.scene.json` then `specs/main.scene.json`: rc 0; files exist; every invocation in run.json has
  `scan_verdict` PASS; `h check` on the copy -> PASS; main.tscn contains `node_paths=PackedStringArray("target")`;
  no node name contains `@`. [contract]
- AC-02.12 `specs/ov.scene.json` (overrides + extra_nodes): file has `[editable path="A"]`; digest shows
  `A/Sprite (override) position=Vector2(50, 50)` and `A/Inner/Extra Marker2D`. [contract]
- AC-02.13 `$new` shape -> exactly one `[sub_resource type="RectangleShape2D"`; `$layers ["world","player"]` ->
  `collision_layer=world|player`; `$layers ["nope"]` -> rc 1 `[scene.bad-value]`. [contract]
- AC-02.14 Inherited spec (root `instance`): root line has `instance=ExtResource(` and no `type=`; digest has
  `inherits: res://scenes/child.tscn`; setting inherited `Sprite` props needs no `[editable]`. [contract]
- AC-02.15 One bad spec per rule (§6 list): rc 1, `saved: none`, target absent, finding with the rule id and the
  JSON pointer; hints: `positoin` -> `position`, `Spirte2D` -> `Sprite2D`, string for Node export -> `$node`. [contract]
- AC-02.16 A spec with 3 independent errors reports all 3 in one run. [contract]
- AC-02.17 Schema errors -> rc 2 `[scene.spec-schema]` with no Godot invocation in run.json, wall <= 1 s: invalid
  JSON (finding has `:LINE`), missing `save`, both `type` and `instance`, key `chlidren`, `save` not `.tscn`,
  `save` under `res://.godot/`. [contract]
- AC-02.18 Existing target without `--force` -> rc 2, file byte-identical; with `--force` -> rc 0, `change:` lines,
  header uid of the old file kept. [contract]
- AC-02.19 Spec whose script `_init` loops, `[timeouts] runner = 5`: rc 1, `[harness.hang]`, no file, <= 25 s. [contract]
- AC-02.20 Two specs where the second instances the first: both `OK` check lines; first spec broken -> its `FAIL`
  line, the second `SKIP`, neither file written. [contract]
- AC-02.21 Spec attaching a parse-broken script -> rc 1, `[scene.bad-script]` and a `godot.parse-error` finding at
  the script's `res://...:LINE`, no file. [contract]
Scene-edit
- AC-02.22 `{"ops": []}` on complex.tscn, inh.tscn and editor_style.tscn: rc 0, digest.json before == after;
  inh.tscn root keeps `instance=`; `[editable path="A"]` kept. [contract]
- AC-02.23 One test per op on complex.tscn (set_prop incl. `A/Sprite.rotation` -> override + editable; add_node;
  add_instance; remove_node (subtree + its conns gone); reparent with index; rename `B`->`Bee` (conn and
  `target=@Bee` follow); connect; disconnect; set_script; groups): rc 0, exactly the expected `change:` lines, and
  digest-after == digest-before + that change only. [contract]
- AC-02.24 Op errors leave the file byte-identical with rc 1 and `saved: none`: node-not-found, duplicate-name
  (rename onto a sibling; add existing name), instance-internal (remove/rename `A/Sprite`; remove inherited `Sprite`
  in inh.tscn), bad-connection, unknown-property, missing-resource (add_instance of a missing scene). [contract]
- AC-02.25 Atomicity: `[valid set_prop, invalid rename]` -> nothing written, both op results reported. [contract]
- AC-02.26 Bad-parent scene as input -> rc 1 `[scene.broken-input]`, file unchanged. [contract]
- AC-02.27 Rename `Sprite` in child.tscn (ov.tscn overrides `A/Sprite`) -> rc 1 `[scene.breaks-dependent]` naming
  `res://scenes/ov.tscn`; child.tscn byte-identical. A dependent already broken before the edit does not block. [contract]
- AC-02.28 `editor_style.tscn` (header uid + ext `uid=`): after a set_prop, header uid and every ext `uid=` are
  unchanged; `diff` of the file shows only the changed property line plus `unique_id=` attributes. [contract]
- AC-02.29 Rename `Sprite` in player.tscn (player.gd uses `$Sprite`) -> rc 5 `[scene.stale-ref]` at
  `res://scripts/player.gd:<line>`, file saved; with `--strict` -> rc 1, rolled back. [contract]
- AC-02.30 set_prop to the current value -> rc 5 `[scene.no-effect]`. [contract]
Cross-cutting
- AC-02.31 Budgets of §3.6 met (median of 3 warm runs). [contract, slow]
- AC-02.32 `h selftest --area A2` -> rc 0, all must faults caught, CLEAN entries pass, <= 240 s. [contract, slow]
- AC-02.33 E2E on a fresh copy of `clean_min`: gen two scenes from specs, edit (add + rename + connect), digest
  both, `h check` PASS, `git status` of the fixture tree clean (B3). [e2e]
- AC-02.34 `model.py` unit tests (deviation §8.3-1): synthetic before/effects/after triples -> missing node,
  missing prop, missing editable, extra node, reordered siblings each yield the named rule. [unit]
Untestable automatically: none.

## 5. Seeded faults (fixture `scene_host`; all `must` unless noted; `files/` hold the planted inputs)
| ID | Planted | Verb + args | Expect (rc, verdict, regex) |
|---|---|---|---|
| FAULT-A2-01 | spec `files/typo.scene.json`: root prop `positoin` | `scene-gen {fault_dir}/files/typo.scene.json` | 1 FAIL `\[scene\.unknown-property\].*positoin.*hint: position`, `^saved: none` |
| FAULT-A2-02 | spec child type `Spirte2D` | scene-gen | 1 FAIL `\[scene\.unknown-type\].*Sprite2D` |
| FAULT-A2-03 | spec `"position": "abc"` | scene-gen | 1 FAIL `\[scene\.bad-value\]` |
| FAULT-A2-04 | spec two children named `A` | scene-gen | 1 FAIL `\[scene\.duplicate-name\]` |
| FAULT-A2-05 | spec `"target": "Child"` (string, Node export) | scene-gen | 1 FAIL `\[scene\.bad-value\].*\$node` |
| FAULT-A2-06 | spec connection to method `_on_nope` | scene-gen | 1 FAIL `\[scene\.bad-connection\]` |
| FAULT-A2-07 | ops `remove_node Sprite` on `scenes/inh.tscn` | `scene-edit scenes/inh.tscn {fault_dir}/files/ops.json` | 1 FAIL `\[scene\.instance-internal\]` |
| FAULT-A2-08 | write `broken/bad_parent.tscn` (r1_4 c10) | `digest broken/bad_parent.tscn` | 1 FAIL `!vanished`, `\[scene\.vanished-node\]` |
| FAULT-A2-09 | same file + ops set_prop on `.` | scene-edit | 1 FAIL `\[scene\.broken-input\]` |
| FAULT-A2-10 | ops rename `Sprite`->`Body` on `scenes/child.tscn` | scene-edit | 1 FAIL `\[scene\.breaks-dependent\].*ov\.tscn`, `rolled back` |
| FAULT-A2-11 | write `scripts/hang.gd` (`_init` loops) + spec using it; `[timeouts] runner = 5` | scene-gen | 1 FAIL `\[harness\.hang\]`, `^saved: none`, <= 40 s |
| FAULT-A2-12 | ops `{"op":"move_node",...}` | scene-edit | 2 ERROR `\[scene\.spec-schema\]` |
| FAULT-A2-13 | write `broken/two_roots.tscn` (c13) | digest | 1 FAIL `\[scene\.load-failed\]` |
| FAULT-A2-14 | spec `save` = existing `res://scenes/child.tscn`, no `--force` | scene-gen | 2 ERROR `exists \(use --force\)` |
| FAULT-A2-15 (nice) | write `broken/missing_inst.tscn` (c23) | digest | 1 FAIL `godot\.(load-failed\|error)` |
| CLEAN-A2-01 | none | `scene-gen` of `specs/child2.scene.json` (new path) | 0 PASS `^saved: res://` |
| CLEAN-A2-02 | none | `scene-edit scenes/complex.tscn` with empty ops | 0 PASS |
| CLEAN-A2-03 | none | `digest --project-summary` | 0 PASS `^autoload: GameState` |
Mutation hints for the verifier (not selftest entries): drop `set_editable_instance` in `scene_edit.gd` (AC-02.23
set_prop must go red via `scene.lossy-save`); skip the owner assignment for grandchildren (AC-02.11 red); make the
validator accept unknown keys (AC-02.17 red); disable ext uid reattach (AC-02.28 red).

## 6. Fixtures needed (T2)
`tests/fixtures/projects/scene_host/` (contract §2.11; must PASS `h check`):
- `project.godot`: name `scene_host`, `run/main_scene="res://scenes/complex.tscn"`, autoload `GameState`,
  `[layer_names] 2d_physics/layer_1="world"`, `layer_2="player"`, `layer_3="hazard"`, `[input]` actions `jump`
  (physical Space), `left`, `right`.
- `scripts/hero.gd`: `extends Node2D`, `signal hit`, `@export var speed: int = 100`, `@export var target: Node`,
  `func _on_hit() -> void`. `scripts/player.gd`: `extends CharacterBody2D`, `@onready var sprite := $Sprite`
  (stale-ref target), `func _on_hurt(_a: Area2D) -> void`. `scripts/game_state.gd` (`extends Node`).
- Hand-written per r1_4 §3: `scenes/child.tscn` (spec_child equivalent: root hero.gd speed 250, `Sprite` %unique at
  (5,6), `Inner` group `inside`), `scenes/complex.tscn` (as the AC-02.1 digest), `scenes/inh.tscn` (§3.7 inherited:
  speed 900, Sprite override, own `Inner/Own` group `mine`, self connection), `scenes/ov.tscn` (overrides `A/Sprite`,
  extra `A/Inner/Extra`, `[editable path="A"]`), `scenes/player.tscn` (CharacterBody2D + player.gd, Sprite,
  CollisionShape2D with sub_resource, Camera2D, AnimationPlayer, Hurtbox Area2D + shape + connection; ~10 nodes),
  `scenes/editor_style.tscn` (header `uid=` and ext `uid=` for hero.gd: run `--import` once on a scratch copy and
  copy the values; uids are deterministic per project name + path + content [Run r1_4 T4]; do not commit `.uid`).
- `specs/child.scene.json`, `specs/main.scene.json`, `specs/ov.scene.json`, `specs/child2.scene.json`, an
  inherited spec, a `$new`/`$layers` spec; `res/item.tres` (+ `scripts/item.gd` class_name ItemData) for AC-02.8;
  `addons/demo/demo.tscn` (excluded by default from `--project-summary`).
- Broken inputs are NOT in the fixture (it must stay clean): copy r1_4 cases c08, c10-c13, c18, c23 into fault
  `files/` or test temp dirs from `.claude/research/scripts/r1_4_scene_format/cases/` (they reference
  `res://scripts/hero.gd` and `res://scenes/gone.tscn`, which suit `scene_host`).
- `FIXTURE.md`: purpose, owner A2, `h check` PASS.

## 7. Build order (builder B2; after B1 has `godot.py`, `out.py` and A1's `load_check.gd` green)
1. `scenes/schema.py`, verb skeletons with arg handling and rc 2 paths -> AC-02.9, 17.
2. `scene_digest.gd` (scene mode) + `model.render` -> AC-02.1-6, 10.
3. Resource and project modes -> AC-02.7, 8; CLEAN-A2-03.
4. `scene_gen.gd` build + checks, no post-verify yet -> AC-02.13-16, 19, 21; FAULT-A2-01..06, 11.
5. Post-write pipeline (load_check, digest-after, expected compare, rollback, uid restore, `--force`, multi-spec)
   -> AC-02.11, 12, 18, 20, 34; FAULT-A2-14; CLEAN-A2-01.
6. `scene_edit.gd` ops + effects model -> AC-02.22-26, 30; FAULT-A2-07, 09, 12; CLEAN-A2-02.
7. Dependents, stale-ref, ext uid reattach -> AC-02.27-29; FAULT-A2-10.
8. Faults/selftest pass, budgets, e2e -> AC-02.31-33; FAULT-A2-08, 13, 15.

## 8. Out of scope, open questions, assumptions
### 8.1 Out of scope (v0)
`.tres` editing (a later `h res-edit`), `.scn` binary scenes, assigning new uids, moving/renaming files (F6 move
tool), transitive dependents, array-of-node exports, signal `unbinds`, editing nodes nested two instance levels deep
(`A/B/C` where B is itself an instance inside A) [U: likely works via the same editable chain, untested], C# scripts
(D1), 3D-specific checks (D2; 3D nodes work generically), a live editor bridge (D3).
### 8.2 Open questions [U]
1. Whether the editor GUI later rewrites a script-generated scene noisily (ids, `unique_id`) on first save (R1.4 open).
2. `unique_id=` attributes are added to every node on the first engine save of a hand-written scene; accepted noise.
3. `scene.stale-ref` is a text heuristic over attached scripts only (no full path lint: A3/F4 C2b).
4. Scripts run `_init` during gen/edit (set_script); `@tool` side effects are not sandboxed (F13).
5. Loading the inherited seed from an absolute path outside `res://` worked [Run]; not tested on a project with a
   `.gdignore`d run dir.
### 8.3 Deviations requested from the contract / plan (reviewer to confirm)
1. Contract §2.12 lets unit tests import only `logscan`/`out`; A2 asks to add `harness.scenes.model` (pure functions)
   for AC-02.34.
2. Plan §7 A2 "digest <= 60 lines" becomes contract-conformant <= 40 lines with `more:` + `artifacts/digest.txt`;
   plan's `--all-props` is dropped (values are always shown, cut at 60 chars; uncut on disk).
3. Plan's `h digest --project` flag is spelled `--project-summary`, because `--project DIR` is a contract common flag.
### 8.4 Assumptions on other areas
- A1: `addons/harness/runners/load_check.gd` takes `-- <res path>...`, emits `@@H` finding records with `path` = the
  res path, exits 0/1 (contract §2.8.5); `godot.run(run, "runner", project, runner=<abs>, user_args=[...])` returns
  the parsed runner records. A1's `h check` covers scenes generally; A2 calls `load_check` only on what it wrote.
- A3 owns `tscn-*` text lint; A2 does not lint text. A8's hook on `.tscn` Edit/Write points the agent to
  `h scene-edit`/`h scene-gen` and `h digest`. A9 commits one `*.scene.json` per sample scene (location of its
  choice; `save` fixes the output) and regenerates with `h scene-gen --force`; scenes edited later with
  `h scene-edit` must get the same change in their spec (A9 rule) or the next regeneration reverts it.
- Plan defaults D1-D5 and B1-B8 as given; nothing here needs Xvfb.
