extends SceneTree
# Reference capture for the shot_min baseline (A6 spec 3.2 steps 4-5, one shot, no harness code).
# Usage: xvfb-run -a godot --path <proj> --rendering-method gl_compatibility --audio-driver Dummy --fixed-fps 60
#        -s capture_ref.gd -- --scene=res://scenes/main.tscn --tick=30 --out=/abs/out.png
var _tick := 30
var _out := ""
var _base := 0
var _done := false
var _scene := "res://scenes/main.tscn"

func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--tick="):
			_tick = int(a.substr(7))
		elif a.begins_with("--out="):
			_out = a.substr(6)
		elif a.begins_with("--scene="):
			_scene = a.substr(8)
	seed(0)
	var inst: Node = (load(_scene) as PackedScene).instantiate()
	root.add_child(inst)
	current_scene = inst
	_base = Engine.get_physics_frames()

func _process(_d: float) -> bool:
	if _done:
		return false
	if Engine.get_physics_frames() - _base >= _tick:
		_done = true
		RenderingServer.frame_post_draw.connect(_save, CONNECT_ONE_SHOT)
	return false

func _save() -> void:
	var img := root.get_texture().get_image()
	img.save_png(_out)
	print("@@REF ", JSON.stringify({"w": img.get_width(), "h": img.get_height(),
		"renderer": str(ProjectSettings.get_setting("rendering/renderer/rendering_method")),
		"adapter": RenderingServer.get_video_adapter_name(),
		"api": RenderingServer.get_video_adapter_api_version(),
		"display": DisplayServer.get_name()}))
	quit(0)
