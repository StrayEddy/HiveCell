#!/usr/bin/env bash
# Model-check the HiveCell safety interlock with TLA+ / TLC (roadmap #1).
#
# The spec lives in spec/HiveCellInterlock.tla; see spec/README.md for the
# model <-> code correspondence table and the abstractions it relies on.
#
#   ./scripts/run_modelcheck.sh              # the three green runs (safety, liveness, blackout)
#   ./scripts/run_modelcheck.sh --deep       # same, with a finer travel discretisation
#   ./scripts/run_modelcheck.sh --mutants    # prove the checks have teeth (slow)
#
# Exit codes:  0 pass   1 a check failed   2 tooling missing
#
# Java resolution order:  $JAVA  ->  $JAVA_HOME/bin/java  ->  java on PATH
# tla2tools.jar:          $TLA_TOOLS  ->  cache dir  ->  downloaded on first run
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC_DIR="$REPO_ROOT/spec"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/hivecell"
JAR_URL="https://github.com/tlaplus/tlaplus/releases/latest/download/tla2tools.jar"

MODE="green"
case "${1:-}" in
  --deep)    MODE="deep" ;;
  --mutants) MODE="mutants" ;;
  --help|-h) sed -n '2,14p' "${BASH_SOURCE[0]}"; exit 0 ;;
  "")        ;;
  *)         echo "run_modelcheck: unknown option '$1' (try --help)" >&2; exit 2 ;;
esac

# --- tooling -----------------------------------------------------------------
find_java() {
  if [[ -n "${JAVA:-}" && -x "${JAVA}" ]]; then echo "${JAVA}"; return 0; fi
  if [[ -n "${JAVA_HOME:-}" && -x "${JAVA_HOME}/bin/java" ]]; then echo "${JAVA_HOME}/bin/java"; return 0; fi
  command -v java 2>/dev/null && return 0
  return 1
}

JAVA_BIN="$(find_java)" || {
  cat >&2 <<'EOF'
run_modelcheck: no Java runtime found -- TLC needs one.
  Arch/Manjaro:  sudo pacman -S jre-openjdk
  Debian/Ubuntu: sudo apt install default-jre
  macOS:         brew install openjdk
Or point $JAVA at a java binary.
EOF
  exit 2
}

JAR="${TLA_TOOLS:-$CACHE_DIR/tla2tools.jar}"
if [[ ! -f "$JAR" ]]; then
  echo "run_modelcheck: fetching tla2tools.jar -> $JAR"
  mkdir -p "$(dirname "$JAR")"
  if ! curl -fsSL -o "$JAR" "$JAR_URL"; then
    rm -f "$JAR"
    echo "run_modelcheck: could not download tla2tools.jar; set \$TLA_TOOLS to a local copy." >&2
    exit 2
  fi
fi

echo "run_modelcheck: java = $JAVA_BIN"
echo "run_modelcheck: jar  = $JAR"

rc=0

# tlc <work-dir> <config-basename>  -> TLC output on stdout
tlc() {
  ( cd "$1" && "$JAVA_BIN" -XX:+UseParallelGC -cp "$JAR" tlc2.TLC \
      -config "$2.cfg" -workers auto -cleanup HiveCellInterlock.tla 2>&1 )
}

passed() { grep -q "Model checking completed. No error has been found." <<<"$1"; }

# Why a run failed, in one line.
violation() {
  grep -oE "Invariant [A-Za-z_]+ is violated|Temporal properties were violated|Error: [^\"]{0,60}" <<<"$1" \
    | head -1
}

# --- the three green runs ----------------------------------------------------
run_green() {
  local work="$SPEC_DIR"
  if [[ "$MODE" == "deep" ]]; then
    # Finer travel discretisation + a longer dwell: same claims, bigger state space.
    work="$(mktemp -d)"; trap 'rm -rf "$work"' RETURN
    cp "$SPEC_DIR/HiveCellInterlock.tla" "$work/"
    for cfg in Safety Liveness Blackout; do
      sed -e 's/Steps      = 4/Steps      = 6/' \
          -e 's/DwellTicks = 2/DwellTicks = 3/' \
          "$SPEC_DIR/$cfg.cfg" > "$work/$cfg.cfg"
    done
    echo "run_modelcheck: deep mode (Steps=6, DwellTicks=3)"
  fi

  for cfg in Safety Liveness Blackout; do
    echo
    echo "=== $cfg ==="
    local out; out="$(tlc "$work" "$cfg")"
    if passed "$out"; then
      echo "  PASS  $(grep -oE '[0-9,]+ distinct states found' <<<"$out" | tail -1)"
    else
      echo "  FAIL  $(violation "$out")"
      echo "  full counterexample:  cd spec && java -cp '$JAR' tlc2.TLC -config $cfg.cfg HiveCellInterlock.tla"
      rc=1
    fi
  done
}

# --- mutation suite ----------------------------------------------------------
#
# A spec that passes proves nothing unless it CAN fail. Each mutant injects one
# real design defect -- most of them defects the ADRs explicitly rejected -- and
# the suite FAILS if TLC does not catch it. This is what makes the green runs
# above evidence rather than decoration.

MUT_WORK=""
mut_caught=0
mut_missed=0

# mutate <name> <config> <sed-expr> <what the defect is>
mutate() {
  local name="$1" cfg="$2" expr="$3" desc="$4"
  local dir="$MUT_WORK/$name"
  mkdir -p "$dir"
  sed "$expr" "$SPEC_DIR/HiveCellInterlock.tla" > "$dir/HiveCellInterlock.tla"
  cp "$SPEC_DIR/$cfg.cfg" "$dir/"

  if cmp -s "$dir/HiveCellInterlock.tla" "$SPEC_DIR/HiveCellInterlock.tla"; then
    echo "  ERROR  $name -- mutation did not apply (spec text moved; fix the sed expr)"
    mut_missed=$((mut_missed + 1)); rc=1; return
  fi

  local out; out="$(tlc "$dir" "$cfg")"
  if passed "$out"; then
    echo "  MISSED $name -- NOT caught: $desc"
    mut_missed=$((mut_missed + 1)); rc=1
  else
    printf '  caught %-20s %-42s <= %s\n' "$name" "$(violation "$out")" "$desc"
    mut_caught=$((mut_caught + 1))
  fi
}

run_mutants() {
  MUT_WORK="$(mktemp -d)"
  trap 'rm -rf "$MUT_WORK"' RETURN

  # SF1 -- occupancy sensing and the ADR-0012 voting rules
  mutate sf1-ignored Safety \
    's|^Verdict(v) == .*|Verdict(v) == FALSE|' \
    'the FSM never consults life detection at all'
  mutate fault-reads-clear Safety \
    's|^Verdict(v) == .*|Verdict(v) == \\E c \\in Channels : v[c] = "OCCUPIED"|' \
    "a faulted channel stops failing safe (ADR-0012 'fault = occupied' dropped)"
  mutate majority-vote Safety \
    's|^Verdict(v) == .*|Verdict(v) == Cardinality({c \\in Channels : v[c] # "CLEAR"}) >= 2|' \
    "2-of-4 voting instead of ADR-0012 'AND toward clear'"

  # SF2 -- the independent contact backstop
  mutate sf2-ignored Safety \
    's|^Edge(ct)   == ct.*|Edge(ct) == FALSE|' \
    'the safety edge is never consulted -- removes the F1->F2 backstop'

  # SF4 -- fail-open drive
  mutate self-locking-drive Blackout \
    's|ELSE Max(progress - 1, Deployed).*|ELSE progress|' \
    'drive holds position without power (the design ADR-0009 rejected; FMEA F3)'
  mutate auto-restart Safety \
    's|ELSE "REDEPLOY"$|ELSE "CLEARING"|' \
    'releasing the E-stop resumes the sweep instead of backing out'

  # Motion integrity
  mutate snap-home Safety \
    "s|    /\\\\ progress' = Max(progress - 1, Deployed)|    /\\\\ progress' = Deployed|" \
    'the piston teleports home instead of reversing through its stroke'

  # Regression guard for what was finding F-1 (ADR-0022) -- this mutant IS the
  # pre-fix code, so if it ever stops being caught, the fix has been undone.
  mutate hold-ignores-trips Safety \
    's|    /\\ IF Verdict(v) \\/ Edge(ct) \\/ hold + 1 >= HoldTicks|    /\\ IF hold + 1 >= HoldTicks|' \
    'CLEARED_HOLD stops re-reading the trips -- the pre-ADR-0022 defect'

  # Liveness -- a frozen machine is safe but useless
  mutate frozen-sweep Liveness \
    "s|          /\\\\ progress' = Min(progress + 1, Flush)|          /\\\\ progress' = progress|" \
    'the machine never moves at all -- only the liveness run catches this'

  echo
  echo "run_modelcheck: mutants caught $mut_caught, missed $mut_missed"
}

case "$MODE" in
  green|deep) run_green ;;
  mutants)
    echo
    echo "=== mutation suite: every injected defect must be CAUGHT ==="
    run_mutants ;;
esac

echo
if [[ $rc -eq 0 ]]; then echo "run_modelcheck: OK"; else echo "run_modelcheck: FAILED"; fi
exit $rc
