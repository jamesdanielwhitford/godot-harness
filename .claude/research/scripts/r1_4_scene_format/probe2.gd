extends SceneTree
func _init() -> void:
	var r = load("res://cases/d06_dup_sibling_names.tscn").instantiate()
	print("d06 children: ", r.get_children().map(func(n): return "%s:%s" % [n.name, n.get_class()]))
	r.free()
	r = load("res://cases/d04_no_editable.tscn").instantiate()
	print("d04 A/Sprite pos (override w/o [editable]): ", r.get_node("A/Sprite").position)
	var ps := PackedScene.new(); ps.pack(r); ResourceSaver.save(ps, "res://cases/d04_resaved_flat.tscn")
	r.free()
	r = load("res://cases/d04_no_editable.tscn").instantiate(PackedScene.GEN_EDIT_STATE_MAIN)
	ps = PackedScene.new(); ps.pack(r); ResourceSaver.save(ps, "res://cases/d04_resaved_main.tscn")
	r.free()
	quit()
