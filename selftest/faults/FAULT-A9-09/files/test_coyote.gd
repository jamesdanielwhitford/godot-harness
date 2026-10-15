extends GdUnitTestSuite
## FAULT-A9-09: the coyote window is 6 ticks at 60 Hz. Sweep k = ticks after leaving the floor (k-th airborne step).


func test_coyote_window_is_six_ticks() -> void:
	for k in range(1, 8):
		var m := PlayerMotor.new()
		m.tuning = MovementTuning.new()
		m.tick_rate = 60
		for i in 5:
			m.post_move(m.step(0.0, false, false, true), true)
		for i in k - 1:
			m.post_move(m.step(0.0, false, false, false), false)
		var v := m.step(0.0, true, true, false)
		var jumped := m.jumps == 1 and v.y < 0.0
		assert_bool(jumped).override_failure_message("k=%d" % k).is_equal(k <= 6)
	assert_int(PlayerMotor.new().coyote_ticks()).is_equal(6)
