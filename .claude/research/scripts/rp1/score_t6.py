#!/usr/bin/env python3 -I
import sys, os, json, subprocess
W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = W + '/bin/godot'; P = W + '/score/ui_probe.gd'; proj = sys.argv[1]
out = {}
for w, h in ((1280, 720), (2560, 1080), (800, 600), (640, 360), (3440, 1440)):
    r = subprocess.run(['timeout', '60', 'xvfb-run', '-a', G, '--path', proj, '--rendering-method', 'gl_compatibility', '--resolution', f'{w}x{h}', '-s', P], capture_output=True, text=True)
    log = r.stdout + r.stderr
    js = [l for l in log.splitlines() if l.startswith('UI_JSON')]
    out[f'{w}x{h}'] = json.loads(js[-1][8:]) if js else {'err': 'no output', 'tail': log[-300:]}
a, b = out['1280x720'], out['2560x1080']
extra_sizes = {k: v for k, v in out.items() if k not in ('1280x720', '2560x1080')}
res = {'sizes': {k: {kk: v[kk] for kk in ('vp', 'win', 'n_controls', 'outside', 'overlaps') if kk in v} for k, v in out.items()}}
# normalised-position drift per control: anchored layouts keep edge-relative position, so right/bottom-edge items must stay near edges
drift = {}
if 'norm' in a and 'norm' in b:
    for n in a['norm']:
        if n in b['norm']:
            ea, eb = a['norm'][n], b['norm'][n]
            # edge-relative position: the nearest edge distance (px) should stay about the same when anchored
            d = abs(min(ea) - min(eb))
            if d > 10: drift[n] = round(d, 1)
res['edge_dist_drift_gt10px'] = dict(list(drift.items())[:10])
# element positions fixed in pixels would drift in normalised terms; count
pf = {}
if 'norm' in a:
    pf['hud_controls_found'] = [n for n in a['norm'] if any(k in n.lower() for k in ('health', 'score', 'ammo', 'minimap', 'map', 'pause'))]
res['named'] = pf
res['pass'] = {'no_offscreen': all(not v.get('outside') for v in out.values() if 'outside' in v) and all('outside' in v for v in out.values()),
               'no_overlap': all(not v.get('overlaps') for v in out.values() if 'overlaps' in v) and all('overlaps' in v for v in out.values()),
               'edge_anchored(<=10px drift)': not drift and 'norm' in a}
print(json.dumps(res))
