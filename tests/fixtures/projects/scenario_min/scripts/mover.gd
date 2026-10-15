extends Node
## Exact counter: after tick k, n == k and x == 1.5 * k.

var n := 0
var x := 0.0


func _ready() -> void:
	Harness.register("mover", self)


func _physics_process(_delta: float) -> void:
	n += 1
	x += 1.5


func _harness_state() -> Dictionary:
	return {"n": n, "x": x}
