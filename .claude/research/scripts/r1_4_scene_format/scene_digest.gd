extends SceneTree
## Usage: godot --headless --path <proj> --script scene_digest.gd -- res://scenes/a.tscn [--all-props]
## Prints tree / types / scripts / unique names / groups / connections / ext deps. Exit 0 ok, 1 load failure.
func _init() -> void:
	var args := OS.get_cmdline_user_args()
	if args.is_empty(): printerr("usage: -- res://x.tscn"); quit(2); return
	var path: String = args[0]
	var res = ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_IGNORE)
	if res == null or not (res is PackedScene):
		printerr("DIGEST FAIL: cannot load ", path); quit(1); return
	var st: SceneState = res.get_state()
	print("scene ", path, " uid=", ResourceUID.id_to_text(ResourceLoader.get_resource_uid(path)), " nodes=", st.get_node_count())
	for i in st.get_node_count():
		var np := st.get_node_path(i)
		var ntype := String(st.get_node_type(i))
		var inst := st.get_node_instance(i)
		if ntype == "": ntype = "(instance)" if inst != null else "(override of inherited/instanced node)"
		var line := "  " + ("." if i == 0 else str(np)) + " : " + ntype
		if inst != null: line += "  [instance " + inst.resource_path + "]"
		var extra := []
		var gr := st.get_node_groups(i)
		if gr.size() > 0: extra.append("groups=" + str(gr))
		for j in st.get_node_property_count(i):
			var pn := st.get_node_property_name(i, j)
			var pv = st.get_node_property_value(i, j)
			if pn == "script" and pv is Script: extra.append("script=" + pv.resource_path)
			elif pn == "unique_name_in_owner" and pv: extra.append("%unique")
			elif "--all-props" in args: extra.append(pn + "=" + var_to_str(pv))
			else: extra.append(pn)
		if not extra.is_empty(): line += "  {" + ", ".join(extra) + "}"
		print(line)
	for i in st.get_connection_count():
		print("  connect ", st.get_connection_source(i), ".", st.get_connection_signal(i), " -> ",
			st.get_connection_target(i), ".", st.get_connection_method(i), " flags=", st.get_connection_flags(i))
	var deps := ResourceLoader.get_dependencies(path)
	print("  deps: ", deps)
	quit(0)
