class_name Hero
extends Node2D

signal hit(amount)

@export var speed: float = 100.0
@export var target: Node


func _on_hit(a):
	print("hit ", a)
