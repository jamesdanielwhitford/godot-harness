extends Node
func _ready():
	self.get_player_position()
	var v = Vector2(1,1)
	v.length_squared_fast()
