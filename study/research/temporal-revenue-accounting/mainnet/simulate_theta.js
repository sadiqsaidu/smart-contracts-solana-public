// Read-only SIMULATION on mainnet (no signature, no state change):
// [UpdateValidatorListBalance(no_merge=true, all entries), UpdateStakePoolBalance]
// returns the simulated post-state of the pool, manager-fee token account, reserve and validator stakes.
// Fee payer = a public permissionless crank key that already submits this exact sequence every epoch;
// sigVerify=false means no key is used and nothing is sent.
const { Connection, PublicKey, TransactionMessage, VersionedTransaction, ComputeBudgetProgram } = require("@solana/web3.js");
const { StakePoolInstruction, StakePoolLayout } = require("@solana/spl-stake-pool");
const c = new Connection(process.env.RPC_URL || "https://api.mainnet-beta.solana.com", "confirmed");
const POOL = new PublicKey("EyKyx9LKz7Qbp6PSbBRoMdt8iNYp8PvFVupQTQRMY9AM");
const SPL = new PublicKey("SPoo1Ku8WFXoNDMHPsrGSTSG1Y47rzgn41SLUNakuHy");
const PAYER = new PublicKey(process.env.PAYER || "4X8avqCKvNxb2a57pPV9nGJNfRQtETgBn7a7iyuNyjaH");
const u64 = (n) => { const b = Buffer.alloc(8); b.writeBigUInt64LE(BigInt(n)); return b; };
const u32 = (n) => { const b = Buffer.alloc(4); b.writeUInt32LE(n); return b; };
(async () => {
  const pi = await c.getAccountInfo(POOL);
  const pool = StakePoolLayout.decode(pi.data);
  const vlData = (await c.getAccountInfo(pool.validatorList)).data;
  const n = vlData.readUInt32LE(5); const pairs = []; const vs = [];
  for (let i = 0; i < n; i++) {
    const e = vlData.subarray(9 + 73 * i, 9 + 73 * (i + 1));
    const vote = new PublicKey(e.subarray(41, 73)); const vss = e.readUInt32LE(36);
    const [stake] = PublicKey.findProgramAddressSync([vote.toBuffer(), POOL.toBuffer(), ...(vss ? [u32(vss)] : [])], SPL);
    const [tr] = PublicKey.findProgramAddressSync([Buffer.from("transient"), vote.toBuffer(), POOL.toBuffer(), u64(e.readBigUInt64LE(24))], SPL);
    pairs.push(stake, tr); vs.push(stake);
  }
  const [withdrawAuthority] = PublicKey.findProgramAddressSync([POOL.toBuffer(), Buffer.from("withdraw")], SPL);
  const base = { stakePool: POOL, withdrawAuthority, validatorList: pool.validatorList, reserveStake: pool.reserveStake };
  const ixs = [ComputeBudgetProgram.setComputeUnitLimit({ units: 1_400_000 }),
    StakePoolInstruction.updateValidatorListBalance({ ...base, validatorAndTransientStakePairs: pairs, startIndex: 0, noMerge: true }),
    StakePoolInstruction.updateStakePoolBalance({ ...base, managerFeeAccount: pool.managerFeeAccount, poolMint: pool.poolMint })];
  const { blockhash } = await c.getLatestBlockhash();
  const msg = new TransactionMessage({ payerKey: PAYER, recentBlockhash: blockhash, instructions: ixs }).compileToV0Message();
  const watch = [POOL, pool.managerFeeAccount, pool.reserveStake, ...vs, pool.poolMint];
  const pre = await c.getMultipleAccountsInfo(watch);
  const slotPre = await c.getSlot();
  const sim = await c.simulateTransaction(new VersionedTransaction(msg), { sigVerify: false, replaceRecentBlockhash: true, commitment: "confirmed", accounts: { encoding: "base64", addresses: watch.map(k => k.toBase58()) } });
  const out = { simulated_at: new Date().toISOString(), context_slot: sim.context.slot, epoch: Math.floor(sim.context.slot / 432000), slot_index: sim.context.slot % 432000, err: sim.value.err, units: sim.value.unitsConsumed, logs: sim.value.logs };
  if (!sim.value.err) {
    const post = sim.value.accounts.map(a => ({ lamports: a.lamports, data: Buffer.from(a.data[0], "base64") }));
    const pp = StakePoolLayout.decode(post[0].data);
    const tokAmt = (d) => d.readBigUInt64LE(64);
    out.pre = { T: pool.totalLamports.toString(), S: pool.poolTokenSupply.toString(), lambda: pool.lastUpdateEpoch.toString(), fee_tokens: tokAmt(pre[1].data).toString(), reserve: pre[2].lamports, V: pre.slice(3, 3 + vs.length).map(a => a.lamports), mint_supply: pre[pre.length - 1].data.readBigUInt64LE(36).toString() };
    out.post = { Theta: pp.totalLamports.toString(), S: pp.poolTokenSupply.toString(), lambda: pp.lastUpdateEpoch.toString(), fee_tokens: tokAmt(post[1].data).toString(), reserve: post[2].lamports, V: post.slice(3, 3 + vs.length).map(a => a.lamports), mint_supply: post[post.length - 1].data.readBigUInt64LE(36).toString() };
    out.D_T = (BigInt(out.post.Theta) - BigInt(out.pre.T)).toString();
    out.manager_fee_tokens_minted = (BigInt(out.post.fee_tokens) - BigInt(out.pre.fee_tokens)).toString();
    out.pre_read_slot = slotPre;
  }
  console.log(JSON.stringify(out, null, 1));
})().catch(e => { console.error(e); process.exit(1); });
