"""Regression: one phone, one immutable license, old codes invalid."""
import os,sqlite3,tempfile,secrets,hashlib,unittest,importlib
from pathlib import Path
import oauth_core
from one_license_migration import migrate
class SingleLicense(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.path=Path(self.tmp.name)/"oauth.sqlite"
  os.environ["AVENA_OAUTH_DB"]=str(self.path)
  os.environ["AVENA_OAUTH_LOGIN_HASH"]="test"
  self.a=importlib.reload(oauth_core)
 def tearDown(self):self.tmp.cleanup()
 def test_new_number_unique_and_wrong_code(self):
  a=self.a;a.init()
  code=a.new_pair("۰۹۱۲۳۴۵۶۷۸۹")
  original=a.lookup_pair(code)
  self.assertEqual(original["phone"],"09123456789")
  with self.assertRaises(a.LicenseAlreadyExists):
   a.new_pair("+989123456789")
  self.assertEqual(a.lookup_pair(code)["id"],original["id"])
  self.assertIsNone(a.lookup_pair("AAAA-BBBB-CCCC-DDDD-EEEE"))
  rejected,err=a.activate_device("AAAA-BBBB-CCCC-DDDD-EEEE","a"*32)
  self.assertIsNone(rejected)
  self.assertEqual(err,"invalid_activation_code")
  token,err=a.activate_device(code,"a"*32)
  self.assertIsNone(err)
  self.assertEqual(a.activate_device(code,"b"*32)[1],"already_activated_on_other_device")
  with a.connect() as c:
   with self.assertRaises(sqlite3.IntegrityError):
    c.execute("UPDATE pairings SET phone=? WHERE id=?",("09123333333",original["id"]))
   with self.assertRaises(sqlite3.IntegrityError):
    c.execute("UPDATE pairings SET code_hash=? WHERE id=?",(a.sha("OTHER"),original["id"]))
 def test_migration_preserves_newest_device_and_revokes_duplicates(self):
  a=self.a
  # Create a legacy schema without the new phone table/unique index.
  with a.connect() as c:
   c.executescript("""CREATE TABLE pairings(id TEXT PRIMARY KEY,phone TEXT NOT NULL,code_hash TEXT UNIQUE NOT NULL,created INTEGER NOT NULL,revoked INTEGER NOT NULL DEFAULT 0,device_id TEXT,device_token_hash TEXT,paired_at INTEGER);
   CREATE TABLE clients(id TEXT PRIMARY KEY,redirects TEXT,created INTEGER);
   CREATE TABLE codes(codehash TEXT PRIMARY KEY,client TEXT,redirect TEXT,challenge TEXT,scopes TEXT,resource TEXT,expire INTEGER,pair_id TEXT);
   CREATE TABLE tokens(hash TEXT PRIMARY KEY,client TEXT,kind TEXT,scopes TEXT,resource TEXT,expire INTEGER,pair_id TEXT);""")
   for i in range(5):
    c.execute("INSERT INTO pairings VALUES(?,?,?,?,?,?,?,?)",
      (f"{i+1:032x}","09123334455",a.sha("CODE"+str(i)),100+i,0,
       f"{i+1:032x}" if i in (1,3) else None,"dev"+str(i) if i in (1,3) else None,
       200+i if i in (1,3) else None))
   c.execute("INSERT INTO tokens VALUES(?,?,?,?,?,?,?)",
     (a.sha("test_access"),"client","access","cad:read",a.RESOURCE,9999999999,f"{1:032x}"))
  report=migrate(str(self.path))
  self.assertEqual(report["phones"],1)
  self.assertEqual(report["duplicate_licenses_revoked"],4)
  self.assertEqual(report["retained_connection_ids"],[f"{4:032x}"[:8]])
  self.assertEqual(migrate(str(self.path))["duplicate_licenses_revoked"],0)
  a.init()
  self.assertIsNone(a.pair_from_oauth("Bearer test_access")) # stale session stays revoked
  self.assertIsNone(a.lookup_pair("CODE0"))
  with self.assertRaises(a.LicenseAlreadyExists):
   a.new_pair("09123334455")
  with a.connect() as c:
   self.assertEqual(c.execute("SELECT COUNT(*) FROM pairings WHERE revoked=0").fetchone()[0],1)
   self.assertEqual(c.execute("SELECT COUNT(*) FROM phone_licenses").fetchone()[0],1)
if __name__=="__main__":unittest.main()
