from __future__ import annotations
import unittest
from src.counter_ops.operations import CounterOpsStore
from src.evidence.capture import EvidenceStore
from src.sync.envelopes import SyncQueue

class WO0007Tests(unittest.TestCase):
 def test_po_lifecycle(self):
  s=CounterOpsStore(); po=s.create_po('B1','SUP1',[{'product_id':'P1','quantity':'2'}],'U1'); self.assertEqual(po.status,'draft'); s.approve_po(po.po_id,'OWNER'); self.assertEqual(po.status,'approved')
  with self.assertRaises(ValueError): s.approve_po(po.po_id,'OWNER')
 def test_transfer_requires_dispatch_before_receipt(self):
  s=CounterOpsStore(); t=s.request_transfer('B1','B2',[{'product_id':'P1','quantity':'1'}],'U1')
  with self.assertRaises(ValueError): s.receive_transfer(t.transfer_id,'U2')
  s.dispatch_transfer(t.transfer_id,'U1'); s.receive_transfer(t.transfer_id,'U2'); self.assertEqual(t.status,'received')
 def test_stock_count_reports_variance_without_mutation(self):
  s=CounterOpsStore(); c=s.start_count('B1','U1'); row=s.record_count_line(c.count_id,'P1','8','10',['E1']); self.assertEqual(str(row['variance']),'-2')
  result=s.finalize_count(c.count_id,'U1'); self.assertFalse(result['stock_mutated']); self.assertEqual(len(result['variances']),1)
 def test_ai_proposal_not_operational_until_accepted(self):
  e=EvidenceStore(); ev=e.capture('B1','photo',b'bench photo','image/jpeg','U1'); p=e.propose(ev.evidence_id,'parts_count',{'P1':7},0.82,'provider-test')
  self.assertEqual(e.operational_observations(),[]); a=e.accept(p.proposal_id,'U1'); self.assertEqual(a.payload['P1'],7); self.assertEqual(len(e.operational_observations()),1)
 def test_sync_idempotency_and_replay(self):
  q=SyncQueue(); a=q.enqueue('K1','D1','B1',1,'sale',{'sale_id':'S1'}); b=q.enqueue('K1','D1','B1',1,'sale',{'sale_id':'S1'}); self.assertEqual(a,b); self.assertEqual(len(q.pending()),1)
  with self.assertRaises(ValueError): q.enqueue('K1','D1','B1',1,'sale',{'sale_id':'S2'})
  q.acknowledge('K1'); self.assertEqual(q.pending(),[])

if __name__=='__main__': unittest.main()
