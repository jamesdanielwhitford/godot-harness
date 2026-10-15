#!/usr/bin/env python3 -I
import json, re, glob, os
W = '/tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad/research/rp1_work/runs'
rows = []
for t in ['t1','t2','t3','t4','t5','t6','t7','t8']:
    for n in (1, 2):
        txt = open(f'{W}/{t}/t{n}.score.txt').read()
        common, _, task = txt.partition('### task')
        st = json.loads(re.findall(r'^\{"gd_files.*$', common, re.M)[0])
        loadfail = re.search(r'fails=(\d+)', common)
        runerr = re.search(r'runmain_rc=(\d+) errs=(\d+)', common)
        lines = [l for l in task.splitlines() if l.startswith('{')]
        passes = {}
        for i, l in enumerate(lines):
            try: d = json.loads(l)
            except Exception: continue
            pr = d.get('pass', {})
            passes.update({(('reg:' if (t == 't2' and i == 1) else '') + k): v for k, v in pr.items()})
        npass = sum(1 for v in passes.values() if v is True); ntot = len(passes)
        j = json.load(open(f'{W}/{t}/t{n}.result.json'))
        meta = open(f'{W}/{t}/t{n}.meta').read()
        secs = re.search(r'secs=(\d+)', meta).group(1)
        rows.append((t, n, st, int(loadfail.group(1)), int(runerr.group(2)), npass, ntot, [k for k, v in passes.items() if v is not True], secs, round(j['total_cost_usd'], 2)))
print('task trial gd tscn LOC auto fsm typed/untyped bool_flags loadfails runerrs pass/total secs cost failed')
for r in rows:
    t, n, st, lf, re_, npass, ntot, failed, secs, cost = r
    print(t, n, st['gd_files'], st['tscn_files'], st['gd_loc'], st['autoloads'], '+'.join(st['fsm_style']), f"{st['typed_vars']}/{st['untyped_vars']}", st['bool_flag_vars'], lf, re_, f'{npass}/{ntot}', secs, cost, failed)
