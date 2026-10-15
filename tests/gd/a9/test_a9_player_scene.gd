extends GdUnitTestSuite
## A9 gdUnit4 suite (AC-09.18): the player scene reacts to the named actions move_right and jump.

const SCENE := "res://scenes/platformer/platformer_game.tscn"


func _find_player(n: Node) -> Node:
	if n is Player:
		return n
	for c in n.get_children():
		var p := _find_player(c)
		if p != null:
			return p
	return null


## Boots the game scene and waits for SceneManager to spawn the player (after the first fade), then lets it land.
func _boot() -> Array:
	var runner := scene_runner(SCENE)
	await runner.simulate_frames(40)
	var player := _find_player(runner.scene())
	var tries := 0
	while player == null and tries < 60:
		await runner.simulate_frames(10)
		player = _find_player(runner.scene())
		tries += 1
	assert_object(player).override_failure_message("no Player spawned after %d extra frames" % (tries * 10)).is_not_null()
	await runner.simulate_frames(30)
	return [runner, player]


func test_ac_09_18_move_right_moves_the_player() -> void:
	var b := await _boot()
	var runner: GdUnitSceneRunner = b[0]
	var player: Node2D = b[1]
	var x0 := player.global_position.x
	runner.simulate_action_press("move_right")
	await runner.simulate_frames(40)
	runner.simulate_action_release("move_right")
	assert_bool(player.global_position.x - x0 > 100.0).override_failure_message("moved %.1f px" % (player.global_position.x - x0)).is_true()


func test_ac_09_18_jump_action_counts_one_jump() -> void:
	var b := await _boot()
	var runner: GdUnitSceneRunner = b[0]
	var player: Node = b[1]
	assert_int(int(player._harness_state()["jumps"])).is_equal(0)
	runner.simulate_action_press("jump")
	await runner.simulate_frames(6)
	runner.simulate_action_release("jump")
	await runner.simulate_frames(60)
	assert_int(int(player._harness_state()["jumps"])).is_equal(1)
