// Challenge I.1 local-validator harness.
//
// Measures (T, S, Sigma, Theta*, lambda, E) on a real SPL Stake Pool cloned from
// mainnet (SPoo1...) and checks the signed gap changes D_T = Theta* - T and
// D_S = S - Sigma produced by single transactions inside one epoch.
//
// Theta* is obtained by SIMULATING [UpdateValidatorListBalance(no_merge=true), UpdateStakePoolBalance]
// and reading the simulated post-state of the stake pool account, so the
// observation itself does not mutate the ledger.
//
// Cell caveat: the local validator is agave 2.0.15 with the builtin (legacy)
// Stake program and rent 2,282,880 for a 200-byte stake account. This is NOT
// the mainnet-2026 cell (Stake v5, rho = 1,666,240). Only cell-independent SPL
// accounting is evidenced here. See ../VERIFICATION.md.
//
// Usage: RPC_URL=http://127.0.0.1:18899 npx ts-node -T harness/two_ledgers.ts > out.json

import * as borsh from "borsh";
import { strict as assert } from "assert";
import {
  Connection,
  Keypair,
  LAMPORTS_PER_SOL,
  PublicKey,
  StakeProgram,
  SystemProgram,
  Transaction,
  TransactionInstruction,
  VersionedTransaction,
  TransactionMessage,
  sendAndConfirmTransaction,
} from "@solana/web3.js";
import {
  TOKEN_PROGRAM_ID,
  createMint,
  getOrCreateAssociatedTokenAccount,
  createBurnInstruction,
  createMintToInstruction,
  getMint,
} from "@solana/spl-token";
import { StakePoolInstruction, StakePoolLayout } from "@solana/spl-stake-pool";
import { Fee, InitializeData, InitializeSchema } from "../../../../tests/stake_pool/types";

const STAKE_POOL_PROGRAM_ID = new PublicKey("SPoo1Ku8WFXoNDMHPsrGSTSG1Y47rzgn41SLUNakuHy");
const RPC_URL = process.env.RPC_URL ?? "http://127.0.0.1:18899";
const connection = new Connection(RPC_URL, "confirmed");

type Snapshot = {
  label: string;
  E: number;
  lambda: bigint;
  T: bigint;
  S: bigint;
  Sigma: bigint;
  Theta: bigint | null;
  thetaError: string | null;
  DT: bigint | null;
  DS: bigint;
  reserve: number;
  validatorStake: number;
};

const results: any = { rpc: RPC_URL, steps: [] as any[], falsification: [] as any[] };

function jsonable(x: any): any {
  return JSON.parse(JSON.stringify(x, (_, v) => (typeof v === "bigint" ? v.toString() : v)));
}

async function airdrop(to: PublicKey, sol: number) {
  const sig = await connection.requestAirdrop(to, sol * LAMPORTS_PER_SOL);
  const bh = await connection.getLatestBlockhash();
  await connection.confirmTransaction({ signature: sig, ...bh }, "confirmed");
}

async function send(ixs: TransactionInstruction[], signers: Keypair[]) {
  const tx = new Transaction().add(...ixs);
  return sendAndConfirmTransaction(connection, tx, signers, { commitment: "confirmed" });
}

async function main() {
  const manager = Keypair.generate(); // also staker and fee-account owner
  const anyone = Keypair.generate(); // no pool role at all
  const holder = Keypair.generate(); // ordinary TruSOL-like holder
  await airdrop(manager.publicKey, 100);
  await airdrop(anyone.publicKey, 10);
  await airdrop(holder.publicKey, 10);

  const voteAccounts = await connection.getVoteAccounts();
  const vote = new PublicKey(voteAccounts.current[0].votePubkey);

  const stakePoolKp = Keypair.generate();
  const validatorListKp = Keypair.generate();
  const reserveKp = Keypair.generate();
  const [withdrawAuthority] = PublicKey.findProgramAddressSync(
    [stakePoolKp.publicKey.toBuffer(), Buffer.from("withdraw")],
    STAKE_POOL_PROGRAM_ID
  );
  const [validatorStake] = PublicKey.findProgramAddressSync(
    [vote.toBuffer(), stakePoolKp.publicKey.toBuffer()],
    STAKE_POOL_PROGRAM_ID
  );
  // transient_seed_suffix stays 0: no Increase/Decrease is executed in this harness
  const [transientStake] = PublicKey.findProgramAddressSync(
    [Buffer.from("transient"), vote.toBuffer(), stakePoolKp.publicKey.toBuffer(), Buffer.alloc(8)],
    STAKE_POOL_PROGRAM_ID
  );

  const poolMint = await createMint(connection, manager, withdrawAuthority, null, 9);
  const managerFee = (await getOrCreateAssociatedTokenAccount(connection, manager, poolMint, manager.publicKey)).address;
  const holderAta = (await getOrCreateAssociatedTokenAccount(connection, holder, poolMint, holder.publicKey)).address;

  const MAX_VALIDATORS = 4;
  const listSize = 4 + 5 + 73 * MAX_VALIDATORS;
  const stakeRent = await connection.getMinimumBalanceForRentExemption(StakeProgram.space);
  results.stakeAccountRent = stakeRent;
  await send(
    [
      SystemProgram.createAccount({
        fromPubkey: manager.publicKey,
        newAccountPubkey: stakePoolKp.publicKey,
        space: 8 + 656,
        lamports: await connection.getMinimumBalanceForRentExemption(8 + 656),
        programId: STAKE_POOL_PROGRAM_ID,
      }),
      SystemProgram.createAccount({
        fromPubkey: manager.publicKey,
        newAccountPubkey: validatorListKp.publicKey,
        space: listSize,
        lamports: await connection.getMinimumBalanceForRentExemption(listSize),
        programId: STAKE_POOL_PROGRAM_ID,
      }),
      StakeProgram.createAccount({
        fromPubkey: manager.publicKey,
        stakePubkey: reserveKp.publicKey,
        lamports: stakeRent,
        authorized: { staker: withdrawAuthority, withdrawer: withdrawAuthority },
        lockup: { custodian: PublicKey.default, epoch: 0, unixTimestamp: 0 },
      }),
    ],
    [manager, stakePoolKp, validatorListKp, reserveKp]
  );

  // Challenge fees: e = 5/100, w = 1/1000, d = 0, referral 0. No deposit authority.
  const initData = new InitializeData({
    instruction: 0,
    fee: new Fee({ numerator: 5, denominator: 100 }),
    withdrawalFee: new Fee({ numerator: 1, denominator: 1000 }),
    depositFee: new Fee({ numerator: 0, denominator: 100 }),
    referralFee: 0,
    maxValidators: MAX_VALIDATORS,
  });
  await send(
    [
      new TransactionInstruction({
        programId: STAKE_POOL_PROGRAM_ID,
        keys: [
          { pubkey: stakePoolKp.publicKey, isSigner: true, isWritable: true },
          { pubkey: manager.publicKey, isSigner: true, isWritable: false },
          { pubkey: manager.publicKey, isSigner: false, isWritable: false },
          { pubkey: withdrawAuthority, isSigner: false, isWritable: false },
          { pubkey: validatorListKp.publicKey, isSigner: false, isWritable: true },
          { pubkey: reserveKp.publicKey, isSigner: false, isWritable: false },
          { pubkey: poolMint, isSigner: false, isWritable: true },
          { pubkey: managerFee, isSigner: false, isWritable: true },
          { pubkey: TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
        ],
        data: Buffer.from(borsh.serialize(InitializeSchema, initData)),
      }),
    ],
    [manager, stakePoolKp]
  );

  const base = {
    stakePool: stakePoolKp.publicKey,
    withdrawAuthority,
    validatorList: validatorListKp.publicKey,
    reserveStake: reserveKp.publicKey,
  };
  const vlbIx = (noMerge: boolean, pairs = [validatorStake, transientStake]) =>
    StakePoolInstruction.updateValidatorListBalance({
      ...base,
      validatorAndTransientStakePairs: pairs,
      startIndex: 0,
      noMerge,
    });
  const spbIx = () => StakePoolInstruction.updateStakePoolBalance({ ...base, managerFeeAccount: managerFee, poolMint });

  // fund the reserve and add the local validator (staker = manager)
  await send([SystemProgram.transfer({ fromPubkey: manager.publicKey, toPubkey: reserveKp.publicKey, lamports: 20 * LAMPORTS_PER_SOL })], [manager]);
  await send(
    [
      StakePoolInstruction.addValidatorToPool({
        ...base,
        staker: manager.publicKey,
        validatorStake,
        validatorVote: vote,
      }),
    ],
    [manager]
  );
  // (d) evidence: before the first epoch boundary the EpochRewards sysvar is unavailable on a
  // fresh local cluster, so UpdateValidatorListBalance fails even with no_merge = true.
  try {
    await send([vlbIx(true)], [anyone]);
    results.epoch0Vlb = { succeeded: true };
  } catch (e: any) {
    results.epoch0Vlb = {
      succeeded: false,
      epoch: (await connection.getEpochInfo("confirmed")).epoch,
      error: String(e?.message ?? e).split("\n").slice(0, 2).join(" "),
    };
  }
  // run every measured step inside one epoch >= 1, past the reward-distribution slots
  for (;;) {
    const info = await connection.getEpochInfo("confirmed");
    if (info.epoch >= 1 && info.slotIndex > 20) break;
    await new Promise((r) => setTimeout(r, 1000));
  }
  // bring the pool to a reconciled fresh state
  await send([vlbIx(false), spbIx()], [manager]);
  // the holder obtains pool tokens through a permissionless DepositSol
  await send(
    [
      StakePoolInstruction.depositSol({
        ...base,
        fundingAccount: holder.publicKey,
        destinationPoolAccount: holderAta,
        managerFeeAccount: managerFee,
        referralPoolAccount: managerFee,
        poolMint,
        lamports: 3 * LAMPORTS_PER_SOL,
      }),
    ],
    [holder]
  );

  const decodePool = (data: Buffer) => StakePoolLayout.decode(data);

  async function observeTheta(pairs?: PublicKey[]): Promise<{ theta: bigint | null; err: string | null; logs?: string[] }> {
    const { blockhash } = await connection.getLatestBlockhash();
    const msg = new TransactionMessage({
      payerKey: anyone.publicKey,
      recentBlockhash: blockhash,
      instructions: [vlbIx(true, pairs), spbIx()],
    }).compileToV0Message();
    const sim = await connection.simulateTransaction(new VersionedTransaction(msg), {
      sigVerify: false,
      replaceRecentBlockhash: true,
      commitment: "confirmed",
      accounts: { encoding: "base64", addresses: [stakePoolKp.publicKey.toBase58()] },
    });
    if (sim.value.err) return { theta: null, err: JSON.stringify(sim.value.err), logs: sim.value.logs ?? [] };
    const acct = sim.value.accounts![0]!;
    const data = Buffer.from(acct.data[0], "base64");
    return { theta: BigInt(decodePool(data).totalLamports.toString()), err: null };
  }

  async function snapshot(label: string): Promise<Snapshot> {
    const poolInfo = await connection.getAccountInfo(stakePoolKp.publicKey, "confirmed");
    const pool = decodePool(poolInfo!.data);
    const mint = await getMint(connection, poolMint, "confirmed");
    const E = (await connection.getEpochInfo("confirmed")).epoch;
    const obs = await observeTheta();
    const T = BigInt(pool.totalLamports.toString());
    const S = BigInt(pool.poolTokenSupply.toString());
    const Sigma = BigInt(mint.supply.toString());
    const snap: Snapshot = {
      label,
      E,
      lambda: BigInt(pool.lastUpdateEpoch.toString()),
      T,
      S,
      Sigma,
      Theta: obs.theta,
      thetaError: obs.err,
      DT: obs.theta === null ? null : obs.theta - T,
      DS: S - Sigma,
      reserve: await connection.getBalance(reserveKp.publicKey, "confirmed"),
      validatorStake: await connection.getBalance(validatorStake, "confirmed"),
    };
    results.steps.push(jsonable(snap));
    return snap;
  }

  const fresh = (s: Snapshot) => assert.equal(s.lambda, BigInt(s.E), `${s.label}: pool not fresh`);

  // W0: reconciled fresh baseline
  const s0 = await snapshot("W0 baseline after VLB+SPB and a DepositSol");
  fresh(s0);
  assert.equal(s0.DT, 0n);
  assert.equal(s0.DS, 0n);

  // W1: anyone donates to the reserve with a System transfer -> D_T += delta
  const d1 = 1_234_567;
  await send([SystemProgram.transfer({ fromPubkey: anyone.publicKey, toPubkey: reserveKp.publicKey, lamports: d1 })], [anyone]);
  const s1 = await snapshot("W1 System transfer to reserve by unprivileged signer");
  fresh(s1);
  assert.equal(s1.DT! - s0.DT!, BigInt(d1));
  assert.equal(s1.DS - s0.DS, 0n);

  // N1: an unprivileged signer neutralizes it later with VLB+SPB; record the epoch-fee mint
  const preMint = s1.Sigma;
  await send([vlbIx(false), spbIx()], [anyone]);
  const n1 = await snapshot("N1 later permissionless VLB+SPB by unprivileged signer");
  fresh(n1);
  assert.equal(n1.DT, 0n);
  assert.equal(n1.DS, 0n);
  results.n1FeeMinted = (n1.Sigma - preMint).toString();
  // exact upstream fee: r = C - T, phi = ceil(5r/100), f = floor(S*phi/(T + r - phi))
  {
    const r = BigInt(d1);
    const phi = (5n * r + 99n) / 100n;
    const f = (s1.S * phi) / (s1.T + r - phi);
    results.n1FeePredicted = f.toString();
    assert.equal(n1.Sigma - preMint, f);
  }

  // W2: holder burns k pool tokens directly through SPL Token -> D_S += k, Sigma drops, S does not
  const k = 7n;
  await send([createBurnInstruction(holderAta, poolMint, holder.publicKey, k)], [holder]);
  const s2 = await snapshot("W2 SPL Token Burn of 7 base units by holder");
  fresh(s2);
  assert.equal(s2.DS - n1.DS, k);
  assert.equal(s2.DT, 0n);

  // N2: SPB alone re-syncs S := Sigma (no reward, so no fee)
  await send([spbIx()], [anyone]);
  const n2 = await snapshot("N2 later permissionless SPB alone");
  fresh(n2);
  assert.equal(n2.DS, 0n);
  assert.equal(n2.DT, 0n);

  // W3: anyone donates to the listed validator stake account -> D_T += delta via the observation's sweep
  const d3 = 777_777;
  await send([SystemProgram.transfer({ fromPubkey: anyone.publicKey, toPubkey: validatorStake, lamports: d3 })], [anyone]);
  const s3 = await snapshot("W3 System transfer to listed validator stake account");
  fresh(s3);
  assert.equal(s3.DT! - n2.DT!, BigInt(d3));

  // W3b: a VLB(no_merge=true) whose pair addresses are wrong succeeds but observes nothing
  const bogus = await observeTheta([Keypair.generate().publicKey, Keypair.generate().publicKey]);
  results.wrongPairObservation = { theta: bogus.theta?.toString() ?? null, err: bogus.err, T: s3.T.toString() };
  assert.equal(bogus.err, null);
  assert.equal(bogus.theta, s3.T); // misses the d3 donation entirely

  // D1: a real VLB(no_merge=true) alone mutates lamports: the sweep moves d3 from V to the reserve
  const vBefore = s3.validatorStake;
  const rBefore = s3.reserve;
  await send([vlbIx(true)], [anyone]);
  const vAfter = await connection.getBalance(validatorStake, "confirmed");
  const rAfter = await connection.getBalance(reserveKp.publicKey, "confirmed");
  results.noMergeMutation = { vBefore, vAfter, rBefore, rAfter };
  assert.equal(vBefore - vAfter, d3);
  assert.equal(rAfter - rBefore, d3);
  await send([spbIx()], [anyone]);
  const n3 = await snapshot("N3 after real VLB(no_merge) sweep then SPB");
  fresh(n3);
  assert.equal(n3.DT, 0n);
  assert.equal(n3.DS, 0n);

  // W4: atomic neutralization: donor composes donation + VLB + SPB in one transaction
  const d4 = 4_242;
  await send(
    [SystemProgram.transfer({ fromPubkey: anyone.publicKey, toPubkey: reserveKp.publicKey, lamports: d4 }), vlbIx(true), spbIx()],
    [anyone]
  );
  const s4 = await snapshot("W4 donation+VLB+SPB in one transaction");
  fresh(s4);
  assert.equal(s4.DT, 0n);
  assert.equal(s4.DS, 0n);

  // W5: DepositSol and WithdrawSol leave both gaps unchanged (exact)
  await send([SystemProgram.transfer({ fromPubkey: anyone.publicKey, toPubkey: reserveKp.publicKey, lamports: 999 })], [anyone]);
  const pre5 = await snapshot("W5 pre: reserve donation 999 to make D_T nonzero");
  await send(
    [
      StakePoolInstruction.depositSol({
        ...base,
        fundingAccount: holder.publicKey,
        destinationPoolAccount: holderAta,
        managerFeeAccount: managerFee,
        referralPoolAccount: managerFee,
        poolMint,
        lamports: 123_456_789,
      }),
    ],
    [holder]
  );
  const s5a = await snapshot("W5a DepositSol 123,456,789 lamports");
  assert.equal(s5a.DT, pre5.DT);
  assert.equal(s5a.DS, pre5.DS);
  await send(
    [
      StakePoolInstruction.withdrawSol({
        ...base,
        sourcePoolAccount: holderAta,
        destinationSystemAccount: holder.publicKey,
        sourceTransferAuthority: holder.publicKey,
        managerFeeAccount: managerFee,
        poolMint,
        poolTokens: 100_000_003,
      }),
    ],
    [holder]
  );
  const s5b = await snapshot("W5b WithdrawSol 100,000,003 pool tokens");
  assert.equal(s5b.DT, pre5.DT);
  assert.equal(s5b.DS, pre5.DS);
  fresh(s5b);

  // Falsification attempts: an unprivileged signer tries to reduce Theta* or raise Sigma
  async function attempt(label: string, ixs: TransactionInstruction[], signers: Keypair[]) {
    try {
      await send(ixs, signers);
      results.falsification.push({ label, succeeded: true });
    } catch (e: any) {
      const logs: string[] = e?.logs ?? e?.transactionLogs ?? [];
      results.falsification.push({
        label,
        succeeded: false,
        error: String(e?.transactionMessage ?? e?.message ?? e).split("\n")[0],
        logs: logs.filter((l) => !l.endsWith("invoke [1]")),
      });
    }
  }
  await attempt(
    "Stake Withdraw from reserve signed by unprivileged key",
    StakeProgram.withdraw({ stakePubkey: reserveKp.publicKey, authorizedPubkey: anyone.publicKey, toPubkey: anyone.publicKey, lamports: 1 }).instructions,
    [anyone]
  );
  await attempt(
    "Stake Withdraw from validator stake signed by unprivileged key",
    StakeProgram.withdraw({ stakePubkey: validatorStake, authorizedPubkey: anyone.publicKey, toPubkey: anyone.publicKey, lamports: 1 }).instructions,
    [anyone]
  );
  await attempt("SPL Token MintTo signed by unprivileged key", [createMintToInstruction(poolMint, holderAta, anyone.publicKey, 1n)], [anyone]);
  await attempt(
    "System transfer out of reserve (stake-owned) claiming reserve as signer",
    [SystemProgram.transfer({ fromPubkey: reserveKp.publicKey, toPubkey: anyone.publicKey, lamports: 1 })],
    [anyone]
  );
  for (const f of results.falsification) assert.equal(f.succeeded, false, f.label);
  const sEnd = await snapshot("END after falsification attempts");
  assert.equal(sEnd.DT, s5b.DT);
  assert.equal(sEnd.DS, s5b.DS);

  results.epochConstant = new Set(results.steps.map((s: any) => s.E)).size === 1;
  assert.ok(results.epochConstant, "epoch changed during the run");
  results.verdict = "PASS";
  console.log(JSON.stringify(results, null, 2));
}

main().catch((e) => {
  results.verdict = "FAIL";
  results.error = String(e?.stack ?? e);
  console.log(JSON.stringify(jsonable(results), null, 2));
  process.exit(1);
});
