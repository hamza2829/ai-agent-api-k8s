import type { ToolResult } from "./tools.js";

type Execute = (name: unknown, args: unknown) => Promise<ToolResult>;

/** A deterministic model replacement. No model API, token, or natural-language understanding is used. */
export class ScriptedModel {
  plan(question: string): { name: string; arguments: Record<string, unknown> } {
    if (question !== "Show two orders for cus_001.") {
      throw new Error("The scripted model only supports its one demonstration question.");
    }
    return { name: "list_orders", arguments: { customer_id: "cus_001", limit: 2 } };
  }

  answer(result: ToolResult): string {
    if (!result.ok) return `Cannot answer: ${result.error.code}. ${result.error.message}`;
    const data = result.data;
    if (typeof data !== "object" || data === null || !("items" in data) || !Array.isArray(data.items)) {
      throw new Error("The orders tool returned an unexpected response shape.");
    }
    const ids = data.items.map((order: unknown): string => {
      if (typeof order !== "object" || order === null || !("id" in order) || typeof order.id !== "string") {
        throw new Error("An order did not contain an id.");
      }
      return order.id;
    });
    return `Found ${ids.length} fake orders for cus_001: ${ids.join(", ")}.`;
  }
}

export async function runScriptedAgent(execute: Execute): Promise<{ call: ReturnType<ScriptedModel["plan"]>; result: ToolResult; answer: string }> {
  const model = new ScriptedModel();
  const call = model.plan("Show two orders for cus_001.");
  const result = await execute(call.name, call.arguments);
  return { call, result, answer: model.answer(result) };
}
