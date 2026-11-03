"""Avena CAD geometry creation contract. Identical on desktop and remote relay."""
from __future__ import annotations
import math
import re

TOOL_BY_TYPE = {
    'line':'entity_create_line', 'rectangle':'entity_create_rectangle',
    'polyline':'entity_create_polyline','circle':'entity_create_circle',
    'text':'entity_create_text','block_ref':'entity_create_block_ref',
    'arc':'entity_create_arc','mtext':'entity_create_mtext',
    'point':'entity_create_point','ellipse':'entity_create_ellipse',
    'spline':'entity_create_spline',
}
FIELDS = {
    'line':({'x1','y1','x2','y2'},set()),
    'rectangle':({'x1','y1','x2','y2'},set()),
    'polyline':({'points'},{'closed'}),
    'circle':({'cx','cy','radius'},set()),
    'arc':({'cx','cy','radius','start_angle','end_angle'},set()),
    'text':({'x','y','text'},{'height','rotation'}),
    'mtext':({'x','y','text'},{'width','height','rotation'}),
    'block_ref':({'x','y','name'},{'scale_x','scale_y','rotation'}),
    'point':({'x','y'},set()),
    'ellipse':({'cx','cy','major_x','major_y','ratio'},set()),
    'spline':({'fit_points'},set()),
}
SCHEMA={
  'type':'array','minItems':1,'maxItems':25,
  'items':{'type':'object','required':['type','args'],'additionalProperties':False,
           'properties':{
             'type':{'type':'string','enum':list(TOOL_BY_TYPE)},
             'args':{'type':'object','description':'Strictly validated geometry arguments; coordinates in active DWG WCS units'}
           }}
}
_NUMERIC={'x','y','x1','y1','x2','y2','cx','cy','radius','start_angle','end_angle','width','height','rotation','scale_x','scale_y','major_x','major_y','ratio'}

def _number(n):
    return type(n) in (float,int) and math.isfinite(n) and abs(n)<=1000000

def _points(raw,minimum):
    if not isinstance(raw,list) or not minimum<=len(raw)<=100:
        return False
    return all(isinstance(p,list) and len(p)==2 and all(_number(n) for n in p) for p in raw)

def validate(operations):
    if not isinstance(operations,list) or not 1<=len(operations)<=25:
        raise ValueError('Expected 1-25 additive operations')
    cleaned=[]
    for i,op in enumerate(operations,1):
        if not isinstance(op,dict) or set(op)!={'type','args'}:
            raise ValueError(f'Operation {i}: type and args are required')
        kind=op['type']
        if kind not in TOOL_BY_TYPE:
            raise ValueError(f'Operation {i}: unapproved geometry type')
        args=op['args']
        required,optional=FIELDS[kind]
        if not isinstance(args,dict) or not required<=set(args) or not set(args)<=required|optional|{'layer','color'}:
            raise ValueError(f'Operation {i}: unknown or missing fields')
        for k,v in args.items():
            if k in _NUMERIC:
                if not _number(v):raise ValueError(f'Operation {i}: invalid {k}')
            elif k in ('points','fit_points'):
                if not _points(v,2 if k=='points' else 3):raise ValueError(f'Operation {i}: invalid {k}')
            elif k=='closed':
                if type(v)!=bool:raise ValueError(f'Operation {i}: closed must be bool')
            elif k=='color':
                if type(v)!=int or not 0<=v<=256:raise ValueError(f'Operation {i}: invalid ACI color')
            elif k=='layer':
                if not isinstance(v,str) or not re.fullmatch(r'[\w.$ -]{1,80}',v):raise ValueError(f'Operation {i}: invalid layer')
            elif k in ('text','name'):
                if not isinstance(v,str) or not 1<=len(v)<=(256 if k=='text' else 80) or any(ord(c)<32 for c in v):
                    raise ValueError(f'Operation {i}: invalid string')
                if k=='name' and v.startswith('*'):raise ValueError(f'Operation {i}: layout block forbidden')
        for positive in ('radius','height','width','scale_x','scale_y','ratio'):
            if positive in args and args[positive]<=0:raise ValueError(f'Operation {i}: {positive} must be positive')
        if kind=='ellipse':
            if args['ratio']>1 or args['major_x']==args['major_y']==0:
                raise ValueError(f'Operation {i}: invalid ellipse axes')
        if kind in ('rectangle','line') and args['x1']==args['x2'] and args['y1']==args['y2']:
            raise ValueError(f'Operation {i}: degenerate geometry')
        cleaned.append({'type':kind,'args':dict(args)})
    return cleaned

def preview(operations):
    plan=validate(operations)
    return {'valid':True,'operations':len(plan),
            'drawing_units':'active AutoCAD WCS drawing units: verify actual INSUNITS and scale',
            'summary':[{'number':i+1,'type':op['type'],'layer':op['args'].get('layer','current')} for i,op in enumerate(plan)],
            'warning':'No geometry is added in preview. Applying changes requires explicit on-screen approval in Windows; no auto-save.',
            'next_step':'Use autocad_drawing_apply after validating positions and scale.'}
