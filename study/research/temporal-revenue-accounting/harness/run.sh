#!/bin/bash
# Local round trip for the temporal revenue study. Clones the PRODUCTION SPL Stake Pool and TruStake
# Staker binaries from mainnet-beta (read-only fetch) into an isolated solana-test-validator.
#   SOLANA_BIN=/path/to/solana-release/bin LEDGER_DIR=/scratch/dir ./run.sh > results.json
set -euo pipefail
SOLANA_BIN=${SOLANA_BIN:?}; LEDGER_DIR=${LEDGER_DIR:?}; RPC_PORT=${RPC_PORT:-28899}
HARNESS_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$LEDGER_DIR"
"$SOLANA_BIN/solana-test-validator" --ledger "$LEDGER_DIR/ledger" --rpc-port "$RPC_PORT" \
  --faucet-port $((RPC_PORT + 1001)) --gossip-port $((RPC_PORT + 1002)) --dynamic-port-range $((RPC_PORT + 1010))-$((RPC_PORT + 1060)) \
  --clone-upgradeable-program SPoo1Ku8WFXoNDMHPsrGSTSG1Y47rzgn41SLUNakuHy \
  --clone-upgradeable-program 6EZAJVrNQdnBJU6ULxXSDaEoK6fN7C3iXTCkZKRWDdGM \
  --url mainnet-beta --slots-per-epoch "${SLOTS_PER_EPOCH:-400}" --reset --quiet > "$LEDGER_DIR/validator.log" 2>&1 &
VPID=$!
trap 'kill $VPID 2>/dev/null || true; wait $VPID 2>/dev/null || true' EXIT
for _ in $(seq 1 120); do
  SLOT=$("$SOLANA_BIN/solana" slot -u "http://127.0.0.1:$RPC_PORT" --commitment confirmed 2>/dev/null || true)
  [ -n "$SLOT" ] && [ "$SLOT" -gt 5 ] && break; sleep 1
done
echo "validator slot: ${SLOT:-none}" >&2
"$SOLANA_BIN/solana-test-validator" --version >&2
for P in SPoo1Ku8WFXoNDMHPsrGSTSG1Y47rzgn41SLUNakuHy 6EZAJVrNQdnBJU6ULxXSDaEoK6fN7C3iXTCkZKRWDdGM; do
  "$SOLANA_BIN/solana" program dump -u "http://127.0.0.1:$RPC_PORT" $P "$LEDGER_DIR/$P.so" >&2
  sha256sum "$LEDGER_DIR/$P.so" >&2
done
cd "$HARNESS_DIR/../../../.."
RPC_URL="http://127.0.0.1:$RPC_PORT" node_modules/.bin/ts-node -T "$HARNESS_DIR/late_credit_roundtrip.ts"
