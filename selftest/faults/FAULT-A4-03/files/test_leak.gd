extends GdUnitTestSuite

func test_leaks_node() -> void:
	var n := Node.new()
	assert_object(n).is_not_null()
