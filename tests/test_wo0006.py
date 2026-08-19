from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from src.payments.payments import PaymentStore
from src.documents.render import render_commercial_document
from src.repository.snapshot import JsonSnapshotRepository
from src.accounting.export_package import build_accounting_package

class WO0006Tests(unittest.TestCase):
 def test_payment_allocation_is_explicit(self):
  s=PaymentStore(); p=s.receive('br-1','cus-1','upi','1000','usr-1','UTR1'); a=s.allocate(p.payment_id,'sale','sale-1','600','usr-1')
  self.assertEqual(str(s.unallocated(p.payment_id)),'400'); self.assertEqual(a.target_id,'sale-1')
  with self.assertRaises(ValueError): s.allocate(p.payment_id,'sale','sale-2','401','usr-1')
 def test_document_is_deterministic_and_printable(self):
  args=dict(document_type='quote',document_id='Q-1',branch={'code':'KVR','name':'Karavaloor'},party={'name':'A','phone':'1'},items=[{'product_id':'P1','description':'CS-620SX','quantity':'1','unit_price':'100','gst_rate':'18'}],created_at='2026-08-19',status='draft')
  a=render_commercial_document(**args); b=render_commercial_document(**args)
  self.assertEqual(a,b); self.assertIn('Print / Save PDF',a); self.assertIn('₹118.00',a)
 def test_accounting_package_is_file_only(self):
  pkg=build_accounting_package(sales=[{'sale_id':'S1','total':'118'}],payments=[{'payment_id':'P1','amount':'118'}])
  self.assertIn('manifest.json',pkg); self.assertIn('"production_write": false',pkg['manifest.json']); self.assertIn('S1',pkg['sales.csv'])
 def test_snapshot_roundtrip(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'snapshot.json'; r=JsonSnapshotRepository(p); r.put('products','P1',{'id':'P1','name':'Saw'}); r.append('events',{'id':'E1'}); r.save()
   r2=JsonSnapshotRepository(p); self.assertEqual(r2.get('products','P1')['name'],'Saw'); self.assertEqual(r2.stream('events')[0]['id'],'E1')

if __name__=='__main__': unittest.main()
