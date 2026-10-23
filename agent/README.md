# Read-only agent tools

This is a function-calling boundary with a scripted model replacement. It does not use an LLM or understand arbitrary questions. The deterministic model chooses a tool, the executor calls the real API, and the model replacement formats the response. No paid API is needed.

The provider-neutral schemas are in [`src/tool-schemas.json`](src/tool-schemas.json). The application can expose four tools: `get_customer`, `list_orders`, `list_invoices`, and `customer_summary`. The executor constructs fixed GET URLs from validated arguments. There is no URL, HTTP method, credential, SQL, or write parameter for a model to control. Authentication and customer scope are enforced by FastAPI as well.

Requires Node.js 22. From this folder:

```powershell
npm ci
npm test
```

The real HTTP test is explicitly skipped when `API_BASE_URL` is absent. Unit tests use a mocked HTTP transport. To include the real API test, first start the SQLite sandbox or PostgreSQL-backed FastAPI service using the root instructions. CI uses PostgreSQL. Then:

```powershell
$env:API_BASE_URL = "http://127.0.0.1:8080"
$env:API_KEY = "demo-only-key-change-me-123456"
npm test
npm run demo
```

The example key is deliberately public and is only for fake portfolio data. Use an operator-controlled environment variable for other credentials. The configured credential is scoped to `cus_001`. The E2E test also confirms that `cus_002` is forbidden.

The demo should return:

```text
Found 2 fake orders for cus_001: ord_001, ord_002.
```

`npm run schemas` prints the JSON schemas. No provider SDK or MCP transport is included. A real model integration would need its own tool-selection loop, identity-to-scope mapping, output handling, and evaluation. Schema validation and fixed GET endpoints reduce the actions the caller can request. They are not proof that an LLM is immune to prompt injection.
