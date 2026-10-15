extends Node2D

func _ready() -> void:
	var bg := ColorRect.new()
	bg.name = "Bg"
	bg.size = Vector2(640, 360)
	bg.color = Color(0.1, 0.2, 0.4)
	add_child(bg)
	var box := ColorRect.new()
	box.name = "Box"
	box.size = Vector2(40, 40)
	box.position = Vector2(20, 100)
	box.color = Color8(255, 165, 0)
	add_child(box)
	var hud := CanvasLayer.new()
	hud.name = "HUD"
	add_child(hud)
	hud.owner = self
	hud.unique_name_in_owner = true
	var panel := PanelContainer.new()
	panel.name = "Panel"
	hud.add_child(panel)
	panel.position = Vector2(10, 10)
	var score := Label.new()
	score.name = "Score"
	score.text = "SCORE 12345"
	panel.add_child(score)
	score.owner = self
	score.unique_name_in_owner = true
	pass # HOOK-READY

func _physics_process(_delta: float) -> void:
	$Box.position.x += 1

func _process(_delta: float) -> void:
	pass # HOOK-PROCESS
