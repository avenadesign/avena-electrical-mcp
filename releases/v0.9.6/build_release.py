"""Build complete Windows source with advanced Avena CAD inspection tools."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import hashlib,sys,urllib.request
base=Path(sys.argv[1])
output=Path(sys.argv[2])
work=Path(sys.argv[3])
with ZipFile(base) as z:
 if z.testzip():raise RuntimeError("Invalid base")
 z.extractall(work)
roots=[x for x in work.iterdir() if x.is_dir()]
if len(roots)!=1:raise RuntimeError("Unexpected base archive")
root=roots[0]
renamed=root.with_name("AvenaElectrical-v0.9.6-Complete-Windows")
root.rename(renamed)
root=renamed
catalog_url="https://raw.githubusercontent.com/avenadesign/avena-electrical-mcp/e203f18f8f9ea28f32dea7650d046a5ff584b8fa/bridge/shared/analysis_catalog.py"
data=urllib.request.urlopen(catalog_url,timeout=30).read().decode("utf-8")
(root/"app/analysis_catalog.py").write_text(data,encoding="utf-8")
agent=root/"app/cloud_agent.py"
s=agent.read_text(encoding="utf-8")
def change(old,new):
 global s
 if s.count(old)!=1:
  raise RuntimeError("Base agent structure changed: "+old[:90])
 s=s.replace(old,new)
change("from __future__ import annotations\n","from __future__ import annotations\nfrom app.analysis_catalog import BY_ENGINE,engine_validated\n")
change("def local_post(method, params, token, session=None, notification=False):",
       "def local_post(method, params, token, session=None, notification=False, timeout=18):")
change("with opener.open(req, timeout=18) as r:","with opener.open(req, timeout=timeout) as r:")
change("return json.loads(r.read(4_194_304)),session","return json.loads(r.read(7_864_320)),session")
change("""def call_local(tool, token):
    if tool not in ALLOWED:
        return {'ok':False,'error':'tool_not_permitted'}""",
"""def call_local(tool, token, arguments=None):
    if tool in ALLOWED:
        if arguments not in ({},None):
            return {'ok':False,'error':'unexpected_arguments'}
        safe_args={}
    elif tool in BY_ENGINE:
        try:
            safe_args=engine_validated(tool,arguments or {})
        except ValueError as exc:
            return {'ok':False,'error':'invalid_read_arguments','detail':str(exc)[:120]}
    else:
        return {'ok':False,'error':'tool_not_permitted'}""")
change("response, _ = local_post('tools/call',{'name':tool,'arguments':{}},token,session)",
"""slow = tool in BY_ENGINE and BY_ENGINE[tool][1]['slow']
    response, _ = local_post('tools/call',{'name':tool,'arguments':safe_args},token,session,
                             timeout=66 if slow else 35)""")
change("""            elif tool not in ALLOWED or args not in ({},None):
                answer = {'ok':False,'error':'tool_not_permitted'}
            else:
                try:
                    answer = call_local(tool,local_token)""",
"""            elif tool not in ALLOWED and tool not in BY_ENGINE:
                answer = {'ok':False,'error':'tool_not_permitted'}
            elif tool in ALLOWED and args not in ({},None):
                answer = {'ok':False,'error':'unexpected_arguments'}
            else:
                try:
                    answer = call_local(tool,local_token,args or {})""")
agent.write_text(s,encoding="utf-8")
version=root/"app/__init__.py"
x=version.read_text(encoding="utf-8")
if '__version__ = "0.9.5"' not in x:raise RuntimeError("Version mismatch")
version.write_text(x.replace('__version__ = "0.9.5"','__version__ = "0.9.6"'),encoding="utf-8")
(root/"README_PRECISION_CAD_FA.txt").write_text("""Avena Electrical 0.9.6 - Precision CAD Tools
20 new allowlisted read-only tools are delivered via ChatGPT MCP.
Entity search/list/get by handle, selection window and polygon, selection filter,
layer/object stats, geometry bounds, exact entity distance and area, room
detection, 2D electrical/network topology, evidence-based drawing inference,
block refs and attributes, capabilities, and a screenshot of AutoCAD window.
The entire list appears AFTER updating the Windows agent and reconnecting
the ChatGPT custom MCP connector to https://elc.avenaai.ir/mcp.
Protected drawing and entity edits remain enabled only after Windows approval.
Never use a layout from an unrelated PDF; inspect the active CAD document.
Units must be verified; autocad_room_candidates upstream assumes millimetres.
Room detection skips unsupported arcs/proxies and reports uncertainties.
No arbitrary LISP, shell commands, file writing, deletes or automatic saves.
Recommended: Save As a DWG copy inside the configured allowed folder.
With unreliable COM calls: leave AutoCAD idle and retry; no blind drawing.
Run: TEST_LAUNCHER_TWICE.bat, then RUN.bat. EXE: BUILD_EXE.bat.
""",encoding="utf-8")
(root/"tests/test_advanced_catalog.py").write_text('''"""Pure offline validation of exposed CAD inspection tools."""
from app.analysis_catalog import READ_TOOLS,BY_ENGINE,validate_args,engine_validated
import pytest
def test_safe_catalog():
    assert len(READ_TOOLS)>=20
    for name,record in READ_TOOLS.items():
        assert record["engine"] in BY_ENGINE
        assert record["schema"]["additionalProperties"] is False
        assert not any(word in name for word in ("delete","save","lisp","run_command","open_file"))
def test_pagination_and_limits():
    assert validate_args("autocad_entity_list",{"limit":40,"offset":80})["compact"] is True
    with pytest.raises(ValueError):
        validate_args("autocad_entity_list",{"limit":9999})
    with pytest.raises(ValueError):
        validate_args("autocad_entity_list",{"path":"C:/sensitive.dwg"})
def test_geometry_validation():
    assert validate_args("autocad_distance",{"x1":0,"y1":0,"x2":200,"y2":30})["x2"]==200
    with pytest.raises(ValueError):
        validate_args("autocad_distance",{"x1":0,"y1":0,"x2":float("nan"),"y2":3})
    with pytest.raises(ValueError):
        validate_args("autocad_entity_get",{"handle":"0","command":"_erase"})
    with pytest.raises(ValueError):
        validate_args("autocad_selection_polygon",{"points":[[0,0],[1,1]]})
def test_engine_pairing():
    upstream="entity_list"
    assert engine_validated(upstream,{"limit":40,"offset":0,"compact":True})["compact"] is True
    with pytest.raises(ValueError):
        engine_validated("system_run_lisp",{})
def test_agent_enforces_catalog():
    from pathlib import Path
    text=(Path(__file__).resolve().parents[1]/"app/cloud_agent.py").read_text(encoding="utf-8")
    assert "engine_validated(tool,arguments or {})" in text
    assert "if tool in BY_ENGINE" in text
''',encoding="utf-8")
for p in root.rglob("*.py"):
 if any(x in p.parts for x in (".venv","__pycache__",".build")):continue
 compile(p.read_bytes(),str(p),"exec")
skip={".build",".venv","__pycache__",".pytest_cache","dist",".git"}
with ZipFile(output,"w",ZIP_DEFLATED,compresslevel=8) as z:
 for p in root.rglob("*"):
  if p.is_file() and not any(t in skip for t in p.relative_to(root).parts) and p.suffix not in (".pyc",".pyo"):
   z.write(p,root.name+"/"+str(p.relative_to(root)))
with ZipFile(output) as z:
 assert z.testzip() is None
 print("FILES",len(z.namelist()),"BYTES",output.stat().st_size,"SHA256",hashlib.sha256(output.read_bytes()).hexdigest())
