#!/usr/bin/env python3 -I
import sys, os, re, json
root = sys.argv[1]
gd = []; tscn = []
for dp, dn, fn in os.walk(root):
    dn[:] = [d for d in dn if not d.startswith('.')]
    for f in fn:
        p = os.path.join(dp, f)
        if f.endswith('.gd'): gd.append(p)
        elif f.endswith('.tscn'): tscn.append(p)
loc = 0; txt = ''
for p in gd:
    s = open(p, errors='replace').read(); txt += '\n' + s
    loc += sum(1 for l in s.splitlines() if l.strip() and not l.strip().startswith('#'))
pg = open(os.path.join(root, 'project.godot'), errors='replace').read()
auto = re.search(r'^\[autoload\]\n(.*?)(?=^\[|\Z)', pg, re.S | re.M)
n_auto = len([l for l in auto.group(1).splitlines() if '=' in l]) if auto else 0
g3 = {
 'export var': len(re.findall(r'^\s*export(\(|\s+var)', txt, re.M)),
 'onready var (no @)': len(re.findall(r'^\s*onready\s+var', txt, re.M)),
 'yield(': txt.count('yield('),
 'KinematicBody': len(re.findall(r'KinematicBody', txt)),
 'move_and_slide(arg)': len(re.findall(r'move_and_slide\([^)]', txt)),
 '.instance()': txt.count('.instance()'),
 'connect(str,self,str)': len(re.findall(r'\.connect\(\s*"[^"]+"\s*,\s*self', txt)),
 'setget': txt.count('setget'),
}
untyped_vars = len(re.findall(r'^\s*(?:@onready\s+)?var\s+\w+\s*=', txt, re.M))
typed_vars = len(re.findall(r'^\s*(?:@onready\s+)?var\s+\w+\s*(?::\s*\w|:=)', txt, re.M))
fsm = []
if re.search(r'enum\s+\w*[Ss]tate', txt) or re.search(r'enum\s*\{[^}]*(IDLE|RUN|JUMP)', txt, re.S): fsm.append('enum')
if re.search(r'match\s+(self\.)?\w*state', txt): fsm.append('match-state')
if re.search(r'class_name\s+\w*State\b', txt) or re.search(r'extends\s+\w*State\b', txt): fsm.append('state-classes')
bools = len(re.findall(r'^\s*var\s+(is_|can_|has_|was_)\w+\s*(:\s*bool)?\s*(=|:=)', txt, re.M))
print(json.dumps({'gd_files': len(gd), 'tscn_files': len(tscn), 'gd_loc': loc, 'autoloads': n_auto,
  'godot3_idioms': {k: v for k, v in g3.items() if v}, 'typed_vars': typed_vars, 'untyped_vars': untyped_vars,
  'fsm_style': fsm or ['none'], 'bool_flag_vars': bools}))
