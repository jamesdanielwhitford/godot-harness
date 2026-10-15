extends CharacterBody2D
const SPEED = 300.0
const JUMP = -450.0
func _physics_process(delta):
	if not is_on_floor():
		velocity.y += 980.0 * delta
	if Input.is_action_just_pressed("jump") and is_on_floor():
		velocity.y = JUMP
	velocity.x = Input.get_axis("move_left", "move_right") * SPEED
	move_and_slide()
