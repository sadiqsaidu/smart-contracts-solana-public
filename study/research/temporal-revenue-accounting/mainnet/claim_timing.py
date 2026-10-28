# Classify history_long.json per epoch: maintenance, Jito claims, user ops; claim timing vs first SPB.
# Usage: python3 -I claim_timing.py > claim_timing.json
import json, collections
d = json.load(open('history_long.json'))
ep = collections.defaultdict(lambda: {"maint": [], "claims": [], "user": [], "other": []})
for t in d['txs']:
    il = [l.split('Instruction: ')[-1] for l in t['logs'] if 'Instruction:' in l]
    e = ep[t['epoch']]
    rec = {"sig": t['sig'], "slot": t['slot'], "slot_index": t['slot_index'], "signer": t['signers'][0], "deltas": {k: v for k, v in t['deltas'].items() if v}, "instr": il[:4], "err": t['err']}
    if t['err']: e['other'].append(rec)
    elif 'ClaimWithPayer' in il: e['claims'].append(rec)
    elif il and il[0] in ('UpdateValidatorListBalance', 'UpdateStakePoolBalance', 'CleanupRemovedValidatorEntries'): e['maint'].append(rec)
    elif any(x in il for x in ('DepositSol', 'WithdrawStake', 'Deposit', 'DepositToSpecificValidator', 'WithdrawSol', 'DepositStake')): e['user'].append(rec)
    else: e['other'].append(rec)
out = {"epochs": {}, "summary": {}}
late = []; total = 0; n = 0; window_user = []
for k in sorted(ep):
    e = ep[k]
    first_spb = min([m['slot_index'] for m in e['maint'] if 'UpdateStakePoolBalance' in m['instr']], default=None)
    claims = e['claims']
    z = sum(sum(v for kk, v in c['deltas'].items() if kk.startswith('V')) for c in claims)
    after = [c for c in claims if first_spb is not None and c['slot_index'] > first_spb]
    mid = [m for m in e['maint'] if first_spb is not None and m['slot_index'] > max([c['slot_index'] for c in claims], default=10**9)]
    out['epochs'][k] = {"first_spb_slot_index": first_spb, "n_maint_txs": len(e['maint']), "claims": [(c['slot_index'], c['deltas'], c['sig']) for c in claims],
                        "z_total": z, "claims_after_first_spb": len(after), "maintenance_after_last_claim": len(mid),
                        "user_txs": [(u['slot_index'], u['instr'], u['deltas'], u['sig'], u['signer']) for u in e['user']],
                        "other_txs": [(o['slot_index'], o['instr'], o['deltas'], o['sig'], o['err']) for o in e['other']]}
    total += z; n += len(claims); late.append(len(after) == len(claims))
    for u in e['user']:
        if claims and u['slot_index'] > min(c['slot_index'] for c in claims):
            window_user.append((k, u['slot_index'], u['instr'], u['deltas'], u['sig']))
eps = sorted(ep)
out['summary'] = {"epochs_covered": [eps[0], eps[-1]], "n_epochs_with_claims": sum(1 for k in ep if ep[k]['claims']), "n_claims": n,
                  "all_claims_after_first_spb_in_every_epoch": all(late), "total_claimed_lamports": total, "user_txs_inside_unrecognised_window": window_user}
print(json.dumps(out, indent=1))
