extends GdUnitTestSuite
## FAULT-A9-03: a snapshot carries its schema version and loads back into a fresh world.


func test_snapshot_has_version_and_round_trips() -> void:
	var w := TacticsWorld.create(7)
	var text := SimSnapshot.to_text(w)
	var d: Dictionary = JSON.parse_string(text)
	assert_bool(d.has("version")).is_true()
	assert_int(int(d["version"])).is_equal(1)
	var loaded := TacticsWorld.new()
	assert_int(SimSnapshot.from_text(text, loaded)).is_equal(OK)
	assert_str(loaded.state_hash()).is_equal(w.state_hash())
