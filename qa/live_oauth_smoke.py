"""Live OAuth connector smoke test with isolated temporary pairing; no secret output."""
import base64,hashlib,html,json,re,secrets,sqlite3,sys,urllib.error,urllib.parse,urllib.request
BASE="https://elc.avenaai.ir"
DB="/opt/avena-elc/state/oauth.sqlite"
pair_id=None
def req(path,data=None,ctype="application/json",headers=None):
    raw=None if data is None else urllib.parse.urlencode(data).encode() if ctype=="application/x-www-form-urlencoded" else json.dumps(data).encode()
    r=urllib.request.Request(BASE+path,data=raw,headers={"Content-Type":ctype,**(headers or {})},method="POST" if raw is not None else "GET")
    opener=urllib.request.build_opener(type("NoRedirect",(urllib.request.HTTPRedirectHandler,),{"redirect_request":lambda self,*args:None})())
    try:
        with opener.open(r,timeout=15) as x:return x.status,dict(x.headers),x.read(400000)
    except urllib.error.HTTPError as e:return e.code,dict(e.headers),e.read(400000)
try:
    status,_,page=req("/connect",{"mobile":"09120000000"},"application/x-www-form-urlencoded")
    assert status==201,(status,page[:200])
    code=re.search(rb"[A-HJ-NP-Z2-9]{4}(?:-[A-HJ-NP-Z2-9]{4}){4}",page)
    assert code is not None,"code missing from /connect HTML"
    code=code.group().decode()
    with sqlite3.connect(DB) as db:
        pair_id=db.execute("SELECT id FROM pairings WHERE code_hash=?",(hashlib.sha256(code.replace("-","").encode()).hexdigest(),)).fetchone()[0]
    status,_,body=req("/oauth/register",{"redirect_uris":["https://chatgpt.com/connector_platform_oauth_redirect"],"token_endpoint_auth_method":"none"})
    assert status==201,(status,body[:200])
    cid=json.loads(body)["client_id"]
    verifier=secrets.token_urlsafe(48)
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    params={"client_id":cid,"response_type":"code","redirect_uri":"https://chatgpt.com/connector_platform_oauth_redirect",
            "scope":"cad:read offline_access","resource":BASE+"/mcp",
            "code_challenge":challenge,"code_challenge_method":"S256","state":"avena-smoke-test"}
    status,_,page=req("/oauth/authorize?"+urllib.parse.urlencode(params))
    assert status==200,(status,page[:200])
    assert b'activation_code' in page
    status,h,_=req("/oauth/authorize",{**params,"activation_code":code},"application/x-www-form-urlencoded")
    assert status==302,(status,h)
    location=h["Location"]
    q=urllib.parse.parse_qs(urllib.parse.urlsplit(location).query)
    assert q["iss"]==[BASE] and q["state"]==["avena-smoke-test"]
    status,_,body=req("/oauth/token",{"grant_type":"authorization_code","client_id":cid,"redirect_uri":params["redirect_uri"],"code":q["code"][0],"code_verifier":verifier,"resource":BASE+"/mcp"},"application/x-www-form-urlencoded")
    assert status==200,(status,body[:200])
    result=json.loads(body);token=result["access_token"]
    status,_,body=req("/mcp",{"jsonrpc":"2.0","method":"initialize","id":101,"params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"AvenaQA","version":"0.1"}}},headers={"Authorization":"Bearer "+token})
    assert status==200 and "result" in json.loads(body),(status,body[:200])
    status,_,body=req("/mcp",{"jsonrpc":"2.0","method":"tools/list","id":102,"params":{}},headers={"Authorization":"Bearer "+token})
    assert status==200 and "result" in json.loads(body),(status,body[:200])
    names=[x["name"] for x in json.loads(body)["result"]["tools"]]
    assert "workstation_status" in names and "autocad_drawing_apply" in names and "autocad_drawing_preview" in names
    status,_,body=req("/mcp",{"jsonrpc":"2.0","method":"tools/call","id":103,"params":{"name":"workstation_status","arguments":{}}},headers={"Authorization":"Bearer "+token})
    assert status==200 and "result" in json.loads(body)
    station=json.loads(json.loads(body)["result"]["content"][0]["text"])
    print("PASS discovery+registration+authorize_302+token_200+initialize+tools_list+workstation_status")
    print("LISTED_TOOLS",len(names),"WINDOWS_AGENT_ONLINE",station.get("online"))
    status,_,body=req("/oauth/token",{"grant_type":"refresh_token","client_id":cid,"refresh_token":result["refresh_token"],"resource":BASE+"/mcp"},"application/x-www-form-urlencoded")
    assert status==200,(status,body[:200])
    print("PASS refresh_token")
finally:
    if pair_id:
        with sqlite3.connect(DB) as db:
            db.execute("DELETE FROM codes WHERE pair_id=?",(pair_id,))
            db.execute("DELETE FROM tokens WHERE pair_id=?",(pair_id,))
            db.execute("DELETE FROM pairings WHERE id=?",(pair_id,))
    print("TEMP_PAIRING_CLEANED")
