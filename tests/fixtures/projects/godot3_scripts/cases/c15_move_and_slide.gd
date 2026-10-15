extends CharacterBody2D
func _physics_process(d):
	velocity = move_and_slide(velocity, Vector2.UP)
