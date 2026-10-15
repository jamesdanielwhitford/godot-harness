extends SceneTree
# Loads every .gd/.tscn/.tres under res://, instantiates scenes. Prints LOADALL lines.
var fails := 0
var n := {"gd":0,"tscn":0,"tres":0}
func _initialize() -> void:
	_walk("res://")
	print("LOADALL_SUMMARY gd=%d tscn=%d tres=%d fails=%d" % [n.gd, n.tscn, n.tres, fails])
	quit(0)
func _walk(p: String) -> void:
	var d := DirAccess.open(p)
	if d == null: return
	for f in d.get_files():
		var path := p.path_join(f)
		var ext := f.get_extension()
		if ext == "gd":
			n.gd += 1
			var s = load(path)
			if s == null or not (s is GDScript) or not s.can_instantiate() and not s.is_abstract():
				# can_instantiate false is normal for static-only/abstract; only count null loads
				if s == null: fails += 1; print("LOADALL_FAIL ", path)
		elif ext == "tscn":
			n.tscn += 1
			var ps = load(path)
			if ps == null: fails += 1; print("LOADALL_FAIL ", path); continue
			var inst = ps.instantiate()
			if inst == null: fails += 1; print("LOADALL_FAIL(inst) ", path)
			else: inst.free()
		elif ext == "tres":
			n.tres += 1
			if load(path) == null: fails += 1; print("LOADALL_FAIL ", path)
	for sub in d.get_directories():
		if sub.begins_with("."): continue
		_walk(p.path_join(sub))
