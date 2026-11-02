"""Native Windows approval and controlled additive AutoCAD drawing actions.

Called from app.cloud_agent after authenticated device polling.
Never save, open, delete or execute arbitrary scripts/commands.
"""
from __future__ import annotations
import json
import os
import sys
import threading
import tkinter as tk

from app.draft_schema import ALLOWED_TYPES, validate

def _ask_local_permission(ops, dwg_info):
    # This code runs in the foreground of the cloud-agent subprocess, not on the
    # remote ChatGPT server. A human must click the actual Windows UI.
    output = {"approved":False}
    app = tk.Tk()
    app.withdraw()
    dialog = tk.Toplevel(app)
    dialog.title("Avena Electrical | DWG Edit Approval")
    dialog.configure(bg="#0e1c2d")
    dialog.geometry("510x405")
    dialog.minsize(450,350)
    dialog.attributes("-topmost",True)
    dialog.protocol("WM_DELETE_WINDOW", lambda: close(False))
    def close(value):
        output["approved"]=bool(value)
        try:app.quit()
        except tk.TclError:pass
    f = tk.Frame(dialog,bg="#0e1c2d",padx=23,pady=20)
    f.pack(fill="both",expand=True)
    title = tk.Label(f,text="تأیید نقشه‌کشی با ChatGPT",font=("Segoe UI",15,"bold"),
                     fg="#eaf7ff",bg="#0e1c2d",anchor="e")
    title.pack(fill="x")
    tk.Label(f,text="عملیات فقط روی نقشه فعال AutoCAD اجرا می‌شوند و به‌طور خودکار ذخیره نمی‌شوند.",
             bg="#0e1c2d",fg="#b8d5e5",wraplength=455,justify="right").pack(fill="x",pady=(13,8))
    summary = f"تعداد عملیات: {len(ops)}\n"
    for i,op in enumerate(ops[:12],1):
        summary += f"{i}. {op['type']}   |   {op['args'].get('layer','Current Layer')}\n"
    if len(ops)>12:summary+=f"... and {len(ops)-12} more\n"
    summary += "\nاطلاعات نقشه فعال:\n" + str(dwg_info)[:320]
    body = tk.Text(f,bg="#192e42",fg="#e7f5fc",insertbackground="#fff",
                   wrap="word",height=13,relief="flat",padx=12,pady=12)
    body.pack(fill="both",expand=True,pady=(3,12))
    body.insert("1.0",summary)
    body.configure(state="disabled")
    buttons = tk.Frame(f,bg="#0e1c2d");buttons.pack(fill="x")
    tk.Button(buttons,text="لغو",command=lambda:close(False),
              bg="#31465d",fg="white",relief="flat",padx=20,pady=9).pack(side="left")
    tk.Button(buttons,text="تأیید ترسیم روی AutoCAD",command=lambda:close(True),
              bg="#27c6b9",fg="#041b20",relief="flat",padx=20,pady=9).pack(side="right")
    # Avoid pending requests being executed when the user is away from the PC.
    app.after(70000, lambda:close(False))
    dialog.lift()
    try:dialog.focus_force()
    except tk.TclError:pass
    app.mainloop()
    app.destroy()
    return output["approved"]

def execute_draft_batch(local_token, incoming_args):
    from app.cloud_agent import local_post, call_local
    if not isinstance(incoming_args,dict) or set(incoming_args)!={"operations"}:
        return {"ok":False,"error":"invalid_draft_arguments"}
    try:
        operations=validate(incoming_args["operations"])
    except ValueError as exc:
        return {"ok":False,"error":"invalid_draft_plan","detail":str(exc)}
    # The plan is approved locally before any create tools are called.
    try:
        drawing=call_local("drawing_info",local_token)
        if not drawing.get("ok"):
            return {"ok":False,"error":"active_drawing_unavailable","detail":drawing}
        init,session=local_post("initialize",{
            "protocolVersion":"2025-06-18","capabilities":{},
            "clientInfo":{"name":"Avena Electrical Draft","version":"0.8"}},local_token)
        if "result" not in init:
            return {"ok":False,"error":"mcp_initialize_failed"}
        local_post("notifications/initialized",{},local_token,session,notification=True)
        tool_listing,session=local_post("tools/list",{},local_token,session)
        if "error" in tool_listing:
            return {"ok":False,"error":"mcp_tools_unavailable","detail":tool_listing["error"]}
        available={x.get("name") for x in tool_listing.get("result",{}).get("tools",[])
                   if isinstance(x,dict)}
        missing=[ALLOWED_TYPES[p["type"]] for p in operations if ALLOWED_TYPES[p["type"]] not in available]
        if missing:return {"ok":False,"error":"local_create_tools_missing","missing":sorted(set(missing))}
        if not _ask_local_permission(operations,drawing.get("content")):
            return {"ok":False,"error":"cancelled_on_windows","created":0}
        results=[]
        for index,op in enumerate(operations,1):
            name=ALLOWED_TYPES[op["type"]]
            try:
                answer,session=local_post("tools/call",
                    {"name":name,"arguments":op["args"]},local_token,session)
            except Exception as exc:
                return {"ok":False,"error":"execution_interrupted","created_or_attempted":index,
                    "completed":len(results),"warning":"Partial DWG changes possible. Inspect DWG before retrying.",
                    "detail":type(exc).__name__}
            if "error" in answer or answer.get("result",{}).get("isError",False):
                return {"ok":False,"error":"local_cad_rejected","completed":len(results),
                    "failed_at":index,"detail":str(answer.get("error",answer.get("result")))[:350],
                    "warning":"Partial DWG edits may exist. Review before trying again."}
            results.append({"index":index,"type":op["type"],"result":answer.get("result",{})})
        return {"ok":True,"created":len(results),"results":results,
            "saved":False,"message":"Added entities to active AutoCAD drawing. Save manually after review."}
    except Exception as exc:
        return {"ok":False,"error":"windows_agent_failure","detail":type(exc).__name__+":"+str(exc)[:160]}
