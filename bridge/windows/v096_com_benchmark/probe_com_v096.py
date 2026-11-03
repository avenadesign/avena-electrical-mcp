"""Manual local Windows COM diagnostics for Avena Electrical v0.9.6.

Runs only on a Windows desktop where AutoCAD is already open.
Does not open a file, save a file, change a layer, or create geometry.
Use --allow-transient-selection ONLY on a disposable DWG copy.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from com_fastpath import count_collection, native_layer_handles, ProbeError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layer", default="Aisle", help="Existing DWG layer to inspect")
    parser.add_argument("--limit", type=int, default=20, help="Max handle count (1..500)")
    parser.add_argument("--allow-transient-selection", action="store_true", 
                        help="On disposable DWG only: create/delete a temporary SelectionSet")
    args = parser.parse_args(argv)
    if sys.platform != "win32":
        print(json.dumps({"ok": False, "error": "Windows_only"}))
        return 2

    # GetActiveObject NEVER starts a new AutoCAD instance. This is deliberate.
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    start=time.perf_counter()
    try:
        app = win32com.client.GetActiveObject("AutoCAD.Application")
        t=time.perf_counter()
        num_docs=count_collection(app.Documents)
        doc_ms=round((time.perf_counter()-t)*1000,1)
        if num_docs<1:
            raise ProbeError("No open AutoCAD DWG")
        doc=app.ActiveDocument
        t=time.perf_counter()
        model_count=count_collection(doc.ModelSpace)
        model_ms=round((time.perf_counter()-t)*1000,1)
        result={"ok": True,"version":"0.9.6","documents_count":num_docs,
                "modelspace_entities":model_count,"document_count_ms":doc_ms,
                "model_count_ms":model_ms,
                "elapsed_ms":round((time.perf_counter()-start)*1000,1),
                "read_only":True,"selected":False,
                "note":"No save/open/close commands are called."}
        if args.allow_transient_selection:
            t=time.perf_counter()
            selected=native_layer_handles(doc,args.layer,max_items=args.limit)
            result.update({"selected":True, "selection_result":selected,
                           "native_layer_selection_ms":round((time.perf_counter()-t)*1000,1),
                           "warning":"This method uses a temporary SelectionSet; inspect on a test DWG."})
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except Exception as exc:
        # No document name, path or credential is logged.
        print(json.dumps({"ok":False,"error_type":type(exc).__name__,
                          "message":str(exc)[:180],"elapsed_ms":round((time.perf_counter()-start)*1000,1)}))
        return 1
    finally:
        pythoncom.CoUninitialize()


if __name__=="__main__":
    raise SystemExit(main())
