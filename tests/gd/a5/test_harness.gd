extends GdUnitTestSuite
## AC-05.26 (spec 2.3 Harness/CommandBus; R-20). Success paths only: no push_error is triggered (orchestrator ruling D-5).

class Ent:
	extends Node
	func _harness_state() -> Dictionary:
		return {"v": 1}


class Ev:
	extends RefCounted
	func to_dict() -> Dictionary:
		return {"type": "obj_ev"}


var _handlers: Array = []
var _ids: Array = []


func after_test() -> void:
	for t in _handlers:
		CommandBus.unhandle(t)
	_handlers.clear()
	for i in _ids:
		Harness.unregister(i)
	_ids.clear()


func _reg(id: Variant) -> Ent:
	var e := Ent.new()
	add_child(e)
	_ids.append(id)
	var ok := Harness.register(id, e)
	assert_bool(ok).is_true()
	return e


func test_ac_05_26_2_register_int_id_and_lookup() -> void:
	var e := _reg(42)
	assert_bool(Harness.has_entity(42)).is_true()
	assert_bool(Harness.has_entity("42")).is_true()
	assert_object(Harness.get_entity("42")).is_same(e)


func test_ac_05_26_4_node_auto_unregisters_when_freed() -> void:
	var e := _reg("gone")
	assert_bool(Harness.has_entity("gone")).is_true()
	remove_child(e)
	e.free()
	assert_bool(Harness.has_entity("gone")).is_false()


func test_ac_05_26_5_is_active_false_outside_runner() -> void:
	assert_bool(Harness.is_active()).is_false()


func test_ac_05_26_8_seq_tick_and_events_emitted() -> void:
	var seen: Array = []
	_handlers.append("seqt")
	CommandBus.handle("seqt", func(cmd: Dictionary) -> Array:
		seen.append(cmd)
		return [{"type": "did_it"}])
	var got: Array = []
	var on_emitted := func(cmd: Dictionary, events: Array) -> void:
		got.append([cmd, events])
	CommandBus.events_emitted.connect(on_emitted)
	var r1 := CommandBus.submit({"type": "seqt"})
	var r2 := CommandBus.submit({"type": "seqt"})
	CommandBus.events_emitted.disconnect(on_emitted)
	assert_int(r1.size()).is_equal(1)
	assert_int(r2.size()).is_equal(1)
	assert_int(seen.size()).is_equal(2)
	assert_bool(seen[0].has("seq")).is_true()
	assert_bool(seen[0].has("tick")).is_true()
	assert_int(int(seen[1]["seq"])).is_equal(int(seen[0]["seq"]) + 1)
	assert_int(int(seen[0]["seq"])).is_greater_equal(1)
	assert_int(got.size()).is_equal(2)
	assert_int((got[0][1] as Array).size()).is_equal(1)


func test_ac_05_26_9_object_events_with_to_dict_accepted() -> void:
	_handlers.append("objev")
	CommandBus.handle("objev", func(_cmd: Dictionary) -> Array:
		return [Ev.new()])
	var r := CommandBus.submit({"type": "objev"})
	assert_int(r.size()).is_equal(1)


func test_ac_05_26_10_second_handle_replaces_first() -> void:
	var first_calls: Array = []
	var second_calls: Array = []
	_handlers.append("rep")
	CommandBus.handle("rep", func(_cmd: Dictionary) -> Array:
		first_calls.append(1)
		return [])
	CommandBus.handle("rep", func(_cmd: Dictionary) -> Array:
		second_calls.append(1)
		return [])
	CommandBus.submit({"type": "rep"})
	assert_int(first_calls.size()).is_equal(0)
	assert_int(second_calls.size()).is_equal(1)


func test_ac_05_26_11_unhandle_unknown_is_noop() -> void:
	var calls: Array = []
	CommandBus.handle("rmv", func(_cmd: Dictionary) -> Array:
		calls.append(1)
		return [])
	CommandBus.unhandle("rmv")
	CommandBus.unhandle("never_registered_type")
	assert_int(calls.size()).is_equal(0)
