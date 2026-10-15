# Spikes status
Done: S1-S6 run; report at .claude/research/r2_spikes.md (uncommitted; main session commits).
- S1 yes. S2 reconciled (rc=1 only for `-s` on the broken script; scene/load paths rc=0 or hang). S3a partial (no Agent tool in spike agent; CLI `--agent` applies `model:`), S3b nested claude -p works. S4 single test via `-i suite:other` exclusions. S5 no push for unopened files; didOpen gives diags in ~7 ms warm. S6 push ok, delete 403.
Open: S3a in-session Agent spawn of `builder`/`planner` untested. Leftover remote branches: spike-test, build/x-spike (delete manually).
