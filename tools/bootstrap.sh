#!/usr/bin/env bash
# Idempotent environment setup. Flags: --quiet --with-vulkan --with-dotnet
set -u
ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
CACHE="${HARNESS_CACHE:-$HOME/.cache/godot-harness}"
QUIET=0; VULKAN=0; DOTNET=0
for a in "$@"; do case "$a" in
  --quiet) QUIET=1;; --with-vulkan) VULKAN=1;; --with-dotnet) DOTNET=1;;
  *) echo "unknown flag: $a" >&2; exit 2;; esac; done
LOG="$(mktemp)"; trap 'rm -f "$LOG"' EXIT
say() { [ "$QUIET" = 1 ] || echo "$*"; }
fail() { echo "bootstrap FAILED: $*" >&2; [ -s "$LOG" ] && tail -n 5 "$LOG" >&2; exit 1; }
pin() { python3 -I -c 'import sys,tomllib;d=tomllib.load(open(sys.argv[1],"rb"));v=d[sys.argv[2]];print(" ".join(v) if isinstance(v,list) else v)' "$ROOT/tools/harness/pins.toml" "$1"; }
mkdir -p "$CACHE" "$ROOT/tools/bin"

# 1-2. Godot
GV="$(pin godot_version)"; GSTR="$(pin godot_version_string)"; GSHA="$(pin godot_sha256)"
GDIR="$CACHE/godot/$GV"; GBIN="$GDIR/Godot_v${GV}_linux.x86_64"
OS="$(uname -s)"; ARCH="$(uname -m)"
if [ "$OS" = Darwin ]; then
  # macOS: use the installed app (override with HARNESS_GODOT); no download
  GBIN="${HARNESS_GODOT:-/Applications/Godot.app/Contents/MacOS/Godot}"
  [ -x "$GBIN" ] || fail "godot not found at $GBIN (install Godot $GSTR or set HARNESS_GODOT)"
fi
if [ "$OS" != Darwin ] && [ ! -x "$GBIN" ]; then
  say "godot: downloading $GV"
  T="$(mktemp -d)"
  curl -fsSL --retry 3 -o "$T/g.zip" "$(pin godot_url)" >"$LOG" 2>&1 || fail "godot download"
  ACT="$(sha256sum "$T/g.zip" | cut -d' ' -f1)"
  if [ -z "$GSHA" ]; then echo "godot_sha256 is empty; pin this: $ACT"; 
  elif [ "$ACT" != "$GSHA" ]; then fail "godot sha256 mismatch ($ACT)"; fi
  mkdir -p "$GDIR" && unzip -qo "$T/g.zip" -d "$GDIR" >"$LOG" 2>&1 || fail "godot unzip"
  chmod +x "$GBIN"; rm -rf "$T"
fi
ln -sf "$GBIN" "$ROOT/tools/bin/godot"
GOT="$("$ROOT/tools/bin/godot" --headless --version 2>/dev/null | tail -n1)"
[ "$GOT" = "$GSTR" ] || fail "godot version '$GOT' != '$GSTR'"
say "godot: $GOT"

# 3. gdUnit4
GD="$CACHE/gdunit4"; GC="$(pin gdunit4_commit)"; GT="$(pin gdunit4_tag)"
if [ "$(git -C "$GD" rev-parse HEAD 2>/dev/null)" != "$GC" ]; then
  rm -rf "$GD"; ok=0
  for u in $(pin gdunit4_urls); do
    git clone -q --depth 1 --branch "$GT" "$u" "$GD" >"$LOG" 2>&1 && { ok=1; break; }; done
  [ "$ok" = 1 ] || fail "gdunit4 clone"
  [ "$(git -C "$GD" rev-parse HEAD)" = "$GC" ] || fail "gdunit4 commit mismatch"
fi
say "gdunit4: $GT ${GC:0:10}"

# 4. odiff
OV="$(pin odiff)"; case "$OS-$ARCH" in Darwin-arm64) OP=darwin-arm64;; Darwin-*) OP=darwin-x64;; *) OP=linux-x64;; esac
OB="$CACHE/odiff/node_modules/@odiff/$OP/odiff"
if [ ! -x "$OB" ]; then
  mkdir -p "$CACHE/odiff"
  npm i --silent --no-audit --no-fund --prefix "$CACHE/odiff" "odiff-bin@$OV" >"$LOG" 2>&1 </dev/null || fail "odiff npm install"
  [ -e "$OB" ] || fail "odiff binary not at $OB"
fi
say "odiff: $OV"

# 5. Python venv
REQ="$ROOT/tools/harness/requirements-dev.txt"
if ! "$ROOT/.venv/bin/python" -c 'import pytest,yaml,gdtoolkit,jsonschema' 2>/dev/null; then
  [ -x "$ROOT/.venv/bin/python" ] || python3 -m venv "$ROOT/.venv" >"$LOG" 2>&1 || fail "venv"
  "$ROOT/.venv/bin/pip" install -q -r "$REQ" >"$LOG" 2>&1 || fail "pip install"
fi
say "venv: ok"

# 6. Display tools
if [ "$OS" != Darwin ]; then
  command -v xvfb-run >/dev/null || echo "WARN: xvfb-run missing (apt-get install xvfb)"
  command -v compare >/dev/null || echo "WARN: ImageMagick compare missing (apt-get install imagemagick)"
fi
if [ "$VULKAN" = 1 ] && [ "$OS" != Darwin ]; then
  { apt-get update && apt-get install -y mesa-vulkan-drivers vulkan-tools mesa-utils; } >"$LOG" 2>&1 || fail "vulkan install"
  say "vulkan: installed"
fi

# 7. dotnet (optional)
if [ "$DOTNET" = 1 ]; then
  DN="$CACHE/dotnet"
  if [ ! -x "$DN/dotnet" ]; then
    curl -fsSL -o "$CACHE/dotnet-install.sh" https://dot.net/v1/dotnet-install.sh >"$LOG" 2>&1 || fail "dotnet-install download"
    bash "$CACHE/dotnet-install.sh" --channel 8.0 --install-dir "$DN" >"$LOG" 2>&1 || fail "dotnet install"
  fi
  say "dotnet: $("$DN/dotnet" --version 2>/dev/null)"
fi

# 8. API index (h api --rebuild: dump + doctool in a scratch dir, never in the repo)
H="$ROOT/tools/harness/h"
API="$CACHE/api/$GSTR"
if [ ! -f "$API/index.json" ] || [ ! -f "$API/@GDScript.xml" ]; then
  "$H" api --rebuild >"$LOG" 2>&1 || echo "WARN: api index failed (see $(tail -n1 "$LOG"))"
fi
[ -f "$API/index.json" ] && say "api index: $API" || echo "WARN: api index missing"

# 9. sync/import the sample project (exists from phase 5 on)
if [ -d "$ROOT/sample" ]; then
  { "$H" sync --project "$ROOT/sample" && "$H" import --project "$ROOT/sample"; } >"$LOG" 2>&1 \
    || echo "WARN: sample sync/import failed"
fi
if [ "$QUIET" = 1 ]; then "$H" doctor >"$LOG" 2>&1 && echo "bootstrap ok" || { cat "$LOG"; exit 1; }
else "$H" doctor; fi
