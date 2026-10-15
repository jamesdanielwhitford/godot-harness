extends Node2D

var target: Object = null

func _physics_process(_delta: float) -> void:
	target.call("foo")
