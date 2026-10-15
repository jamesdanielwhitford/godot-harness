# Sourced by tools/dev/*.sh. Resolves ROOT (HARNESS_ROOT overrides; used by self-tests).
if [ -n "${HARNESS_ROOT:-}" ]; then
  ROOT="$(cd "$HARNESS_ROOT" && pwd)"
else
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi
DEV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Prints "sha256  path" lines (LC_ALL=C sorted) for every file under tests/ and selftest/,
# excluding the lock itself and generated noise (pycache, .pytest_cache, .godot, *.pyc).
lock_manifest() {
  ( cd "$ROOT" || exit 1
    for d in tests selftest; do
      if [ -d "$d" ]; then
        find "$d" \( -name __pycache__ -o -name .pytest_cache -o -name .godot \) -prune -o \
          -type f ! -name '*.pyc' ! -path 'tests/LOCK.sha256' -print
      fi
    done | LC_ALL=C sort | while IFS= read -r f; do sha256sum -- "$f"; done
  )
}
