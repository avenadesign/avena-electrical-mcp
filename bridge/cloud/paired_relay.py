"""Avena Electrical v0.8: paired, read-only queries plus approved additive CAD drawing."""
import hashlib,json,os,queue,secrets,sqlite3,threading,time,hmac
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from drawing_schema_v2 import validate,preview,SCHEMA
from edit_schema import validate_edits,preview as edit_preview,SCHEMA as EDIT_SCHEMA
from analysis_catalog import READ_TOOLS,validate_args

MCP_SECRET=os.environ["AVENA_MCP_CLIENT_TOKEN"]
DB=os.environ.get("AVENA_OAUTH_DB","/opt/avena-elc/state/oauth.sqlite")
queues={};waiting={};last={};expired={};guard=threading.RLock()

def agent_online(pid):
 now=time.monotonic()
 with guard:
  return (now-last.get(pid,0)<35 or
          any(t["pid"]==pid and t.get("claimed",False) and
              now-t.get("claimed_at",0)<115 for t in waiting.values()))

def rpc_wait_seconds(name):
 if name in READ_TOOLS and READ_TOOLS[name]["slow"]:return 103
 if name in ("autocad_drawing_apply","autocad_entity_edit_apply"):return 100
 return 80

def error_result(error,**details):
 return {"content":[{"type":"text","text":json.dumps({"ok":False,"error":error,**details})}],
         "isError":True}

TOOLS={"autocad_system_status":"system_status","autocad_drawing_info":"drawing_info","autocad_list_layers":"layer_list","autocad_list_blocks":"block_list"}

def get_device(header):
 if not header.startswith("Bearer ") or len(header)>170:return None
 try:
  with sqlite3.connect(DB,timeout=8) as c:
   p=c.execute("SELECT id FROM pairings WHERE device_token_hash=? AND revoked=0",
       (hashlib.sha256(header[7:].encode()).hexdigest(),)).fetchone()
  return p[0] if p else None
 except sqlite3.Error:return None
def verify_pair(pid):
 if not isinstance(pid,str) or len(pid)!=32:return False
 try:
  with sqlite3.connect(DB,timeout=8) as c:
   return c.execute("SELECT 1 FROM pairings WHERE id=? AND revoked=0",(pid,)).fetchone() is not None
 except sqlite3.Error:return False

class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def send(self,status,obj=None):
  data=b"" if obj is None else json.dumps(obj,ensure_ascii=False).encode()
  self.send_response(status);self.send_header("Content-Type","application/json")
  self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(data)))
  self.end_headers()
  if data and self.command!="HEAD":self.wfile.write(data)
 def get_auth(self):
  return get_device(self.headers.get("Authorization",""))
 def do_GET(self):
  if self.path=="/agent/poll":
   pid=self.get_auth()
   if not pid:return self.send(401,{"error":"unauthorized"})
   with guard:
    last[pid]=time.monotonic()
    q=queues.setdefault(pid,queue.Queue(maxsize=20))
   try:job=q.get(timeout=13)
   except queue.Empty:job={"idle":True}
   if isinstance(job,dict) and isinstance(job.get("id"),str):
    with guard:
     task=waiting.get(job["id"])
     if task and task["pid"]==pid:
      task["claimed"]=True
      task["claimed_at"]=time.monotonic()
     else:
      # An RPC may time out while an unclaimed job is queued. Never execute
      # that stale job later, especially if it would modify the drawing.
      job={"idle":True}
   return self.send(200,job)
  if self.path=="/agent/status":
   pid=self.get_auth()
   if not pid:return self.send(401,{"error":"unauthorized"})
   return self.send(200,{"ok":True,"paired":True,"connection_id":pid[:8],"online":agent_online(pid)})
  return self.send(404,{"error":"not_found"})
 def do_POST(self):
  if self.path=="/mcp":
   if not hmac.compare_digest(self.headers.get("Authorization",""),"Bearer "+MCP_SECRET):
    return self.send(401,{"error":"unauthorized"})
   pid=self.headers.get("X-Avena-Pair-ID","")
   if not verify_pair(pid):return self.send(403,{"error":"invalid_pair"})
  elif self.path=="/agent/result":
   pid=self.get_auth()
   if not pid:return self.send(401,{"error":"unauthorized"})
  else:return self.send(404,{"error":"not_found"})
  try:
   n=int(self.headers.get("Content-Length","0"))
   if not 0<n<8388608:return self.send(413,{"error":"size"})
   msg=json.loads(self.rfile.read(n))
   if not isinstance(msg,dict):return self.send(400,{"error":"json"})
  except (ValueError,UnicodeError):return self.send(400,{"error":"json"})
  if self.path=="/agent/result":
   key=msg.get("id")
   with guard:
    now=time.monotonic()
    for old,entry in list(expired.items()):
     if entry["expires"]<now:expired.pop(old,None)
    task=waiting.get(key) if isinstance(key,str) else None
    if not task:
     stale=expired.get(key) if isinstance(key,str) else None
     if stale and stale["pid"]==pid:
      expired.pop(key,None)
      return self.send(200,{"accepted":False,"stale":True})
     return self.send(403,{"error":"foreign_task"})
    if task["pid"]!=pid:return self.send(403,{"error":"foreign_task"})
    task["reply"]=msg.get("result",{"ok":False,"error":"missing"})
    task["event"].set()
   return self.send(200,{"accepted":True})
  if msg.get("jsonrpc")!="2.0":return self.send(400,{"error":"rpc"})
  mid=msg.get("id");method=msg.get("method")
  if mid is None:return self.send(202)
  result=None;error=None
  if method=="initialize":
   result={"protocolVersion":"2025-06-18","capabilities":{"tools":{}},"serverInfo":{"name":"Avena Electrical","version":"0.9.6"}}
  elif method=="ping":result={}
  elif method=="tools/list":
   result={"tools":[
     *[{"name":name,"description":"Read-only AutoCAD query","inputSchema":{"type":"object","properties":{},"additionalProperties":False},"annotations":{"readOnlyHint":True,"destructiveHint":False}} for name in ["workstation_status",*TOOLS]],
     *[{"name":name,"description":spec["description"],"inputSchema":spec["schema"],"annotations":{"readOnlyHint":not spec.get("mutates_view",False),"destructiveHint":False}} for name,spec in READ_TOOLS.items()],
     {"name":"autocad_drawing_preview","description":"Validate and summarize a plan to draw lines, polylines, circles, rectangles, text or existing blocks in the active DWG. No DWG changes.","inputSchema":{"type":"object","required":["operations"],"additionalProperties":False,"properties":{"operations":SCHEMA}},"annotations":{"readOnlyHint":True,"destructiveHint":False}},
     {"name":"autocad_entity_edit_preview","description":"Preview restricted edits on existing AutoCAD entity handles: move, relabel text, or change layer/color. Does not edit DWG.","inputSchema":{"type":"object","required":["operations"],"additionalProperties":False,"properties":{"operations":EDIT_SCHEMA}},"annotations":{"readOnlyHint":True,"destructiveHint":False}},
     {"name":"autocad_entity_edit_apply","description":"Edit existing DWG entities by handle. Windows user MUST confirm on screen. NO deletes or automatic saves.","inputSchema":{"type":"object","required":["operations"],"additionalProperties":False,"properties":{"operations":EDIT_SCHEMA}},"annotations":{"readOnlyHint":False,"destructiveHint":False,"idempotentHint":False}},
     {"name":"autocad_drawing_apply","description":"DRAW the supplied additive operations in the active AutoCAD DWG. Local Windows human confirmation is REQUIRED before editing. Maximum 10 shapes per approval. No automatic save or deletion.","inputSchema":{"type":"object","required":["operations"],"additionalProperties":False,"properties":{"operations":SCHEMA}},"annotations":{"readOnlyHint":False,"destructiveHint":False,"idempotentHint":False}}
   ]}
  elif method=="tools/call":
   p=msg.get("params") or {};name=p.get("name")
   args=p.get("arguments") or {}
   plan=None
   read_arguments={}
   if name in READ_TOOLS:
    try:read_arguments=validate_args(name,args)
    except ValueError as exc:error={"code":-32602,"message":str(exc)}
   if name in ("autocad_drawing_preview","autocad_drawing_apply","autocad_entity_edit_preview","autocad_entity_edit_apply"):
    try:
     if not isinstance(args,dict) or set(args)!={"operations"}:raise ValueError("Expected operations array")
     plan=validate_edits(args["operations"]) if name.startswith("autocad_entity_edit_") else validate(args["operations"])
    except ValueError as exc:
     error={"code":-32602,"message":str(exc)}
   if error:
    pass
   elif name=="autocad_drawing_preview":
    result={"content":[{"type":"text","text":json.dumps(preview(plan),ensure_ascii=False)}]}
   elif name=="autocad_entity_edit_preview":
    result={"content":[{"type":"text","text":json.dumps(edit_preview(plan),ensure_ascii=False)}]}
   elif name not in ["workstation_status",*TOOLS,*READ_TOOLS,"autocad_drawing_apply","autocad_entity_edit_apply"] or (name in ["workstation_status",*TOOLS] and args):
    error={"code":-32602,"message":"Unknown tool or arguments"}
   elif name=="workstation_status":
    result={"content":[{"type":"text","text":json.dumps({"online":agent_online(pid),"paired":True,"connection_id":pid[:8]})}]}
   else:
    with guard:
     if any(x["pid"]==pid for x in waiting.values()):
      result=error_result("agent_busy",message="Another AutoCAD request is in progress; retry later.")
      queue_task=False
     elif not agent_online(pid):
      result=error_result("agent_offline",message="Windows agent has not polled recently.")
      queue_task=False
     else:
      key=secrets.token_hex(16)
      task={"pid":pid,"event":threading.Event(),"reply":None,
            "claimed":False,"claimed_at":None}
      waiting[key]=task
      q=queues.setdefault(pid,queue.Queue(maxsize=20))
      queue_task=True
    if queue_task:
     try:
      upstream=READ_TOOLS[name]["engine"] if name in READ_TOOLS else TOOLS.get(name)
      q.put_nowait({"id":key,"tool":"__avena_edit_batch__" if name=="autocad_entity_edit_apply"
                    else "__avena_draw_batch__" if name=="autocad_drawing_apply"
                    else upstream,
                    "arguments":{"operations":plan} if name in ("autocad_drawing_apply","autocad_entity_edit_apply")
                    else read_arguments if name in READ_TOOLS else {}})
      finished=task["event"].wait(rpc_wait_seconds(name))
      if finished:
       answer=task["reply"] if task["reply"] is not None else {"ok":False,"error":"agent_missing_result"}
      else:
       answer={"ok":False,"error":"agent_timeout",
               "message":"Windows did not finish the requested CAD operation before its deadline.",
               "tool":name,"timeout_seconds":rpc_wait_seconds(name)}
       with guard:
        expired[key]={"pid":pid,"expires":time.monotonic()+180}
      if name in READ_TOOLS and READ_TOOLS[name]["image"] and answer.get("ok"):
       images=[item for item in answer.get("content",[]) if item.get("type")=="image" and item.get("mimeType")=="image/png"]
       if images and sum(len(item.get("data","")) for item in images)<3_500_000:
        result={"content":images,"isError":False}
       else:
        result=error_result("image_unavailable_or_too_large")
      else:
       result={"content":[{"type":"text","text":json.dumps(answer,ensure_ascii=False)}],
               "isError":not answer.get("ok",False)}
     except queue.Full:
      result=error_result("agent_queue_full")
     finally:
      with guard:waiting.pop(key,None)
  else:error={"code":-32601,"message":"Unknown method"}
  return self.send(200,{"jsonrpc":"2.0","id":mid,**({"error":error} if error else {"result":result})})

if __name__=="__main__":ThreadingHTTPServer(("127.0.0.1",18727),H).serve_forever()
