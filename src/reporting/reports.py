from __future__ import annotations
from decimal import Decimal
from src.business.models import money


def _sum(items, attr='total'):
    return money(sum((getattr(x,attr) for x in items),Decimal('0')))


def executive_summary(store, payment_store=None, cash_closings=(), bank_transactions=()):
    sales=list(store.sales.values()); purchases=list(store.purchases.values()); quotes=list(store.quotes.values())
    stock=sum((Decimal(r['quantity']) for r in store.stock_snapshot()),Decimal('0'))
    payments=list(payment_store.payments.values()) if payment_store else []
    allocated=sum((payment_store.allocated(p.payment_id) for p in payments),Decimal('0')) if payment_store else Decimal('0')
    return {
      'active_branches':len([x for x in store.branches.values() if x.active]),
      'active_users':len([x for x in store.users.values() if x.active]),
      'active_products':len([x for x in store.products.values() if x.active]),
      'customers':len(store.customers),'quotes':len(quotes),'quote_value':str(_sum(quotes)),
      'sales':len(sales),'sales_value':str(_sum(sales)),'purchases':len(purchases),
      'purchase_value':str(_sum(purchases)),'stock_units':str(stock),
      'payments_received':str(money(sum((p.amount for p in payments),Decimal('0')))),
      'payments_allocated':str(money(allocated)),
      'cash_closings':len(list(cash_closings)),'bank_evidence_rows':len(list(bank_transactions)),
      'reconciliation_status':'not_inferred'
    }


def branch_summary(store,branch_id,payment_store=None,cash_closings=(),bank_transactions=()):
    sales=[x for x in store.sales.values() if x.branch_id==branch_id]
    purchases=[x for x in store.purchases.values() if x.branch_id==branch_id]
    payments=[p for p in payment_store.payments.values() if p.branch_id==branch_id] if payment_store else []
    return {
      'branch_id':branch_id,'sales_count':len(sales),'sales_value':str(_sum(sales)),
      'purchase_count':len(purchases),'purchase_value':str(_sum(purchases)),
      'payment_value':str(money(sum((p.amount for p in payments),Decimal('0')))),
      'cash_closings':len([x for x in cash_closings if getattr(x,'branch_id',None)==branch_id]),
      'bank_evidence_rows':len([x for x in bank_transactions if getattr(x,'branch_id',None)==branch_id]),
      'stock':[r for r in store.stock_snapshot() if r['branch_id']==branch_id],
      'note':'Sales, payments, cash closings and bank evidence are reported separately until explicitly reconciled.'
    }


def stock_exceptions(store):
    return [r for r in store.stock_snapshot() if Decimal(r['quantity']) < 0]


def sales_by_product(store):
    rows={}
    for sale in store.sales.values():
        for line in sale.lines:
            row=rows.setdefault(line.product_id,{'product_id':line.product_id,'quantity':Decimal('0'),'value':Decimal('0')})
            row['quantity']+=line.quantity; row['value']+=line.line_total
    return [{**r,'quantity':str(r['quantity']),'value':str(money(r['value']))} for r in rows.values()]
