#!/usr/bin/env python3 -I
import sys, os, json, subprocess, re, glob
W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = W + '/bin/godot'; P = W + '/score/flow_probe.gd'; proj = sys.argv[1]
r = subprocess.run(['timeout', '120', G, '--headless', '--path', proj, '--fixed-fps', '60', '-s', P], capture_output=True, text=True)
log = r.stdout + r.stderr
js = [l for l in log.splitlines() if l.startswith('FLOW_JSON')]
o = json.loads(js[-1][10:]) if js else {'err': 'no output', 'rc': r.returncode}
errs = [l for l in log.splitlines() if 'SCRIPT ERROR' in l or 'Parse Error' in l]
r5 = subprocess.run(['timeout', '120', G, '--headless', '--path', proj, '--fixed-fps', '60', '-s', P, '--', 'settle=5'], capture_output=True, text=True)
js5 = [l for l in (r5.stdout + r5.stderr).splitlines() if l.startswith('FLOW_JSON')]
o5 = json.loads(js5[-1][10:]) if js5 else {'err': 'no output'}
p = {'trigger_during_fade_in_not_swallowed(5f)': o5.get('cycles_done') == 8 and not o5.get('problems'), 'full_loop_x8(menu>L1>L2>GO>retry)': o.get('cycles_done') == 8 and not o.get('problems'), 'fade_observed': bool(o.get('fade_seen')), 'no_script_errors': not errs}
c = o.get('counts_node_orphan_obj') or []
if len(c) >= 3:
    p['no_node_growth(cycle2->8)'] = c[-1][0] <= c[1][0]
    p['no_orphan_growth'] = c[-1][1] <= c[1][1]
    p['no_object_growth(<=+20)'] = c[-1][2] - c[1][2] <= 20
gd = ''
for f in glob.glob(proj + '/**/*.gd', recursive=True):
    if '/.godot/' not in f: gd += open(f, errors='replace').read() + '\n'
files_with_change = [os.path.relpath(f, proj) for f in glob.glob(proj + '/**/*.gd', recursive=True) if '/.godot/' not in f and 'change_scene_to' in open(f, errors='replace').read()]
lint = {'change_scene_call_sites': len(re.findall(r'change_scene_to_(file|packed)', gd)), 'files_calling_change_scene': files_with_change,
        'uses_threaded_load': 'load_threaded' in gd, 'uses_tween_or_animplayer': bool(re.search(r'create_tween|AnimationPlayer', gd))}
print(json.dumps({'probe_settle5_problems': o5.get('problems'), 'probe': o, 'errors': errs[:4], 'pass': p, 'lint': lint}))
