extends Node
func _ready():
	var n := 0
	var f := func(): n += 1
	f.call()
	print(n)
