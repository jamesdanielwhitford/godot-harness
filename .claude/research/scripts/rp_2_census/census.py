import json,re,sys,os,subprocess,collections
S='/tmp/claude-0/-home-user/77c17b82-ea72-5e78-90c8-1959b76a4dc3/scratchpad'
rules=[r for r in json.load(open(S+'/research/r1_5_work/rules.json')) if r.get('false_positive_risk')!='AUTO']
NOISY={'syn-semicolon-end','syn-python-elif-colon-missing','syn-dot-super','syn-int-div'}
rules=[r for r in rules if r['id'] not in NOISY]
comp=[(r['id'],re.compile(r['regex']),tuple(r['applies_to'].split(','))) for r in rules]
VAR_T=re.compile(r'^\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:static\s+)?var\s+\w+\s*(:|:=)')
VAR_U=re.compile(r'^\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:static\s+)?var\s+\w+\s*(=|$)')
FUNC=re.compile(r'^\s*(?:static\s+)?func\s+\w+')
FUNC_R=re.compile(r'^\s*(?:static\s+)?func\s+\w+\s*\(.*\)\s*->')
def walk(root):
    for dp,dn,fn in os.walk(root):
        dn[:]=[d for d in dn if d!='.git']
        for f in fn: yield os.path.join(dp,f)
def analyse(root):
    out={}
    projs=[p for p in walk(root) if p.endswith('/project.godot')]
    projs.sort(key=lambda p:p.count('/'))
    out['projects']=[os.path.relpath(p,root) for p in projs][:12]
    out['n_projects']=len(projs)
    if projs:
        t=open(projs[0],errors='ignore').read()
        m=re.search(r'config/features=PackedStringArray\(([^)]*)\)',t); out['features']=m.group(1) if m else None
        m=re.search(r'config/name="([^"]*)"',t); out['name']=m.group(1) if m else None
        m=re.search(r'\[autoload\](.*?)(\n\[|\Z)',t,re.S); out['autoloads']=len(re.findall(r'^\w+="',m.group(1),re.M)) if m else 0
        out['gl']=bool(re.search(r'config_version=5',t))
    tot=collections.Counter(); hits=collections.defaultdict(list)
    for p in walk(root):
        ext=os.path.splitext(p)[1]
        if ext not in ('.gd','.tscn','.tres'): continue
        rel=os.path.relpath(p,root); addon='addons/' in rel
        try: lines=open(p,errors='ignore').read().split('\n')
        except: continue
        if ext=='.gd':
            k='gd_addon' if addon else 'gd_game'
            tot[k+'_files']+=1; tot[k+'_loc']+=sum(1 for l in lines if l.strip() and not l.strip().startswith('#'))
            for l in lines:
                if VAR_T.match(l): tot[k+'_var_typed']+=1
                elif VAR_U.match(l): tot[k+'_var_untyped']+=1
                if FUNC.match(l):
                    tot[k+'_func']+=1
                    if FUNC_R.match(l): tot[k+'_func_ret']+=1
        else: tot[ext]+=1
        for i,l in enumerate(lines,1):
            if ext=='.gd' and l.lstrip().startswith('#'): continue
            for rid,rx,ap in comp:
                if ext in ap and rx.search(l):
                    hits[rid].append(f'{rel}:{i}:{l.strip()[:80]}')
    out['tot']=dict(tot); out['hits']={k:len(v) for k,v in hits.items()}
    out['hit_examples']={k:v[:2] for k,v in hits.items()}
    return out
if __name__=='__main__':
    d=sys.argv[1]; name=os.path.basename(d.rstrip('/'))
    r=analyse(d)
    g=lambda a:subprocess.run(['git','-C',d]+a,capture_output=True,text=True).stdout.strip()
    r['commit']=g(['rev-parse','HEAD']); r['date']=g(['log','-1','--format=%cs']); r['url']=g(['remote','get-url','origin'])
    lic=[f for f in os.listdir(d) if re.match(r'(?i)(licen[sc]e|copying|unlicense)',f)]
    r['license_files']=lic
    json.dump(r,open(f'{S}/research/rp2_work/census_{name}.json','w'),indent=1)
    print(name,'done')
