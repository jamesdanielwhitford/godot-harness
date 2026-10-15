extends Node
@export var a: int = 1
@onready var b = 2
func _ready():
	print(a, b)
