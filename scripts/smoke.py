"""Exercise the deployed nginx proxy. No model API and no third-party client needed."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--output", type=Path, default=Path("artifacts/smoke.json"))
    args = parser.parse_args()
    api_key = os.environ.get("API_KEY")
    if not api_key:
        parser.error("Set API_KEY in the environment. It is never written to the report.")
    base = args.base_url.rstrip("/")
    results: list[dict] = []

    def request(path: str, authenticated: bool = True) -> tuple[int, dict, object]:
        headers = {"Accept": "application/json"}
        if authenticated:
            headers["X-API-Key"] = api_key
        try:
            response = urlopen(Request(base + path, headers=headers), timeout=10)
        except HTTPError as error:
            response = error
        with response:
            content = response.read().decode("utf-8")
            try:
                body = json.loads(content)
            except json.JSONDecodeError:
                body = content[:300]
            return response.status, dict(response.headers.items()), body

    def check(name: str, condition: bool, detail: object) -> None:
        results.append({"check": name, "passed": bool(condition), "detail": detail})
        print(f"{'PASS' if condition else 'FAIL'} {name}: {detail}")

    try:
        status, headers, body = request("/health", authenticated=False)
        check("health", status == 200 and body == {"status": "ok"}, {"status": status})
        status, _, _ = request("/ready", authenticated=False)
        check("database_readiness", status == 200, {"status": status})
        status, _, body = request("/v1/customers/cus_001/orders")
        valid_orders = (isinstance(body,dict) and isinstance(body.get('items'),list)
                        and len(body['items']) == 3 and body['items'][0].get('id') == 'ord_001'
                        and all(row.get('customer_id') == 'cus_001' for row in body['items']))
        check("authenticated_orders", status == 200 and valid_orders, {"status": status, "expected_rows":3})
        time.sleep(1.1)
        status, rejected_headers, _ = request("/v1/customers/cus_001/orders", authenticated=False)
        check("missing_key_rejected", status == 401, {"status": status})
        time.sleep(1.1)
        status, _, _ = request("/v1/customers/cus_002/orders")
        check("customer_scope_rejected", status == 403, {"status": status})
        time.sleep(1.1)
        status, _, _ = request("/v1/customers/cus_001/orders?limit=0")
        check("bad_input_rejected", status == 422, {"status": status})
        expected_headers = {
            "x-content-type-options": "nosniff",
            "x-frame-options": "DENY",
            "referrer-policy": "no-referrer",
            "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
        }
        normal = {key.lower(): value for key, value in headers.items()}
        rejected = {key.lower(): value for key, value in rejected_headers.items()}
        valid = all(normal.get(key) == value and rejected.get(key) == value for key, value in expected_headers.items())
        valid = valid and bool(normal.get("x-request-id")) and bool(rejected.get("x-request-id"))
        check("security_headers_on_success_and_error", valid, {"checked_headers": [*expected_headers, "x-request-id"]})
        time.sleep(4.1)  # Let nginx's small burst budget drain before the burst.
        with ThreadPoolExecutor(max_workers=24) as pool:
            statuses = list(pool.map(lambda _: request("/v1/customers/cus_001/orders")[0], range(24)))
        counts = {str(code): statuses.count(code) for code in sorted(set(statuses))}
        check("proxy_rate_limit", 429 in statuses and all(code in (200, 429) for code in statuses), counts)
    except (URLError, TimeoutError, OSError) as error:
        check("proxy_connection", False, str(error))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base,
        "passed": sum(item["passed"] for item in results),
        "failed": sum(not item["passed"] for item in results),
        "checks": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['passed']}/{len(results)} checks passed; report: {args.output}")
    return 0 if report["failed"] == 0 and len(results) == 8 else 1


if __name__ == "__main__":
    raise SystemExit(main())
