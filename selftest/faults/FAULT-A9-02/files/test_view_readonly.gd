extends GdUnitTestSuite
## FAULT-A9-02: the view must never write to the world. Same commands with and without a view give one hash.


func test_view_never_mutates_the_world() -> void:
	var runner := scene_runner("res://scenes/tactics/tactics.tscn")
	var host := runner.scene().get_node("Host") as TacticsHost
	var start_text := SimSnapshot.to_text(host.world)
	host.submit({"type": "autoplay", "value": 60})
	var headless := TacticsWorld.new()
	assert_int(SimSnapshot.from_text(start_text, headless)).is_equal(OK)
	TacticsRules.new().apply(headless, {"type": "autoplay", "value": 60})
	assert_str(host.world.state_hash()).is_equal(headless.state_hash())
