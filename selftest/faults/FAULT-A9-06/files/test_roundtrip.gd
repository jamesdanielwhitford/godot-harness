extends GdUnitTestSuite
## FAULT-A9-06: loading is type-strict; the stats dictionary comes back with int values and the text is equal.


func test_round_trip_keeps_int_stats() -> void:
	var w := TacticsWorld.create(42)
	TacticsRules.new().apply(w, {"type": "autoplay", "value": 300})
	var text := SimSnapshot.to_text(w)
	var loaded := TacticsWorld.new()
	assert_int(SimSnapshot.from_text(text, loaded)).is_equal(OK)
	for k in loaded.stats.keys():
		assert_int(typeof(loaded.stats[k])).is_equal(TYPE_INT)
	assert_str(SimSnapshot.to_text(loaded)).is_equal(text)
