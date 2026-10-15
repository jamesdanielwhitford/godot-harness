extends SceneTree
func _init() -> void:
	for p in OS.get_cmdline_user_args():
		var r = load(p).instantiate()
		var s := p.get_file() + ": "
		match p.get_file():
			"c01_unknown_node_prop.tscn": s += "position=%s meta=%s props_has_speeed=%s" % [r.position, r.get_meta_list(), "speeed" in r]
			"c02_unknown_subres_prop.tscn": s += "shape=%s" % [r.shape]
			"c04_wrong_uid_right_path.tscn", "c05_right_uid_wrong_path.tscn": s += "script=%s speed=%s" % [r.get_script(), r.get("speed")]
			"c06_dup_ext_id.tscn": s += "script=%s" % [r.get_script().resource_path if r.get_script() else null]
			"c07_dup_sub_id.tscn": s += "shape=%s radius=%s" % [r.shape.get_class(), r.shape.get("radius")]
			"c15_wrong_value_type.tscn": s += "position=%s visible=%s z=%s" % [r.position, r.visible, r.z_index]
			"c20_no_header_format.tscn", "c21_stale_load_steps.tscn", "c22_godot3_format.tscn": s += "root=%s script=%s" % [r.name, r.get_script()]
			"c24_typed_arrays.tscn": s += "a=%s d=%s np=%s" % [var_to_str(r.get_meta("a")), var_to_str(r.get_meta("d")), r.get_meta("np")]
			"c25_bad_nodepath_export.tscn", "c26_export_node_no_node_paths.tscn": s += "target=%s" % [r.get("target")]
			"c13_two_roots.tscn": s += "-"
		print(s)
		r.free()
	quit()
