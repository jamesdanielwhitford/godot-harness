extends SceneTree
## h scene-edit runner (A2 3.3): applies an ops list to a MAIN (or MAIN_INHERITED) instance of a scene and saves once.
##   -s <this> -- --lib <_scene_lib.gd> --scene <res://x.tscn> --ops <abs json> --loc <ops path> [--uid <uid>] [--ext-uids <abs json>]
## Emits findings and {"kind":"op","i":k,"op":name,"effects":[...]} per op (effect schema: scenes/model.py), then
## {"kind":"edit","live_nodes","live_conns"}. Any error: nothing is saved (exit 1).

var lib: RefCounted
var root_node: Node = null
var inherited: Dictionary = {}        # paths present in the base scene chain
var defaults: Array = []              # [{fx, node, prop}] resolved to is_default after pack()
var addprops: Array = []              # [{fx, node, prop}] props of added nodes, filled after pack()


func _init() -> void:
	var a := {}
	var args := OS.get_cmdline_user_args()
	var i := 0
	while i + 1 < args.size():
		a[args[i]] = args[i + 1]
		i += 2
	for k in ["--lib", "--scene", "--ops", "--loc"]:
		if not a.has(k):
			_done(2, "missing " + k)
			return
	var ls = load(a["--lib"])
	if ls == null or not ls.can_instantiate():
		_done(2, "cannot load --lib")
		return
	lib = ls.new()
	lib.loc = a["--loc"]
	var doc = JSON.parse_string(FileAccess.get_file_as_string(a["--ops"]))
	if typeof(doc) != TYPE_DICTIONARY:
		_done(2, "bad ops json")
		return
	_run(doc, a)


func _done(rc: int, msg: String = "") -> void:
	if msg != "":
		printerr("scene_edit: " + msg)
	if root_node != null and is_instance_valid(root_node):
		root_node.free()
		root_node = null
	lib = null
	print("@@H " + JSON.stringify({"t": "done", "rc": rc}))
	quit(rc)


func _run(doc: Dictionary, a: Dictionary) -> void:
	var scene_path: String = a["--scene"]
	var ps = ResourceLoader.load(scene_path, "", ResourceLoader.CACHE_MODE_IGNORE)
	if ps == null or not (ps is PackedScene):
		lib.finding("scene.broken-input", "error", "", "cannot load " + scene_path, "", scene_path)
		_done(1)
		return
	var st: SceneState = ps.get_state()
	var base: SceneState = st.get_base_scene_state()
	if base != null:
		for p in lib.state_paths(base):
			inherited[p] = true
	root_node = ps.instantiate(PackedScene.GEN_EDIT_STATE_MAIN_INHERITED if base != null else PackedScene.GEN_EDIT_STATE_MAIN)
	if root_node == null:
		lib.finding("scene.broken-input", "error", "", "cannot instantiate " + scene_path, "", scene_path)
		_done(1)
		return
	lib.root = root_node
	var ops: Array = doc.get("ops", [])
	var records: Array = []
	for i in ops.size():
		var op: Dictionary = ops[i]
		var errs0: int = lib.errors
		var fx = _op(i, op)
		if fx == null or lib.errors > errs0:
			_done(1)
			return
		records.append({"t": "data", "kind": "op", "i": i, "op": op["op"], "effects": fx})
	var ps2 := PackedScene.new()
	var err := ps2.pack(root_node)
	if err != OK:
		lib.finding("scene.lossy-save", "error", "", "PackedScene.pack() failed: " + error_string(err))
		_done(1)
		return
	err = ResourceSaver.save(ps2, scene_path)
	if err != OK:
		lib.finding("scene.lossy-save", "error", "", "ResourceSaver.save() failed: " + error_string(err))
		_done(1)
		return
	if a.has("--uid"):
		var id := ResourceUID.text_to_id(a["--uid"])
		if id != ResourceUID.INVALID_ID:
			ResourceSaver.set_uid(scene_path, id)
	if a.has("--ext-uids"):
		_reattach_ext_uids(scene_path, a["--ext-uids"])
	var st2: SceneState = ps2.get_state()
	for d in defaults:
		d["fx"]["is_default"] = not (is_instance_valid(d["node"]) and lib.state_has_prop(st2, lib.path_of(d["node"]), d["prop"]))
	for d in addprops:
		if is_instance_valid(d["node"]):
			var p: String = lib.path_of(d["node"])
			if lib.state_has_prop(st2, p, d["prop"]):
				d["fx"]["props"][d["prop"]] = lib.render_prop(d["prop"], d["node"].get(d["prop"]), p, d["node"].get_class())
	for r in records:
		lib.emit(r)
	lib.emit({"t": "data", "kind": "edit", "live_nodes": lib.count_nodes(root_node), "live_conns": lib.list_conns().size()})
	_done(0)


func _reattach_ext_uids(path: String, map_path: String) -> void:
	var map = JSON.parse_string(FileAccess.get_file_as_string(map_path))
	if typeof(map) != TYPE_DICTIONARY or map.is_empty():
		return
	var text: String = FileAccess.get_file_as_string(path)
	var lines: PackedStringArray = text.split("\n")
	var changed := false
	for i in lines.size():
		var ln: String = lines[i]
		if not ln.begins_with("[ext_resource") or ln.contains(" uid=\""):
			continue
		var m := ln.find(" path=\"")
		if m < 0:
			continue
		var e := ln.find("\"", m + 7)
		var rp: String = ln.substr(m + 7, e - m - 7)
		if not map.has(rp):
			continue
		var want: String = map[rp]
		var id := ResourceLoader.get_resource_uid(rp)
		if id != ResourceUID.INVALID_ID and ResourceUID.id_to_text(id) == want:
			lines[i] = ln.substr(0, m) + " uid=\"" + want + "\"" + ln.substr(m)
			changed = true
	if changed:
		var f := FileAccess.open(path, FileAccess.WRITE)
		if f != null:
			f.store_string("\n".join(lines))
			f.close()


# ---- helpers ------------------------------------------------------------------------------------------------------
func _find(path: String, ptr: String) -> Node:
	var n: Node = lib.find_node(path)
	if n == null:
		lib.finding("scene.node-not-found", "error", ptr, "node '%s' not found" % path)
	return n


func _owned(n: Node) -> bool:
	if n == root_node:
		return true
	if n.owner != root_node:
		return false
	return not inherited.has(lib.path_of(n))


func _internal(n: Node, ptr: String, what: String) -> bool:
	## true (after a finding) when n is not owned by this scene
	if _owned(n):
		return false
	var src := ""
	var anc: Node = n.get_parent()
	while anc != null and anc != root_node:
		if anc.scene_file_path != "":
			src = anc.scene_file_path
			break
		anc = anc.get_parent()
	if src == "":
		src = "the base scene"
	lib.finding("scene.instance-internal", "error", ptr, "%s: '%s' belongs to %s, not to this scene" % [what, lib.path_of(n), src],
		"edit that scene instead, or use set_prop / add_node under it")
	return true


func _prevs(n: Node) -> Array:
	var res: Array = []
	var par: Node = n.get_parent()
	if par == null:
		return res
	var idx := n.get_index()
	for k in range(idx - 1, -1, -1):
		res.append(String(par.get_child(k).name))
	return res


func _np_refs(moved: Node) -> Array:
	## NodePath-typed stored properties of owned nodes that point into `moved`'s subtree
	var res: Array = []
	var stack: Array = [root_node]
	while not stack.is_empty():
		var m: Node = stack.pop_back()
		for ch in m.get_children():
			stack.append(ch)
		if m != root_node and m.owner != root_node:
			continue
		for p in m.get_property_list():
			if int(p["usage"]) & PROPERTY_USAGE_STORAGE and int(p["type"]) == TYPE_NODE_PATH:
				var v: NodePath = m.get(p["name"])
				if not v.is_empty():
					var t: Node = m.get_node_or_null(v)
					if t != null and (t == moved or moved.is_ancestor_of(t)):
						res.append({"m": m, "prop": p["name"], "t": t})
	return res


func _fix_refs(refs: Array) -> void:
	for r in refs:
		if is_instance_valid(r["m"]) and is_instance_valid(r["t"]):
			r["m"].set(r["prop"], r["m"].get_path_to(r["t"]))


func _conn_fx(kind: String, c: Dictionary) -> Dictionary:
	return {"e": kind, "c": c}


func _info(n: Node, with_instance_groups: bool) -> Dictionary:
	var gs: Array = []
	if n.scene_file_path == "":
		for g in n.get_groups():
			if not str(g).begins_with("_"):
				gs.append(String(g))
	var sp: String = lib.script_path(n.get_script()) if n.scene_file_path == "" else ""
	return {"kind": "instance" if n.scene_file_path != "" else "node", "type": null if n.scene_file_path != "" else n.get_class(),
		"instance": n.scene_file_path if n.scene_file_path != "" else null, "script": sp if sp != "" else null, "groups": gs,
		"unique": n.unique_name_in_owner}


# ---- ops --------------------------------------------------------------------------------------------------------
func _op(i: int, op: Dictionary) -> Variant:
	var ptr := "/ops/%d" % i
	match String(op["op"]):
		"set_prop":
			return _set_prop(op, ptr)
		"add_node":
			return _add(op, op["node"], ptr + "/node", ptr)
		"add_instance":
			var nd := {"name": op["name"], "instance": op["scene"]}
			if op.has("props"):
				nd["props"] = op["props"]
			return _add(op, nd, ptr, ptr)
		"remove_node":
			return _remove(op, ptr)
		"reparent":
			return _reparent(op, ptr)
		"rename":
			return _rename(op, ptr)
		"connect":
			return _connect(op, ptr)
		"disconnect":
			return _disconnect(op, ptr)
		"set_script":
			return _set_script(op, ptr)
		"groups":
			return _groups(op, ptr)
	lib.finding("scene.spec-schema", "error", ptr + "/op", "unknown op")
	return null


func _flush_pending(track: Array) -> void:
	lib.resolve_pending()
	for p in lib.pending:
		if p.get("done", false):
			track.append({"node": p["obj"], "prop": p["prop"]})
	lib.pending.clear()


func _set_prop(op: Dictionary, ptr: String) -> Variant:
	var n := _find(op["node"], ptr + "/node")
	if n == null:
		return null
	var fx: Array = []
	var before: Dictionary = lib.snapshot(n)
	var added: Array = lib.ensure_editable(n)
	var track: Array = []
	lib.pending.clear()
	var errs0: int = lib.errors
	lib.apply_props(n, op["props"], ptr + "/props", track)
	_flush_pending(track)
	if lib.errors > errs0:
		return null
	var after: Dictionary = lib.snapshot(n)
	var path: String = lib.path_of(n)
	var seen: Dictionary = {}
	for t in track:
		var prop: String = t["prop"]
		if seen.has(prop):
			continue
		seen[prop] = true
		var nv: Variant = after.get(prop)
		var had: bool = before.has(prop)
		if had and lib.same(before[prop], nv):
			continue
		var d := {"e": "set", "path": path, "prop": prop, "value": lib.render_prop(prop, nv, path, n.get_class()),
			"old": lib.render_prop(prop, before[prop], path, n.get_class()) if had else null, "is_default": false}
		fx.append(d)
		defaults.append({"fx": d, "node": n, "prop": prop})
	for ap in added:
		fx.append({"e": "editable+", "path": ap})
	if fx.is_empty():
		lib.finding("scene.no-effect", "warning", ptr, "set_prop on '%s' changed nothing (values already match)" % path)
	return fx


func _add(op: Dictionary, nd: Dictionary, nptr: String, ptr: String) -> Variant:
	var par := _find(op["parent"], ptr + "/parent")
	if par == null:
		return null
	var added: Array = lib.ensure_editable(par)
	var track: Array = []
	lib.pending.clear()
	var errs0: int = lib.errors
	var n: Node = lib.build_node(nd, par, root_node, nptr, track)
	_flush_pending(track)
	if n == null or lib.errors > errs0:
		return null
	if op.has("index"):
		par.move_child(n, mini(int(op["index"]), par.get_child_count() - 1))
	var fx: Array = []
	var tops: Array = [n]
	var by_node: Dictionary = {}
	var stack: Array = [n]
	while not stack.is_empty():
		var m: Node = stack.pop_front()
		if m != n and m.owner != root_node:
			continue
		var inf := _info(m, false)
		var d := {"e": "add", "path": lib.path_of(m), "kind": inf["kind"], "type": inf["type"], "instance": inf["instance"],
			"script": inf["script"], "groups": inf["groups"], "unique": inf["unique"], "props": {},
			"prevs": _prevs(m) if m == n else null}
		by_node[m.get_instance_id()] = d
		fx.append(d)
		for ch in m.get_children():
			stack.append(ch)
	for t in track:
		if by_node.has(t["node"].get_instance_id()):
			addprops.append({"fx": by_node[t["node"].get_instance_id()], "node": t["node"], "prop": t["prop"]})
	for ap in added:
		fx.append({"e": "editable+", "path": ap})
	return fx


func _remove(op: Dictionary, ptr: String) -> Variant:
	var n := _find(op["node"], ptr + "/node")
	if n == null:
		return null
	if n == root_node:
		lib.finding("scene.bad-value", "error", ptr + "/node", "the scene root cannot be removed")
		return null
	if _internal(n, ptr + "/node", "remove_node"):
		return null
	var path: String = lib.path_of(n)
	var fx: Array = []
	for c in lib.list_conns():
		if c["from"] == path or c["from"].begins_with(path + "/") or c["to"] == path or c["to"].begins_with(path + "/"):
			fx.append(_conn_fx("conn-", c))
	# references to the removed subtree would dangle: clear them
	var stack: Array = [root_node]
	while not stack.is_empty():
		var m: Node = stack.pop_back()
		for ch in m.get_children():
			stack.append(ch)
		if m == n or n.is_ancestor_of(m) or (m != root_node and m.owner != root_node):
			continue
		for p in m.get_property_list():
			if int(p["usage"]) & PROPERTY_USAGE_STORAGE and int(p["type"]) == TYPE_OBJECT:
				var v: Variant = m.get(p["name"])
				if v is Node and (v == n or n.is_ancestor_of(v)):
					m.set(p["name"], null)
					var d := {"e": "set", "path": lib.path_of(m), "prop": p["name"], "value": "null", "is_default": true}
					fx.append(d)
	n.get_parent().remove_child(n)
	n.free()
	fx.append({"e": "remove", "path": path})
	return fx


func _reparent(op: Dictionary, ptr: String) -> Variant:
	var n := _find(op["node"], ptr + "/node")
	var par := _find(op["parent"], ptr + "/parent")
	if n == null or par == null:
		return null
	if n == root_node:
		lib.finding("scene.bad-value", "error", ptr + "/node", "the scene root cannot be reparented")
		return null
	if _internal(n, ptr + "/node", "reparent"):
		return null
	if par != root_node and par.owner != root_node:
		lib.finding("scene.instance-internal", "error", ptr + "/parent", "reparent into '%s': it is inside an instance" % lib.path_of(par),
			"instance the scene under an owned node instead")
		return null
	if par == n or n.is_ancestor_of(par):
		lib.finding("scene.bad-value", "error", ptr + "/parent", "cannot reparent '%s' into its own subtree" % lib.path_of(n))
		return null
	var oldpar: Node = n.get_parent()
	if par != oldpar and par.has_node(NodePath(String(n.name))):
		lib.finding("scene.duplicate-name", "error", ptr + "/parent", "'%s' already exists under '%s'" % [n.name, lib.path_of(par)])
		return null
	var old_path: String = lib.path_of(n)
	var refs := _np_refs(n)
	var owned_desc: Array = []
	var stack: Array = n.get_children()
	while not stack.is_empty():
		var m: Node = stack.pop_back()
		for ch in m.get_children():
			stack.append(ch)
		if m.owner == root_node:
			owned_desc.append(m)
	oldpar.remove_child(n)
	n.owner = null
	for m in owned_desc:
		m.owner = null
	par.add_child(n, true)
	n.owner = root_node
	for m in owned_desc:
		m.owner = root_node
	if op.has("index"):
		par.move_child(n, mini(int(op["index"]), par.get_child_count() - 1))
	_fix_refs(refs)
	var new_path: String = lib.path_of(n)
	return [{"e": "move", "from": old_path, "to": new_path, "prevs": _prevs(n)}]


func _rename(op: Dictionary, ptr: String) -> Variant:
	var n := _find(op["node"], ptr + "/node")
	if n == null:
		return null
	if n == root_node:
		lib.finding("scene.bad-value", "error", ptr + "/node", "the scene root cannot be renamed")
		return null
	if _internal(n, ptr + "/node", "rename"):
		return null
	var nm: String = op["name"]
	if String(n.name) == nm:
		lib.finding("scene.no-effect", "warning", ptr, "'%s' already has that name" % lib.path_of(n))
		return []
	var par: Node = n.get_parent()
	if par.has_node(NodePath(nm)):
		lib.finding("scene.duplicate-name", "error", ptr + "/name", "'%s' already exists under '%s'" % [nm, lib.path_of(par)])
		return null
	var old_path: String = lib.path_of(n)
	var refs := _np_refs(n)
	n.name = nm
	if String(n.name) != nm:
		lib.finding("scene.duplicate-name", "error", ptr + "/name", "the engine renamed '%s' to '%s'" % [nm, n.name])
		return null
	_fix_refs(refs)
	return [{"e": "move", "from": old_path, "to": lib.path_of(n), "prevs": null}]


func _conn_dict(f: Node, sg: String, t: Node, mn: String, flags: int, binds: Array) -> Dictionary:
	var d := {"from": lib.path_of(f), "signal": sg, "to": lib.path_of(t), "method": mn, "flags": flags}
	if not binds.is_empty():
		d["binds"] = lib.one_line(var_to_str(binds))
	return d


func _connect(op: Dictionary, ptr: String) -> Variant:
	var ck = lib.check_conn(op, ptr)
	if ck == null:
		return null
	var flags: int = int(op.get("flags", 0)) | CONNECT_PERSIST
	if ck["f"].is_connected(ck["signal"], ck["cb"]):
		lib.finding("scene.no-effect", "warning", ptr, "the connection already exists")
		return []
	ck["f"].connect(ck["signal"], ck["cb"], flags)
	return [_conn_fx("conn+", _conn_dict(ck["f"], ck["signal"], ck["t"], str(op["method"]), flags, op.get("binds", [])))]


func _disconnect(op: Dictionary, ptr: String) -> Variant:
	var f := _find(op["from"], ptr + "/from")
	var t := _find(op["to"], ptr + "/to")
	if f == null or t == null:
		return null
	var sg: String = op["signal"]
	var mn: String = op["method"]
	if f.has_signal(sg):
		for c in f.get_signal_connection_list(sg):
			var cb: Callable = c["callable"]
			if cb.get_object() == t and String(cb.get_method()) == mn:
				var binds: Array = cb.get_bound_arguments()
				var d := _conn_dict(f, sg, t, mn, int(c["flags"]), binds)
				f.disconnect(sg, cb)
				return [_conn_fx("conn-", d)]
	lib.finding("scene.bad-connection", "error", ptr, "%s.%s is not connected to %s.%s" % [op["from"], sg, op["to"], mn])
	return null


func _set_script(op: Dictionary, ptr: String) -> Variant:
	var n := _find(op["node"], ptr + "/node")
	if n == null:
		return null
	if _internal(n, ptr + "/node", "set_script"):
		return null
	var s: Variant = null
	if op["script"] != null:
		s = lib.load_script_for(str(op["script"]), ptr + "/script", n.get_class())
		if s == null:
			return null
	var old: String = lib.script_path(n.get_script())
	var new_path: String = str(op["script"]) if op["script"] != null else ""
	if old == new_path:
		lib.finding("scene.no-effect", "warning", ptr, "'%s' already has that script" % lib.path_of(n))
		return []
	var before: Dictionary = lib.plist_of(n)
	n.set_script(s)
	var after: Dictionary = lib.plist_of(n)
	var dropped: Array = []
	for k in before:
		if int(before[k]["usage"]) & PROPERTY_USAGE_SCRIPT_VARIABLE and not after.has(k):
			dropped.append(k)
	return [{"e": "script", "path": lib.path_of(n), "script": new_path if new_path != "" else null, "old": old if old != "" else null,
		"dropped": dropped}]


func _groups(op: Dictionary, ptr: String) -> Variant:
	var n := _find(op["node"], ptr + "/node")
	if n == null:
		return null
	var path: String = lib.path_of(n)
	var fx: Array = []
	for g in op.get("add", []):
		if not n.is_in_group(g):
			n.add_to_group(g, true)
			fx.append({"e": "group+", "path": path, "group": g})
	for g in op.get("remove", []):
		if n.is_in_group(g):
			n.remove_from_group(g)
			fx.append({"e": "group-", "path": path, "group": g})
	if fx.is_empty():
		lib.finding("scene.no-effect", "warning", ptr, "groups on '%s' already match" % path)
	return fx
