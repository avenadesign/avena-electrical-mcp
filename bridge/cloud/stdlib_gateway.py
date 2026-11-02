import os,json,hmac,time,secrets,queue,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
C=os.environ['AVENA_MCP_CLIENT_TOKEN'];A=os.environ['AVENA_AGENT_TOKEN']
if min(len(C),len(A))<40 or C==A: raise RuntimeError('secure distinct tokens required')
Q=queue.Queue(maxsize=30); P={};L=threading.Lock();LAST=[0.]
T={'autocad_system_status':'system_status','autocad_drawing_info':'drawing_info','autocad_list_layers':'layer_list','autocad_list_blocks':'block_list'}
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def write(self,status,obj=None):
  data=b'' if obj is None else json.dumps(obj,ensure_ascii=False).encode()
  self.send_response(status);self.send_header('Content-Type','application/json')
  self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers()
  if data:self.wfile.write(data)
 def ok(self,token):return hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token)
 def do_GET(self):
  if self.path=='/agent/poll':
   if not self.ok(A):return self.write(401,{'error':'unauthorized'})
   LAST[0]=time.monotonic()
   try:v=Q.get(timeout=15)
   except queue.Empty:v={'idle':True}
   return self.write(200,v)
  if self.path=='/mcp':
   if not self.ok(C):return self.write(401,{'error':'unauthorized'})
   return self.write(405,{'error':'POST-only MCP'})
  if self.path=='/health':
   if not self.ok(C):return self.write(401,{'error':'unauthorized'})
   return self.write(200,{'ok':True,'agent_online':time.monotonic()-LAST[0]<40})
  return self.write(404,{})
 def do_POST(self):
  if self.path=='/mcp':token=C
  elif self.path=='/agent/result':token=A
  else:return self.write(404,{})
  if not self.ok(token):return self.write(401,{'error':'unauthorized'})
  try:
   n=int(self.headers.get('Content-Length','0'))
   if n<0 or n>2097152:return self.write(413,{})
   msg=json.loads(self.rfile.read(n))
   if not isinstance(msg,dict):return self.write(400,{})
  except (ValueError,UnicodeError):return self.write(400,{})
  if self.path=='/agent/result':
   with L:item=P.get(msg.get('id'))
   if item:item['val']=msg.get('result');item['event'].set()
   return self.write(200,{'ok':bool(item)})
  name=msg.get('method');mid=msg.get('id')
  if mid is None:return self.write(202)
  err=None;result=None
  if name=='initialize':result={'protocolVersion':'2025-06-18','capabilities':{'tools':{}},'serverInfo':{'name':'Avena Electrical','version':'0.4.0'}}
  elif name=='ping':result={}
  elif name=='tools/list':
   result={'tools':[{'name':x,'description':'Read-only AutoCAD query','inputSchema':{'type':'object','properties':{},'additionalProperties':False},'annotations':{'readOnlyHint':True}} for x in ['workstation_status']+list(T)]}
  elif name=='tools/call':
   p=msg.get('params') or {};tool=p.get('name')
   if p.get('arguments') or tool not in ['workstation_status']+list(T):err={'code':-32602,'message':'unsupported tool/args'}
   elif tool=='workstation_status':result={'content':[{'type':'text','text':json.dumps({'online':time.monotonic()-LAST[0]<40})}]}
   else:
    key=secrets.token_hex(16);item={'event':threading.Event(),'val':None}
    with L:P[key]=item
    try:
     Q.put_nowait({'id':key,'tool':T[tool],'arguments':{}})
     item['event'].wait(45)
     reply=item['val'] or {'ok':False,'error':'windows_offline_or_timeout'}
     result={'content':[{'type':'text','text':json.dumps(reply,ensure_ascii=False)}],'isError':not reply.get('ok',False)}
    except queue.Full:result={'content':[{'type':'text','text':'queue_full'}],'isError':True}
    finally:
     with L:P.pop(key,None)
  else:err={'code':-32601,'message':'unsupported method'}
  return self.write(200,{'jsonrpc':'2.0','id':mid,**({'error':err} if err else {'result':result})})
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',18727),H).serve_forever()
