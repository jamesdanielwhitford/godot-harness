#!/usr/bin/env python3 -I
"""Platformer scorer: python3 -I score_t1.py <projdir> [--no-spec]. Prints JSON metrics + pass flags."""
import sys, os, json, subprocess, csv, tempfile
W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = W + '/bin/godot'; PROBE = W + '/score/plat_probe.gd'
proj = sys.argv[1]
def run(name, sc):
    tmp = proj + '/.score'; os.makedirs(tmp, exist_ok=True)
    sp = f'{tmp}/{name}.json'; out = f'{tmp}/{name}.csv'
    json.dump(sc, open(sp, 'w'))
    if os.path.exists(out): os.remove(out)
    r = subprocess.run(['timeout', '60', G, '--headless', '--path', proj, '--fixed-fps', '60', '-s', PROBE, '--', f'scenario={sp}', f'out={out}'], capture_output=True, text=True)
    log = r.stdout + r.stderr
    errs = [l for l in log.splitlines() if 'SCRIPT ERROR' in l or 'Parse Error' in l or 'PROBE_ERR' in l]
    rows = []
    if os.path.exists(out):
        rows = [{k: float(v) for k, v in row.items()} for row in csv.DictReader(open(out))]
    return rows, errs
res = {}; errs_all = []
# 1 run speed
rows, e = run('run', {'frames': 60, 'events': [{'f': 0, 'a': 'move_right', 'p': True}]}); errs_all += e
if rows:
    vmax = max(r['vx'] for r in rows)
    f95 = next((r['f'] for r in rows if r['vx'] >= 0.95 * 220), None)
    f100 = next((r['f'] for r in rows if r['vx'] >= 219.5), None)
    res['vmax'] = round(vmax, 1); res['frames_to_95pct_of_220'] = f95; res['frames_to_220'] = f100
# 2 jump (hold)
def jump(name, hold):
    ev = [{'f': 10, 'a': 'jump', 'p': True}, {'f': 10 + hold, 'a': 'jump', 'p': False}]
    rows, e = run(name, {'frames': 120, 'events': ev}); errs_all.extend(e)
    if not rows: return None
    y0 = rows[10]['y']
    up = [(y0 - r['y'], r['f']) for r in rows if r['f'] >= 10]
    h, fa = max(up)
    # time from first frame of upward velocity
    start = next((r['f'] for r in rows if r['f'] >= 10 and r['vy'] < 0), None)
    return {'apex_px': round(h, 1), 'apex_frame': fa, 'jump_start_frame': start,
            't_apex_s': round((fa - start) / 60.0, 3) if start is not None else None}
def jump_tps(tps):
    k = tps / 60.0
    f0, f1, fn = int(10 * k), int(70 * k), int(120 * k)
    ev = [{'f': f0, 'a': 'jump', 'p': True}, {'f': f1, 'a': 'jump', 'p': False}]
    rows, e = run(f'jump_{tps}', {'tps': tps, 'frames': fn, 'events': ev}); errs_all.extend(e)
    if not rows: return None
    y0 = rows[f0]['y']
    h, fa = max((y0 - r['y'], r['f']) for r in rows if r['f'] >= f0)
    start = next((r['f'] for r in rows if r['f'] >= f0 and r['vy'] < 0), None)
    return {'apex_px': round(h, 1), 't_apex_s': round((fa - start) / tps, 3) if start is not None else None}
res['apex_at_120hz'] = jump_tps(120); res['apex_at_30hz'] = jump_tps(30)
hold = jump('jump_hold', 60); tap = jump('jump_tap', 2)
res['jump_hold'] = hold; res['jump_tap'] = tap
# 3 coyote: run off edge at floor_end=60, press jump k frames after leaving
def coyote(k):
    ev = [{'f': 0, 'a': 'move_right', 'p': True}, {'after': 'airborne', 'k': k, 'a': 'jump', 'p': True}, {'after': 'airborne', 'k': k + 6, 'a': 'jump', 'p': False}]
    rows, e = run(f'coy{k}', {'floor_end': 60, 'frames': 90, 'events': ev}); errs_all.extend(e)
    if not rows: return None
    # jumped if vy < -50 at any time while in air after press
    return any(r['vy'] < -100 for r in rows)
coy = {k: coyote(k) for k in range(0, 13)}
acc = [k for k, v in coy.items() if v]
res['coyote_max_accepted_k'] = max(acc) if acc else None   # frames after first airborne tick
# 4 buffer: hold jump 20 frames then release, find landing frame L, then re-run pressing jump L-k
ev0 = [{'f': 0, 'a': 'jump', 'p': True}, {'f': 20, 'a': 'jump', 'p': False}]
rows, e = run('buf0', {'frames': 140, 'events': ev0}); errs_all += e
land = None
if rows:
    air = [r for r in rows if r['f'] > 3 and r['floor'] == 0]
    if air: land = int(max(r['f'] for r in air)) + 1
def buf(k):
    if land is None: return None
    ev = ev0 + [{'f': land - k, 'a': 'jump', 'p': True}, {'f': land - k + 6, 'a': 'jump', 'p': False}]
    rows, e = run(f'buf{k}', {'frames': land + 30, 'events': ev}); errs_all.extend(e)
    if not rows: return None
    return any(r['vy'] < -100 for r in rows if r['f'] >= land)
res['land_frame'] = land
bufr = {k: buf(k) for k in range(0, 15)} if land else {}
bacc = [k for k, v in bufr.items() if v]
res['buffer_max_accepted_k'] = max(bacc) if bacc else None  # frames before landing
res['script_errors'] = list(dict.fromkeys(errs_all))[:5]
# pass flags vs spec
p = {}
if 'frames_to_95pct_of_220' in res: p['speed<=8f'] = res['frames_to_95pct_of_220'] is not None and res['frames_to_95pct_of_220'] <= 8 and 209 <= res['vmax'] <= 231
if hold and hold['t_apex_s'] is not None: p['apex48px_0.38s'] = abs(hold['apex_px'] - 48) <= 6 and abs(hold['t_apex_s'] - 0.38) <= 0.03
if hold and tap: p['variable_jump(tap<0.8hold)'] = tap['apex_px'] < 0.8 * hold['apex_px']
ck = res['coyote_max_accepted_k']; bk = res['buffer_max_accepted_k']
for key in ('apex_at_120hz', 'apex_at_30hz'):
    v = res[key]
    p['fps_indep_' + key] = bool(v and v['t_apex_s'] is not None and abs(v['apex_px'] - 48) <= 8 and abs(v['t_apex_s'] - 0.38) <= 0.05)
p['coyote~6(3..7)'] = ck is not None and 3 <= ck <= 7
p['buffer~6(5..7)'] = bk is not None and 5 <= bk <= 7
res['pass'] = p
print(json.dumps(res))
