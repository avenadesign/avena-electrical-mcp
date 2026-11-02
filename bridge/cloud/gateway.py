"""Avena Electrical remote MCP relay: read-only AutoCAD tools over an outbound Windows agent."""
import asyncio
import hmac
import os
import secrets
from fastmcp import FastMCP
from fastmcp.server.auth import StaticTokenVerifier
from starlette.applications import Starlette
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.responses import JSONResponse
from starlette.websockets import WebSocket, WebSocketDisconnect

CLIENT_TOKEN=os.environ["AVENA_MCP_CLIENT_TOKEN"]
AGENT_TOKEN=os.environ["AVENA_AGENT_TOKEN"]
if min(len(CLIENT_TOKEN),len(AGENT_TOKEN))<40 or CLIENT_TOKEN==AGENT_TOKEN:
    raise RuntimeError("Independent long tokens required")
mcp=FastMCP("Avena Electrical MCP",auth=StaticTokenVerifier(tokens={CLIENT_TOKEN:{"client_id":"avena-private","scopes":["mcp:read"]}}))

class Relay:
    def __init__(self):
        self.socket=None
        self.pending={}
        self.lock=asyncio.Lock()
    async def ask(self,tool,args=None):
        if self.socket is None: return {"ok":False,"error":"windows_agent_offline"}
        key=secrets.token_hex(16)
        task=asyncio.get_running_loop().create_future()
        self.pending[key]=task
        try:
            async with self.lock:
                await self.socket.send_json({"id":key,"tool":tool,"arguments":args or {}})
            return await asyncio.wait_for(task,timeout=75)
        except (asyncio.TimeoutError,RuntimeError,WebSocketDisconnect):
            return {"ok":False,"error":"agent_unresponsive"}
        finally:
            self.pending.pop(key,None)
relay=Relay()
async def workstation_agent(ws:WebSocket):
    if not hmac.compare_digest(ws.headers.get("authorization",""),"Bearer "+AGENT_TOKEN):
        await ws.close(code=1008)
        return
    if relay.socket is not None:
        await ws.close(code=1008)
        return
    await ws.accept()
    relay.socket=ws
    try:
        while True:
            data=await ws.receive_json()
            f=relay.pending.get(data.get("id"))
            if f is not None and not f.done():
                f.set_result(data.get("result",{"ok":False,"error":"invalid_response"}))
    except WebSocketDisconnect:
        pass
    finally:
        if relay.socket is ws: relay.socket=None
        for f in list(relay.pending.values()):
            if not f.done(): f.set_result({"ok":False,"error":"agent_disconnected"})
async def health(request):
    return JSONResponse({"ok":True,"agent_online":relay.socket is not None})
@mcp.tool(annotations={"readOnlyHint":True})
async def workstation_status()->dict:
    """Check if the paired Windows workstation is connected."""
    return {"online":relay.socket is not None}
@mcp.tool(annotations={"readOnlyHint":True})
async def autocad_system_status()->dict:
    """Read local AutoCAD MCP status without editing."""
    return await relay.ask("system_status")
@mcp.tool(annotations={"readOnlyHint":True})
async def autocad_drawing_info()->dict:
    """Read the active DWG drawing metadata."""
    return await relay.ask("drawing_info")
@mcp.tool(annotations={"readOnlyHint":True})
async def autocad_list_layers()->dict:
    """List layers of active CAD drawing."""
    return await relay.ask("layer_list")
@mcp.tool(annotations={"readOnlyHint":True})
async def autocad_list_blocks()->dict:
    """List block definitions of active CAD drawing."""
    return await relay.ask("block_list")

mcp_app=mcp.http_app(path="/mcp")
app=Starlette(routes=[Route("/health",health),WebSocketRoute("/agent",workstation_agent),Mount("/",app=mcp_app)],lifespan=mcp_app.lifespan)
