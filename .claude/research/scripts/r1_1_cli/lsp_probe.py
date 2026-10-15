import socket, json, sys, time
port=int(sys.argv[1]); root=sys.argv[2]
s=socket.create_connection(("127.0.0.1",port),timeout=10)
def send(o):
    b=json.dumps(o).encode(); s.sendall(b"Content-Length: %d\r\n\r\n"%len(b)+b)
buf=b""
def recv():
    global buf
    while True:
        i=buf.find(b"\r\n\r\n")
        if i>=0:
            n=int([l for l in buf[:i].split(b"\r\n") if l.lower().startswith(b"content-length")][0].split(b":")[1])
            if len(buf)>=i+4+n:
                m=buf[i+4:i+4+n]; buf=buf[i+4+n:]; return json.loads(m)
        buf+=s.recv(65536)
send({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"processId":None,"rootUri":"file://"+root,"capabilities":{}}})
while True:
    m=recv()
    if m.get("id")==1: print("INIT caps keys:",sorted(m["result"]["capabilities"].keys())); break
send({"jsonrpc":"2.0","method":"initialized","params":{}})
txt=open(root+"/s_type.gd").read()
send({"jsonrpc":"2.0","method":"textDocument/didOpen","params":{"textDocument":{"uri":"file://"+root+"/s_type.gd","languageId":"gdscript","version":1,"text":txt}}})
t=time.time(); s.settimeout(8)
try:
    while time.time()-t<8:
        m=recv()
        if m.get("method")=="textDocument/publishDiagnostics": print("DIAG",json.dumps(m["params"])[:400]); break
        else: print("other msg:",str(m)[:150])
except Exception as e: print("no diag:",e)
send({"jsonrpc":"2.0","id":2,"method":"textDocument/documentSymbol","params":{"textDocument":{"uri":"file://"+root+"/main.gd"}}})
try:
    while True:
        m=recv()
        if m.get("id")==2: print("SYMBOLS",json.dumps(m["result"])[:300]); break
except Exception as e: print("no symbols:",e)
