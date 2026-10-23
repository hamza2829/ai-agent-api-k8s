# Ordered setup and screenshot guide

Use the fake data only. Local Docker is not required. The image build and kind cluster run on the GitHub-hosted runner. Screenshot names below are a checklist, not a claim that you have captured them.

## 1. Open and install the project

Open `ai-agent-api-k8s` in your editor. In its root directory run:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
npm ci --prefix agent
```

Use Node 22. On Linux/macOS use `python3.12` to create the environment and `.venv/bin/python` afterward. No virtual-environment activation is required when calling the full executable path.

**Screenshot:** `01-install.png`, showing successful installation and the project folders.

## 2. Run Python tests without Docker

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-temp
```

Without TEST_DATABASE_URL the 7 actual PostgreSQL tests are skipped explicitly. The SQLite tests cover API behavior, not PostgreSQL roles. The current local result is 35 passed and 7 skipped. A restricted terminal may require loopback access for FastAPI TestClient.

**Screenshot:** `02-pytest-local.png`, including counts, skips and any failures.

## 3. Start the local fake-data sandbox

Terminal 1:

```powershell
$env:API_KEY = "demo-only-key-change-me-123456"
.\.venv\Scripts\python.exe -m uvicorn agent_api.local_demo:app --host 127.0.0.1 --port 8080 --no-access-log
```

Leave it running. It uses a fresh in-memory SQLite fixture. This local path requires no PostgreSQL or Docker.

**Screenshot:** `03-local-api.png`, showing startup and a redacted JSON request-log line after the next step.

## 4. Make an allowed and rejected call

Terminal 2:

```powershell
curl.exe -i http://127.0.0.1:8080/health
curl.exe -i -H "X-API-Key: demo-only-key-change-me-123456" http://127.0.0.1:8080/v1/customers/cus_001/orders
curl.exe -i http://127.0.0.1:8080/v1/customers/cus_001/orders
curl.exe -i -H "X-API-Key: demo-only-key-change-me-123456" http://127.0.0.1:8080/v1/customers/cus_002/orders
curl.exe -i -H "X-API-Key: demo-only-key-change-me-123456" "http://127.0.0.1:8080/v1/customers/cus_001/orders?limit=0"
```

Expected status codes: 200, 200, 401, 403 and 422. On Linux/macOS use `curl` instead of `curl.exe`. The displayed key is intentionally public and only for this fake-data demo.

**Screenshot:** `04-allowed-denied.png`, showing one successful response and the three rejected calls. Do not replace an unexpected response with the expected value.

## 5. Run the scripted agent

Keep terminal 1 running. In terminal 2:

```powershell
$env:API_BASE_URL = "http://127.0.0.1:8080"
$env:API_KEY = "demo-only-key-change-me-123456"
npm run demo --prefix agent
npm test --prefix agent
```

The model mock requests list_orders for cus_001 with limit 2. It receives ord_001 and ord_002 from an actual HTTP request. All 40 tests should pass when the service is reachable. Without API_BASE_URL the E2E test is skipped, so the expected result is 39 passes and 1 skip. The mock is scripted, not an AI accuracy evaluation.

**Screenshot:** `05-scripted-agent.png`, with the selected tool, returned fake IDs and test totals.

## 6. Inspect schemas and migrations

Open `agent/src/tool-schemas.json`, `migrations/001_schema.sql` and `src/agent_api/migrate.py`. Confirm four read-only functions, strict allowed arguments, SQL foreign keys, migration checksums and SELECT-only reader grants. Optional: `npm run schemas --prefix agent` prints the tool schema.

If a disposable PostgreSQL server is already available locally, initialize it from the project root:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://postgres:<your-owner-password>@127.0.0.1:5432/customer_demo"
$env:READ_DB_PASSWORD = "<your-demo-reader-password>"
.\.venv\Scripts\python.exe -m agent_api.migrate --demo-bootstrap
```

Replace placeholders. The database must exist first. After migration run the API with the `agent_reader` connection, not the owner connection. You can skip this local PostgreSQL setup: CI provisions and checks the real server automatically.

**Screenshot:** `06-read-only-design.png`, showing a tool definition and the database reader grants.

## 7. Inspect Kubernetes and nginx

Open `deploy/api.yaml`, `deploy/nginx.conf` and `deploy/secret.demo.yaml`. Confirm probes, resource limits, ClusterIP backend, NodePort proxy, rate limit and security headers. The Secret is a published fake example. Do not put real keys into this committed file.

If kubectl is installed, `kubectl kustomize deploy` renders the manifests without Docker or a cluster. Otherwise inspect the YAML and leave deployment to CI.

**Screenshot:** `07-deployment-config.png`, showing probes/resource limits and the nginx rate-limit/header directives.

## 8. Open the GitHub repository and CI run

The intended repository is [hamza2829/ai-agent-api-k8s](https://github.com/hamza2829/ai-agent-api-k8s). Open **Actions** > **CI** > the latest run. A push starts it automatically; **Run workflow** starts another run manually.

The first job starts real PostgreSQL, applies migrations, runs all Python tests and runs the scripted agent against an HTTP API using the read-only account. The second job builds the image and creates kind on the hosted runner, then applies the manifests and waits for readiness.

**Screenshot:** `08-ci-jobs.png`, showing the real run URL and both job conclusions.

## 9. Inspect the proxy smoke results

Open the step **Smoke test through nginx, including denied calls and rate limiting**. It checks health, readiness, authenticated read, missing-key rejection, out-of-scope rejection, bad-input rejection, security headers and a burst producing 429. These requests go through nginx in the deployed cluster, not FastAPI TestClient.

Download **kind-smoke-logs** from the run's **Artifacts** section and open `smoke.json` plus the API/nginx logs. The workflow collects pod and event diagnostics even if deployment fails. Inspect **test-results** for the Python XML and TypeScript log.

**Screenshot:** `09-proxy-smoke.png`, showing actual passed/failed totals and observed statuses, including 429. **Screenshot:** `10-cluster-logs.png`, showing real pod readiness and redacted request logs. Do not screenshot a Secret dump.

## 10. Review the final evidence

Read `docs/RESULTS.md` and README. Keep initial failed runs and their causes in the results history. Use actual test counts and smoke outcomes. The badge reflects the current remote workflow. A green badge does not establish production readiness, TLS or model safety.

**Screenshot:** `11-readme-results.png`, showing the badge, real measured table and limitations. Save genuine captures to `docs/screenshots/` when taken. Stop the local server with Ctrl+C after testing.
