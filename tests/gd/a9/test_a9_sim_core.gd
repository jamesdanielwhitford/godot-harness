extends GdUnitTestSuite
## A9 gdUnit4 suite (AC-09.8 .. AC-09.13). Runs inside a copy of sample/ at res://tests/a9/.
## Uses only the spec 2.2/2.6 API: TacticsWorld, TacticsRules, Unit, SimSnapshot, SimWorld.

var _rules := TacticsRules.new()


func _autoplay(w: TacticsWorld, n: int) -> Array:
	return _rules.apply(w, {"type": "autoplay", "value": n})


func _types(evs: Array) -> Array:
	var out := []
	for e in evs:
		out.append(e["type"])
	return out


func _first(evs: Array, type: String) -> Dictionary:
	for e in evs:
		if e["type"] == type:
			return e
	return {}


func _unit(w: TacticsWorld, id: int) -> Unit:
	return w.get_thing(id) as Unit


func _edit(text: String, edit: Callable) -> String:
	var d: Dictionary = JSON.parse_string(text)
	edit.call(d)
	return JSON.stringify(d, "\t", true, true) + "\n"


func _expect_reject(w: TacticsWorld, cmd: Dictionary, reason: String) -> void:
	var before := w.state_hash()
	var evs := _rules.apply(w, cmd)
	assert_int(evs.size()).override_failure_message("%s: want exactly one event" % reason).is_equal(1)
	assert_str(evs[0]["type"]).is_equal("rejected")
	assert_str(evs[0]["reason"]).is_equal(reason)
	assert_str(w.state_hash()).override_failure_message("%s: world changed" % reason).is_equal(before)


# ---------------------------------------------------------------- AC-09.8
func test_ac_09_8_autoplay_1000_ticks_and_seed_determinism() -> void:
	var a := TacticsWorld.create(42)
	var t0 := Time.get_ticks_msec()
	_autoplay(a, 1000)
	var ms := Time.get_ticks_msec() - t0
	assert_int(a.tick).is_equal(1000)
	assert_bool(ms <= 2000).override_failure_message("1000 turns took %d ms" % ms).is_true()
	var b := TacticsWorld.create(42)
	_autoplay(b, 1000)
	assert_str(b.state_hash()).is_equal(a.state_hash())
	var c := TacticsWorld.create(43)
	_autoplay(c, 1000)
	assert_str(c.state_hash()).is_not_equal(a.state_hash())


# ---------------------------------------------------------------- AC-09.9
func test_ac_09_9_split_run_equals_straight_run() -> void:
	var straight := TacticsWorld.create(42)
	_autoplay(straight, 1000)
	var first := TacticsWorld.create(42)
	_autoplay(first, 500)
	var text := SimSnapshot.to_text(first)
	var second := TacticsWorld.new()
	assert_int(SimSnapshot.from_text(text, second)).is_equal(OK)
	_autoplay(second, 500)
	assert_str(second.state_hash()).is_equal(straight.state_hash())
	assert_int(second.tick).is_equal(1000)


# ---------------------------------------------------------------- AC-09.10
func test_ac_09_10_text_round_trip_is_type_strict() -> void:
	var w := TacticsWorld.create(42)
	_autoplay(w, 300)
	var text := SimSnapshot.to_text(w)
	assert_bool(text.ends_with("\n")).is_true()
	var loaded := TacticsWorld.new()
	assert_int(SimSnapshot.from_text(text, loaded)).is_equal(OK)
	assert_str(SimSnapshot.to_text(loaded)).is_equal(text)
	for k in loaded.stats.keys():
		assert_int(typeof(loaded.stats[k])).override_failure_message("stats[%s] is not TYPE_INT" % k).is_equal(TYPE_INT)
	assert_int(typeof(loaded.tick)).is_equal(TYPE_INT)
	assert_int(loaded.rng.state).is_equal(w.rng.state)
	assert_int(loaded.rng.seed).is_equal(w.rng.seed)


func test_ac_09_10_file_round_trip_leaves_no_tmp() -> void:
	var path := "user://a9_rt.json"
	var w := TacticsWorld.create(42)
	_autoplay(w, 300)
	assert_int(SimSnapshot.save_file(w, path)).is_equal(OK)
	assert_bool(FileAccess.file_exists(path)).is_true()
	assert_bool(FileAccess.file_exists(path + ".tmp")).is_false()
	var loaded := TacticsWorld.new()
	assert_int(SimSnapshot.load_file(path, loaded)).is_equal(OK)
	assert_str(SimSnapshot.to_text(loaded)).is_equal(SimSnapshot.to_text(w))
	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))


func test_ac_09_10_export_snapshot_for_schema_check() -> void:
	# The pytest wrapper reads this file from the project copy and validates it against sim_snapshot.schema.json.
	var w := TacticsWorld.create(7)
	_autoplay(w, 300)
	var f := FileAccess.open("res://a9_snapshot_out.json", FileAccess.WRITE)
	assert_object(f).is_not_null()
	f.store_string(SimSnapshot.to_text(w))
	f.close()


# ---------------------------------------------------------------- AC-09.11
func test_ac_09_11_float_hp_is_rejected_and_target_unchanged() -> void:
	var text := SimSnapshot.to_text(TacticsWorld.create(7))
	var bad := _edit(text, func(d: Dictionary) -> void: d["things"]["t1"]["hp"] = 3.5)
	var target := TacticsWorld.create(8)
	_autoplay(target, 20)
	var before := target.state_hash()
	assert_int(SimSnapshot.from_text(bad, target)).is_equal(ERR_INVALID_DATA)
	assert_str(target.last_error).contains("hp")
	assert_str(target.state_hash()).is_equal(before)


func test_ac_09_11_missing_version_newer_version_other_schema() -> void:
	var text := SimSnapshot.to_text(TacticsWorld.create(7))
	var cases := {
		"missing version": _edit(text, func(d: Dictionary) -> void: d.erase("version")),
		"version 2": _edit(text, func(d: Dictionary) -> void: d["version"] = 2),
		"other schema": _edit(text, func(d: Dictionary) -> void: d["schema"] = "other"),
	}
	for label in cases.keys():
		var target := TacticsWorld.create(8)
		var before := target.state_hash()
		var err := SimSnapshot.from_text(cases[label], target)
		assert_int(err).override_failure_message("%s: want ERR_INVALID_DATA" % label).is_equal(ERR_INVALID_DATA)
		assert_str(target.state_hash()).override_failure_message("%s: target changed" % label).is_equal(before)


func test_ac_09_11_garbage_text_is_a_parse_error() -> void:
	var target := TacticsWorld.create(8)
	var before := target.state_hash()
	assert_int(SimSnapshot.from_text("{not json", target)).is_equal(ERR_PARSE_ERROR)
	assert_str(target.state_hash()).is_equal(before)


func test_ac_09_11_integral_float_loads_as_int() -> void:
	var original := SimSnapshot.to_text(TacticsWorld.create(7))
	var text := _edit(original, func(d: Dictionary) -> void: d["things"]["t1"]["hp"] = 3.0)
	var loaded := TacticsWorld.new()
	assert_int(SimSnapshot.from_text(text, loaded)).is_equal(OK)
	var u := _unit(loaded, 1)
	assert_int(u.hp).is_equal(3)
	assert_int(typeof(u.hp)).is_equal(TYPE_INT)
	# every other number (3.0 -> 3 style floats all over the text) also came back as int
	var want := TacticsWorld.create(7)
	_unit(want, 1).hp = 3
	assert_str(SimSnapshot.to_text(loaded)).is_equal(SimSnapshot.to_text(want))


# ---------------------------------------------------------------- AC-09.12
class V2World extends TacticsWorld:
	var migrated_from: int = -1

	func schema_version() -> int:
		return 2

	func migrate(d: Dictionary, from_version: int) -> Dictionary:
		migrated_from = from_version
		d["version"] = 2
		return d


func test_ac_09_12_migration_from_v1_text() -> void:
	var text := SimSnapshot.to_text(TacticsWorld.create(7))
	var w2 := V2World.new()
	assert_int(SimSnapshot.from_text(text, w2)).is_equal(OK)
	assert_int(w2.migrated_from).is_equal(1)
	assert_int(w2.to_dict()["version"]).is_equal(2)
	assert_int(w2.ids().size()).is_equal(6)


# ---------------------------------------------------------------- AC-09.13
func test_ac_09_13_move_rejections() -> void:
	var w := TacticsWorld.create(7)
	_expect_reject(w, {"type": "move", "target": "99", "value": [1, 1]}, "no_such_unit")
	_expect_reject(w, {"type": "move", "target": "4", "value": [6, 2]}, "not_your_turn")
	_expect_reject(w, {"type": "move", "target": "1", "value": [-1, 1]}, "out_of_bounds")
	_expect_reject(w, {"type": "move", "target": "1", "value": [0, 3]}, "blocked")  # occupied by unit 2
	_expect_reject(w, {"type": "move", "target": "2", "value": [3, 3]}, "blocked")  # blocked terrain, within range
	_expect_reject(w, {"type": "move", "target": "1", "value": [5, 1]}, "out_of_range")
	_expect_reject(w, {"type": "move", "target": "1", "value": "x"}, "bad_args")
	_expect_reject(w, {"type": "move", "target": "1"}, "bad_args")


func test_ac_09_13_already_acted_and_unknown_command() -> void:
	var w := TacticsWorld.create(7)
	var evs := _rules.apply(w, {"type": "move", "target": "1", "value": [1, 1]})
	assert_array(_types(evs)).contains(["unit_moved"])
	_expect_reject(w, {"type": "move", "target": "1", "value": [2, 1]}, "already_acted")
	_expect_reject(w, {"type": "attack", "target": "1", "value": 4}, "already_acted")
	_expect_reject(w, {"type": "no_such_command"}, "unknown_command")


func test_ac_09_13_attack_rejections() -> void:
	var w := TacticsWorld.create(7)
	_expect_reject(w, {"type": "attack", "target": "99", "value": 4}, "no_such_unit")
	_expect_reject(w, {"type": "attack", "target": "4", "value": 1}, "not_your_turn")
	_expect_reject(w, {"type": "attack", "target": "1", "value": 4}, "not_adjacent")
	_expect_reject(w, {"type": "attack", "target": "1", "value": "abc"}, "bad_args")
	# friendly fire: move unit 1 next to unit 2 (0,3), then unit 2 attacks it
	_rules.apply(w, {"type": "move", "target": "1", "value": [0, 2]})
	_expect_reject(w, {"type": "attack", "target": "2", "value": 1}, "friendly_fire")


func test_ac_09_13_legal_move_event_carries_end_state() -> void:
	var w := TacticsWorld.create(7)
	var evs := _rules.apply(w, {"type": "move", "target": "1", "value": [2, 1]})
	var e := _first(evs, "unit_moved")
	assert_bool(e.is_empty()).is_false()
	assert_int(int(e["id"])).is_equal(1)
	assert_array(e["to"]).is_equal([2, 1])
	assert_object(_unit(w, 1)).is_not_null()
	assert_that(_unit(w, 1).cell).is_equal(Vector2i(2, 1))


func test_ac_09_13_attack_damage_is_three_or_four() -> void:
	for s in [1, 2, 3, 4, 5, 6]:
		var w := TacticsWorld.create(s)
		_unit(w, 1).cell = Vector2i(6, 2)  # next to unit 4 at (7,2)
		var evs := _rules.apply(w, {"type": "attack", "target": "1", "value": 4})
		var att := _first(evs, "unit_attacked")
		assert_bool(att.is_empty()).is_false()
		var dmg := int(att["damage"])
		assert_bool(dmg == 3 or dmg == 4).override_failure_message("seed %d: damage %d" % [s, dmg]).is_true()
		var dm := _first(evs, "unit_damaged")
		assert_int(int(dm["hp"])).is_equal(10 - dmg)
		assert_int(_unit(w, 4).hp).is_equal(10 - dmg)


func test_ac_09_13_kill_despawns_and_ids_are_never_reused() -> void:
	var w := TacticsWorld.create(7)
	_unit(w, 1).cell = Vector2i(6, 2)
	_unit(w, 4).hp = 1
	var evs := _rules.apply(w, {"type": "attack", "target": "1", "value": 4})
	assert_array(_types(evs)).contains(["unit_died"])
	assert_int(int(_first(evs, "unit_died")["id"])).is_equal(4)
	assert_bool(w.has_thing(4)).is_false()
	assert_int(int(w.stats["kills"])).is_equal(1)
	assert_array(w.ids()).not_contains([4])
	# empty the other enemy units, end the turn: team 1 is respawned with fresh ids
	w.despawn(5)
	w.despawn(6)
	var next_before := w.next_id
	var evs2 := _rules.apply(w, {"type": "end_turn"})
	var spawned := []
	for e in evs2:
		if e["type"] == "unit_spawned":
			spawned.append(int(e["id"]))
	assert_int(spawned.size()).is_equal(3)
	for id in spawned:
		assert_bool(id >= next_before).override_failure_message("id %d reused (next_id was %d)" % [id, next_before]).is_true()
	assert_bool(w.has_thing(4)).is_false()
	assert_array(_types(evs2)).contains(["wave_started", "turn_ended"])


func _violations(w: TacticsWorld) -> String:
	var seen := {}
	var last := 0
	for id in w.ids():
		if id <= last:
			return "ids() not ascending at %d" % id
		last = id
		var u := _unit(w, id)
		if u == null:
			return "thing %d is not a Unit" % id
		if id >= w.next_id:
			return "id %d >= next_id %d" % [id, w.next_id]
		if u.cell.x < 0 or u.cell.y < 0 or u.cell.x >= 8 or u.cell.y >= 8:
			return "unit %d out of bounds %s" % [id, u.cell]
		if u.cell == Vector2i(3, 3) or u.cell == Vector2i(4, 4):
			return "unit %d on a blocked cell %s" % [id, u.cell]
		if seen.has(u.cell):
			return "units %d and %d share %s" % [seen[u.cell], id, u.cell]
		seen[u.cell] = id
		if u.hp <= 0 or u.hp > u.max_hp:
			return "unit %d hp %d/%d" % [id, u.hp, u.max_hp]
	return ""


func test_ac_09_13_invariants_hold_for_1000_ai_turns() -> void:
	var w := TacticsWorld.create(42)
	var bad := ""
	for i in 1000:
		_rules.apply(w, {"type": "ai_turn"})
		bad = _violations(w)
		if bad != "":
			bad = "turn %d: %s" % [i + 1, bad]
			break
	assert_str(bad).is_equal("")
	assert_int(w.tick).is_equal(1000)
