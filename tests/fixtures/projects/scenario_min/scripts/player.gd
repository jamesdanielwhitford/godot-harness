extends CharacterBody2D
## scenario_min player. The `# HOOK-*` lines are the exact edit points of the FAULT-A5-* entries.

const GRAVITY := 980.0
const JUMP_SPEED := -400.0
const RUN_SPEED := 200.0

var input_events := 0
var tw_x := 0.0
var own_rng := RandomNumberGenerator.new()
var _jumped := false
var _was_on_floor := false


func _ready() -> void:
	Harness.register("player", self)
	CommandBus.handle("teleport", _on_teleport)
	pass # HOOK-READY


func _on_teleport(cmd: Dictionary) -> Array:
	var v: Dictionary = cmd.get("value", {})
	position = Vector2(float(v.get("x", position.x)), float(v.get("y", position.y)))
	return [{"type": "teleported"}]


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("jump"):
		input_events += 1


func _process(delta: float) -> void:
	pass # HOOK-PROCESS


func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity.y += GRAVITY * delta
	var just_pressed := Input.is_action_just_pressed("jump")
	if just_pressed and is_on_floor():
		velocity.y = JUMP_SPEED
		_jumped = true
	velocity.x = RUN_SPEED * (Input.get_action_strength("right") - Input.get_action_strength("left"))
	move_and_slide()
	if just_pressed:
		Harness.event("jump_pressed", {"just": true, "pressed": Input.is_action_pressed("jump")})
	if Input.is_action_just_released("jump"):
		Harness.event("jump_released", {})
	var on_floor := is_on_floor()
	if on_floor and not _was_on_floor and _jumped:
		_jumped = false
		Harness.event("landed", {})
	_was_on_floor = on_floor
	pass # HOOK-PHYS


func _harness_state() -> Dictionary:
	var extra := {} # HOOK-STATE
	var s := {
		"position": position,
		"velocity": velocity,
		"on_floor": is_on_floor(),
		"input_events": input_events,
		"tw_x": tw_x,
	}
	s.merge(extra, true)
	return s
