extends GdUnitTestSuite
## AC-07.22: the Trace autoload is dormant unless --trace=<spec> is in the user args. Owner: T7.


func _trace() -> Node:
	return Engine.get_main_loop().root.get_node_or_null("Trace")


func test_trace_autoload_is_present() -> void:
	assert_object(_trace()).is_not_null()


func test_dormant_without_trace_user_arg() -> void:
	var t = _trace()
	assert_bool(t.is_active()).is_false()


func test_mark_is_a_noop_when_dormant() -> void:
	var t = _trace()
	t.mark("state", "fall")
	t.mark("undeclared_channel", 3)
	assert_bool(t.is_active()).is_false()


func test_dormant_trace_writes_no_csv_file() -> void:
	var t = _trace()
	t.mark("state", "ground")
	await get_tree().physics_frame
	await get_tree().physics_frame
	for root in ["user://", "res://"]:
		for f in DirAccess.get_files_at(root):
			assert_bool(f.ends_with(".csv") and f.begins_with("trace")).is_false()
