#!/usr/bin/env python3 -I
"""Dash + wall slide/jump scorer, reuses plat_probe.gd. Usage: score_t2.py <proj>"""
import sys, os, json, subprocess, csv
W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = W + '/bin/godot'; PROBE = W + '/score/plat_probe.gd'; proj = sys.argv[1]
errs_all = []
def run(name, sc):
    tmp = proj + '/.score'; os.makedirs(tmp, exist_ok=True)
    sp = f'{tmp}/{name}.json'; out = f'{tmp}/{name}.csv'
    json.dump(sc, open(sp, 'w'))
    if os.path.exists(out): os.remove(out)
    r = subprocess.run(['timeout', '60', G, '--headless', '--path', proj, '--fixed-fps', '60', '-s', PROBE, '--', f'scenario={sp}', f'out={out}'], capture_output=True, text=True)
    log = r.stdout + r.stderr
    errs_all.extend(l for l in log.splitlines() if 'SCRIPT ERROR' in l or 'Parse Error' in l or 'PROBE_ERR' in l)
    return [{k: float(v) for k, v in row.items()} for row in csv.DictReader(open(out))] if os.path.exists(out) else []
res = {}
def dash(name, extra):
    ev = [{'f': 0, 'a': 'move_right', 'p': True}] + extra
    return run(name, {'frames': 60, 'events': ev})
base = dash('d_base', [])
dd = dash('d_dash', [{'f': 20, 'a': 'dash', 'p': True}, {'f': 21, 'a': 'dash', 'p': False}])
if base and dd:
    res['ground_dash_extra_px_over_30f'] = round(dd[50]['x'] - base[50]['x'], 1)
    res['ground_dash_peak_vx'] = round(max(abs(r['vx']) for r in dd), 1)
    res['base_peak_vx'] = round(max(abs(r['vx']) for r in base), 1)
    res['dash_vx_after_dash_recovers(f59 vs base)'] = [round(dd[59]['vx'], 1), round(base[59]['vx'], 1)]
# no-direction dash (standing)
sd = run('d_stand', {'frames': 40, 'events': [{'f': 5, 'a': 'dash', 'p': True}, {'f': 6, 'a': 'dash', 'p': False}]})
if sd: res['standing_dash_dx'] = round(sd[35]['x'] - sd[0]['x'], 1)
# wall: find slide start
wall = {'wall_x': 100, 'frames': 150, 'events': [{'f': 0, 'a': 'move_right', 'p': True}, {'f': 40, 'a': 'jump', 'p': True}, {'f': 70, 'a': 'jump', 'p': False}]}
w0 = run('w0', wall)
free = run('w_free', {'frames': 150, 'events': [{'f': 40, 'a': 'jump', 'p': True}, {'f': 70, 'a': 'jump', 'p': False}]})
slide_frames = [r for r in w0 if r['wall'] == 1 and r['floor'] == 0 and r['vy'] > 0]
res['slide_frames'] = len(slide_frames)
if slide_frames and free:
    res['slide_max_vy'] = round(max(r['vy'] for r in slide_frames), 1)
    res['free_fall_max_vy(no wall)'] = round(max(r['vy'] for r in free), 1)
    s0 = int(slide_frames[0]['f'])
    w1 = run('w1', {**wall, 'events': wall['events'] + [{'f': s0 + 6, 'a': 'jump', 'p': True}, {'f': s0 + 8, 'a': 'jump', 'p': False}]})
    after = [r for r in w1 if s0 + 6 <= r['f'] <= s0 + 20]
    if after:
        res['walljump_min_vy'] = round(min(r['vy'] for r in after), 1)
        res['walljump_min_vx'] = round(min(r['vx'] for r in after), 1)
res['script_errors'] = list(dict.fromkeys(errs_all))[:5]
p = {}
if 'ground_dash_extra_px_over_30f' in res: p['dash_burst(peak_vx>=1.3x max, extra>=15px; threshold set post hoc)'] = res['ground_dash_peak_vx'] >= 1.3 * res['base_peak_vx'] and res['ground_dash_extra_px_over_30f'] >= 15
if 'slide_max_vy' in res:
    p['wall_slide_slower(<0.7 free fall)'] = res['slide_max_vy'] < 0.7 * res['free_fall_max_vy(no wall)']
    p['wall_jump(vy<-100 after press)'] = res.get('walljump_min_vy', 0) < -100
else:
    p['wall_slide_detected'] = False
res['pass'] = p
print(json.dumps(res))
