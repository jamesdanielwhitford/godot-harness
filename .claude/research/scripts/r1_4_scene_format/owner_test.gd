extends SceneTree
func _init() -> void:
	# (a) forget owner on grandchild
	var r := Node2D.new(); r.name = "R"
	var a := Node2D.new(); a.name = "A"; r.add_child(a); a.owner = r
	var b := Node2D.new(); b.name = "B_noowner"; a.add_child(b)             # no owner
	var c := Node2D.new(); c.name = "C_wrongowner"; a.add_child(c); c.owner = a  # owner is not the root
	var ps := PackedScene.new(); print("pack a: ", error_string(ps.pack(r)))
	ResourceSaver.save(ps, "res://cases/own_a.tscn")
	# (b) owner on children of instanced scene
	var r2 := Node2D.new(); r2.name = "R2"
	var inst: Node = load("res://scenes/child.tscn").instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE)
	r2.add_child(inst); inst.owner = r2
	for ch in inst.get_children(): ch.owner = r2     # the mistake
	var ps2 := PackedScene.new(); print("pack b: ", error_string(ps2.pack(r2)))
	ResourceSaver.save(ps2, "res://cases/own_b.tscn")
	# (c) pack a non-root-owned subtree: pack(a) where a has parent
	var ps3 := PackedScene.new(); print("pack c (node with parent, children owned by r): ", error_string(ps3.pack(a)))
	ResourceSaver.save(ps3, "res://cases/own_c.tscn")
	# (d) name collisions: two children same name
	var r4 := Node2D.new(); r4.name = "R4"
	for i in 2:
		var x := Node2D.new(); x.name = "Dup"; r4.add_child(x); x.owner = r4
	print("names: ", r4.get_children().map(func(n): return n.name))
	var ps4 := PackedScene.new(); ps4.pack(r4); ResourceSaver.save(ps4, "res://cases/own_d.tscn")
	# (e) add_child with force_readable_name false vs true: name of unnamed node
	var r5 := Node2D.new(); r5.name = "R5"; var y := Sprite2D.new(); r5.add_child(y); y.owner = r5; print("auto name: ", y.name)
	var z := Sprite2D.new(); r5.add_child(z, true); z.owner = r5; print("auto name readable: ", z.name)
	quit()
