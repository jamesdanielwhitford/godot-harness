extends SceneTree
# Args: size=WxH (passed also as --resolution). Prints UI_JSON with layout metrics for the main scene.
func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("size="):
			var wh := a.substr(5).split("x")
			root.size = Vector2i(int(wh[0]), int(wh[1]))
	var ms: String = ProjectSettings.get_setting("application/run/main_scene", "")
	root.add_child((load(ms) as PackedScene).instantiate())
var f := 0
func _collect(n: Node, out: Array) -> void:
	if n is Control and n.is_visible_in_tree(): out.append(n)
	for c in n.get_children(): _collect(c, out)
func _physics_process(_d: float) -> bool:
	f += 1
	if f < 8: return false
	var vp := root.get_visible_rect()
	var ctrls := []
	_collect(root, ctrls)
	var outside := []
	var leaves := []
	var vp_area := vp.size.x * vp.size.y
	for c in ctrls:
		var r: Rect2 = c.get_global_rect()
		if r.size.x <= 0 or r.size.y <= 0: continue
		var is_leaf: bool = (c is Label or c is Button or c is ProgressBar or c is RichTextLabel or c is TextureProgressBar or (c is TextureRect and r.size.x * r.size.y < 0.25 * vp_area))
		if is_leaf:
			leaves.append(c)
			if not vp.grow(1.0).encloses(r): outside.append(String(c.get_path()))
	var overlaps := []
	for i in leaves.size():
		for j in range(i + 1, leaves.size()):
			var a: Control = leaves[i]; var b: Control = leaves[j]
			if a.is_ancestor_of(b) or b.is_ancestor_of(a): continue
			var ra: Rect2 = a.get_global_rect(); var rb: Rect2 = b.get_global_rect()
			var inter: Rect2 = ra.intersection(rb)
			if inter.size.x > 2 and inter.size.y > 2:
				var smaller: float = min(ra.get_area(), rb.get_area())
				if inter.get_area() < 0.8 * smaller: overlaps.append(String(a.name) + "<>" + String(b.name))
	var names := {}
	for c in leaves:
		var r2: Rect2 = c.get_global_rect()
		names[String(c.name)] = [r2.position.x, r2.position.y, vp.size.x - r2.end.x, vp.size.y - r2.end.y]
	print("UI_JSON ", JSON.stringify({"vp": [vp.size.x, vp.size.y], "win": [root.size.x, root.size.y], "n_controls": ctrls.size(), "outside": outside.slice(0, 8), "overlaps": overlaps.slice(0, 8), "norm": names}))
	quit(0); return true
