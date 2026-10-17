extends SceneTree
## h scene-gen runner (A2 3.3 step 4): builds a scene from a spec, checks everything, saves only when error free.
##   -s <this> -- --lib <_scene_lib.gd> --spec <abs json> --out <res://x.tscn> --loc <finding path> [--uid <uid>] [--seed <abs tscn>]
## Emits findings, then one data record {"kind":"gen","live_nodes","live_conns","sets":[...]}.

var lib: RefCounted
var root_node: Node = null


func _init() -> void:
	var a := {}
	var args := OS.get_cmdline_user_args()
	var i := 0
	while i + 1 < args.size():
		a[args[i]] = args[i + 1]
		i += 2
	for k in ["--lib", "--spec", "--out", "--loc"]:
		if not a.has(k):
			_done(2, "missing " + k)
			return
	var ls = load(a["--lib"])
	if ls == null or not ls.can_instantiate():
		_done(2, "cannot load --lib")
		return
	lib = ls.new()
	lib.loc = a["--loc"]
	var spec = JSON.parse_string(FileAccess.get_file_as_string(a["--spec"]))
	if typeof(spec) != TYPE_DICTIONARY:
		_done(2, "bad spec json")
		return
	_run(spec, a)


func _done(rc: int, msg: String = "") -> void:
	if msg != "":
		printerr("scene_gen: " + msg)
	if root_node != null and is_instance_valid(root_node):
		root_node.free()
		root_node = null
	lib = null
	print("@@H " + JSON.stringify({"t": "done", "rc": rc}))
	quit(rc)


func _run(spec: Dictionary, a: Dictionary) -> void:
	var track: Array = []
	var rd: Dictionary = spec["root"]
	if rd.has("instance"):
		var seed_path: String = a.get("--seed", "")
		var ps = null
		if seed_path != "" and ResourceLoader.exists(rd["instance"]):
			ps = ResourceLoader.load(seed_path, "", ResourceLoader.CACHE_MODE_IGNORE)
		if ps == null or not (ps is PackedScene):
			lib.finding("scene.missing-resource", "error", "/root/instance", "cannot load scene " + str(rd["instance"]))
			_done(1)
			return
		root_node = ps.instantiate(PackedScene.GEN_EDIT_STATE_MAIN_INHERITED)
		if root_node == null:
			lib.finding("scene.missing-resource", "error", "/root/instance", "cannot instantiate " + str(rd["instance"]))
			_done(1)
			return
		root_node.name = rd["name"]
		lib.root = root_node
		if rd.has("script"):
			var s = lib.load_script_for(rd["script"], "/root/script", root_node.get_class())
			if s != null:
				root_node.set_script(s)
		if rd.has("props"):
			lib.apply_props(root_node, rd["props"], "/root/props", track)
		for g in rd.get("groups", []):
			root_node.add_to_group(str(g), true)
		if rd.get("unique_name", false):
			root_node.unique_name_in_owner = true
		var kids: Array = rd.get("children", [])
		for k in kids.size():
			lib.build_node(kids[k], root_node, root_node, "/root/children/%d" % k, track)
	else:
		root_node = lib.build_node(rd, null, null, "/root", track)
		if root_node == null:
			_done(1)
			return
	_finish(spec, a, track)


func _finish(spec: Dictionary, a: Dictionary, track: Array) -> void:
	var root: Node = root_node
	# overrides: properties of nodes inside instanced / inherited scenes
	var ov: Dictionary = spec.get("overrides", {})
	for path in ov:
		var tgt: Node = lib.find_node(str(path))
		var ptr := "/overrides/" + str(path)
		if tgt == null:
			lib.finding("scene.node-not-found", "error", ptr, "override target '%s' not found" % path)
			continue
		lib.ensure_editable(tgt)
		lib.apply_props(tgt, ov[path], ptr, track)
	var xs: Array = spec.get("extra_nodes", [])
	for i in xs.size():
		var xd: Dictionary = xs[i]
		var par: Node = lib.find_node(str(xd["parent"]))
		if par == null:
			lib.finding("scene.node-not-found", "error", "/extra_nodes/%d/parent" % i, "parent '%s' not found" % xd["parent"])
			continue
		lib.ensure_editable(par)
		lib.build_node(xd, par, root, "/extra_nodes/%d" % i, track)
	lib.resolve_pending()
	for p in lib.pending:
		if p.get("done", false):
			track.append({"node": p["obj"], "prop": p["prop"]})
	var cs: Array = spec.get("connections", [])
	for i in cs.size():
		var c: Dictionary = cs[i]
		var ck = lib.check_conn(c, "/connections/%d" % i)
		if ck == null:
			continue
		if ck["f"].is_connected(ck["signal"], ck["cb"]):
			lib.finding("scene.bad-connection", "error", "/connections/%d" % i, "the connection already exists")
			continue
		ck["f"].connect(ck["signal"], ck["cb"], int(c.get("flags", 0)) | CONNECT_PERSIST)
	if lib.errors > 0:
		_done(1)
		return
	var ps := PackedScene.new()
	var err := ps.pack(root)
	if err != OK:
		lib.finding("scene.lossy-save", "error", "", "PackedScene.pack() failed: " + error_string(err))
		_done(1)
		return
	var out_path: String = a["--out"]
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out_path.get_base_dir()))
	err = ResourceSaver.save(ps, out_path)
	if err != OK:
		lib.finding("scene.lossy-save", "error", "", "ResourceSaver.save() failed: " + error_string(err))
		_done(1)
		return
	if a.has("--uid"):
		var id := ResourceUID.text_to_id(a["--uid"])
		if id != ResourceUID.INVALID_ID:
			ResourceSaver.set_uid(out_path, id)
	lib.emit({"t": "data", "kind": "gen", "live_nodes": lib.count_nodes(root), "live_conns": lib.list_conns().size(),
		"sets": lib.set_records(track, ps.get_state())})
	_done(0)
