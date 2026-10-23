# Measured results

## Local verification

Windows, Python 3.12.14, Node 22. No local Docker was used.

| Check | Actual result |
| --- | --- |
| Python unit and SQLite API tests | 35 passed |
| Real PostgreSQL checks locally | 7 explicitly skipped, no local server configured |
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
- Review found that reusing an existing reader role could preserve old write grants. Bootstrap now revokes direct table privileges before granting SELECT and rejects elevated/member/owner roles. A new PostgreSQL regression deliberately grants INSERT, reruns bootstrap and verifies that the grant is removed. Its result will be recorded from CI.

## Remote evidence

The [initial CI run 40033163701](https://github.com/hamza2829/ai-agent-api-k8s/actions/runs/40033163701) passed at commit `d6e427d`: 40 Python tests, 40 TypeScript tests and 8/8 kind proxy smoke checks. PostgreSQL and actual HTTP were used in the test job. The image built and API, PostgreSQL and nginx all reached 1/1 ready with zero restarts. The 24-request burst returned 4 responses with HTTP 200 and 20 with HTTP 429.

One nginx readiness probe returned 502 while the API was still starting, then recovered to 200. Deployment readiness waited for recovery; no container restart was required. This did not fail the smoke test, which ran after rollout readiness.

The final security regression update adds two tests, taking the Python suite to 42. Its remote result is pending the next run. The workflow collects Python XML, TypeScript logs, API request logs, smoke JSON and cluster diagnostics. Final verification will link that tested commit and run separately.
