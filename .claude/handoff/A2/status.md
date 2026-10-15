area: A2 scene      phase: plan      state: done (re-run after REVIEW v1)
spec: .claude/plans/specs/02_scene.md @ uncommitted (v2, 469 lines)
tests: 0 total (spec only; 34 ACs, 15 faults + 3 clean entries for T2)      lock: n/a
updated: 2026-10-15 by planner re-run (claude-opus-5-5)
done:
- v1: h digest / scene-gen / scene-edit, post-write pipeline, uid preservation, 7 spikes [Run]
- v2 (REVIEW B14, R-30): pre/post write checks go through A1's checkrun.load_check(run, project, res_paths, smoke=0) -> list[dict] (§3.3 new "Load-check" paragraph, gen steps 3/5, edit step 3); dependent findings mapped to scene.breaks-dependent (§3.4); A2 no longer ports load_check.gd (§3.2); build order gated on B1 step 2 (§7); §8.4 A1 bullet closed
- v2: godot.run returns Invocation (inv.records / inv.findings), explicit ensure_imported (§3.3, R-31/R-32)
- v2 (N05, N17): §8.3 deviations marked accepted with R-ids (R-01 scenes.model public names, R-22, R-23) plus R-21 ext uid= rewrite (§8.3-4, §3.3 step 4)
next:
- spec reviewer: confirm B14/N05 applied for G1
- T2 writes tests/fixtures/projects/scene_host + tests/{contract,unit,e2e}/a2 + selftest faults FAULT-A2-01..15, CLEAN-A2-01..03
blockers:
- none (depends on B1 exposing checkrun.load_check by step 2, REVIEW §4)
disputes: 0 open
