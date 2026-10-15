#!/bin/bash
# usage: loadcheck.sh <name> <relproj|ADDON:x>
S=/tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad
G=$S/dl/godot/bin/Godot_v4.7-stable_linux.x86_64
W=$S/research/rp2_work
name=$1; spec=$2; label=${3:-$1}; src=$S/dl/refs/$name; dst=$W/copies/$label
rm -rf "$dst"; mkdir -p "$dst"
if [[ $spec == ADDON:* ]]; then
  mkdir -p "$dst/addons"; cp -r "$src/addons/"* "$dst/addons/"
  printf 'config_version=5\n[application]\nconfig/name="census"\nconfig/features=PackedStringArray("4.7")\n' > "$dst/project.godot"
  [ -d "$src/dev_scenes" ] && cp -r "$src/dev_scenes" "$dst/"
elif [[ $spec == NEWPROJ ]]; then
  cp -a "$src/." "$dst/"; rm -rf "$dst/.git"
  [ -f "$dst/project.godot" ] || printf 'config_version=5\n[application]\nconfig/name="census"\nconfig/features=PackedStringArray("4.7")\n' > "$dst/project.godot"
else
  cp -a "$src/$spec/." "$dst/"; rm -rf "$dst/.git"
fi
python3 -I $W/scripts/inject.py "$dst"
cd "$dst"
{ echo "== import"; ( time timeout 900 $G --headless --path "$dst" --import ) 2>&1 | tail -n 4000 ; } > $W/log_${label}_import.txt 2>&1
{ echo "== load"; timeout 900 $G --headless --path "$dst" --quit-after 3000; echo "exit=$?"; } > $W/log_${label}_load.txt 2>&1
echo "$label import-errs: $(grep -c -E 'SCRIPT ERROR|Parse Error|ERROR:' $W/log_${label}_import.txt) ; $(grep -E 'CENSUS_STAT|exit=' $W/log_${label}_load.txt | tr '\n' ' ')"
rm -rf "$dst"
