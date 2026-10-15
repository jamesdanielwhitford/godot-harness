extends Control

func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var title := Label.new()
	title.name = "Title"
	title.text = "GAME TITLE"
	title.clip_text = true
	add_child(title)
	title.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
	title.offset_left = 20
	title.offset_right = -20
	title.offset_top = 10
	title.offset_bottom = 36
	var score := Label.new()
	score.name = "Score"
	score.text = "SCORE 12345"
	add_child(score)
	score.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	score.offset_left = -150
	score.offset_right = -10
	score.offset_top = 40
	score.offset_bottom = 63
	var health := Label.new()
	health.name = "Health"
	health.text = "HEALTH 100"
	add_child(health)
	health.position = Vector2(20, 300)
	var bar := HBoxContainer.new()
	bar.name = "Bar"
	add_child(bar)
	for i in 3:
		var b := Button.new()
		b.name = "Btn%d" % i
		b.text = "B%d" % i
		b.custom_minimum_size = Vector2(150, 40)
		bar.add_child(b)
	bar.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	bar.offset_left = 10
	bar.offset_top = -50
	bar.offset_right = 476
	bar.offset_bottom = -10
	pass # HOOK-HUD
