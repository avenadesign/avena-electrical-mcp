"""Explicit safe read-only AutoCAD tool catalog for Avena Electrical MCP bridge.

The engine has 250+ tools, many mutating. Only operations in this module
are remotely callable without local Windows human approval. No raw commands,
scripts, file-path arguments, arbitrary method dispatch, or auto-save.
"""
from __future__ import annotations
import math
import re

def number(description="CAD coordinate or length", minimum=-10000000, maximum=10000000):
    return {"type":"number","minimum":minimum,"maximum":maximum,"description":description}
def integer(description="",minimum=0,maximum=100000):
    return {"type":"integer","minimum":minimum,"maximum":maximum,"description":description}
def string(description="",maxlen=80):
    return {"type":"string","minLength":1,"maxLength":maxlen,"description":description}
def boolean(description=""):
    return {"type":"boolean","description":description}
def array(items,minimum=1,maximum=40,description=""):
    return {"type":"array","items":items,"minItems":minimum,"maxItems":maximum,"description":description}
COORD=number()
HANDLE=string("Hex AutoCAD entity handle",20)
LAYER=string("Exact existing layer name",100)
POINT=array(COORD,2,2,"[x,y] in DWG units")
LAYERS=array(LAYER,1,12)
def define(engine,description,props=None,required=(),slow=False,image=False,defaults=None):
    return {"engine":engine,"description":description,
            "schema":{"type":"object","properties":props or {},"required":list(required),"additionalProperties":False},
            "slow":slow,"image":image,"defaults":defaults or {}}

READ_TOOLS={
 "autocad_entity_list":define("entity_list","Browse paginated entity geometry, handles, layers, positions and properties. Continue with next_offset; never infer full coverage from one page.",
  {"type_filter":string("DXF entity type",30),"layer_filter":LAYER,"limit":integer("Number of entities per page",1,80),
   "offset":integer("Number to skip",0,1000000)},defaults={"limit":40,"offset":0,"compact":True}),
 "autocad_entity_get":define("entity_get","Inspect a real entity handle: WCS geometry, type, layer, properties, bounding box and annotations.",{"handle":HANDLE},("handle",)),
 "autocad_entity_measure":define("analysis_measure_entity","Measure a curved/closed entity; report exactness and tolerance.",
   {"handle":HANDLE,"flatten_tolerance":number("Curve flattening tolerance",0.000001,1000)},("handle",)),
 "autocad_entity_stats":define("analysis_entity_stats","Count all entities by type and layer; useful for determining architectural and MEP disciplines."),
 "autocad_layer_stats":define("analysis_layer_stats","Count real entities and geometry types per layer; may be slow on large DWGs.",slow=True),
 "autocad_drawing_bounds":define("analysis_bounding_box","Compute drawing geometry bounds; detect discrepancy with cached extents."),
 "autocad_selection_window":define("selection_window","Get entity handles inside/crossing an exact rectangular window in DWG coordinates.",
   {"x1":COORD,"y1":COORD,"x2":COORD,"y2":COORD,
    "mode":{"type":"string","enum":["window","crossing"]},
    "entity_type":string("DXF type",30),"layer":LAYER},("x1","y1","x2","y2")),
 "autocad_selection_polygon":define("selection_polygon","Select handles inside/crossing an actual polygon rather than its bounding box.",
   {"points":array(POINT,3,30),"mode":{"type":"string","enum":["window","crossing"]},"entity_type":string("DXF type",30),"layer":LAYER},("points",)),
 "autocad_selection_filter":define("selection_filter","Search drawing handles by entity type, layer, colour and linetype.",
   {"entity_type":string("DXF type",30),"layer":LAYER,
    "color":integer("ACI color index",0,256),"linetype":string("Linetype",60)}),
 "autocad_selection_get":define("selection_get","Read geometry of objects already selected inside the AutoCAD viewport."),
 "autocad_block_attributes":define("block_get_attributes","Read block-reference attribute tags and values.",{"handle":HANDLE},("handle",)),
 "autocad_block_references":define("block_find_references","Find places where a block is inserted; engine may cap scanned inserts.",
   {"name":string("Exact block definition name",80)},("name",),defaults={"compact":True}),
 "autocad_distance":define("analysis_measure_distance","Measure WCS distance, vector and angle between two points.",
   {"x1":COORD,"y1":COORD,"x2":COORD,"y2":COORD},("x1","y1","x2","y2")),
 "autocad_area":define("analysis_measure_area","Measure area/perimeter of an explicit polygon in DWG units.",
   {"points":array(POINT,3,60)},("points",)),
 "autocad_drawing_understand":define("drawing_understand","Advanced evidence-based drawing interpretation: inferred units, true extents, text tags, clusters, layers and room candidates. Does not certify design.",slow=True),
 "autocad_room_candidates":define("arch_rooms_detect","Detect closed rooms and corridors from wall layers; reports skipped geometry and confidence. Coordinates interpreted as mm by the upstream algorithm.",
   {"layers":LAYERS,"min_area":number("Minimum area in assumed mm squared",0.01,1e12),
    "tol":number("Endpoint merge tolerance in assumed mm",0.0001,10000)},slow=True),
 "autocad_topology":define("drawing_topology_check","Read-only tracing of electrical/piping networks: dangling segments, near misses and crossings. Provides evidence per finding.",
   {"layers":LAYERS,"gap":number("Near-miss tolerance in drawing units",0.0001,1e6),
    "tol":number("Endpoint tolerance",0.000001,1e5),"limit":integer("Max findings per category",1,250)},slow=True),
 "autocad_drawing_properties":define("drawing_properties_get","Read drawing author/properties and other document metadata."),
 "autocad_system_capabilities":define("system_capabilities","Read active engine capabilities and AutoCAD COM support."),
 "autocad_drawing_settings_read":define("drawing_settings","Read drawing settings and units only. No settings changes are accepted."),
 "autocad_xdata":define("entity_get_xdata","Read application-specific typed XDATA from an existing AutoCAD entity by handle.",
   {"handle":HANDLE,"app_name":string("Registered application name",70)},("handle",)),
 "autocad_system_variable":define("system_get_variable","Read a safe engineering system variable; no system variable changes.",
   {"name":{"type":"string","minLength":3,"maxLength":24,"enum":["INSUNITS","MEASUREMENT","LUNITS","LUPREC","AUNITS","AUPREC","DIMSCALE","DIMLFAC","DIMTXT","LTSCALE","CLAYER","CANNOSCALE","UCSNAME","WORLDUCS","TILEMODE","CVPORT","PSLTSCALE","OSMODE"]}},("name",)),
 "autocad_document_list":define("document_list","List open AutoCAD documents; does not change active drawing."),
 "autocad_dimstyle_list":define("dimstyle_list","Read dimension style names and parameters."),
 "autocad_textstyle_list":define("textstyle_list","Read text styles, fonts and formatting."),
 "autocad_mleaderstyle_list":define("mleaderstyle_list","Read multileader/annotation style definitions."),
 "autocad_page_setup_list":define("page_setup_list","Read page setups for paper-space layouts."),
 "autocad_plot_style_list":define("plot_style_list","Read available plot styles; no plot is initiated."),
 "autocad_viewport_list":define("viewport_list","Read viewport geometry and scales without changing them."),
 "autocad_layer_state_list":define("layer_state_list","Read saved layer visibility and property states."),
 "autocad_named_view_list":define("view_named_list","Read named viewport camera positions."),
 "autocad_ucs_list":define("ucs_list","Read World/User Coordinate System frames for coordinate accuracy."),
 "autocad_template_list":define("drawing_template_list","Read available standard drawing templates without creating files."),
 "autocad_arch_catalogue":define("arch_catalogue_list","Read standard architectural symbols and their nominal dimensions."),
 "autocad_pid_symbol_catalogue":define("pid_symbol_list","Read P&ID engineering symbol catalogue."),
 "autocad_pid_network_graph":define("pid_graph","Analyze P&ID connectivity and equipment graph from current model, read-only, no exports.",slow=True),
 "autocad_pid_line_list":define("pid_line_list","Read P&ID pipe/line network from active drawing; no CSV file generated.",slow=True),
 "autocad_pid_equipment_list":define("pid_equipment_list","Read equipment and tags from P&ID drawing; no CSV file generated.",slow=True),
 "autocad_view_screenshot":define("view_screenshot","Capture current AutoCAD drawing-window PNG for visual inspection; no zoom or drawing changes.",
   image=True,slow=True),
}
# Engine names are unique, and no remote tool accepts a source path or shell command.
assert len({t["engine"] for t in READ_TOOLS.values()})==len(READ_TOOLS)
BY_ENGINE={record["engine"]:(name,record) for name,record in READ_TOOLS.items()}

def validate_args(name,args):
    if name not in READ_TOOLS:raise ValueError("Tool not available")
    spec=READ_TOOLS[name]
    schema=spec["schema"]
    if not isinstance(args,dict):raise ValueError("Expected object arguments")
    if len(str(args))>12000:raise ValueError("Arguments exceed limit")
    if set(args)-set(schema["properties"]):raise ValueError("Unexpected arguments")
    if set(schema["required"])-set(args):raise ValueError("Missing required arguments")
    def check(value,rule,depth=0):
        if depth>4:raise ValueError("Input nesting excessive")
        typ=rule["type"]
        if typ=="number":
            if type(value) not in (float,int) or not math.isfinite(value) or not rule["minimum"]<=value<=rule["maximum"]:
                raise ValueError("Invalid numeric argument")
        elif typ=="integer":
            if type(value)!=int or not rule["minimum"]<=value<=rule["maximum"]:raise ValueError("Invalid integer argument")
        elif typ=="string":
            if not isinstance(value,str) or len(value)<rule.get("minLength",0) or len(value)>rule.get("maxLength",1024) or any(ord(c)<32 for c in value):
                raise ValueError("Invalid string argument")
        elif typ=="boolean":
            if type(value)!=bool:raise ValueError("Invalid boolean argument")
        elif typ=="array":
            if not isinstance(value,list) or not rule["minItems"]<=len(value)<=rule["maxItems"]:raise ValueError("Invalid array length")
            for item in value:check(item,rule["items"],depth+1)
        else:raise ValueError("Unknown field schema")
        if "enum" in rule and value not in rule["enum"]:raise ValueError("Invalid option")
    for key,value in args.items():check(value,schema["properties"][key])
    if name=="autocad_selection_window" and args["x1"]==args["x2"] and args["y1"]==args["y2"]:
        raise ValueError("Zero-area selection window")
    if name=="autocad_topology" and "gap" in args and "tol" in args and args["gap"]<=args["tol"]:
        raise ValueError("Gap threshold must exceed endpoint tolerance")
    normalized=dict(spec["defaults"])
    normalized.update(args)
    return normalized

def engine_validated(engine,args):
    if engine not in BY_ENGINE:raise ValueError("Engine tool forbidden")
    name,record=BY_ENGINE[engine]
    # Internal defaults are allowed only from the server catalog.
    given=dict(args or {})
    for key,value in record["defaults"].items():
        if key in given and given[key]==value:given.pop(key)
    return validate_args(name,given)
