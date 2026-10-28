// Temporal revenue accounting: local-validator round trip.
//
// Programs: SPL Stake Pool SPoo1... and the TruStake Staker 6EZAJ... are both CLONED from mainnet
// (production binaries; hashes recorded by run.sh). The Staker is initialised locally with throwaway
// keys (owner = agent), so its deposit path (whitelist + pause checks + DepositSol CPI signed by the
// deposit PDA) is the production code. The pool is configured like mainnet: stake and SOL deposit
// authority = Staker deposit PDA, SOL withdraw authority = the pool's own withdraw PDA (unsignable),
// epoch fee 5/100, stake/SOL withdrawal fee 1/1000, deposit fees 0.
//
// Deviations (recorded in results): the pool `staker` is a local key (not the Staker staker PDA), so
// stake allocation uses SPL directly; the "Jito claim" is a SystemProgram transfer to the validator
// stake account of the same kind of lamport credit (the mainnet claim debits the program-owned TDA and
// credits the claimant's lamports; neither changes stake data); the cluster is agave 2.0.15 with the
// LEGACY builtin Stake program and rent 2,282,880 (mainnet: Stake v5.1.0 BPF, rent 1,666,240).
//
// Usage: RPC_URL=http://127.0.0.1:28899 ts-node -T late_credit_roundtrip.ts > results.json

import * as borsh from "borsh";
import { createHash } from "crypto";
import {
  Connection, Keypair, LAMPORTS_PER_SOL, PublicKey, StakeProgram, SystemProgram, Transaction,
  TransactionInstruction, TransactionMessage, VersionedTransaction, VoteProgram, VoteInit,
  sendAndConfirmTransaction, ComputeBudgetProgram, Authorized, Lockup,
} from "@solana/web3.js";
import { TOKEN_PROGRAM_ID, createMint, getMint, getOrCreateAssociatedTokenAccount, getAccount } from "@solana/spl-token";
import { StakePoolInstruction, StakePoolLayout } from "@solana/spl-stake-pool";
import { Fee, InitializeData, InitializeSchema } from "../../../../tests/stake_pool/types";

const SPL = new PublicKey("SPoo1Ku8WFXoNDMHPsrGSTSG1Y47rzgn41SLUNakuHy");
const STAKER = new PublicKey("6EZAJVrNQdnBJU6ULxXSDaEoK6fN7C3iXTCkZKRWDdGM");
const TOKEN_2022 = new PublicKey("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb");
const RPC_URL = process.env.RPC_URL ?? "http://127.0.0.1:28899";
const connection = new Connection(RPC_URL, "confirmed");
const results: any = { rpc: RPC_URL, deviations: [], steps: [], checks: [], controls: [] };
const big = (x: any) => BigInt(x.toString());
const jsonable = (x: any) => JSON.parse(JSON.stringify(x, (_, v) => (typeof v === "bigint" ? v.toString() : v)));
const ceilDiv = (a: bigint, b: bigint) => (a + b - 1n) / b;
let failures = 0;
function check(name: string, cond: boolean, detail: any = {}) {
  results.checks.push(jsonable({ name, pass: cond, ...detail }));
  if (!cond) failures++;
}
const disc = (name: string) => createHash("sha256").update(`global:${name}`).digest().subarray(0, 8);
const pda = (seeds: Buffer[], prog = STAKER) => PublicKey.findProgramAddressSync(seeds, prog)[0];
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function airdrop(to: PublicKey, sol: number) {
  const sig = await connection.requestAirdrop(to, sol * LAMPORTS_PER_SOL);
  const bh = await connection.getLatestBlockhash();
  await connection.confirmTransaction({ signature: sig, ...bh }, "confirmed");
}
async function send(ixs: TransactionInstruction[], signers: Keypair[]) {
  const tx = new Transaction().add(...ixs);
  const bh = await connection.getLatestBlockhash("confirmed");
  tx.recentBlockhash = bh.blockhash; tx.feePayer = signers[0].publicKey; tx.sign(...signers);
  const sig = await connection.sendRawTransaction(tx.serialize(), { skipPreflight: true });
  await connection.confirmTransaction({ signature: sig, ...bh }, "confirmed");
  let info = null;
  for (let k = 0; k < 20 && !info; k++) { info = await connection.getTransaction(sig, { commitment: "confirmed", maxSupportedTransactionVersion: 0 }); if (!info) await sleep(300); }
  if (!info || info.meta?.err) {
    const e: any = new Error(`tx ${sig} failed: ${JSON.stringify(info?.meta?.err)} :: ${(info?.meta?.logMessages ?? []).slice(-6).join(" | ")}`);
    e.logs = info?.meta?.logMessages ?? [];
    throw e;
  }
  return { sig, fee: info.meta!.fee, slot: info.slot };
}
async function expectFail(name: string, ixs: TransactionInstruction[], signers: Keypair[]) {
  try {
    await send(ixs, signers);
    results.controls.push({ name, failed: false });
    check(`control fails: ${name}`, false);
  } catch (e: any) {
    const msg = String(e?.message ?? e);
    const logs: string[] = e?.logs ?? [];
    results.controls.push({ name, failed: true, error: msg.split(" :: ")[0].slice(0, 220), log_tail: logs.filter((l) => /Error|error|failed|Program log/.test(l)).slice(-3) });
    check(`control fails: ${name}`, true);
  }
}
async function waitFor(pred: (e: number, s: number) => boolean, label: string) {
  for (;;) {
    const i = await connection.getEpochInfo("confirmed");
    if (pred(i.epoch, i.slotIndex)) return i;
    await sleep(800);
  }
}

async function main() {
  const owner = Keypair.generate();       // Staker owner (agent) and pool manager/staker
  const cranker = Keypair.generate();     // no pool role at all: runs maintenance
  const incumbent = Keypair.generate();   // whitelisted, deposits first
  const depositor = Keypair.generate();   // whitelisted, enters in the late-credit window
  const depositor2 = Keypair.generate();  // whitelisted, credit+deposit in one transaction
  const depositor3 = Keypair.generate();  // whitelisted, maintenance+deposit in one transaction
  const outsider = Keypair.generate();    // not whitelisted
  const tipPayer = Keypair.generate();    // stands in for the program-owned tip distribution account
  for (const k of [owner, cranker, incumbent, depositor, depositor2, depositor3, outsider, tipPayer]) await airdrop(k.publicKey, 200);
  const stakeRent = BigInt(await connection.getMinimumBalanceForRentExemption(StakeProgram.space));
  results.env = { stakeRent, version: await connection.getVersion() };
  results.deviations.push(
    "pool staker = local owner key (mainnet: Staker staker PDA); stake moves via SPL directly",
    "late credit = SystemProgram transfer to the validator stake account (mainnet: Jito tip-distribution Claim, a program-owned lamport debit/credit; no stake-data change in either)",
    `legacy builtin Stake program, stake rent ${stakeRent} (mainnet: Stake v5.1.0 BPF, rent 1,666,240)`,
    "min delegation and epoch length are local-cluster values"
  );

  // ---- Staker initialisation (production binary, throwaway keys) -------------------------------
  const access = pda([Buffer.from("access")]);
  const eventAuthority = pda([Buffer.from("__event_authority")]);
  const agentOf = (k: PublicKey) => pda([Buffer.from("agent"), k.toBuffer()]);
  const userStatus = (k: PublicKey) => pda([Buffer.from("user"), k.toBuffer()]);
  const depositPda = pda([Buffer.from("deposit")]);
  await send([new TransactionInstruction({
    programId: STAKER, data: disc("initialize_staker"),
    keys: [
      { pubkey: owner.publicKey, isSigner: true, isWritable: true },
      { pubkey: access, isSigner: false, isWritable: true },
      { pubkey: agentOf(owner.publicKey), isSigner: false, isWritable: true },
      { pubkey: owner.publicKey, isSigner: false, isWritable: false },
      { pubkey: pda([Buffer.from("stake_manager"), owner.publicKey.toBuffer()]), isSigner: false, isWritable: true },
      { pubkey: owner.publicKey, isSigner: false, isWritable: false },
      { pubkey: TOKEN_2022, isSigner: false, isWritable: false },
      { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
      { pubkey: eventAuthority, isSigner: false, isWritable: false },
      { pubkey: STAKER, isSigner: false, isWritable: false },
    ],
  })], [owner]);
  for (const u of [incumbent, depositor, depositor2, depositor3]) {
    await send([new TransactionInstruction({
      programId: STAKER, data: Buffer.concat([disc("add_user_to_whitelist"), u.publicKey.toBuffer()]),
      keys: [
        { pubkey: owner.publicKey, isSigner: true, isWritable: true },
        { pubkey: userStatus(u.publicKey), isSigner: false, isWritable: true },
        { pubkey: agentOf(owner.publicKey), isSigner: false, isWritable: false },
        { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
        { pubkey: eventAuthority, isSigner: false, isWritable: false },
        { pubkey: STAKER, isSigner: false, isWritable: false },
      ],
    })], [owner]);
  }

  // ---- vote accounts: the local voting one (earns rewards) plus one fresh (does not vote) -------
  const votes: PublicKey[] = [new PublicKey((await connection.getVoteAccounts()).current[0].votePubkey)];
  {
    const vote = Keypair.generate(), node = Keypair.generate();
    await send(VoteProgram.createAccount({ fromPubkey: owner.publicKey, votePubkey: vote.publicKey, voteInit: new VoteInit(node.publicKey, owner.publicKey, owner.publicKey, 0), lamports: await connection.getMinimumBalanceForRentExemption(VoteProgram.space) }).instructions, [owner, vote, node]);
    votes.push(vote.publicKey);
  }

  // ---- pool, configured like mainnet -------------------------------------------------------------
  const poolKp = Keypair.generate(), listKp = Keypair.generate(), reserveKp = Keypair.generate();
  const pool = poolKp.publicKey;
  const [withdrawAuthority] = PublicKey.findProgramAddressSync([pool.toBuffer(), Buffer.from("withdraw")], SPL);
  const vStake = votes.map((v) => PublicKey.findProgramAddressSync([v.toBuffer(), pool.toBuffer()], SPL)[0]);
  const xStake = (i: number, seed: bigint) => { const b = Buffer.alloc(8); b.writeBigUInt64LE(seed); return PublicKey.findProgramAddressSync([Buffer.from("transient"), votes[i].toBuffer(), pool.toBuffer(), b], SPL)[0]; };
  const poolMint = await createMint(connection, owner, withdrawAuthority, null, 9);
  const managerFee = (await getOrCreateAssociatedTokenAccount(connection, owner, poolMint, owner.publicKey)).address;
  const ata: Record<string, PublicKey> = {};
  for (const [n, k] of [["incumbent", incumbent], ["depositor", depositor], ["depositor2", depositor2], ["depositor3", depositor3], ["outsider", outsider]] as [string, Keypair][]) {
    ata[n] = (await getOrCreateAssociatedTokenAccount(connection, k, poolMint, k.publicKey)).address;
  }
  const MAXV = 8, listSize = 4 + 5 + 73 * MAXV;
  await send([
    SystemProgram.createAccount({ fromPubkey: owner.publicKey, newAccountPubkey: pool, space: 8 + 656, lamports: await connection.getMinimumBalanceForRentExemption(8 + 656), programId: SPL }),
    SystemProgram.createAccount({ fromPubkey: owner.publicKey, newAccountPubkey: listKp.publicKey, space: listSize, lamports: await connection.getMinimumBalanceForRentExemption(listSize), programId: SPL }),
    ...StakeProgram.createAccount({ fromPubkey: owner.publicKey, stakePubkey: reserveKp.publicKey, lamports: Number(stakeRent), authorized: new Authorized(withdrawAuthority, withdrawAuthority), lockup: new Lockup(0, 0, PublicKey.default) }).instructions,
  ], [owner, poolKp, listKp, reserveKp]);
  const initData = new InitializeData({ instruction: 0, fee: new Fee({ numerator: 5, denominator: 100 }), withdrawalFee: new Fee({ numerator: 1, denominator: 1000 }), depositFee: new Fee({ numerator: 0, denominator: 100 }), referralFee: 0, maxValidators: MAXV });
  await send([new TransactionInstruction({
    programId: SPL,
    keys: [
      { pubkey: pool, isSigner: true, isWritable: true },
      { pubkey: owner.publicKey, isSigner: true, isWritable: false },
      { pubkey: owner.publicKey, isSigner: false, isWritable: false },
      { pubkey: withdrawAuthority, isSigner: false, isWritable: false },
      { pubkey: listKp.publicKey, isSigner: false, isWritable: true },
      { pubkey: reserveKp.publicKey, isSigner: false, isWritable: false },
      { pubkey: poolMint, isSigner: false, isWritable: true },
      { pubkey: managerFee, isSigner: false, isWritable: true },
      { pubkey: TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
      { pubkey: depositPda, isSigner: false, isWritable: false },   // stake deposit authority
    ],
    data: Buffer.from(borsh.serialize(InitializeSchema, initData)),
  })], [owner, poolKp]);
  const setFunding = (type: number, auth: PublicKey) => new TransactionInstruction({ programId: SPL, data: Buffer.from([15, type]), keys: [
    { pubkey: pool, isSigner: false, isWritable: true }, { pubkey: owner.publicKey, isSigner: true, isWritable: false }, { pubkey: auth, isSigner: false, isWritable: false }] });
  await send([setFunding(1, depositPda), setFunding(2, withdrawAuthority)], [owner]);

  const base = { stakePool: pool, withdrawAuthority, validatorList: listKp.publicKey, reserveStake: reserveKp.publicKey };
  const readList = async () => {
    const d = (await connection.getAccountInfo(listKp.publicKey, "confirmed"))!.data;
    const n = d.readUInt32LE(5);
    return Array.from({ length: n }, (_, i) => { const e = d.subarray(9 + 73 * i, 9 + 73 * (i + 1)); return { A: e.readBigUInt64LE(0), tau: e.readBigUInt64LE(8), lue: e.readBigUInt64LE(16), tseed: e.readBigUInt64LE(24) }; });
  };
  const pairs = async () => { const l = await readList(); return votes.flatMap((_, i) => [vStake[i], xStake(i, l[i].tseed)]); };
  const vlb = async (noMerge = false) => StakePoolInstruction.updateValidatorListBalance({ ...base, validatorAndTransientStakePairs: await pairs(), startIndex: 0, noMerge });
  const spb = () => StakePoolInstruction.updateStakePoolBalance({ ...base, managerFeeAccount: managerFee, poolMint });
  const stakerDeposit = (user: Keypair, userAta: PublicKey, amount: bigint) => {
    const data = Buffer.alloc(16); disc("deposit").copy(data, 0); data.writeBigUInt64LE(amount, 8);
    return new TransactionInstruction({ programId: STAKER, data, keys: [
      { pubkey: user.publicKey, isSigner: true, isWritable: true },
      { pubkey: userStatus(user.publicKey), isSigner: false, isWritable: true },
      { pubkey: access, isSigner: false, isWritable: true },
      { pubkey: pool, isSigner: false, isWritable: true },
      { pubkey: depositPda, isSigner: false, isWritable: true },
      { pubkey: withdrawAuthority, isSigner: false, isWritable: true },
      { pubkey: reserveKp.publicKey, isSigner: false, isWritable: true },
      { pubkey: userAta, isSigner: false, isWritable: true },
      { pubkey: managerFee, isSigner: false, isWritable: true },
      { pubkey: poolMint, isSigner: false, isWritable: true },
      { pubkey: managerFee, isSigner: false, isWritable: true },
      { pubkey: TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
      { pubkey: SPL, isSigner: false, isWritable: false },
      { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
      { pubkey: eventAuthority, isSigner: false, isWritable: false },
      { pubkey: STAKER, isSigner: false, isWritable: false },
    ] });
  };
  const tokenBal = async (a: PublicKey) => big((await getAccount(connection, a, "confirmed")).amount);
  const poolState = async () => StakePoolLayout.decode((await connection.getAccountInfo(pool, "confirmed"))!.data);
  async function thetaStar(): Promise<bigint | string> {
    const { blockhash } = await connection.getLatestBlockhash();
    const msg = new TransactionMessage({ payerKey: cranker.publicKey, recentBlockhash: blockhash, instructions: [await vlb(true), spb()] }).compileToV0Message();
    const sim = await connection.simulateTransaction(new VersionedTransaction(msg), { sigVerify: false, replaceRecentBlockhash: true, commitment: "confirmed", accounts: { encoding: "base64", addresses: [pool.toBase58()] } });
    if (sim.value.err) return JSON.stringify(sim.value.err);
    return big(StakePoolLayout.decode(Buffer.from(sim.value.accounts![0]!.data[0], "base64")).totalLamports);
  }
  async function snap(label: string, extra: any = {}) {
    const p = await poolState(); const info = await connection.getEpochInfo("confirmed");
    const mint = await getMint(connection, poolMint, "confirmed");
    const th = await thetaStar();
    const s = { label, E: info.epoch, slotIndex: info.slotIndex, lambda: big(p.lastUpdateEpoch), T: big(p.totalLamports), S: big(p.poolTokenSupply), Sigma: big(mint.supply),
      Theta: th, D_T: typeof th === "bigint" ? th - big(p.totalLamports) : null, reserve: (await connection.getBalance(reserveKp.publicKey, "confirmed")),
      V: await Promise.all(vStake.map((v) => connection.getBalance(v, "confirmed"))), feeTokens: await tokenBal(managerFee), ...extra };
    results.steps.push(jsonable(s));
    return s;
  }

  // ---- epoch 0: validators, incumbent deposit, stake allocation --------------------------------
  await send([SystemProgram.transfer({ fromPubkey: owner.publicKey, toPubkey: reserveKp.publicKey, lamports: 2 * (LAMPORTS_PER_SOL + Number(stakeRent)) })], [owner]);
  for (let i = 0; i < votes.length; i++) await send([StakePoolInstruction.addValidatorToPool({ ...base, staker: owner.publicKey, validatorStake: vStake[i], validatorVote: votes[i] })], [owner]);
  await send([stakerDeposit(incumbent, ata.incumbent, 60n * BigInt(LAMPORTS_PER_SOL))], [incumbent]);
  const tseed0 = 7n;
  await send([StakePoolInstruction.increaseValidatorStake({ ...base, staker: owner.publicKey, transientStake: xStake(0, tseed0), validatorStake: vStake[0], validatorVote: votes[0], lamports: 25 * LAMPORTS_PER_SOL, transientStakeSeed: Number(tseed0) })], [owner]);
  await send([StakePoolInstruction.increaseValidatorStake({ ...base, staker: owner.publicKey, transientStake: xStake(1, tseed0), validatorStake: vStake[1], validatorVote: votes[1], lamports: 25 * LAMPORTS_PER_SOL, transientStakeSeed: Number(tseed0) })], [owner]);
  results.setupEpoch = (await connection.getEpochInfo("confirmed")).epoch;

  // ---- epoch 1: merge transients ------------------------------------------------------------------
  let info = await waitFor((e, s) => e >= results.setupEpoch + 1 && s > 40, "epoch1");
  await send([ComputeBudgetProgram.setComputeUnitLimit({ units: 1_000_000 }), await vlb(false), spb()], [cranker]);
  await snap("epoch1 after merge maintenance");

  // ---- experiment epoch X: maintenance, late credit, deposits -----------------------------------
  info = await waitFor((e, s) => e >= results.setupEpoch + 2 && s > 1, "epochX-start");
  const X = info.epoch;
  // while stale, price-sensitive operations are refused
  await expectFail("Staker deposit while pool is stale (lambda < E)", [stakerDeposit(depositor, ata.depositor, BigInt(LAMPORTS_PER_SOL))], [depositor]);
  await waitFor((e, s) => e === X && s > 40, "past rewards");
  const m1 = await send([ComputeBudgetProgram.setComputeUnitLimit({ units: 1_000_000 }), await vlb(false), spb()], [cranker]);
  const sM = await snap("X: after complete maintenance (cranker, no role)", { tx: m1 });
  check("after complete maintenance D_T = 0 and pool fresh", sM.D_T === 0n && sM.lambda === BigInt(X));

  const z = 777_777_777n;   // late credit to V0 (e.g. claimed tips), sized to be visible
  const c1 = await send([SystemProgram.transfer({ fromPubkey: tipPayer.publicKey, toPubkey: vStake[0], lamports: Number(z) })], [tipPayer]);
  const sC = await snap("X: after late credit z to V0", { tx: c1 });
  check("late credit leaves the pool fresh with D_T = z", sC.lambda === BigInt(X) && sC.D_T === z, { D_T: sC.D_T });

  // credit to an account the pool does not observe (e.g. operator / vote account): no effect
  const c0 = await send([SystemProgram.transfer({ fromPubkey: tipPayer.publicKey, toPubkey: votes[1], lamports: 123_456_789 })], [tipPayer]);
  const sU = await snap("X: after credit to an unobserved account", { tx: c0 });
  check("credit to unobserved account changes neither T nor Theta*", sU.D_T === z && sU.T === sC.T);

  // honest counterfactual for the depositor: simulate [VLB, SPB, deposit] with the same L
  const L = 40n * BigInt(LAMPORTS_PER_SOL);
  {
    const { blockhash } = await connection.getLatestBlockhash();
    const msg = new TransactionMessage({ payerKey: depositor.publicKey, recentBlockhash: blockhash, instructions: [ComputeBudgetProgram.setComputeUnitLimit({ units: 1_000_000 }), await vlb(true), spb(), stakerDeposit(depositor, ata.depositor, L)] }).compileToV0Message();
    const sim = await connection.simulateTransaction(new VersionedTransaction(msg), { sigVerify: false, replaceRecentBlockhash: true, commitment: "confirmed", accounts: { encoding: "base64", addresses: [ata.depositor.toBase58(), pool.toBase58()] } });
    const amt = sim.value.err ? null : Buffer.from(sim.value.accounts![0]!.data[0], "base64").readBigUInt64LE(64);
    results.counterfactual = jsonable({ err: sim.value.err, minted_if_reconciled_first: amt, pool_after: sim.value.err ? null : (() => { const pp = StakePoolLayout.decode(Buffer.from(sim.value.accounts![1]!.data[0], "base64")); return { T: big(pp.totalLamports), S: big(pp.poolTokenSupply) }; })() });
  }
  const w0 = await connection.getBalance(depositor.publicKey, "confirmed");
  const pre = await poolState();
  const d1 = await send([stakerDeposit(depositor, ata.depositor, L)], [depositor]);
  const minted = await tokenBal(ata.depositor);
  const expected = (L * big(pre.poolTokenSupply)) / big(pre.totalLamports);
  check("window deposit mints floor(L*S/T) at the recorded (stale) price", minted === expected, { minted, expected });
  check("window deposit mints more than the honest counterfactual", results.counterfactual.minted_if_reconciled_first !== null && minted > BigInt(results.counterfactual.minted_if_reconciled_first), { minted, cf: results.counterfactual.minted_if_reconciled_first });
  const sD = await snap("X: after window deposit L", { tx: d1, minted });
  check("deposit leaves D_T unchanged (= z)", sD.D_T === z);

  // credit and deposit in one transaction (depositor2): still priced at T excluding the credit
  const z2 = 55_555_555n, L2 = 5n * BigInt(LAMPORTS_PER_SOL);
  const preB = await poolState();
  const d2 = await send([SystemProgram.transfer({ fromPubkey: depositor2.publicKey, toPubkey: vStake[1], lamports: Number(z2) }), stakerDeposit(depositor2, ata.depositor2, L2)], [depositor2]);
  const minted2 = await tokenBal(ata.depositor2);
  check("credit+deposit in one tx: minted at recorded price (credit unseen)", minted2 === (L2 * big(preB.poolTokenSupply)) / big(preB.totalLamports), { minted2 });
  const sD2 = await snap("X: after same-tx credit z2 + deposit", { tx: d2, minted2 });
  check("D_T = z + z2", sD2.D_T === z + z2);

  // maintenance and deposit in one transaction (depositor3): recognises z + z2 before minting
  const L3 = 5n * BigInt(LAMPORTS_PER_SOL);
  const d3 = await send([ComputeBudgetProgram.setComputeUnitLimit({ units: 1_000_000 }), await vlb(true), spb(), stakerDeposit(depositor3, ata.depositor3, L3)], [depositor3]);
  const minted3 = await tokenBal(ata.depositor3);
  const sD3 = await snap("X: after same-tx VLB+SPB+deposit (depositor3)", { tx: d3, minted3 });
  check("maintenance+deposit in one tx: D_T back to 0 and depositor3 priced at reconciled T", sD3.D_T === 0n);

  // controls: unprivileged routes into / out of the pool
  await expectFail("non-whitelisted user deposit via Staker", [stakerDeposit(outsider, ata.outsider, BigInt(LAMPORTS_PER_SOL))], [outsider]);
  await expectFail("direct SPL DepositSol without the deposit-authority signature", [StakePoolInstruction.depositSol({ ...base, fundingAccount: outsider.publicKey, destinationPoolAccount: ata.outsider, managerFeeAccount: managerFee, referralPoolAccount: managerFee, poolMint, lamports: LAMPORTS_PER_SOL })], [outsider]);
  await expectFail("WithdrawSol by a token holder (SOL withdraw authority = pool PDA)", [StakePoolInstruction.withdrawSol({ ...base, sourcePoolAccount: ata.depositor, sourceTransferAuthority: depositor.publicKey, destinationSystemAccount: depositor.publicKey, managerFeeAccount: managerFee, poolMint, poolTokens: Number(minted / 10n), solWithdrawAuthority: depositor.publicKey })], [depositor]);

  // ---- epoch X+1: rewards, recognition, redemption --------------------------------------------
  await waitFor((e, s) => e >= X + 1, "X+1");
  const sStale = await snap("X+1: before maintenance (stale)");
  {
    const tmp = Keypair.generate();
    await expectFail("WithdrawStake while stale (lambda < E)", [
      SystemProgram.createAccount({ fromPubkey: depositor.publicKey, newAccountPubkey: tmp.publicKey, lamports: Number(stakeRent), space: StakeProgram.space, programId: StakeProgram.programId }),
      StakePoolInstruction.withdrawStake({ ...base, validatorStake: vStake[0], destinationStake: tmp.publicKey, destinationStakeAuthority: depositor.publicKey, sourceTransferAuthority: depositor.publicKey, sourcePoolAccount: ata.depositor, managerFeeAccount: managerFee, poolMint, poolTokens: Number(minted) }),
    ], [depositor, tmp]);
  }
  await waitFor((e, s) => e === X + 1 && s > 40, "X+1 past rewards");
  const preM = await poolState();
  const feePre = await tokenBal(managerFee);
  const m2 = await send([ComputeBudgetProgram.setComputeUnitLimit({ units: 1_000_000 }), await vlb(false), spb()], [cranker]);
  const postM = await poolState();
  const feeMinted = (await tokenBal(managerFee)) - feePre;
  const r = big(postM.totalLamports) - big(preM.totalLamports);
  const phi = ceilDiv(r * 5n, 100n);
  const fExp = (big(preM.poolTokenSupply) * phi) / (big(preM.totalLamports) + r - phi);
  check("X+1 SPB epoch-fee mint equals floor(S*phi/(T+r-phi))", feeMinted === fExp, { r, phi, feeMinted, fExp });
  const sR = await snap("X+1: after recognition maintenance", { tx: m2, r, feeMinted });

  // depositor redeems everything by WithdrawStake, routed as SPL requires: validators first (each split
  // bounded by v - rent - min_delegation), the reserve only once no validator has lamports above tolerance
  const minDel = BigInt((await connection.getStakeMinimumDelegation("confirmed")).value);
  results.env.minDelegation = minDel;
  const exits: any[] = [];
  const dests: { kp: Keypair; fromReserve: boolean }[] = [];
  let remaining = minted;
  let exitFees = 0;
  for (let round = 0; remaining > 0n && round < 8; round++) {
    const ps = await poolState();
    const T = big(ps.totalLamports), S = big(ps.poolTokenSupply);
    const ellOf = (p: bigint) => ((p - ceilDiv(p, 1000n)) * T) / S;
    const vb = await Promise.all(vStake.map(async (v) => BigInt(await connection.getBalance(v, "confirmed"))));
    const order = [...vb.keys()].sort((x, y) => (vb[y] > vb[x] ? 1 : -1));
    let done = false;
    for (const src of [...order, -1]) {
      const spare = src === -1 ? BigInt(await connection.getBalance(reserveKp.publicKey, "confirmed")) - stakeRent : vb[src] - stakeRent - minDel;
      let lo = 0n, hi = remaining;
      while (lo < hi) { const mid = (lo + hi + 1n) / 2n; if (ellOf(mid) <= spare) lo = mid; else hi = mid - 1n; }
      if (lo === 0n || (src !== -1 && ellOf(lo) < minDel)) continue;
      const dest = Keypair.generate();
      try {
        const tx = await send([
          SystemProgram.createAccount({ fromPubkey: depositor.publicKey, newAccountPubkey: dest.publicKey, lamports: Number(stakeRent), space: StakeProgram.space, programId: StakeProgram.programId }),
          StakePoolInstruction.withdrawStake({ ...base, validatorStake: src === -1 ? reserveKp.publicKey : vStake[src], destinationStake: dest.publicKey, destinationStakeAuthority: depositor.publicKey, sourceTransferAuthority: depositor.publicKey, sourcePoolAccount: ata.depositor, managerFeeAccount: managerFee, poolMint, poolTokens: Number(lo) }),
        ], [depositor, dest]);
        const got = BigInt(await connection.getBalance(dest.publicKey, "confirmed")) - stakeRent;
        check(`WithdrawStake #${exits.length} (source ${src === -1 ? "reserve" : "V" + src}) pays floor((p - ceil(p/1000)) * T / S)`, got === ellOf(lo), { p: lo, got, expected: ellOf(lo) });
        exits.push({ source: src === -1 ? "reserve" : `V${src}`, p: lo, fee_tokens: ceilDiv(lo, 1000n), lamports: got, tx });
        exitFees += tx.fee; remaining -= lo; dests.push({ kp: dest, fromReserve: src === -1 }); done = true;
        break;
      } catch (e: any) {
        exits.push({ source: src === -1 ? "reserve" : `V${src}`, p: lo, rejected: String(e?.message ?? e).split(" :: ")[1]?.slice(0, 200) });
      }
    }
    if (!done) break;
  }
  check("depositor fully redeemed by WithdrawStake routing", remaining === 0n, { remaining });
  await snap("X+1: after depositor redemption", { exits: exits.length });
  for (const d of dests) if (!d.fromReserve) {
    const t = await send([StakeProgram.deactivate({ stakePubkey: d.kp.publicKey, authorizedPubkey: depositor.publicKey }).instructions[0]], [depositor]);
    exitFees += t.fee;
  }

  // ---- epoch X+2: withdraw SOL from every stake account ------------------------------------------
  await waitFor((e, s) => e >= X + 2 && s > 40, "X+2");
  let withdrawnTotal = 0n;
  for (const d of dests) {
    const bal = await connection.getBalance(d.kp.publicKey, "confirmed");
    const t = await send([StakeProgram.withdraw({ stakePubkey: d.kp.publicKey, authorizedPubkey: depositor.publicKey, toPubkey: depositor.publicKey, lamports: bal }).instructions[0]], [depositor]);
    exitFees += t.fee; withdrawnTotal += BigInt(bal) - stakeRent;
  }
  const w1 = await connection.getBalance(depositor.publicKey, "confirmed");
  const cf = BigInt(results.counterfactual.minted_if_reconciled_first);
  results.roundtrip = jsonable({ X, L, z, minted, cf_minted: cf, extra_tokens: minted - cf, exits, redeemed_lamports: withdrawnTotal,
    wallet_before_deposit: w0, wallet_after_final_withdraw: w1, realized_pnl_wallet: BigInt(w1) - BigInt(w0),
    tx_fees_after_deposit: exitFees + d1.fee, recognition_x1: { r, feeMinted } });
  results.verdict = failures === 0 ? "PASS" : `FAIL (${failures})`;
}

main().then(() => { console.log(JSON.stringify(jsonable(results), null, 1)); process.exit(failures ? 1 : 0); })
  .catch((e) => { results.fatal = String(e?.stack ?? e); console.log(JSON.stringify(jsonable(results), null, 1)); process.exit(2); });
