extends GdUnitTestSuite
## AC-07.22: FeelTargets save + load round-trip keeps every field. Owner: T7.

const TARGET := "res://addons/harness/feel_target.gd"
const TARGETS := "res://addons/harness/feel_targets.gd"
const PATH := "user://a7_roundtrip_targets.tres"


func _mk_target(metric: String, lo: float, hi: float, unit: String, by: String, on: String, note: String) -> Resource:
	var t: Resource = load(TARGET).new()
	t.metric = metric
	t.min_value = lo
	t.max_value = hi
	t.unit = unit
	t.approved_by = by
	t.approved_on = on
	t.note = note
	return t


func test_feel_targets_round_trip_keeps_all_fields() -> void:
	var ts: Resource = load(TARGETS).new()
	ts.tick_rate = 120
	ts.targets.append(_mk_target("jump.coyote_window", 4.0, 8.0, "ticks", "J. Whitford", "2026-10-01", "feel ok"))
	ts.targets.append(_mk_target("jump.apex_px", 70.0, 1e9, "px", "", "", ""))
	assert_int(ResourceSaver.save(ts, PATH)).is_equal(OK)

	var back: Resource = ResourceLoader.load(PATH, "", ResourceLoader.CACHE_MODE_IGNORE)
	assert_object(back).is_not_null()
	assert_int(back.tick_rate).is_equal(120)
	assert_int(back.targets.size()).is_equal(2)
	var a: Resource = back.targets[0]
	assert_str(a.metric).is_equal("jump.coyote_window")
	assert_float(a.min_value).is_equal(4.0)
	assert_float(a.max_value).is_equal(8.0)
	assert_str(a.unit).is_equal("ticks")
	assert_str(a.approved_by).is_equal("J. Whitford")
	assert_str(a.approved_on).is_equal("2026-10-01")
	assert_str(a.note).is_equal("feel ok")
	var b: Resource = back.targets[1]
	assert_str(b.metric).is_equal("jump.apex_px")
	assert_float(b.min_value).is_equal(70.0)
	assert_float(b.max_value).is_equal(1e9)
	assert_str(b.approved_by).is_equal("")
	DirAccess.remove_absolute(ProjectSettings.globalize_path(PATH))


func test_feel_target_defaults() -> void:
	var t: Resource = load(TARGET).new()
	assert_str(t.metric).is_equal("")
	assert_str(t.approved_by).is_equal("")
	var ts: Resource = load(TARGETS).new()
	assert_int(ts.tick_rate).is_equal(60)
	assert_int(ts.targets.size()).is_equal(0)
