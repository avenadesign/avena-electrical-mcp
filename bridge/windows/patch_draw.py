"""Apply v0.8.1 additive drawing support to existing Avena Electrical v0.7 source.
Place patch files beside RUN.bat. Source only: no CAD/DWG file mutations here.
"""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parent
app=root/"app"
if not (app/"cloud_agent.py").is_file() or not (app/"gui.py").is_file():
    raise SystemExit("Extract patch next to RUN.bat and then run INSTALL_DRAW.bat")
def edit(name,changes):
    file=app/name
    original=file.read_text(encoding="utf-8")
    source=original
    for old,new in changes:
        if new in source:continue
        if old not in source:raise SystemExit("Unsupported app version: "+name)
        source=source.replace(old,new,1)
    if original!=source:file.write_text(source,encoding="utf-8")
shutil.copy2(root/"approved_draw.py",app/"approved_draw.py")
edit("cloud_agent.py",[
 ("ALLOWED = {'system_status', 'drawing_info', 'layer_list', 'block_list'}",
  "ALLOWED = {'system_status', 'drawing_info', 'layer_list', 'block_list'}\nDRAW_TASK = '__avena_draw_batch__'"),
 ("            if tool not in ALLOWED or args not in ({},None):",
  "            if tool == DRAW_TASK and isinstance(args,dict) and set(args)=={'operations'}:\n                from app.approved_draw import run as approved_run\n                answer = approved_run(args['operations'],local_token)\n            elif tool not in ALLOWED or args not in ({},None):")
])
edit("gui.py",[
 ("        self._licensed = False",
  "        self.draw_enabled = tk.BooleanVar(value=True)\n        self._licensed = False"),
 ('        environment["AVENA_LOCAL_MCP_TOKEN"]=self.token',
  '        environment["AVENA_ALLOWED_PATHS"]=self.allowed.get()\n        environment["AVENA_AUTOCAD_RELEASE"]=self.release.get()\n        environment["AVENA_DRAW_ENABLED"]="1" if self.draw_enabled.get() else "0"\n        environment["AVENA_LOCAL_MCP_TOKEN"]=self.token'),
 ('        self.cloud_status_label=self.text(p3,"اتصال ابری برقرار نیست",10,"muted")',
  '        tk.Checkbutton(p3,text="ترسیم با تأیید جداگانه در ویندوز",variable=self.draw_enabled,\n            bg=COL["panel"],fg=COL["text"],selectcolor=COL["bg"],\n            font=(self.font,10),anchor="e").pack(anchor="e",pady=(8,3))\n        self.cloud_status_label=self.text(p3,"اتصال ابری برقرار نیست",10,"muted")')
])
version=app/"__init__.py"
version.write_text(version.read_text(encoding="utf-8").replace("0.7.0","0.8.1"),encoding="utf-8")
print("AVENA DRAW HOTFIX INSTALLED: restart Avena GUI and cloud agent with RUN.bat.")
