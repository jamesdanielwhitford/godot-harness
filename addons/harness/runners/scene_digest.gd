extends SceneTree
## h digest runner (A2 3.3). Run by absolute path:
##   godot --headless --path <proj> -s <this> -- --mode scene|resource|project --lib <_scene_lib.gd> [--path res://x] [--expand] [--list file]
## Prints one `@@H {"t":"data","kind":"digest"|"resource"|"project",...}` record; Python renders it.

var lib: RefCounted


func _init() -> void:
	var mode := ""
	var lib_path := ""
	var target := ""
	var list_path := ""
	var expand := false
	var args := OS.get_cmdline_user_args()
	var i := 0
	while i < args.size():
		var a: String = args[i]
		if a == "--mode" and i + 1 < args.size():
			mode = args[i + 1]
			i += 2
		elif a == "--lib" and i + 1 < args.size():
			lib_path = args[i + 1]
			i += 2
		elif a == "--path" and i + 1 < args.size():
			target = args[i + 1]
			i += 2
		elif a == "--list" and i + 1 < args.size():
			list_path = args[i + 1]
			i += 2
		elif a == "--expand":
			expand = true
			i += 1
		else:
			_done(2, "unknown argument " + a)
			return
	var lib_script = load(lib_path)
	if lib_script == null or not lib_script.can_instantiate():
		_done(2, "cannot load --lib " + lib_path)
		return
	lib = lib_script.new()
	if mode == "scene":
		_scene(target, expand)
	elif mode == "resource":
		_resource(target)
	elif mode == "project":
		_project(list_path)
	else:
		_done(2, "bad --mode")


func _done(rc: int, msg: String = "") -> void:
	if msg != "":
		printerr("scene_digest: " + msg)
	lib = null
	print("@@H " + JSON.stringify({"t": "done", "rc": rc}))
	quit(rc)


func _emit(d: Dictionary) -> void:
	print("@@H " + JSON.stringify(d))


func _parent_of(p: String) -> String:
	var k := p.rfind("/")
	return "." if k < 0 else p.substr(0, k)


func _below_any(parent: String, entries: Array) -> bool:
	## entries: [{path, kind}] seen earlier. Parent resolves when it is the root, an entry, or inside an instance/override.
	if parent == ".":
		return true
	for e in entries:
		var ep: String = e["path"]
		if parent == ep:
			return true
		if (e["kind"] == "instance" or e["kind"] == "override") and parent.begins_with(ep + "/"):
			return true
	return false


func _collect_state(st: SceneState, is_main: bool, base_entries: Array) -> Array:
	## -> list of entry dicts (without rendering) for the state
	var res: Array = []
	for i in st.get_node_count():
		var p: String = lib.norm_state_path(st.get_node_path(i), i)
		var ntype: String = String(st.get_node_type(i))
		var inst = st.get_node_instance(i)
		var kind := "node"
		if ntype == "":
			kind = "instance" if inst != null else "override"
		res.append({"i": i, "path": p, "kind": kind, "type": ntype, "inst": inst})
	return res


func _scene(path: String, expand: bool) -> void:
	var out := {"t": "data", "kind": "digest", "path": path, "status": "ok", "nodes": [], "connections": [],
		"inherits": null, "instantiated": 0}
	var res = ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_IGNORE)
	if res == null or not (res is PackedScene):
		out["status"] = "load-failed"
		_emit(out)
		_done(1)
		return
	var st: SceneState = res.get_state()
	var base: SceneState = st.get_base_scene_state()
	var ents: Array = _collect_state(st, true, [])
	var base_ents: Array = []
	var b: SceneState = base
	while b != null:
		base_ents += _collect_state(b, false, [])
		b = b.get_base_scene_state()
	for e in ents:
		lib.known[e["path"]] = true
		if e["kind"] == "instance":
			lib.inst_prefixes.append(e["path"])
	for e in base_ents:
		lib.known[e["path"]] = true
		if e["kind"] == "instance":
			lib.inst_prefixes.append(e["path"])
	if base != null and ents.size() > 0 and ents[0]["inst"] != null:
		out["inherits"] = ents[0]["inst"].resource_path
	var nodes: Array = []
	var seen: Array = []
	for e in ents:
		var i: int = e["i"]
		var p: String = e["path"]
		var props: Dictionary = {}
		var script := ""
		var unique := false
		for j in st.get_node_property_count(i):
			var pn: String = String(st.get_node_property_name(i, j))
			var pv: Variant = st.get_node_property_value(i, j)
			if pn == "script":
				script = lib.script_path(pv)
			elif pn == "unique_name_in_owner":
				unique = bool(pv)
			else:
				props[pn] = lib.render_prop(pn, pv, p, e["type"])
		var groups: Array = []
		for g in st.get_node_groups(i):
			groups.append(String(g))
		var vanished := false
		if i > 0:
			var par := _parent_of(p)
			if not _below_any(par, seen) and not (base != null and _below_any(par, base_ents)):
				vanished = true
		seen.append({"path": p, "kind": e["kind"]})
		nodes.append({"path": p, "kind": e["kind"], "type": e["type"] if e["type"] != "" else null,
			"instance": e["inst"].resource_path if e["inst"] != null else null,
			"script": script if script != "" else null, "groups": groups, "unique": unique, "props": props,
			"vanished": vanished, "from": null})
	var conns: Array = []
	for k in st.get_connection_count():
		var cb: Array = st.get_connection_binds(k)
		var c := {"from": lib.norm_state_path(st.get_connection_source(k), 1), "signal": String(st.get_connection_signal(k)),
			"to": lib.norm_state_path(st.get_connection_target(k), 1), "method": String(st.get_connection_method(k)),
			"flags": st.get_connection_flags(k)}
		if not cb.is_empty():
			c["binds"] = lib.one_line(var_to_str(cb))
		conns.append(c)
	out["connections"] = conns
	var inst_root = res.instantiate()
	if inst_root == null:
		out["status"] = "instantiate-failed"
		out["nodes"] = nodes
		_emit(out)
		_done(1)
		return
	out["instantiated"] = _count(inst_root)
	if expand:
		var names: Dictionary = {}
		for n in nodes:
			names[n["path"]] = true
		_expand(inst_root, inst_root, names, nodes, out["inherits"])
	out["nodes"] = nodes
	inst_root.free()
	_emit(out)
	_done(0)


func _count(n: Node) -> int:
	var c := 1
	for ch in n.get_children():
		c += _count(ch)
	return c


func _expand(n: Node, root: Node, names: Dictionary, nodes: Array, inherits) -> void:
	for ch in n.get_children():
		var p: String = str(root.get_path_to(ch))
		if not names.has(p):
			var groups: Array = []
			for g in ch.get_groups():
				if not str(g).begins_with("_"):
					groups.append(String(g))
			var from = null
			if ch.owner != null and ch.owner != root and ch.owner.scene_file_path != "":
				from = ch.owner.scene_file_path
			elif inherits != null:
				from = inherits
			var sp: String = lib.script_path(ch.get_script())
			nodes.append({"path": p, "kind": "node", "type": ch.get_class(), "instance": ch.scene_file_path if ch.scene_file_path != "" else null,
				"script": sp if sp != "" else null, "groups": groups, "unique": ch.unique_name_in_owner, "props": {},
				"vanished": false, "from": from})
		_expand(ch, root, names, nodes, inherits)


func _resource(path: String) -> void:
	var out := {"t": "data", "kind": "resource", "path": path, "status": "ok", "type": null, "script_class": null, "props": {}}
	var res = ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_IGNORE)
	if res == null:
		out["status"] = "load-failed"
		_emit(out)
		_done(1)
		return
	out["type"] = res.get_class()
	var scr = res.get_script()
	if scr is Script:
		var gn: String = scr.get_global_name()
		out["script_class"] = gn if gn != "" else null
	var props: Dictionary = {}
	var order: Array = []
	for p in res.get_property_list():
		var n: String = p["name"]
		if n in lib.SKIP_RES_PROPS or not (int(p["usage"]) & PROPERTY_USAGE_STORAGE):
			continue
		var v: Variant = res.get(n)
		var dv: Variant = null
		var have_def := false
		if scr is Script:
			dv = scr.get_property_default_value(n)
			have_def = dv != null or typeof(v) == TYPE_NIL
		elif ClassDB.can_instantiate(res.get_class()):
			var d: Object = ClassDB.instantiate(res.get_class())
			dv = d.get(n)
			have_def = true
		if have_def and typeof(dv) == typeof(v) and dv == v:
			continue
		props[n] = lib.render(v, ".")
	out["props"] = props
	_emit(out)
	_done(0)


func _project(list_path: String) -> void:
	var out := {"t": "data", "kind": "project", "name": str(ProjectSettings.get_setting("application/config/name", "")),
		"main_scene": str(ProjectSettings.get_setting("application/run/main_scene", "")), "autoload": [], "actions": [],
		"layers": {}, "scenes": []}
	var rc := 0
	for p in ProjectSettings.get_property_list():
		var n: String = p["name"]
		if n.begins_with("autoload/"):
			var v: String = str(ProjectSettings.get_setting(n))
			if v.begins_with("*"):
				v = v.substr(1)
			out["autoload"].append([n.substr(9), v])
		elif n.begins_with("input/"):
			var d = ProjectSettings.get_setting(n)
			var evs: Array = []
			if d is Dictionary:
				for e in d.get("events", []):
					if e is InputEvent:
						evs.append(e.as_text())
			out["actions"].append([n.substr(6), evs])
		elif n.begins_with("layer_names/"):
			var rest := n.substr(12)
			var sl := rest.find("/layer_")
			if sl > 0:
				var kind := rest.substr(0, sl)
				var num := int(rest.substr(sl + 7))
				var nm: String = str(ProjectSettings.get_setting(n))
				if nm != "":
					if not out["layers"].has(kind):
						out["layers"][kind] = []
					out["layers"][kind].append([num, nm])
	out["autoload"].sort_custom(func(a, b): return a[0] < b[0])
	out["actions"].sort_custom(func(a, b): return a[0] < b[0])
	if FileAccess.file_exists(list_path):
		for ln in FileAccess.get_file_as_string(list_path).split("\n"):
			var s := ln.strip_edges()
			if s == "":
				continue
			var res = ResourceLoader.load(s)
			if res == null or not (res is PackedScene):
				out["scenes"].append({"path": s, "root": null, "nodes": 0})
				rc = 1
				continue
			var st: SceneState = res.get_state()
			var rk := ""
			if st.get_node_count() > 0:
				rk = String(st.get_node_type(0))
				if rk == "":
					var inst = st.get_node_instance(0)
					rk = "<" + inst.resource_path + ">" if inst != null else "?"
			out["scenes"].append({"path": s, "root": rk, "nodes": st.get_node_count()})
	_emit(out)
	_done(rc)
