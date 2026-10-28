// Challenge IV.4 local-validator harness: settlement semantics at the SPL level.
//
// There is no batch program here (anchor/cargo are not installed). Instead each
// experiment sends the exact SPL instruction sequence that the proposed `settle`
// instruction performs by CPI, as a client-composed transaction:
//     [ ...adversary pre-instructions, VLB(all pairs, no_merge=true), SPB, DepositSol(B) ]
// against the SPL Stake Pool binary cloned from mainnet, on a pool with 23 validators.
//
//   E1  atomic settle: same-transaction donations before the observation are priced in
//   E2  non-atomic settle ("first complete maintenance" price): stale mint after a credit
//   E3  settler passes one wrong (V,X) pair: VLB skips it silently, stale mint succeeds
//   E4  account-lock limit: settle-shaped transactions with 60, 64 and 65 accounts
//
// Theta* is measured by simulating [VLB(all, no_merge=true), SPB] and reading the
// simulated pool account. Cell caveat: agave 2.0.15, legacy Stake, rent 2,282,880.

import * as borsh from "borsh";
import { strict as assert } from "assert";
import {
  AddressLookupTableAccount,
  AddressLookupTableProgram,
  ComputeBudgetProgram,
  Connection,
  Keypair,
  LAMPORTS_PER_SOL,
  PublicKey,
  StakeProgram,
  SystemProgram,
  Transaction,
  TransactionInstruction,
  TransactionMessage,
  VersionedTransaction,
  VoteInit,
  VoteProgram,
  sendAndConfirmTransaction,
} from "@solana/web3.js";
import { TOKEN_PROGRAM_ID, createMint, getMint, getOrCreateAssociatedTokenAccount } from "@solana/spl-token";
import { StakePoolInstruction, StakePoolLayout } from "@solana/spl-stake-pool";
import { Fee, InitializeData, InitializeSchema } from "../../../../tests/stake_pool/types";

const SPL = new PublicKey("SPoo1Ku8WFXoNDMHPsrGSTSG1Y47rzgn41SLUNakuHy");
const RPC_URL = process.env.RPC_URL ?? "http://127.0.0.1:18899";
const N = Number(process.env.N_VALIDATORS ?? 23);
const connection = new Connection(RPC_URL, "confirmed");
const results: any = { rpc: RPC_URL, n: N, experiments: {} };

const big = (x: any) => BigInt(x.toString());
const json = (x: any) => JSON.parse(JSON.stringify(x, (_, v) => (typeof v === "bigint" ? v.toString() : v)));

async function airdrop(to: PublicKey, sol: number) {
  const sig = await connection.requestAirdrop(to, sol * LAMPORTS_PER_SOL);
  const bh = await connection.getLatestBlockhash();
  await connection.confirmTransaction({ signature: sig, ...bh }, "confirmed");
}

async function send(ixs: TransactionInstruction[], signers: Keypair[]) {
  return sendAndConfirmTransaction(connection, new Transaction().add(...ixs), signers, { commitment: "confirmed" });
}

async function sendV0(ixs: TransactionInstruction[], signers: Keypair[], alt: AddressLookupTableAccount) {
  const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash("confirmed");
  const msg = new TransactionMessage({ payerKey: signers[0].publicKey, recentBlockhash: blockhash, instructions: ixs }).compileToV0Message([alt]);
  const tx = new VersionedTransaction(msg);
  tx.sign(signers);
  const sig = await connection.sendTransaction(tx, { skipPreflight: false });
  const conf = await connection.confirmTransaction({ signature: sig, blockhash, lastValidBlockHeight }, "confirmed");
  if (conf.value.err) throw new Error(JSON.stringify(conf.value.err));
  const info = await connection.getTransaction(sig, { commitment: "confirmed", maxSupportedTransactionVersion: 0 });
  return { sig, size: tx.serialize().length, accounts: msg.staticAccountKeys.length + msg.addressTableLookups.reduce((a, l) => a + l.readonlyIndexes.length + l.writableIndexes.length, 0), cu: info?.meta?.computeUnitsConsumed };
}

async function main() {
  const manager = Keypair.generate();
  const adversary = Keypair.generate(); // no pool role
  const depositor = Keypair.generate(); // stands in for the batch funding PDA
  await airdrop(manager.publicKey, 500);
  await airdrop(adversary.publicKey, 400);
  await airdrop(depositor.publicKey, 400);

  // ---- vote accounts: the local one plus N-1 fresh ones ----------------------
  const votes: PublicKey[] = [new PublicKey((await connection.getVoteAccounts()).current[0].votePubkey)];
  const voteRent = await connection.getMinimumBalanceForRentExemption(VoteProgram.space);
  while (votes.length < N) {
    const ixs: TransactionInstruction[] = [];
    const signers: Keypair[] = [manager];
    for (let k = 0; k < 1 && votes.length + k < N; k++) {
      const vote = Keypair.generate();
      const node = Keypair.generate();
      ixs.push(...VoteProgram.createAccount({
        fromPubkey: manager.publicKey,
        votePubkey: vote.publicKey,
        voteInit: new VoteInit(node.publicKey, manager.publicKey, manager.publicKey, 0),
        lamports: voteRent,
      }).instructions);
      signers.push(vote, node);
      votes.push(vote.publicKey);
    }
    await send(ixs, signers);
  }
  votes.length = N;

  // ---- pool: no deposit authority, challenge fees -----------------------------
  const poolKp = Keypair.generate();
  const listKp = Keypair.generate();
  const reserveKp = Keypair.generate();
  const [withdrawAuthority] = PublicKey.findProgramAddressSync([poolKp.publicKey.toBuffer(), Buffer.from("withdraw")], SPL);
  const vStake = votes.map((v) => PublicKey.findProgramAddressSync([v.toBuffer(), poolKp.publicKey.toBuffer()], SPL)[0]);
  const xStake = votes.map((v) => PublicKey.findProgramAddressSync([Buffer.from("transient"), v.toBuffer(), poolKp.publicKey.toBuffer(), Buffer.alloc(8)], SPL)[0]);
  const poolMint = await createMint(connection, manager, withdrawAuthority, null, 9);
  const managerFee = (await getOrCreateAssociatedTokenAccount(connection, manager, poolMint, manager.publicKey)).address;
  const depositorAta = (await getOrCreateAssociatedTokenAccount(connection, depositor, poolMint, depositor.publicKey)).address;
  const MAXV = 32;
  const listSize = 4 + 5 + 73 * MAXV;
  const stakeRent = await connection.getMinimumBalanceForRentExemption(StakeProgram.space);
  await send([
    SystemProgram.createAccount({ fromPubkey: manager.publicKey, newAccountPubkey: poolKp.publicKey, space: 8 + 656, lamports: await connection.getMinimumBalanceForRentExemption(8 + 656), programId: SPL }),
    SystemProgram.createAccount({ fromPubkey: manager.publicKey, newAccountPubkey: listKp.publicKey, space: listSize, lamports: await connection.getMinimumBalanceForRentExemption(listSize), programId: SPL }),
    ...StakeProgram.createAccount({ fromPubkey: manager.publicKey, stakePubkey: reserveKp.publicKey, lamports: stakeRent, authorized: { staker: withdrawAuthority, withdrawer: withdrawAuthority }, lockup: { custodian: PublicKey.default, epoch: 0, unixTimestamp: 0 } }).instructions,
  ], [manager, poolKp, listKp, reserveKp]);
  const initData = new InitializeData({ instruction: 0, fee: new Fee({ numerator: 5, denominator: 100 }), withdrawalFee: new Fee({ numerator: 1, denominator: 1000 }), depositFee: new Fee({ numerator: 0, denominator: 100 }), referralFee: 0, maxValidators: MAXV });
  await send([new TransactionInstruction({
    programId: SPL,
    keys: [
      { pubkey: poolKp.publicKey, isSigner: true, isWritable: true },
      { pubkey: manager.publicKey, isSigner: true, isWritable: false },
      { pubkey: manager.publicKey, isSigner: false, isWritable: false },
      { pubkey: withdrawAuthority, isSigner: false, isWritable: false },
      { pubkey: listKp.publicKey, isSigner: false, isWritable: true },
      { pubkey: reserveKp.publicKey, isSigner: false, isWritable: false },
      { pubkey: poolMint, isSigner: false, isWritable: true },
      { pubkey: managerFee, isSigner: false, isWritable: true },
      { pubkey: TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
    ],
    data: Buffer.from(borsh.serialize(InitializeSchema, initData)),
  })], [manager, poolKp]);

  const base = { stakePool: poolKp.publicKey, withdrawAuthority, validatorList: listKp.publicKey, reserveStake: reserveKp.publicKey };
  const pairs = (wrong: number = -1) => votes.flatMap((_, i) => (i === wrong ? [Keypair.generate().publicKey, Keypair.generate().publicKey] : [vStake[i], xStake[i]]));
  const vlb = (wrong: number = -1) => StakePoolInstruction.updateValidatorListBalance({ ...base, validatorAndTransientStakePairs: pairs(wrong), startIndex: 0, noMerge: true });
  const spb = (pad: PublicKey[] = []) => {
    const ix = StakePoolInstruction.updateStakePoolBalance({ ...base, managerFeeAccount: managerFee, poolMint });
    ix.keys.push(...pad.map((pubkey) => ({ pubkey, isSigner: false, isWritable: false })));
    return ix;
  };
  const depositSol = (lamports: number) => StakePoolInstruction.depositSol({ ...base, fundingAccount: depositor.publicKey, destinationPoolAccount: depositorAta, managerFeeAccount: managerFee, referralPoolAccount: managerFee, poolMint, lamports });

  // fund the reserve and add every validator while still in epoch 0 (Add needs lambda = E only)
  const q = LAMPORTS_PER_SOL + stakeRent;
  await send([SystemProgram.transfer({ fromPubkey: manager.publicKey, toPubkey: reserveKp.publicKey, lamports: N * q + 60 * LAMPORTS_PER_SOL })], [manager]);
  for (let i = 0; i < N; i++) {
    await send([StakePoolInstruction.addValidatorToPool({ ...base, staker: manager.publicKey, validatorStake: vStake[i], validatorVote: votes[i] })], [manager]);
  }
  results.setupEpoch = (await connection.getEpochInfo("confirmed")).epoch;

  // address lookup table for everything except signers and top-level programs
  const slot = await connection.getSlot("finalized");
  const [createIx, altAddr] = AddressLookupTableProgram.createLookupTable({ authority: manager.publicKey, payer: manager.publicKey, recentSlot: slot });
  await send([createIx], [manager]);
  const pads = Array.from({ length: 8 }, () => Keypair.generate().publicKey);
  const altKeys = [poolKp.publicKey, withdrawAuthority, listKp.publicKey, reserveKp.publicKey, managerFee, poolMint, depositorAta, TOKEN_PROGRAM_ID, StakeProgram.programId,
    new PublicKey("SysvarC1ock11111111111111111111111111111111"), new PublicKey("SysvarStakeHistory1111111111111111111111111"), ...vStake, ...xStake, ...pads];
  for (let k = 0; k < altKeys.length; k += 20) {
    await send([AddressLookupTableProgram.extendLookupTable({ payer: manager.publicKey, authority: manager.publicKey, lookupTable: altAddr, addresses: altKeys.slice(k, k + 20) })], [manager]);
  }

  // ---- wait for epoch >= 1 (EpochRewards sysvar exists) ----------------------
  for (;;) {
    const info = await connection.getEpochInfo("confirmed");
    if (info.epoch >= 1 && info.slotIndex > 20) break;
    await new Promise((r) => setTimeout(r, 1000));
  }
  const alt = (await connection.getAddressLookupTable(altAddr)).value!;
  const E = (await connection.getEpochInfo("confirmed")).epoch;
  results.measuredEpoch = E;

  const readPool = async () => {
    const p = StakePoolLayout.decode((await connection.getAccountInfo(poolKp.publicKey, "confirmed"))!.data);
    return { T: big(p.totalLamports), S: big(p.poolTokenSupply), lambda: big(p.lastUpdateEpoch) };
  };
  const sigma = async () => big((await getMint(connection, poolMint, "confirmed")).supply);
  const observe = async (): Promise<{ theta: bigint; sigmaStar: bigint }> => {
    const { blockhash } = await connection.getLatestBlockhash();
    const msg = new TransactionMessage({ payerKey: adversary.publicKey, recentBlockhash: blockhash, instructions: [ComputeBudgetProgram.setComputeUnitLimit({ units: 1_400_000 }), vlb(), spb()] }).compileToV0Message([alt]);
    const sim = await connection.simulateTransaction(new VersionedTransaction(msg), { sigVerify: false, replaceRecentBlockhash: true, commitment: "confirmed", accounts: { encoding: "base64", addresses: [poolKp.publicKey.toBase58(), poolMint.toBase58()] } });
    if (sim.value.err) throw new Error("observe failed: " + JSON.stringify(sim.value.err) + (sim.value.logs ?? []).slice(-3).join(" | "));
    const pd = StakePoolLayout.decode(Buffer.from(sim.value.accounts![0]!.data[0], "base64"));
    const md = Buffer.from(sim.value.accounts![1]!.data[0], "base64");
    return { theta: big(pd.totalLamports), sigmaStar: md.readBigUInt64LE(36) };
  };
  const tokens = async () => big((await connection.getTokenAccountBalance(depositorAta, "confirmed")).value.amount);
  // exact transfer to the depositor, in lamports, at the post-state net true price
  const transferOf = async (minted: bigint, paid: bigint) => {
    const o = await observe();
    const num = minted * o.theta - paid * o.sigmaStar;
    return { transferNumerator: num, transferDenominator: o.sigmaStar, approxLamports: Number(num) / Number(o.sigmaStar), thetaAfter: o.theta, sigmaStarAfter: o.sigmaStar };
  };
  const cuIx = ComputeBudgetProgram.setComputeUnitLimit({ units: 1_400_000 });

  // initial complete maintenance (one transaction, N pairs)
  await sendV0([cuIx, vlb(), spb()], [manager], alt);
  const B = 30 * LAMPORTS_PER_SOL;
  const z = 20 * LAMPORTS_PER_SOL;

  // ---- E1: atomic settle; adversary donations in the same transaction, before the observation
  {
    const pre = await readPool();
    const obsPre = await observe();
    const tok0 = await tokens();
    const r = await sendV0([
      cuIx,
      SystemProgram.transfer({ fromPubkey: adversary.publicKey, toPubkey: vStake[5], lamports: z }),
      SystemProgram.transfer({ fromPubkey: adversary.publicKey, toPubkey: reserveKp.publicKey, lamports: 3_333_333 }),
      vlb(), spb(), depositSol(B),
    ], [depositor, adversary], alt);
    const post = await readPool();
    const minted = (await tokens()) - tok0;
    const tAtMint = post.T - BigInt(B);
    const sAtMint = post.S - minted;
    const obsPost = await observe();
    results.experiments.E1_atomic = json({
      tx: r, pre, post, thetaBefore: obsPre.theta, minted,
      tAtMint, sAtMint, priceIncludesDonations: tAtMint === obsPre.theta + BigInt(z) + 3_333_333n,
      mintedEqualsFloor: minted === (BigInt(B) * sAtMint) / tAtMint,
      DT_after: obsPost.theta - post.T, DS_after: post.S - (await sigma()),
      ...(await transferOf(minted, BigInt(B))),
    });
    assert.equal(minted, (BigInt(B) * sAtMint) / tAtMint);
    assert.equal(tAtMint, obsPre.theta + BigInt(z) + 3_333_333n);
    assert.equal(obsPost.theta, post.T);
  }

  // ---- E2: non-atomic: maintenance (tx1), credit to V_7 (tx2), DepositSol alone (tx3)
  {
    await sendV0([cuIx, vlb(), spb()], [manager], alt);                       // tx1, anyone
    await send([SystemProgram.transfer({ fromPubkey: adversary.publicKey, toPubkey: vStake[7], lamports: z })], [adversary]); // tx2
    const pre = await readPool();
    const obsPre = await observe();
    const tok0 = await tokens();
    await send([depositSol(B)], [depositor]);                                 // tx3
    const minted = (await tokens()) - tok0;
    const fairApprox = Number(BigInt(B) * obsPre.sigmaStar) / Number(obsPre.theta);
    results.experiments.E2_nonatomic = json({
      pre, thetaBefore: obsPre.theta, DT_at_mint: obsPre.theta - pre.T, minted, fairMintApprox: fairApprox,
      ...(await transferOf(minted, BigInt(B))),
    });
    assert.ok(obsPre.theta - pre.T >= BigInt(z));
  }

  // ---- E3: wrong pair for entry 9: VLB skips it, SPB succeeds (entries already fresh), stale mint
  {
    await sendV0([cuIx, vlb(), spb()], [manager], alt);                       // reconcile E2's gap
    await send([SystemProgram.transfer({ fromPubkey: adversary.publicKey, toPubkey: vStake[9], lamports: z })], [adversary]);
    const pre = await readPool();
    const obsPre = await observe();
    const tok0 = await tokens();
    const r = await sendV0([cuIx, vlb(9), spb(), depositSol(B)], [depositor], alt);
    const minted = (await tokens()) - tok0;
    const post = await readPool();
    results.experiments.E3_wrong_pair = json({
      tx: r, thetaBefore: obsPre.theta, tAtMint: post.T - BigInt(B), DT_at_mint: obsPre.theta - (post.T - BigInt(B)), minted,
      ...(await transferOf(minted, BigInt(B))),
    });
    assert.ok(obsPre.theta - (post.T - BigInt(B)) >= BigInt(z));
  }

  // ---- E4: account-lock limit for settle-shaped transactions --------------------
  {
    await sendV0([cuIx, vlb(), spb()], [manager], alt);
    // force a sweep CPI in every entry to measure the compute cost upper end
    for (let k = 0; k < N; k += 10) {
      await send(vStake.slice(k, k + 10).map((v) => SystemProgram.transfer({ fromPubkey: adversary.publicKey, toPubkey: v, lamports: 1_000_003 })), [adversary]);
    }
    const out: any = {};
    for (const pad of [0, 4, 5]) {
      try {
        const r = await sendV0([cuIx, vlb(), spb(pads.slice(0, pad)), depositSol(LAMPORTS_PER_SOL)], [depositor], alt);
        out[`pad${pad}`] = { ok: true, ...r };
      } catch (e: any) {
        out[`pad${pad}`] = { ok: false, error: String(e?.message ?? e).split("\n").slice(0, 2).join(" ") };
      }
    }
    results.experiments.E4_lock_limit = out;
  }

  results.epochAtEnd = (await connection.getEpochInfo("confirmed")).epoch;
  assert.equal(results.epochAtEnd, E, "epoch changed during the experiments");
  results.verdict = "PASS";
  console.log(JSON.stringify(json(results), null, 2));
}

main().catch((e) => {
  results.verdict = "FAIL";
  results.error = String(e?.stack ?? e);
  console.log(JSON.stringify(json(results), null, 2));
  process.exit(1);
});
