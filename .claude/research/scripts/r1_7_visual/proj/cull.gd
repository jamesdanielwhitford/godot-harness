extends Node3D
func _ready():
	var out = OS.get_cmdline_user_args()[0].substr(6)
	var cam = Camera3D.new(); cam.position = Vector3(0,0,5); add_child(cam)
	var a = MeshInstance3D.new(); a.mesh = BoxMesh.new(); a.position = Vector3(-1,0,0); a.layers = 1; add_child(a)
	var b = MeshInstance3D.new(); b.mesh = SphereMesh.new(); b.position = Vector3(1,0,0); b.layers = 2; add_child(b)
	var lt = DirectionalLight3D.new(); lt.rotation_degrees = Vector3(-30,20,0); add_child(lt)
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(out+"/all.png")
	cam.cull_mask = 1
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(out+"/layer1.png")
	cam.cull_mask = 2
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(out+"/layer2.png")
	get_tree().quit()
