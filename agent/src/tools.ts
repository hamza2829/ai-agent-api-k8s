import schemas from "./tool-schemas.json" with { type: "json" };

export const TOOL_SCHEMAS = schemas;
const TOOL_NAMES = ["get_customer", "list_orders", "list_invoices", "customer_summary"] as const;
export type ToolName = typeof TOOL_NAMES[number];
export type ToolResult =
  | { ok: true; data: unknown }
  | { ok: false; error: { code: string; message: string; retry_after_seconds?: number } };
export interface ExecutorConfig {
  apiBaseUrl: string;
  apiKey: string;
  fetchImpl?: typeof fetch;
}

type Arguments = { customer_id: string; limit?: number; status?: string };

function failure(code: string, message: string): ToolResult {
  return { ok: false, error: { code, message } };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value) &&
    [Object.prototype, null].includes(Object.getPrototypeOf(value) as object | null);
}

function validate(name: ToolName, value: unknown): Arguments | string {
  if (!isRecord(value)) return "Arguments must be a JSON object.";
  const list = name === "list_orders" || name === "list_invoices";
  const permitted = list ? ["customer_id", "limit", "status"] : ["customer_id"];
  if (Object.keys(value).some(key => !permitted.includes(key))) {
    return `Only these arguments are accepted: ${permitted.join(", ")}.`;
  }
  if (!Object.hasOwn(value, "customer_id") || typeof value.customer_id !== "string" || !/^cus_[0-9]{3}$/.test(value.customer_id)) {
    return "customer_id must match cus_ followed by exactly three digits.";
  }
  if (Object.hasOwn(value, "limit") &&
      (typeof value.limit !== "number" || !Number.isInteger(value.limit) || value.limit < 1 || value.limit > 20)) {
    return "limit must be an integer from 1 to 20.";
  }
  const statuses = name === "list_orders" ? ["pending", "shipped", "cancelled"] : ["open", "paid", "overdue"];
  if (Object.hasOwn(value, "status") && (typeof value.status !== "string" || !statuses.includes(value.status))) {
    return `status must be one of: ${statuses.join(", ")}.`;
  }
  return {
    customer_id: value.customer_id,
    ...(typeof value.limit === "number" ? { limit: value.limit } : {}),
    ...(typeof value.status === "string" ? { status: value.status } : {}),
  };
}

/** The application supplies credentials. A model can supply only a tool name and validated arguments. */
export function createExecutor(config: ExecutorConfig): (name: unknown, args: unknown) => Promise<ToolResult> {
  const base = new URL(config.apiBaseUrl);
  if (!["http:", "https:"].includes(base.protocol) || base.username || base.password ||
      base.search || base.hash || base.pathname !== "/") {
    throw new Error("API_BASE_URL must be an HTTP(S) origin without credentials, path, query, or fragment.");
  }
  if (!config.apiKey || /[\r\n]/.test(config.apiKey)) throw new Error("API_KEY is required and must not contain line breaks.");
  const fetchImpl = config.fetchImpl ?? fetch;

  return async (name: unknown, args: unknown): Promise<ToolResult> => {
    if (typeof name !== "string" || !TOOL_NAMES.includes(name as ToolName)) {
      return failure("unknown_tool", "Unknown tool. Available tools: get_customer, list_orders, list_invoices, customer_summary. All are read only.");
    }
    const toolName = name as ToolName;
    const checked = validate(toolName, args);
    if (typeof checked === "string") return failure("invalid_arguments", checked);
    const suffix = {
      get_customer: "",
      list_orders: "/orders",
      list_invoices: "/invoices",
      customer_summary: "/summary",
    }[toolName];
    const url = new URL(`/v1/customers/${checked.customer_id}${suffix}`, base);
    if (toolName === "list_orders" || toolName === "list_invoices") {
      url.searchParams.set("limit", String(checked.limit ?? 10));
      if (checked.status) url.searchParams.set("status", checked.status);
    }
    try {
      const response = await fetchImpl(url, {
        method: "GET",
        headers: { "Accept": "application/json", "X-API-Key": config.apiKey },
        redirect: "error",
        signal: AbortSignal.timeout(3000),
      });
      if (!response.ok) {
        const errors: Record<number, [string, string]> = {
          401: ["unauthorized", "API authentication failed. Ask the application operator to configure its API key."],
          403: ["forbidden", "The configured credential cannot read this customer."],
          404: ["not_found", "The requested customer or resource does not exist."],
          422: ["invalid_request", "The API rejected the request parameters."],
          429: ["rate_limited", "Too many requests. Wait before retrying."],
          503: ["unavailable", "The service or its database is unavailable."],
        };
        const [code, message] = errors[response.status] ?? ["unavailable", "The service returned an unexpected error."];
        const result = failure(code, message);
        const retry = response.headers.get("Retry-After");
        if (!result.ok && response.status === 429 && retry && /^\d+$/.test(retry)) {
          result.error.retry_after_seconds = Number(retry);
        }
        return result;
      }
      try {
        return { ok: true, data: await response.json() as unknown };
      } catch {
        return failure("invalid_response", "The service did not return valid JSON.");
      }
    } catch (error: unknown) {
      if (error instanceof Error && ["TimeoutError", "AbortError"].includes(error.name)) {
        return failure("timeout", "The API request timed out after 3 seconds.");
      }
      // Do not echo network exceptions, request headers, or server error bodies to a model.
      return failure("unavailable", "The service could not be reached. Check the application configuration.");
    }
  };
}

export function executorFromEnvironment(): ReturnType<typeof createExecutor> {
  if (!process.env.API_BASE_URL || !process.env.API_KEY) {
    throw new Error("Set API_BASE_URL and API_KEY in the application environment before running the demo.");
  }
  return createExecutor({ apiBaseUrl: process.env.API_BASE_URL, apiKey: process.env.API_KEY });
}
