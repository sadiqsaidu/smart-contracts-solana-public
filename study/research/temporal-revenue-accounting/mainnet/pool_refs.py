# Read-only: sample transactions that reference the pool account (not its asset accounts) and tally programs.
import json, sys, time, urllib.request, collections
URL = "https://api.mainnet-beta.solana.com"
def rpc(m, p):
    for a in range(8):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(URL, data=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(), headers={"content-type":"application/json"}), timeout=30))
            if "result" in r: return r["result"]
        except Exception: pass
        time.sleep(3*(a+1))
sigs = rpc("getSignaturesForAddress", ["EyKyx9LKz7Qbp6PSbBRoMdt8iNYp8PvFVupQTQRMY9AM", {"limit": 1000}])
step = max(1, len(sigs)//int(sys.argv[1]))
tally = collections.Counter(); samples = []
for s in sigs[::step]:
    tx = rpc("getTransaction", [s["signature"], {"maxSupportedTransactionVersion": 0, "encoding": "json"}]); time.sleep(1.2)
    if not tx: continue
    keys = tx["transaction"]["message"]["accountKeys"] + tx["meta"].get("loadedAddresses", {}).get("writable", []) + tx["meta"].get("loadedAddresses", {}).get("readonly", [])
    progs = sorted(set(keys[i["programIdIndex"]] for i in tx["transaction"]["message"]["instructions"]))
    ilog = [l for l in tx["meta"]["logMessages"] if "Instruction:" in l][:6]
    tally[tuple(progs)] += 1
    samples.append({"sig": s["signature"], "slot": s["slot"], "programs": progs, "instr_logs": ilog, "err": tx["meta"]["err"]})
print(json.dumps({"n_sigs_page": len(sigs), "first_slot": sigs[-1]["slot"], "last_slot": sigs[0]["slot"], "tally": [[list(k), v] for k, v in tally.most_common()], "samples": samples}, indent=1))
