// Measures the transaction account-lock limit of the local cluster: sends a 1-lamport
// System transfer padded with read-only accounts from an address lookup table, at a range of
// total account counts. agave 2.0.15 uses 128 if feature increase_tx_account_lock_limit
// (9LZdXeKGeBV6hRLdxS1rHbHoEUsKqesCC2ZAPTPKJAbK) is active, else 64 (runtime/src/bank.rs:3240-3251).
import {
  AddressLookupTableProgram, Connection, Keypair, LAMPORTS_PER_SOL, PublicKey, SystemProgram,
  Transaction, TransactionMessage, VersionedTransaction, sendAndConfirmTransaction,
} from "@solana/web3.js";

const connection = new Connection(process.env.RPC_URL ?? "http://127.0.0.1:18899", "confirmed");

async function main() {
  const payer = Keypair.generate();
  const sig = await connection.requestAirdrop(payer.publicKey, 10 * LAMPORTS_PER_SOL);
  await connection.confirmTransaction({ signature: sig, ...(await connection.getLatestBlockhash()) }, "confirmed");
  const dest = Keypair.generate().publicKey;
  const pads = Array.from({ length: 140 }, () => Keypair.generate().publicKey);
  const [createIx, alt] = AddressLookupTableProgram.createLookupTable({ authority: payer.publicKey, payer: payer.publicKey, recentSlot: await connection.getSlot("finalized") });
  await sendAndConfirmTransaction(connection, new Transaction().add(createIx), [payer], { commitment: "confirmed" });
  for (let k = 0; k < pads.length; k += 25) {
    await sendAndConfirmTransaction(connection, new Transaction().add(AddressLookupTableProgram.extendLookupTable({ payer: payer.publicKey, authority: payer.publicKey, lookupTable: alt, addresses: pads.slice(k, k + 25) })), [payer], { commitment: "confirmed" });
  }
  await new Promise((r) => setTimeout(r, 2000));
  const table = (await connection.getAddressLookupTable(alt)).value!;
  const out: any = { feature: "9LZdXeKGeBV6hRLdxS1rHbHoEUsKqesCC2ZAPTPKJAbK" };
  const featureAcct = await connection.getAccountInfo(new PublicKey(out.feature));
  out.featureOwner = featureAcct?.owner.toBase58() ?? null;
  for (const total of [64, 65, 127, 128, 129]) {
    // static keys: payer, dest, System program = 3
    const ix = SystemProgram.transfer({ fromPubkey: payer.publicKey, toPubkey: dest, lamports: 1_000_000 });
    ix.keys.push(...pads.slice(0, total - 3).map((pubkey) => ({ pubkey, isSigner: false, isWritable: false })));
    const { blockhash } = await connection.getLatestBlockhash("confirmed");
    const msg = new TransactionMessage({ payerKey: payer.publicKey, recentBlockhash: blockhash, instructions: [ix] }).compileToV0Message([table]);
    const tx = new VersionedTransaction(msg);
    tx.sign([payer]);
    const n = msg.staticAccountKeys.length + msg.addressTableLookups.reduce((a, l) => a + l.readonlyIndexes.length + l.writableIndexes.length, 0);
    try {
      const s = await connection.sendTransaction(tx);
      const c = await connection.confirmTransaction(s, "confirmed");
      out[`accounts_${n}`] = c.value.err ? { ok: false, err: c.value.err } : { ok: true };
    } catch (e: any) {
      out[`accounts_${n}`] = { ok: false, error: String(e?.message ?? e).split("\n")[0] };
    }
  }
  console.log(JSON.stringify(out, null, 2));
}
main().catch((e) => { console.log(JSON.stringify({ error: String(e?.stack ?? e) })); process.exit(1); });
