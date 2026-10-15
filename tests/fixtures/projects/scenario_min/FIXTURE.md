scenario_min: CharacterBody2D player on a floor, mover/dice sims, scenarios under scenarios/ (A5 `h run`; also A6 AC-06.25).
Owner: A5/T5. Declares 3 harness autoloads and ships no addons/: the verb syncs it. Never import the repo copy (B3).
Expected `h check` after `h sync`: PASS. Player hook lines (HOOK-PHYS/PROCESS/READY/STATE) are the FAULT-A5-* edit points.
Exact values: mover n = k and x = 1.5 k at tick k; player.input_events counts jump presses (not releases).
Player `landed` fires only on floor entry after a jump (the initial fall is not an event).
