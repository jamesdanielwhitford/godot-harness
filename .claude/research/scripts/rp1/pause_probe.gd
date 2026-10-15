extends SceneTree
# menu -> Play -> level; exercises Esc pause. Prints PAUSE_JSON.
var f := 0
var phase := 0
var wait := 0
var out := {}
var menu_path := ""
var level_path := ""
var pos0 := Vector2.ZERO
var pl: Node2D
func _initialize() -> void:
	change_scene_to_file(ProjectSettings.get_setting("application/run/main_scene"))
func _btn(n: Node, rx: String) -> Button:
	var re := RegEx.new(); re.compile("(?i)" + rx)
	var st := [n]
	while not st.is_empty():
		var c = st.pop_back()
		if c is Button and c.is_visible_in_tree() and (re.search(c.text) != null or re.search(String(c.name)) != null): return c
		st.append_array(c.get_children())
	return null
func _btn_any(rx: String) -> Button:
	return _btn(root, rx)
func _player(n: Node) -> Node2D:
	var st := [n]
	while not st.is_empty():
		var c = st.pop_back()
		if c is CharacterBody2D and (c.is_in_group("player") or "player" in String(c.name).to_lower()): return c
		st.append_array(c.get_children())
	return null
func _esc() -> void:
	for pr in [true, false]:
		var e := InputEventKey.new()
		e.keycode = KEY_ESCAPE; e.physical_keycode = KEY_ESCAPE; e.pressed = pr
		Input.parse_input_event(e)
func _hold(on: bool) -> void:
	for a in ["move_right", "ui_right"]:
		if InputMap.has_action(a):
			if on: Input.action_press(a)
			else: Input.action_release(a)
func _end() -> bool:
	print("PAUSE_JSON ", JSON.stringify(out)); quit(0); return true
func _physics_process(_d: float) -> bool:
	f += 1
	if f < 10: return false
	if wait > 0:
		wait -= 1; return false
	var cs := current_scene
	if cs == null: return false
	match phase:
		0:
			menu_path = cs.scene_file_path
			var b := _btn(cs, "play|start|new game|begin")
			if b == null: out["err"] = "no Play"; return _end()
			b.pressed.emit(); phase = 1; wait = 120
		1:
			level_path = cs.scene_file_path
			if level_path == menu_path: out["err"] = "still on menu"; return _end()
			pl = _player(cs)
			out["level"] = level_path
			out["paused_before"] = paused
			if pl != null and is_instance_valid(pl):
				pos0 = pl.global_position
				_hold(true)
			phase = 15; wait = 30
		15:
			_hold(false)
			if pl != null and is_instance_valid(pl):
				out["control_moved_unpaused_px"] = snappedf(pl.global_position.distance_to(pos0), 0.1)
			wait = 20
			phase = 16
		16:
			_esc(); phase = 2; wait = 10
		2:
			out["paused_after_esc"] = paused
			out["time_scale_after_esc"] = Engine.time_scale
			var rs := _btn_any("resume|continue")
			var rt := _btn_any("restart|retry")
			var qt := _btn_any("menu|quit|exit")
			out["buttons_found"] = {"resume": rs != null, "restart": rt != null, "quit": qt != null}
			if rs != null:
				out["resume_can_process_while_paused"] = rs.can_process()
			var fo := root.gui_get_focus_owner()
			out["focus_owner_is_button"] = fo is Button
			if pl != null and is_instance_valid(pl):
				pos0 = pl.global_position
				_hold(true)
			phase = 3; wait = 40
		3:
			if pl != null and is_instance_valid(pl):
				out["world_moved_while_paused_px"] = snappedf(pl.global_position.distance_to(pos0), 0.1)
			_hold(false)
			var rs2 := _btn_any("resume|continue")
			if rs2 != null: rs2.pressed.emit()
			phase = 4; wait = 5
		4:
			out["paused_after_resume_button"] = paused
			_esc(); phase = 5; wait = 5
		5:
			out["paused_after_esc_again"] = paused
			_esc(); phase = 6; wait = 5
		6:
			out["paused_after_esc_toggle_off"] = paused
			_esc(); phase = 7; wait = 5
		7:
			var rt2 := _btn_any("restart|retry")
			if rt2 != null:
				rt2.pressed.emit()
			phase = 8; wait = 120
		8:
			out["after_restart_paused"] = paused
			out["after_restart_scene_is_level"] = current_scene != null and current_scene.scene_file_path == level_path
			out["after_restart_ts"] = Engine.time_scale
			_esc(); phase = 9; wait = 5
		9:
			var q := _btn_any("menu|quit|exit")
			if q != null: q.pressed.emit()
			phase = 10; wait = 150
		10:
			out["after_quit_paused"] = paused
			out["after_quit_scene"] = current_scene.scene_file_path if current_scene != null else "none"
			out["after_quit_is_menu"] = current_scene != null and current_scene.scene_file_path == menu_path
			out["after_quit_ts"] = Engine.time_scale
			# Esc on menu must not pause
			_esc(); phase = 11; wait = 10
		11:
			out["esc_on_menu_pauses"] = paused
			return _end()
	return false
