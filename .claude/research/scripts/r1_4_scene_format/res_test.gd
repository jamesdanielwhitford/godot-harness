extends SceneTree
func _init() -> void:
	var r := ItemData.new(); r.title = "Sword"; r.cost = 5; r.tags = ["a", "b"] as Array[String]; r.stats = {"atk": 3}
	print("save small: ", error_string(ResourceSaver.save(r, "res://cases/item_small.tres")))
	r.blob = PackedByteArray(); r.blob.resize(100)
	print("save blob100: ", error_string(ResourceSaver.save(r, "res://cases/item_blob.tres")))
	# UID assignment from script
	var ps: PackedScene = load("res://scenes/child.tscn")
	var id := ResourceUID.create_id_for_path("res://scenes/child.tscn")
	print("set_uid: ", error_string(ResourceSaver.set_uid("res://scenes/child.tscn", id)), " ", ResourceUID.id_to_text(id))
	quit()
