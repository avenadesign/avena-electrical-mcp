from pathlib import Path
import sys,urllib.request
root=Path(sys.argv[1]).resolve()
assert (root/'app/cloud_agent.py').is_file()
base='https://raw.githubusercontent.com/avenadesign/avena-electrical-mcp'
sources={
 'app/analysis_catalog.py':base+'/db28195a45cb8885ea6b3104ac35487c5aa622b7/bridge/shared/analysis_catalog.py',
 'app/drawing_schema_v2.py':base+'/9beaff8e9494b083429fca1d0fc0c19709a752fa/bridge/shared/drawing_schema_v2.py'
}
for path,url in sources.items():
 (root/path).write_bytes(urllib.request.urlopen(url,timeout=25).read())
p=root/'app/drawing_approval.py'
s=p.read_text(encoding='utf-8')
start=s.index('TOOL_BY_TYPE =')
end=s.index('def verify_active_drawing',start)
s=s[:start]+'from app.drawing_schema_v2 import TOOL_BY_TYPE,validate as validate_plan\n\n'+s[end:]
p.write_text(s,encoding='utf-8')
p=root/'app/cloud_agent.py'
s=p.read_text(encoding='utf-8')
old="""    result = response.get('result', {})
    return {'ok':not result.get('isError',False),'content':result.get('content',[]),
            'structuredContent':result.get('structuredContent')}"""
new="""    result = response.get('result', {})
    content=result.get('content',[])
    if tool == 'view_screenshot':
        images=[part for part in content if isinstance(part,dict) and part.get('type')=='image'
                and part.get('mimeType')=='image/png']
        if not images:
            return {'ok':False,'error':'autocad_screenshot_not_available'}
        if sum(len(part.get('data','')) for part in images)>3_400_000:
            return {'ok':False,'error':'autocad_screenshot_too_large','detail':
                    'Zoom into the desired zone in AutoCAD, then retry.'}
    return {'ok':not result.get('isError',False),'content':content,
            'structuredContent':result.get('structuredContent')}"""
assert s.count(old)==1
p.write_text(s.replace(old,new),encoding='utf-8')
p=root/'tests/test_advanced_catalog.py'
s=p.read_text(encoding='utf-8').replace('assert len(READ_TOOLS)>=20','assert len(READ_TOOLS)>=39')
p.write_text(s,encoding='utf-8')
p=root/'README_PRECISION_CAD_FA.txt'
s=p.read_text(encoding='utf-8').replace('20 new allowlisted read-only tools','39 new allowlisted read-only tools')
s+='\n11 strictly checked drawing primitives; local Windows approval required.\n'
p.write_text(s,encoding='utf-8')
for file in root.rglob('*.py'):
 if any(p in ('.build','.venv','__pycache__') for p in file.parts):continue
 compile(file.read_bytes(),str(file),'exec')
print('AVENA_PRECISION_SOURCE_FINALIZED')
