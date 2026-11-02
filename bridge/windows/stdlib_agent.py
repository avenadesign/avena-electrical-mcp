"""Avena Electrical Windows agent v0.5. Python stdlib only.
Outbound HTTPS polling, read-only allowlist, local loopback MCP Streamable HTTP.
"""
import json,os,time,urllib.request,urllib.error,secrets,sys
BASE=os.environ.get("AVENA_GATEWAY_URL","https://elc.avenaai.ir").rstrip("/")
LOCAL="http://127.0.0.1:18327/mcp"
AGENT=os.environ["AVENA_AGENT_TOKEN"]
LOCAL_SECRET=os.environ["AVENA_LOCAL_MCP_TOKEN"]
ALLOW={"system_status","drawing_info","layer_list","block_list"}
if len(AGENT)<40 or len(LOCAL_SECRET)<32:raise RuntimeError("Strong independent agent and local credentials required")
def cloud(method,path,payload=None):
 data=None if payload is None else json.dumps(payload).encode()
 req=urllib.request.Request(BASE+path,data=data,method=method,headers={"Authorization":"Bearer "+AGENT,"Content-Type":"application/json","User-Agent":"AvenaElectricalAgent/0.5"})
 with urllib.request.urlopen(req,timeout=33) as response:
  return json.loads(response.read(4194304))
def local_post(method,params,session=None,notification=False):
 data=json.dumps({"jsonrpc":"2.0",**({} if notification else {"id":secrets.randbelow(900000)+100000}),"method":method,"params":params}).encode()
 headers={"Authorization":"Bearer "+LOCAL_SECRET,"Content-Type":"application/json","Accept":"application/json, text/event-stream","MCP-Protocol-Version":"2025-06-18"}
 if session:headers["Mcp-Session-Id"]=session
 req=urllib.request.Request(LOCAL,data=data,method="POST",headers=headers)
 with urllib.request.urlopen(req,timeout=18) as r:
  sid=r.headers.get("Mcp-Session-Id") or session
  ctype=r.headers.get("Content-Type","")
  if r.status==202 or notification:return {},sid
  if "text/event-stream" in ctype:
   for line in r:
    if line.startswith(b"data:"):
     try:
      response=json.loads(line[5:].strip())
      if "result" in response or "error" in response:return response,sid
     except ValueError:continue
   raise ValueError("No MCP result event")
  return json.loads(r.read(4194304)),sid
def call_local(tool):
 init,session=local_post("initialize",{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"Avena Windows","version":"0.5"}})
 if "result" not in init:raise RuntimeError("Invalid MCP initialization")
 local_post("notifications/initialized",{},session,notification=True)
 outcome,_=local_post("tools/call",{"name":tool,"arguments":{}},session)
 if "error" in outcome:return {"ok":False,"error":"mcp_rpc_error","detail":outcome["error"]}
 result=outcome.get("result",{})
 return {"ok":not result.get("isError",False),"content":result.get("content",[]),"structuredContent":result.get("structuredContent")}
def main():
 print("[AVENA] Connecting to "+BASE+" | READ ONLY | COM remains on this PC",flush=True)
 delay=3
 while True:
  try:
   job=cloud("GET","/agent/poll")
   delay=3
   if job.get("idle"):continue
   task_id=job.get("id");tool=job.get("tool");args=job.get("arguments")
   if not isinstance(task_id,str):continue
   if tool not in ALLOW or args not in ({},None):
    response={"ok":False,"error":"tool_not_permitted"}
   else:
    try:response=call_local(tool)
    except Exception as exc:response={"ok":False,"error":"local_mcp_error","detail":str(exc)[:200]}
   cloud("POST","/agent/result",{"id":task_id,"result":response})
  except KeyboardInterrupt:
   print("[AVENA] Disconnected by user",flush=True);return
  except (urllib.error.URLError,TimeoutError,OSError,ValueError) as exc:
   print("[AVENA] Retry after connection error: "+type(exc).__name__,flush=True)
   time.sleep(delay);delay=min(delay*2,30)
if __name__=="__main__":main()
