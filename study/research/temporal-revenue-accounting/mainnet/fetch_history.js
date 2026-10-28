// Read-only: getSignaturesForAddress + getTransaction for the pool's counted accounts.
// Usage: node fetch_history.js <min_epoch> > history.json
const fs = require("fs");
const { Connection, PublicKey } = require("@solana/web3.js");
const RPC = process.env.RPC_URL || "https://api.mainnet-beta.solana.com";
const c = new Connection(RPC, "confirmed");
const state = JSON.parse(fs.readFileSync(__dirname + "/pool_state.json"));
const MIN_EPOCH = Number(process.argv[2] || 1064);
const SLOTS = 432000;
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
async function retry(f) { for (let i = 0; ; i++) { try { return await f(); } catch (e) { if (i > 8) throw e; await sleep(3000 * (i + 1)); } } }
const watched = { pool: state.pool_address, reserve: state.pool.reserve_stake, validator_list: state.pool.validator_list, mint: state.pool.pool_mint, manager_fee: state.pool.manager_fee_account };
for (const v of state.validators) { watched["V" + v.i] = v.stake_account; watched["X" + v.i] = v.transient_account; }
(async () => {
  const sigs = new Map();
  for (const [name, addr] of Object.entries(watched)) {
    if (!(process.env.ACCOUNTS || "reserve,manager_fee,V0,V1,V2,V3,X0,X1,X2,X3").split(",").includes(name)) continue; // the pool account itself is referenced read-only by thousands of unrelated txs
    let before; let done = false;
    while (!done) {
      const page = await retry(() => c.getSignaturesForAddress(new PublicKey(addr), { before, limit: 1000 }));
      if (!page.length) break;
      for (const s of page) {
        if (Math.floor(s.slot / SLOTS) < MIN_EPOCH) { done = true; break; }
        if (!sigs.has(s.signature)) sigs.set(s.signature, { slot: s.slot, err: s.err, touched: [] });
        sigs.get(s.signature).touched.push(name);
      }
      before = page[page.length - 1].signature;
      if (page.length < 1000) break;
      await sleep(300);
    }
    console.error(name, addr, "sigs so far", sigs.size);
  }
  const addrName = Object.fromEntries(Object.entries(watched).map(([k, v]) => [v, k]));
  const out = [];
  for (const [sig, meta] of [...sigs.entries()].sort((a, b) => a[1].slot - b[1].slot)) {
    const tx = await retry(() => c.getTransaction(sig, { maxSupportedTransactionVersion: 0 }));
    await sleep(Number(process.env.SLEEP_MS || 700));
    if (!tx) { out.push({ sig, ...meta, missing: true }); continue; }
    const msg = tx.transaction.message;
    const keys = msg.getAccountKeys({ accountKeysFromLookups: tx.meta.loadedAddresses }).keySegments().flat().map(k => k.toBase58());
    const deltas = {};
    keys.forEach((k, j) => { if (addrName[k]) deltas[addrName[k]] = tx.meta.postBalances[j] - tx.meta.preBalances[j]; });
    const top = msg.compiledInstructions.map(ix => ({ program: keys[ix.programIdIndex], data0: Buffer.from(ix.data).subarray(0, 8).toString("hex"), accounts: ix.accountKeyIndexes.map(a => addrName[keys[a]] || keys[a]) }));
    const inner = (tx.meta.innerInstructions || []).flatMap(g => g.instructions.map(ix => keys[ix.programIdIndex]));
    out.push({ sig, slot: tx.slot, epoch: Math.floor(tx.slot / SLOTS), slot_index: tx.slot % SLOTS, blockTime: tx.blockTime, err: tx.meta.err, fee: tx.meta.fee, signers: keys.slice(0, msg.header.numRequiredSignatures), touched: meta.touched, deltas, top, inner_programs: [...new Set(inner)], logs: (tx.meta.logMessages || []).filter(l => /Instruction:|Program log: (?!Instruction)/.test(l)).slice(0, 40) });
  }
  console.log(JSON.stringify({ rpc: RPC, min_epoch: MIN_EPOCH, fetched_at: new Date().toISOString(), watched, txs: out }, null, 1));
})().catch(e => { console.error(e); process.exit(1); });
