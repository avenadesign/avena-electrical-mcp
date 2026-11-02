"""Strict, deterministic validation for pre-approved edits to existing DWG entities."""
import math,re
TOOLS={"move":"entity_move","text":"entity_edit_text","properties":"entity_set_properties"}
REQ={"move":{"handle","dx","dy"},"text":{"handle","text"},"properties":{"handle","layer"}}
OPT={"move":{"dz"},"text":{"height","rotation"},"properties":{"color"}}
SCHEMA={"type":"array","minItems":1,"maxItems":8,"items":{"type":"object","required":["type","args"],"additionalProperties":False,"properties":{"type":{"type":"string","enum":list(TOOLS)},"args":{"type":"object"}}}}
def validate_edits(operations):
 if not isinstance(operations,list) or not 1<=len(operations)<=8:raise ValueError("Expected 1-8 edit operations")
 clean=[]
 for item in operations:
  if not isinstance(item,dict) or set(item)!={"type","args"}:raise ValueError("Invalid edit")
  kind=item["type"]
  if kind not in TOOLS:raise ValueError("Unsupported edit type")
  args=item["args"]
  if not isinstance(args,dict) or not REQ[kind].issubset(args) or not set(args).issubset(REQ[kind]|OPT[kind]):raise ValueError("Unknown or missing args")
  handle=args["handle"]
  if not isinstance(handle,str) or not re.fullmatch(r"[a-fA-F0-9]{1,16}",handle) or int(handle,16)==0:raise ValueError("Invalid handle")
  for field in ["dx","dy","dz","height","rotation"]:
   if field in args and (type(args[field]) not in (int,float) or not math.isfinite(args[field]) or abs(args[field])>100000):raise ValueError("Invalid numeric")
  if kind=="text":
   v=args["text"]
   if not isinstance(v,str) or not 1<=len(v)<=256 or any(x in v for x in "\n\r\x00") or args.get("height",1)<=0:raise ValueError("Invalid text")
  if kind=="properties":
   if not isinstance(args["layer"],str) or re.fullmatch(r"[\w.$ -]{1,80}",args["layer"]) is None:raise ValueError("Invalid layer")
   if "color" in args and (type(args["color"]) is not int or not 0<=args["color"]<=256):raise ValueError("Invalid color")
  clean.append({"type":kind,"args":dict(args)})
 return clean
def preview(ops):
 ops=validate_edits(ops)
 return {"valid":True,"count":len(ops),"summary":[{"type":x["type"],"handle":x["args"]["handle"]} for x in ops],"note":"Requires separate human approval on Windows; changes unsaved"}
