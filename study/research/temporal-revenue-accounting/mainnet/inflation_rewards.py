# Read-only: getInflationReward for the pool's validator stake accounts and reserve, per epoch.
import json, sys, time, urllib.request
URL = "https://api.mainnet-beta.solana.com"
st = json.load(open(sys.argv[1]))
addrs = [v["stake_account"] for v in st["validators"]] + [st["pool"]["reserve_stake"]]
out = {"addresses": addrs, "epochs": {}}
for ep in range(int(sys.argv[2]), int(sys.argv[3]) + 1):
    for attempt in range(8):
        req = urllib.request.Request(URL, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getInflationReward", "params": [addrs, {"epoch": ep}]}).encode(), headers={"content-type": "application/json"})
        r = json.load(urllib.request.urlopen(req, timeout=30))
        if "result" in r: break
        time.sleep(4 * (attempt + 1))
    out["epochs"][ep] = r.get("result", r)
    time.sleep(2)
print(json.dumps(out, indent=1))
