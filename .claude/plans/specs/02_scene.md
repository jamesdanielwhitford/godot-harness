# 02 Scene generator, editor and digest (A2)

Status: spec v2, 2026-10-15, Opus planner P2 re-run (REVIEW B14/R-30, N05, N17 applied). Conforms to
`00_contract.md` ("contract §x"); deviations in §8.3 (all accepted by REVIEW).
Tags: [Run] verified in the §3.6 spikes (Godot 4.7.stable.official.5b4e0cb0f), [U] unverified.

## 1. Purpose and failure modes covered
Scenes become readable as text and writable only through the engine, and every write is verified.
- **F3** hand-editing `.tscn`: `h scene-gen` (spec -> engine-built scene) and `h scene-edit` (ops on a
  `GEN_EDIT_STATE_MAIN` round trip) replace hand edits; R1.4 rules 1-20 hold by construction.
- **F4** node paths: `h digest` prints real root-relative paths (`A/Inner/Extra`, `%unique`).
- **F5** signal wiring: digest lists every connection; `connect` ops check the signal and the method.
- **F6** uid refs: edits keep the scene uid and ext_resource `uid=` attributes, which a script save drops [Run].
- **F10** layers: digest prints `collision_layer`/`collision_mask` as named layers.
- **F11**: contract §2.3 output (<= 40 lines), full digest on disk.
- **R1.4 silent group** (c01, c02, c15, c26, d06, own_a, d04, mod0): the generator rejects unknown props, wrong
  value types and duplicate names; writes `node_paths`; applies the owner rule, `[editable]` and MAIN edit states;
  and compares expected vs actual digests after each write, because `pack()`/`save()` return OK for lossy results.

## 2. Interfaces

### 2.1 `h digest`
```
h digest [--project DIR] <scene.tscn|res.tres> [--node PATH] [--expand] [--json] [--strict]
h digest [--project DIR] --project-summary [--json]
```
- Target: `res://...` or a filesystem path inside the project. Missing, not `.tscn`/`.tres`, outside the project,
  a target together with `--project-summary`, or an unknown `--node`: rc 2 `ERROR digest usage: ...`.
- `--node PATH` (root-relative or `%Name`): only that node and its subtree. `--expand`: also nodes inside instances
  (from the instantiated tree), marked `(from <res://scene>)`.
- Every run writes `artifacts/digest.txt` (all lines, uncut) and `artifacts/digest.json` (§2.7); `--json` adds the
  stat line `json: <path>`.
- rc: 0 clean; 1 load errors, vanished nodes or failed instantiate; 2 usage; 4 env; 5 warnings only.

Stat lines (contract grammar, this order): `project:`, `import:`, `scene:` (or `resource:`), `inherits:` (inherited
only), `node:` per node in file order, `conn:` per connection, `editable:` and `deps:` (comma lists). When the lines
do not fit in 40, the last kept stat is `more: <K> lines in <run dir>/artifacts/digest.txt`.
Node line: `node: <path> <kind>[ %unique][ groups=a,b][ script=res://x.gd][ <prop>=<value>]...[ !vanished]`.
`<path>` is `.` for the root, else root-relative as `get_node()` from the root takes it. `<kind>` is the class,
`<res://child.tscn>` for an instance, `(override)` for an entry that only overrides an inner node of an instance or
base scene. Props: only those stored in the file, file order, §2.6 rendering, each value cut to 60 chars with `...`;
`collision_layer`/`collision_mask` render as `world|player|#5` from `layer_names/*` (`#N` = unnamed bit).
Conn line: `conn: <from>.<signal> -> <to>.<method>[ flags=N][ binds=<var_to_str>]` (flags shown only if != 2).
`.tres` target: `resource: res://x.tres type=<Class>[ script_class=<Name>]`, then `prop: <name>=<value>` lines.
`--project-summary`: `project:`, `name:`, `main_scene:`, `autoload: <Name> <res path>` each, `action: <name>
<event as_text>, ...` per key of the `[input]` section of `project.godot`, `layers-<kind>: 1=world 2=player` per
non-empty `layer_names/<kind>`, `scenes: <n>`, then `scene: <res path> <root kind> nodes=<n>` per `.tscn` (sorted;
hidden dirs, `.godot/` and `[scene] project_exclude` skipped), then `more:` if cut.
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
```
A vanished node (r1_4 c10) prints `node: Nope/A Node2D !vanished`, rc 1, plus `res://broken/bad_parent.tscn:
[scene.vanished-node] error: node 'Nope/A' is dropped at load: parent 'Nope' does not exist (hint: parent= is
root-relative, never with the root name)` and the scanned `-: [godot.parent-vanished] error: ...` line.

### 2.2 `h scene-gen`
`h scene-gen [--project DIR] <spec.json>... [--force] [--strict]`. Specs (§2.4) run in order (a later spec may
instance an earlier one). Per spec: validate (Python, no Godot) -> build in the engine -> save -> verify (§3.3) ->
keep or roll back. The first failing spec stops the run; later specs get `SKIP` check lines and are not written.
- Target exists without `--force`: rc 2 `ERROR scene-gen usage: res://x.tscn exists (use --force)`, nothing written.
  With `--force`: the old uid is kept, `change:` lines vs the old digest, direct dependents re-checked (§3.4).
- Stats: `project:`, `import:`, `saved: <res path>|none[ (rolled back)]`, `uid: kept <uid>|none`, then `node:`/
  `conn:` lines (new file) or `change:` lines (overwrite). Several specs: one check line each (`OK   <res path>:
  created|replaced, <n> nodes`, `FAIL ...`, `SKIP ...`) and no node lines.
- rc: 0 written and verified; 1 semantic error or failed verification (not written / restored); 2 JSON, schema or
  usage error (no Godot run); 4 env; 5 written with warnings only.
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
`h scene-edit [--project DIR] <scene.tscn> <ops.json> [--strict]`. All ops (§2.5) apply in order to one instance
(`GEN_EDIT_STATE_MAIN`, or `_MAIN_INHERITED` when the scene has a base state), then one save. All-or-nothing: any op
error -> nothing written. An input with any load error is refused (`scene.broken-input`): MAIN-state instantiation
silently re-parents vanished nodes to the root as `Parent#Name` [Run]; repair by regenerating or a minimal hand fix.
- Stats: `project:`, `import:`, `saved: ...`, `uid: ...`, `dependents: <n> checked`, then `change:` lines:
  `+ <path> <kind>`, `- <path>`, `> <old> -> <new>` (rename/reparent), `~ <path> <prop>: <old> -> <new>`,
  `+ conn <conn>`, `- conn <conn>`, `+ group <path> <g>`, `- group <path> <g>`, `+ editable <path>`.
- rc as `scene-gen`; rc 2 also when the scene is missing or not `.tscn`.
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

### 2.4 Scene spec (`*.scene.json`; JSON Schema 2020-12; validated at runtime by stdlib code)
```json
{"$id":"harness.scene-spec/1","type":"object","required":["save","root"],"additionalProperties":false,
 "properties":{"schema":{"const":"harness.scene-spec/1"},
  "save":{"type":"string","pattern":"^res://(?!\\.godot/|\\.harness/)[^\\s\"]+\\.tscn$"},
  "root":{"$ref":"#/$defs/node"},"overrides":{"type":"object","additionalProperties":{"$ref":"#/$defs/props"}},
  "extra_nodes":{"type":"array","items":{"allOf":[{"$ref":"#/$defs/node"},{"required":["parent"]}]}},
  "connections":{"type":"array","items":{"$ref":"#/$defs/conn"}}},
 "$defs":{"name":{"type":"string","minLength":1,"pattern":"^[^./:@%\"]+$"},"path":{"type":"string","minLength":1},
  "node":{"type":"object","required":["name"],"additionalProperties":false,"oneOf":[{"required":["type"]},{"required":["instance"]}],
   "properties":{"name":{"$ref":"#/$defs/name"},"type":{"type":"string","pattern":"^[A-Za-z_][A-Za-z0-9_]*$"},
    "instance":{"type":"string","pattern":"^res://.+\\.tscn$"},"parent":{"$ref":"#/$defs/path"},
    "script":{"type":"string","pattern":"^res://.+\\.gd$"},"props":{"$ref":"#/$defs/props"},
    "groups":{"type":"array","items":{"type":"string","minLength":1},"uniqueItems":true},
    "unique_name":{"type":"boolean"},"index":{"type":"integer","minimum":0},
    "children":{"type":"array","items":{"$ref":"#/$defs/node"}}}},
  "props":{"type":"object","propertyNames":{"pattern":"^[A-Za-z_][A-Za-z0-9_/:]*$"},"additionalProperties":{"$ref":"#/$defs/value"}},
  "value":{"oneOf":[{"type":["boolean","number","string","null","array"]},
   {"type":"object","required":["$var"],"additionalProperties":false,"properties":{"$var":{"type":"string"}}},
   {"type":"object","required":["$res"],"additionalProperties":false,"properties":{"$res":{"type":"string","pattern":"^res://"}}},
   {"type":"object","required":["$node"],"additionalProperties":false,"properties":{"$node":{"$ref":"#/$defs/path"}}},
   {"type":"object","required":["$new"],"additionalProperties":false,"properties":{"$new":{"type":"string"},"props":{"$ref":"#/$defs/props"}}},
   {"type":"object","required":["$layers"],"additionalProperties":false,"properties":{"$layers":{"type":"array","items":{"type":["string","integer"]}}}}]},
  "conn":{"type":"object","required":["from","signal","to","method"],"additionalProperties":false,
   "properties":{"from":{"$ref":"#/$defs/path"},"signal":{"type":"string"},"to":{"$ref":"#/$defs/path"},
    "method":{"type":"string"},"flags":{"type":"integer","minimum":0},"binds":{"type":"array"}}}}}
```
Extra validator rules (rc 2, `[scene.spec-schema]`): `root` has no `parent`/`index`; `save` differs from every
`instance` in the spec. A root with `instance` makes an **inherited scene**. All paths (`$node`, `parent`,
`overrides` keys, `from`/`to`) are root-relative (`.` = root) or `%Name`; the generator converts `$node` to the
node-relative NodePath the engine stores.

### 2.5 Ops file (`{"schema"?: "harness.scene-ops/1", "ops": [...]}`; each op object has exactly these keys)
| op | required | optional | effect |
|---|---|---|---|
| `set_prop` | node, props | | set props (§2.6) |
| `add_node` | parent, node (spec node, may nest) | index | add subtree |
| `add_instance` | parent, name, scene | props, index | = `add_node` with `instance` |
| `remove_node` | node | | remove subtree and its connections |
| `reparent` | node, parent | index | remove_child + add_child(n, true) + re-own (not `Node.reparent`, [Run] warning) |
| `rename` | node, name | | |
| `connect` | from, signal, to, method | flags, binds | CONNECT_PERSIST always OR-ed in |
| `disconnect` | from, signal, to, method | | |
| `set_script` | node, script (`res://*.gd` or null) | | props of the old script disappear |
| `groups` | node | add, remove (string arrays) | persistent groups |
T2 writes this as JSON Schema (`oneOf` of the 10 shapes, `additionalProperties: false`, defs from §2.4). Ops see the
tree left by earlier ops. `remove_node`/`reparent`/`rename`/`set_script` on a node the scene does not own (inside an
instance, or inherited) and `reparent` into an instance: `scene.instance-internal`. `set_prop`/`add_node` under an
inner node are allowed and call `set_editable_instance`. `rename`/`reparent` rewrite NodePath-typed props that
pointed into the moved subtree (editor parity).

### 2.6 Values: input forms and rendering
| Spec value | Meaning | Check |
|---|---|---|
| bool/number/string/null/array | assigned | type must match: int->float, integral float->int, string->StringName/NodePath, string->enum int via hint name (case-insensitive); else `scene.bad-value` |
| `{"$var": "Vector2(1, 2)"}` | `str_to_var` | null for non-`null` text, or type != property type: `scene.bad-value` |
| `{"$res": "res://x.png"}` | `load()` | null: `scene.missing-resource`; class not matching the hint: `scene.bad-value` |
| `{"$node": "A/B"}` | node ref, saved with `node_paths` | missing: `scene.node-not-found`; property not Node-typed: `scene.bad-value` |
| `{"$new": "RectangleShape2D", "props": {}}` | new sub-resource, props checked recursively | unknown/abstract/not a Resource: `scene.unknown-type` |
| `{"$layers": ["world", 3]}` | bitmask by `layer_names/2d_physics` (`3d_physics` for 3D nodes) or bit 1-32 | unknown name: `scene.bad-value` |
Property names must exist after the script is attached, else `scene.unknown-property` (hint: most similar stored
name, `String.similarity` >= 0.5). A non-`PROPERTY_USAGE_STORAGE` prop is accepted only if setting it changes a
stored one (`rotation_degrees`), else `scene.not-stored`. A plain string for a Node export: `scene.bad-value`, hint
`use {"$node": "<path>"}`. Rendering (digest, `change:`): node refs and resolvable NodePaths -> `@<root-relative
path>`; external resources -> `res://path`; sub-resources -> `<Class>{k=v, ...}` (sorted); else `var_to_str` with
newlines -> spaces (valid `$var` input).

### 2.7 Digest JSON (`artifacts/digest.json`; deterministic: sorted keys, nodes in file order, connections sorted)
```json
{"$id":"harness.digest/1","type":"object","required":["schema","kind","path"],
 "properties":{"schema":{"const":"harness.digest/1"},"kind":{"enum":["scene","resource","project"]},
  "path":{"type":["string","null"]},"uid":{"type":["string","null"]},"format":{"type":["integer","null"]},
  "inherits":{"type":["string","null"]},"editable":{"type":"array","items":{"type":"string"}},
  "deps":{"type":"array","items":{"type":"string"}},"ext_uids":{"type":"object","additionalProperties":{"type":"string"}},
  "nodes":{"type":"array","items":{"type":"object","required":["path","kind","props","groups","unique","vanished"],
   "properties":{"path":{"type":"string"},"kind":{"enum":["node","instance","override"]},"type":{"type":["string","null"]},
    "instance":{"type":["string","null"]},"script":{"type":["string","null"]},"groups":{"type":"array","items":{"type":"string"}},
    "unique":{"type":"boolean"},"props":{"type":"object","additionalProperties":{"type":"string"}},
    "vanished":{"type":"boolean"},"from":{"type":["string","null"]}}}},
  "connections":{"type":"array","items":{"type":"object","required":["from","signal","to","method","flags"],
   "properties":{"from":{"type":"string"},"signal":{"type":"string"},"to":{"type":"string"},"method":{"type":"string"},
    "flags":{"type":"integer"},"binds":{"type":"string"}}}},
  "resource":{"type":["object","null"]},"project":{"type":["object","null"]}}}
```
`props` hold uncut §2.6 renderings. `ext_uids` maps ext_resource path -> `uid://...` as written in the file.

### 2.8 Rule ids (prefix `scene.`, contract §2.7)
| id | sev | by | meaning |
|---|---|---|---|
| `scene.spec-schema` | error (rc 2) | gen, edit | JSON syntax (finding has `:LINE`), schema, extra rules, bad save path |
| `scene.unknown-type` | error | gen, edit | class missing, abstract, not a Node (not a Resource for `$new`); hint nearest class |
| `scene.unknown-property` | error | gen, edit | no such property; hint nearest |
| `scene.not-stored` | error | gen, edit | property is not saved in the file |
| `scene.bad-value` | error | gen, edit | type mismatch, unparseable, unknown layer name |
| `scene.missing-resource` | error | gen, edit | `$res`, `instance`, `script` cannot be loaded |
| `scene.bad-script` | error | gen, edit | script loads but `can_instantiate()` is false |
| `scene.duplicate-name` | error | gen, edit | sibling name clash (the engine silently renames to `Name2` [Run]) |
| `scene.node-not-found` | error | gen, edit | op target, `$node`, override key, extra parent, conn endpoint |
| `scene.bad-connection` | error | gen, edit | signal missing on source or method missing on target |
| `scene.instance-internal` | error | edit | structural op on a node the scene does not own |
| `scene.broken-input` | error | edit | input scene has load errors (also listed as their own findings) |
| `scene.lossy-save` | error | gen, edit | saved file lacks an expected node/prop/conn/editable, or node count differs |
| `scene.unexpected-change` | error | edit | after-digest != before-digest + expected effects |
| `scene.breaks-dependent` | error | gen --force, edit | a direct dependent has a new error finding |
| `scene.no-effect` | warning | edit | an op changed nothing (same value, existing group) |
| `scene.stale-ref` | warning | edit | a script attached in the scene contains `$Old`, `%Old` or `"Old"` after rename/remove |
| `scene.vanished-node` | error | digest | file entry whose parent path does not resolve |
| `scene.load-failed` | error | digest | load returns null or instantiate fails (two roots, c13) |
Spec/ops findings use the spec/ops file path as loc (`res://` inside the project, else cwd-relative) and start the
message with the JSON pointer; scene findings use the scene `res://` path, no line.

### 2.9 Config (`[scene]`, `CONFIG_TABLE = "scene"`)
`project_exclude = ["res://addons"]`: res:// dir prefixes skipped by `--project-summary` and the dependents scan.
No other keys. All invocations use kind `runner` (contract §2.8.2, 60 s default).
## 3. Design

### 3.1 Files (builder B2)
| Path | Content |
|---|---|
| `tools/harness/harness/verbs/{digest,scene_gen,scene_edit}.py` | args, resolution, pipeline calls, render (`HELP`, `run`; digest also `CONFIG_TABLE`/`CONFIG_KEYS`) |
| `tools/harness/harness/scenes/{__init__,schema}.py` | stdlib validator for §2.4/§2.5, JSON line numbers from `JSONDecodeError` |
| `tools/harness/harness/scenes/model.py` | pure: render, diff -> `change:` lines, expected-effects model, compare |
| `tools/harness/harness/scenes/pipeline.py` | backup/rollback, dependents scan, header uid read, post-write verify |
| `addons/harness/runners/scene_digest.gd` | modes scene/resource/project; Logger capture; `@@H` digest data |
| `addons/harness/runners/scene_gen.gd` | port of r1_4 `scene_gen.gd` + §2.6 checks + inherited seed + effect records |
| `addons/harness/runners/scene_edit.gd` | ops on a MAIN/MAIN_INHERITED instance, effect records, uid restore |
Runners follow contract §2.8.5 (self-contained, `@@H` records, `done` then `quit(N)`, `can_instantiate()` before
`.new()`) and free every node they create, also on failure (a failed r1_4 build leaked a CanvasItem RID -> WARNING [Run]).

### 3.2 Ported from `.claude/research/scripts/r1_4_scene_format/`
`scene_gen.gd` (owner rule, `add_child(n, true)`, `GEN_EDIT_STATE_INSTANCE`, `set_editable_instance`), `scene_digest.gd`
(with the `Cap` Logger from r1_4 `load_check.gd`), `modify.gd`, `setuid.gd`. A2 does not port or modify
`load_check.gd`: A1 owns it and A2 reaches it only through `checkrun.load_check` (§3.3, REVIEW R-30).
Fixes: free the root on failure; no silent coercion
(`type_convert("abc", TYPE_VECTOR2)` = `(0, 0)` [Run]); detect auto-renamed duplicates.

### 3.3 Pipelines
**Load-check (A1 protocol, REVIEW R-30).** Every pre/post write check is one call
`checkrun.load_check(run, project, res_paths, smoke=0) -> list[dict]` (A1 §3.2 steps 3-8: `load_check.gd --mode
scenes --list <file>`, begin/end records, resume after hang/crash, record->finding mapping, scan merge; no lint).
It returns findings and adds none to the Run. A2 adds target findings with `run.add_findings`; dependent findings
are only compared (§3.4), and pre-check findings go to `run.json` `extra.precheck`, never to stdout.
**Godot calls.** Every verb calls `godot.ensure_imported(run, project)` once before its first invocation (contract
§2.8.7). A2 runners go through `godot.run(run, "runner", project, runner=<abs>, user_args=[...])`, which returns an
`Invocation`; A2 reads its `@@H` data from `inv.records` and calls `run.add_findings(inv.findings)` (contract §2.9).

**digest**: `ensure_imported`, then `scene_digest.gd -- --mode scene <res> [--expand]`. The runner loads with
`CACHE_MODE_IGNORE` under the Logger, walks `SceneState`, marks an entry `vanished` when its parent path is neither
the root, another entry, nor below an instance/override entry, instantiates (default state) to detect
`load-failed`, reads `layer_names/*`, and prints one `{"t":"data","kind":"digest",...}` (§2.7 body). Python renders.
`godot.py` still scans the engine lines (contract §2.8.4); the runner adds the structural findings.

**scene-gen** (per spec): (1) parse + validate; `save` vs `--force` (rc 2 stops before Godot). (2) `ensure_imported`.
(3) Existing target: digest-before (diff, uid, `ext_uids`), copy to `artifacts/backup/`, list dependents (§3.4),
pre load-check them with `checkrun.load_check`. (4) `scene_gen.gd -- --spec <abs> --out <res> [--uid <uid>]
[--seed <abs>]`. Inherited root: Python writes the seed `[gd_scene format=3]` / `[ext_resource type="PackedScene"
path="<base>" id="1"]` / `[node name="<root>" instance=ExtResource("1")]` to `artifacts/seed.tscn`; the runner loads
it by absolute path and instantiates `_MAIN_INHERITED` [Run]. The runner collects all errors; if any, it emits them
and exits 1 without saving. Else it packs, saves (`make_dir_recursive`), restores `--uid` via `set_uid`, and emits
`{"kind":"gen","live_nodes":N,"live_conns":C,"sets":[{"path","prop","value","is_default"}]}`. (5) Verify: one
`checkrun.load_check(run, project, [target] + dependents)` call, then digest-after. Python requires: every spec node with its
kind/type/instance/script/groups/unique; each non-default set value equal in the after-digest; spec connections;
`[editable]` for override/extra parents; no other entries; instantiated count == `live_nodes`; else
`scene.lossy-save`. New dependent errors -> `scene.breaks-dependent`. (6) Any error in (4)-(5), or a warning under
`--strict`: restore the backup or delete the new file, keep the result as `artifacts/rejected/<name>.tscn`, print
`saved: none (rolled back)`; `run.json` `extra: {"saved": null, "rolled_back": true}`.

**scene-edit**: (1) validate ops (rc 2). (2) `ensure_imported`. (3) digest-before; any error finding ->
`scene.broken-input`, stop. Backup, dependents + their pre `checkrun.load_check`. (4) `scene_edit.gd -- --scene <res> --ops
<abs> [--uid <uid>] [--ext-uids <abs json>]`. Per op it emits `{"kind":"op","i":k,"op":..,"effects":[..]}` with the
resolved facts Python needs: added paths+kinds, removed paths, moved old->new, props set (rendered value,
`is_default`), NodePath props rewritten, conns added/removed, groups, `editable_added`, props dropped by
`set_script`. Errors: exit 1 before saving. After saving: restore the header uid, then **ext uid reattach**: on each
`[ext_resource` header line whose path had a `uid=` before (`--ext-uids`) and still resolves to that uid
(`ResourceLoader.get_resource_uid`), re-insert `uid="..."`. This is the only text rewrite (header attributes only,
followed by the load-check, digest compare and byte-exact rollback on any error; REVIEW R-21 accepted it as the
harness repairing an engine save, not a hand edit). (5) Verify as gen, plus `model.expected(before, effects)` == after-digest (nodes, kinds,
props, groups, unique, sibling order, conns, editable), else `scene.unexpected-change` (or `scene.lossy-save` for
missing items). (6) `scene.stale-ref`: grep scripts attached in the before-digest after rename/remove. (7) Roll back
as gen.

### 3.4 Dependents, uid, rollback
Direct dependents: `.tscn`/`.tres` files (project walk skipping hidden dirs, `.godot/`, `project_exclude`) whose text
contains `path="<target>"` or `uid="<target uid>"`. Of the post `load_check` findings at a dependent path, only
errors absent from the pre-check (key: path, rule, message) count; each becomes one `scene.breaks-dependent` at
that path, message `new after edit of <target>: <original message>`. Transitive dependents are deferred. A script save drops the header uid and every ext `uid=` [Run];
`set_uid` restores the header and `load("uid://...")` works without re-import [Run]. v0 never assigns new uids (the
editor adds them on its first GUI save). Rollback restores bytes exactly (`shutil.copy2`).

### 3.5 Errors, timeouts, budgets
Runner findings per §2.8; engine lines per contract §2.8.4, no downgrades in A2. A hanging spec script gives
`[harness.hang]` from `godot.py`; any non-PASS gen/edit invocation counts as "not saved" (backup restored if the
file changed anyway). Budgets, warm imported copy of `scene_host`: digest <= 2 s; `--project-summary` <= 3 s for 50 scenes; scene-gen (<= 30 nodes, new file) <= 5 s; scene-edit
(<= 10 ops, <= 3 dependents) <= 6 s. One headless runner invocation costs ~0.3 s [Run]: gen = 3, edit = 4-5.

### 3.6 Spikes ([Run], scratchpad `a2/proj`, r1_4 scripts and cases)
- Cost: `-s scene_digest.gd -- res://scenes/ov.tscn`: 0.29 / 0.29 / 0.33 s wall, rc 0.
- Bad parent (c10-c12): `SceneState` keeps `./Nope/A parent=./Nope`; `instantiate()` drops it (`WARNING: Parent path
  './Nope' ... has vanished`); `instantiate(GEN_EDIT_STATE_MAIN)` attaches it to the root as `Nope#A` (c11 `Root_A#B`).
- MAIN round trip of `main.tscn` (set_prop `A/Sprite.rotation` + `set_editable_instance`, rename B->Bee, add, reparent,
  connect) kept `node_paths`, groups, both connections, added `[editable path="A"]`; renaming instance `A` moved
  `[editable path="Ay"]`. `Node.reparent()` warned `... will make owner 'Main' inconsistent`.
- `inh.tscn` via `_MAIN_INHERITED`: set_prop/rename/add correct; removing inherited `Sprite` saved with no error but
  only dropped its override (the node returns from the base).
- uid: after `set_uid`, any script save writes `[gd_scene format=3]` (uid gone); a MAIN edit dropped ext
  `uid="uid://c8r8xvphd81hm"`; `set_uid` restore, then `load("uid://b81y0yt6ktkry")` worked with no re-import.
- Second `add_child(Dup, true)` -> `Dup2`; `str_to_var("Vector2(1,")` -> null; `$new` -> one `[sub_resource]`;
  `rotation_degrees`/`global_position`/`transform`/`name` have usage 0; `motion_mode` hint `Grounded,Floating`.
- `set_scene_inherited_state` is not exposed to GDScript (call error, then hang); `_MAIN_INHERITED` of a normal
  scene saves a flat copy; the 3-line seed + `_MAIN_INHERITED` saved `[node name="Enemy" instance=ExtResource(..)]`.

## 4. Acceptance criteria (T2: `tests/{contract,unit,e2e}/a2/`; every `h` result passes `assert_contract`)
- AC-02.1 `digest scenes/complex.tscn`: rc 0; `node:` paths exactly `. A A/Sprite A/Inner/Extra B Area Area/Shape`;
  lines contain `A <res://scenes/child.tscn>`, `A/Sprite (override)`, `target=@A`, `collision_layer=world|player`,
  `conn: A.hit -> B._on_hit`, `conn: Area.area_entered -> ._on_hit flags=3`, `editable: A`. [contract]
- AC-02.2 Two digests of one file: same stdout except `log:`, byte-identical digest.json. [contract]
- AC-02.3 r1_4 c10, c11, c12 in a temp copy: rc 1, a `!vanished` node line, `[scene.vanished-node]` naming it. [contract]
- AC-02.4 c08, c18, c23: rc 1 with >= 1 error finding; c13 (two roots): rc 1 `[scene.load-failed]`. [contract]
- AC-02.5 `--json`: `json:` stat line; the file validates against §2.7. [contract]
- AC-02.6 `player.tscn`: <= 40 lines, no `more:`. An 80-node generated scene: <= 40 lines, `more: <K> lines in
  .../digest.txt`, digest.txt has 80 `node:` lines. `--node Hurtbox` prints only that subtree. [contract]
- AC-02.7 `--project-summary`: `name: scene_host`, `main_scene: res://scenes/complex.tscn`, `autoload: GameState
  res://scripts/game_state.gd`, an `action: jump` line containing `Space`, `layers-2d_physics: 1=world 2=player
  3=hazard`, one `scene:` per `.tscn` outside `res://addons`; <= 3 s warm. [contract]
- AC-02.8 `res/item.tres`: `resource:` with `type=` and `script_class=ItemData`, `prop:` lines. [contract]
- AC-02.9 Missing file, `.gd` target, path outside the project, unknown `--node`: rc 2. [contract]
- AC-02.10 `--expand` on complex.tscn lists `A/Inner` with `(from res://scenes/child.tscn)`. [contract]
- AC-02.11 `specs/child.scene.json` + `specs/main.scene.json` to new paths: rc 0; every invocation in run.json has
  `scan_verdict` PASS; `h check` on the copy PASS; main file has `node_paths=PackedStringArray("target")`; no node
  name contains `@`. [contract]
- AC-02.12 `specs/ov.scene.json`: file has `[editable path="A"]`; digest has `A/Sprite (override)
  position=Vector2(50, 50)` and `A/Inner/Extra Marker2D`. [contract]
- AC-02.13 `$new` shape -> exactly one `[sub_resource type="RectangleShape2D"`; `$layers ["world","player"]` ->
  `collision_layer=world|player`; `$layers ["nope"]` -> rc 1 `[scene.bad-value]`. [contract]
- AC-02.14 Inherited spec: root line has `instance=ExtResource(` and no `type=`; `inherits: res://scenes/child.tscn`;
  props on inherited `Sprite` saved without `[editable]`. [contract]
- AC-02.15 One bad spec per gen rule of §2.8 (§6 list): rc 1, `saved: none`, no target file, the rule id and the
  JSON pointer in the finding; hints `positoin`->`position`, `Spirte2D`->`Sprite2D`, string Node export->`$node`. [contract]
- AC-02.16 A spec with 3 independent errors reports all 3 in one run. [contract]
- AC-02.17 rc 2 `[scene.spec-schema]`, no Godot invocation in run.json, <= 1 s, for: invalid JSON (loc has `:LINE`),
  missing `save`, `type` and `instance` together, key `chlidren`, `save` not `.tscn`, `save` under `res://.godot/`. [contract]
- AC-02.18 Existing target without `--force`: rc 2, file byte-identical. With `--force`: rc 0, `change:` lines, the
  old header uid kept. [contract]
- AC-02.19 Spec script whose `_init` loops, `[timeouts] runner = 5`: rc 1, `[harness.hang]`, no file, <= 25 s. [contract]
- AC-02.20 Two specs, the second instancing the first: two `OK` check lines. First spec broken: its `FAIL` line, the
  second `SKIP`, no file written. [contract]
- AC-02.21 Spec attaching a parse-broken script: rc 1, `[scene.bad-script]` and `[godot.parse-error]` at the
  script's `res://...:LINE`, no file. [contract]
- AC-02.22 `{"ops": []}` on complex.tscn, inh.tscn, editor_style.tscn: rc 0, digest.json before == after; inh.tscn
  root keeps `instance=`; `[editable path="A"]` kept. [contract]
- AC-02.23 One test per op on complex.tscn: set_prop (incl. `A/Sprite` rotation -> override, editable kept), add_node,
  add_instance, remove_node (subtree and its conns gone), reparent with index, rename `B`->`Bee` (conn and
  `target=@Bee` follow), connect, disconnect, set_script, groups. Each: rc 0, exactly the expected `change:` lines,
  digest-after == digest-before + that change. set_prop on `A/Sprite` of a copy without `[editable]` adds it. [contract]
- AC-02.24 rc 1, `saved: none`, file byte-identical for: node-not-found, duplicate-name (rename onto a sibling; add an
  existing name), instance-internal (remove/rename `A/Sprite`; remove inherited `Sprite` in inh.tscn),
  bad-connection, unknown-property, missing-resource (add_instance of a missing scene). [contract]
- AC-02.25 `[valid set_prop, invalid rename]`: nothing written. [contract]
- AC-02.26 Input c10 (bad parent): rc 1 `[scene.broken-input]`, file unchanged. [contract]
- AC-02.27 Rename `Sprite` in child.tscn (ov.tscn overrides `A/Sprite`): rc 1 `[scene.breaks-dependent]` naming
  `res://scenes/ov.tscn`, child.tscn byte-identical. A dependent already broken before does not block. [contract]
- AC-02.28 editor_style.tscn (header uid + ext `uid=`): after a set_prop, header uid and each ext `uid=` unchanged;
  the file diff touches only the changed property line and `unique_id=` attributes. [contract]
- AC-02.29 Rename `Sprite` in player.tscn (player.gd has `$Sprite`): rc 5 `[scene.stale-ref]` at
  `res://scripts/player.gd:<line>`, file saved; with `--strict`: rc 1, rolled back. [contract]
- AC-02.30 set_prop to the current value: rc 5 `[scene.no-effect]`. [contract]
- AC-02.31 §3.5 budgets (median of 3 warm runs). [contract, slow]
- AC-02.32 `h selftest --area A2`: rc 0, all must faults caught, CLEAN pass, <= 240 s. [contract, slow]
- AC-02.33 Fresh copy of `clean_min`: gen two scenes from specs, edit (add + rename + connect), digest both,
  `h check` PASS, fixture tree unchanged (B3). [e2e]
- AC-02.34 `model.py` on synthetic before/effects/after triples: missing node, missing prop, missing editable, extra
  node, reordered siblings each give the named rule (deviation §8.3-1). [unit]
Untestable automatically: none.

## 5. Seeded faults (fixture `scene_host`; `must` unless noted; planted inputs in `files/`)
| ID | Planted | Verb + args | Expect |
|---|---|---|---|
| FAULT-A2-01 | spec root prop `positoin` | `scene-gen {fault_dir}/files/s.scene.json` | 1 FAIL `\[scene\.unknown-property\].*hint: position`, `^saved: none` |
| FAULT-A2-02 | spec child type `Spirte2D` | scene-gen | 1 FAIL `\[scene\.unknown-type\].*Sprite2D` |
| FAULT-A2-03 | spec `"position": "abc"` | scene-gen | 1 FAIL `\[scene\.bad-value\]` |
| FAULT-A2-04 | spec with two children named `A` | scene-gen | 1 FAIL `\[scene\.duplicate-name\]` |
| FAULT-A2-05 | spec `"target": "Child"` (string for a Node export) | scene-gen | 1 FAIL `\[scene\.bad-value\].*\$node` |
| FAULT-A2-06 | spec connection to method `_on_nope` | scene-gen | 1 FAIL `\[scene\.bad-connection\]` |
| FAULT-A2-07 | ops `remove_node Sprite` | `scene-edit scenes/inh.tscn {fault_dir}/files/ops.json` | 1 FAIL `\[scene\.instance-internal\]` |
| FAULT-A2-08 | write `broken/bad_parent.tscn` (c10) | `digest broken/bad_parent.tscn` | 1 FAIL `!vanished`, `\[scene\.vanished-node\]` |
| FAULT-A2-09 | same file; ops set_prop on `.` | scene-edit | 1 FAIL `\[scene\.broken-input\]` |
| FAULT-A2-10 | ops rename `Sprite`->`Body` | `scene-edit scenes/child.tscn ...` | 1 FAIL `\[scene\.breaks-dependent\].*ov\.tscn`, `rolled back` |
| FAULT-A2-11 | `scripts/hang.gd` (`_init` loops), spec using it, `[timeouts] runner = 5` | scene-gen | 1 FAIL `\[harness\.hang\]`, `^saved: none`, <= 40 s |
| FAULT-A2-12 | ops `{"op": "move_node", ...}` | scene-edit | 2 ERROR `\[scene\.spec-schema\]` |
| FAULT-A2-13 | write `broken/two_roots.tscn` (c13) | digest | 1 FAIL `\[scene\.load-failed\]` |
| FAULT-A2-14 | spec `save` = existing `res://scenes/child.tscn`, no `--force` | scene-gen | 2 ERROR `exists \(use --force\)` |
| FAULT-A2-15 (nice) | write `broken/missing_inst.tscn` (c23) | digest | 1 FAIL `godot\.(load-failed\|error)` |
| CLEAN-A2-01 | none | `scene-gen specs/child2.scene.json` (new path) | 0 PASS `^saved: res://` |
| CLEAN-A2-02 | none | `scene-edit scenes/complex.tscn` with `{"ops": []}` | 0 PASS |
| CLEAN-A2-03 | none | `digest --project-summary` | 0 PASS `^autoload: GameState` |
Mutation hints for the verifier: drop `set_editable_instance` in `scene_edit.gd` (AC-02.23 must go red via
`scene.lossy-save`); skip owner on grandchildren (AC-02.11); accept unknown keys (AC-02.17); disable ext uid
reattach (AC-02.28).

## 6. Fixtures needed (T2)
`tests/fixtures/projects/scene_host/` (contract §2.11; must PASS `h check`):
- `project.godot`: name `scene_host`, `run/main_scene="res://scenes/complex.tscn"`, autoload `GameState`,
  `[layer_names]` `2d_physics/layer_1="world"`, `layer_2="player"`, `layer_3="hazard"`; `[input]` `jump` (physical
  Space), `left`, `right`.
- `scripts/hero.gd` (`extends Node2D`, `signal hit`, `@export var speed: int = 100`, `@export var target: Node`,
  `func _on_hit() -> void`); `scripts/player.gd` (`extends CharacterBody2D`, `@onready var sprite := $Sprite`,
  `func _on_hurt(_a: Area2D) -> void`); `scripts/game_state.gd`; `scripts/item.gd` (`class_name ItemData`,
  `extends Resource`, two exports) + `res/item.tres`.
- Hand-written per r1_4 §3: `scenes/child.tscn` (root hero.gd speed 250, `%Sprite` at (5, 6), `Inner` in group
  `inside`); `scenes/complex.tscn` (as AC-02.1); `scenes/inh.tscn` (§3.6: speed 900, Sprite override, own `Inner/Own`
  in group `mine`, self connection); `scenes/ov.tscn` (override `A/Sprite`, extra `A/Inner/Extra`, `[editable]`);
  `scenes/player.tscn` (~10 nodes: CharacterBody2D + player.gd, Sprite, CollisionShape2D + sub_resource, Camera2D,
  AnimationPlayer, Hurtbox Area2D + shape, a connection to `_on_hurt`); `scenes/editor_style.tscn` (header `uid=` and
  ext `uid=` for hero.gd: import a scratch copy once and copy the values; uids are deterministic for project name +
  path + content [Run r1_4 T4]; never commit `.uid` files); `addons/demo/demo.tscn` (excluded by default).
- `specs/{child,main,ov,child2,inherited,shapes}.scene.json` (`shapes` uses `$new` and `$layers`), saving to paths
  that do not exist yet in the fixture (`res://gen/...`) except where a test wants `--force`.
- Broken inputs stay out of the fixture: copy r1_4 cases c08, c10-c13, c18, c23 (`.claude/research/scripts/
  r1_4_scene_format/cases/`, they use `res://scripts/hero.gd`) into fault `files/` or test temp dirs. `FIXTURE.md`.

## 7. Build order (builder B2, after B1 step 2: `godot.py`, `out.py`, `checkrun.load_check` green; REVIEW §4)
1. `scenes/schema.py`, verb skeletons, rc 2 paths -> AC-02.9, 17; FAULT-A2-12.
2. `scene_digest.gd` scene mode + `model.render` -> AC-02.1-6, 10; FAULT-A2-08, 13, 15.
3. Resource and project modes -> AC-02.7, 8; CLEAN-A2-03.
4. `scene_gen.gd` build + checks, no post-verify -> AC-02.13-16, 19, 21; FAULT-A2-01..06, 11.
5. Post-write pipeline (load_check, digest-after, compare, rollback, uid restore, `--force`, multi-spec) ->
   AC-02.11, 12, 18, 20, 34; FAULT-A2-14; CLEAN-A2-01.
6. `scene_edit.gd` + effects model -> AC-02.22-26, 30; FAULT-A2-07, 09; CLEAN-A2-02.
7. Dependents, stale-ref, ext uid reattach -> AC-02.27-29; FAULT-A2-10.
8. selftest, budgets, e2e -> AC-02.31-33.

## 8. Out of scope, open questions, assumptions
### 8.1 Out of scope (v0)
`.tres` editing, binary `.scn`, assigning new uids, file move/rename (F6), transitive dependents, array-of-node
exports, signal `unbinds`, ops two instance levels deep [U], C# (D1), 3D-specific checks (D2), live editor (D3).
### 8.2 Open questions [U]
1. Whether the editor GUI rewrites a script-generated scene noisily on first save; `unique_id=` noise is accepted.
2. `scene.stale-ref` is a text heuristic; full path lint is A1/A3 (F4). 3. Scripts' `_init` runs during gen/edit
(F13, `@tool` not sandboxed). 4. Seed load by absolute path [Run] untested with `.gdignore`d run dirs.
### 8.3 Deviations (all accepted by REVIEW §1)
1. **Accepted (R-01).** Unit tests may import `harness.scenes.model` (pure, stdlib-only, side-effect-free) for
   AC-02.34; it is on the contract §2.12 allowlist. Public names: `render`, `diff`, `expected`, `compare`.
2. **Accepted (R-22).** Plan §7 "digest <= 60 lines" -> contract <= 40 + `more:` + digest.txt (contract §2.3);
   `--all-props` dropped (values always shown).
3. **Accepted (R-23).** Plan §3.2 `h digest --project` is spelled `--project-summary`, since `--project DIR` is a
   contract common flag.
4. **Accepted (R-21).** scene-edit ext `uid=` header-attribute rewrite (§3.3 step 4), as specified.
### 8.4 Assumptions about other areas
- A1 (R-30, closed): A1's load_check protocol is canonical. A2 uses only `checkrun.load_check(run, project,
  res_paths, smoke=0) -> list[dict]` (§3.3) and never runs `load_check.gd` itself or adds a mode to it (that would
  need an A1 re-plan). `godot.run` returns an `Invocation` (R-31); `ensure_imported` is explicit (R-32).
- A3 owns `tscn-*` text lint; A8's `.tscn` Edit/Write hook points to `h scene-edit`/`scene-gen`/`digest`. A9 commits
  one `*.scene.json` per sample scene, regenerates with `--force`, and mirrors any `h scene-edit` into the spec.
  Plan defaults D1-D5, B1-B8 as given; nothing in A2 needs Xvfb.
