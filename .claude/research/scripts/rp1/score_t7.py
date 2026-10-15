#!/usr/bin/env python3 -I
import sys, os, json, subprocess, re
W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = W + '/bin/godot'; P = W + '/score/inv_probe.gd'; proj = sys.argv[1]
res = {}; errs = []
for t in ('add', 'stack', 'move', 'self', 'swap'):
    r = subprocess.run(['timeout', '60', G, '--headless', '--path', proj, '-s', P, '--', f'test={t}'], capture_output=True, text=True)
    log = r.stdout + r.stderr
    js = [l for l in log.splitlines() if l.startswith('INV_JSON')]
    res[t] = json.loads(js[-1][9:]) if js else {'err': 'no output', 'rc': r.returncode}
    errs += [l for l in log.splitlines() if 'SCRIPT ERROR' in l or 'Parse Error' in l]
res['script_errors'] = list(dict.fromkeys(errs))[:5]
a = res['add']; p = {}
if 'occupied' in a:
    p['>=20_slots'] = a['n_slots'] >= 20
    p['add_works'] = a['occupied'] > 0
    st = res['stack']; p['stacks(occupied<presses)'] = st.get('occupied', 99) < st.get('presses', 0)
    p['overflow_no_crash(40 adds)'] = a['occupied'] <= a['n_slots']
    m = res['move']; p['move_to_empty'] = bool(m.get('src_empty_after') and m.get('dst_occupied_after'))
    s = res['self']; p['self_drop_safe'] = s.get('occ_after') == s.get('occ_before')
    w = res['swap']; p['swap_or_merge_conserves(occ in {n,n-1})'] = w.get('occ_after') in (w.get('occ_before'), (w.get('occ_before') or 0) - 1) if 'occ_after' in w else None
p['no_script_errors'] = not res['script_errors']
res['pass'] = p
# lint: model/view split + Resource items
gd = {}
for dp, dn, fn in os.walk(proj):
    dn[:] = [d for d in dn if not d.startswith('.') and d != '.score']
    for f in fn:
        if f.endswith('.gd'): gd[os.path.join(dp, f)] = open(os.path.join(dp, f), errors='replace').read()
model = [os.path.relpath(k, proj) for k, v in gd.items() if re.search(r'^extends\s+(RefCounted|Resource|Object)', v, re.M) and re.search(r'(slots|items)\s*[:=]', v) and re.search(r'func\s+(add|try_add|insert)', v)]
item_res = [os.path.relpath(k, proj) for k, v in gd.items() if re.search(r'^extends\s+Resource', v, re.M) and re.search(r'max_stack|stack', v)]
tres = sum(1 for dp, dn, fn in os.walk(proj) for f in fn if f.endswith('.tres') and '.godot' not in dp)
res['lint'] = {'model_scripts_non_control': model, 'item_resource_scripts': item_res, 'tres_files': tres}
print(json.dumps(res))
