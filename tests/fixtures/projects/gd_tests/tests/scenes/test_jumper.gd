extends GdUnitTestSuite


func test_jump_counts_once() -> void:
	var runner := scene_runner("res://scenes/jumper.tscn")
	runner.simulate_action_press("jump")
	await runner.simulate_frames(2)
	runner.simulate_action_release("jump")
	await runner.simulate_frames(2)
	assert_int(runner.get_property("jumps")).is_equal(1)
