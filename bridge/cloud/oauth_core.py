"""Avena Electrical OAuth 2.1 core, DCR and S256 PKCE; no third party dependencies."""
import base64,hashlib,hmac,json,os,re,secrets,sqlite3,time
from urllib.parse import urlsplit
BASE=os.environ.get("AVENA_PUBLIC_BASE","https://elc.avenaai.ir").rstrip("/")
RESOURCE=BASE+"/mcp"; ISSUER=BASE
DB=os.environ.get("AVENA_OAUTH_DB","/opt/avena-elc/state/oauth.sqlite")
PASS_HASH=os.environ["AVENA_OAUTH_LOGIN_HASH"]
SCOPES={"cad:read","offline_access"}
def sha(t):return hashlib.sha256(t.encode()).hexdigest()
def connect():
 c=sqlite3.connect(DB,timeout=10);c.row_factory=sqlite3.Row;return c
def init():
 with connect() as c:
  c.executescript("""
  CREATE TABLE IF NOT EXISTS clients(id TEXT PRIMARY KEY, redirects TEXT, created INTEGER);
  CREATE TABLE IF NOT EXISTS codes(codehash TEXT PRIMARY KEY, client TEXT, redirect TEXT, challenge TEXT, scopes TEXT, resource TEXT, expire INTEGER);
  CREATE TABLE IF NOT EXISTS tokens(hash TEXT PRIMARY KEY, client TEXT, kind TEXT, scopes TEXT, resource TEXT, expire INTEGER);
  """)
  now=int(time.time())
  c.execute("DELETE FROM codes WHERE expire < ?",(now,))
  c.execute("DELETE FROM tokens WHERE expire < ?",(now,))
def valid_pass(password):
 try:
  salt,expected=PASS_HASH.split("$",1)
  found=hashlib.pbkdf2_hmac("sha256",password.encode(),bytes.fromhex(salt),350000).hex()
  return hmac.compare_digest(found,expected)
 except (ValueError,TypeError):return False
def valid_redirect(uri):
 try:
  p=urlsplit(uri)
  return p.scheme=="https" and p.hostname in ("chatgpt.com","chat.openai.com") and p.port in (None,443) and not(p.username or p.password or p.query or p.fragment) and (p.path=="/connector_platform_oauth_redirect" or p.path.startswith("/connector/oauth/"))
 except ValueError:return False
def register(data):
 redirects=data.get("redirect_uris")
 if not isinstance(redirects,list) or not 1<=len(redirects)<=4 or not all(isinstance(r,str) and valid_redirect(r) for r in redirects):
  return None,"invalid_redirect_uri"
 if data.get("token_endpoint_auth_method","none")!="none":return None,"invalid_client_metadata"
 client="avena-"+secrets.token_urlsafe(24)
 with connect() as c:c.execute("INSERT INTO clients VALUES (?,?,?)",(client,json.dumps(redirects),int(time.time())))
 return {"client_id":client,"client_id_issued_at":int(time.time()),"redirect_uris":redirects,"token_endpoint_auth_method":"none","grant_types":["authorization_code","refresh_token"],"response_types":["code"]},None
def validate(p):
 with connect() as c: row=c.execute("SELECT redirects FROM clients WHERE id=?",(p.get("client_id",""),)).fetchone()
 if not row or p.get("redirect_uri") not in json.loads(row["redirects"]):return "invalid_client_or_redirect"
 if p.get("response_type")!="code" or p.get("code_challenge_method")!="S256":return "PKCE_S256_required"
 if not re.fullmatch(r"[A-Za-z0-9_-]{43,128}",p.get("code_challenge","")):return "invalid_challenge"
 if p.get("resource",RESOURCE)!=RESOURCE:return "invalid_audience"
 requested=set(p.get("scope","cad:read").split())
 if not requested or "cad:read" not in requested or not requested.issubset(SCOPES):return "invalid_scope"
 if len(p.get("state",""))>1500:return "invalid_state"
 return None
def issue_code(p):
 token=secrets.token_urlsafe(42)
 with connect() as c:c.execute("INSERT INTO codes VALUES (?,?,?,?,?,?,?)",(sha(token),p["client_id"],p["redirect_uri"],p["code_challenge"]," ".join(sorted(set(p.get("scope","cad:read").split()))),RESOURCE,int(time.time())+90))
 return token
def issue_token(client,kind,scope,resource,expires):
 token=secrets.token_urlsafe(48)
 with connect() as c:c.execute("INSERT INTO tokens VALUES (?,?,?,?,?,?)",(sha(token),client,kind,scope,resource,int(time.time())+expires))
 return token
def exchange(p):
 kind=p.get("grant_type");client=p.get("client_id","");now=int(time.time())
 if kind=="authorization_code":
  verifier=p.get("code_verifier","")
  if not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}",verifier):return None,"invalid_grant"
  key=sha(p.get("code",""))
  with connect() as c:
   row=c.execute("SELECT * FROM codes WHERE codehash=?",(key,)).fetchone()
   c.execute("DELETE FROM codes WHERE codehash=?",(key,))
  if not row or row["client"]!=client or row["redirect"]!=p.get("redirect_uri") or row["expire"]<now or p.get("resource",RESOURCE)!=row["resource"]:return None,"invalid_grant"
  challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
  if not hmac.compare_digest(challenge,row["challenge"]):return None,"invalid_grant"
 elif kind=="refresh_token":
  key=sha(p.get("refresh_token",""))
  with connect() as c:
   row=c.execute("SELECT * FROM tokens WHERE hash=? AND kind='refresh' AND expire>?",(key,now)).fetchone()
   if row and row["client"]==client and p.get("resource",RESOURCE)==row["resource"]:
    c.execute("DELETE FROM tokens WHERE hash=?",(key,))
   else:row=None
  if not row:return None,"invalid_grant"
 else:return None,"unsupported_grant_type"
 scope=row["scopes"];resource=row["resource"]
 return {"access_token":issue_token(client,"access",scope,resource,3600),"token_type":"Bearer","expires_in":3600,"refresh_token":issue_token(client,"refresh",scope,resource,30*86400),"scope":scope},None
def verify(auth):
 if not auth.startswith("Bearer ") or len(auth)>170:return False
 with connect() as c:row=c.execute("SELECT * FROM tokens WHERE hash=? AND kind='access' AND expire>?",(sha(auth[7:]),int(time.time()))).fetchone()
 return bool(row and row["resource"]==RESOURCE and "cad:read" in row["scopes"].split())
