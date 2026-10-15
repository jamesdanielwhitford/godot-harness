extends SceneTree
## Usage: godot --headless --path <proj> --script load_check.gd -- res://a.tscn [res://b.tres ...]
## Loads (cache ignored) + instantiates each file, capturing every engine ERROR/WARNING via OS.add_logger.
## Exit 0 = clean; 1 = load/instantiate failure; 3 = loaded but engine emitted errors/warnings.
class Cap extends Logger:
	var msgs: PackedStringArray = []
	func _log_error(function: String, file: String, line: int, code: String, rationale: String, editor_notify: bool, error_type: int, script_backtraces: Array) -> void:
		var kind := "WARNING" if error_type == ERROR_TYPE_WARNING else "ERROR"
		msgs.append("%s: %s" % [kind, rationale if rationale != "" else code])
func _init() -> void:
	var cap := Cap.new()
	OS.add_logger(cap)
	var rc := 0
	for p in OS.get_cmdline_user_args():
		var before := cap.msgs.size()
		var res = ResourceLoader.load(p, "", ResourceLoader.CACHE_MODE_IGNORE)
		if res == null:
			print("FAIL load ", p); rc = 1
		else:
			var detail := ""
			if res is PackedScene:
				var inst = res.instantiate()
				if inst == null: print("FAIL instantiate ", p); rc = 1
				else:
					detail = " root=%s children=%d" % [inst.get_class(), inst.get_child_count()]
					inst.free()
			print("loaded ", p, detail)
		for i in range(before, cap.msgs.size()):
			print("  ", cap.msgs[i])
		if cap.msgs.size() > before and rc == 0: rc = 3
	OS.remove_logger(cap)
	quit(rc)
