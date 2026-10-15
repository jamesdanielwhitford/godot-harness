extends GdUnitTestSuite


func test_add() -> void:
	var c := Counter.new()
	assert_int(c.add(2)).is_equal(2)


func test_add_twice() -> void:
	var c := Counter.new()
	c.add(2)
	assert_int(c.add(3)).is_equal(5)


func test_table(a: int, b: int, expected: int, test_parameters := [[1, 2, 3], [2, 2, 4]]) -> void:
	assert_int(Counter.new().add(a) + b).is_equal(expected)
