"""Versioned PostgreSQL SQL migrations. Run only with a separate owner credential."""
import argparse
import hashlib
import os
from pathlib import Path
import psycopg
from psycopg import sql


def migrate(database_url=None, demo_bootstrap=False, read_password=None):
    url = (database_url or os.environ['DATABASE_URL']).replace('postgresql+psycopg://','postgresql://',1)
    directory = Path(__file__).resolve().parents[2] / 'migrations'
    if not directory.exists():
        # Docker working directory contains migrations; source checkout uses parents[2].
        directory = Path.cwd() / 'migrations'
    files = sorted(directory.glob('*.sql'))
    if not files:
        raise RuntimeError('No SQL migrations found; run from the repository root or image /app directory')
    with psycopg.connect(url) as connection:
        connection.execute('SELECT pg_advisory_xact_lock(67239201)')
        connection.execute('''CREATE TABLE IF NOT EXISTS schema_migrations
          (version TEXT PRIMARY KEY, checksum TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())''')
        for path in files:
            body = path.read_text(encoding='utf-8')
            checksum = hashlib.sha256(body.encode()).hexdigest()
            existing = connection.execute('SELECT checksum FROM schema_migrations WHERE version=%s',(path.name,)).fetchone()
            if existing:
                if existing[0] != checksum:
                    raise ValueError(f'Applied migration changed: {path.name}')
                continue
            connection.execute(body,prepare=False)
            connection.execute('INSERT INTO schema_migrations(version,checksum) VALUES (%s,%s)',(path.name,checksum))
            print(f'Applied {path.name}')
        if demo_bootstrap:
            password = read_password or os.environ['READ_DB_PASSWORD']
            if len(password) < 12:
                raise ValueError('Demo reader password must have at least 12 characters')
            exists = connection.execute("SELECT 1 FROM pg_roles WHERE rolname='agent_reader'").fetchone()
            if not exists:
                connection.execute('CREATE ROLE agent_reader LOGIN')
            connection.execute(sql.SQL('ALTER ROLE agent_reader PASSWORD {}').format(sql.Literal(password)))
            connection.execute('REVOKE ALL ON SCHEMA public FROM PUBLIC')
            connection.execute('GRANT USAGE ON SCHEMA public TO agent_reader')
            connection.execute('GRANT SELECT ON customers,orders,invoices TO agent_reader')
            connection.execute("ALTER ROLE agent_reader SET default_transaction_read_only = on")
            print('Configured demo read-only agent_reader role')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo-bootstrap',action='store_true',help='Create demo read-only database role; requires owner rights')
    args = parser.parse_args()
    migrate(demo_bootstrap=args.demo_bootstrap)
