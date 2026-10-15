#!/bin/bash
S=/tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad
G=$S/dl/godot/bin/Godot_v4.7-stable_linux.x86_64; W=$S/research/rp2_work
name=$1; sub=$2; src=$S/dl/refs/$name/$sub; dst=$W/copies/so_$name
rm -rf $dst; mkdir -p $dst
python3 -I $W/scripts/cpsel.py $src $dst
python3 -I $W/scripts/inject.py $dst
cd $dst
timeout 900 $G --headless --path $dst --import > $W/log_so_${name}_import.txt 2>&1
timeout 900 $G --headless --path $dst --quit-after 3000 > $W/log_so_${name}_load.txt 2>&1; echo "exit=$?" >> $W/log_so_${name}_load.txt
echo "$name script-only: $(grep -E 'CENSUS_STAT|exit=' $W/log_so_${name}_load.txt | tr '\n' ' ')"
du -sh $dst
