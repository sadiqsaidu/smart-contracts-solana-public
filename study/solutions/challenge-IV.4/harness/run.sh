#!/bin/bash
# Runs the Challenge IV.4 settlement-semantics harness against an isolated local validator.
#
# The validator clones the SPL Stake Pool program SPoo1... from mainnet-beta
# (read-only RPC fetch) and uses non-default ports so it cannot collide with a
# validator started by ./test.sh. Usage, from the repository root:
#
#   SOLANA_BIN=/path/to/solana-release/bin LEDGER_DIR=/some/tmp/dir \
#     study/solutions/challenge-IV.4/harness/run.sh > out.json
#
# Epochs are 1024 slots because SPL 2.1.x UpdateValidatorListBalance needs
# the EpochRewards sysvar, which a fresh local cluster only has after epoch 0.
# Setup (23 vote accounts, AddValidator x23) runs in epoch 0; experiments run in epoch 1.

set -euo pipefail

SOLANA_BIN=${SOLANA_BIN:?set SOLANA_BIN to a solana-release/bin directory}
LEDGER_DIR=${LEDGER_DIR:?set LEDGER_DIR to a scratch directory}
RPC_PORT=${RPC_PORT:-18899}
HARNESS_DIR="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$LEDGER_DIR"
"$SOLANA_BIN/solana-test-validator" \
  --ledger "$LEDGER_DIR/ledger" \
  --rpc-port "$RPC_PORT" \
  --faucet-port $((RPC_PORT + 1001)) \
  --gossip-port $((RPC_PORT + 1002)) \
  --dynamic-port-range $((RPC_PORT + 1010))-$((RPC_PORT + 1060)) \
  --clone-upgradeable-program SPoo1Ku8WFXoNDMHPsrGSTSG1Y47rzgn41SLUNakuHy \
  --url mainnet-beta \
  --slots-per-epoch "${SLOTS_PER_EPOCH:-1024}" \
  --reset --quiet > "$LEDGER_DIR/validator.log" 2>&1 &
VALIDATOR_PID=$!
trap 'kill $VALIDATOR_PID 2>/dev/null || true; wait $VALIDATOR_PID 2>/dev/null || true' EXIT

for _ in $(seq 1 90); do
  SLOT=$("$SOLANA_BIN/solana" slot -u "http://127.0.0.1:$RPC_PORT" --commitment confirmed 2>/dev/null || true)
  [ -n "$SLOT" ] && [ "$SLOT" -gt 10 ] && break
  sleep 1
done
echo "validator slot: ${SLOT:-none}" >&2
"$SOLANA_BIN/solana" program dump -u "http://127.0.0.1:$RPC_PORT" \
  SPoo1Ku8WFXoNDMHPsrGSTSG1Y47rzgn41SLUNakuHy "$LEDGER_DIR/spoo1-local.so" >&2
sha256sum "$LEDGER_DIR/spoo1-local.so" >&2

cd "$HARNESS_DIR/../../../.."
RPC_URL="http://127.0.0.1:$RPC_PORT" node_modules/.bin/ts-node -T "$HARNESS_DIR/settle_semantics.ts"
