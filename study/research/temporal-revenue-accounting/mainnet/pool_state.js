// Read-only mainnet snapshot of the TruStake pool, validator list and derived PDAs.
// Usage: node pool_state.js > pool_state.json   (only getAccountInfo / getEpochInfo / getMultipleAccounts)
const { Connection, PublicKey } = require("@solana/web3.js");
const RPC = process.env.RPC_URL || "https://api.mainnet-beta.solana.com";
const POOL = new PublicKey(process.env.POOL || "EyKyx9LKz7Qbp6PSbBRoMdt8iNYp8PvFVupQTQRMY9AM");
const SPL = new PublicKey("SPoo1Ku8WFXoNDMHPsrGSTSG1Y47rzgn41SLUNakuHy");
const STAKER = new PublicKey("6EZAJVrNQdnBJU6ULxXSDaEoK6fN7C3iXTCkZKRWDdGM");
const TIPDIST = new PublicKey("4R3gSG8BpU4t19KYj8CfnbtRpnT8gtk4dvTHxVRwc2r7");
const c = new Connection(RPC, "confirmed");
const u64 = (n) => { const b = Buffer.alloc(8); b.writeBigUInt64LE(BigInt(n)); return b; };
const u32 = (n) => { const b = Buffer.alloc(4); b.writeUInt32LE(n); return b; };
(async () => {
  const ei = await c.getEpochInfo();
  const pa = await c.getAccountInfo(POOL);
  const d = pa.data; let o = 1;
  const pk = () => { const k = new PublicKey(d.subarray(o, o + 32)); o += 32; return k.toBase58(); };
  const pool = { account_type: d[0] };
  pool.manager = pk(); pool.staker = pk(); pool.stake_deposit_authority = pk();
  pool.stake_withdraw_bump_seed = d[o]; o += 1;
  pool.validator_list = pk(); pool.reserve_stake = pk(); pool.pool_mint = pk(); pool.manager_fee_account = pk(); pool.token_program_id = pk();
  pool.total_lamports = d.readBigUInt64LE(o).toString(); o += 8;
  pool.pool_token_supply = d.readBigUInt64LE(o).toString(); o += 8;
  pool.last_update_epoch = d.readBigUInt64LE(o).toString(); o += 8;
  // lockup: unix_timestamp i64, epoch u64, custodian 32
  pool.lockup = { unix_timestamp: d.readBigInt64LE(o).toString(), epoch: d.readBigUInt64LE(o + 8).toString(), custodian: new PublicKey(d.subarray(o + 16, o + 48)).toBase58() }; o += 48;
  const fee = () => { const r = { denominator: d.readBigUInt64LE(o).toString(), numerator: d.readBigUInt64LE(o + 8).toString() }; o += 16; return r; };
  pool.epoch_fee = fee();
  const optFee = () => { if (d[o] === 0) { o += 1; return null; } o += 1; return fee(); };
  pool.next_epoch_fee = d[o]; // FutureEpoch enum tag
  { const tag = d[o]; o += 1; pool.next_epoch_fee = tag === 0 ? "None" : { tag, fee: fee() }; }
  pool.preferred_deposit_validator = d[o] ? (o += 1, pk()) : (o += 1, null);
  pool.preferred_withdraw_validator = d[o] ? (o += 1, pk()) : (o += 1, null);
  pool.stake_deposit_fee = fee(); pool.stake_withdrawal_fee = fee();
  { const tag = d[o]; o += 1; pool.next_stake_withdrawal_fee = tag === 0 ? "None" : { tag, fee: fee() }; }
  pool.stake_referral_fee = d[o]; o += 1;
  pool.sol_deposit_authority = d[o] ? (o += 1, pk()) : (o += 1, null);
  pool.sol_deposit_fee = fee(); pool.sol_referral_fee = d[o]; o += 1;
  pool.sol_withdraw_authority = d[o] ? (o += 1, pk()) : (o += 1, null);
  pool.sol_withdrawal_fee = fee();
  { const tag = d[o]; o += 1; pool.next_sol_withdrawal_fee = tag === 0 ? "None" : { tag, fee: fee() }; }
  pool.last_epoch_pool_token_supply = d.readBigUInt64LE(o).toString(); o += 8;
  pool.last_epoch_total_lamports = d.readBigUInt64LE(o).toString(); o += 8;
  const [withdrawAuth] = PublicKey.findProgramAddressSync([POOL.toBuffer(), Buffer.from("withdraw")], SPL);
  const pda = (s) => PublicKey.findProgramAddressSync([Buffer.from(s)], STAKER)[0].toBase58();
  const derived = { pool_withdraw_authority: withdrawAuth.toBase58(), staker_deposit_pda: pda("deposit"), staker_staker_pda: pda("staker"), staker_withdraw_pda: pda("withdraw") };
  const mint = await c.getParsedAccountInfo(new PublicKey(pool.pool_mint));
  const vl = (await c.getAccountInfo(new PublicKey(pool.validator_list))).data;
  const max = vl.readUInt32LE(1), n = vl.readUInt32LE(5);
  const validators = [];
  for (let i = 0; i < n; i++) {
    const e = vl.subarray(9 + 73 * i, 9 + 73 * (i + 1));
    const vote = new PublicKey(e.subarray(41, 73));
    const vss = e.readUInt32LE(36);
    const [stake] = PublicKey.findProgramAddressSync([vote.toBuffer(), POOL.toBuffer(), ...(vss ? [u32(vss)] : [])], SPL);
    const tseed = e.readBigUInt64LE(24);
    const [trans] = PublicKey.findProgramAddressSync([Buffer.from("transient"), vote.toBuffer(), POOL.toBuffer(), u64(tseed)], SPL);
    const [tdaPrev] = PublicKey.findProgramAddressSync([Buffer.from("TIP_DISTRIBUTION_ACCOUNT"), vote.toBuffer(), u64(ei.epoch - 1)], TIPDIST);
    const [tdaCur] = PublicKey.findProgramAddressSync([Buffer.from("TIP_DISTRIBUTION_ACCOUNT"), vote.toBuffer(), u64(ei.epoch)], TIPDIST);
    validators.push({ i, vote: vote.toBase58(), active_stake_lamports: e.readBigUInt64LE(0).toString(), transient_stake_lamports: e.readBigUInt64LE(8).toString(), last_update_epoch: e.readBigUInt64LE(16).toString(), transient_seed_suffix: tseed.toString(), validator_seed_suffix: vss, status: e[40], stake_account: stake.toBase58(), transient_account: trans.toBase58(), tda_prev_epoch: tdaPrev.toBase58(), tda_cur_epoch: tdaCur.toBase58() });
  }
  const keys = [pool.reserve_stake, ...validators.flatMap(v => [v.stake_account, v.transient_account, v.vote, v.tda_prev_epoch, v.tda_cur_epoch])].map(k => new PublicKey(k));
  const accs = await c.getMultipleParsedAccounts(keys);
  const acct = {};
  keys.forEach((k, j) => { const a = accs.value[j]; acct[k.toBase58()] = a ? { lamports: a.lamports, owner: a.owner.toBase58(), space: a.space, parsed: a.data.parsed ?? null } : null; });
  for (const v of validators) {
    const va = acct[v.vote];
    v.vote_account = va ? { lamports: va.lamports, node_pubkey: va.parsed?.info?.nodePubkey, commission: va.parsed?.info?.commission } : null;
    v.stake_account_state = acct[v.stake_account];
    v.transient_state = acct[v.transient_account];
    v.tda_prev_epoch_state = acct[v.tda_prev_epoch] ? { lamports: acct[v.tda_prev_epoch].lamports, owner: acct[v.tda_prev_epoch].owner, space: acct[v.tda_prev_epoch].space } : null;
    v.tda_cur_epoch_state = acct[v.tda_cur_epoch] ? { lamports: acct[v.tda_cur_epoch].lamports, owner: acct[v.tda_cur_epoch].owner, space: acct[v.tda_cur_epoch].space } : null;
  }
  const out = { rpc: RPC, read_at: new Date().toISOString(), epochInfo: ei, version: await c.getVersion(), pool_address: POOL.toBase58(), pool, derived, mint: mint.value?.data?.parsed?.info ?? null, validator_list_max: max, validators, reserve: acct[pool.reserve_stake] };
  console.log(JSON.stringify(out, null, 1));
})().catch(e => { console.error(e); process.exit(1); });
