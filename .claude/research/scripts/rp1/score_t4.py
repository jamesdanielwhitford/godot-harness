#!/usr/bin/env python3 -I
import sys, os, json, subprocess, glob, shutil, re
W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = W + '/bin/godot'; P = W + '/score/persist_probe.gd'; proj = sys.argv[1]
home = proj + '/.score_home'; shutil.rmtree(home, ignore_errors=True); os.makedirs(home)
env = dict(os.environ, XDG_DATA_HOME=home, HOME=home)
def run(args, timeout=60):
    r = subprocess.run(['timeout', str(timeout), G, '--headless', '--path', proj] + args, capture_output=True, text=True, env=env)
    return r.stdout + r.stderr, r.returncode
def probe(mode):
    log, rc = run(['--fixed-fps', '60', '-s', P, '--', f'mode={mode}'])
    js = [l for l in log.splitlines() if l.startswith('PERSIST_JSON')]
    errs = [l for l in log.splitlines() if 'SCRIPT ERROR' in l or 'Parse Error' in l]
    return (json.loads(js[-1][13:]) if js else {'err': 'no output', 'rc': rc}), errs
def userfiles():
    return sorted(os.path.relpath(p, home) for p in glob.glob(home + '/**/*', recursive=True) if os.path.isfile(p))
res = {}; errs = []
base, e = probe('check'); res['baseline'] = base; errs += e
mut, e = probe('mutate'); res['mutate'] = mut; errs += e
res['user_files_after_mutate'] = userfiles()
chk, e = probe('check'); res['after_restart'] = chk; errs += e
rst, e = probe('reset'); res['reset'] = rst; errs += e
chk2, e = probe('check'); res['after_reset_restart'] = chk2; errs += e
# corrupt save files
files = [p for p in glob.glob(home + '/**/*', recursive=True) if os.path.isfile(p)]
corrupt_errs = []
for mode in ('garbage', 'empty', 'truncated'):
    for p in files:
        if mode == 'garbage': open(p, 'w').write('{{{ not json \x00\x01')
        elif mode == 'empty': open(p, 'w').write('')
        else: open(p, 'w').write('{"version": 1, "levels": {"1": ')
    c, e = probe('check'); corrupt_errs += [f'{mode}: {x}' for x in e]
    if 'err' in c: corrupt_errs.append(f'{mode}: probe failed {c}')
res['corrupt_file_errors'] = corrupt_errs[:6]
res['script_errors'] = list(dict.fromkeys(errs))[:5]
p = {}
m = res['mutate']; a = res['after_restart']
p['save_api_found'] = 'owner' in m
if 'owner' in m and 'owner' in a:
    p['level_progress_persists'] = bool(a.get('lvl1_completed')) and abs(float(a.get('lvl1_best', -1)) - 12.3) < 0.01
    p['music_volume_persists'] = abs(a.get('music_linear', -1) - 0.3) < 0.02
    p['remap_persists'] = bool(a.get('jump_has_K'))
    r2 = res['after_reset_restart']
    p['reset_clears_progress'] = (not r2.get('lvl1_completed', True))
p['music_bus_exists_at_baseline'] = res['baseline'].get('music_bus_idx', -1) >= 0
p['survives_corrupt_save'] = not corrupt_errs
res['pass'] = p
# lint
gd = ''
for f in glob.glob(proj + '/**/*.gd', recursive=True):
    if '/.godot/' not in f: gd += open(f, errors='replace').read() + '\n'
res['lint'] = {'versioned': bool(re.search(r'version', gd, re.I)), 'atomic_tmp_rename': bool(re.search(r'\.tmp|rename', gd)),
  'uses_ResourceSaver_or_store_var': bool(re.search(r'ResourceSaver|store_var|var_to_bytes', gd)),
  'linear_to_db': 'linear_to_db' in gd, 'user_path_writes': len(re.findall(r'user://[\w./-]+', gd)),
  'raw_KEY_in_gameplay_checks': len(re.findall(r'is_key_pressed|KEY_', gd))}
print(json.dumps(res))
