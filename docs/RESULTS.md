# Measured results

## Local verification

Windows, Python 3.12.14, Node 22. No local Docker was used.

| Check | Actual result |
| --- | --- |
| Python unit and SQLite API tests | 34 passed |
| Real PostgreSQL checks locally | 6 explicitly skipped, no local server configured |
| TypeScript unit and actual HTTP scripted-agent tests | 40 passed, 0 skipped |
| Scripted model demo | Returned ord_001 and ord_002 from the real local FastAPI SQLite sandbox |
| Kustomize rendering | Successful, no Kubernetes server or local Docker needed |
| kind deployment and proxy smoke | Pending remote CI |

`local-pytest.xml` records the local Python run. The TypeScript HTTP run used the SQLite sandbox; it is not PostgreSQL evidence. There is no model API call or paid provider usage.

## Failures and fixes

- FastAPI's TestClient initially hung in the restricted Windows sandbox because its event loop could not create a loopback socket. Re-running the test process with loopback access passed. This was an execution-environment failure, not a bypassed API assertion.
- Two initial TypeScript HTTP attempts produced 39 passes and 1 E2E failure because loopback connections to the sandbox server were blocked. Starting the server and running the tests with loopback access gave 40 passes. No mock response replaced the HTTP request.
- The initial editable installation could not write to the sandbox's temporary build directory. Installation using the permitted runtime completed successfully.
- PostgreSQL read-only defaults can report a read-only-transaction error before checking table privileges. The permission tests explicitly request a write transaction before trying INSERT, UPDATE and DELETE. This separates the actual SELECT-only grant from its read-only default.

## Remote evidence

No remote result is claimed until GitHub Actions completes. The workflow collects Python XML, TypeScript logs, API request logs, smoke JSON and cluster diagnostics. The final README will link the actual run and artifact evidence.
