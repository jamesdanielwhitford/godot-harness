extends Node2D
var t := 0.0
var cl: CanvasLayer
var spr: ColorRect
var parts: CPUParticles2D
var mode := "static"
func _ready():
	var args = OS.get_cmdline_user_args()
	var out = "/tmp/out"
	var n = 1
	for a in args:
		if a.begins_with("--out="): out = a.substr(6)
		if a.begins_with("--mode="): mode = a.substr(7)
		if a.begins_with("--n="): n = int(a.substr(4))
	var bg = ColorRect.new(); bg.color = Color(0.1,0.2,0.4); bg.size = Vector2(320,240); add_child(bg)
	spr = ColorRect.new(); spr.color = Color.ORANGE; spr.size = Vector2(40,40); spr.position = Vector2(20,100); add_child(spr)
	cl = CanvasLayer.new(); cl.name="HUD"; add_child(cl)
	var l = Label.new(); l.text = "HUD 123"; l.position = Vector2(10,10); cl.add_child(l)
	if mode == "anim" or mode == "particles":
		parts = CPUParticles2D.new(); parts.position = Vector2(160,120); parts.amount = 50; parts.emitting = true; parts.explosiveness=0.0; parts.visible = mode.begins_with("particles"); if mode=="particles_seed": parts.use_fixed_seed = true; parts.seed = 7; parts.initial_velocity_min=30; parts.initial_velocity_max=60; parts.spread=180; add_child(parts)
	if mode == "3d" or mode == "3dtaa":
		var vp = get_viewport()
		if mode == "3dtaa": vp.use_taa = true
		var cam = Camera3D.new(); cam.position = Vector3(0,1,3); add_child(cam)
		var mi = MeshInstance3D.new(); mi.mesh = BoxMesh.new(); mi.name="Cube"; add_child(mi)
		var lt = DirectionalLight3D.new(); lt.rotation_degrees = Vector3(-45,30,0); add_child(lt)
		cam.look_at(Vector3.ZERO)
	if n == 0: return
	var t0 = Time.get_ticks_usec()
	for i in n:
		if mode != "static": spr.position.x += 5
		if mode.begins_with("3d"): get_node("Cube").rotate_y(0.2)
		await RenderingServer.frame_post_draw
		var t1 = Time.get_ticks_usec()
		get_viewport().get_texture().get_image().save_png("%s/f%03d.png" % [out, i])
		print("cap ", i, " ms=", (Time.get_ticks_usec()-t1)/1000.0)
		if i == 0 and mode=="layers":
			cl.visible = false
			await RenderingServer.frame_post_draw
			get_viewport().get_texture().get_image().save_png("%s/nohud.png" % out)
			var img = get_viewport().get_texture().get_image()
			img.get_region(Rect2i(10,90,100,60)).save_png("%s/crop.png" % out)
	print("total ms=", (Time.get_ticks_usec()-t0)/1000.0, " renderer=", RenderingServer.get_video_adapter_name(), " api=", RenderingServer.get_video_adapter_api_version())
	get_tree().quit()
func _process(_d):
	if mode.begins_with("particles") or mode == "move" or mode=="3d":
		if spr: spr.position.x += 2
		if mode=="3d" and has_node("Cube"): get_node("Cube").rotate_y(0.1)
