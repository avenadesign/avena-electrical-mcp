import os,sys,sqlite3,hashlib,json,time,threading,tempfile,unittest,urllib.request,urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer
from concurrent.futures import ThreadPoolExecutor

PAIR = 'e' * 32
DEVICE_TOKEN = 'QA_ONLY_AGENT_ACCESS'
MCP_SECRET = 'QA_ONLY_MCP_ACCESS'

class RelayCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir=tempfile.TemporaryDirectory(prefix='avena-superpowers-test-')
        db=Path(cls.dir.name)/'oauth.sqlite'
        with sqlite3.connect(db) as c:
            c.execute('CREATE TABLE pairings (id TEXT PRIMARY KEY, revoked INTEGER NOT NULL,device_token_hash TEXT)')
            c.execute('INSERT INTO pairings VALUES (?,?,?)',(PAIR,0,hashlib.sha256(DEVICE_TOKEN.encode()).hexdigest()))
        os.environ['AVENA_MCP_CLIENT_TOKEN']=MCP_SECRET
        os.environ['AVENA_OAUTH_DB']=str(db)
        import paired_relay
        cls.relay=paired_relay
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),paired_relay.H)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base='http://127.0.0.1:%s'%cls.server.server_port
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.dir.cleanup()
    def setUp(self):
        with self.relay.guard:
            self.relay.waiting.clear()
            self.relay.queues.clear()
            self.relay.last.clear()
            if hasattr(self.relay,'expired'):self.relay.expired.clear()
    def post(self,method,params,timeout=2):
        body=json.dumps({'jsonrpc':'2.0','method':method,'params':params,'id':99}).encode()
        r=urllib.request.Request(self.base+'/mcp',data=body,headers={'Content-Type':'application/json','Authorization':'Bearer '+MCP_SECRET,'X-Avena-Pair-ID':PAIR},method='POST')
        with urllib.request.urlopen(r,timeout=timeout) as resp:return json.load(resp)
    def test_status_remains_online_while_claimed_agent_call_is_running(self):
        now=time.monotonic()
        with self.relay.guard:
            self.relay.last[PAIR]=now-40
            self.relay.waiting['busy']={'pid':PAIR,'event':threading.Event(),'reply':None,'claimed':True,'claimed_at':now-10}
        response=self.post('tools/call',{'name':'workstation_status','arguments':{}})
        actual=json.loads(response['result']['content'][0]['text'])
        self.assertTrue(actual['online'],actual)
    def test_second_request_fails_fast_as_busy_instead_of_waiting_45_seconds(self):
        now=time.monotonic()
        with self.relay.guard:
            self.relay.last[PAIR]=now
            self.relay.waiting['busy']={'pid':PAIR,'event':threading.Event(),'reply':None,'claimed':True,'claimed_at':now}
        started=time.monotonic()
        response=self.post('tools/call',{'name':'autocad_entity_list','arguments':{'limit':5}},timeout=1)
        self.assertLess(time.monotonic()-started,0.8)
        self.assertIn('agent_busy',json.dumps(response))
    def test_wait_period_covers_35sec_local_read_plus_initialize(self):
        self.assertGreaterEqual(self.relay.rpc_wait_seconds('autocad_entity_list'),72)
        self.assertGreaterEqual(self.relay.rpc_wait_seconds('autocad_drawing_understand'),95)
        self.assertLess(self.relay.rpc_wait_seconds('autocad_drawing_understand'),115)
    def test_expired_unclaimed_job_is_never_dispatched_to_windows(self):
        import queue
        with self.relay.guard:
            self.relay.queues[PAIR]=queue.Queue()
            self.relay.queues[PAIR].put_nowait({'id':'expired-job','tool':'entity_create_circle',
                                               'arguments':{'radius':20}})
            self.relay.expired['expired-job']={'pid':PAIR,'expires':time.monotonic()+120}
        req=urllib.request.Request(self.base+'/agent/poll',
            headers={'Authorization':'Bearer '+DEVICE_TOKEN},method='GET')
        with urllib.request.urlopen(req,timeout=2) as response:
            task=json.load(response)
        self.assertTrue(task.get('idle'),task)
        self.assertNotIn('tool',task)

    def test_unknown_agent_does_not_queue_any_work(self):
        started=time.monotonic()
        response=self.post('tools/call',{'name':'autocad_entity_list','arguments':{'limit':5}},timeout=1)
        self.assertLess(time.monotonic()-started,0.8)
        self.assertIn('agent_offline',json.dumps(response))

    def test_read_only_call_round_trip_through_agent_and_validated_arguments(self):
        with self.relay.guard:
            self.relay.last[PAIR]=time.monotonic()
        def model_request():
            return self.post('tools/call',{'name':'autocad_entity_list',
                              'arguments':{'layer_filter':'Aisle','limit':5}},timeout=5)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(model_request)
            req=urllib.request.Request(self.base+'/agent/poll',
                headers={'Authorization':'Bearer '+DEVICE_TOKEN},method='GET')
            with urllib.request.urlopen(req,timeout=3) as response:
                task=json.load(response)
            self.assertEqual(task['tool'],'entity_list')
            self.assertEqual(task['arguments']['layer_filter'],'Aisle')
            self.assertEqual(task['arguments']['limit'],5)
            reply=json.dumps({'id':task['id'],'result':{'ok':True,
                 'content':[{'type':'text','text':'5 corridor entities'}]}}).encode()
            r=urllib.request.Request(self.base+'/agent/result',data=reply,
                headers={'Content-Type':'application/json','Authorization':'Bearer '+DEVICE_TOKEN},method='POST')
            with urllib.request.urlopen(r,timeout=3) as response:
                self.assertTrue(json.load(response)['accepted'])
            got=future.result(timeout=3)
        self.assertFalse(got['result']['isError'])
        self.assertIn('5 corridor entities',json.dumps(got))

    def test_unsafe_auto_lisp_and_unsanctioned_fields_rejected(self):
        unsafe=self.post('tools/call',{'name':'autocad_system_run_lisp',
                                     'arguments':{'code':'(princ)'}},timeout=2)
        self.assertEqual(unsafe['error']['code'],-32602)
        invalid=self.post('tools/call',{'name':'autocad_entity_list',
                         'arguments':{'layer_filter':'Aisle','command':'ERASE'}},timeout=2)
        self.assertEqual(invalid['error']['code'],-32602)

    def test_late_result_acknowledged_not_rejected_as_foreign_task(self):
        self.relay.expired['oldtask']={'pid':PAIR,'expires':time.monotonic()+120}
        body=json.dumps({'id':'oldtask','result':{'ok':True,'content':[{'type':'text','text':'late'}]}}).encode()
        req=urllib.request.Request(self.base+'/agent/result',data=body,headers={'Content-Type':'application/json','Authorization':'Bearer '+DEVICE_TOKEN},method='POST')
        with urllib.request.urlopen(req,timeout=2) as response:
            payload=json.load(response)
        self.assertFalse(payload['accepted'])
        self.assertTrue(payload['stale'])
if __name__=='__main__':unittest.main(verbosity=2)
