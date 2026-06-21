#!/bin/zsh
# Reproduce the reach-chain feasibility PoC with real souffle.
# Usage: ./run.sh   (run from this directory)
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SOUFFLE="${SOUFFLE:-/opt/homebrew/bin/souffle}"
WORK="$(mktemp -d)"
mkdir -p "$WORK/facts" "$WORK/out"

# facts (TSV) — three subjects: C-EVE (na fails @td<90, fo holds), C-M1 (both hold), C-DANA (fo fails @amt>=20000)
printf 'C-EVE\ta_eve_c\nC-M1\ta_m1_c\nC-DANA\ta_dana_c\n'                                  > "$WORK/facts/customer.facts"
printf 'C-EVE\t2000\ta_eve_t\nC-M1\t20\ta_m1_t\nC-DANA\t1200\ta_dana_t\n'                  > "$WORK/facts/tenure.facts"
printf 'Eo\tC-EVE\tout\t28000\ta_eo\nM1o\tC-M1\tout\t28000\ta_m1o\nD1\tC-DANA\tin\t5000\ta_d1\nDo\tC-DANA\tout\t4000\ta_do\n' > "$WORK/facts/transfer.facts"
printf 'C-EVE\nC-M1\nC-DANA\n'                                                            > "$WORK/facts/subject.facts"

"$SOUFFLE" -F "$WORK/facts" -D "$WORK/out" "$HERE/reach.dl"

echo "===== new_account branch ====="
for r in na_r1 na_r2 na_r3; do echo "--- $r ---"; sed 's/\t/  |  /g' "$WORK/out/$r.csv" 2>/dev/null; done
echo
echo "===== forwards_out branch ====="
for r in fo_r2 fo_r3 fo_r4; do echo "--- $r ---"; sed 's/\t/  |  /g' "$WORK/out/$r.csv" 2>/dev/null; done
rm -rf "$WORK"
