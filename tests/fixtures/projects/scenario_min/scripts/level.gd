extends Node2D
## scenario_min level: builds floor, player, mover and dice in code.

const PlayerScript := preload("res://scripts/player.gd")
const MoverScript := preload("res://scripts/mover.gd")
const DiceScript := preload("res://scripts/dice.gd")


func _ready() -> void:
	var floor_body := StaticBody2D.new()
	floor_body.name = "Floor"
	floor_body.position = Vector2(0, 300)
	var floor_shape := CollisionShape2D.new()
	var floor_rect := RectangleShape2D.new()
	floor_rect.size = Vector2(4000, 40)
	floor_shape.shape = floor_rect
	floor_body.add_child(floor_shape)
	add_child(floor_body)

	var player := PlayerScript.new()
	player.name = "Player"
	player.position = Vector2(0, 200)
	var body_shape := CollisionShape2D.new()
	var capsule := CapsuleShape2D.new()
	capsule.radius = 10.0
	capsule.height = 40.0
	body_shape.shape = capsule
	player.add_child(body_shape)
	add_child(player)

	var mover := MoverScript.new()
	mover.name = "Mover"
	add_child(mover)

	var dice := DiceScript.new()
	dice.name = "Dice"
	add_child(dice)

	Harness.tick_completed.connect(_on_tick_completed)


func _on_tick_completed(_tick: int) -> void:
	Harness.metric("tick_signals", 1.0, "add")
