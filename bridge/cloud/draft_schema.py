"""Strict v0.8 drawing plan contract shared by cloud and Windows agents.

Only additive geometry. No open/save/delete/rename or arbitrary AutoCAD commands.
Lengths/angles are in the active drawing's native units.
"""
import math
import re

ALLOWED_TYPES = {
    "line": "entity_create_line",
    "rectangle": "entity_create_rectangle",
    "polyline": "entity_create_polyline",
    "circle": "entity_create_circle",
    "text": "entity_create_text",
    "block_ref": "entity_create_block_ref",
}
NUM_KEYS = {
    "line": ("x1","y1","x2","y2"),
    "rectangle": ("x1","y1","x2","y2"),
    "polyline": (),
    "circle": ("cx","cy","radius"),
    "text": ("x","y"),
    "block_ref": ("x","y"),
}
OPTIONAL_NUM = {
    "text": ("height","rotation"),
    "block_ref": ("scale_x","scale_y","rotation"),
}
OPTIONAL_KEYS = {"layer"}
SCHEMA = {
    "type":"array","minItems":1,"maxItems":25,
    "items":{"type":"object","required":["type","args"],"additionalProperties":False,
      "properties":{
        "type":{"type":"string","enum":list(ALLOWED_TYPES)},
        "args":{"type":"object","description":"Arguments for the selected shape"}
      }
    }
}

def _number(v):
    return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and abs(v)<=1000000

def _valid_string(v,maxlen=128):
    return isinstance(v,str) and 0<len(v)<=maxlen and "\x00" not in v and "\r" not in v and "\n" not in v

def validate(operations):
    if not isinstance(operations,list) or not 1<=len(operations)<=25:
        raise ValueError("Provide between 1 and 25 drawing operations")
    out=[]
    for idx,op in enumerate(operations):
        if not isinstance(op,dict) or set(op)!={"type","args"}:
            raise ValueError(f"Operation {idx+1}: expected type and args only")
        typ=op["type"]
        if typ not in ALLOWED_TYPES:
            raise ValueError(f"Operation {idx+1}: unsupported drawing command")
        args=op["args"]
        if not isinstance(args,dict):
            raise ValueError(f"Operation {idx+1}: args must be an object")
        required=set(NUM_KEYS[typ])
        extra=set(OPTIONAL_NUM.get(typ,()))|OPTIONAL_KEYS
        if typ=="polyline":required|={"points"};extra|={"closed","color"}
        elif typ=="text":required|={"text"};extra|={"color"}
        elif typ=="block_ref":required|={"name"}
        else:extra|={"color"}
        if not required.issubset(args) or not set(args).issubset(required|extra):
            raise ValueError(f"Operation {idx+1}: missing or unknown arguments")
        for k in NUM_KEYS[typ]+OPTIONAL_NUM.get(typ,()):
            if k in args and not _number(args[k]):
                raise ValueError(f"Operation {idx+1}: invalid numeric {k}")
        if typ=="polyline":
            points=args["points"]
            if not isinstance(points,list) or not 2<=len(points)<=100:
                raise ValueError(f"Operation {idx+1}: polyline needs 2..100 points")
            if any(not isinstance(p,list) or len(p)!=2 or not all(_number(c) for c in p) for p in points):
                raise ValueError(f"Operation {idx+1}: invalid polyline coordinates")
            if "closed" in args and not isinstance(args["closed"],bool):
                raise ValueError(f"Operation {idx+1}: closed must be true/false")
        if typ=="circle" and args["radius"]<=0:
            raise ValueError(f"Operation {idx+1}: circle radius must be positive")
        if typ=="text":
            if not _valid_string(args["text"],256):
                raise ValueError(f"Operation {idx+1}: text must be 1..256 chars")
            if "height" in args and args["height"]<=0:
                raise ValueError(f"Operation {idx+1}: text height must be positive")
        if typ=="block_ref":
            if not _valid_string(args["name"],80) or args["name"].startswith("*"):
                raise ValueError(f"Operation {idx+1}: invalid block name")
            if any(args.get(k,1)<=0 for k in ("scale_x","scale_y")):
                raise ValueError(f"Operation {idx+1}: block scale must be positive")
        if "layer" in args and (not _valid_string(args["layer"],80)
            or not re.fullmatch(r"[\w\-.$ ]{1,80}",args["layer"],flags=re.UNICODE)):
            raise ValueError(f"Operation {idx+1}: invalid layer name")
        if "color" in args and (type(args["color"]) is not int or not 0<=args["color"]<=256):
            raise ValueError(f"Operation {idx+1}: invalid AutoCAD color")
        out.append({"type":typ,"args":dict(args)})
    return out

def preview(operations):
    plan=validate(operations)
    return {
        "valid":True,
        "operations":len(plan),
        "drawing_units":"active AutoCAD drawing units (verify before applying)",
        "summary":[{"number":i+1,"type":p["type"],"layer":p["args"].get("layer","current")} for i,p in enumerate(plan)],
        "warning":"This creates unsaved entities in the currently active DWG. It does not automatically save or certify an IEC electrical schematic.",
        "next_step":"Use autocad_drawing_apply with the same operations. The Windows computer will request local human approval."
    }
