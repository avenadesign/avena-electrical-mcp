"""Avena Electrical v0.9.6 experimental COM diagnostic helpers.

Read-only entity collection and opt-in temporary native selection set.
Not activated by the cloud relay and not a replacement for production COM.
"""
from __future__ import annotations

import re
import secrets


class ProbeError(ValueError):
    pass


def count_collection(collection, redispatch=None) -> int:
    """Get a COM collection count, recovering only a narrowed .Count wrapper.

    Real COM faults (e.g. RPC_E_CALL_REJECTED) propagate unchanged: retrying
    an active AutoCAD command in a GUI thread may block indefinitely.
    """
    try:
        return int(collection.Count)
    except AttributeError:
        ole = getattr(collection, "_oleobj_", None)
        if ole is None:
            raise
        if redispatch is None:
            import win32com.client.dynamic
            redispatch = win32com.client.dynamic.Dispatch
        rebound = redispatch(ole)
        return int(rebound.Count)


def native_layer_handles(
    doc,
    layer: str,
    *,
    max_items: int = 20,
    offset: int = 0,
    selection_factory=None,
    variant_factory=None,
) -> dict:
    """Use AutoCAD's native DXF layer selection to retrieve handles.

    Opt-in test-only path. Creates a temporary named selection set and removes
    it in finally. Invoke on a disposable DWG copy, never during an active CAD
    command, and do not assume selection excludes nested block geometry.
    """
    if not isinstance(layer, str) or not re.fullmatch(r"[\w.$ -]{1,80}", layer):
        raise ProbeError("invalid layer name")
    if type(max_items) is not int or not 1 <= max_items <= 500:
        raise ProbeError("max_items out of bounds")
    if type(offset) is not int or not 0 <= offset <= 1_000_000:
        raise ProbeError("offset out of bounds")
    try:
        active = int(doc.GetVariable("CMDACTIVE"))
    except Exception as exc:
        raise ProbeError("cannot verify AutoCAD is idle") from exc
    if active:
        raise ProbeError("AutoCAD has an active command; selection refused")
    if selection_factory is None:
        selection_factory = lambda collection, name: collection.Add(name)
    if variant_factory is None:
        import pythoncom
        import win32com.client
        filter_type = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I2, [8])
        filter_data = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, [layer])
    else:
        filter_type = variant_factory(0, [8])
        filter_data = variant_factory(0, [layer])
    name = "AVENA_QA_" + secrets.token_hex(8).upper()
    selection = None
    try:
        selection = selection_factory(doc.SelectionSets, name)
        # 5 = acSelectionSetAll. DXF group 8 = layer. No CAD command strings.
        selection.Select(5, None, None, filter_type, filter_data)
        total = count_collection(selection)
        stop = min(total, offset + max_items)
        handles = [str(selection.Item(i).Handle) for i in range(offset, stop)]
        return {"total": total, "offset": offset, "handles": handles, "method": "native_selection_set",
                "nested_blocks_included": False, "geometry_modified": False}
    finally:
        if selection is not None:
            selection.Delete()
