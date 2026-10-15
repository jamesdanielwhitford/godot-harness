import re,os,sys
VT=re.compile(r'^\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:static\s+)?var\s+\w+\s*(:|:=)')
VU=re.compile(r'^\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:static\s+)?var\s+\w+\s*(=|$)')
F=re.compile(r'^\s*(?:static\s+)?func\s+\w+'); FR=re.compile(r'^\s*(?:static\s+)?func\s+\w+\s*\(.*\)\s*->')
def run(root):
    t=u=f=fr=files=loc=0
    for dp,dn,fn in os.walk(root):
        dn[:]=[d for d in dn if d!='.git']
        for x in fn:
            if not x.endswith('.gd'): continue
            files+=1
            for l in open(os.path.join(dp,x),errors='ignore'):
                if l.strip() and not l.strip().startswith('#'): loc+=1
                if VT.match(l): t+=1
                elif VU.match(l): u+=1
                if F.match(l):
                    f+=1
                    if FR.match(l): fr+=1
    return files,loc,t/max(1,t+u),fr/max(1,f)
for a in sys.argv[1:]:
    r=run(a); print(f"{a}: files={r[0]} loc={r[1]} var_typed={r[2]:.2f} ret_typed={r[3]:.2f}")
