from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool


DEMO_SCHEMA = '''
CREATE TABLE customers (id TEXT PRIMARY KEY, name TEXT NOT NULL, tier TEXT NOT NULL);
CREATE TABLE orders (id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id), total_cents INTEGER NOT NULL CHECK(total_cents >= 0), status TEXT NOT NULL CHECK(status IN ('pending','shipped','cancelled')), created_at TEXT NOT NULL);
CREATE TABLE invoices (id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id), order_id TEXT NOT NULL REFERENCES orders(id), total_cents INTEGER NOT NULL CHECK(total_cents >= 0), status TEXT NOT NULL CHECK(status IN ('open','paid','overdue')), due_date TEXT NOT NULL);
'''
DEMO_SEED = '''
INSERT INTO customers VALUES ('cus_001','Example Workshop','standard'),('cus_002','Example Studio','plus');
INSERT INTO orders VALUES ('ord_001','cus_001',12900,'pending','2026-10-01'),('ord_002','cus_001',4500,'shipped','2026-10-02'),('ord_003','cus_001',9900,'cancelled','2026-10-03'),('ord_004','cus_002',22000,'pending','2026-10-04');
INSERT INTO invoices VALUES ('inv_001','cus_001','ord_001',12900,'open','2026-11-01'),('inv_002','cus_001','ord_002',4500,'paid','2026-10-15'),('inv_003','cus_001','ord_003',9900,'overdue','2026-10-01'),('inv_004','cus_002','ord_004',22000,'open','2026-11-04');
'''


class Database:
    def __init__(self, url):
        kwargs = {'pool_pre_ping':True}
        if url.startswith('sqlite'):
            kwargs.update(connect_args={'check_same_thread':False},poolclass=StaticPool)
        else:
            kwargs['connect_args'] = {'connect_timeout':3, 'options':'-c statement_timeout=3000'}
        self.engine = create_engine(url, **kwargs)

    def fetch_all(self, sql, params=None):
        with self.engine.connect() as connection:
            return [dict(row) for row in connection.execute(text(sql),params or {}).mappings()]

    def fetch_one(self, sql, params=None):
        rows = self.fetch_all(sql,params)
        return rows[0] if rows else None

    def ready(self):
        return self.fetch_one('SELECT 1 AS ready')['ready'] == 1

    def prepare_sqlite_demo(self):
        """Local/test fixture only. PostgreSQL uses versioned SQL migrations."""
        if self.engine.dialect.name != 'sqlite':
            raise ValueError('This fixture is only for SQLite; run migrations for PostgreSQL')
        with self.engine.begin() as connection:
            for statement in (DEMO_SCHEMA + DEMO_SEED).split(';'):
                if statement.strip():
                    connection.execute(text(statement))
