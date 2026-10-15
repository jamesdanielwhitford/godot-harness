extends SceneTree
# Args: test=add|move|self|swap  Prints INV_JSON
var scene: Node
var slots: Array = []
var adders: Array = []
var f := 0
var test := "add"
func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("test="): test = a.substr(5)
	var ms: String = ProjectSettings.get_setting("application/run/main_scene", "")
	scene = (load(ms) as PackedScene).instantiate()
	root.add_child(scene)
func _walk(n: Node) -> void:
	for c in n.get_children(): _walk(c)
	if n is Control and n.has_method("_get_drag_data"): slots.append(n)
	if n is Button and not n.has_method("_get_drag_data"):
		var t: String = (n.text + " " + String(n.name)).to_lower()
		for k in ["add", "give", "+", "pick", "spawn", "random", "item", "potion", "sword", "arrow", "armor", "shield"]:
			if t.contains(k): adders.append(n); break
func _occ() -> Array:
	var o := []
	for i in slots.size():
		if slots[i]._get_drag_data(Vector2(4, 4)) != null: o.append(i)
	return o
func _out(d: Dictionary) -> bool:
	print("INV_JSON ", JSON.stringify(d)); quit(0); return true
func _physics_process(_d: float) -> bool:
	f += 1
	if f == 3:
		_walk(scene)
	if f == 4:
		if slots.size() == 0: return _out({"err": "no slot controls with _get_drag_data (custom DnD or none)", "adders": adders.size()})
		var n_presses := 0
		var rounds := 40 if test == "add" else (adders.size() * 3 if test == "stack" else 6)
		for r in rounds:
			if adders.is_empty(): break
			var b: Button = adders[r % adders.size()]
			b.pressed.emit(); n_presses += 1
		var occ := _occ()
		if test == "add" or test == "stack":
			return _out({"n_slots": slots.size(), "adders": adders.size(), "presses": n_presses, "occupied": occ.size()})
		if occ.is_empty(): return _out({"err": "nothing added", "n_slots": slots.size(), "adders": adders.size()})
		var a: int = occ[0]
		var data = slots[a]._get_drag_data(Vector2(4, 4))
		if test == "self":
			var ok: bool = slots[a]._can_drop_data(Vector2(4, 4), data)
			if ok: slots[a]._drop_data(Vector2(4, 4), data)
			return _out({"occ_before": occ.size(), "occ_after": _occ().size(), "can_drop_self": ok})
		if test == "move":
			var empty := -1
			for i in slots.size():
				if not occ.has(i): empty = i; break
			if empty < 0: return _out({"err": "no empty slot"})
			var ok2: bool = slots[empty]._can_drop_data(Vector2(4, 4), data)
			if ok2: slots[empty]._drop_data(Vector2(4, 4), data)
			var after := _occ()
			return _out({"can_drop": ok2, "occ_before": occ.size(), "occ_after": after.size(), "src_empty_after": not after.has(a), "dst_occupied_after": after.has(empty)})
		if test == "swap":
			if occ.size() < 2: return _out({"err": "need 2 occupied", "occ": occ.size()})
			var b2: int = occ[1]
			var ok3: bool = slots[b2]._can_drop_data(Vector2(4, 4), data)
			if ok3: slots[b2]._drop_data(Vector2(4, 4), data)
			return _out({"can_drop": ok3, "occ_before": occ.size(), "occ_after": _occ().size()})
	if f > 10: return _out({"err": "timeout"})
	return false
