extends Node
func _ready():
	var b = Button.new()
	b.connect("pressed", _x)
	b.connect("nosuch", _x)
func _x():
	pass
