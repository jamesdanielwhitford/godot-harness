#!/bin/bash
# usage: run_trial.sh <task> <trial> [startdir-to-copy]
W=/tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad/research/rp1_work
T=$1; N=$2; SRC=${3:-$W/empty_start}
B=$W/runs/$T; D=$B/t$N; rm -rf $D; mkdir -p $D; cp -r $SRC/. $D/
cd $D
export PATH=$W/bin:$PATH
PROMPT="$(cat $W/tasks/pre.txt)
$(cat $W/tasks/$T.txt)"
START=$(date +%s)
timeout 1800 env -u CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD -u CLAUDE_CODE_SESSION_ID /opt/node22/bin/claude -p "$PROMPT" --max-turns 60 --permission-mode acceptEdits --allowedTools "Bash" "Read" "Write" "Edit" "Glob" "Grep" --output-format json > $B/t$N.result.json 2> $B/t$N.stderr
echo "rc=$? secs=$(( $(date +%s)-START ))" > $B/t$N.meta
