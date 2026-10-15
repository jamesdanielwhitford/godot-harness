extends SceneTree
# Platformer scenario probe. Args after --: scenario=<json path> out=<csv path>
# Scenario JSON: {"floor_end": <px or null>, "wall_x": <px or null>, "frames": N,
#   "events": [{"f":int,"a":str,"p":bool} | {"after":"airborne","k":int,"a":str,"p":bool} ]}
# The agent's main scene is instantiated far from origin test geometry is added at (100000,100000).
const OX := 100000.0
const OY := 100000.0
var player: CharacterBody2D
var sc: Dictionary
var rows: Array = []
var frame := -1
var settle := 90
var held := {}
var left_floor_frame := -1
var was_floor := true
func _find_player(n: Node) -> CharacterBody2D:
	var best: CharacterBody2D = null
	var stack := [n]
	while not stack.is_empty():
		var c: Node = stack.pop_back()
		if c is CharacterBody2D:
			if best == null or "player" in c.name.to_lower() or c.is_in_group("player"): best = c
		for k in c.get_children(): stack.append(k)
	return best
func _initialize() -> void:
	var args := {}
	for a in OS.get_cmdline_user_args():
		var kv := a.split("=", true, 1)
		if kv.size() == 2: args[kv[0]] = kv[1]
	sc = JSON.parse_string(FileAccess.get_file_as_string(args["scenario"]))
	if sc.has("tps"): Engine.physics_ticks_per_second = int(sc["tps"])
	var ms: String = ProjectSettings.get_setting("application/run/main_scene", "")
	var scene: Node = (load(ms) as PackedScene).instantiate()
	root.add_child(scene)
	player = _find_player(scene)
	if player == null:
		print("PROBE_ERR no CharacterBody2D found"); quit(2); return
	# test floor: top surface at y=OY
	var fe = sc.get("floor_end", null)
	var x0 := OX - 3000.0
	var x1 := OX + 3000.0 if fe == null else OX + float(fe)
	_add_box(Vector2((x0 + x1) / 2.0, OY + 16.0), Vector2(x1 - x0, 32.0))
	var wx = sc.get("wall_x", null)
	if wx != null:
		_add_box(Vector2(OX + float(wx) + 16.0, OY - 400.0), Vector2(32.0, 1000.0))
	player.velocity = Vector2.ZERO
	player.global_position = Vector2(OX, OY - 60.0)
	set_meta("out", args["out"])
func _add_box(c: Vector2, s: Vector2) -> void:
	var b := StaticBody2D.new()
	b.collision_layer = 0xFFFFFFFF
	b.collision_mask = 0
	var cs := CollisionShape2D.new()
	var r := RectangleShape2D.new(); r.size = s
	cs.shape = r; b.add_child(cs); root.add_child(b); b.global_position = c
func _act(a: String, p: bool) -> void:
	if p: Input.action_press(a)
	else: Input.action_release(a)
func _physics_process(_d: float) -> bool:
	if player == null or not is_instance_valid(player): return false
	frame += 1
	var f := frame - settle
	if f >= 0:
		var onf := player.is_on_floor()
		if was_floor and not onf and left_floor_frame < 0 and player.velocity.y >= 0.0: left_floor_frame = f
		was_floor = onf
		for e in sc["events"]:
			if e.has("f") and e["f"] == f: _act(e["a"], e["p"])
			elif e.has("after") and left_floor_frame >= 0 and f == left_floor_frame + int(e["k"]) and not e.get("done", false):
				_act(e["a"], e["p"]); e["done"] = true
		rows.append([f, player.global_position.x - OX, player.global_position.y - OY, player.velocity.x, player.velocity.y, int(player.is_on_floor()), int(player.is_on_wall())])
		if f >= int(sc["frames"]):
			var fa := FileAccess.open(get_meta("out"), FileAccess.WRITE)
			fa.store_line("f,x,y,vx,vy,floor,wall")
			for r in rows: fa.store_line(",".join(PackedStringArray(r.map(func(v): return str(v)))))
			fa.close(); print("PROBE_OK rows=", rows.size()); quit(0); return true
	return false
