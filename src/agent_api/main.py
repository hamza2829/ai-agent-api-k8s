from contextlib import asynccontextmanager
from enum import Enum
from typing import Annotated
import hmac
import json
import logging
import re
import time
from uuid import uuid4
from fastapi import FastAPI, Depends, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from sqlalchemy.exc import SQLAlchemyError
from .config import Settings
from .database import Database
from .security import RateLimiter

logger = logging.getLogger('agent_api.requests')
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
key_header = APIKeyHeader(name='X-API-Key',auto_error=False)
CustomerId = Annotated[str, Path(pattern=r'^cus_[0-9]{3}$')]
Limit = Annotated[int, Query(ge=1,le=20)]
Offset = Annotated[int, Query(ge=0,le=1000)]


class OrderStatus(str, Enum):
    pending='pending'
    shipped='shipped'
    cancelled='cancelled'


class InvoiceStatus(str, Enum):
    open='open'
    paid='paid'
    overdue='overdue'


def create_app(settings=None, database=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.settings = settings or Settings.from_env()
        app.state.database = database or Database(app.state.settings.database_url)
        app.state.limiter = RateLimiter(app.state.settings.rate_limit,app.state.settings.rate_window_seconds)
        yield
        if database is None:
            app.state.database.engine.dispose()

    app = FastAPI(title='Read-only fake customer API',version='0.1.0',lifespan=lifespan)

    @app.middleware('http')
    async def request_log(request, call_next):
        supplied_id = request.headers.get('X-Request-ID','')
        request_id = supplied_id if re.fullmatch(r'[a-f0-9]{32}',supplied_id) else uuid4().hex
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers['X-Request-ID'] = request_id
            response.headers['Cache-Control'] = 'no-store'
            return response
        finally:
            route = request.scope.get('route')
            logger.info(json.dumps(dict(request_id=request_id,method=request.method,
                                        path=getattr(route,'path','/unmatched'),status=status,
                                        duration_ms=round((time.perf_counter()-started)*1000,3))))

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, error):
        # Do not expose SQL, credential-bearing connection strings or driver errors.
        return JSONResponse(status_code=503,content={'detail':'Customer data unavailable; retry later'})

    def authorize(customer_id:CustomerId,request:Request,key:Annotated[str|None,Depends(key_header)]):
        valid = key is not None and key.isascii() and hmac.compare_digest(key,request.app.state.settings.api_key)
        if not valid:
            raise HTTPException(401,'Missing or invalid API key',headers={'WWW-Authenticate':'ApiKey'})
        # Scope is independent of what the model requests in its arguments.
        if customer_id not in request.app.state.settings.allowed_customer_ids:
            raise HTTPException(403,'API key is not authorized for this customer')
        allowed, retry = request.app.state.limiter.check('configured-api-key')
        if not allowed:
            raise HTTPException(429,'Request limit exceeded; retry later',headers={'Retry-After':str(retry)})
        return customer_id

    def customer_exists(db, customer_id):
        row = db.fetch_one('SELECT id,name,tier FROM customers WHERE id=:customer_id',{'customer_id':customer_id})
        if row is None:
            raise HTTPException(404,'Customer not found')
        return row

    @app.get('/health')
    def health():
        return {'status':'ok'}

    @app.get('/ready')
    def ready(request:Request):
        if not request.app.state.database.ready():
            raise HTTPException(503,'Customer data unavailable; retry later')
        return {'status':'ready'}

    @app.get('/v1/customers/{customer_id}')
    def get_customer(request:Request, customer_id:Annotated[str,Depends(authorize)]):
        return customer_exists(request.app.state.database,customer_id)

    def list_records(db,customer_id,kind,limit,offset,status):
        customer_exists(db,customer_id)
        # Identifiers are from these fixed source-code branches; inputs are bound values.
        columns = 'id,customer_id,total_cents,status,created_at' if kind=='orders' else 'id,customer_id,order_id,total_cents,status,due_date'
        sql = f'SELECT {columns} FROM {kind} WHERE customer_id=:customer_id'
        params = dict(customer_id=customer_id,limit=limit,offset=offset)
        if status is not None:
            sql += ' AND status=:status'
            params['status'] = status.value
        sql += ' ORDER BY id LIMIT :limit OFFSET :offset'
        items = db.fetch_all(sql,params)
        return dict(items=items,count=len(items),limit=limit,offset=offset)

    @app.get('/v1/customers/{customer_id}/orders')
    def orders(request:Request, customer_id:Annotated[str,Depends(authorize)], limit:Limit=10,
               offset:Offset=0,status:OrderStatus|None=None):
        return list_records(request.app.state.database,customer_id,'orders',limit,offset,status)

    @app.get('/v1/customers/{customer_id}/invoices')
    def invoices(request:Request, customer_id:Annotated[str,Depends(authorize)], limit:Limit=10,
                 offset:Offset=0,status:InvoiceStatus|None=None):
        return list_records(request.app.state.database,customer_id,'invoices',limit,offset,status)

    @app.get('/v1/customers/{customer_id}/summary')
    def summary(request:Request, customer_id:Annotated[str,Depends(authorize)]):
        db = request.app.state.database
        customer_exists(db,customer_id)
        result = db.fetch_one('''SELECT
          (SELECT COUNT(*) FROM orders WHERE customer_id=:customer_id) AS order_count,
          (SELECT COUNT(*) FROM invoices WHERE customer_id=:customer_id) AS invoice_count,
          (SELECT COALESCE(SUM(total_cents),0) FROM invoices WHERE customer_id=:customer_id AND status != 'paid') AS outstanding_cents''',
          {'customer_id':customer_id})
        return dict(customer_id=customer_id,**result)

    return app


app = create_app()
