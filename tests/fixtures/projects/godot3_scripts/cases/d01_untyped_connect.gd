extends Node
func _ready():
	var b = Button.new()
	b.connect("pressed", self, "_x")
func _x():
	pass
