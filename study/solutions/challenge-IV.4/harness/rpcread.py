import json, sys, base64, struct, urllib.request
URL = "https://api.mainnet-beta.solana.com"
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
def b58(b):
    n = int.from_bytes(b, "big"); s = ""
    while n: n, r = divmod(n, 58); s = B58[r] + s
    return "1" * (len(b) - len(b.lstrip(b"\0"))) + s
def get(addr):
    req = urllib.request.Request(URL, data=json.dumps({"jsonrpc":"2.0","id":1,"method":"getAccountInfo","params":[addr,{"encoding":"base64"}]}).encode(), headers={"content-type":"application/json"})
    v = json.load(urllib.request.urlopen(req, timeout=20))["result"]["value"]
    return v, base64.b64decode(v["data"][0])
pool, d = get(sys.argv[1])
print("pool owner", pool["owner"], "len", len(d))
o = 1; manager = b58(d[o:o+32]); o += 32; staker = b58(d[o:o+32]); o += 32; sda = b58(d[o:o+32]); o += 32; o += 1
vlist = b58(d[o:o+32]); o += 32; reserve = b58(d[o:o+32]); o += 32; mint = b58(d[o:o+32]); o += 32; fee = b58(d[o:o+32]); o += 32; tokp = b58(d[o:o+32]); o += 32
T, S, lam = struct.unpack_from("<QQQ", d, o)
print(json.dumps(dict(manager=manager, staker=staker, stake_deposit_authority=sda, validator_list=vlist, reserve=reserve, mint=mint, fee_account=fee, token_program=tokp, total_lamports=T, pool_token_supply=S, last_update_epoch=lam), indent=1))
vl, vd = get(vlist)
maxv, = struct.unpack_from("<I", vd, 1); n, = struct.unpack_from("<I", vd, 5)
print("validator_list max", maxv, "entries", n)
for i in range(n):
    e = vd[9+73*i: 9+73*(i+1)]
    act, tr, tseed = struct.unpack_from("<QQQ", e, 0); st = e[24+4+4+8] if False else None
    print(i, "A", act, "tau", tr, "tseed", tseed, "status", e[60] if len(e)>60 else "?")
