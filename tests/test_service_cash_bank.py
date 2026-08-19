from __future__ import annotations
import unittest
from datetime import date
from decimal import Decimal
from src.service.service import MachineRecord, ServiceStore
from src.cash.closing import create_closing
from src.bank.normalization import BankTransaction, candidate_reconciliation
from src.import_export.csv_contracts import FIELDSETS

class ServiceCashBankTests(unittest.TestCase):
 def test_service_history_is_machine_linked(self):
  s=ServiceStore(); s.add_machine(MachineRecord('mach-1','cus-1','prd-1','CS-620SX','SER123')); j=s.open_job('br-1','cus-1','mach-1','Stops when hot','usr-1'); s.add_observation(j.job_id,'Fuel line checked','usr-2'); s.update_status(j.job_id,'inspecting','Diagnosis started','usr-2'); h=s.history_for_machine('mach-1'); self.assertEqual(len(h['jobs']),1); self.assertGreaterEqual(len(h['events']),3)
 def test_closing_cash_variance(self):
  c=create_closing('br-1',date(2026,8,19),1000,5000,0,250,2000,3800,'usr-1'); self.assertEqual(c.expected_closing,Decimal('3750')); self.assertEqual(c.variance,Decimal('50'))
 def test_bank_candidate_does_not_confirm_match(self):
  b=BankTransaction('bt-1','st-1','hdfc.csv',7,'acct-1',date(2026,8,19),None,'credit',Decimal('5000'),'UPI RECEIPT','ref'); b.validate(); r=candidate_reconciliation(b,5000,date(2026,8,19)); self.assertTrue(r['amount_equal']); self.assertEqual(r['status'],'candidate_only_not_confirmed')
 def test_contracts_include_service_cash_bank(self):
  for name in ('machines','service_jobs','service_events','cash_closings','bank_transactions'): self.assertIn(name,FIELDSETS)

if __name__=='__main__': unittest.main()
