#!/usr/bin/env python3 -I
import sys, os, json, subprocess
W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = W + '/bin/godot'; P = W + '/score/ai_probe.gd'; proj = sys.argv[1]
def run(mode, idx=0):
    r = subprocess.run(['timeout', '60', G, '--headless', '--path', proj, '--fixed-fps', '60', '-s', P, '--', f'mode={mode}', f'idx={idx}'], capture_output=True, text=True)
    log = r.stdout + r.stderr
    js = [l for l in log.splitlines() if l.startswith('PROBE_JSON')]
    errs = [l for l in log.splitlines() if 'SCRIPT ERROR' in l or 'Parse Error' in l]
    return (json.loads(js[-1][11:]) if js else {'err': 'no output', 'rc': r.returncode}), errs
res = {}
res['cands'], _ = run('cands') if False else (None, None)
clear, e1 = run('clear'); res['clear'] = clear
blocked = []; e2 = []
for i in range(3):
    b, e = run('blocked', i); blocked.append(b); e2 += e
res['blocked'] = blocked
freed, e3 = run('freed'); res['freed'] = freed
res['script_errors'] = list(dict.fromkeys(e1 + e2 + e3))[:5]
p = {}
if 'dist_start' in clear:
    p['chases_when_visible'] = (clear['chase_frames'] > 0) if clear.get('state_prop') else (clear['dist_end'] < 0.5 * clear['dist_start'])
bl = [b for b in blocked if 'dist_start' in b]
if bl:
    p['no_chase_through_wall'] = all(b['chase_frames'] == 0 for b in bl) if clear.get('state_prop') else all(b['dist_min'] > 0.5 * b['dist_start'] for b in bl)
p['survives_player_freed'] = not e3 and 'dist_start' in freed
res['pass'] = p
print(json.dumps(res))
