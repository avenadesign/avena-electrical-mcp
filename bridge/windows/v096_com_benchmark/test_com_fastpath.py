import unittest
from unittest.mock import Mock
from com_fastpath import count_collection, native_layer_handles, ProbeError

class FallbackCountTest(unittest.TestCase):
    def test_typed_collection_count(self):
        self.assertEqual(count_collection(type("Typed",(),{"Count":7})()),7)

    def test_unknown_count_uses_late_dispatch_once(self):
        class Opaque:
            _oleobj_=object()
            @property
            def Count(self):raise AttributeError("<unknown>.Count")
        late=type("Concrete",(),{"Count":5})()
        spy=Mock(return_value=late)
        self.assertEqual(count_collection(Opaque(),redispatch=spy),5)
        spy.assert_called_once()

    def test_real_com_error_is_not_silenced(self):
        class Error:
            @property
            def Count(self):raise RuntimeError("RPC_E_CALL_REJECTED")
        with self.assertRaisesRegex(RuntimeError,"RPC_E_CALL_REJECTED"):
            count_collection(Error(),redispatch=Mock())

class NativeSelectionTest(unittest.TestCase):
    def fake_document(self,entities,raise_on_item=False):
        class Selection:
            def __init__(self):
                self.deleted=False
                self.Count=len(entities)
                self.selected=[]
            def Select(self,mode,point1,point2,filter_type,filter_data):
                self.selected.append((mode,filter_type,filter_data))
            def Item(self,index):
                if raise_on_item:raise RuntimeError("COM error")
                return type("E",(),{"Handle":entities[index]})()
            def Delete(self):self.deleted=True
        selected=Selection()
        class Sets:
            def Add(self,name):return selected
        doc=type("Doc",(),{"SelectionSets":Sets(),"GetVariable":lambda self,n:0})()
        return doc,selected

    def test_native_filter_uses_dxf_layer_and_cleans_up(self):
        doc,ss=self.fake_document(["ABC","DEF","GHI"])
        got=native_layer_handles(doc,"Aisle",max_items=2,offset=1,selection_factory=lambda col,name:col.Add(name),
            variant_factory=lambda vt,v:v)
        self.assertEqual(got["handles"],["DEF","GHI"])
        self.assertEqual(got["total"],3)
        self.assertEqual(ss.selected[0][0],5)
        self.assertEqual(ss.selected[0][1],[8])
        self.assertEqual(ss.selected[0][2],["Aisle"])
        self.assertTrue(ss.deleted)

    def test_failure_removes_transient_selection(self):
        doc,ss=self.fake_document(["ABC"],raise_on_item=True)
        with self.assertRaisesRegex(RuntimeError,"COM error"):
            native_layer_handles(doc,"Aisle",selection_factory=lambda col,name:col.Add(name),
              variant_factory=lambda vt,v:v)
        self.assertTrue(ss.deleted)

    def test_bad_layer_never_creates_selection(self):
        doc,ss=self.fake_document(["ABC"])
        with self.assertRaises(ProbeError):
            native_layer_handles(doc,"Aisle;ERASE",selection_factory=lambda col,name:col.Add(name),
              variant_factory=lambda vt,v:v)
        self.assertFalse(ss.deleted)

    def test_modal_command_fails_closed(self):
        doc,ss=self.fake_document(["ABC"])
        doc.GetVariable=lambda name:1
        with self.assertRaises(ProbeError):
            native_layer_handles(doc,"Aisle",selection_factory=lambda col,name:col.Add(name),
              variant_factory=lambda vt,v:v)
        self.assertFalse(ss.deleted)

if __name__=="__main__":unittest.main(verbosity=2)
