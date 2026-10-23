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
| kind deployment and proxy smoke locally | Not run locally; verified separately in CI below |

`local-pytest.xml` records the local Python run. The TypeScript HTTP run used the SQLite sandbox; it is not PostgreSQL evidence. There is no model API call or paid provider usage.

## Failures and fixes

- FastAPI's TestClient initially hung in the restricted Windows sandbox because its event loop could not create a loopback socket. Re-running the test process with loopback access passed. This was an execution-environment failure, not a bypassed API assertion.
- Two initial TypeScript HTTP attempts produced 39 passes and 1 E2E failure because loopback connections to the sandbox server were blocked. Starting the server and running the tests with loopback access gave 40 passes. No mock response replaced the HTTP request.
- The initial editable installation could not write to the sandbox's temporary build directory. Installation using the permitted runtime completed successfully.
- PostgreSQL read-only defaults can report a read-only-transaction error before checking table privileges. The permission tests explicitly request a write transaction before trying INSERT, UPDATE and DELETE. This separates the actual SELECT-only grant from its read-only default.
- Review found that reusing an existing reader role could preserve old write grants. Bootstrap now revokes direct table and schema privileges before granting SELECT and rejects elevated/member/owner roles. A new PostgreSQL regression deliberately grants INSERT and schema CREATE, reruns bootstrap and verifies that both grants are removed. It passed against real PostgreSQL in the final CI run.

## Remote evidence

The [initial CI run 40033163701](https://github.com/hamza2829/ai-agent-api-k8s/actions/runs/40033163701) passed at commit `d6e427d`: 40 Python tests, 40 TypeScript tests and 8/8 kind proxy smoke checks. PostgreSQL and actual HTTP were used in the test job. The image built and API, PostgreSQL and nginx all reached 1/1 ready with zero restarts. The 24-request burst returned 4 responses with HTTP 200 and 20 with HTTP 429.

One nginx readiness probe returned 502 while the API was still starting, then recovered to 200. Deployment readiness waited for recovery; no container restart was required. This did not fail the smoke test, which ran after rollout readiness.

## Final security-regression run

[CI run 40033618850](https://github.com/hamza2829/ai-agent-api-k8s/actions/runs/40033618850) succeeded at implementation commit `5eaddcb`. It adds the safe request-ID and reused-role regressions, taking the Python suite to 42. Actual results:

| Check | Observed |
| --- | --- |
| Python | 42 passed, 0 failed/errors, 0 skipped |
| TypeScript | 40 passed, 0 failed, 0 skipped |
| kind proxy smoke | 8 passed, 0 failed |
| Authenticated order response | 200, all 3 expected rows belong to cus_001 |
| Missing key / forbidden customer / bad input | 401 / 403 / 422 |
| Health and database readiness | 200 / 200 |
| Proxy rate-limit burst | 24 requests, 4 accepted and 20 HTTP 429 |
| Security headers | Present on success and 401 response |
| API / nginx / PostgreSQL | Each 1/1 ready, zero restarts |
| Migration Job | Completed |
| Initial startup 502 in final run | None |

The tests job took 42 seconds; the kind job took 1 minute 57 seconds. All 13 requests forwarded by nginx matched API request IDs in the collected logs; other API log events were direct pod probes. No CI tests or smoke checks failed in either completed run. Expected 401, 403, 422 and 429 responses are passing rejection checks, not hidden errors.

Evidence: [test artifact](https://github.com/hamza2829/ai-agent-api-k8s/actions/runs/40033618850/artifacts/12536276380), [smoke and cluster logs](https://github.com/hamza2829/ai-agent-api-k8s/actions/runs/40033618850/artifacts/12536840092). GitHub artifact retention is 14 days. Summarized JSON copies are retained under [results/](results). The hosted kind cluster was deleted after the workflow. There is no ongoing public API deployment and no paid model was called.
