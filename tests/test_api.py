import json
import logging
import uuid
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from agent_api.main import create_app


def test_health_and_ready_do_not_require_a_key(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").status_code == 200


@pytest.mark.parametrize("path", ["/ready", "/v1/customers/cus_001/orders"])
def test_database_failure_is_sanitized_and_liveness_remains_healthy(client, database, auth_headers, monkeypatch, path):
    def unavailable(*args, **kwargs):
        raise SQLAlchemyError("connection failed: password=never-expose-this")

    monkeypatch.setattr(database, "fetch_all", unavailable)
    response = client.get(path, headers=auth_headers)
    assert response.status_code == 503
    assert response.json() == {"detail": "Customer data unavailable; retry later"}
    assert "never-expose-this" not in response.text
    assert client.get("/health").status_code == 200


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "incorrect-secret"}])
def test_missing_or_wrong_authentication_is_rejected(client, headers):
    response = client.get("/v1/customers/cus_001/orders", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "ApiKey"
    assert "detail" in response.json()


@pytest.mark.parametrize("suffix", ["", "/orders", "/invoices", "/summary"])
def test_customer_scope_applies_to_every_data_endpoint(client, auth_headers, suffix):
    response = client.get(f"/v1/customers/cus_002{suffix}", headers=auth_headers)
    assert response.status_code == 403
    assert "items" not in response.json()


@pytest.mark.parametrize("customer_id", ["not-a-customer", "cus_001' OR '1'='1"])
def test_invalid_customer_id_including_sql_injection_is_rejected(client, auth_headers, customer_id):
    response = client.get(f"/v1/customers/{customer_id}/orders", headers=auth_headers)
    assert response.status_code == 422


def test_customer_endpoint_has_no_other_customers(client, auth_headers):
    response = client.get("/v1/customers/cus_001", headers=auth_headers)
    assert response.status_code == 200
    customer = response.json()
    assert customer["id"] == "cus_001"
    assert customer["name"]
    assert customer["tier"]


@pytest.mark.parametrize("resource", ["orders", "invoices"])
def test_list_results_are_scoped_and_paginated(client, auth_headers, resource):
    path = f"/v1/customers/cus_001/{resource}"
    all_items = client.get(path, headers=auth_headers).json()
    assert all_items["count"] == 3
    assert all(item["customer_id"] == "cus_001" for item in all_items["items"])
    assert all(isinstance(item["total_cents"], int) for item in all_items["items"])
    page = client.get(path, params={"limit": 1, "offset": 1}, headers=auth_headers).json()
    assert page["limit"] == 1
    assert page["offset"] == 1
    assert page["count"] == 1
    assert page["items"] == all_items["items"][1:2]
    empty = client.get(path, params={"offset": 999}, headers=auth_headers).json()
    assert empty["items"] == []
    assert empty["count"] == 0


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 21}, {"offset": -1}, {"offset": 1001}, {"limit": "many"}],
)
def test_bad_pagination_is_rejected(client, auth_headers, params):
    response = client.get("/v1/customers/cus_001/orders", params=params, headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("resource", "status"),
    [("orders", "shipped"), ("invoices", "overdue")],
)
def test_status_filters_return_only_matching_items(client, auth_headers, resource, status):
    response = client.get(
        f"/v1/customers/cus_001/{resource}", params={"status": status}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["items"]
    assert all(item["status"] == status for item in response.json()["items"])


@pytest.mark.parametrize("resource", ["orders", "invoices"])
def test_unknown_status_is_rejected(client, auth_headers, resource):
    response = client.get(
        f"/v1/customers/cus_001/{resource}", params={"status": "deleted"}, headers=auth_headers
    )
    assert response.status_code == 422


def test_summary_matches_scoped_read_data(client, auth_headers):
    base = "/v1/customers/cus_001"
    orders = client.get(f"{base}/orders", headers=auth_headers).json()["items"]
    invoices = client.get(f"{base}/invoices", headers=auth_headers).json()["items"]
    response = client.get(f"{base}/summary", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {
        "customer_id": "cus_001",
        "order_count": len(orders),
        "invoice_count": len(invoices),
        "outstanding_cents": sum(row["total_cents"] for row in invoices if row["status"] != "paid"),
    }


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_data_routes_have_no_write_methods(client, auth_headers, method):
    response = getattr(client, method)("/v1/customers/cus_001/orders", headers=auth_headers)
    assert response.status_code == 405


def test_request_id_is_generated_and_not_taken_from_untrusted_header(client, auth_headers):
    headers = {**auth_headers, "X-Request-ID": "untrusted request id"}
    response = client.get("/v1/customers/cus_001/orders", headers=headers)
    request_id = response.headers["x-request-id"]
    assert uuid.UUID(request_id).version == 4
    assert request_id != headers["X-Request-ID"]


def test_request_log_omits_api_key_and_query_values(client, auth_headers, caplog):
    caplog.set_level(logging.INFO)
    response = client.get(
        "/v1/customers/cus_001/orders?private_note=do-not-log-this", headers=auth_headers
    )
    assert response.status_code == 200
    messages = [record.getMessage() for record in caplog.records]
    assert auth_headers["X-API-Key"] not in "\n".join(messages)
    # Only structured application request logs are checked, because httpx also logs full URLs.
    request_logs = []
    for message in messages:
        try:
            entry = json.loads(message)
        except (ValueError, TypeError):
            continue
        if isinstance(entry, dict) and "method" in entry and "path" in entry:
            request_logs.append(entry)
    assert request_logs, "No structured request log was emitted"
    entry = request_logs[-1]
    assert "do-not-log-this" not in json.dumps(entry)
    assert "private_note" not in json.dumps(entry)
    assert entry["method"] == "GET"
    assert entry["status"] == 200
    assert entry["duration_ms"] >= 0
    assert entry["request_id"] == response.headers["x-request-id"]


def test_api_rate_limit_and_health_exemption(settings, database, auth_headers):
    settings = replace(settings, rate_limit=3)
    app = create_app(settings=settings, database=database)
    with TestClient(app) as client:
        for _ in range(3):
            assert client.get("/v1/customers/cus_001", headers=auth_headers).status_code == 200
        rejected = client.get("/v1/customers/cus_001", headers=auth_headers)
        assert rejected.status_code == 429
        assert int(rejected.headers["retry-after"]) >= 1
        assert "detail" in rejected.json()
        assert client.get("/health").status_code == 200


def test_invalid_credentials_do_not_consume_valid_key_quota(settings, database, auth_headers):
    settings = replace(settings, rate_limit=1)
    app = create_app(settings=settings, database=database)
    with TestClient(app) as client:
        for _ in range(3):
            assert client.get("/v1/customers/cus_001").status_code == 401
        assert client.get("/v1/customers/cus_001", headers=auth_headers).status_code == 200
