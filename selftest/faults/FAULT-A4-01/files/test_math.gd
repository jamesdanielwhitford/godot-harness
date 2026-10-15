extends GdUnitTestSuite
func test_ok() -> void:
	assert_int(1).is_equal(1)
func test_bad() -> void:
	var x := 2
	assert_int(x).is_equal(3)
func test_bad_str() -> void:
	assert_str("hello\nworld").is_equal("hello world")
