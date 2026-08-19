-- TAGRO ECHO OS canonical relational model v0.1
-- Provider-independent PostgreSQL-compatible design. Not a deployment script.

create table branches (
  branch_id text primary key, code text not null unique, name text not null,
  district text not null, branch_type text not null default 'counter', active boolean not null default true
);
create table users (
  user_id text primary key, name text not null, email text not null unique,
  role text not null, branch_id text references branches(branch_id), active boolean not null default true
);
create table products (
  product_id text primary key, sku text not null unique, model text not null,
  name text not null, category text not null, gst_rate numeric(6,3) not null,
  unit text not null default 'nos', serial_tracked boolean not null default false,
  active boolean not null default true
);
create table prices (
  price_id text primary key, product_id text not null references products(product_id),
  price_type text not null, amount numeric(14,2) not null check(amount>=0),
  effective_from date not null, effective_to date,
  branch_id text references branches(branch_id)
);
create table customers (
  customer_id text primary key, name text not null, phone text not null,
  email text not null default '', gstin text not null default '', district text not null default ''
);
create table suppliers (
  supplier_id text primary key, name text not null, phone text not null default '',
  email text not null default '', gstin text not null default ''
);
create table quote_headers (
  quote_id text primary key, branch_id text not null references branches(branch_id),
  customer_id text not null references customers(customer_id), created_at timestamptz not null,
  status text not null, total numeric(14,2) not null
);
create table quote_lines (
  quote_id text not null references quote_headers(quote_id), line_no integer not null,
  product_id text not null references products(product_id), quantity numeric(14,3) not null check(quantity>0),
  unit_price numeric(14,2) not null check(unit_price>=0), discount numeric(14,2) not null default 0,
  gst_rate numeric(6,3) not null, line_total numeric(14,2) not null,
  primary key(quote_id,line_no)
);
create table sale_headers (
  sale_id text primary key, branch_id text not null references branches(branch_id),
  customer_id text references customers(customer_id), created_at timestamptz not null,
  payment_status text not null, source_quote_id text references quote_headers(quote_id),
  total numeric(14,2) not null
);
create table sale_lines (
  sale_id text not null references sale_headers(sale_id), line_no integer not null,
  product_id text not null references products(product_id), quantity numeric(14,3) not null check(quantity>0),
  unit_price numeric(14,2) not null check(unit_price>=0), discount numeric(14,2) not null default 0,
  gst_rate numeric(6,3) not null, line_total numeric(14,2) not null,
  primary key(sale_id,line_no)
);
create table purchase_headers (
  purchase_id text primary key, branch_id text not null references branches(branch_id),
  supplier_id text not null references suppliers(supplier_id), created_at timestamptz not null,
  supplier_invoice_no text not null default '', total numeric(14,2) not null
);
create table purchase_lines (
  purchase_id text not null references purchase_headers(purchase_id), line_no integer not null,
  product_id text not null references products(product_id), quantity numeric(14,3) not null check(quantity>0),
  unit_price numeric(14,2) not null check(unit_price>=0), discount numeric(14,2) not null default 0,
  gst_rate numeric(6,3) not null, line_total numeric(14,2) not null,
  primary key(purchase_id,line_no)
);
create table stock_movements (
  movement_id text primary key, branch_id text not null references branches(branch_id),
  product_id text not null references products(product_id), quantity_delta numeric(14,3) not null check(quantity_delta<>0),
  movement_type text not null, occurred_at timestamptz not null,
  reference_type text not null, reference_id text not null, note text not null default ''
);

-- Stock position is derived, never independently edited.
create view stock_position as
select branch_id, product_id, sum(quantity_delta) quantity
from stock_movements group by branch_id, product_id;
