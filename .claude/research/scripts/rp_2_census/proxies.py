import re,os,sys
EX=re.compile(r'^\s*@export')
RES=re.compile(r'^\s*(?:class_name\s+\w+\s+)?extends\s+Resource\b|^\s*extends\s+(?:\w*Resource\w*)\b')
AC=re.compile(r'\badd_child\(')
def run(spec):
    name,roots=spec.split('=')
    gd=ts=loc=ex=res=ac=0
    for r in roots.split(','):
        for dp,dn,fn in os.walk(r):
            dn[:]=[d for d in dn if d!='.git']
            for f in fn:
                p=os.path.join(dp,f)
                if f.endswith('.tscn'): ts+=1
                if f.endswith('.gd'):
                    gd+=1
                    for l in open(p,errors='ignore'):
                        s=l.strip()
                        if s and not s.startswith('#'): loc+=1
                        if EX.match(l): ex+=1
                        if RES.match(l): res+=1
                        if AC.search(l): ac+=1
    k=max(loc,1)/1000
    print(f"{name}: gd={gd} tscn={ts} loc={loc} export/KLOC={ex/k:.1f} resource_scripts={res} add_child/KLOC={ac/k:.1f} tscn/gd={ts/max(gd,1):.2f}")
for s in sys.argv[1:]: run(s)
