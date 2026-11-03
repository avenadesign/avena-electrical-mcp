"""OAuth protected front-end for the private Avena Electrical MCP relay (port 18728)."""
import html,json,os,re,time,urllib.error,urllib.request
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import parse_qs,urlencode,urlsplit
import oauth_core as auth

BACKEND="http://127.0.0.1:18727/mcp"
INTERNAL=os.environ["AVENA_MCP_CLIENT_TOKEN"]
META=auth.BASE+"/.well-known/oauth-protected-resource"
tries={}
def throttle(ip,limit=7,window=600):
 t=time.monotonic()
 arr=[x for x in tries.get(ip,[]) if t-x<window]
 arr.append(t);tries[ip]=arr
 return len(arr)<=limit
class Handler(BaseHTTPRequestHandler):
 server_version="AvenaElectricalOAuth/0.5";sys_version=""
 def log_message(self,*args):pass
 def ip(self):return self.headers.get("X-Real-IP",self.client_address[0])
 def reply(self,status,value=None,extra=None,ctype="application/json"):
  data=(json.dumps(value,ensure_ascii=False).encode() if isinstance(value,(dict,list)) else value.encode() if isinstance(value,str) else value or b"")
  self.send_response(status)
  self.send_header("Content-Type",ctype)
  self.send_header("Cache-Control","no-store")
  self.send_header("X-Content-Type-Options","nosniff")
  self.send_header("Content-Length",str(len(data)))
  for k,v in (extra or {}).items():self.send_header(k,v)
  self.end_headers()
  if data and self.command!="HEAD":self.wfile.write(data)
 def bad(self,detail,code=400):return self.reply(code,{"error":"invalid_request","error_description":detail})
 def challenge(self):
  self.reply(401,{"error":"unauthorized","error_description":"OAuth sign-in required"},{"WWW-Authenticate":'Bearer resource_metadata="'+META+'", scope="cad:read"'})
 def input(self,form=False):
  try:
   n=int(self.headers.get("Content-Length","0"))
   if not 0<n<=262144:return None
   raw=self.rfile.read(n)
   if form:
    d=parse_qs(raw.decode(),max_num_fields=24,keep_blank_values=True)
    return {k:v[0] for k,v in d.items()}
   d=json.loads(raw);return d if isinstance(d,dict) else None
  except (ValueError,UnicodeError,TypeError):return None
 def oauth_form(self,p,warning=""):
  names=("client_id","redirect_uri","response_type","scope","state","code_challenge","code_challenge_method","resource")
  hidden="".join('<input type="hidden" name="'+k+'" value="'+html.escape(str(p[k]),quote=True)+'">' for k in names if k in p and str(p[k])!="")
  page="""<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Avena Electrical — اتصال امن ChatGPT</title><style>
body{margin:0;background:#0b1320;color:#eff7ff;font:16px/1.8 Tahoma,Arial,sans-serif;min-height:100vh;display:grid;place-items:center}
main{box-sizing:border-box;max-width:460px;width:94vw;padding:35px;border-radius:20px;background:#14243a;border:1px solid #34506d}
h1{font-size:25px;margin:0 0 10px}p{color:#b9cadd}label{display:block;margin:20px 0 4px}
input{box-sizing:border-box;background:#0a1625;color:white;border:1px solid #5e7693;padding:14px;width:100%;border-radius:10px}
button{display:block;margin-top:20px;width:100%;padding:14px;border:0;border-radius:10px;background:#35d3c2;color:#06212b;font-weight:bold;cursor:pointer}
small{color:#96b4cf}.error{color:#ff8a8a}</style><main><h1>آونا الکتریکال</h1>
<p>برای اتصال ChatGPT به نقشه‌های AutoCAD، دسترسی <b>فقط خواندنی</b> را با کد اتصال دریافتی از elc.avenaai.ir/connect تأیید کن.</p>"""
  if warning:page+='<p class="error">'+html.escape(warning)+'</p>'
  page+='<form method="post" action="/oauth/authorize">'+hidden+'<label>کد ۲۰ کاراکتری اتصال</label><input type="text" name="activation_code" required autocomplete="off" placeholder="XXXX-XXXX-XXXX-XXXX-XXXX"><button type="submit">تأیید اتصال</button></form><p><small>رمز را فقط در این صفحه HTTPS وارد کن. این سرویس تغییری روی نقشه‌ها اعمال نمی‌کند.</small></p></main>'
  self.reply(200,page,{"Referrer-Policy":"no-referrer"},"text/html; charset=utf-8")
 def pairing_html(self,body):
  page="""<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>فعال‌سازی Avena Electrical</title><style>body{margin:0;background:#0b1320;color:#edf6ff;font:16px/1.9 Tahoma,Arial,sans-serif;min-height:100vh;display:grid;place-items:center}
main{box-sizing:border-box;width:min(94vw,470px);padding:32px;background:#14243a;border:1px solid #34506d;border-radius:20px}
h1{margin:0;font-size:24px}p{color:#b9cadd}label{display:block;margin:15px 0 4px}
input{box-sizing:border-box;background:#0a1625;color:#fff;border:1px solid #5e7693;padding:14px;width:100%;border-radius:10px;font:inherit;direction:ltr;text-align:left}
button{display:block;width:100%;padding:14px;margin-top:20px;border:0;border-radius:10px;background:#35d3c2;color:#06212b;font:inherit;font-weight:bold;cursor:pointer}
strong{display:block;border:1px dashed #35d3c2;color:#35d3c2;padding:15px;border-radius:10px;font:bold 19px Consolas,monospace;text-align:center;direction:ltr;overflow-wrap:anywhere}
small{color:#91a9c3}a{color:#35d3c2}</style><main>"""
  return page+body+"</main>"
 def do_GET(self):
  path=urlsplit(self.path).path
  if path=="/connect":
   content=self.pairing_html("""<h1>کد فعال‌سازی آونا الکتریکال</h1><p>شماره موبایلت را وارد کن تا برای آن یک لایسنس ثابت صادر شود. هر شماره فقط یک کد دارد؛ ثبت دوباره کد جدید نمی‌سازد. فعلاً بدون پیامک، OTP و اشتراک.</p>
<form action="/connect" method="post"><label>شماره موبایل</label><input type="tel" name="mobile" placeholder="09123456789" required maxlength="16"><button>دریافت کد اتصال</button></form>
<p><small>شماره در این نسخه تأیید نمی‌شود. در نسخه آزمایشی، واردکردن دوباره شماره همان کد را نمایش می‌دهد؛ تا فعال‌شدن OTP، هر کسی که شماره را بداند می‌تواند کد را ببیند.</small></p>""")
   return self.reply(200,content,ctype="text/html; charset=utf-8")
  if path in ("/.well-known/oauth-protected-resource","/.well-known/oauth-protected-resource/mcp"):
   return self.reply(200,{"resource":auth.RESOURCE,"authorization_servers":[auth.ISSUER],"scopes_supported":["cad:read","offline_access"]})
  if path in ("/.well-known/oauth-authorization-server","/.well-known/oauth-authorization-server/mcp"):
   return self.reply(200,{"issuer":auth.ISSUER,"authorization_endpoint":auth.BASE+"/oauth/authorize","token_endpoint":auth.BASE+"/oauth/token","registration_endpoint":auth.BASE+"/oauth/register","response_types_supported":["code"],"grant_types_supported":["authorization_code","refresh_token"],"token_endpoint_auth_methods_supported":["none"],"code_challenge_methods_supported":["S256"],"authorization_response_iss_parameter_supported":True,"scopes_supported":["cad:read","offline_access"]})
  if path=="/oauth/authorize":
   query={k:v[0] for k,v in parse_qs(urlsplit(self.path).query,keep_blank_values=True).items()}
   error=auth.validate(query)
   return self.bad(error) if error else self.oauth_form(query)
  if path=="/mcp":
   if not auth.verify(self.headers.get("Authorization","")):return self.challenge()
   return self.reply(405,{"error":"method_not_allowed"})
  return self.reply(404,{"error":"not_found"})
 def do_POST(self):
  path=urlsplit(self.path).path
  if path=="/connect":
   if not throttle("phone:"+self.ip(),6,3600):return self.bad("rate_limit",429)
   p=self.input(form=True)
   if not p:return self.bad("invalid_mobile")
   try:code=auth.new_pair(p.get("mobile",""))
   except auth.LicenseAlreadyExists:
    try:
     code=auth.restore_license_code(p.get("mobile",""))
    except RuntimeError:
     phone=auth.normalize_phone(p.get("mobile",""))
     page=self.pairing_html('<h1>ثبت یک‌باره کد قدیمی</h1><p>این شماره از نسخه قدیمی لایسنس دارد. برای اینکه از دفعه بعد فقط با شماره همان کد نمایش داده شود، یک‌بار کد فعلی را وارد کن. لایسنس عوض نمی‌شود.</p><form action="/connect/recover" method="post"><input name="mobile" value="'+html.escape(phone,quote=True)+'" readonly><label>کد لایسنس قبلی</label><input type="text" name="activation_code" required maxlength="30" placeholder="XXXX-XXXX-XXXX-XXXX-XXXX"><button>ثبت و نمایش کد قبلی</button></form><a href="/connect">بازگشت</a>')
     return self.reply(200,page,ctype="text/html; charset=utf-8")
    if not code:
     return self.bad("registered_license_not_found",409)
    page=self.pairing_html('<h1>کد لایسنس قبلی شما</h1><p>این همان کدی است که قبلاً برای این شماره صادر شده؛ کد جدید ساخته نشده است.</p><strong>'+html.escape(code)+'</strong><p><small>فعلاً شماره موبایل تأیید نمی‌شود. کد را مانند رمز حساب نگهداری کن.</small></p><a href="/connect">بازگشت</a>')
    return self.reply(200,page,ctype="text/html; charset=utf-8")
   except ValueError:
    return self.reply(400,self.pairing_html('<h1>شماره نامعتبر</h1><p>شماره باید ۱۱ رقم و با ۰۹ شروع شود.</p><a href="/connect">بازگشت</a>'),ctype="text/html; charset=utf-8")
   page=self.pairing_html('<h1>کد اتصال آماده است</h1><p>این کد تا زمان لغو دستی معتبر خواهد ماند. آن را در برنامه آونا ویندوز و ورود ChatGPT استفاده کن:</p><strong>'+html.escape(code)+'</strong><p><small>کد را نگه دار؛ اگر شماره را دوباره وارد کنی، همین کد نمایش داده می‌شود.</small></p><a href="/connect">بازگشت</a>')
   return self.reply(201,page,ctype="text/html; charset=utf-8")
  if path=="/connect/recover":
   if not throttle("restore:"+self.ip(),6,3600):
    return self.bad("rate_limit",429)
   p=self.input(form=True)
   if not p:return self.bad("invalid_request")
   try:
    phone=auth.normalize_phone(p.get("mobile",""))
    code=p.get("activation_code","")
    pair=auth.lookup_pair(code)
    if pair is None or pair["phone"]!=phone:
     return self.reply(401,self.pairing_html('<h1>کد صحیح نیست</h1><p>کدی که وارد کردی متعلق به این شماره نیست یا غیرفعال شده است.</p><a href="/connect">بازگشت</a>'),ctype="text/html; charset=utf-8")
    auth.backfill_existing_license_code(code)
    page=self.pairing_html('<h1>کد قبلی بازیابی شد</h1><p>همین کد ذخیره شد؛ از این پس فقط شماره را وارد کن تا نمایش داده شود. هیچ لایسنسی تغییر نکرد.</p><strong>'+html.escape(code)+'</strong><a href="/connect">بازگشت</a>')
    return self.reply(200,page,ctype="text/html; charset=utf-8")
   except ValueError:
    return self.bad("invalid_phone_or_code")
  if path=="/api/device/activate":
   if not throttle("activate:"+self.ip(),12,3600):return self.bad("rate_limit",429)
   p=self.input()
   if not p:return self.bad("invalid_activation")
   token,error=auth.activate_device(p.get("activation_code",""),p.get("device_id",""))
   return self.reply(409 if error in ("already_activated_on_other_device","device_already_has_license") else 401,{"error":error}) if error else self.reply(200,token)
  if path=="/oauth/register":
   if not throttle("reg:"+self.ip(),20,3600):return self.bad("rate_limit",429)
   p=self.input()
   if p is None:return self.bad("invalid_metadata")
   data,error=auth.register(p)
   return self.reply(400,{"error":error}) if error else self.reply(201,data)
  if path=="/oauth/authorize":
   p=self.input(form=True)
   if not p:return self.bad("missing_fields")
   error=auth.validate(p)
   if error:return self.oauth_form(p,"پارامترهای اتصال معتبر نیستند؛ اتصال را دوباره از ChatGPT آغاز کن. ("+error+")")
   pair=auth.lookup_pair(p.get("activation_code",""))
   if pair is None:
    if not throttle("login:"+self.ip()):return self.oauth_form(p,"تلاش‌های ناموفق زیاد است. چند دقیقه دیگر دوباره امتحان کن.")
    return self.oauth_form(p,"کد فعال‌سازی معتبر نیست؛ کد کامل را از صفحه دریافت کد کپی کن.")
   if not pair["device_id"]:
    return self.oauth_form(p,"ابتدا برنامه ویندوز را با همین کد فعال کن؛ این لایسنس هنوز دستگاه متصل ندارد.")
   code=auth.issue_code(p,pair["id"])
   redirect=p["redirect_uri"]+"?"+urlencode({"code":code,"state":p.get("state",""),"iss":auth.ISSUER})
   return self.reply(302,extra={"Location":redirect})
  if path=="/oauth/token":
   p=self.input(form=True)
   if not p:return self.bad("invalid_token_request")
   result,error=auth.exchange(p)
   return self.reply(400,{"error":error}) if error else self.reply(200,result)
  if path=="/mcp":
   pair=auth.pair_from_oauth(self.headers.get("Authorization",""))
   if pair is None:return self.challenge()
   origin=self.headers.get("Origin")
   if origin and origin not in ("https://chatgpt.com","https://chat.openai.com"):return self.bad("invalid_origin",403)
   raw_len=self.headers.get("Content-Length")
   try:
    n=int(raw_len or 0)
    if not 0<n<=262144: return self.bad("invalid_body_size")
    body=self.rfile.read(n)
    request=json.loads(body)
    if not isinstance(request,dict) or request.get("jsonrpc")!="2.0":return self.bad("invalid_jsonrpc")
   except (ValueError,UnicodeError):return self.bad("invalid_json")
   headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream","Authorization":"Bearer "+INTERNAL,"X-Avena-Pair-ID":pair["id"]}
   if self.headers.get("MCP-Protocol-Version"):headers["MCP-Protocol-Version"]=self.headers["MCP-Protocol-Version"]
   try:
    req=urllib.request.Request(BACKEND,body,headers,method="POST")
    with urllib.request.urlopen(req,timeout=70) as response:
     output=response.read(4194304)
     return self.reply(response.status,output,ctype=response.headers.get("Content-Type","application/json"))
   except urllib.error.HTTPError as error:
    return self.reply(error.code,error.read(2048))
   except (TimeoutError,OSError):
    return self.reply(502,{"error":"internal_mcp_gateway_unavailable"})
  return self.reply(404,{"error":"not_found"})
 def do_HEAD(self):return self.do_GET()
def serve():
 auth.init()
 ThreadingHTTPServer(("127.0.0.1",int(os.environ.get("AVENA_OAUTH_PORT","18728"))),Handler).serve_forever()
if __name__=="__main__":serve()
