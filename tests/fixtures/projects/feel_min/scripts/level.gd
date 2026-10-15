extends Node2D

@export var floor_end: float = 4000.0


func _ready() -> void:
	var floor_body := StaticBody2D.new()
	floor_body.name = "Floor"
	var floor_shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	var width := floor_end + 2000.0
	rect.size = Vector2(width, 20.0)
	floor_shape.shape = rect
	floor_body.position = Vector2(-2000.0 + width * 0.5, 310.0)
	floor_body.add_child(floor_shape)
	add_child(floor_body)

	var player := CharacterBody2D.new()
	player.name = "Player"
	player.position = Vector2(0.0, 284.0)
	var body_shape := CollisionShape2D.new()
	var body_rect := RectangleShape2D.new()
	body_rect.size = Vector2(16.0, 32.0)
	body_shape.shape = body_rect
	player.add_child(body_shape)
	var cam := Camera2D.new()
	cam.name = "Camera"
	player.add_child(cam)
	player.set_script(load("res://scripts/player.gd"))
	add_child(player)
