import sys,re,os,shutil
d=sys.argv[1]; W='/tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad/research/rp2_work/scripts'
os.makedirs(d+'/__census',exist_ok=True)
shutil.copy(W+'/census_load_node.gd',d+'/__census/c.gd')
open(d+'/__census/c.tscn','w').write('[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://__census/c.gd" id="1"]\n[node name="C" type="Node"]\nscript = ExtResource("1")\n')
p=d+'/project.godot'; t=open(p,errors='ignore').read()
line='run/main_scene="res://__census/c.tscn"'
if re.search(r'^run/main_scene=.*$',t,re.M): t=re.sub(r'^run/main_scene=.*$',line,t,flags=re.M)
elif re.search(r'^\[application\]\s*$',t,re.M): t=re.sub(r'^\[application\]\s*$','[application]\n'+line,t,count=1,flags=re.M)
else: t+='\n[application]\n'+line+'\n'
open(p,'w').write(t)
