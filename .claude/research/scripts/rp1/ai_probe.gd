extends SceneTree
# Args: mode=clear|blocked|freed|cands  idx=<n>
var player: Node2D
var enemy: Node2D
var mode := "clear"
var idx := 0
var frame := 0
var target := Vector2.ZERO
var dists: Array = []
var states: Array = []
var enum_names := {}
var state_prop := ""
var freed_done := false
var enemy_start := Vector2.ZERO
const CHASEY := ["chase","attack","pursue","alert","hunt","follow","engage","combat"]
func _find(n: Node, pred: Callable, out: Array) -> void:
	if pred.call(n): out.append(n)
	for c in n.get_children(): _find(c, pred, out)
func _blocked(a: Vector2, b: Vector2) -> bool:
	var q := PhysicsRayQueryParameters2D.create(a, b, 0xFFFFFFFF)
	q.exclude = [player.get_rid(), enemy.get_rid()] if player is CollisionObject2D and enemy is CollisionObject2D else []
	return not get_root().get_world_2d().direct_space_state.intersect_ray(q).is_empty()
func _free_pt(p: Vector2) -> bool:
	var q := PhysicsPointQueryParameters2D.new()
	q.position = p; q.collision_mask = 0xFFFFFFFF
	return get_root().get_world_2d().direct_space_state.intersect_point(q, 4).is_empty()
func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.split("=", true, 1)
		if kv[0] == "mode": mode = kv[1]
		if kv[0] == "idx": idx = int(kv[1])
	var ms: String = ProjectSettings.get_setting("application/run/main_scene", "")
	var scene: Node = (load(ms) as PackedScene).instantiate()
	root.add_child(scene)
	var ps := []; _find(scene, func(n): return n is CharacterBody2D and (n.is_in_group("player") or "player" in n.name.to_lower()), ps)
	var es := []; _find(scene, func(n): return (n is CharacterBody2D or n is Node2D) and "enemy" in n.name.to_lower() and not (n.get_parent() != null and "enemy" in n.get_parent().name.to_lower() and n.get_parent() is Node2D and n.get_parent() != scene), es)
	if ps.is_empty() or es.is_empty(): print("PROBE_JSON ", JSON.stringify({"err": "player/enemy not found", "p": ps.size(), "e": es.size()})); quit(2); return
	player = ps[0]; enemy = es[0]
	var sc = enemy.get_script()
	if sc != null:
		for p in enemy.get_property_list():
			if p.usage & PROPERTY_USAGE_SCRIPT_VARIABLE and p.name.to_lower() in ["state","current_state","_state","ai_state","behavior","mode"]:
				state_prop = p.name
		var cm: Dictionary = sc.get_script_constant_map()
		for k in cm:
			if cm[k] is Dictionary and (k.to_lower().contains("state") or k.to_lower().contains("mode")):
				for n in cm[k]: enum_names[cm[k][n]] = String(n)
	player.set_physics_process(false); player.set_process_input(false); player.set_process_unhandled_input(false)
	if player is CharacterBody2D: player.velocity = Vector2.ZERO
func _sname(v) -> String:
	if enum_names.has(v): return enum_names[v]
	return str(v)
func _physics_process(_d: float) -> bool:
	if enemy == null: return false
	frame += 1
	if frame == 5:
		enemy_start = enemy.global_position
		var cands := []
		var ring := [60.0, 90.0, 120.0, 150.0] if mode != "clear" else [80.0]
		for r in ring:
			for k in 16:
				var p: Vector2 = enemy_start + Vector2.RIGHT.rotated(TAU * k / 16.0) * float(r)
				if not _free_pt(p): continue
				var b: bool = _blocked(enemy_start, p)
				if (mode == "blocked" or mode == "cands") == b: cands.append(p)
		if mode == "cands":
			print("PROBE_JSON ", JSON.stringify({"n_blocked_cands": cands.size()})); quit(0); return true
		if cands.is_empty(): print("PROBE_JSON ", JSON.stringify({"err": "no candidate point for mode " + mode})); quit(3); return true
		target = cands[min(idx * 3, cands.size() - 1)] if mode == "blocked" else cands[0]
		player.global_position = target
	if frame > 5:
		var chasey := false
		if state_prop != "":
			var sn := _sname(enemy.get(state_prop)).to_lower()
			states.append(sn)
		if player != null and is_instance_valid(player):
			dists.append(enemy.global_position.distance_to(player.global_position))
		else:
			dists.append(-1.0)
		if mode == "freed" and frame == 50 and is_instance_valid(player):
			player.queue_free()
		if frame >= 150:
			var changes := 0
			for i in range(1, states.size()):
				if states[i] != states[i-1]: changes += 1
			var chase_frames := 0
			for s in states:
				for w in CHASEY:
					if s.contains(w): chase_frames += 1; break
			var d0 = dists[0] if dists.size() > 0 else -1
			print("PROBE_JSON ", JSON.stringify({"mode": mode, "state_prop": state_prop, "state_values": states.slice(0,1) + states.slice(-1), "distinct_states": _distinct(), "state_changes": changes, "chase_frames": chase_frames, "dist_start": d0, "dist_min": dists.min() if dists.size() > 0 else -1, "dist_end": dists[-1] if dists.size() > 0 else -1}))
			quit(0); return true
	return false
func _distinct() -> Array:
	var out := []
	for s in states:
		if not out.has(s): out.append(s)
	return out
