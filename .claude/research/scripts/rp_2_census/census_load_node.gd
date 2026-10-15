extends Node
## Injected as main scene so autoload globals exist. Loads every .gd and .tscn under res:// (cache ignored).
class Cap extends Logger:
	var msgs: PackedStringArray = []
	func _log_error(function: String, file: String, line: int, code: String, rationale: String, editor_notify: bool, error_type: int, script_backtraces: Array) -> void:
		msgs.append(("W: " if error_type == ERROR_TYPE_WARNING else "E: ") + (rationale if rationale != "" else code))
func _walk(d: String, out: Array) -> void:
	var da: DirAccess = DirAccess.open(d)
	if da == null: return
	for f: String in da.get_files():
		var e: String = f.get_extension()
		if e == "gd" or e == "tscn": out.append(d.path_join(f))
	for s: String in da.get_directories():
		if s.begins_with(".") or s == "__census": continue
		_walk(d.path_join(s), out)
func _ready() -> void:
	await get_tree().process_frame
	var cap: Cap = Cap.new()
	OS.add_logger(cap)
	var files: Array = []
	_walk("res://", files)
	var stat: Dictionary = {}
	var firsts: Array = []
	for p: String in files:
		var addon: bool = p.begins_with("res://addons/")
		var key: String = ("addon_" if addon else "game_") + p.get_extension()
		if not stat.has(key): stat[key] = {"n": 0, "fail": 0, "err": 0, "warn": 0}
		stat[key]["n"] += 1
		var before: int = cap.msgs.size()
		var res: Resource = ResourceLoader.load(p, "", ResourceLoader.CACHE_MODE_IGNORE)
		if res == null:
			stat[key]["fail"] += 1
		elif res is PackedScene:
			var inst: Node = (res as PackedScene).instantiate()
			if inst == null: stat[key]["fail"] += 1
			else: inst.free()
		var had_e: bool = false
		var had_w: bool = false
		for i: int in range(before, cap.msgs.size()):
			if cap.msgs[i].begins_with("E:"): had_e = true
			else: had_w = true
		if had_e: stat[key]["err"] += 1
		if had_w: stat[key]["warn"] += 1
		if (had_e or res == null) and firsts.size() < 10 and not addon:
			firsts.append(p + " :: " + (cap.msgs[before] if cap.msgs.size() > before else "load null"))
	OS.remove_logger(cap)
	print("CENSUS_STAT ", JSON.stringify(stat))
	for f: String in firsts: print("CENSUS_FIRST ", f)
	get_tree().quit(0)
