extends CharacterBody2D

const MAX_SPEED := 220.0
const ACCEL := 220.0 * 10.0
const DECEL := 220.0 * 10.0
const JUMP_SPEED := 400.0
const RISE_GRAVITY := 980.0
const FALL_GRAVITY := 1960.0 # FEEL-FALL
const JUMP_CUT := true # FEEL-CUT
const COYOTE_S := 0.1 # FEEL-COYOTE
const BUFFER_S := 0.1 # FEEL-BUFFER
const COYOTE_IN_TICKS := false # FEEL-COYOTE-TICKS
const CAM_SMOOTH := true # FEEL-CAM
const CAM_PHYSICS := true # FEEL-CAM-PROC

var coyote_t := 0.0
var coyote_n := 0
var buffer_t := 0.0


func _ready() -> void:
	var cam := get_node("Camera") as Camera2D
	cam.position_smoothing_enabled = CAM_SMOOTH
	cam.position_smoothing_speed = 5.0
	if CAM_PHYSICS:
		cam.process_callback = Camera2D.CAMERA2D_PROCESS_PHYSICS
	else:
		cam.process_callback = Camera2D.CAMERA2D_PROCESS_IDLE
	cam.make_current()


func _physics_process(delta: float) -> void:
	var on_floor := is_on_floor()
	var dir := Input.get_axis("left", "right")
	if dir != 0.0:
		velocity.x = move_toward(velocity.x, dir * MAX_SPEED, ACCEL * delta) # FEEL-ACCEL
	else:
		velocity.x = move_toward(velocity.x, 0.0, DECEL * delta)

	# gravity is always applied; move_and_slide removes vy against the floor
	velocity.y += (RISE_GRAVITY if velocity.y < 0.0 else FALL_GRAVITY) * delta
	if JUMP_CUT and velocity.y < -100.0 and not Input.is_action_pressed("jump"):
		velocity.y = -100.0

	if on_floor:
		coyote_t = COYOTE_S
		coyote_n = 6
	else:
		coyote_t -= delta
		coyote_n -= 1
	var can_coyote := coyote_t > 0.0
	if COYOTE_IN_TICKS:
		can_coyote = coyote_n > 0

	var pressed := Input.is_action_just_pressed("jump")
	if pressed:
		buffer_t = BUFFER_S
	var want_jump := pressed or buffer_t > 0.0
	buffer_t -= delta

	if want_jump and (on_floor or can_coyote):
		velocity.y = -JUMP_SPEED
		coyote_t = 0.0
		coyote_n = 0
		buffer_t = 0.0

	move_and_slide()

	if is_on_floor():
		Trace.mark("state", "ground")
	elif velocity.y < 0.0:
		Trace.mark("state", "rise")
	else:
		Trace.mark("state", "fall")
