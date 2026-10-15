Purpose: hand-written 2D platformer feel fixture for `h trace` (A7): run, jump, coyote, buffer, camera probes.
Owner: A7 (T7). Expected `h trace res://feel/player.feel.json`: PASS (11/11 targets met). No addons/ (synced by the verb).
Hook lines in scripts/player.gd and feel/targets.tres are the exact text the FAULT-A7-* replace ops match.
Deviation from spec 6: fall_rise_ratio target is [0.5, 0.9] (fall gravity > rise gravity gives ~0.72, not > 1.2).
jump.json also taps `right` at tick 1 so scenario mode traces 9 columns (AC-07.13).
