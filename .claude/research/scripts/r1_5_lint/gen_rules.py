import json,re,sys
d=json.load(open('renames.json'))
def un(s): return s.strip().strip('"')
rules=[]
def add(**k): rules.append(k)
# hand-written syntax rules (derived from converter regexes + observed Godot 4.7 errors)
H=[
("syn-yield",r'(?<![\w.])yield\s*\(',".gd","yield() removed","await signal_or_coroutine  e.g. await get_tree().create_timer(1.0).timeout","low"),
("syn-onready",r'^\s*onready\s+var\b',".gd","bare 'onready' keyword removed","@onready var ...","low"),
("syn-export",r'^\s*export\s*(\(|var\b)',".gd","bare 'export' keyword removed","@export var x: T  / @export_range(...) etc.","low"),
("syn-tool",r'^tool\s*$',".gd","bare 'tool' removed","@tool (first line)","low"),
("syn-setget",r'\bsetget\b',".gd","setget removed","var x: T:\n\tset(v): ...\n\tget: ...","low"),
("syn-remote-keywords",r'^\s*(remote|remotesync|sync|slave|puppet|puppetsync|master|mastersync)\s+func\b',".gd","Godot 3 rpc keywords removed","@rpc(\"any_peer\"|\"authority\", \"call_local\"|\"call_remote\", \"reliable\"|\"unreliable\") func","low"),
("syn-connect-3arg",r'\bconnect\s*\(\s*"[^"]*"\s*,\s*[^,()]+,\s*"',".gd","string-based 3-arg connect()","sig.connect(callable)  e.g. button.pressed.connect(_on_pressed)","low"),
("syn-disconnect-3arg",r'\bdisconnect\s*\(\s*"[^"]*"\s*,\s*[^,()]+,\s*"',".gd","string-based 3-arg disconnect()","sig.disconnect(callable)","low"),
("syn-is-connected-3arg",r'\bis_connected\s*\(\s*"[^"]*"\s*,\s*[^,()]+,\s*"',".gd","string-based 3-arg is_connected()","sig.is_connected(callable)","low"),
("syn-dot-super",r'^\s*\.[a-zA-Z_]\w*\s*\(' if False else r'^\s*\.[a-zA-Z_]\w*\s*\(',".gd","Godot 3 '.method()' super call","super.method()  or  super()","low"),
("syn-instance",r'\.instance\s*\(',".gd","PackedScene.instance() renamed","PackedScene.instantiate()","low"),
("syn-empty-call",r'\.empty\s*\(\s*\)',".gd","Array/String/Dictionary.empty() renamed","is_empty()","low"),
("syn-find-node",r'(?<!func )\bfind_node\s*\(',".gd","Node.find_node() renamed","find_child(pattern, recursive, owned)","low"),
("syn-get-node-at",r'get_node\s*\(\s*@',".gd","Godot 4.0-alpha NodePath @ syntax","get_node(\"...\")","low"),
("syn-engine-editor-hint",r'\bEngine\.editor_hint\b',".gd","Engine.editor_hint removed","Engine.is_editor_hint()","low"),
("syn-tween-new",r'\bTween\.new\s*\(',".gd","Tween.new() is an engine error in 4.x; Godot 3 Tween node API removed","var t := create_tween(); t.tween_property(obj, \"prop\", val, dur)","low"),
("syn-tween-interpolate",r'\.(interpolate_property|interpolate_method|interpolate_callback)\s*\(',".gd","Godot 3 Tween API","create_tween().tween_property()/tween_method()/tween_callback()","low"),
("syn-os-ticks",r'\bOS\.(get_ticks_msec|get_ticks_usec|get_unix_time|get_datetime|get_system_time_msecs|get_system_time_secs)\b',".gd","OS time API moved to Time singleton","Time.get_ticks_msec() / get_unix_time_from_system() / get_datetime_dict_from_system()","low"),
("syn-os-window",r'\bOS\.(window_fullscreen|window_size|window_position|window_maximized|window_minimized|window_borderless|vsync_enabled|set_window_title|get_screen_size|current_screen|set_window_fullscreen|is_window_fullscreen|set_use_vsync)\b',".gd","OS window API moved to DisplayServer / Window","DisplayServer.window_set_mode()/window_set_size()/screen_get_size(); get_window().title","low"),
("syn-file-dir-class",r'(?<![\w.])(File|Directory)\.new\s*\(',".gd","File/Directory classes removed","FileAccess.open(path, FileAccess.READ) / DirAccess.open(path)","low"),
("syn-json-parse",r'\b(parse_json|to_json|validate_json)\s*\(|\bJSON\.print\s*\(|\bJSON\.parse\s*\([^)]*\)\s*\.(result|error)\b',".gd","Godot 3 JSON API","JSON.stringify(v) / var j := JSON.new(); j.parse(s); j.data","low"),
("syn-str2var-deep",r'\bis_valid_integer\s*\(\)|\bis_valid_float\s*\(\)',".gd","kept in 4.x (not an error) - NOT a rule","","skip"),
("syn-rand-seed",r'(?<![\w.])(rand_range|rand_seed|stepify|deg2rad|rad2deg|range_lerp|ease_in_out|is_nan_inf)\s*\(',".gd","renamed global functions","randf_range / randi_range, snapped, deg_to_rad, rad_to_deg, remap","low"),
("syn-move-and-slide-args",r'\bmove_and_slide(_with_snap)?\s*\(\s*[^)\s]',".gd","move_and_slide() takes no args in 4.x; uses CharacterBody velocity property","set velocity then call move_and_slide()","low"),
("syn-change-scene",r'(?<!func )\bchange_scene\s*\(',".gd","SceneTree.change_scene() split","change_scene_to_file(path) / change_scene_to_packed(scene)","low"),
("syn-get-tree-set-pause",r'\bget_tree\(\)\.(set_network_peer|network_peer)\b',".gd","SceneTree network_peer removed","multiplayer.multiplayer_peer","low"),
("syn-poolarray",r'\bPool(Byte|Color|Int|Real|String|Vector2|Vector3)Array\b',".gd,.tscn,.tres","Pool*Array types removed","Packed*Array (PoolIntArray->PackedInt32Array, PoolRealArray->PackedFloat32Array)","low"),
("syn-uppercase-bool-null",r'\b(True|False|None)\b',".gd","Python-isms","true / false / null","medium"),
("syn-python-self-print",r'^\s*print\s*\(.*\bf"',".gd","Python f-string","\"%s\" % x  or  \"{x}\".format({...})","medium"),
("syn-python-elif-colon-missing",r'^\s*(if|elif|while|for|else)\b[^#:\n]*[^:\s#,(\[{]\s*$',".gd","statement without trailing colon (multi-line expressions can false-positive)","add ':'","high"),
("syn-semicolon-end",r';\s*$',".gd","C-style semicolon (legal but non-idiomatic; usually LLM C#/JS leakage)","remove ';'","medium"),
("syn-braces-block",r'^\s*(if|for|while|func)\b.*\{\s*$',".gd","C-style brace blocks","indent-based block with ':'","medium"),
("syn-var-types-csharp",r'^\s*(int|float|string|bool|Vector2|Vector3)\s+[a-z_]\w*\s*(=|;)',".gd","C#-style typed declaration","var x: int = 0","low"),
("syn-void-return-type",r'\)\s*->\s*(Void|None)\b',".gd","wrong void spelling","-> void","low"),
("syn-func-public",r'^\s*(public|private|protected|static void|void)\s+\w+\s*\(',".gd","C#/Java method declaration","func name() -> void:","low"),
("syn-lambda-capture-reassign",r'func\s*\([^)]*\)\s*(->\s*\w+\s*)?:\s*\w+\s*(\+|-|\*|/)?=',".gd","single-line lambda reassigning an outer local (captures by value for primitives; outer variable NOT updated; engine warning CONFUSABLE_CAPTURE_REASSIGNMENT only in some cases)","use an Array/Dictionary/RefCounted holder, a member variable, or a Callable bound to a method","high"),
("syn-yield-signal-string-emit",r'\bemit_signal\s*\(\s*"',".gd","legal in 4.x but string-typed; typos are RUNTIME errors only","sig_name.emit(args)","medium"),
("syn-get-node-ready-var",r'^(var|const)\s+\w+(\s*:\s*\w+)?\s*(:?=)\s*(\$|get_node\()',".gd","$ / get_node() in a member initializer runs before the node is in the tree","@onready var x := $Path  (or @onready var x: T = $Path)","low"),
("syn-variant-infer-clamp",r':=\s*(clamp|min|max|abs|sign|lerp|round|floor|ceil|snapped)\s*\(',".gd","global math funcs return Variant -> ':=' fails with INFERENCE_ON_VARIANT (error by default in 4.7 [Run])","typed variants: clampf/clampi, minf/mini, maxf/maxi, absf/absi, signf, lerpf, roundf, floorf, ceilf, snappedf; or 'var x: float = ...'","medium"),
("syn-dict-get-infer",r':=\s*\w[\w.]*\.get\s*\(',".gd","Dictionary.get()/Object.get() return Variant -> ':=' fails","var x: T = d.get(k, default)","medium"),
("syn-int-div",r'\bint\s*\(\s*\w+\s*/\s*\w+\s*\)|(?<![\w.])randi\s*\(\s*\)\s*%\s*\w+',".gd","integer division / randi()%n idioms - legal; flagged by engine as INTEGER_DIVISION warning, not error","use floori(a / b) or randi_range(0, n-1)","high"),
("syn-rect-props-gd",r'(?<![\w])(rect_(position|size|min_size|scale|rotation|pivot_offset|clip_content|global_position)|margin_(left|right|top|bottom))\b(?!\s*:)',".gd","Godot 3 Control properties","position/size/custom_minimum_size/scale/rotation/pivot_offset/clip_contents/global_position; offset_left/right/top/bottom","medium"),
("tscn-g3-header",r'^\[gd_(scene|resource)\b[^\]]*\bformat=[12]\b',".tscn,.tres","Godot 3 scene/resource format header (loads via compat, but is stale)","format=3 (written by the 4.x editor/ResourceSaver)","low"),
("tscn-extresource-spaces",r'(Ext|Sub)Resource\(\s+\d',".tscn,.tres","Godot 3 numeric id with spaces: ExtResource( 1 ). Loads in 4.7 [Run] but 4.x writes ExtResource(\"1_ab12c\")","ExtResource(\"id\")","low"),
("tscn-ext-path-first",r'^\[ext_resource\s+path=',".tscn,.tres","Godot 3 attribute order/ numeric id","[ext_resource type=\"T\" uid=\"uid://...\" path=\"res://...\" id=\"1_xxxxx\"]","low"),
("tscn-g3-numeric-id",r'\bid=\d+\]',".tscn,.tres","numeric ext/sub resource id (Godot 3 style)","string ids","low"),
("tscn-rect-props",r'^(rect_(position|size|min_size|scale|rotation|pivot_offset|clip_content)|margin_(left|right|top|bottom))\s*=',".tscn","Godot 3 Control properties silently dropped on load [Run]","position/size/custom_minimum_size/scale/rotation/pivot_offset/clip_contents; offset_*","low"),
("tscn-onready-in-scene",r'^\s*script\s*=\s*"res://',".tscn","script assigned as string path instead of ExtResource","script = ExtResource(\"id\")","medium"),
("tscn-g3-types",r'^\[node\s+name="[^"]*"\s+type="(Spatial|KinematicBody2?D?|RigidBody|StaticBody|Area|Camera|MeshInstance|CollisionShape|Sprite|AnimatedSprite|Position2D|Position3D|Particles2D|Particles|ViewportContainer|Viewport|YSort|ToolButton)"',".tscn","Godot 3 node class names (4.7 loads many via compat remap, silently) [Run]","Node3D, CharacterBody3D, RigidBody3D, StaticBody3D, Area3D, Camera3D, MeshInstance3D, CollisionShape3D, Sprite2D, AnimatedSprite2D, Marker2D, Marker3D, GPUParticles2D/3D, SubViewportContainer, SubViewport, (YSort->Node2D y_sort_enabled), Button","low"),
]
for h in H:
    if h[5]=="skip": continue
    add(id=h[0],regex=h[1],applies_to=h[2],message=h[3],godot4_replacement=h[4],false_positive_risk=h[5],source="hand+converter/observed")
# generated from renames
def ident_ok(s): return re.fullmatch(r'[A-Za-z_]\w*',s) is not None
seen=set()
for a,b,c in d['gdscript_function_renames']:
    if not ident_ok(a) or a in seen: continue
    seen.add(a)
    add(id='fn-'+a,regex=r'(?<![\w])(?<!func )%s\s*\('%a,applies_to='.gd',message=f'method {a}() renamed in Godot 4 (class: {c or "n/a"})',godot4_replacement=un(b),false_positive_risk='AUTO',source='renames_map_3_to_4.cpp:gdscript_function_renames',klass=c)
for a,b,c in d['gdscript_properties_renames']:
    if not ident_ok(a) or a in seen: continue
    seen.add('p'+a)
    add(id='prop-'+a,regex=r'\.%s\b(?!\s*\()'%a,applies_to='.gd,.tscn',message=f'property {a} renamed (class: {c or "n/a"})',godot4_replacement=un(b),false_positive_risk='AUTO',source='renames_map_3_to_4.cpp:gdscript_properties_renames',klass=c)
for a,b,c in d['gdscript_signals_renames']:
    if not ident_ok(a): continue
    add(id='sig-'+a,regex=r'\.%s\.(connect|emit)\b|\bconnect\s*\(\s*"%s"'%(a,a),applies_to='.gd',message=f'signal {a} renamed (class: {c or "n/a"})',godot4_replacement=un(b),false_positive_risk='AUTO',source='renames_map_3_to_4.cpp:gdscript_signals_renames',klass=c)
for a,b,c in d['enum_renames']:
    if not ident_ok(a): continue
    add(id='enum-'+a,regex=r'(?<![\w.])%s\b'%a,applies_to='.gd',message=f'constant {a} renamed',godot4_replacement=un(b),false_positive_risk='AUTO',source='renames_map_3_to_4.cpp:enum_renames',klass=c)
for a,b,c in d['class_renames']:
    if not ident_ok(a): continue
    add(id='class-'+a,regex=r'(?:\bextends\s+|:\s*|\bas\s+|\bis\s+|->\s*|\[\s*)%s\b(?![\w"\'/])|(?<![\w"\'/.$])%s\.new\s*\('%(a,a),applies_to='.gd',message=f'class {a} renamed/removed',godot4_replacement=un(b),false_positive_risk='AUTO',source='renames_map_3_to_4.cpp:class_renames')
    add(id='tscnclass-'+a,regex=r'\btype="%s"'%a,applies_to='.tscn,.tres',message=f'class {a} renamed/removed (4.7 may remap on load)',godot4_replacement=un(b),false_positive_risk='AUTO',source='renames_map_3_to_4.cpp:class_renames')
for a,b,c in d['color_renames']:
    if not ident_ok(a): continue
    add(id='color-'+a,regex=r'\bColor\.%s\b'%a,applies_to='.gd',message=f'Color.{a} renamed',godot4_replacement='Color.'+un(b),false_positive_risk='AUTO',source='renames_map_3_to_4.cpp:color_renames')
for a,b,c in d['theme_override_renames']:
    if not ident_ok(a): continue
    add(id='theme-'+a,regex=r'"%s"'%a,applies_to='.gd',message=f'theme override name {a} renamed',godot4_replacement=un(b),false_positive_risk='AUTO',source='renames_map_3_to_4.cpp:theme_override_renames')
json.dump(rules,open('rules.json','w'),indent=1)
print(len(rules))

# ---- post-process with ClassDB(4.7) existence check
db=json.load(open('classdb.json'))
cls=set(db['classes'])
out=[]
for r in rules:
    i=r['id']; src=r.get('source','')
    name=None
    if i.startswith('class-') or i.startswith('tscnclass-'):
        name=i.split('-',1)[1]
        if name in cls: continue   # still a valid 4.7 class -> not a rule
    elif i.startswith('fn-'):
        n=i[3:]
        if n in db['methods']: r['still_exists_in_4_7']=db['methods'][n]
    elif i.startswith('prop-'):
        n=i[5:]
        if n in db['props']: r['still_exists_in_4_7']=db['props'][n]
    elif i.startswith('sig-'):
        n=i[4:]
        if n in db['signals']: r['still_exists_in_4_7']=db['signals'][n]
    elif i.startswith('enum-'):
        n=i[5:]
        if n in db['consts']: r['still_exists_in_4_7']=db['consts'][n]
    out.append(r)
rules=out
json.dump(rules,open('rules.json','w'),indent=1)
print('after classdb filter',len(rules), 'still-exists', sum('still_exists_in_4_7' in r for r in rules))
