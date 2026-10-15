extends GdUnitTestSuite
## A9 gdUnit4 suite (AC-09.16): PlayerMotor is pure (no scene); tests drive step()/post_move() like Player does.
## Conventions used here (spec 2.7): "k ticks after leaving the floor" = the press happens on the k-th airborne
## step (k = 1 is the first step with on_floor == false); "k ticks before landing" = the press is step 0 and the
## landing step (on_floor == true) is step k.


func _motor(rate: int = 60) -> PlayerMotor:
	var m := PlayerMotor.new()
	m.tuning = MovementTuning.new()
	m.tick_rate = rate
	return m


func _floor_ticks(m: PlayerMotor, n: int) -> void:
	for i in n:
		var v := m.step(0.0, false, false, true)
		m.post_move(v, true)


func _air_tick(m: PlayerMotor, pressed: bool, held: bool) -> Vector2:
	var v := m.step(0.0, pressed, held, false)
	m.post_move(v, false)
	return v


## Jump on tick 0 from the floor, then free air. hold = number of ticks the button stays held (0-based, the press
## tick counts). Returns {"apex": px, "apex_tick": n}.
func _jump_apex(rate: int, hold: int) -> Dictionary:
	var m := _motor(rate)
	var dt := 1.0 / float(rate)
	var y := 0.0
	var min_y := 0.0
	var apex_tick := 0
	for i in rate * 3:
		var v := m.step(0.0, i == 0, i < hold, i == 0)
		y += v.y * dt
		m.post_move(v, false)
		if y < min_y:
			min_y = y
			apex_tick = i + 1
	return {"apex": -min_y, "apex_tick": apex_tick}


func test_ac_09_16_tick_windows_scale_with_rate() -> void:
	assert_int(_motor(60).coyote_ticks()).is_equal(6)
	assert_int(_motor(60).buffer_ticks()).is_equal(6)
	assert_int(_motor(30).coyote_ticks()).is_equal(3)
	assert_int(_motor(120).buffer_ticks()).is_equal(12)


func test_ac_09_16_gravity_and_jump_velocity_follow_height_and_apex_time() -> void:
	var m := _motor(60)
	var t := m.tuning
	assert_float(m.gravity()).is_equal_approx(2.0 * t.jump_height / (t.time_to_apex * t.time_to_apex), 0.5)
	assert_float(m.jump_velocity()).is_equal_approx(-2.0 * t.jump_height / t.time_to_apex, 0.5)


func test_ac_09_16_apex_within_one_px_at_30_60_120_hz() -> void:
	for rate in [30, 60, 120]:
		var r := _jump_apex(rate, 100000)
		var h: float = MovementTuning.new().jump_height
		assert_float(r["apex"]).override_failure_message("%d Hz: apex %.2f px" % [rate, r["apex"]]).is_equal_approx(h, 1.0)


func test_ac_09_16_time_to_apex_matches_tuning() -> void:
	for rate in [30, 60, 120]:
		var r := _jump_apex(rate, 100000)
		var want := roundi(MovementTuning.new().time_to_apex * rate)
		var got: int = r["apex_tick"]
		assert_bool(absi(got - want) <= 1).override_failure_message("%d Hz: apex at tick %d, want %d +/- 1" % [rate, got, want]).is_true()


func test_ac_09_16_accel_ticks_to_max_speed() -> void:
	var m := _motor(60)
	var max_speed := m.tuning.max_speed
	var n := 0
	var reached := false
	for i in 60:
		var v := m.step(1.0, false, false, true)
		m.post_move(v, true)
		n += 1
		if v.x >= max_speed - 0.01:
			reached = true
			break
	assert_bool(reached).is_true()
	var want := ceili(m.tuning.accel_time * 60.0)
	assert_bool(absi(n - want) <= 1).override_failure_message("%d ticks to max speed, want %d +/- 1" % [n, want]).is_true()
	assert_bool(n > 1).is_true()


func test_ac_09_16_coyote_window_edges() -> void:
	for k in range(1, 8):
		var m := _motor(60)
		_floor_ticks(m, 5)
		for i in k - 1:
			_air_tick(m, false, false)
		var v := m.step(0.0, true, true, false)
		m.post_move(v, false)
		var jumped := m.jumps == 1 and v.y < 0.0
		if k <= 6:
			assert_bool(jumped).override_failure_message("press %d ticks after leaving the floor must jump" % k).is_true()
		else:
			assert_bool(jumped).override_failure_message("press %d ticks after leaving the floor must NOT jump" % k).is_false()


func test_ac_09_16_buffer_window_edges() -> void:
	for k in range(1, 8):
		var m := _motor(60)
		_floor_ticks(m, 3)
		for i in 12:  # walk off and fall past the coyote window
			_air_tick(m, false, false)
		_air_tick(m, true, true)  # the early press, step 0
		assert_int(m.jumps).override_failure_message("k=%d: jumped in the air" % k).is_equal(0)
		for i in k - 1:
			_air_tick(m, false, true)
		var v := m.step(0.0, false, true, true)  # landing, step k
		m.post_move(v, true)
		var jumped := m.jumps == 1 and v.y < 0.0
		if k <= 6:
			assert_bool(jumped).override_failure_message("press %d ticks before landing must jump on landing" % k).is_true()
		else:
			assert_bool(jumped).override_failure_message("press %d ticks before landing must NOT jump" % k).is_false()


func test_ac_09_16_early_release_cuts_the_jump() -> void:
	var full := _jump_apex(60, 100000)
	var cut := _jump_apex(60, 2)
	assert_bool(cut["apex"] > 0.0).is_true()
	assert_bool(cut["apex"] < 0.5 * full["apex"]).override_failure_message("cut apex %.2f vs full %.2f" % [cut["apex"], full["apex"]]).is_true()


func test_ac_09_16_no_second_jump_in_the_air() -> void:
	for press_at in [3, 10, 30]:
		var m := _motor(60)
		var v := m.step(0.0, true, true, true)
		m.post_move(v, false)
		assert_int(m.jumps).is_equal(1)
		for i in range(1, press_at):
			_air_tick(m, false, true)
		var before_vy := m.velocity.y
		_air_tick(m, true, true)
		assert_int(m.jumps).override_failure_message("air press at tick %d jumped again" % press_at).is_equal(1)
		assert_bool(m.velocity.y >= before_vy - 1.0).is_true()


func test_ac_09_16_to_dict_is_plain_data() -> void:
	var d := _motor(60).to_dict()
	assert_bool(d.is_empty()).is_false()
	assert_str(JSON.stringify(d)).is_not_empty()
