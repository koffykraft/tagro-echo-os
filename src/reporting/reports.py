from __future__ import annotations
from decimal import Decimal
from src.business.models import money


def executive_summary(store):
    sales=money(sum((s.total for s in store.sales.values()),Decimal('0')))
    purchases=money(sum((p.total for p in store.purchases.values()),Decimal('0')))
    quotes=money(sum((q.total for q in store.quotes.values()),Decimal('0')))
    stock=sum((Decimal(r['quantity']) for r in store.stock_snapshot()),Decimal('0'))
    return {
      'active_branches':len([x for x in store.branches.values() if x.active]),
      'active_users':len([x for x in store.users.values() if x.active]),
      'active_products':len([x for x in store.products.values() if x.active]),
      'customers':len(store.customers),'quotes':len(store.quotes),'quote_value':str(quotes),
      'sales':len(store.sales),'sales_value':str(sales),'purchases':len(store.purchases),
      'purchase_value':str(purchases),'stock_units':str(stock)
    }


def branch_summary(store,branch_id):
    sales=[x for x in store.sales.values() if x.branch_id==branch_id]
    purchases=[x for x in store.purchases.values() if x.branch_id==branch_id]
    return {'branch_id':branch_id,'sales_count':len(sales),'sales_value':str(money(sum((x.total for x in sales),Decimal('0')))),'purchase_count':len(purchases),'purchase_value':str(money(sum((x.total for x in purchases),Decimal('0')))),'stock':[r for r in store.stock_snapshot() if r['branch_id']==branch_id]}
