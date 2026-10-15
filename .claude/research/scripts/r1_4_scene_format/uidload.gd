extends SceneTree
func _init() -> void:
	var r = load("uid://b2q28pmmagj7y")
	print("uid load: ", r, " path=", ResourceUID.ensure_path("uid://b2q28pmmagj7y"))
	quit()
