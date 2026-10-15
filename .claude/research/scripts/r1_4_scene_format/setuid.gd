extends SceneTree
func _init() -> void:
	var p: String = OS.get_cmdline_user_args()[0]
	var id := ResourceUID.create_id_for_path(p)
	print("set_uid ", p, " ", error_string(ResourceSaver.set_uid(p, id)), " ", ResourceUID.id_to_text(id))
	quit()
