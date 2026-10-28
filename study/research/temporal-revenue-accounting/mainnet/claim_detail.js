// Read-only: full detail of one Tip Router claim tx and the TDA accounts for an epoch.
const fs = require("fs");
const { Connection, PublicKey } = require("@solana/web3.js");
const c = new Connection(process.env.RPC_URL || "https://api.mainnet-beta.solana.com", "confirmed");
const TIPDIST = new PublicKey("4R3gSG8BpU4t19KYj8CfnbtRpnT8gtk4dvTHxVRwc2r7");
const u64 = (n) => { const b = Buffer.alloc(8); b.writeBigUInt64LE(BigInt(n)); return b; };
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
  const st = JSON.parse(fs.readFileSync(__dirname + "/pool_state.json"));
  const sig = process.argv[2]; const epoch = Number(process.argv[3]);
  const tx = await c.getTransaction(sig, { maxSupportedTransactionVersion: 0 });
  const keys = tx.transaction.message.getAccountKeys({ accountKeysFromLookups: tx.meta.loadedAddresses }).keySegments().flat().map(k => k.toBase58());
  const msg = tx.transaction.message;
  const out = { sig, slot: tx.slot, blockTime: tx.blockTime, fee: tx.meta.fee, numSigners: msg.header.numRequiredSignatures,
    keys: keys.map((k, j) => ({ k, signer: j < msg.header.numRequiredSignatures, writable: msg.isAccountWritable(j), pre: tx.meta.preBalances[j], post: tx.meta.postBalances[j] })),
    top: msg.compiledInstructions.map(ix => ({ program: keys[ix.programIdIndex], data: Buffer.from(ix.data).toString("hex"), accounts: ix.accountKeyIndexes.map(a => keys[a]) })),
    inner: (tx.meta.innerInstructions || []).map(g => g.instructions.map(ix => ({ program: keys[ix.programIdIndex], data_b58: ix.data, accounts: ix.accounts.map(a => keys[a]) }))),
    logs: tx.meta.logMessages };
  await sleep(500);
  out.tda = [];
  for (const v of st.validators) {
    const [tda] = PublicKey.findProgramAddressSync([Buffer.from("TIP_DISTRIBUTION_ACCOUNT"), new PublicKey(v.vote).toBuffer(), u64(epoch)], TIPDIST);
    const a = await c.getAccountInfo(tda); await sleep(400);
    if (!a) { out.tda.push({ i: v.i, tda: tda.toBase58(), exists: false }); continue; }
    const d = a.data; let o = 8;
    const vote = new PublicKey(d.subarray(o, o + 32)).toBase58(); o += 32;
    const upl = new PublicKey(d.subarray(o, o + 32)).toBase58(); o += 32;
    let mr = null; if (d[o] === 1) { o += 1; mr = { root: d.subarray(o, o + 32).toString("hex"), max_total_claim: d.readBigUInt64LE(o + 32).toString(), max_num_nodes: d.readBigUInt64LE(o + 40).toString(), total_funds_claimed: d.readBigUInt64LE(o + 48).toString(), num_nodes_claimed: d.readBigUInt64LE(o + 56).toString() }; o += 64; } else o += 1;
    const epoch_created_at = d.readBigUInt64LE(o).toString(); o += 8;
    const commission_bps = d.readUInt16LE(o); o += 2;
    const expires_at = d.readBigUInt64LE(o).toString(); o += 8;
    out.tda.push({ i: v.i, tda: tda.toBase58(), lamports: a.lamports, len: d.length, vote, merkle_root_upload_authority: upl, merkle_root: mr, epoch_created_at, validator_commission_bps: commission_bps, expires_at });
  }
  console.log(JSON.stringify(out, null, 1));
})().catch(e => { console.error(e); process.exit(1); });
