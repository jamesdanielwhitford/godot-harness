area: A6 visual      phase: plan      state: done
spec: .claude/plans/specs/06_visual.md @ uncommitted
tests: 0 total / 0 pass / 0 fail (spec only; 27 ACs, 12 faults + 3 clean entries for T6)      lock: n/a
updated: 2026-10-15 by planner (claude-opus-5-5)
done:
- 06_visual.md: `h shot` (scene + scenario mode, --tick/--crop/--node/--hide/--hide-layer/--size/--twice/--movie/--compare), `h shot --layout` (headless, 4 rules), `h baseline propose|approve|list` (approve needs /dev/tty), baseline meta schema, exact vs tolerant compare
- spikes [Run] K1-K11: capture 0.78-0.84 s at 640x360; unseeded CPUParticles2D differ even with --fixed-fps, seed() in runner fixes it (3/3); tick-exact capture via _process + one-shot frame_post_draw; layout works under --headless (same rects as Xvfb); runtime load of _capture.gd by abs path works; input injection under Xvfb same as headless (A5 open Q2)
- contract open question (3) answered (spec §3.5): xvfb-run returns Godot's rc (7, 134); group SIGTERM -> all gone, Popen rc -15; group SIGKILL leaves stale /tmp/.X<n>-lock + socket
next:
- spec reviewer: deviations D-a (binary PNG baseline in fixture shot_min), D-b (runtime load of _capture.gd), D-c (layout runs headless), D-d (godot.py xvfb: stale-lock cleanup, extra Godot args, display-failure retry); ownership of the A6 block in A5's runners/scenario.gd and A5 run_scenario extra_args
- T6 writes tests/contract/a6/, fixture shot_min (+ capture_ref.gd tool and approved baseline PNG), FAULT-A6-01..12, CLEAN-A6-01..03
blockers:
- none
disputes: 0 open
