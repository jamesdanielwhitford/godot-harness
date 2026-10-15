extends Node

const JUMP_KEY: int = KEY_SPACE


func is_jump_key(event: InputEventKey) -> bool:
	return event.keycode == JUMP_KEY
