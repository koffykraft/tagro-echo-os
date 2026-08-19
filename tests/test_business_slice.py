from __future__ import annotations
import unittest
from datetime import date
from decimal import Decimal
from src.business.models import Branch,Customer,LineItem,PriceRecord,Product,Supplier,UserRecord
from src.business.store import BusinessError,InMemoryBusinessStore
from src.import_export.csv_contracts import FIELDSETS,ImportContractError,read_csv,template_csv
from src.reporting.reports import executive_summary

class BusinessSliceTests(unittest.TestCase):
 def setUp(self):
  self.s=InMemoryBusinessStore(); self.s.add_branch(Branch('br-001','TVM01','Test Counter','Thiruvananthapuram')); self.s.add_user(UserRecord('usr-001','Staff','staff@example.com','seller','br-001')); self.s.add_product(Product('prd-001','CS620SX','CS-620SX','ECHO CS-620SX','chainsaw',Decimal('18'),serial_tracked=True)); self.s.add_price(PriceRecord('prc-001','prd-001','mrp',Decimal('65400'),date(2026,8,1))); self.s.add_customer(Customer('cus-001','Customer','9999999999')); self.s.add_supplier(Supplier('sup-001','Supplier')); self.s.create_purchase('br-001','sup-001',[LineItem('prd-001',Decimal('2'),Decimal('100'),Decimal('18'))],'INV-1')
 def test_quote(self): self.assertEqual(str(self.s.create_quote('br-001','cus-001',[LineItem('prd-001',Decimal('1'),Decimal('100'),Decimal('18'))]).total),'118.00')
 def test_stock_flow(self):
  self.assertEqual(self.s.stock_on_hand('br-001','prd-001'),Decimal('2')); self.s.create_sale('br-001','cus-001',[LineItem('prd-001',Decimal('1'),Decimal('100'),Decimal('18'))]); self.assertEqual(self.s.stock_on_hand('br-001','prd-001'),Decimal('1'))
 def test_negative_stock_blocked(self):
  with self.assertRaises(BusinessError): self.s.create_sale('br-001','cus-001',[LineItem('prd-001',Decimal('3'),Decimal('100'),Decimal('18'))])
 def test_price(self): self.assertEqual(self.s.current_price('prd-001',date(2026,8,19),'br-001').amount,Decimal('65400'))
 def test_import_header_strict(self):
  self.assertEqual(tuple(template_csv('products').strip().split(',')),FIELDSETS['products'])
  with self.assertRaises(ImportContractError): read_csv('products','sku,name\nA,B\n')
 def test_report_same_store(self):
  self.s.create_sale('br-001','cus-001',[LineItem('prd-001',Decimal('1'),Decimal('100'),Decimal('18'))]); r=executive_summary(self.s); self.assertEqual(r['sales'],1); self.assertEqual(r['purchases'],1); self.assertEqual(r['stock_units'],'1')

if __name__=='__main__': unittest.main()
