extends SceneTree
# Drives menu -> level1 -> level2 -> game over -> retry, N cycles, heuristically. Prints FLOW_JSON.
const CYCLES := 8
var cycle := 0
var step := 0          # 0 find menu/Play,1 wait L1,2 hit exit,3 wait L2,4 hit hazard,5 wait GO,6 retry,7 wait L1 again
var wait := 0
var menu_path := ""
var paths := []
var log_steps := []
var fade_frames := 0
var fade_seen := false
var counts := []
var done := false
var problems := []
var last_path := ""
var total := 0
var settle_wait := 90
func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("settle="): settle_wait = int(a.substr(7))
	change_scene_to_file(ProjectSettings.get_setting("application/run/main_scene"))
func _cs() -> Node: return current_scene
func _btn(n: Node, rx: String) -> Button:
	var re := RegEx.new(); re.compile("(?i)" + rx)
	var st := [n]
	while not st.is_empty():
		var c = st.pop_back()
		if c is Button and c.is_visible_in_tree() and (re.search(c.text) != null or re.search(String(c.name)) != null): return c
		st.append_array(c.get_children())
	return null
func _area(n: Node, rx: String) -> Node2D:
	var re := RegEx.new(); re.compile("(?i)" + rx)
	var st := [n]
	while not st.is_empty():
		var c = st.pop_back()
		if (c is Area2D or c is Node3D) and re.search(String(c.name)) != null: return c
		st.append_array(c.get_children())
	return null
func _player(n: Node) -> Node2D:
	var st := [n]
	while not st.is_empty():
		var c = st.pop_back()
		if c is CharacterBody2D and (c.is_in_group("player") or "player" in String(c.name).to_lower()): return c
		st.append_array(c.get_children())
	return null
func _scan_fade() -> void:
	var vp := root.get_visible_rect().size
	var st := [root]
	while not st.is_empty():
		var c = st.pop_back()
		if c is Control and c.is_visible_in_tree():
			var a := 1.0
			var n: Node = c
			while n is CanvasItem:
				a *= n.modulate.a
				n = n.get_parent()
			if c is ColorRect: a *= c.color.a
			if (c is ColorRect or c is TextureRect or c is Panel) and c.size.x >= vp.x * 0.9 and c.size.y >= vp.y * 0.9 and a > 0.05 and a < 0.95:
				fade_frames += 1; fade_seen = true; return
		st.append_array(c.get_children())
func _physics_process(_d: float) -> bool:
	if done: return false
	total += 1
	if total > 12000: return _fail("global frame cap")
	if wait > 0:
		wait -= 1
	var cs := _cs()
	if cs == null: return false
	if total < 10: return false
	_scan_fade()
	match step:
		0:
			if wait > 0: return false
			menu_path = cs.scene_file_path
			var b := _btn(cs, "play|start|new game|begin")
			if b == null: return _fail("no Play button in main scene " + menu_path)
			last_path = menu_path
			b.pressed.emit(); step = 1; wait = 400
		1, 3, 5, 7:
			var p := cs.scene_file_path
			if p != last_path:
				last_path = p; paths.append(p); log_steps.append([cycle, step, p, 400 - wait]); step += 1; wait = settle_wait
			elif wait == 0: return _fail("timeout waiting scene change at step %d (still %s)" % [step, last_path])
		2:
			if wait > 0: return false
			var ex := _area(cs, "exit|goal|door|finish|portal|end|flag|next")
			var pl := _player(cs)
			if ex == null or pl == null: return _fail("no exit/player in " + cs.scene_file_path)
			pl.global_position = ex.global_position
			if "velocity" in pl: pl.velocity = Vector2.ZERO
			step = 3; wait = 400
		4:
			if wait > 0: return false
			var hz := _area(cs, "hazard|spike|death|kill|lava|trap|damage|danger")
			var pl2 := _player(cs)
			if hz == null or pl2 == null: return _fail("no hazard/player in " + cs.scene_file_path)
			pl2.global_position = hz.global_position
			if "velocity" in pl2: pl2.velocity = Vector2.ZERO
			step = 5; wait = 400
		6:
			if wait > 0: return false
			var rb := _btn(cs, "retry|again|restart|try")
			if rb == null: return _fail("no Retry button on game over scene " + cs.scene_file_path)
			rb.pressed.emit(); step = 7; wait = 400
		8:
			# back in level 1 again
			if wait > 0: return false
			if paths.size() >= 4 and paths[-1] != paths[0]: problems.append("retry did not return to level 1 (%s vs %s)" % [paths[-1], paths[0]])
			counts.append([int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT)), int(Performance.get_monitor(Performance.OBJECT_ORPHAN_NODE_COUNT)), int(Performance.get_monitor(Performance.OBJECT_COUNT))])
			cycle += 1
			if cycle >= CYCLES: return _finish()
			# go back to menu via goto if possible, else restart from level 1 by repeating exit->hazard path
			step = 2; wait = 5; paths.append("(loop)")
	return false
func _fail(msg: String) -> bool:
	problems.append(msg); return _finish()
func _finish() -> bool:
	done = true
	print("FLOW_JSON ", JSON.stringify({"cycles_done": cycle, "problems": problems, "paths": paths.slice(0, 6), "fade_seen": fade_seen, "fade_frames": fade_frames, "counts_node_orphan_obj": counts, "steps": log_steps.slice(0, 6)}))
	quit(0); return true
