"""Migrate existing phone duplicates to ONE immutable license per phone.
Does not transfer OAuth credentials across licenses. Stop OAuth writer first.
"""
import sqlite3,sys
from collections import defaultdict
def migrate(path):
 c=sqlite3.connect(path,timeout=15);c.row_factory=sqlite3.Row
 try:
  c.execute('BEGIN IMMEDIATE')
  c.execute('CREATE TABLE IF NOT EXISTS phone_licenses(phone TEXT PRIMARY KEY,pair_id TEXT UNIQUE NOT NULL,created INTEGER NOT NULL)')
  groups=defaultdict(list)
  for p in c.execute('SELECT id,phone,created,paired_at,revoked,device_id FROM pairings'):
   groups[p['phone']].append(p)
  revoked=0;kept=[]
  for phone,rows in groups.items():
   registered=c.execute('SELECT pair_id FROM phone_licenses WHERE phone=?',(phone,)).fetchone()
   if registered:
    target=next((p for p in rows if p['id']==registered['pair_id']),None)
    if target is None:raise RuntimeError('Registry mismatch')
   else:
    candidates=[p for p in rows if not p['revoked']] or rows
    target=max(candidates,key=lambda p:(p['device_id'] is not None,p['paired_at'] or 0,p['created'],p['id']))
    c.execute('INSERT INTO phone_licenses VALUES(?,?,?)',(phone,target['id'],target['created']))
   for p in rows:
    if p['id']!=target['id'] and not p['revoked']:
     c.execute('UPDATE pairings SET revoked=1 WHERE id=?',(p['id'],))
     revoked+=1
   kept.append(target['id'][:8])
  c.execute('CREATE UNIQUE INDEX IF NOT EXISTS ux_pair_active_phone ON pairings(phone) WHERE revoked=0')
  c.execute('CREATE UNIQUE INDEX IF NOT EXISTS ux_one_device_per_license ON pairings(device_id) WHERE device_id IS NOT NULL AND revoked=0')
  c.execute("CREATE TRIGGER IF NOT EXISTS lock_pair_identity BEFORE UPDATE OF phone,code_hash ON pairings BEGIN SELECT RAISE(ABORT,'immutable license'); END")
  c.execute("CREATE TRIGGER IF NOT EXISTS lock_phone_mapping BEFORE UPDATE ON phone_licenses BEGIN SELECT RAISE(ABORT,'immutable license mapping'); END")
  assert c.execute('SELECT COUNT(*) FROM phone_licenses').fetchone()[0]==len(groups)
  c.commit()
  return {'phones':len(groups),'duplicate_licenses_revoked':revoked,'retained_connection_ids':kept}
 except:
  c.rollback();raise
 finally:c.close()
if __name__=='__main__':print(migrate(sys.argv[1]))
