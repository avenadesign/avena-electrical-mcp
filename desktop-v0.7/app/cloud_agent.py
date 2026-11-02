"""Windows-only Avena Electrical cloud agent, persistent activation via DPAPI.
Only read-only CAD MCP tools are reachable from ChatGPT. Python 3.11+ stdlib.
"""
from __future__ import annotations
import ctypes,ctypes.wintypes,json,os,secrets,time,urllib.request,urllib.error
from pathlib import Path
BASE=os.getenv("AVENA_GATEWAY_URL","https://elc.avenaai.ir").rstrip("/")
ALLOWED={"system_status","drawing_info","layer_list","block_list"}
LOCAL="http://127.0.0.1:18327/mcp"

def _file():
 return Path(os.getenv("LOCALAPPDATA",str(Path.home()))) / "AvenaElectrical" / "device.json"

def _dpapi(payload,decrypt=False):
 if os.name!="nt":raise OSError("Windows DPAPI required")
 class Blob(ctypes.Structure):
  _fields_=[("cbData",ctypes.wintypes.DWORD),("pbData",ctypes.POINTER(ctypes.c_ubyte))]
 raw=ctypes.create_string_buffer(payload);src=Blob(len(payload),ctypes.cast(raw,ctypes.POINTER(ctypes.c_ubyte)));dest=Blob()
 dll=ctypes.WinDLL("crypt32",use_last_error=True)
 dll.CryptProtectData.argtypes=[ctypes.POINTER(Blob),ctypes.c_wchar_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.wintypes.DWORD,ctypes.POINTER(Blob)]
 dll.CryptUnprotectData.argtypes=[ctypes.POINTER(Blob),ctypes.POINTER(ctypes.c_wchar_p),ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.wintypes.DWORD,ctypes.POINTER(Blob)]
 dll.CryptProtectData.restype=dll.CryptUnprotectData.restype=ctypes.wintypes.BOOL
 done=(dll.CryptUnprotectData(ctypes.byref(src),None,None,None,None,0,ctypes.byref(dest)) if decrypt else dll.CryptProtectData(ctypes.byref(src),"Avena Electrical",None,None,None,0x01,ctypes.byref(dest)))
 if not done:raise ctypes.WinError(ctypes.get_last_error())
 try:return ctypes.string_at(dest.pbData,dest.cbData)
 finally:
  release=ctypes.WinDLL("kernel32",use_last_error=True).LocalFree
  release.argtypes=[ctypes.c_void_p];release.restype=ctypes.c_void_p
  release(ctypes.cast(dest.pbData,ctypes.c_void_p))

def _read_state():
 try:
  val=json.loads(_file().read_text(encoding="utf-8"))
  if isinstance(val,dict) and isinstance(val.get("device_id"),str):return val
 except (OSError,ValueError):pass
 return {"device_id":secrets.token_hex(16)}
def _load_token(state):
 try:return _dpapi(bytes.fromhex(state["encrypted_token"]),True).decode("ascii")
 except (KeyError,ValueError,OSError,UnicodeError):return None
def has_saved_activation():return bool(_load_token(_read_state()))
def _save_state(state):
 if os.name!="nt":raise OSError("Windows required")
 file=_file();file.parent.mkdir(parents=True,exist_ok=True)
 temp=file.with_suffix(".tmp")
 temp.write_text(json.dumps(state),encoding="utf-8")
 os.replace(temp,file)

def cloud_request(method,path,token=None,payload=None,timeout=25):
 data=json.dumps(payload).encode() if payload is not None else None
 headers={"Content-Type":"application/json","User-Agent":"AvenaElectricalWindows/0.7"}
 if token:headers["Authorization"]="Bearer "+token
 req=urllib.request.Request(BASE+path,data=data,headers=headers,method=method)
 with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read(4194304))

def activated_token(code=None):
 state=_read_state()
 old=_load_token(state)
 if old:
  try:
   status=cloud_request("GET","/agent/status",old,timeout=10)
   if status.get("paired"):return old
  except urllib.error.HTTPError as e:
   if e.code!=401:raise
  except (OSError,TimeoutError):raise
 code=code or os.environ.pop("AVENA_ACTIVATION_CODE","")
 value=code.upper().replace("-","").replace(" ","")
 if len(value)!=20 or not value.isascii() or not value.isalnum():
  raise ValueError("کد لایسنس ۲۰ کاراکتری الزامی است.")
 obj=cloud_request("POST","/api/device/activate",payload={"activation_code":code,"device_id":state["device_id"]})
 token=obj.get("device_token")
 if not isinstance(token,str) or len(token)<40:raise ValueError("Server returned invalid device token")
 state["encrypted_token"]=_dpapi(token.encode("ascii"),False).hex()
 _save_state(state)
 return token

def local_post(name,params,token,session=None,notification=False):
 item={"jsonrpc":"2.0","method":name,"params":params}
 if not notification:item["id"]=secrets.randbelow(900000)+100000
 headers={"Authorization":"Bearer "+token,"Content-Type":"application/json",
          "Accept":"application/json, text/event-stream","MCP-Protocol-Version":"2025-06-18"}
 if session:headers["Mcp-Session-Id"]=session
 req=urllib.request.Request(LOCAL,data=json.dumps(item).encode(),headers=headers,method="POST")
 with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=18) as r:
  sess=r.headers.get("Mcp-Session-Id") or session
  if notification or r.status==202:return {},sess
  if "text/event-stream" in r.headers.get("Content-Type",""):
   for line in r:
    if line.startswith(b"data:"):
     try:obj=json.loads(line[5:].strip())
     except ValueError:continue
     if "result" in obj or "error" in obj:return obj,sess
   raise RuntimeError("MCP event result missing")
  return json.loads(r.read(4194304)),sess

def call_local(tool,token):
 if tool not in ALLOWED:return {"ok":False,"error":"tool_denied"}
 handshake,sess=local_post("initialize",{"protocolVersion":"2025-06-18","capabilities":{},
   "clientInfo":{"name":"Avena Electrical","version":"0.7"}},token)
 if "result" not in handshake:raise RuntimeError("Local MCP handshake refused")
 local_post("notifications/initialized",{},token,sess,notification=True)
 response,_=local_post("tools/call",{"name":tool,"arguments":{}},token,sess)
 if "error" in response:return {"ok":False,"error":"local_mcp_error","detail":response["error"]}
 result=response.get("result",{})
 return {"ok":not result.get("isError",False),"content":result.get("content",[])}

def main():
 local_secret=os.getenv("AVENA_LOCAL_MCP_TOKEN","")
 if len(local_secret)<32:raise RuntimeError("MCP local token missing")
 device_secret=activated_token()
 delay=3
 print("[AVENA] Licensed. Connecting to elc.avenaai.ir",flush=True)
 while True:
  try:
   task=cloud_request("GET","/agent/poll",device_secret,timeout=28)
   delay=3
   if task.get("idle"):continue
   key=task.get("id");tool=task.get("tool")
   if not isinstance(key,str):continue
   if tool not in ALLOWED or task.get("arguments") not in ({},None):
    result={"ok":False,"error":"tool_denied"}
   else:
    try:result=call_local(tool,local_secret)
    except Exception as exc:result={"ok":False,"error":"local_mcp_failed","detail":type(exc).__name__}
   cloud_request("POST","/agent/result",device_secret,{"id":key,"result":result})
  except KeyboardInterrupt:return
  except urllib.error.HTTPError as exc:
   if exc.code in (401,403):raise RuntimeError("Device license revoked") from exc
  except (OSError,ValueError,TimeoutError):pass
  time.sleep(delay);delay=min(delay*2,30)
if __name__=="__main__":main()
