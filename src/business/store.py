from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable

from .models import Branch, Customer, LineItem, PriceRecord, Product, Purchase, Quote, Sale, StockMovement, Supplier, UserRecord, new_id


class BusinessError(ValueError):
    pass


class InMemoryBusinessStore:
    def __init__(self):
        self.users={}; self.branches={}; self.products={}; self.prices={}; self.customers={}; self.suppliers={}
        self.quotes={}; self.sales={}; self.purchases={}; self.stock_movements=[]

    def add_branch(self, x: Branch):
        if x.branch_id in self.branches or any(v.code.lower()==x.code.lower() for v in self.branches.values()): raise BusinessError('branch must be unique')
        self.branches[x.branch_id]=x; return x
    def add_user(self, x: UserRecord):
        if x.branch_id and x.branch_id not in self.branches: raise BusinessError('user branch does not exist')
        self.users[x.user_id]=x; return x
    def add_product(self, x: Product):
        if x.product_id in self.products or any(v.sku.lower()==x.sku.lower() for v in self.products.values()): raise BusinessError('product must be unique')
        self.products[x.product_id]=x; return x
    def add_price(self, x: PriceRecord):
        if x.product_id not in self.products: raise BusinessError('price product does not exist')
        self.prices[x.price_id]=x; return x
    def add_customer(self, x: Customer): self.customers[x.customer_id]=x; return x
    def add_supplier(self, x: Supplier): self.suppliers[x.supplier_id]=x; return x

    def current_price(self, product_id, on_date, branch_id=None, price_type='mrp'):
        rows=[p for p in self.prices.values() if p.product_id==product_id and p.price_type==price_type and p.effective_from<=on_date and (p.effective_to is None or p.effective_to>=on_date) and (p.branch_id is None or p.branch_id==branch_id)]
        if not rows: raise BusinessError('no active price found')
        return sorted(rows,key=lambda p:(p.branch_id is not None,p.effective_from),reverse=True)[0]

    def create_quote(self, branch_id, customer_id, items: Iterable[LineItem]):
        self._branch(branch_id)
        if customer_id not in self.customers: raise BusinessError('customer does not exist')
        items=self._items(items)
        q=Quote(new_id('quo'),branch_id,customer_id,datetime.now(timezone.utc),items)
        self.quotes[q.quote_id]=q; return q

    def create_purchase(self, branch_id, supplier_id, items: Iterable[LineItem], supplier_invoice_no=''):
        self._branch(branch_id)
        if supplier_id not in self.suppliers: raise BusinessError('supplier does not exist')
        items=self._items(items)
        p=Purchase(new_id('pur'),branch_id,supplier_id,datetime.now(timezone.utc),items,supplier_invoice_no)
        self.purchases[p.purchase_id]=p
        for i in items: self._stock(branch_id,i.product_id,i.quantity,'purchase','purchase',p.purchase_id)
        return p

    def create_sale(self, branch_id, customer_id, items: Iterable[LineItem], source_quote_id=None):
        self._branch(branch_id)
        if customer_id and customer_id not in self.customers: raise BusinessError('customer does not exist')
        items=self._items(items)
        for i in items:
            if self.stock_on_hand(branch_id,i.product_id)<i.quantity: raise BusinessError(f'insufficient stock for {i.product_id}')
        s=Sale(new_id('sal'),branch_id,customer_id,datetime.now(timezone.utc),items,source_quote_id=source_quote_id)
        self.sales[s.sale_id]=s
        for i in items: self._stock(branch_id,i.product_id,-i.quantity,'sale','sale',s.sale_id)
        return s

    def adjust_stock(self, branch_id, product_id, delta, note):
        self._branch(branch_id); self._product(product_id)
        delta=Decimal(str(delta))
        if not note.strip(): raise BusinessError('stock adjustment requires a note')
        if self.stock_on_hand(branch_id,product_id)+delta<0: raise BusinessError('adjustment would make stock negative')
        return self._stock(branch_id,product_id,delta,'adjustment','manual_adjustment',new_id('adj'),note)

    def stock_on_hand(self, branch_id, product_id):
        return sum((m.quantity_delta for m in self.stock_movements if m.branch_id==branch_id and m.product_id==product_id),Decimal('0'))

    def stock_snapshot(self):
        keys={(m.branch_id,m.product_id) for m in self.stock_movements}
        return [{'branch_id':b,'product_id':p,'quantity':str(self.stock_on_hand(b,p))} for b,p in sorted(keys)]

    def _stock(self,b,p,d,kind,ref_type,ref_id,note=''):
        m=StockMovement(new_id('stk'),b,p,Decimal(str(d)),kind,datetime.now(timezone.utc),ref_type,ref_id,note)
        self.stock_movements.append(m); return m
    def _items(self,items):
        items=tuple(items)
        if not items: raise BusinessError('at least one line item is required')
        for i in items:
            self._product(i.product_id)
            if i.quantity<=0 or i.unit_price<0 or i.discount<0: raise BusinessError('invalid line item')
        return items
    def _branch(self,b):
        if b not in self.branches: raise BusinessError('branch does not exist')
    def _product(self,p):
        if p not in self.products: raise BusinessError('product does not exist')
