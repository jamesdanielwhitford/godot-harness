area: A2 scene      phase: plan      state: done
spec: .claude/plans/specs/02_scene.md @ uncommitted
tests: 0 total (spec only; 34 ACs, 15 faults + 3 clean entries for T2)      lock: n/a
updated: 2026-10-15 by planner (claude-opus-5-5)
done:
- 02_scene.md (450 lines): h digest (scene/.tres/--project-summary, --node/--expand/--json), h scene-gen (spec JSON Schema, $var/$res/$node/$new/$layers, inherited via seed, --force, multi-spec), h scene-edit (10 ops, MAIN/MAIN_INHERITED, all-or-nothing)
- post-write pipeline: A1 load_check + digest-after + expected-effects compare + dependents re-check + byte-exact rollback; uid + ext uid= preservation
- 7 spikes [Run] (runner cost 0.3 s; MAIN-state re-parents vanished nodes as Parent#Name; inherited removal silently no-op; script saves drop scene uid and ext uid=; set_uid restore works w/o reimport; set_scene_inherited_state not exposed -> seed file approach works)
next:
- spec reviewer: confirm deviations §8.3 (unit import of harness.scenes.model; digest <=40 lines + more:; --project-summary flag name)
- A1 planner/reviewer: confirm load_check.gd runner interface assumed in §8.4
- T2 writes tests/fixtures/projects/scene_host + tests/{contract,unit,e2e}/a2 + selftest faults FAULT-A2-01..15, CLEAN-A2-01..03
blockers:
- none
disputes: 0 open
