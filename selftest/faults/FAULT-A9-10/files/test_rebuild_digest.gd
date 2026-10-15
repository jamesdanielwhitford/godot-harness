extends GdUnitTestSuite
## FAULT-A9-10: after events and finish_animations() the live view equals a fresh rebuild from the world.


func test_live_view_equals_rebuild() -> void:
	var runner := scene_runner("res://scenes/tactics/tactics.tscn")
	var host := runner.scene().get_node("Host") as TacticsHost
	var view := runner.scene().get_node("View") as TacticsView
	host.submit({"type": "autoplay", "value": 30})
	view.finish_animations()
	var live := JSON.stringify(view.view_digest(), "", true, true)
	var fresh := TacticsView.new()
	add_child(auto_free(fresh))
	fresh.bind(host.world.clone())
	assert_str(JSON.stringify(fresh.view_digest(), "", true, true)).is_equal(live)
