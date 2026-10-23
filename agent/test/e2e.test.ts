import assert from "node:assert/strict";
import test from "node:test";
import { executorFromEnvironment } from "../src/tools.js";
import { runScriptedAgent } from "../src/scripted-agent.js";

test("scripted agent calls real FastAPI HTTP and summarizes two seeded orders", {
  skip: !process.env.API_BASE_URL ? "Set API_BASE_URL and API_KEY to run against the real service; CI runs this test with PostgreSQL." : false,
}, async () => {
  const execute = executorFromEnvironment();
  const run = await runScriptedAgent(execute);
  assert.equal(run.result.ok, true, "The service must return a successful orders response.");
  assert.equal(run.call.name, "list_orders");
  assert.deepEqual(run.call.arguments, { customer_id: "cus_001", limit: 2 });
  assert.equal(run.answer, "Found 2 fake orders for cus_001: ord_001, ord_002.");
  if (run.result.ok) {
    const data = run.result.data as { items: { id: string; customer_id: string; total_cents: number }[]; count: number };
    assert.equal(data.items.length, 2);
    assert.equal(data.items[0]!.id, "ord_001");
    assert.equal(data.items[0]!.customer_id, "cus_001");
    assert.equal(data.items[0]!.total_cents, 12900);
  }
  const denied = await execute("get_customer", { customer_id: "cus_002" });
  assert.equal(denied.ok, false);
  if (!denied.ok) assert.equal(denied.error.code, "forbidden");
  assert.equal(JSON.stringify(run.call).includes(process.env.API_KEY!), false);
});
