extends RefCounted

var next_id: int = 0
var positions: Dictionary = {}
var rng: RandomNumberGenerator


func _init(r: RandomNumberGenerator) -> void:
	rng = r


func spawn() -> int:
	next_id += 1
	positions[next_id] = Vector2(rng.randf(), rng.randf())
	return next_id
