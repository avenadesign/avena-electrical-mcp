"""Offline multi-device pairing + OAuth regression suite."""
import base64,hashlib,os,secrets,tempfile,unittest
class Cases(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  os.environ["AVENA_OAUTH_DB"]=self.tmp.name+"/qa.sqlite"
  os.environ["AVENA_OAUTH_LOGIN_HASH"]="test"
  import importlib,oauth_core
  self.a=importlib.reload(oauth_core)
  self.a.init()
 def tearDown(self):
  self.tmp.cleanup()
 def test_phone_and_pairing(self):
  a=self.a
  self.assertEqual(a.normalize_phone("۰۹۱۲۳۴۵۶۷۸۹"),"09123456789")
  code=a.new_pair("09123456789")
  self.assertEqual(len(a.normalize_code(code)),20)
  token,err=a.activate_device(code,"a"*32)
  self.assertIsNone(err)
  self.assertEqual(a.pair_from_agent("Bearer "+token["device_token"])["id"],token["pairing_id"])
  self.assertEqual(a.activate_device(code,"b"*32)[1],"already_activated_on_other_device")
 def test_oauth_audience_isolation(self):
  a=self.a
  pair1=a.lookup_pair(a.new_pair("09123456789"))
  pair2=a.lookup_pair(a.new_pair("09123456788"))
  client,err=a.register({"redirect_uris":["https://chatgpt.com/connector_platform_oauth_redirect"]})
  self.assertIsNone(err)
  verifier=secrets.token_urlsafe(48)
  challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
  params={"client_id":client["client_id"],"redirect_uri":client["redirect_uris"][0],
  "response_type":"code","code_challenge_method":"S256","code_challenge":challenge}
  self.assertIsNone(a.validate(params))
  code=a.issue_code(params,pair1["id"])
  request={"client_id":client["client_id"],"grant_type":"authorization_code",
   "redirect_uri":params["redirect_uri"],"code":code,"code_verifier":verifier}
  token,err=a.exchange(request)
  self.assertIsNone(err)
  self.assertEqual(a.pair_from_oauth("Bearer "+token["access_token"])["id"],pair1["id"])
  self.assertNotEqual(a.pair_from_oauth("Bearer "+token["access_token"])["id"],pair2["id"])
  self.assertEqual(a.exchange(request)[1],"invalid_grant")
if __name__=="__main__":unittest.main()
