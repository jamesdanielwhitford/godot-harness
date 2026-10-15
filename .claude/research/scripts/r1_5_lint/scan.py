import json,re,sys,os,collections
rules=json.load(open('rules.json'))
def files(root):
    for dp,dn,fn in os.walk(root):
        if '/.git' in dp: continue
        for f in fn:
            if f.endswith(('.gd','.tscn','.tres')): yield os.path.join(dp,f)
def scan(root):
    comp=[]
    for r in rules:
        try: comp.append((r,re.compile(r['regex']),tuple(r['applies_to'].split(','))))
        except re.error as e: print('BAD',r['id'],e); 
    hits=collections.defaultdict(list)
    n=0
    for p in files(root):
        ext=os.path.splitext(p)[1]; n+=1
        for i,l in enumerate(open(p,errors='ignore'),1):
            s=l.lstrip()
            if ext=='.gd' and s.startswith('#'): continue
            for r,rx,ap in comp:
                if ext in ap and rx.search(l): hits[r['id']].append(f'{p}:{i}:{l.strip()[:90]}')
    return n,hits
if __name__=='__main__':
    n,h=scan(sys.argv[1]); print('files',n,'rules_hit',len(h),'total_hits',sum(map(len,h.values())))
    json.dump(h,open(sys.argv[2],'w'),indent=0)
    for k,v in sorted(h.items(),key=lambda x:-len(x[1]))[:40]: print(len(v),k,v[0])
