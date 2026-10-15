extends Node
## Seeded RNG consumer: sum of d6 rolls from the Rng "dice" stream.

var sum := 0


func _ready() -> void:
	Harness.register("dice", self)


func _physics_process(_delta: float) -> void:
	sum += Rng.stream(&"dice").randi_range(1, 6)


func _harness_state() -> Dictionary:
	return {"sum": sum}
