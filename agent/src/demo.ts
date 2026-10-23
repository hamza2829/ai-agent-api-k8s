import { executorFromEnvironment } from "./tools.js";
import { runScriptedAgent } from "./scripted-agent.js";

try {
  const { call, result, answer } = await runScriptedAgent(executorFromEnvironment());
  console.log(JSON.stringify({ mode: "scripted model, real HTTP API", call, result, answer }, null, 2));
  if (!result.ok) process.exitCode = 1;
} catch (error: unknown) {
  console.error(error instanceof Error ? error.message : "Demo failed.");
  process.exitCode = 1;
}
