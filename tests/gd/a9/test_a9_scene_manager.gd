extends GdUnitTestSuite
## A9 gdUnit4 suite (AC-09.17): SceneManager never drops a request (rp_1 trap P10/D7).

const A := "res://scenes/platformer/level_1.tscn"
const B := "res://scenes/platformer/level_2.tscn"
const C := "res://scenes/tactics/unit_view.tscn"

var _slot: Node
var _finished: Array = []
var _cb: Callable


func _wait_idle(max_frames: int = 900) -> void:
	var n := 0
	while SceneManager.is_busy() and n < max_frames:
		await get_tree().physics_frame
		n += 1


func before_test() -> void:
	await _wait_idle()
	_slot = Node.new()
	add_child(_slot)
	SceneManager.set_slot(_slot)
	_finished = []
	_cb = func(p: String) -> void: _finished.append(p)
	SceneManager.transition_finished.connect(_cb)


func after_test() -> void:
	await _wait_idle()
	if SceneManager.transition_finished.is_connected(_cb):
		SceneManager.transition_finished.disconnect(_cb)
	_slot.queue_free()


func test_ac_09_17_idle_goto_starts_immediately() -> void:
	SceneManager.goto(A)
	assert_bool(SceneManager.is_busy()).is_true()
	assert_str(SceneManager.pending_path()).is_equal("")
	await _wait_idle()
	assert_bool(SceneManager.is_busy()).is_false()
	assert_str(SceneManager.current_path()).is_equal(A)
	assert_int(_slot.get_child_count()).is_equal(1)
	assert_array(_finished).is_equal([A])


func test_ac_09_17_requests_during_a_transition_are_kept_latest_wins() -> void:
	var base: int = SceneManager.stats()["completed"]
	SceneManager.goto(A)
	for i in 3:
		await get_tree().physics_frame
	SceneManager.goto(B)
	assert_bool(SceneManager.is_busy()).is_true()
	assert_str(SceneManager.pending_path()).is_equal(B)
	for i in 2:
		await get_tree().physics_frame
	SceneManager.goto(C)
	assert_str(SceneManager.pending_path()).is_equal(C)
	await _wait_idle()
	assert_str(SceneManager.current_path()).is_equal(C)
	assert_int(int(SceneManager.stats()["completed"]) - base).is_equal(2)
	assert_int(int(SceneManager.stats()["dropped"])).is_equal(0)
	assert_array(_finished).is_equal([A, C])  # one transition_finished per completed path, B superseded
	assert_int(_slot.get_child_count()).is_equal(1)
	assert_str(SceneManager.pending_path()).is_equal("")


func test_ac_09_17_stats_shape() -> void:
	var s: Dictionary = SceneManager.stats()
	for k in ["requests", "completed", "dropped", "busy"]:
		assert_bool(s.has(k)).override_failure_message("stats() lacks '%s'" % k).is_true()
	assert_int(int(s["dropped"])).is_equal(0)
