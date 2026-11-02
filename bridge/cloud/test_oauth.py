"""Offline OAuth 2.1 regression tests, no production credentials."""
import base64,hashlib,importlib,os,secrets,tempfile,unittest
class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  os.environ["AVENA_OAUTH_DB"]=self.temp.name+"/oauth.sqlite"
  os.environ["AVENA_OAUTH_LOGIN_HASH"]="a1"*16+"$"+hashlib.pbkdf2_hmac("sha256",b"qa-secret",bytes.fromhex("a1"*16),350000).hex()
  import oauth_core
  self.a=importlib.reload(oauth_core)
  self.a.init()
 def tearDown(self):self.temp.cleanup()
 def test_login_and_redirect_protection(self):
  self.assertTrue(self.a.valid_pass("qa-secret"))
  self.assertFalse(self.a.valid_pass("bad"))
  self.assertFalse(self.a.valid_redirect("https://attacker.example/callback"))
  self.assertTrue(self.a.valid_redirect("https://chatgpt.com/connector_platform_oauth_redirect"))
 def test_pkce_bearer_replay_refresh(self):
  a=self.a
  client,error=a.register({"redirect_uris":["https://chatgpt.com/connector_platform_oauth_redirect"],"token_endpoint_auth_method":"none"})
  self.assertIsNone(error)
  verifier=secrets.token_urlsafe(48)
  challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
  p={"client_id":client["client_id"],"redirect_uri":client["redirect_uris"][0],
    "response_type":"code","resource":a.RESOURCE,"scope":"cad:read offline_access",
    "code_challenge":challenge,"code_challenge_method":"S256"}
  self.assertIsNone(a.validate(p))
  code=a.issue_code(p)
  request={"grant_type":"authorization_code","client_id":client["client_id"],
          "redirect_uri":p["redirect_uri"],"code":code,"code_verifier":verifier,"resource":a.RESOURCE}
  tokens,error=a.exchange(request)
  self.assertIsNone(error)
  self.assertTrue(a.verify("Bearer "+tokens["access_token"]))
  _,error=a.exchange(request)
  self.assertEqual(error,"invalid_grant")
  new,error=a.exchange({"grant_type":"refresh_token","client_id":client["client_id"],
      "refresh_token":tokens["refresh_token"],"resource":a.RESOURCE})
  self.assertIsNone(error)
  self.assertTrue(a.verify("Bearer "+new["access_token"]))
  old,error=a.exchange({"grant_type":"refresh_token","client_id":client["client_id"],
      "refresh_token":tokens["refresh_token"],"resource":a.RESOURCE})
  self.assertEqual(error,"invalid_grant")
if __name__=="__main__":unittest.main()
