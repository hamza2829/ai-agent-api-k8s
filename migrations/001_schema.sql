CREATE TABLE customers (
  id TEXT PRIMARY KEY CHECK (id ~ '^cus_[0-9]{3}$'),
  name TEXT NOT NULL,
  tier TEXT NOT NULL CHECK (tier IN ('standard','plus'))
);
CREATE TABLE orders (
  id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL REFERENCES customers(id),
  total_cents INTEGER NOT NULL CHECK(total_cents >= 0),
  status TEXT NOT NULL CHECK(status IN ('pending','shipped','cancelled')),
  created_at DATE NOT NULL,
  UNIQUE(id,customer_id)
);
CREATE TABLE invoices (
  id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL REFERENCES customers(id),
  order_id TEXT NOT NULL,
  total_cents INTEGER NOT NULL CHECK(total_cents >= 0),
  status TEXT NOT NULL CHECK(status IN ('open','paid','overdue')),
  due_date DATE NOT NULL,
  FOREIGN KEY(order_id,customer_id) REFERENCES orders(id,customer_id)
);
CREATE INDEX orders_customer_status ON orders(customer_id,status);
CREATE INDEX invoices_customer_status ON invoices(customer_id,status);
