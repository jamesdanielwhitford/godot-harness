extends Node2D

var jumps: int = 0


func _physics_process(_delta: float) -> void:
	if Input.is_action_just_pressed("jump"):
		jumps += 1
