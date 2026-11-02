"""Avena Electrical: locally confirmed additive CAD geometry, never delete/save/run commands."""
import math,os,re,tkinter as tk
from pathlib import Path
NAMES={"line":"entity_create_line","rectangle":"entity_create_rectangle","polyline":"entity_create_polyline","circle":"entity_create_circle","text":"entity_create_text","block_ref":"entity_create_block_ref"}
REQUIRED={"line":set("x1 y1 x2 y2".split()),"rectangle":set("x1 y1 x2 y2".split()),"polyline":{"points"},"circle":set("cx cy radius".split()),"text":set("x y text".split()),"block_ref":set("x y name".split())}
OPTIONAL={"line":set("layer color".split()),"rectangle":set("layer color".split()),"polyline":set("layer color closed".split()),"circle":set("layer color".split()),"text":set("layer color height rotation".split()),"block_ref":set("layer scale_x scale_y rotation".split())}
NUM=set("x1 y1 x2 y2 cx cy x y radius height rotation scale_x scale_y".split())
def finite(x):return type(x) in (int,float) and math.isfinite(x) and abs(x)<=1e6
def validate(ops):
    if not isinstance(ops,list) or not 1<=len(ops)<=10:raise ValueError("1-10 drawing operations per approval")
    for i,op in enumerate(ops,1):
        if not isinstance(op,dict) or set(op)!={"type","args"} or op["type"] not in NAMES:raise ValueError("Forbidden CAD operation")
        kind=op["type"];a=op["args"]
        if not isinstance(a,dict) or not REQUIRED[kind].issubset(a) or not set(a).issubset(REQUIRED[kind]|OPTIONAL[kind]):raise ValueError("Unexpected CAD arguments")
        for k,v in a.items():
            if k in NUM and not finite(v):raise ValueError("Invalid number")
            if k=="color" and (type(v) is not int or not 0<=v<=256):raise ValueError("Invalid color")
            if k=="layer" and (not isinstance(v,str) or re.fullmatch(r"[\w.$ -]{1,80}",v) is None):raise ValueError("Invalid layer")
            if k=="points" and (not isinstance(v,list) or not 2<=len(v)<=100 or any(not isinstance(p,list) or len(p)!=2 or not all(finite(n) for n in p) for p in v)):raise ValueError("Invalid points")
            if k=="closed" and type(v) is not bool:raise ValueError("Invalid closed flag")
            if k in ("text","name") and (not isinstance(v,str) or not 1<=len(v)<=(256 if k=="text" else 80) or any(c in v for c in "\n\r\x00")):raise ValueError("Invalid string")
        if kind=="circle" and a["radius"]<=0:raise ValueError("Invalid radius")
        if kind=="text" and a.get("height",2.5)<=0:raise ValueError("Invalid height")
        if kind=="block_ref" and (a["name"].startswith("*") or a.get("scale_x",1)<=0 or a.get("scale_y",1)<=0):raise ValueError("Invalid block")
    return ops
def check_dwg(expected=None):
    from app.com_probe import probe
    release=os.getenv("AVENA_AUTOCAD_RELEASE","");allowed=os.getenv("AVENA_ALLOWED_PATHS","")
    if release not in ("2026","2027") or not allowed:raise RuntimeError("Drawing restrictions missing")
    doc=probe(release)
    if not doc.available or not doc.attached or not doc.document_path:raise RuntimeError("No active AutoCAD DWG/COM")
    root=Path(allowed).resolve(strict=True);drawing=Path(doc.document_path).resolve(strict=True)
    if not drawing.is_file() or drawing.suffix.lower()!=".dwg" or not drawing.is_relative_to(root):raise RuntimeError("DWG outside allowed folder")
    if expected and os.path.normcase(str(drawing))!=os.path.normcase(str(expected)):raise RuntimeError("Active DWG changed")
    return str(drawing)
def approve(dwg,ops):
    if os.name!="nt":return False
    w=tk.Tk();w.title("Avena Electrical — تأیید ترسیم");w.geometry("620x450");w.attributes("-topmost",True)
    result={"yes":False}
    def close(yes=False):result["yes"]=yes;w.destroy()
    try:
        tk.Label(w,text="آیا این ترسیم‌ها روی نقشه اجرا شوند؟",font=("Tahoma",14,"bold")).pack(pady=16)
        tk.Label(w,text=dwg,wraplength=565).pack(pady=5)
        tk.Label(w,text="فقط افزودن هندسه در واحد جاری DWG؛ بدون حذف یا ذخیره خودکار.",wraplength=565).pack(pady=5)
        info=tk.Text(w,height=12);info.pack(fill="both",expand=True,padx=15,pady=10)
        for i,o in enumerate(ops,1):info.insert("end",f'{i}. {o["type"]}  {o["args"]}\n')
        info.configure(state="disabled")
        frame=tk.Frame(w);frame.pack(fill="x",padx=20,pady=13)
        tk.Button(frame,text="رد درخواست",command=lambda:close(False)).pack(side="left")
        tk.Button(frame,text="تأیید ترسیم",command=lambda:close(True)).pack(side="right")
        w.protocol("WM_DELETE_WINDOW",lambda:close(False));w.after(25000,lambda:close(False));w.mainloop()
    finally:
        try:w.destroy()
        except tk.TclError:pass
    return result["yes"]
def run(ops,token):
    from app import cloud_agent as agent
    if os.environ.get("AVENA_DRAW_ENABLED")!="1":return {"ok":False,"error":"drawing_disabled"}
    try:
        plan=validate(ops);dwg=check_dwg()
        if not approve(dwg,plan):return {"ok":False,"error":"denied_or_timeout"}
        check_dwg(dwg)
        init,sid=agent.local_post("initialize",{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"AvenaDraw","version":"0.8.1"}},token)
        if "result" not in init:raise RuntimeError("MCP initialize failed")
        agent.local_post("notifications/initialized",{},token,sid,notification=True)
        count=0
        for i,op in enumerate(plan,1):
            check_dwg(dwg)
            reply,sid=agent.local_post("tools/call",{"name":NAMES[op["type"]],"arguments":op["args"]},token,sid)
            if "result" not in reply or reply.get("error") or reply["result"].get("isError"):
                return {"ok":False,"error":"cad_command_failed","failed_at":i,"created":count,"detail":str(reply)[:400],"saved":False}
            count+=1
        return {"ok":True,"drawing":dwg,"created":count,"saved":False,"note":"Review and manually save in AutoCAD"}
    except Exception as exc:return {"ok":False,"error":"cad_draw_failed","message":str(exc)[:250],"saved":False}
