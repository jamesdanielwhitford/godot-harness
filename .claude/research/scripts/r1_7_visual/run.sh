#!/bin/bash
# usage: run.sh name method driver mode n
S=/tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad; W=$S/research/r1_7_work; G=$S/dl/godot/bin/Godot_v4.7-stable_linux.x86_64; cd $W
for k in a b; do d=out/$1_$k; rm -rf $d; mkdir -p $d; timeout 60 xvfb-run -a $G --path proj --rendering-method $2 --rendering-driver $3 $EXTRA -- --out=$W/$d --mode=$4 --n=$5  >$d/log.txt 2>&1; done
same=0; for f in out/$1_a/f*.png; do cmp -s $f out/$1_b/$(basename $f) && same=$((same+1)); done
echo "$1 ($2/$3 $4): identical $same/$5 ; $(grep -h 'total ms' out/$1_a/log.txt | sed 's/renderer.*//')"
