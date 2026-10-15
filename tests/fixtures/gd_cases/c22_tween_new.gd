extends Node
func _ready():
	var t = Tween.new()
	t.interpolate_property(self,"x",0,1,1)
