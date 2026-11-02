"""Outbound Windows bridge: long-poll remote relay, local COM-backed MCP."""
import asyncio,json,os,time,urllib.error,urllib.request
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
BASE=os.getenv("AVENA_GATEWAY_URL","https://elc.avenaai.ir")
LOCAL=os.getenv("AVENA_LOCAL_MCP","http://127.0.0.1:18327/mcp")
AGENT_TOKEN=os.environ["AVENA_AGENT_TOKEN"]
LOCAL_TOKEN=os.environ["AVENA_LOCAL_MCP_TOKEN"]
ALLOW={"system_status","drawing_info","layer_list","block_list"}
def fetch(method,path,body=None):
    data=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request(BASE+path,data=data,method=method,headers={"Authorization":"Bearer "+AGENT_TOKEN,"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=35) as reply:
        return json.loads(reply.read(2097152))
async def local_call(name):
    if name not in ALLOW:return {"ok":False,"error":"denied"}
    transport=StreamableHttpTransport(LOCAL,headers={"Authorization":"Bearer "+LOCAL_TOKEN})
    async with Client(transport) as client:
        result=await client.call_tool(name,{},raise_on_error=False)
        return {"ok":not result.is_error,"content":[getattr(x,"text",str(x)) for x in result.content]}
def main():
    print("[AVENA] Outbound bridge starting. Cloud:",BASE,flush=True)
    while True:
        try:
            item=fetch("GET","/agent/poll")
            if item.get("idle"):continue
            key=item.get("id");name=item.get("tool")
            if not isinstance(key,str):continue
            try:
                if item.get("arguments") not in ({},None):raise ValueError("Arguments denied")
                result=asyncio.run(asyncio.wait_for(local_call(name),timeout=50))
            except Exception as e:
                result={"ok":False,"error":type(e).__name__,"message":str(e)[:250]}
            fetch("POST","/agent/result",{"id":key,"result":result})
        except Exception as e:
            print("[AVENA] Agent offline; retrying:",type(e).__name__,flush=True)
            time.sleep(5)
if __name__=="__main__":main()
