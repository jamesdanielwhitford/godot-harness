extends Node
# args after "--": mode=<rng|phys|time|anim> ticks=600
var args := {}
var ticks := 0
var target := 600
var bodies3: Array = []
var chars3: Array = []
var bodies2: Array = []
var chars2: Array = []
var pdeltas := []
var pdelta_sum := 0.0
var pdelta_min := 1e9
var pdelta_max := 0.0
var pdelta_n := 0
var pcount_per_frame := {}
var frames := 0
var procdeltas := []

func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.split("=")
		args[kv[0]] = kv[1] if kv.size() > 1 else "1"
	target = int(args.get("ticks", "600"))
	match args.get("mode", "phys"):
		"rng": run_rng(); get_tree().quit()
		"phys": build_phys()
		"time": build_time()
		"anim": build_anim()

func run_rng() -> void:
	var r := RandomNumberGenerator.new()
	r.seed = 12345
	var o := []
	for i in 5: o.append(r.randi())
	print("RNG seed=12345 randi x5: ", o)
	r.seed = 12345
	print("RNG randf x3: ", [r.randf(), r.randf(), r.randf()], " state=", r.state)
	r.seed = 12345
	print("RNG randi_range(0,99) x5: ", [r.randi_range(0,99), r.randi_range(0,99), r.randi_range(0,99), r.randi_range(0,99), r.randi_range(0,99)])
	r.seed = 12345
	print("RNG randfn x2: ", [r.randfn(), r.randfn()])
	r.seed = 12345
	var arr := [1,2,3,4,5,6,7,8,9,10]
	print("rng.pick? (RNG has no shuffle) randi_range-based: ", r.randi_range(0,9))
	# global
	seed(12345)
	print("global seed(12345) randi x3: ", [randi(), randi(), randi()])
	seed(12345)
	print("global randf x3: ", [randf(), randf(), randf()])
	seed(12345)
	var a := [1,2,3,4,5,6,7,8,9,10]
	a.shuffle()
	print("global shuffle: ", a)
	seed(12345)
	var b := [1,2,3,4,5,6,7,8,9,10]
	print("global pick_random x3: ", [b.pick_random(), b.pick_random(), b.pick_random()])
	seed(12345)
	print("global randi_range x3: ", [randi_range(0,99), randi_range(0,99), randi_range(0,99)])
	seed(12345)
	print("global randfn: ", randfn(0.0,1.0))
	seed(12345)
	var pa := PackedInt32Array([1,2,3,4,5,6,7,8,9,10])
	var pb := PackedInt32Array([1,2,3,4,5,6,7,8,9,10])
	# independence: does RNG instance use global?
	seed(1)
	var r2 := RandomNumberGenerator.new()
	r2.seed = 777
	var x1 := r2.randi()
	seed(999)
	r2.seed = 777
	var x2 := r2.randi()
	print("RNG independent of global seed: ", x1 == x2, " ", x1)
	# unseeded RNG differs?
	var u1 := RandomNumberGenerator.new(); var u2 := RandomNumberGenerator.new()
	print("two default-constructed RNGs equal first randi? ", u1.randi() == u2.randi(), " default seed1=", u1.seed, " seed2=", u2.seed)
	# global unseeded between runs: print first randi w/o seed
	print("global unseeded randi (varies per run?): ", randi())
	print("randomize() not called; seed state of global is process-random? done")
	# seed(str hash) cross check
	print("hash('abc')=", "abc".hash(), " hash(Vector2(1,2))=", hash(Vector2(1,2)), " hash(1.0)=", hash(1.0))
	# Dictionary iteration order
	var d := {"b":1,"a":2,"c":3}
	print("dict keys insertion order: ", d.keys())
	# RandomPCG known
	var pcg := RandomNumberGenerator.new()
	pcg.seed = 0
	print("seed 0 randi: ", pcg.randi(), " state ", pcg.state)

# ---------- physics ----------
func build_phys() -> void:
	var dim: String = args.get("dim", "3")
	Engine.physics_ticks_per_second = int(args.get("tps", "60"))
	Engine.max_physics_steps_per_frame = int(args.get("maxsteps", "8"))
	if dim == "3":
		var floor := StaticBody3D.new()
		var fs := CollisionShape3D.new(); var bs := BoxShape3D.new(); bs.size = Vector3(100,1,100)
		fs.shape = bs; floor.add_child(fs); floor.position = Vector3(0,-0.5,0); add_child(floor)
		var slope := StaticBody3D.new()
		var ss := CollisionShape3D.new(); var sb := BoxShape3D.new(); sb.size = Vector3(10,0.5,10); ss.shape = sb
		slope.add_child(ss); slope.position = Vector3(3,1,0); slope.rotation = Vector3(0,0,0.3); add_child(slope)
		var rng := RandomNumberGenerator.new(); rng.seed = 42
		for i in int(args.get("n","40")):
			var rb := RigidBody3D.new()
			var cs := CollisionShape3D.new()
			var sh: Shape3D
			match i % 3:
				0: sh = SphereShape3D.new()
				1: sh = BoxShape3D.new()
				2: sh = CapsuleShape3D.new()
			cs.shape = sh; rb.add_child(cs)
			rb.position = Vector3(rng.randf_range(-2,2) + float(i/50)*1.7, 2.0 + (i%50)*0.9,  rng.randf_range(-2,2))
			rb.rotation = Vector3(rng.randf(), rng.randf(), rng.randf())
			rb.linear_velocity = Vector3(rng.randf_range(-1,1),0,rng.randf_range(-1,1))
			add_child(rb); bodies3.append(rb)
		for i in 4:
			var cb := CharacterBody3D.new()
			var cs := CollisionShape3D.new(); var cap := CapsuleShape3D.new(); cs.shape = cap; cb.add_child(cs)
			cb.position = Vector3(i*1.5 - 2, 3, 0.5)
			cb.set_meta("vel", Vector3(1.5, 0, 0.7))
			add_child(cb); chars3.append(cb)
	else:
		var floor := StaticBody2D.new()
		var fs := CollisionShape2D.new(); var r := RectangleShape2D.new(); r.size = Vector2(2000,40)
		fs.shape = r; floor.add_child(fs); floor.position = Vector2(0,500); add_child(floor)
		var rng := RandomNumberGenerator.new(); rng.seed = 42
		for i in 40:
			var rb := RigidBody2D.new(); var cs := CollisionShape2D.new()
			if i%2==0:
				var c := CircleShape2D.new(); c.radius = 12; cs.shape = c
			else:
				var rr := RectangleShape2D.new(); rr.size = Vector2(24,24); cs.shape = rr
			rb.add_child(cs); rb.position = Vector2(rng.randf_range(-100,100), 400 - i*30); rb.rotation = rng.randf()
			add_child(rb); bodies2.append(rb)
		for i in 4:
			var cb := CharacterBody2D.new(); var cs := CollisionShape2D.new(); var c := CapsuleShape2D.new(); cs.shape = c; cb.add_child(cs)
			cb.position = Vector2(i*50-100, 300); cb.set_meta("vel", Vector2(60,0))
			add_child(cb); chars2.append(cb)

func _physics_process(delta: float) -> void:
	var mode: String = args.get("mode", "phys")
	pdelta_n += 1
	pdelta_sum += delta
	pdelta_min = min(pdelta_min, delta); pdelta_max = max(pdelta_max, delta)
	pcount_per_frame[Engine.get_process_frames()] = pcount_per_frame.get(Engine.get_process_frames(), 0) + 1
	if mode == "phys":
		for cb in chars3:
			var v: Vector3 = cb.velocity
			v.y -= 9.8 * delta
			v.x = cb.get_meta("vel").x; v.z = cb.get_meta("vel").z
			cb.velocity = v
			cb.move_and_slide()
		for cb in chars2:
			var v: Vector2 = cb.velocity
			v.y += 980 * delta
			v.x = cb.get_meta("vel").x
			cb.velocity = v
			cb.move_and_slide()
	ticks += 1
	if mode == "phys" and ticks >= target:
		report_phys(); get_tree().quit()
	if mode == "time" and ticks >= target:
		report_time(); get_tree().quit()
	if mode == "anim" and ticks >= target:
		_process_anim_report(); get_tree().quit()

func _process(delta: float) -> void:
	frames += 1
	procdeltas.append(delta)

func fmt(v) -> String:
	if v is Vector3: return "%.9f,%.9f,%.9f" % [v.x,v.y,v.z]
	if v is Vector2: return "%.9f,%.9f" % [v.x,v.y]
	return str(v)

func report_phys() -> void:
	var all := PackedFloat64Array()
	for b in bodies3 + chars3 + bodies2 + chars2:
		var p = b.global_position
		all.append(p.x); all.append(p.y)
		if p is Vector3: all.append(p.z)
		if b is RigidBody3D or b is RigidBody2D:
			var lv = b.linear_velocity
			all.append(lv.x); all.append(lv.y)
			if lv is Vector3: all.append(lv.z)
	var s := all.to_byte_array().hex_encode()
	var sample := fmt((bodies3 + bodies2)[0].global_position) if (bodies3 + bodies2).size() > 0 else ""
	var csample := fmt((chars3 + chars2)[0].global_position)
	print("RESULT engine=", ProjectSettings.get_setting("physics/3d/physics_engine"), " dim=", args.get("dim","3"), " ticks=", ticks,
		" hash=", s.hash(), " sha=", s.sha256_text().substr(0,16), " rb0=", sample, " ch0=", csample, " frames=", frames)

func build_time() -> void:
	Engine.physics_ticks_per_second = int(args.get("tps","60"))
	if args.has("ts"): Engine.time_scale = float(args["ts"])
	if args.has("interp"): ProjectSettings.set_setting("physics/common/physics_interpolation", true)

func report_time() -> void:
	var ps := 0.0; var pmn := 1e9; var pmx := 0.0
	for d in procdeltas: ps += d; pmn = min(pmn,d); pmx = max(pmx,d)
	var mx_per := 0
	for k in pcount_per_frame: mx_per = max(mx_per, pcount_per_frame[k])
	print("TIME tps=", Engine.physics_ticks_per_second, " ts=", Engine.time_scale, " physics: n=", pdelta_n, " min=", pdelta_min, " max=", pdelta_max, " sum=", pdelta_sum,
		" | process: n=", procdeltas.size(), " min=", pmn, " max=", pmx, " sum=", ps, " | max phys ticks per frame=", mx_per,
		" | first5 proc=", procdeltas.slice(0,5), " | ticks_msec=", Time.get_ticks_msec())

# ---------- anim/tween/timer ----------
var timer_p: Timer; var timer_i: Timer
var log_tw := {}
var tween_p: Tween; var tween_i: Tween
var obj_p := Node2D.new(); var obj_i := Node2D.new()
var ap: AnimationPlayer; var ap_phys: AnimationPlayer
var anim_node_i := Node2D.new(); var anim_node_p := Node2D.new()
var timer_fires := {"proc":[], "phys":[]}
func build_anim() -> void:
	Engine.physics_ticks_per_second = int(args.get("tps","60"))
	add_child(obj_p); add_child(obj_i); add_child(anim_node_i); add_child(anim_node_p)
	tween_p = create_tween().set_process_mode(Tween.TWEEN_PROCESS_PHYSICS)
	tween_p.tween_property(obj_p, "position:x", 100.0, 1.0)
	tween_i = create_tween().set_process_mode(Tween.TWEEN_PROCESS_IDLE)
	tween_i.tween_property(obj_i, "position:x", 100.0, 1.0)
	timer_p = Timer.new(); timer_p.wait_time = 0.1; timer_p.process_callback = Timer.TIMER_PROCESS_PHYSICS; add_child(timer_p)
	timer_i = Timer.new(); timer_i.wait_time = 0.1; timer_i.process_callback = Timer.TIMER_PROCESS_IDLE; add_child(timer_i)
	timer_p.timeout.connect(func(): timer_fires.phys.append(Engine.get_physics_frames()))
	timer_i.timeout.connect(func(): timer_fires.proc.append(Engine.get_physics_frames()))
	timer_p.start(); timer_i.start()
	var lib := AnimationLibrary.new()
	var an := Animation.new(); an.length = 1.0
	var t := an.add_track(Animation.TYPE_VALUE); an.track_set_path(t, ".:position:x")
	an.track_insert_key(t, 0.0, 0.0); an.track_insert_key(t, 1.0, 100.0)
	lib.add_animation("go", an)
	ap = AnimationPlayer.new(); anim_node_i.add_child(ap); ap.add_animation_library("", lib)
	ap.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_IDLE
	ap.root_node = ap.get_path_to(anim_node_i)
	ap_phys = AnimationPlayer.new(); anim_node_p.add_child(ap_phys); ap_phys.add_animation_library("", lib.duplicate())
	ap_phys.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_PHYSICS
	ap_phys.root_node = ap_phys.get_path_to(anim_node_p)
	ap.play("go"); ap_phys.play("go")

func _process_anim_report() -> void:
	print("ANIM tween_phys x=", obj_p.position.x, " tween_idle x=", obj_i.position.x, " anim_idle x=", anim_node_i.position.x, " anim_phys x=", anim_node_p.position.x,
		" physframes=", Engine.get_physics_frames(), " procframes=", Engine.get_process_frames())
	print("  timer phys-mode fires(physframe)=", timer_fires.phys.slice(0,12), " count=", timer_fires.phys.size())
	print("  timer idle-mode fires(physframe)=", timer_fires.proc.slice(0,12), " count=", timer_fires.proc.size())

func _notification(what: int) -> void:
	pass
