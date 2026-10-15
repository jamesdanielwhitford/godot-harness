import subprocess,json,sys,os,time
cmd=sys.argv[1:]
p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
i=0
def rpc(m,params=None,wait=60):
    global i; i+=1
    p.stdin.write(json.dumps({"jsonrpc":"2.0","id":i,"method":m,"params":params or {}})+"\n"); p.stdin.flush()
    while True:
        l=p.stdout.readline()
        if not l: return None
        try: d=json.loads(l)
        except: continue
        if d.get("id")==i: return d
def call(n,a): 
    r=rpc("tools/call",{"name":n,"arguments":a}); print(">>",n,json.dumps(r)[:900]); return r
r=rpc("initialize",{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"t","version":"0"}})
print(json.dumps(r)[:300])
p.stdin.write(json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"})+"\n");p.stdin.flush()
r=rpc("tools/list"); print("TOOLS",[t["name"] for t in r["result"]["tools"]])
proj=os.environ["PROJ"]
call("run_project",{"projectPath":proj})
call("game_call" if False else "godot_call",{"toolName":"game_eval","arguments":{"code":"return get_tree().current_scene.n"}})
call("stop_project",{})
p.terminate()
