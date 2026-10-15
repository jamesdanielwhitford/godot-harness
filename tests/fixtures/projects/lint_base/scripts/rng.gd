extends Node

var _rng := RandomNumberGenerator.new()


func reseed(s: int) -> void:
	seed(s)
	_rng.seed = s


func roll() -> int:
	return randi_range(1, 6)
