extends SceneTree
## Usage: godot --headless --path <proj> --script scene_gen.gd -- spec.json
## Spec (JSON):
## {"save":"res://scenes/a.tscn",
##  "root":{"name":"Main","type":"Node2D","script":"res://scripts/hero.gd",
##          "props":{"position":{"$var":"Vector2(10,20)"},"texture":{"$res":"res://icon.svg"},"target":{"$node":"Child"}},
##          "groups":["g"],"unique_name":false,
##          "children":[{...same shape..., or "instance":"res://scenes/other.tscn"}]},
##  "connections":[{"from":"Child","signal":"hit","to":".","method":"_on_hit","flags":0}]}
## Exit code: 0 ok, 2 spec/IO error, 3 node creation error, 4 save error.
var errors: PackedStringArray = []
var pending_refs: Array = []   # [node, prop, path] resolved after tree is built

func _init() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() < 1:
		_fail(2, "usage: -- spec.json")
		return
	var txt := FileAccess.get_file_as_string(args[0])
	var spec = JSON.parse_string(txt)
	if typeof(spec) != TYPE_DICTIONARY:
		_fail(2, "bad JSON spec: " + args[0])
		return
	var root := _build(spec["root"], null, null)
	if root == null:
		_fail(3, "build failed:\n" + "\n".join(errors))
		return
	for r in pending_refs:
		var n: Node = root.get_node_or_null(NodePath(r[2]))
		if n == null:
			errors.append("node ref not found: %s (for %s.%s)" % [r[2], r[0].name, r[1]])
		else:
			r[0].set(r[1], n)
	# Overrides of properties on nodes INSIDE instanced scenes (needs set_editable_instance or pack() drops them).
	for path in spec.get("overrides", {}):
		var tgt := root.get_node_or_null(NodePath(path))
		if tgt == null:
			errors.append("override target not found: " + path); continue
		var anc := tgt
		while anc != null and anc != root:
			if anc != tgt and anc.scene_file_path != "": root.set_editable_instance(anc, true)
			anc = anc.get_parent()
		for k in spec["overrides"][path]:
			tgt.set(k, _val(spec["overrides"][path][k], tgt, k))
	# New nodes added UNDER nodes of an instanced scene.
	for ex in spec.get("extra_nodes", []):
		var par := root.get_node_or_null(NodePath(ex["parent"]))
		if par == null: errors.append("extra_nodes parent not found: " + str(ex["parent"])); continue
		var a2 := par
		while a2 != null and a2 != root:
			if a2 != par and a2.scene_file_path != "": root.set_editable_instance(a2, true)
			a2 = a2.get_parent()
		if _build(ex, par, root) == null: break
	for c in spec.get("connections", []):
		var f := root.get_node_or_null(NodePath(c["from"]))
		var t := root.get_node_or_null(NodePath(c["to"]))
		if f == null or t == null or not f.has_signal(c["signal"]) or not t.has_method(c["method"]):
			errors.append("bad connection: %s" % [c])
			continue
		f.connect(c["signal"], Callable(t, c["method"]), int(c.get("flags", CONNECT_PERSIST)) | CONNECT_PERSIST)
	if not errors.is_empty():
		_fail(3, "\n".join(errors))
		return
	var ps := PackedScene.new()
	var err := ps.pack(root)
	if err != OK:
		_fail(4, "pack failed: %s" % error_string(err))
		return
	err = ResourceSaver.save(ps, spec["save"])
	if err != OK:
		_fail(4, "save failed: %s" % error_string(err))
		return
	print("OK saved ", spec["save"], " nodes=", _count(root))
	root.free()
	quit(0)

func _val(v, n: Node, k: String):
	if typeof(v) == TYPE_DICTIONARY:
		if v.has("$var"): v = str_to_var(v["$var"])
		elif v.has("$res"): v = load(v["$res"])
	for p in n.get_property_list():
		if p["name"] == k and typeof(v) != p["type"] and p["type"] != TYPE_NIL and p["type"] != TYPE_OBJECT:
			return type_convert(v, p["type"])
	return v

func _count(n: Node) -> int:
	var c := 1
	for ch in n.get_children(): c += _count(ch)
	return c

func _fail(code: int, msg: String) -> void:
	printerr("scene_gen ERROR: ", msg)
	quit(code)

func _build(d: Dictionary, parent: Node, root: Node) -> Node:
	var n: Node
	if d.has("instance"):
		var ps = load(d["instance"])
		if ps == null or not (ps is PackedScene):
			errors.append("cannot load instance " + str(d["instance"])); return null
		n = ps.instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE)  # keeps it an instance link
	else:
		if not ClassDB.class_exists(d.get("type", "")) or not ClassDB.can_instantiate(d["type"]):
			errors.append("unknown/abstract type " + str(d.get("type"))); return null
		n = ClassDB.instantiate(d["type"])
	n.name = d["name"] if d.has("name") else n.name
	if d.has("script"):
		var s = load(d["script"])
		if s == null: errors.append("cannot load script " + d["script"])
		else: n.set_script(s)
	var r := root if root != null else n
	if parent != null:
		parent.add_child(n, true)
		n.owner = r        # THE OWNER RULE: every node to be saved needs owner = scene root
	# NOTE: children *inside* an instanced scene must not be re-owned (we never recurse into them).
	var plist := {}
	for p in n.get_property_list(): plist[p["name"]] = p
	for k in d.get("props", {}):
		var v = d["props"][k]
		if typeof(v) == TYPE_DICTIONARY and v.has("$node"):
			pending_refs.append([n, k, v["$node"]]); continue
		v = _val(v, n, k)
		if not plist.has(k) and not (k.contains("/") or k.contains(":")):
			errors.append("%s has no property '%s'" % [n.name, k]); continue
		if plist.has(k) and typeof(v) != plist[k]["type"] and plist[k]["type"] != TYPE_NIL and plist[k]["type"] != TYPE_OBJECT:
			v = type_convert(v, plist[k]["type"])
		n.set(k, v)
	for g in d.get("groups", []): n.add_to_group(g, true)
	if d.get("unique_name", false): n.unique_name_in_owner = true
	for ch in d.get("children", []):
		if _build(ch, n, r) == null: return null
	return n
