class_name Counter
extends RefCounted

var total: int = 0


func add(k: int) -> int:
	total += k
	return total
