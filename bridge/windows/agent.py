"""Read-only outbound connection from Windows AutoCAD MCP to Avena cloud."""
import asyncio,json,os
import websockets
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
REMOTE=os.getenv("AVENA_CLOUD_WS","wss://elc.avenaai.ir/agent")
LOCAL=os.getenv("AVENA_LOCAL_MCP","http://127.0.0.1:18327/mcp")
AGENT_TOKEN=os.environ["AVENA_AGENT_TOKEN"]
LOCAL_TOKEN=os.environ["AVENA_LOCAL_MCP_TOKEN"]
ALLOW={"system_status","drawing_info","layer_list","block_list"}
async def perform(name,args):
    if name not in ALLOW or not isinstance(args,dict): return {"ok":False,"error":"denied"}
    transport=StreamableHttpTransport(LOCAL,headers={"Authorization":"Bearer "+LOCAL_TOKEN})
    async with Client(transport) as client:
        result=await client.call_tool(name,args,raise_on_error=False)
        return {"ok":not result.is_error,"content":[getattr(c,"text",str(c)) for c in result.content]}
async def main():
    while True:
        try:
            async with websockets.connect(REMOTE,additional_headers={"Authorization":"Bearer "+AGENT_TOKEN},ping_interval=20,ping_timeout=20,max_size=2097152) as ws:
                print("[AVENA] Windows connected to elc.avenaai.ir",flush=True)
                async for raw in ws:
                    req=json.loads(raw)
                    key=req.get("id")
                    if not isinstance(key,str):continue
                    try:result=await asyncio.wait_for(perform(req.get("tool"),req.get("arguments") or {}),timeout=60)
                    except Exception as e:result={"ok":False,"error":type(e).__name__,"message":str(e)[:250]}
                    await ws.send(json.dumps({"id":key,"result":result},ensure_ascii=False))
        except Exception as e:
            print("[AVENA] Reconnecting:",type(e).__name__,flush=True)
        await asyncio.sleep(5)
if __name__=="__main__": asyncio.run(main())
