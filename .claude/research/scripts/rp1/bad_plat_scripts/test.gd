extends SceneTree
func _initialize():
	var lv = load("res://scenes/level.tscn").instantiate()
	root.add_child(lv)
	var p = lv.get_node("Player")
	var frame := 0
	var start_y := 0.0
	var best := 0.0
	var best_f := 0
	var phase := 0
	var f2 := 0
	while frame < 400:
		await physics_frame
		frame += 1
		if phase == 0:
			if p.is_on_floor() and frame > 10:
				phase = 1; start_y = p.position.y
				
				Input.action_press("jump"); f2 = 0
		elif phase == 1:
			f2 += 1
			pass
			var h = start_y - p.position.y
			if h > best: best = h; best_f = f2 - 1
			if f2 == 20: print("speed@20f=", p.velocity.x); 
			var sp = p.velocity.x
			if sp >= 220.0 and not has_meta("m"): set_meta("m", true); print("max speed frame ", f2)
			if f2 > 60: break
	print("apex h=", best, " at t=", best_f/60.0)
	quit()
