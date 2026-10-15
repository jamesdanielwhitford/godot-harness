import os,shutil,sys
src,dst=sys.argv[1:3]; ex=('.gd','.tscn','.tres','.cfg','.gdshader','.gdshaderinc','.uid','.json','.godot')
for dp,dn,fn in os.walk(src):
    dn[:]=[d for d in dn if d not in ('.git',)]
    for f in fn:
        if f=='project.godot' or f.endswith(ex):
            s=os.path.join(dp,f); r=os.path.relpath(s,src); t=os.path.join(dst,r)
            os.makedirs(os.path.dirname(t),exist_ok=True); shutil.copy2(s,t)
