import re,json,sys
t=open('pu/renames_map_3_to_4.cpp').read()
out={}
for m in re.finditer(r'RenamesMap3To4::(\w+)\[\]\[2\] = \{(.*?)\n\};',t,re.S):
    name=m.group(1); body=m.group(2); pairs=[]
    for line in body.split('\n'):
        s=line.strip()
        if s.startswith('//'): continue
        mm=re.match(r'\{\s*"([^"]*(?:\\.[^"]*)*)",\s*(.*?)\s*\},?\s*(//\s*(.*))?$',s)
        if mm and mm.group(1)!='' :
            new=mm.group(2).strip()
            pairs.append((mm.group(1),new,(mm.group(4) or '')))
    out[name]=pairs
json.dump(out,open('renames.json','w'),indent=0)
for k,v in out.items(): print(k,len(v))
