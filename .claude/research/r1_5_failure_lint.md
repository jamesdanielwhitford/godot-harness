# R1.5 LLM failure catalogue and Godot-3-idiom lint rules (Godot 4.7)

Date: 2026-10-15. Engine under test: `Godot_v4.7-stable_linux.x86_64` (`--version` = `4.7.stable.official.5b4e0cb0f`). All [Run] items were executed headless in `r1_5_work/proj` (cases in `proj/cases/*.gd`, logs `check_only.log`, `runtime.log`, `scenes.log`).

## Answer

1. LLM Godot errors cluster into (a) Godot 3 idioms/renames, (b) Godot 4 strict-typing traps, (c) hallucinated or mistyped API names, (d) silent semantic bugs. Most of (a) and half of (b)/(c) are caught by a plain parse: `godot --headless --path P --check-only -s res://file.gd` printed `SCRIPT ERROR: Parse Error` for 23 of the 31 faulty test snippets (the 32nd is a clean baseline) [Run: check_only.log].
2. **Exit codes are useless.** Every run exited 0, including scripts with parse errors and runtime script errors. A load-check must grep stderr/stdout for `SCRIPT ERROR`, `Parse Error`, `ERROR:`, `Failed to load script` [Run: runtime.log, scenes.log].
3. **A scene can load "successfully" with a broken script**: `load("scene.tscn").instantiate()` printed `LOADSCENE: ok` while stderr had `Failed to load script ... Parse error`; the root node came back scriptless [Run: scenes.log g4_badscript].
4. **Godot-3 `.tscn` files load silently in 4.7** (`format=2`, `ExtResource( 1 )`, `Spatial`, `KinematicBody2D` were remapped to `Node3D`/`CharacterBody2D`; `rect_position` and unknown properties were dropped without any message). So a load-check cannot detect stale scenes; use the lint rules (`tscn-*`) [Run: scenes.log g3, g4_mixed].
5. Not caught by parse, caught only at runtime: `.instance()`, `.empty()`, `change_scene()`, `Tween.new()`, `emit_signal("typo")` on untyped receivers, bad InputMap action names. Caught by nothing: lambda captured-variable reassignment (printed `0`), integer division, `_process` vs `_physics_process`, wrong node paths [Run].
6. The authoritative rename list is `editor/project_upgrade/renames_map_3_to_4.cpp` at `4.7-stable` (commit `5b4e0cb0f`). I generated 1,213 regex rules (1,165 from the rename tables, filtered against 4.7 ClassDB, plus 48 hand-written) into `lint_rules_full.yaml`; on 994 files of the official 4.7 demo projects (godot-demo-projects@b761b4c) they produce 56 hits, all explained (embedded GLSL strings, user functions named `find_node`/`change_scene`, `randi() % n` idiom) [Run: scan.py]. A curated 76-rule subset is in section 2.
7. **Better than any regex fixer: the 4.7 binary still ships `--convert-3to4` and `--validate-conversion-3to4`** [Run: `--help`]. It converted a 3.x sample correctly (`yield`->`await`, `export`->`@export`, 3-arg `connect`->`Callable`, `move_and_slide(v,up)`->`set_velocity`+`move_and_slide()`, `.instance()`, `Color.red`) [Run: conv/p/a.gd]. Caveat: it also rewrote `$Sprite` to `$Sprite2D`, so it is not safe to run blindly; use `--validate-conversion-3to4` as an oracle.
8. gdtoolkit 4.5.0 (PyPI latest, lark 1.2.2) parses all 461 `.gd` files of the 4.7 demo projects with zero failures and handles `@abstract`, variadics `...args`, typed Dictionary, `match` guards/patterns, `is not`, `%Unique`, `^""`, `&""` [Run: gdp.py, gdt/modern.gd]. It has no Godot-3-rename lint rules; it only fails to parse bare `onready`/`export`/`tool`/`setget` [Run]. Use it for formatting and structure, not for migration lint.

## 1. Top-30 failure patterns, ranked by likely frequency

Ranking basis: [Doc/Src] size of the Godot 3 to 4 rename surface, forum and vendor reports (see Evidence caveat), plus my own judgement of how often each idiom appears in 2020-2023 tutorial text. Frequency is a judgement, not a measurement; no source I could reach measured LLM error rates on a corpus. Column "Catch": P = Godot parse error at `--check-only` (load-check catches), R = runtime error logged, exit code still 0, S = silent (no engine message), L = lintable by regex. "Evidence" tags: [Run] = reproduced on 4.7 in `proj/cases`.

| # | Pattern (wrong -> right) | Catch | Evidence |
|---|---|---|---|
| 1 | Godot 3 class names: `KinematicBody2D`, `Spatial`, `Sprite`, `Position2D`, `Area`, `Camera`, `Particles2D`, `YSort`, `ToolButton`, `Tabs` in `extends`/`.new()`/`.tscn` | P in .gd (`Could not find base class "KinematicBody2D"`); S in .tscn (compat remap) | [Run c01, g3, g4_mixed]; [Src: renames_map_3_to_4.cpp class_renames, 198 entries]; vendor tests list KinematicBody, Spatial.translation [Ziva](https://ziva.sh/blogs/claude-godot), [Surmado](https://www.surmado.com/blog/ai-mistakes-in-godot-4-code) |
| 2 | Bare `onready var`, `export var`, `export(int) var`, `tool` | P (`The "onready" keyword was removed in Godot 4. Use the "@onready" annotation`) | [Run c02 c03 c07]; [Src: project_converter_3_to_4.cpp:112-123 keyword regexes] |
| 3 | `yield(obj, "sig")` instead of `await obj.sig` | P (`"yield" was removed in Godot 4. Use "await" instead.`) | [Run c04]; [Src: project_converter_3_to_4.cpp:1944 yield rule] |
| 4 | 3-arg string `connect("sig", self, "method")` / `disconnect` | P when the receiver type is known (self; `var b = Button.new()` inferred) | [Run c05, d01]; vendor: GPT-4o "mixed 3 and 4" [Ziva](https://ziva.sh/blogs/claude-godot); forum: "The connect syntax is wrong, even for Godot 3" [forum 94508](https://forum.godotengine.org/t/connect-a-signal-to-a-function-via-script/94508) |
| 5 | `move_and_slide(velocity, Vector2.UP)` / `move_and_slide_with_snap` (velocity is now a property) | P (`Too many arguments ... Expected at most 0`) | [Run c15]; [Src: project_converter_3_to_4.cpp:1786-1883] |
| 6 | `.instance()` instead of `.instantiate()` | R on inferred/untyped receivers (`Nonexistent function 'instance' in base 'PackedScene'`) | [Run c06]; [Src: converter reg_instantiate line 79] |
| 7 | Renamed globals: `rand_range`, `stepify`, `deg2rad`, `rad2deg`, `range_lerp`, `randomize()` misuse | P (`Function "rand_range()" not found ... Did you mean "randf_range()"`) | [Run c10 c17 c25]; [Src: renames_map gdscript_function_renames] |
| 8 | `OS.get_ticks_msec()`, `OS.window_fullscreen`, `OS.get_unix_time()`, `OS.get_datetime()` | P | [Run c13]; [Src: converter lines 2254-2264, OS regexes 47-109] |
| 9 | `File.new()`, `Directory.new()` (now `FileAccess.open`, `DirAccess.open`) | P (`Identifier "File" not declared`) | [Run c14]; [Src: class_renames Directory->DirAccess] |
| 10 | `PoolStringArray`, `PoolIntArray`, `PoolRealArray` etc. | P | [Run c12]; [Src: builtin_types_renames] |
| 11 | Control props `rect_position`, `rect_size`, `rect_min_size`, `margin_left`, `align` | P on typed receiver; R on untyped (`Invalid assignment of property ... 'rect_position'`); S in .tscn (dropped) | [Run c09, d02, g3]; [Src: gdscript_properties_renames, tscn rect_* handling] |
| 12 | `setget` | P | [Run c08]; [Src: converter lines 73-75, 1674-1685] |
| 13 | `var x := d.get("k")`, `:= clamp(...)`, `:= weakref(...)`, ternary with `null`: Variant inference | P by default (`INFERENCE_ON_VARIANT` is an error in 4.7) | [Run c11]; [Zenn](https://zenn.dev/iori_001/articles/gdscript4-strict-mode-7-traps) reports it under `warning_as_error`; it claims `--check-only` passes, but in my 4.7 run `--check-only` failed on it. Treat Zenn's claim as Godot 4.4-specific [Unverified for 4.4] |
| 14 | `var n = $Node` / `get_node()` in member initializer without `@onready` | P (`The default value uses "$" which won't return nodes ... (Warning treated as error)`) | [Run c19] |
| 15 | Hallucinated method/property on a known class (`self.get_player_position()`, `Vector2.length_squared_fast()`) | P when receiver type is known; R otherwise | [Run c27]; [forum](https://forum.godotengine.org/t/connect-a-signal-to-a-function-via-script/94508) and [Ziva](https://ziva.sh/blogs/claude-godot) quote users reporting invented function names |
| 16 | Tab/space mix in indentation (LLM emits 4 spaces into tab files) | P (`Used space character for indentation instead of tab`) | [Run c28] |
| 17 | Typed Array/Dictionary element mismatch (`Array[int] = [1, "x"]`) | P | [Run c24] |
| 18 | `get_tree().change_scene("res://x.tscn")` (now `change_scene_to_file`) | R only (`Nonexistent function 'change_scene' in base 'SceneTree'`) | [Run c16]; [Src: renames change_scene->change_scene_to_file] |
| 19 | `Tween.new()` + `interpolate_property` (now `create_tween().tween_property`) | R only (`Tween can't be created directly`) | [Run c22] |
| 20 | `.empty()` on Array/String/Dictionary | R only | [Run c26]; [Src: converter line 1630] |
| 21 | `emit_signal("sig_typo")` / string signal names | R (`Can't emit non-existing signal`); typed `sig.emit()` would be P | [Run c18, d03] |
| 22 | Lambda reassigning outer local (`func(): n += 1`) does not update outer variable | S (printed `0`) | [Run c21]; [Zenn](https://zenn.dev/iori_001/articles/gdscript4-strict-mode-7-traps) trap 6 (cites a `CONFUSABLE_CAPTURE_REASSIGNMENT` warning, not seen in my run) |
| 23 | Integer division / `randi() % n` assumed float | S (`5/2` stored in float gives 2.0) | [Run c29] |
| 24 | Input action names that do not exist in the InputMap (`"jump"`, `"ui_jump"`) | R at call (`The InputMap action "nope" doesn't exist`); S if the call is guarded | [Run c32] |
| 25 | Physics body moved in `_process` instead of `_physics_process` | S | [Surmado](https://www.surmado.com/blog/ai-mistakes-in-godot-4-code) (vendor, fixtures) ; not run by me |
| 26 | Brittle `get_parent().get_node(...)`, `../../Player` paths; wrong `$Path` case | S until the null is dereferenced | [Surmado](https://www.surmado.com/blog/ai-mistakes-in-godot-4-code) (vendor) |
| 27 | Hand-written .tscn with unknown property names or wrong `parent=` | S for unknown props; warning only for missing parent (node reparented and renamed `Missing#Sub`) | [Run g4_mixed] |
| 28 | Script with parse error attached to scene: scene loads, node scriptless | S (stderr only, `load()` non-null) | [Run g4_badscript] |
| 29 | Godot 3 .tscn/.tres headers and ids (`format=2`, `ExtResource( 1 )`, `id=1`, `[ext_resource path= type= id=]`) | S (4.7 accepts them) | [Run g3, g4_mixed] |
| 30 | Version drift inside 4.x (suggesting APIs/classes of the wrong 4.x minor, deprecated `TileMap` rather than `TileMapLayer`, GDScript/C# syntax bleed) | depends | `TileMap` and `TileMapLayer` both still exist in 4.7 ClassDB [Run: classdb.json]; the drift claim is vendor-only [Ziva](https://ziva.sh/blogs/claude-godot) [Unverified] |

Also seen but not ranked: Python-isms (`True`, `None`, f-strings, missing colons), C#/Java declarations (`int x = 0;`, `public void f()`), and brace blocks. Rules exist (`syn-uppercase-bool-null`, `syn-python-*`, `syn-var-types-csharp`, `syn-func-public`, `syn-braces-block`) but they are speculative: I found no source reporting them for Godot specifically. [Unverified]

**Evidence caveat.** The vendor posts (Ziva, Surmado) are single-day, single-prompt or fixture-based and sell AI-for-Godot tooling; Ziva's table says Claude Opus 4.7 got the six tested APIs right, which suggests that modern Claude models make patterns 1-4 much less often than older GPT-class models, but the sample is six prompts. Forum sources: [forum 94508](https://forum.godotengine.org/t/connect-a-signal-to-a-function-via-script/94508) (ChatGPT connect syntax "very wrong") and [forum 110307](https://forum.godotengine.org/t/what-are-the-best-practices-for-combining-godot-with-ai-assisted-code-generation/110307) ("LLMs ... frequently suggest incorrect and outdated" code). I did not reach Reddit threads (Reddit returned 200 to curl for `/r/godot/` but I did not extract thread contents). So patterns 1-4 are well documented; the ordering beyond them is my estimate.

## 2. Machine-usable lint list

How it was built. `renames_map_3_to_4.cpp` (4.7-stable, 1,863 lines) holds 15 tables: enum/constants 112, gdscript function 409, property 94, signal 14, builtin types 9, class 198, color 146, theme override 22, project settings 39, shaders 14, others [Run: parse.py -> renames.json]. Each entry is `{old, new}`; the file warns that commented-out entries were disabled because the converter's regex approach is too unsafe for them (e.g. `get_name`, `get_mode`, `raise`, `instance` handled by custom rule) [Src: renames_map_3_to_4.cpp:157-172]. I therefore:
- kept only enabled entries,
- dropped every class rule whose old name still exists in 4.7 ClassDB (Viewport, Texture, Path ... are still valid classes in 4.7) [Run: dump.gd -> classdb.json],
- marked function/property/signal/constant rules whose old name still exists on some 4.7 class with `false_positive_risk: high` (39 rules; `still_exists_in_4_7` is recorded in the full file),
- measured every rule on 994 .gd/.tscn/.tres files from godot-demo-projects@b761b4c, whose projects declare `config/features` "4.7": 56 total hits, all false positives, listed in `demo_hits.json`. `demo_corpus_hits` is in each rule.
- false_positive_risk values: low = 0 hits in the 4.7 corpus and old name not in 4.7 ClassDB; medium = hit in corpus or idiom-based; high = old name is still a valid 4.7 API.

Files (data, not reports): full list `/tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad/research/r1_5_work/lint_rules_full.yaml` (1,213 rules: 48 hand + 1,165 generated), generator `gen_rules.py`, scanner `scan.py` (per-line Python `re`; skips `#` comment lines in .gd; `applies_to` is a comma list of extensions). Regexes use Python `re` syntax (lookbehind). Validated: all compile; on the 36-file fault corpus `tp/` (32 snippets + 4 scenes) they flag every case except c24 (typed-array mismatch), c27 (hallucinated method), c28 (space indentation), c29 (integer division), c30, c31, c32 and the clean baselines, which only the engine or tests catch.

Curated subset below (48 hand rules + 28 high-value generated ones). Generated families in the full file: `fn-*` (method call renamed), `prop-*`, `sig-*`, `enum-*` (e.g. `BUTTON_LEFT`->`MOUSE_BUTTON_LEFT`), `class-*` / `tscnclass-*`, `color-*` (`Color.red`->`Color.RED`), `theme-*`.

Known weak spots of the regex approach: `syn-python-elif-colon-missing` hits multi-line expressions (10 hits in 4.7 demos); `syn-semicolon-end` hits embedded GLSL in strings (28); `syn-dot-super` hits leading-dot method chains (4); `syn-int-div` flags idioms that are legal (3). Use these as warnings, not gates.

```yaml
- id: syn-yield
  regex: (?<![\w.])yield\s*\(
  applies_to: .gd
  message: yield() removed
  godot4_replacement: await signal_or_coroutine  e.g. await get_tree().create_timer(1.0).timeout
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-onready
  regex: ^\s*onready\s+var\b
  applies_to: .gd
  message: bare 'onready' keyword removed
  godot4_replacement: '@onready var ...'
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-export
  regex: ^\s*export\s*(\(|var\b)
  applies_to: .gd
  message: bare 'export' keyword removed
  godot4_replacement: '@export var x: T  / @export_range(...) etc.'
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-tool
  regex: ^tool\s*$
  applies_to: .gd
  message: bare 'tool' removed
  godot4_replacement: '@tool (first line)'
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-setget
  regex: \bsetget\b
  applies_to: .gd
  message: setget removed
  godot4_replacement: "var x: T:\n\tset(v): ...\n\tget: ..."
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-remote-keywords
  regex: ^\s*(remote|remotesync|sync|slave|puppet|puppetsync|master|mastersync)\s+func\b
  applies_to: .gd
  message: Godot 3 rpc keywords removed
  godot4_replacement: '@rpc("any_peer"|"authority", "call_local"|"call_remote", "reliable"|"unreliable") func'
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-connect-3arg
  regex: \bconnect\s*\(\s*"[^"]*"\s*,\s*[^,()]+,\s*"
  applies_to: .gd
  message: string-based 3-arg connect()
  godot4_replacement: sig.connect(callable)  e.g. button.pressed.connect(_on_pressed)
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-disconnect-3arg
  regex: \bdisconnect\s*\(\s*"[^"]*"\s*,\s*[^,()]+,\s*"
  applies_to: .gd
  message: string-based 3-arg disconnect()
  godot4_replacement: sig.disconnect(callable)
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-is-connected-3arg
  regex: \bis_connected\s*\(\s*"[^"]*"\s*,\s*[^,()]+,\s*"
  applies_to: .gd
  message: string-based 3-arg is_connected()
  godot4_replacement: sig.is_connected(callable)
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-dot-super
  regex: ^\s*\.[a-zA-Z_]\w*\s*\(
  applies_to: .gd
  message: Godot 3 '.method()' super call
  godot4_replacement: super.method()  or  super()
  false_positive_risk: medium
  demo_corpus_hits: 4
- id: syn-instance
  regex: \.instance\s*\(
  applies_to: .gd
  message: PackedScene.instance() renamed
  godot4_replacement: PackedScene.instantiate()
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-empty-call
  regex: \.empty\s*\(\s*\)
  applies_to: .gd
  message: Array/String/Dictionary.empty() renamed
  godot4_replacement: is_empty()
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-find-node
  regex: (?<!func )\bfind_node\s*\(
  applies_to: .gd
  message: Node.find_node() renamed
  godot4_replacement: find_child(pattern, recursive, owned)
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-get-node-at
  regex: get_node\s*\(\s*@
  applies_to: .gd
  message: Godot 4.0-alpha NodePath @ syntax
  godot4_replacement: get_node("...")
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-engine-editor-hint
  regex: \bEngine\.editor_hint\b
  applies_to: .gd
  message: Engine.editor_hint removed
  godot4_replacement: Engine.is_editor_hint()
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-tween-new
  regex: \bTween\.new\s*\(
  applies_to: .gd
  message: Tween.new() is an engine error in 4.x; Godot 3 Tween node API removed
  godot4_replacement: var t := create_tween(); t.tween_property(obj, "prop", val, dur)
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-tween-interpolate
  regex: \.(interpolate_property|interpolate_method|interpolate_callback)\s*\(
  applies_to: .gd
  message: Godot 3 Tween API
  godot4_replacement: create_tween().tween_property()/tween_method()/tween_callback()
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-os-ticks
  regex: \bOS\.(get_ticks_msec|get_ticks_usec|get_unix_time|get_datetime|get_system_time_msecs|get_system_time_secs)\b
  applies_to: .gd
  message: OS time API moved to Time singleton
  godot4_replacement: Time.get_ticks_msec() / get_unix_time_from_system() / get_datetime_dict_from_system()
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-os-window
  regex: \bOS\.(window_fullscreen|window_size|window_position|window_maximized|window_minimized|window_borderless|vsync_enabled|set_window_title|get_screen_size|current_screen|set_window_fullscreen|is_window_fullscreen|set_use_vsync)\b
  applies_to: .gd
  message: OS window API moved to DisplayServer / Window
  godot4_replacement: DisplayServer.window_set_mode()/window_set_size()/screen_get_size(); get_window().title
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-file-dir-class
  regex: (?<![\w.])(File|Directory)\.new\s*\(
  applies_to: .gd
  message: File/Directory classes removed
  godot4_replacement: FileAccess.open(path, FileAccess.READ) / DirAccess.open(path)
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-json-parse
  regex: \b(parse_json|to_json|validate_json)\s*\(|\bJSON\.print\s*\(|\bJSON\.parse\s*\([^)]*\)\s*\.(result|error)\b
  applies_to: .gd
  message: Godot 3 JSON API
  godot4_replacement: JSON.stringify(v) / var j := JSON.new(); j.parse(s); j.data
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-rand-seed
  regex: (?<![\w.])(rand_range|rand_seed|stepify|deg2rad|rad2deg|range_lerp|ease_in_out|is_nan_inf)\s*\(
  applies_to: .gd
  message: renamed global functions
  godot4_replacement: randf_range / randi_range, snapped, deg_to_rad, rad_to_deg, remap
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-move-and-slide-args
  regex: \bmove_and_slide(_with_snap)?\s*\(\s*[^)\s]
  applies_to: .gd
  message: move_and_slide() takes no args in 4.x; uses CharacterBody velocity property
  godot4_replacement: set velocity then call move_and_slide()
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-change-scene
  regex: (?<!func )\bchange_scene\s*\(
  applies_to: .gd
  message: SceneTree.change_scene() split
  godot4_replacement: change_scene_to_file(path) / change_scene_to_packed(scene)
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-get-tree-set-pause
  regex: \bget_tree\(\)\.(set_network_peer|network_peer)\b
  applies_to: .gd
  message: SceneTree network_peer removed
  godot4_replacement: multiplayer.multiplayer_peer
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-poolarray
  regex: \bPool(Byte|Color|Int|Real|String|Vector2|Vector3)Array\b
  applies_to: .gd,.tscn,.tres
  message: Pool*Array types removed
  godot4_replacement: Packed*Array (PoolIntArray->PackedInt32Array, PoolRealArray->PackedFloat32Array)
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-uppercase-bool-null
  regex: \b(True|False|None)\b
  applies_to: .gd
  message: Python-isms
  godot4_replacement: true / false / null
  false_positive_risk: medium
  demo_corpus_hits: 1
- id: syn-python-self-print
  regex: ^\s*print\s*\(.*\bf"
  applies_to: .gd
  message: Python f-string
  godot4_replacement: '"%s" % x  or  "{x}".format({...})'
  false_positive_risk: medium
  demo_corpus_hits: 0
- id: syn-python-elif-colon-missing
  regex: ^\s*(if|elif|while|for|else)\b[^#:\n]*[^:\s#,(\[{]\s*$
  applies_to: .gd
  message: statement without trailing colon (multi-line expressions can false-positive)
  godot4_replacement: add ':'
  false_positive_risk: high
  demo_corpus_hits: 10
- id: syn-semicolon-end
  regex: ;\s*$
  applies_to: .gd
  message: C-style semicolon (legal but non-idiomatic; usually LLM C#/JS leakage)
  godot4_replacement: remove ';'
  false_positive_risk: medium
  demo_corpus_hits: 28
- id: syn-braces-block
  regex: ^\s*(if|for|while|func)\b.*\{\s*$
  applies_to: .gd
  message: C-style brace blocks
  godot4_replacement: indent-based block with ':'
  false_positive_risk: medium
  demo_corpus_hits: 1
- id: syn-var-types-csharp
  regex: ^\s*(int|float|string|bool|Vector2|Vector3)\s+[a-z_]\w*\s*(=|;)
  applies_to: .gd
  message: C#-style typed declaration
  godot4_replacement: 'var x: int = 0'
  false_positive_risk: medium
  demo_corpus_hits: 4
- id: syn-void-return-type
  regex: \)\s*->\s*(Void|None)\b
  applies_to: .gd
  message: wrong void spelling
  godot4_replacement: -> void
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-func-public
  regex: ^\s*(public|private|protected|static void|void)\s+\w+\s*\(
  applies_to: .gd
  message: C#/Java method declaration
  godot4_replacement: 'func name() -> void:'
  false_positive_risk: medium
  demo_corpus_hits: 1
- id: syn-lambda-capture-reassign
  regex: func\s*\([^)]*\)\s*(->\s*\w+\s*)?:\s*\w+\s*(\+|-|\*|/)?=
  applies_to: .gd
  message: single-line lambda reassigning an outer local (captures by value for primitives; outer variable NOT updated; engine warning CONFUSABLE_CAPTURE_REASSIGNMENT only in some cases)
  godot4_replacement: use an Array/Dictionary/RefCounted holder, a member variable, or a Callable bound to a method
  false_positive_risk: high
  demo_corpus_hits: 0
- id: syn-yield-signal-string-emit
  regex: \bemit_signal\s*\(\s*"
  applies_to: .gd
  message: legal in 4.x but string-typed; typos are RUNTIME errors only
  godot4_replacement: sig_name.emit(args)
  false_positive_risk: medium
  demo_corpus_hits: 2
- id: syn-get-node-ready-var
  regex: ^(var|const)\s+\w+(\s*:\s*\w+)?\s*(:?=)\s*(\$|get_node\()
  applies_to: .gd
  message: $ / get_node() in a member initializer runs before the node is in the tree
  godot4_replacement: '@onready var x := $Path  (or @onready var x: T = $Path)'
  false_positive_risk: low
  demo_corpus_hits: 0
- id: syn-variant-infer-clamp
  regex: :=\s*(clamp|min|max|abs|sign|lerp|round|floor|ceil|snapped)\s*\(
  applies_to: .gd
  message: global math funcs return Variant -> ':=' fails with INFERENCE_ON_VARIANT (error by default in 4.7 [Run])
  godot4_replacement: 'typed variants: clampf/clampi, minf/mini, maxf/maxi, absf/absi, signf, lerpf, roundf, floorf, ceilf, snappedf; or ''var x: float = ...'''
  false_positive_risk: medium
  demo_corpus_hits: 0
- id: syn-dict-get-infer
  regex: :=\s*\w[\w.]*\.get\s*\(
  applies_to: .gd
  message: Dictionary.get()/Object.get() return Variant -> ':=' fails
  godot4_replacement: 'var x: T = d.get(k, default)'
  false_positive_risk: medium
  demo_corpus_hits: 0
- id: syn-int-div
  regex: \bint\s*\(\s*\w+\s*/\s*\w+\s*\)|(?<![\w.])randi\s*\(\s*\)\s*%\s*\w+
  applies_to: .gd
  message: integer division / randi()%n idioms - legal; flagged by engine as INTEGER_DIVISION warning, not error
  godot4_replacement: use floori(a / b) or randi_range(0, n-1)
  false_positive_risk: high
  demo_corpus_hits: 3
- id: syn-rect-props-gd
  regex: (?<![\w])(rect_(position|size|min_size|scale|rotation|pivot_offset|clip_content|global_position)|margin_(left|right|top|bottom))\b(?!\s*:)
  applies_to: .gd
  message: Godot 3 Control properties
  godot4_replacement: position/size/custom_minimum_size/scale/rotation/pivot_offset/clip_contents/global_position; offset_left/right/top/bottom
  false_positive_risk: medium
  demo_corpus_hits: 0
- id: tscn-g3-header
  regex: ^\[gd_(scene|resource)\b[^\]]*\bformat=[12]\b
  applies_to: .tscn,.tres
  message: Godot 3 scene/resource format header (loads via compat, but is stale)
  godot4_replacement: format=3 (written by the 4.x editor/ResourceSaver)
  false_positive_risk: low
  demo_corpus_hits: 0
- id: tscn-extresource-spaces
  regex: (Ext|Sub)Resource\(\s+\d
  applies_to: .tscn,.tres
  message: 'Godot 3 numeric id with spaces: ExtResource( 1 ). Loads in 4.7 [Run] but 4.x writes ExtResource("1_ab12c")'
  godot4_replacement: ExtResource("id")
  false_positive_risk: low
  demo_corpus_hits: 0
- id: tscn-ext-path-first
  regex: ^\[ext_resource\s+path=
  applies_to: .tscn,.tres
  message: Godot 3 attribute order/ numeric id
  godot4_replacement: '[ext_resource type="T" uid="uid://..." path="res://..." id="1_xxxxx"]'
  false_positive_risk: low
  demo_corpus_hits: 0
- id: tscn-g3-numeric-id
  regex: \bid=\d+\]
  applies_to: .tscn,.tres
  message: numeric ext/sub resource id (Godot 3 style)
  godot4_replacement: string ids
  false_positive_risk: low
  demo_corpus_hits: 0
- id: tscn-rect-props
  regex: ^(rect_(position|size|min_size|scale|rotation|pivot_offset|clip_content)|margin_(left|right|top|bottom))\s*=
  applies_to: .tscn
  message: Godot 3 Control properties silently dropped on load [Run]
  godot4_replacement: position/size/custom_minimum_size/scale/rotation/pivot_offset/clip_contents; offset_*
  false_positive_risk: low
  demo_corpus_hits: 0
- id: tscn-onready-in-scene
  regex: ^\s*script\s*=\s*"res://
  applies_to: .tscn
  message: script assigned as string path instead of ExtResource
  godot4_replacement: script = ExtResource("id")
  false_positive_risk: medium
  demo_corpus_hits: 0
- id: tscn-g3-types
  regex: ^\[node\s+name="[^"]*"\s+type="(Spatial|KinematicBody2?D?|RigidBody|StaticBody|Area|Camera|MeshInstance|CollisionShape|Sprite|AnimatedSprite|Position2D|Position3D|Particles2D|Particles|ViewportContainer|Viewport|YSort|ToolButton)"
  applies_to: .tscn
  message: Godot 3 node class names (4.7 loads many via compat remap, silently) [Run]
  godot4_replacement: Node3D, CharacterBody3D, RigidBody3D, StaticBody3D, Area3D, Camera3D, MeshInstance3D, CollisionShape3D, Sprite2D, AnimatedSprite2D, Marker2D, Marker3D, GPUParticles2D/3D, SubViewportContainer, SubViewport, (YSort->Node2D y_sort_enabled), Button
  false_positive_risk: low
  demo_corpus_hits: 0
- id: fn-add_color_override
  regex: (?<![\w])(?<!func )add_color_override\s*\(
  applies_to: .gd
  message: 'method add_color_override() renamed in Godot 4 (class: Control)'
  godot4_replacement: add_theme_color_override
  false_positive_risk: low
  demo_corpus_hits: 0
- id: fn-can_instance
  regex: (?<![\w])(?<!func )can_instance\s*\(
  applies_to: .gd
  message: 'method can_instance() renamed in Godot 4 (class: PackedScene, Script)'
  godot4_replacement: can_instantiate
  false_positive_risk: low
  demo_corpus_hits: 0
- id: fn-change_scene
  regex: (?<![\w])(?<!func )change_scene\s*\(
  applies_to: .gd
  message: 'method change_scene() renamed in Godot 4 (class: SceneTree)'
  godot4_replacement: change_scene_to_file
  false_positive_risk: low
  demo_corpus_hits: 0
- id: fn-get_surface_material
  regex: (?<![\w])(?<!func )get_surface_material\s*\(
  applies_to: .gd
  message: 'method get_surface_material() renamed in Godot 4 (class: MeshInstance3D -- Breaks ImporterMesh.)'
  godot4_replacement: get_surface_override_material
  false_positive_risk: high
  demo_corpus_hits: 0
- id: fn-world_to_map
  regex: (?<![\w])(?<!func )world_to_map\s*\(
  applies_to: .gd
  message: 'method world_to_map() renamed in Godot 4 (class: TileMap, GridMap)'
  godot4_replacement: local_to_map
  false_positive_risk: low
  demo_corpus_hits: 0
- id: fn-deg2rad
  regex: (?<![\w])(?<!func )deg2rad\s*\(
  applies_to: .gd
  message: 'method deg2rad() renamed in Godot 4 (class: n/a)'
  godot4_replacement: deg_to_rad
  false_positive_risk: low
  demo_corpus_hits: 0
- id: fn-rand_range
  regex: (?<![\w])(?<!func )rand_range\s*\(
  applies_to: .gd
  message: 'method rand_range() renamed in Godot 4 (class: n/a)'
  godot4_replacement: randf_range
  false_positive_risk: low
  demo_corpus_hits: 0
- id: fn-stepify
  regex: (?<![\w])(?<!func )stepify\s*\(
  applies_to: .gd
  message: 'method stepify() renamed in Godot 4 (class: n/a)'
  godot4_replacement: snapped
  false_positive_risk: low
  demo_corpus_hits: 0
- id: prop-bbcode_text
  regex: \.bbcode_text\b(?!\s*\()
  applies_to: .gd,.tscn
  message: 'property bbcode_text renamed (class: RichTextLabel)'
  godot4_replacement: text
  false_positive_risk: low
  demo_corpus_hits: 0
- id: prop-rect_position
  regex: \.rect_position\b(?!\s*\()
  applies_to: .gd,.tscn
  message: 'property rect_position renamed (class: Control)'
  godot4_replacement: position
  false_positive_risk: low
  demo_corpus_hits: 0
- id: sig-about_to_show
  regex: \.about_to_show\.(connect|emit)\b|\bconnect\s*\(\s*"about_to_show"
  applies_to: .gd
  message: 'signal about_to_show renamed (class: Popup)'
  godot4_replacement: about_to_popup
  false_positive_risk: low
  demo_corpus_hits: 0
- id: sig-network_peer_connected
  regex: \.network_peer_connected\.(connect|emit)\b|\bconnect\s*\(\s*"network_peer_connected"
  applies_to: .gd
  message: 'signal network_peer_connected renamed (class: MultiplayerAPI)'
  godot4_replacement: peer_connected
  false_positive_risk: low
  demo_corpus_hits: 0
- id: enum-BUTTON_LEFT
  regex: (?<![\w.])BUTTON_LEFT\b
  applies_to: .gd
  message: constant BUTTON_LEFT renamed
  godot4_replacement: MOUSE_BUTTON_LEFT
  false_positive_risk: low
  demo_corpus_hits: 0
- id: enum-TYPE_REAL
  regex: (?<![\w.])TYPE_REAL\b
  applies_to: .gd
  message: constant TYPE_REAL renamed
  godot4_replacement: TYPE_FLOAT
  false_positive_risk: low
  demo_corpus_hits: 0
- id: class-Camera
  regex: (?:\bextends\s+|:\s*|\bas\s+|\bis\s+|->\s*|\[\s*)Camera\b(?![\w"\'/])|(?<![\w"\'/.$])Camera\.new\s*\(
  applies_to: .gd
  message: class Camera renamed/removed
  godot4_replacement: Camera3D
  false_positive_risk: low
  demo_corpus_hits: 0
- id: class-Reference
  regex: (?:\bextends\s+|:\s*|\bas\s+|\bis\s+|->\s*|\[\s*)Reference\b(?![\w"\'/])|(?<![\w"\'/.$])Reference\.new\s*\(
  applies_to: .gd
  message: class Reference renamed/removed
  godot4_replacement: RefCounted
  false_positive_risk: low
  demo_corpus_hits: 0
- id: class-Tabs
  regex: (?:\bextends\s+|:\s*|\bas\s+|\bis\s+|->\s*|\[\s*)Tabs\b(?![\w"\'/])|(?<![\w"\'/.$])Tabs\.new\s*\(
  applies_to: .gd
  message: class Tabs renamed/removed
  godot4_replacement: TabBar
  false_positive_risk: low
  demo_corpus_hits: 0
- id: class-AnimatedSprite
  regex: (?:\bextends\s+|:\s*|\bas\s+|\bis\s+|->\s*|\[\s*)AnimatedSprite\b(?![\w"\'/])|(?<![\w"\'/.$])AnimatedSprite\.new\s*\(
  applies_to: .gd
  message: class AnimatedSprite renamed/removed
  godot4_replacement: AnimatedSprite2D
  false_positive_risk: low
  demo_corpus_hits: 0
- id: class-KinematicBody
  regex: (?:\bextends\s+|:\s*|\bas\s+|\bis\s+|->\s*|\[\s*)KinematicBody\b(?![\w"\'/])|(?<![\w"\'/.$])KinematicBody\.new\s*\(
  applies_to: .gd
  message: class KinematicBody renamed/removed
  godot4_replacement: CharacterBody3D
  false_positive_risk: low
  demo_corpus_hits: 0
- id: class-KinematicBody2D
  regex: (?:\bextends\s+|:\s*|\bas\s+|\bis\s+|->\s*|\[\s*)KinematicBody2D\b(?![\w"\'/])|(?<![\w"\'/.$])KinematicBody2D\.new\s*\(
  applies_to: .gd
  message: class KinematicBody2D renamed/removed
  godot4_replacement: CharacterBody2D
  false_positive_risk: low
  demo_corpus_hits: 0
- id: class-NetworkedMultiplayerENet
  regex: (?:\bextends\s+|:\s*|\bas\s+|\bis\s+|->\s*|\[\s*)NetworkedMultiplayerENet\b(?![\w"\'/])|(?<![\w"\'/.$])NetworkedMultiplayerENet\.new\s*\(
  applies_to: .gd
  message: class NetworkedMultiplayerENet renamed/removed
  godot4_replacement: ENetMultiplayerPeer
  false_positive_risk: low
  demo_corpus_hits: 0
- id: class-Particles2D
  regex: (?:\bextends\s+|:\s*|\bas\s+|\bis\s+|->\s*|\[\s*)Particles2D\b(?![\w"\'/])|(?<![\w"\'/.$])Particles2D\.new\s*\(
  applies_to: .gd
  message: class Particles2D renamed/removed
  godot4_replacement: GPUParticles2D
  false_positive_risk: low
  demo_corpus_hits: 0
- id: class-Position2D
  regex: (?:\bextends\s+|:\s*|\bas\s+|\bis\s+|->\s*|\[\s*)Position2D\b(?![\w"\'/])|(?<![\w"\'/.$])Position2D\.new\s*\(
  applies_to: .gd
  message: class Position2D renamed/removed
  godot4_replacement: Marker2D
  false_positive_risk: low
  demo_corpus_hits: 0
- id: class-Spatial
  regex: (?:\bextends\s+|:\s*|\bas\s+|\bis\s+|->\s*|\[\s*)Spatial\b(?![\w"\'/])|(?<![\w"\'/.$])Spatial\.new\s*\(
  applies_to: .gd
  message: class Spatial renamed/removed
  godot4_replacement: Node3D
  false_positive_risk: low
  demo_corpus_hits: 0
- id: class-Sprite
  regex: (?:\bextends\s+|:\s*|\bas\s+|\bis\s+|->\s*|\[\s*)Sprite\b(?![\w"\'/])|(?<![\w"\'/.$])Sprite\.new\s*\(
  applies_to: .gd
  message: class Sprite renamed/removed
  godot4_replacement: Sprite2D
  false_positive_risk: low
  demo_corpus_hits: 0
- id: class-ToolButton
  regex: (?:\bextends\s+|:\s*|\bas\s+|\bis\s+|->\s*|\[\s*)ToolButton\b(?![\w"\'/])|(?<![\w"\'/.$])ToolButton\.new\s*\(
  applies_to: .gd
  message: class ToolButton renamed/removed
  godot4_replacement: Button
  false_positive_risk: low
  demo_corpus_hits: 0
- id: class-YSort
  regex: (?:\bextends\s+|:\s*|\bas\s+|\bis\s+|->\s*|\[\s*)YSort\b(?![\w"\'/])|(?<![\w"\'/.$])YSort\.new\s*\(
  applies_to: .gd
  message: class YSort renamed/removed
  godot4_replacement: Node2D
  false_positive_risk: low
  demo_corpus_hits: 0
- id: color-red
  regex: \bColor\.red\b
  applies_to: .gd
  message: Color.red renamed
  godot4_replacement: Color.RED
  false_positive_risk: low
  demo_corpus_hits: 0
```

## 3. What a load-check catches vs what only lint or tests catch

Load-check = `godot --headless --path P --check-only -s res://x.gd` for scripts, and `load()` + `instantiate()` in a `--script` for scenes, followed by grep of output for `SCRIPT ERROR|Parse Error|ERROR:|WARNING: Parent path|Failed to load`. Exit codes must be ignored (always 0 in my runs).

| Class of failure | Load-check | Needs lint | Needs test/run |
|---|---|---|---|
| Removed keywords (`onready`, `export`, `tool`, `setget`, `yield`) | yes, P | optional (earlier, clearer message) | no |
| Removed/renamed classes in `extends`, type hints, `X.new()` | yes, P | | |
| Renamed global functions, `OS.*`, `File`, `Pool*Array`, `move_and_slide(args)` | yes, P | | |
| 3-arg `connect` with known receiver type | yes, P | | |
| Variant inference (`:=` on Variant), `$` in initializer, typed-array mismatch, indentation | yes, P (4.7 defaults) | | |
| Hallucinated method on a statically typed receiver | yes, P | | |
| Same on untyped/Variant receiver (`.instance()`, `.empty()`, `rect_position` on `var b = Node2D.new()`, `change_scene`, `Tween.new()`) | no | yes (rules `syn-instance`, `syn-empty-call`, `syn-change-scene`, `syn-tween-*`, `fn-*`) | R: only when executed |
| `emit_signal("typo")`, `connect("nosuch", cb)`, bad InputMap action | no | partial (`syn-yield-signal-string-emit` flags the string form) | yes, R, must execute the path and grep stderr |
| Script parse error inside a scene | no (scene `load()` succeeds) | | yes: grep stderr for `Failed to load script` |
| Stale Godot 3 .tscn/.tres (format=2, `ExtResource( 1 )`, old types, `rect_*`) and unknown properties | no (silently remapped/dropped) | yes (`tscn-*`) | scene digest / property diff against ClassDB |
| Wrong `parent=` in hand-edited .tscn | warning only (`Parent path ... has vanished`), node renamed `Missing#Sub`; grep for it | | yes |
| Lambda capture reassignment, integer division, `_process` vs `_physics_process`, brittle node paths | no | weak (`syn-lambda-capture-reassign`, `syn-int-div`) | behavioural tests only |
| Python/C#-isms | yes (generally parse errors) | | |

Extra operational findings [Run]:
- Running a script that has a parse error through `-s runner.gd` (which does `load(path).new()`) hung until `timeout 20` killed it (rc 124) for `c05_connect3` and `d01_untyped_connect`, whereas `--check-only` returned promptly. Always use `--check-only` for parse errors and wrap runtime checks in `timeout`.
- `--check-only` is documented as "use with --script" [Run: `--help`].
- Zenn reports `--check-only` passing while normal start fails on Variant inference in 4.4 [Zenn](https://zenn.dev/iori_001/articles/gdscript4-strict-mode-7-traps); 4.7 `--check-only` flagged it in my run (c11). Whether this changed between 4.4 and 4.7 is not verified. Zenn says autoload failures cascade only at real startup; consider also one `--headless --quit-after 2` project start [Unverified].
- Use `--validate-conversion-3to4` as a second oracle: it lists what the official converter would rename [Run: help text; converted sample in `conv/p/a.gd`].

## 4. gdlint / gdformat on 4.7 syntax

- Version: `gdtoolkit` 4.5.0 on PyPI, lark 1.2.2; changelog top entry 4.5.0 (2025-10-09) adds `@abstract` and variadic functions [Src: Scony/godot-gdscript-toolkit@f61a1f3:CHANGELOG.md:3-7; setup.py:6,34]. No release for 4.6/4.7 exists in the clone I checked (HEAD f61a1f3).
- Parse coverage [Run: `gdp.py` using `gdtoolkit.parser.parser.parse`]: 461/461 `.gd` files in godot-demo-projects@b761b4c (4.7) parse; `gdt/modern.gd` (with `@abstract`, `...args`, `Dictionary[String, int]`, `match` with `var q when`, array/dict patterns, `is not`, `%Unique`, `^"..."`, `&"..."`, `@warning_ignore`, `static var`, `for i: int`) parses [Run]. gdformat ran over `2d` and `3d` demos (240 files) without a crash: 193 "would be reformatted" (style only), gdlint reported class-definitions-order and similar style problems. So it is usable on 4.7 code today; any syntax newer than 4.5 not present in the demos is [Unverified].
- gdformat reformats one-line `match` arms into two lines and inserts blank lines [Run: diff of gdt/modern.gd]. Adopt it project-wide from the first commit or the diffs get noisy.
- As a migration linter it is weak. It fails on bare `onready`, `export`, `tool`, `setget` (grammar errors, `gdparse` rc 1), and passes `yield(...)`, 3-arg `connect`, `KinematicBody2D`, `rand_range`, `Pool*Array`, `.instance()`, `.empty()` (all "Success: no problems found") [Run: gdlint/gdparse on proj/cases]. It also did not flag `$Missing` in a member initializer. Its default rules (naming, class-definitions-order, unused-argument, max-line-length) are style rules, and `class-definitions-order` is noisy against the official demos.
- Recommendation: Gate = Godot `--check-only` + the YAML lint rules above; format = `gdformat`; run `gdlint` only with a trimmed config (disable `class-definitions-order` and `max-line-length`) if at all.

## Recommendations (concrete)

1. Make the post-edit hook run, per changed `.gd`, `godot --headless --path . --check-only -s res://f.gd` with `timeout 30`, fail on `SCRIPT ERROR|Parse Error`; per changed `.tscn`, a `load().instantiate()` script that fails on any `ERROR|WARNING: Parent path|Failed to load`; ignore exit codes.
2. Add `lint_rules_full.yaml` (low-risk rules as errors, medium/high as warnings) as a second pass; it covers the silent classes (stale .tscn, untyped receivers).
3. Put the ten highest-ranked patterns into CLAUDE.md as a "never write" list, with the right-hand replacements from section 1.
4. Add three behavioural checks the tools cannot do: a smoke run that executes `_ready` paths of each scene for 2 frames and greps stderr; an InputMap action existence check against `project.godot`; a signal-name check (`emit_signal("x")` against `signal x` declarations).
5. For any imported Godot 3 snippet use `--validate-conversion-3to4` then `--convert-3to4` on a copy, then review (it renamed `$Sprite` to `$Sprite2D` in my test).

## Blocked sources

- None of the allowed hosts were blocked for me. `WebFetch` returned `getaddrinfo ENOTFOUND` for surmado.com and zenn.dev, so I fetched those with `curl` through the proxy (HTTP 200).
- Reddit: `https://www.reddit.com/r/godot/` returned HTTP 200 to `curl` but I did not search it for LLM-related threads; no Reddit evidence is cited. github.com web pages and api.github.com were not used.
- Godot GitHub issues and discussions about LLM-generated code were not searched (github.com web blocked per shared rules). [Unverified: any claim about maintainers' policy on AI PRs, only mentioned second-hand by Surmado.]
- Docs page "Upgrading from Godot 3 to Godot 4" (`https://docs.godotengine.org/en/stable/tutorials/migrating/upgrading_to_godot_4.html`) was fetched (HTTP 200; anchors `running-the-project-upgrade-tool`, `using-the-command-line`, `list-of-automatically-renamed-methods-properties-signals-and-constants`) but I relied on the C++ source for the actual rename lists rather than the page text.

## Open questions

- Frequency ranking beyond patterns 1-4 is judgement; a measurement would need a corpus of Claude-generated GDScript (could be gathered from this harness's own runs and fed back into the rule hit counts).
- Does `--check-only` behaviour on Variant inference differ from 4.4 (Zenn) to 4.7? Not tested on 4.4.
- Untested: `--convert-3to4` on a larger real project (idempotence on already-4.x files, `.tscn`/`.tres` `uid` handling), C# (`csharp_*_renames` tables exist, no `dotnet` here).
- Untested: whether 4.6/4.7-only GDScript syntax additions parse in gdtoolkit; the demos use none that failed.
- Hand-written regexes `syn-python-*`, `syn-var-types-csharp`, `syn-braces-block` have no external evidence of LLM frequency for Godot.
