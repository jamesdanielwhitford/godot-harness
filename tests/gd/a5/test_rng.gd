extends GdUnitTestSuite
## AC-05.25 (spec 05_scenario.md 2.3 `Rng`): per-name streams, derivation, save/restore, shuffle, pick.


func _expected_seed(root_seed: int, stream_name: String) -> int:
	return ("%d:%s" % [root_seed, stream_name]).sha256_buffer().decode_s64(0)


func test_ac_05_25_1_stream_independent_of_creation_order() -> void:
	Rng.seed_all(7)
	var first_a := Rng.stream(&"a").randi()
	Rng.seed_all(7)
	var other := Rng.stream(&"b")
	other.randi()
	var second_a := Rng.stream(&"a").randi()
	assert_int(second_a).is_equal(first_a)


func test_ac_05_25_2_stream_seed_derivation() -> void:
	Rng.seed_all(7)
	# [Run S6] "7:default".sha256_buffer().decode_s64(0)
	assert_int(Rng.stream(&"default").seed).is_equal(7278379237195912242)
	assert_int(Rng.stream(&"a").seed).is_equal(_expected_seed(7, "a"))
	assert_int(Rng.get_seed()).is_equal(7)


func test_ac_05_25_3_same_object_until_seed_all() -> void:
	Rng.seed_all(7)
	var s1 := Rng.stream(&"same")
	assert_bool(Rng.stream(&"same") == s1).is_true()
	Rng.seed_all(7)
	var s2 := Rng.stream(&"same")
	# reset: a fresh stream again produces the sequence from the start
	var ref := RandomNumberGenerator.new()
	ref.seed = _expected_seed(7, "same")
	assert_int(s2.randi()).is_equal(ref.randi())


func test_ac_05_25_4_default_stream_helpers() -> void:
	Rng.seed_all(11)
	var ref := RandomNumberGenerator.new()
	ref.seed = _expected_seed(11, "default")
	assert_int(Rng.randi_range(1, 6)).is_equal(ref.randi_range(1, 6))
	assert_float(Rng.randf()).is_equal(ref.randf())
	assert_float(Rng.randf_range(2.0, 3.0)).is_equal(ref.randf_range(2.0, 3.0))


func test_ac_05_25_5_save_restore_continues_identically() -> void:
	Rng.seed_all(9)
	Rng.stream(&"x").randi()
	Rng.stream(&"x").randi()
	Rng.randi_range(1, 100)
	var saved := Rng.save()
	assert_int(int(saved["seed"])).is_equal(9)
	assert_bool(saved.has("streams")).is_true()
	var names: Array = []
	for k in saved["streams"].keys():
		names.append(str(k))
	assert_array(names).contains(["x"])
	var run1 := [Rng.stream(&"x").randi(), Rng.stream(&"x").randi(), Rng.randi_range(1, 100)]
	Rng.restore(saved)
	var run2 := [Rng.stream(&"x").randi(), Rng.stream(&"x").randi(), Rng.randi_range(1, 100)]
	assert_array(run2).is_equal(run1)


func test_ac_05_25_6_shuffle_is_fisher_yates() -> void:
	Rng.seed_all(21)
	var arr: Array = range(1, 11)
	Rng.shuffle(arr, &"sh")
	var ref := RandomNumberGenerator.new()
	ref.seed = _expected_seed(21, "sh")
	var expected: Array = range(1, 11)
	for i in range(expected.size() - 1, 0, -1):
		var j := ref.randi_range(0, i)
		var tmp = expected[i]
		expected[i] = expected[j]
		expected[j] = tmp
	assert_array(arr).is_equal(expected)


func test_ac_05_25_7_pick() -> void:
	Rng.seed_all(5)
	assert_that(Rng.pick([])).is_null()
	var items := ["a", "b", "c", "d"]
	var ref := RandomNumberGenerator.new()
	ref.seed = _expected_seed(5, "pk")
	var idx := ref.randi_range(0, items.size() - 1)
	assert_str(Rng.pick(items, &"pk")).is_equal(items[idx])
