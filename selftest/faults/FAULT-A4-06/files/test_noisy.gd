extends GdUnitTestSuite

func test_noisy_runs() -> void:
	assert_int(Noisy.new().run()).is_equal(1)
