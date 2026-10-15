extends SceneTree
## h check runner (A1 2.7). Run by absolute path:
##   godot --headless --path <proj> -s <this file> -- --mode scripts|scenes --list <file of res:// paths> [--smoke N]
## Per item: loads with the cache ignored (scenes: instantiate, optionally add to the tree and step N physics
## frames), capturing every engine ERROR/WARNING/SCRIPT ERROR through a Logger. Output: `@@H <json>` lines.
## Never calls .new() on loaded scripts. rc: 0 clean, 1 findings, 2 bad args.

class Cap extends Logger:
	var recs: Array = []

	func _log_error(function: String, file: String, line: int, code: String, rationale: String, editor_notify: bool, error_type: int, script_backtraces: Array) -> void:
		var bt: Array = []
		for sb in script_backtraces:
			if sb == null or sb.is_empty():
				continue
			for i in range(sb.get_frame_count()):
				var f: String = sb.get_frame_file(i)
				if f.begins_with("res://"):
					bt.append("%s:%d" % [f, sb.get_frame_line(i)])
		var t := 0
		if error_type == 1:
			t = 1
		elif error_type == 2:
			t = 2
		recs.append({"type": t, "file": file, "line": line, "msg": rationale if rationale != "" else code, "bt": bt})


func _emit(d: Dictionary) -> void:
	print("@@H " + JSON.stringify(d))


func _bad_args(msg: String) -> void:
	printerr("load_check: " + msg)
	_emit({"t": "done", "rc": 2})
	quit(2)


func _init() -> void:
	var mode := ""
	var list_path := ""
	var smoke := 0
	var args := OS.get_cmdline_user_args()
	var i := 0
	while i < args.size():
		var a: String = args[i]
		if a == "--mode" and i + 1 < args.size():
			mode = args[i + 1]
			i += 2
		elif a == "--list" and i + 1 < args.size():
			list_path = args[i + 1]
			i += 2
		elif a == "--smoke" and i + 1 < args.size():
			smoke = int(args[i + 1])
			i += 2
		else:
			_bad_args("unknown argument " + a)
			return
	if mode != "scripts" and mode != "scenes":
		_bad_args("--mode must be scripts or scenes")
		return
	if not FileAccess.file_exists(list_path):
		_bad_args("--list file not found: " + list_path)
		return
	var items: Array = []
	for ln in FileAccess.get_file_as_string(list_path).split("\n"):
		var s := ln.strip_edges()
		if s != "":
			items.append(s)

	var cap := Cap.new()
	OS.add_logger(cap)
	var rc := 0
	for p in items:
		_emit({"t": "data", "ev": "begin", "path": p})
		cap.recs.clear()
		var status := "ok"
		var res = ResourceLoader.load(p, "", ResourceLoader.CACHE_MODE_IGNORE)
		if res == null:
			status = "load-failed"
		elif mode == "scenes" and res is PackedScene:
			var inst = res.instantiate()
			if inst == null:
				status = "instantiate-failed"
			else:
				if smoke > 0:
					root.add_child(inst)
					for _n in range(smoke):
						await physics_frame
					if is_instance_valid(inst) and inst.get_parent() == root:
						root.remove_child(inst)
				if is_instance_valid(inst):
					inst.free()
		res = null
		var recs: Array = cap.recs.duplicate()
		if status != "ok":
			rc = 1
		for r in recs:
			if r["type"] != 1:
				rc = 1
		_emit({"t": "data", "ev": "end", "path": p, "status": status, "recs": recs})
	OS.remove_logger(cap)
	_emit({"t": "done", "rc": rc})
	quit(rc)
