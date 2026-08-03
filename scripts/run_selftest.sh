#!/usr/bin/env bash
# Run the HiveCell headless self-tests (safety interlock, etc.).
# Exits non-zero if any test fails, so it can gate a pre-push hook or CI.
#
# Godot binary resolution order:
#   1. $GODOT_BIN if set
#   2. the known local install
#   3. `godot` / `godot4` on PATH
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

find_godot() {
  if [[ -n "${GODOT_BIN:-}" && -x "${GODOT_BIN}" ]]; then echo "${GODOT_BIN}"; return; fi
  local known="/home/eddy/Godot/Godot_v4.7.1-stable_linux.x86_64"
  if [[ -x "$known" ]]; then echo "$known"; return; fi
  for c in godot4 godot; do
    if command -v "$c" >/dev/null 2>&1; then command -v "$c"; return; fi
  done
  return 1
}

BIN="$(find_godot)" || { echo "run_selftest: no Godot binary found (set GODOT_BIN)"; exit 2; }
echo "run_selftest: using $BIN"

# Ensure imports exist so res:// resolves headless.
"$BIN" --headless --path "$REPO_ROOT/godot" --import >/dev/null 2>&1 || true

rc=0
for t in "$REPO_ROOT"/godot/tests/*.gd; do
  name="$(basename "$t")"
  echo "run_selftest: $name ..."
  "$BIN" --headless --path "$REPO_ROOT/godot" --script "res://tests/$name" || rc=1
done
# Formal verification of the interlock invariants (TLA+ / TLC, roadmap #1).
# Skipped with a warning when there is no JRE, so a contributor without Java is
# not blocked from pushing -- the Godot tests above still gate. Set
# HIVECELL_SKIP_MODELCHECK=1 to skip it deliberately (it costs ~70s).
if [[ "${HIVECELL_SKIP_MODELCHECK:-0}" == "1" ]]; then
  echo "run_selftest: model check SKIPPED (HIVECELL_SKIP_MODELCHECK=1)"
else
  echo "run_selftest: model-checking the safety interlock ..."
  mc=0
  "$REPO_ROOT/scripts/run_modelcheck.sh" || mc=$?   # set -e must not abort here
  case "$mc" in
    0) ;;
    2) echo "run_selftest: model check SKIPPED (no Java / no tla2tools.jar) -- see spec/README.md" ;;
    *) rc=1 ;;
  esac
fi

[ "$rc" -eq 0 ] && echo "run_selftest: all tests passed." || { echo "run_selftest: TESTS FAILED"; exit 1; }
