extends GdUnitTestSuite
## A9 gdUnit4 suite (AC-09.14, AC-09.15): the view is read-only, rebuildable and snaps to the world.

const SCENE := "res://scenes/tactics/tactics.tscn"


func _digest(v: SimView) -> String:
	return JSON.stringify(v.view_digest(), "", true, true)


func test_ac_09_14_view_is_read_only() -> void:
	var runner := scene_runner(SCENE)
	var host := runner.scene().get_node("Host") as TacticsHost
	var view := runner.scene().get_node("View") as TacticsView
	var start_text := SimSnapshot.to_text(host.world)
	var evs := host.submit({"type": "autoplay", "value": 60})
	assert_bool(evs.size() > 0).is_true()
	view.finish_animations()
	# the same commands on a headless world (no view at all)
	var headless := TacticsWorld.new()
	assert_int(SimSnapshot.from_text(start_text, headless)).is_equal(OK)
	TacticsRules.new().apply(headless, {"type": "autoplay", "value": 60})
	assert_str(host.world.state_hash()).is_equal(headless.state_hash())
	assert_int(host.world.tick).is_equal(headless.tick)


func test_ac_09_14_second_view_of_a_clone_has_equal_digest() -> void:
	var runner := scene_runner(SCENE)
	var host := runner.scene().get_node("Host") as TacticsHost
	var view := runner.scene().get_node("View") as TacticsView
	host.submit({"type": "autoplay", "value": 60})
	view.finish_animations()
	var v2 := TacticsView.new()
	add_child(auto_free(v2))
	v2.bind(host.world.clone())
	v2.finish_animations()
	assert_str(_digest(v2)).is_equal(_digest(view))
	assert_bool(view.view_digest().size() > 0).is_true()


func test_ac_09_14_load_from_then_digest_equals_fresh_rebuild() -> void:
	var runner := scene_runner(SCENE)
	var host := runner.scene().get_node("Host") as TacticsHost
	var view := runner.scene().get_node("View") as TacticsView
	var path := "user://a9_view_save.json"
	assert_int(host.save_to(path)).is_equal(OK)
	var saved_hash := host.world.state_hash()
	host.submit({"type": "autoplay", "value": 40})
	view.finish_animations()
	assert_str(host.world.state_hash()).is_not_equal(saved_hash)
	assert_int(host.load_from(path)).is_equal(OK)
	view.finish_animations()
	assert_str(host.world.state_hash()).is_equal(saved_hash)
	var live := _digest(view)
	var fresh := TacticsView.new()
	add_child(auto_free(fresh))
	fresh.bind(host.world.clone())
	assert_str(_digest(fresh)).is_equal(live)
	view.rebuild()
	view.finish_animations()
	assert_str(_digest(view)).is_equal(live)
	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))


# ---------------------------------------------------------------- AC-09.15
func test_ac_09_15_snap_to_end_removes_view_of_silently_despawned_unit() -> void:
	var runner := scene_runner(SCENE)
	var host := runner.scene().get_node("Host") as TacticsHost
	var view := runner.scene().get_node("View") as TacticsView
	var victim: int = host.world.ids()[0]
	assert_object(view.view_of(victim)).is_not_null()
	assert_bool(host.world.despawn(victim)).is_true()  # no event emitted
	view.apply_events([])
	assert_object(view.view_of(victim)).is_null()
	assert_bool(view.view_digest().has("t%d" % victim)).is_false()
	assert_int(view.view_digest().size()).is_equal(host.world.ids().size())


func test_ac_09_15_snap_to_end_creates_view_of_silently_spawned_unit() -> void:
	var runner := scene_runner(SCENE)
	var host := runner.scene().get_node("Host") as TacticsHost
	var view := runner.scene().get_node("View") as TacticsView
	var before := view.view_digest().size()
	var u := Unit.new()
	u.kind = "unit"
	u.team = 0
	u.cell = Vector2i(1, 6)
	var id := host.world.spawn(u)
	view.apply_events([])
	assert_object(view.view_of(id)).is_not_null()
	assert_int(view.view_digest().size()).is_equal(before + 1)
