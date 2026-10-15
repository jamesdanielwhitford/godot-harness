#!/bin/bash
# usage: check_project.sh <projdir>  -> prints import/load-all/run-main results (JSON-ish lines)
W=/tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad/research/rp1_work
G=$W/bin/godot; P=$1; S=$W/score
cd $P
timeout 120 $G --headless --path . --import > $P/.import.log 2>&1
echo "import_errs=$(grep -c -E 'SCRIPT ERROR|Parse Error|Failed to load|ERROR:' $P/.import.log)"
timeout 60 $G --headless --path . -s $S/load_all.gd > $P/.loadall.log 2>&1
grep LOADALL_SUMMARY $P/.loadall.log
echo "loadall_errlines=$(grep -c -E 'SCRIPT ERROR|Parse Error|Failed to load|ERROR:' $P/.loadall.log)"
timeout 60 $G --headless --path . --quit-after 120 > $P/.runmain.log 2>&1
echo "runmain_rc=$? errs=$(grep -c -E 'SCRIPT ERROR|Parse Error|Failed to load|ERROR:' $P/.runmain.log) has_main_scene=$(grep -c 'run/main_scene' project.godot)"
python3 -I $S/static_stats.py $P
