extends CharacterBody2D

signal hit

const SPEED: float = 200.0
const JUMP_VELOCITY: float = -300.0


func _ready() -> void:
	var tw: Tween = create_tween().set_process_mode(Tween.TWEEN_PROCESS_PHYSICS)
	tw.tween_property(self, "modulate:a", 1.0, 0.2)


func _physics_process(_delta: float) -> void:
	var dir: float = Input.get_axis("move_left", "move_right")
	velocity.x = dir * SPEED
	if Input.is_action_just_pressed("jump"):
		velocity.y = JUMP_VELOCITY
	move_and_slide()


func take_hit() -> void:
	hit.emit()
