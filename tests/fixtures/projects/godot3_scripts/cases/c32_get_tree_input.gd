extends Node
func _ready():
	Input.is_action_pressed("nope")
	print(Input.is_action_pressed("nope"))
