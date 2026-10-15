#!/usr/bin/env python3 -I
import sys, os, json, subprocess, re, glob
W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = W + '/bin/godot'; P = W + '/score/pause_probe.gd'; proj = sys.argv[1]
r = subprocess.run(['timeout', '90', G, '--headless', '--path', proj, '--fixed-fps', '60', '-s', P], capture_output=True, text=True)
log = r.stdout + r.stderr
js = [l for l in log.splitlines() if l.startswith('PAUSE_JSON')]
o = json.loads(js[-1][11:]) if js else {'err': 'no output', 'rc': r.returncode}
errs = [l for l in log.splitlines() if 'SCRIPT ERROR' in l or 'Parse Error' in l]
p = {}
if 'paused_after_esc' in o:
    p['esc_pauses'] = o['paused_after_esc'] is True
    p['control_player_moves_when_unpaused(>5px)'] = o.get('control_moved_unpaused_px', 0) > 5
    p['world_frozen(<=1px)'] = o.get('world_moved_while_paused_px', 99) <= 1.0
    p['menu_buttons(resume,restart,quit)'] = all(o['buttons_found'].values())
    p['menu_alive_when_paused'] = bool(o.get('resume_can_process_while_paused'))
    p['focus_on_button'] = bool(o.get('focus_owner_is_button'))
    p['resume_button_unpauses'] = o.get('paused_after_resume_button') is False
    p['esc_toggles(on,off)'] = o.get('paused_after_esc_again') is True and o.get('paused_after_esc_toggle_off') is False
    p['restart_unpauses_and_reloads'] = o.get('after_restart_paused') is False and bool(o.get('after_restart_scene_is_level'))
    p['quit_to_menu_unpaused'] = o.get('after_quit_paused') is False and bool(o.get('after_quit_is_menu'))
    p['time_scale_untouched'] = all(abs(o.get(k, 1.0) - 1.0) < 1e-6 for k in ('time_scale_after_esc', 'after_restart_ts', 'after_quit_ts'))
    p['esc_on_menu_does_not_pause'] = o.get('esc_on_menu_pauses') is False
p['no_script_errors'] = not errs
gd = ''
for f in glob.glob(proj + '/**/*.gd', recursive=True):
    if '/.godot/' not in f: gd += open(f, errors='replace').read() + '\n'
lint = {'time_scale_assign': len(re.findall(r'time_scale\s*=', gd)), 'process_mode_always_or_when_paused': len(re.findall(r'PROCESS_MODE_(ALWAYS|WHEN_PAUSED)', gd)), 'tree_paused_assign': len(re.findall(r'\.paused\s*=', gd))}
print(json.dumps({'probe': o, 'errors': errs[:4], 'pass': p, 'lint': lint}))
