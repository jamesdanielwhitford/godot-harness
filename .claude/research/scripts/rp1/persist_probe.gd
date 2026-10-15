extends SceneTree
# Args: mode=mutate|check|reset. Prints PERSIST_JSON. Finds the autoload that owns save_game/save and drives it by name patterns.
var mode := "check"
var owner_node: Node
var f := 0
func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("mode="): mode = a.substr(5)
func _find_owner() -> Node:
	for c in root.get_children():
		if c.get_script() != null and (c.has_method("save_game") or c.has_method("save") or c.has_method("save_all")):
			return c
	return null
func _saver(n: Node) -> String:
	for m in ["save_game", "save", "save_all"]:
		if n.has_method(m): return m
	return ""
func _physics_process(_d: float) -> bool:
	f += 1
	if f < 5: return false
	owner_node = _find_owner()
	var out := {"mode": mode}
	if owner_node == null:
		out["err"] = "no autoload with save method"; print("PERSIST_JSON ", JSON.stringify(out)); quit(0); return true
	out["owner"] = String(owner_node.name)
	var n := owner_node
	if mode == "mutate":
		var notes := []
		if n.has_method("complete_level"):
			n.complete_level(1, 12.3); notes.append("complete_level(1,12.3)")
		if n.has_method("set_volume"):
			n.set_volume("Music", 0.3); notes.append("set_volume(Music,0.3)")
		elif "music_volume" in n:
			n.music_volume = 0.3; notes.append("music_volume=0.3")
			if n.has_method("apply_settings"): n.apply_settings()
		if n.has_method("set_binding"):
			n.set_binding("jump", KEY_K); notes.append("set_binding(jump,K)")
		var sv := _saver(n)
		if sv != "": n.call(sv); notes.append(sv + "()")
		out["notes"] = notes
	elif mode == "reset":
		if n.has_method("reset_progress"): n.reset_progress(); out["reset_called"] = true
		var sv2 := _saver(n)
		if sv2 != "": n.call(sv2)
	# observables
	var bus := AudioServer.get_bus_index("Music")
	out["music_bus_idx"] = bus
	if bus >= 0: out["music_linear"] = snappedf(db_to_linear(AudioServer.get_bus_volume_db(bus)), 0.001)
	var evs := InputMap.action_get_events("jump") if InputMap.has_action("jump") else []
	var keys := []
	for e in evs:
		if e is InputEventKey: keys.append(e.physical_keycode if e.physical_keycode != 0 else e.keycode)
	out["jump_keys"] = keys
	out["jump_has_K"] = keys.has(KEY_K)
	if n.has_method("is_completed"): out["lvl1_completed"] = n.is_completed(1)
	for bt in ["get_best_time", "best_time"]:
		if n.has_method(bt): out["lvl1_best"] = n.call(bt, 1)
	print("PERSIST_JSON ", JSON.stringify(out))
	quit(0); return true
