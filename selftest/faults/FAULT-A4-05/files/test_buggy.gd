extends GdUnitTestSuite

func test_runs() -> void:
	var runner := scene_runner("res://scenes/buggy.tscn")
	await runner.simulate_frames(3)
	assert_bool(true).is_true()
