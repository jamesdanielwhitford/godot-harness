import socket, json, sys, time
port=int(sys.argv[1]); root=sys.argv[2]; files=sys.argv[3:]
s=socket.create_connection(("127.0.0.1",port),timeout=10)
def send(o):
    b=json.dumps(o).encode(); s.sendall(b"Content-Length: %d\r\n\r\n"%len(b)+b)
buf=b""
def recv(timeout):
    global buf
    end=time.time()+timeout
    while True:
        i=buf.find(b"\r\n\r\n")
        if i>=0:
            n=int([l for l in buf[:i].split(b"\r\n") if l.lower().startswith(b"content-length")][0].split(b":")[1])
            if len(buf)>=i+4+n:
                m=buf[i+4:i+4+n]; buf=buf[i+4+n:]; return json.loads(m)
        rem=end-time.time()
        if rem<=0: return None
        s.settimeout(rem)
        try: buf+=s.recv(65536)
        except socket.timeout: return None
t0=time.time()
send({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"processId":None,"rootUri":"file://"+root,"capabilities":{}}})
while True:
    m=recv(30)
    if m is None: print("NO INIT"); sys.exit(1)
    if m.get("id")==1: print("init in %.2fs"%(time.time()-t0)); break
send({"jsonrpc":"2.0","method":"initialized","params":{}})
# phase A: passive wait, nothing opened
t=time.time(); got=[]
while time.time()-t<6:
    m=recv(1)
    if m: got.append(m.get("method") or ("resp",m.get("id")))
print("PHASE A (no didOpen, 6s idle): msgs=",got)
# phase B: didOpen each file, twice (cold then warm)
for rnd in range(3):
  for f in files:
    p=root+"/"+f; uri="file://"+p; txt=open(p).read()
    t=time.time()
    if rnd==0: send({"jsonrpc":"2.0","method":"textDocument/didOpen","params":{"textDocument":{"uri":uri,"languageId":"gdscript","version":1,"text":txt}}})
    else: send({"jsonrpc":"2.0","method":"textDocument/didChange","params":{"textDocument":{"uri":uri,"version":rnd+1},"contentChanges":[{"text":txt}]}})
    d=None
    while time.time()-t<8:
        m=recv(8-(time.time()-t))
        if m is None: break
        if m.get("method")=="textDocument/publishDiagnostics" and m["params"]["uri"]==uri: d=m; break
    if d: print("round%d %s: %.3fs diags=%s"%(rnd,f,time.time()-t,[(x['range']['start']['line']+1,x['severity'],x['message'][:60]) for x in d['params']['diagnostics']]))
    else: print("round%d %s: NO diagnostics in 8s"%(rnd,f))
