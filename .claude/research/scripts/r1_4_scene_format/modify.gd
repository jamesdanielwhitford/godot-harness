extends SceneTree
## Usage: -- res://in.tscn res://out.tscn <edit_state:0..3> (0=DISABLED,1=INSTANCE,2=MAIN,3=MAIN_INHERITED)
func _init() -> void:
	var a := OS.get_cmdline_user_args()
	var ps: PackedScene = load(a[0])
	var root := ps.instantiate(int(a[2]))
	root.position = Vector2(7, 7)             # a trivial edit
	var n := Node2D.new(); n.name = "Added"; root.add_child(n); n.owner = root
	var p2 := PackedScene.new()
	var e := p2.pack(root)
	if e != OK: printerr("pack failed ", e); quit(4); return
	e = ResourceSaver.save(p2, a[1])
	print("saved ", a[1], " err=", e)
	root.free()
	quit(0 if e == OK else 4)
