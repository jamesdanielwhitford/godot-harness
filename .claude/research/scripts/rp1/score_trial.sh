#!/bin/bash
# usage: score_trial.sh <task tN> <trial n>
W=/tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad/research/rp1_work
T=$1; N=$2; P=$W/runs/$T/t$N
{
echo "### common"; $W/score/check_project.sh $P 2>&1
echo "### task"; 
case $T in
 t1) python3 -I $W/score/score_t1.py $P;;
 t2) python3 -I $W/score/score_t2.py $P; echo "### t1-regression"; python3 -I $W/score/score_t1.py $P;;
 t3) python3 -I $W/score/score_t3.py $P;;
 t4) python3 -I $W/score/score_t4.py $P;;
 t5) python3 -I $W/score/score_t5.py $P;;
 t6) python3 -I $W/score/score_t6.py $P;;
 t7) python3 -I $W/score/score_t7.py $P;;
 t8) python3 -I $W/score/score_t8.py $P;;
esac
} > $W/runs/$T/t$N.score.txt 2>&1
