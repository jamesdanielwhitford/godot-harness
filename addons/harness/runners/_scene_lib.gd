extends RefCounted
## Shared library of the A2 runners (scene_digest, scene_gen, scene_edit). Loaded with load() from an absolute path
## given in --lib. No class_name, never prints `done`, never calls quit() (contract 2.8.5).

var loc: String = "-"          # path used for spec/ops findings
var errors: int = 0
var warnings: int = 0
var root: Node = null           # scene root of the live tree (for @path rendering)
var known: Dictionary = {}      # digest mode: entry path -> true
var inst_prefixes: Array = []   # digest mode: instance entry paths

const SKIP_RES_PROPS := ["script", "resource_path", "resource_name", "resource_local_to_scene", "resource_scene_unique_id"]


func emit(d: Dictionary) -> void:
	print("@@H " + JSON.stringify(d))


func finding(rule: String, sev: String, ptr: String, msg: String, hint: String = "", path: String = "", line: int = 0) -> void:
	if sev == "error":
		errors += 1
	elif sev == "warning":
		warnings += 1
	var m: String = (ptr + ": " + msg) if ptr != "" else msg
	var d := {"t": "finding", "path": path if path != "" else loc, "rule": rule, "severity": sev, "message": m}
	if line > 0:
		d["line"] = line
	if hint != "":
		d["hint"] = hint
	emit(d)


func suggest(name: String, candidates: Array) -> String:
	var best := ""
	var score := 0.5
	for c in candidates:
		var s: float = name.similarity(str(c))
		if s >= score:
			score = s
			best = str(c)
	return best


# ---- paths ----------------------------------------------------------------------------------------------------
func norm_state_path(np: NodePath, i: int) -> String:
	if i == 0:
		return "."
	var s := str(np)
	if s.begins_with("./"):
		s = s.substr(2)
	return "." if s == "" else s


func resolve(base: String, rel: String) -> String:
	## base: root-relative path of the owner node ("." for the root). Returns "" when not representable.
	if rel.begins_with("/") or rel.begins_with("%") or rel.contains(":"):
		return ""
	var parts: Array = []
	if base != ".":
		parts = base.split("/")
	for seg in rel.split("/"):
		if seg == "" or seg == ".":
			continue
		if seg == "..":
			if parts.is_empty():
				return ""
			parts.pop_back()
		else:
			parts.append(seg)
	return "." if parts.is_empty() else "/".join(parts)


func path_exists(p: String) -> bool:
	if root != null:
		return p == "." or root.has_node(NodePath(p))
	if p == "." or known.has(p):
		return true
	for pre in inst_prefixes:
		if p.begins_with(str(pre) + "/"):
			return true
	return false


func path_of(n: Node) -> String:
	if root == null or n == root:
		return "."
	if not root.is_ancestor_of(n):
		return "?" + str(n.name)
	return str(root.get_path_to(n))


# ---- rendering (02_scene.md 2.6) ---------------------------------------------------------------------------------
func layer_kind(type_name: String) -> String:
	if type_name != "" and ClassDB.class_exists(type_name) and ClassDB.is_parent_class(type_name, "Node3D"):
		return "3d_physics"
	return "2d_physics"


func layer_text(mask: int, kind: String) -> String:
	var names: Array = []
	for b in range(1, 33):
		if mask & (1 << (b - 1)):
			var nm: String = str(ProjectSettings.get_setting("layer_names/%s/layer_%d" % [kind, b], ""))
			names.append(nm if nm != "" else "#%d" % b)
	return "|".join(names) if not names.is_empty() else "0"


func one_line(s: String) -> String:
	return s.replace("\r", "").replace("\n", " ")


func render(v: Variant, base: String = ".", depth: int = 0) -> String:
	if v == null:
		return "null"
	if v is Node:
		return "@" + path_of(v)
	if v is NodePath:
		var r: String = resolve(base, str(v))
		if r != "" and path_exists(r):
			return "@" + r
		return one_line(var_to_str(v))
	if v is Resource:
		var rp: String = v.resource_path
		if rp != "" and not rp.contains("::"):
			return rp
		return render_sub(v, depth)
	if v is Object:
		return "<" + v.get_class() + ">"
	return one_line(var_to_str(v))


func render_sub(r: Resource, depth: int) -> String:
	var cls: String = r.get_class()
	if depth >= 3:
		return cls + "{...}"
	var def: Object = null
	if ClassDB.can_instantiate(cls):
		def = ClassDB.instantiate(cls)
	var items: Dictionary = {}
	for p in r.get_property_list():
		var n: String = p["name"]
		if n in SKIP_RES_PROPS or not (int(p["usage"]) & PROPERTY_USAGE_STORAGE):
			continue
		var val: Variant = r.get(n)
		if def != null and typeof(def.get(n)) == typeof(val) and def.get(n) == val:
			continue
		items[n] = render(val, ".", depth + 1)
	var keys: Array = items.keys()
	keys.sort()
	var parts: Array = []
	for k in keys:
		parts.append("%s=%s" % [k, items[k]])
	return cls + "{" + ", ".join(parts) + "}"


func render_prop(pname: String, v: Variant, base: String, type_name: String) -> String:
	if (pname == "collision_layer" or pname == "collision_mask") and typeof(v) == TYPE_INT:
		return layer_text(int(v), layer_kind(type_name))
	return render(v, base)


func script_path(v: Variant) -> String:
	if v is Script:
		return v.resource_path
	return ""


# ---- value coercion (02_scene.md 2.6) ------------------------------------------------------------------------------
var pending: Array = []   # deferred {"$node": ...} references: {obj, prop, path, ptr, info}


func ok_(v: Variant) -> Dictionary:
	return {"ok": true, "v": v}


func bad(ptr: String, msg: String, hint: String = "") -> Dictionary:
	finding("scene.bad-value", "error", ptr, msg, hint)
	return {"ok": false}


func plist_of(obj: Object) -> Dictionary:
	var d: Dictionary = {}
	for p in obj.get_property_list():
		d[p["name"]] = p
	return d


func snapshot(obj: Object) -> Dictionary:
	## stored properties (PROPERTY_USAGE_STORAGE) -> current values; script excluded
	var d: Dictionary = {}
	for p in obj.get_property_list():
		if int(p["usage"]) & PROPERTY_USAGE_STORAGE and p["name"] != "script":
			var v: Variant = obj.get(p["name"])
			d[p["name"]] = v.duplicate() if (v is Array or v is Dictionary) else v
	return d


func same(a: Variant, b: Variant) -> bool:
	var ta := typeof(a)
	var tb := typeof(b)
	if ta != tb:
		if (ta == TYPE_INT or ta == TYPE_FLOAT) and (tb == TYPE_INT or tb == TYPE_FLOAT):
			return is_equal_approx(float(a), float(b))
		if (ta == TYPE_STRING or ta == TYPE_STRING_NAME) and (tb == TYPE_STRING or tb == TYPE_STRING_NAME):
			return str(a) == str(b)
		return false
	if ta == TYPE_FLOAT:
		return is_equal_approx(a, b)
	if ta in [TYPE_VECTOR2, TYPE_VECTOR3, TYPE_VECTOR4, TYPE_COLOR, TYPE_QUATERNION, TYPE_BASIS, TYPE_TRANSFORM2D,
			TYPE_TRANSFORM3D, TYPE_RECT2, TYPE_AABB, TYPE_PLANE]:
		return a.is_equal_approx(b)
	return a == b


func enum_lookup(hs: String, s: String) -> Dictionary:
	var nxt := 0
	for part in hs.split(","):
		var nm: String = part
		var val := nxt
		var c := part.rfind(":")
		if c >= 0:
			nm = part.substr(0, c)
			val = int(part.substr(c + 1))
		nxt = val + 1
		if nm.strip_edges().to_lower() == s.to_lower():
			return {"found": true, "v": val}
	return {"found": false}


func find_node(path: String) -> Node:
	if root == null:
		return null
	if path == "." or path == "":
		return root
	return root.get_node_or_null(NodePath(path))


func node_classes() -> Array:
	var res: Array = []
	for c in ClassDB.get_inheriters_from_class("Node"):
		if ClassDB.can_instantiate(c):
			res.append(c)
	return res


func resource_classes() -> Array:
	var res: Array = []
	for c in ClassDB.get_inheriters_from_class("Resource"):
		if ClassDB.can_instantiate(c):
			res.append(c)
	return res


func coerce(obj: Object, pname: String, info: Dictionary, v: Variant, ptr: String) -> Dictionary:
	## -> {"ok": bool, "v": Variant} or {"ok": true, "defer": true, "path": String}
	var t: int = int(info.get("type", TYPE_NIL))
	if typeof(v) == TYPE_DICTIONARY:
		return _form(obj, pname, info, t, v, ptr)
	var hint: int = int(info.get("hint", 0))
	var hs: String = str(info.get("hint_string", ""))
	var tn: String = type_string(t)
	var vt := typeof(v)
	if vt == TYPE_NIL:
		if t == TYPE_OBJECT or t == TYPE_NIL:
			return ok_(null)
		return bad(ptr, "null is not a valid %s" % tn)
	if vt == TYPE_BOOL:
		if t == TYPE_BOOL or t == TYPE_NIL:
			return ok_(v)
		return bad(ptr, "a boolean was given but the property is %s" % tn)
	if vt == TYPE_FLOAT or vt == TYPE_INT:
		var integral: bool = float(v) == floor(float(v)) and absf(float(v)) < 9.0e15
		if t == TYPE_FLOAT:
			return ok_(float(v))
		if t == TYPE_INT:
			if integral:
				return ok_(int(v))
			return bad(ptr, "%s expects an integer, got %s" % [pname, str(v)])
		if t == TYPE_NIL:
			return ok_(int(v) if integral else v)
		return bad(ptr, "a number was given but the property '%s' is %s" % [pname, tn], _var_hint(t))
	if vt == TYPE_STRING:
		if t == TYPE_STRING or t == TYPE_NIL:
			return ok_(v)
		if t == TYPE_STRING_NAME:
			return ok_(StringName(v))
		if t == TYPE_NODE_PATH:
			return ok_(NodePath(v))
		if t == TYPE_INT and hint == PROPERTY_HINT_ENUM:
			var e := enum_lookup(hs, v)
			if e["found"]:
				return ok_(e["v"])
			return bad(ptr, "'%s' is not one of the enum values (%s)" % [v, hs])
		if t == TYPE_OBJECT:
			if hint == PROPERTY_HINT_NODE_TYPE:
				return bad(ptr, "a string cannot be assigned to the node reference '%s'" % pname, "use {\"$node\": \"%s\"}" % v)
			if hint == PROPERTY_HINT_RESOURCE_TYPE:
				return bad(ptr, "a string cannot be assigned to the resource '%s'" % pname, "use {\"$res\": \"res://...\"}")
			return bad(ptr, "a string cannot be assigned to the object '%s'" % pname)
		return bad(ptr, "a string was given but the property '%s' is %s" % [pname, tn], _var_hint(t))
	if vt == TYPE_ARRAY:
		if t == TYPE_NIL:
			return ok_(v)
		if t == TYPE_ARRAY:
			var cur: Variant = obj.get(pname)
			var arr: Array = cur.duplicate() if cur is Array else []
			arr.assign(v)
			return ok_(arr)
		if t >= TYPE_PACKED_BYTE_ARRAY and t <= TYPE_PACKED_VECTOR4_ARRAY and t != TYPE_PACKED_VECTOR2_ARRAY \
				and t != TYPE_PACKED_VECTOR3_ARRAY and t != TYPE_PACKED_COLOR_ARRAY and t != TYPE_PACKED_VECTOR4_ARRAY:
			var conv: Variant = type_convert(v, t)
			if typeof(conv) == t and conv.size() == v.size():
				return ok_(conv)
		return bad(ptr, "an array was given but the property '%s' is %s" % [pname, tn], _var_hint(t))
	return bad(ptr, "unsupported JSON value")


func _var_hint(t: int) -> String:
	return "use {\"$var\": \"%s(...)\"}" % type_string(t) if t != TYPE_NIL else ""


func _form(obj: Object, pname: String, info: Dictionary, t: int, v: Dictionary, ptr: String) -> Dictionary:
	var hint: int = int(info.get("hint", 0))
	var hs: String = str(info.get("hint_string", ""))
	if v.has("$var"):
		var txt: String = str(v["$var"])
		var parsed: Variant = str_to_var(txt)
		if typeof(parsed) == TYPE_NIL and txt.strip_edges() != "null":
			return bad(ptr + "/$var", "cannot parse '%s' with str_to_var" % txt)
		var pt := typeof(parsed)
		if t == TYPE_NIL or pt == t:
			return ok_(parsed)
		if t == TYPE_FLOAT and pt == TYPE_INT:
			return ok_(float(parsed))
		if t == TYPE_OBJECT and pt == TYPE_NIL:
			return ok_(null)
		return bad(ptr + "/$var", "'%s' is a %s but '%s' expects %s" % [txt, type_string(pt), pname, type_string(t)])
	if v.has("$res"):
		var rp: String = str(v["$res"])
		if t != TYPE_OBJECT and t != TYPE_NIL:
			return bad(ptr + "/$res", "'%s' is %s, not a resource" % [pname, type_string(t)])
		var res: Variant = null
		if ResourceLoader.exists(rp):
			res = load(rp)
		if res == null:
			finding("scene.missing-resource", "error", ptr + "/$res", "cannot load " + rp)
			return {"ok": false}
		if hint == PROPERTY_HINT_RESOURCE_TYPE and hs != "":
			var matched := false
			for h in hs.split(","):
				if not ClassDB.class_exists(h) or res.is_class(h):
					matched = true
			if not matched:
				return bad(ptr + "/$res", "%s is a %s but '%s' expects %s" % [rp, res.get_class(), pname, hs])
		return ok_(res)
	if v.has("$node"):
		if t != TYPE_OBJECT or hint == PROPERTY_HINT_RESOURCE_TYPE:
			return bad(ptr + "/$node", "'%s' is not a node reference" % pname)
		return {"ok": true, "defer": true, "path": str(v["$node"])}
	if v.has("$new"):
		if t != TYPE_OBJECT and t != TYPE_NIL:
			return bad(ptr + "/$new", "'%s' is %s, not a resource" % [pname, type_string(t)])
		var cls: String = str(v["$new"])
		if not ClassDB.class_exists(cls) or not ClassDB.can_instantiate(cls) or not ClassDB.is_parent_class(cls, "Resource"):
			finding("scene.unknown-type", "error", ptr + "/$new", "unknown, abstract or non-Resource class '%s'" % cls,
				suggest(cls, resource_classes()))
			return {"ok": false}
		var nr: Resource = ClassDB.instantiate(cls)
		if hint == PROPERTY_HINT_RESOURCE_TYPE and hs != "":
			var matched2 := false
			for h2 in hs.split(","):
				if not ClassDB.class_exists(h2) or nr.is_class(h2):
					matched2 = true
			if not matched2:
				return bad(ptr + "/$new", "%s is not a %s" % [cls, hs])
		var sub: Dictionary = v.get("props", {})
		var okp := true
		if not sub.is_empty():
			okp = apply_props(nr, sub, ptr + "/props", [])
		return ok_(nr) if okp else {"ok": false}
	if v.has("$layers"):
		if t != TYPE_INT:
			return bad(ptr + "/$layers", "'%s' is %s, not an integer bit mask" % [pname, type_string(t)])
		var kind := "2d_physics"
		if obj is Node:
			kind = layer_kind(obj.get_class())
		var mask := 0
		var good := true
		var items: Array = v["$layers"]
		for it in items:
			if typeof(it) == TYPE_STRING:
				var bit := 0
				for b in range(1, 33):
					if str(ProjectSettings.get_setting("layer_names/%s/layer_%d" % [kind, b], "")) == it:
						bit = b
						break
				if bit == 0:
					bad(ptr + "/$layers", "unknown layer name '%s' in layer_names/%s" % [it, kind])
					good = false
				else:
					mask |= 1 << (bit - 1)
			else:
				var n := int(it)
				if n < 1 or n > 32:
					bad(ptr + "/$layers", "layer bit %d is outside 1-32" % n)
					good = false
				else:
					mask |= 1 << (n - 1)
		return ok_(mask) if good else {"ok": false}
	return bad(ptr, "unknown value form")


func apply_props(obj: Object, props: Dictionary, ptr: String, track: Array) -> bool:
	## Validates and assigns props. track receives {node, prop} for every stored property that was set on a Node.
	var pl: Dictionary = plist_of(obj)
	var ok := true
	for k in props:
		var key: String = str(k)
		var kp := ptr + "/" + key
		var info: Dictionary = pl.get(key, {})
		if info.is_empty() and not (key.contains("/") or key.contains(":")):
			finding("scene.unknown-property", "error", kp, "%s has no property '%s'" % [obj.get_class(), key], suggest(key, pl.keys()))
			ok = false
			continue
		var c := coerce(obj, key, info, props[k], kp)
		if not c["ok"]:
			ok = false
			continue
		if c.get("defer", false):
			pending.append({"obj": obj, "prop": key, "path": c["path"], "ptr": kp + "/$node", "info": info})
			continue
		var names: Variant = assign(obj, key, info, c["v"], kp)
		if names == null:
			ok = false
			continue
		if obj is Node:
			for nm in names:
				track.append({"node": obj, "prop": nm})
	return ok


func assign(obj: Object, key: String, info: Dictionary, val: Variant, kp: String) -> Variant:
	## -> Array of stored property names that were set, or null after a finding.
	var stored: bool = info.is_empty() or (int(info.get("usage", 0)) & PROPERTY_USAGE_STORAGE) != 0
	if stored:
		obj.set(key, val)
		var got: Variant = obj.get(key)
		if info.is_empty():
			if typeof(got) == TYPE_NIL and typeof(val) != TYPE_NIL:
				finding("scene.unknown-property", "error", kp, "%s has no property '%s'" % [obj.get_class(), key])
				return null
		elif not same(got, val) and not (typeof(val) == TYPE_OBJECT):
			bad(kp, "the engine did not accept the value (the property reads back as %s)" % one_line(var_to_str(got)))
			return null
		return [key]
	var before := snapshot(obj)
	var cur: Variant = obj.get(key)
	obj.set(key, val)
	var after := snapshot(obj)
	var changed: Array = []
	for n in after:
		if not before.has(n) or not same(before[n], after[n]):
			changed.append(n)
	if changed.is_empty():
		if same(cur, val):
			return []
		finding("scene.not-stored", "error", kp, "property '%s' is not saved in the scene file and changes no saved property" % key)
		return null
	return changed


func resolve_pending() -> void:
	for p in pending:
		var tgt: Node = find_node(p["path"])
		if tgt == null:
			finding("scene.node-not-found", "error", p["ptr"], "node '%s' not found" % p["path"])
			continue
		var hs: String = str(p["info"].get("hint_string", ""))
		if hs != "" and ClassDB.class_exists(hs) and not tgt.is_class(hs):
			bad(p["ptr"], "node '%s' is a %s but '%s' expects %s" % [p["path"], tgt.get_class(), p["prop"], hs])
			continue
		p["obj"].set(p["prop"], tgt)
		p["done"] = true
	# callers read pending entries with "done" for set tracking
	return


# ---- node building ------------------------------------------------------------------------------------------------
func load_script_for(sp: String, ptr: String, node_class: String) -> Variant:
	## -> Script or null (after a finding)
	if not ResourceLoader.exists(sp):
		finding("scene.missing-resource", "error", ptr, "cannot load script " + sp)
		return null
	var s: Variant = load(sp)
	if s == null or not (s is Script):
		finding("scene.missing-resource", "error", ptr, "cannot load script " + sp)
		return null
	if not s.can_instantiate():
		finding("scene.bad-script", "error", ptr, "script %s does not compile (see the parse error)" % sp)
		return null
	var base: String = str(s.get_instance_base_type())
	if node_class != "" and base != "" and ClassDB.class_exists(base) and not ClassDB.is_parent_class(node_class, base):
		finding("scene.bad-script", "error", ptr, "script %s extends %s but the node is a %s" % [sp, base, node_class])
		return null
	return s


func build_node(d: Dictionary, parent: Node, owner_root: Node, ptr: String, track: Array) -> Node:
	var n: Node = null
	if d.has("instance"):
		var ip: String = d["instance"]
		var ps: Variant = null
		if ResourceLoader.exists(ip):
			ps = load(ip)
		if ps == null or not (ps is PackedScene):
			finding("scene.missing-resource", "error", ptr + "/instance", "cannot load scene " + ip)
			return null
		n = ps.instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE)
		if n == null:
			finding("scene.missing-resource", "error", ptr + "/instance", "cannot instantiate " + ip)
			return null
	else:
		var tn: String = d["type"]
		if not ClassDB.class_exists(tn) or not ClassDB.can_instantiate(tn) or not ClassDB.is_parent_class(tn, "Node"):
			finding("scene.unknown-type", "error", ptr + "/type", "unknown, abstract or non-Node class '%s'" % tn, suggest(tn, node_classes()))
			return null
		n = ClassDB.instantiate(tn)
	var nm: String = d["name"]
	var r: Node = owner_root
	if parent == null:
		r = n
		if root == null:
			root = n
	if parent != null:
		if parent.has_node(NodePath(nm)):
			finding("scene.duplicate-name", "error", ptr + "/name", "'%s' already exists under '%s'" % [nm, path_of(parent)])
			n.free()
			return null
		n.name = nm
		parent.add_child(n, true)
		n.owner = owner_root
		if n.name != nm:
			finding("scene.duplicate-name", "error", ptr + "/name", "the engine renamed '%s' to '%s'" % [nm, n.name])
	else:
		n.name = nm
	var script_ok := true
	if d.has("script"):
		var s: Variant = load_script_for(d["script"], ptr + "/script", n.get_class())
		if s == null:
			script_ok = false
		else:
			n.set_script(s)
	if d.has("props") and script_ok:
		apply_props(n, d["props"], ptr + "/props", track)
	for g in d.get("groups", []):
		n.add_to_group(str(g), true)
	if d.get("unique_name", false):
		n.unique_name_in_owner = true
	if d.has("index") and parent != null:
		parent.move_child(n, mini(int(d["index"]), parent.get_child_count() - 1))
	var kids: Array = d.get("children", [])
	for i in kids.size():
		build_node(kids[i], n, r, ptr + "/children/%d" % i, track)
	return n


func ensure_editable(node: Node) -> Array:
	## set_editable_instance on every instance ancestor of `node` below the root (not `node` itself).
	## -> paths newly made editable
	var added: Array = []
	var anc: Node = node.get_parent()
	while anc != null and anc != root:
		if anc.scene_file_path != "" and anc.owner == root:
			if not root.is_editable_instance(anc):
				root.set_editable_instance(anc, true)
				added.append(path_of(anc))
		anc = anc.get_parent()
	return added


# ---- connections ----------------------------------------------------------------------------------------------------
func list_conns(only_owned: bool = true) -> Array:
	var out: Array = []
	if root == null:
		return out
	var stack: Array = [root]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		for ch in n.get_children():
			stack.append(ch)
		if n != root and n.owner != root:
			continue
		for sg in n.get_signal_list():
			for c in n.get_signal_connection_list(sg["name"]):
				if not (int(c["flags"]) & CONNECT_PERSIST):
					continue
				var cb: Callable = c["callable"]
				var tgt: Object = cb.get_object()
				if not (tgt is Node) or (tgt != root and tgt.owner != root):
					continue
				var d := {"from": path_of(n), "signal": String(sg["name"]), "to": path_of(tgt), "method": String(cb.get_method()),
					"flags": int(c["flags"])}
				var bd: Array = cb.get_bound_arguments()
				if not bd.is_empty():
					d["binds"] = one_line(var_to_str(bd))
				out.append(d)
	return out


func suggest_methods(t: Object, name: String) -> String:
	var names: Array = []
	for m in t.get_method_list():
		names.append(str(m["name"]))
	return suggest(name, names)


func check_conn(c: Dictionary, cp: String) -> Variant:
	## validates a connection description -> {"f": Node, "t": Node, "cb": Callable} or null
	var f: Node = find_node(str(c["from"]))
	var t: Node = find_node(str(c["to"]))
	var good := true
	if f == null:
		finding("scene.node-not-found", "error", cp + "/from", "node '%s' not found" % c["from"])
		good = false
	if t == null:
		finding("scene.node-not-found", "error", cp + "/to", "node '%s' not found" % c["to"])
		good = false
	if not good:
		return null
	var sg: String = str(c["signal"])
	if not f.has_signal(sg):
		var names: Array = []
		for s in f.get_signal_list():
			names.append(String(s["name"]))
		finding("scene.bad-connection", "error", cp + "/signal", "%s (%s) has no signal '%s'" % [c["from"], f.get_class(), sg], suggest(sg, names))
		good = false
	var mn: String = str(c["method"])
	if not t.has_method(mn):
		finding("scene.bad-connection", "error", cp + "/method", "%s (%s) has no method '%s'" % [c["to"], t.get_class(), mn], suggest_methods(t, mn))
		good = false
	if not good:
		return null
	var cb := Callable(t, mn)
	var binds: Array = c.get("binds", [])
	if not binds.is_empty():
		cb = cb.bindv(binds)
	return {"f": f, "t": t, "cb": cb, "signal": sg}


# ---- packed state helpers ---------------------------------------------------------------------------------------------
func state_has_prop(st: SceneState, path: String, prop: String) -> bool:
	for i in st.get_node_count():
		if norm_state_path(st.get_node_path(i), i) == path:
			for j in st.get_node_property_count(i):
				if String(st.get_node_property_name(i, j)) == prop:
					return true
	return false


func state_paths(st: SceneState) -> Array:
	var res: Array = []
	var s: SceneState = st
	while s != null:
		for i in s.get_node_count():
			res.append(norm_state_path(s.get_node_path(i), i))
		s = s.get_base_scene_state()
	return res


func count_nodes(n: Node) -> int:
	var c := 1
	for ch in n.get_children():
		c += count_nodes(ch)
	return c


func set_records(track: Array, st: SceneState) -> Array:
	## dedup tracked (node, prop) -> [{path, prop, value, is_default}]
	var seen: Dictionary = {}
	var res: Array = []
	for t in track:
		var n: Node = t["node"]
		var key: String = str(n.get_instance_id()) + "|" + str(t["prop"])
		if seen.has(key):
			continue
		seen[key] = true
		var p: String = path_of(n)
		var v: Variant = n.get(t["prop"])
		res.append({"path": p, "prop": t["prop"], "value": render_prop(t["prop"], v, p, n.get_class()),
			"is_default": not state_has_prop(st, p, t["prop"])})
	return res
