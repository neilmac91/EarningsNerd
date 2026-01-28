# Code Mode Reference

Code Mode is an experimental feature that generates executable JavaScript to orchestrate multiple tools, replacing individual tool calls with unified code execution.

## Overview

Traditional tool calling requires one LLM request per tool call, leading to high token consumption for complex workflows. Code Mode addresses this by having the LLM generate code that orchestrates multiple tools in a single execution.

### Benefits
- **Reduced tokens** - Single generation for complex workflows
- **Self-debugging** - Generated code includes error recovery
- **Efficiency** - Execute multiple tools without round-trips

## Configuration

### Wrangler Setup

```jsonc
{
  "name": "codemode-agent",
  "main": "src/index.ts",
  "durable_objects": {
    "bindings": [
      { "name": "MY_AGENT", "class_name": "MyAgent" }
    ]
  },
  "migrations": [
    { "tag": "v1", "new_sqlite_classes": ["MyAgent"] }
  ],
  "services": [
    { "binding": "GLOBAL_OUTBOUND", "service": "global-outbound" },
    { "binding": "CODEMODE_PROXY", "service": "codemode-proxy" }
  ]
}
```

### Dependencies

```bash
npm install @cloudflare/codemode ai @ai-sdk/openai zod
```

## Implementation

### Export CodeModeProxy

```typescript
import { CodeModeProxy } from "@cloudflare/codemode";

// Must be exported from your worker
export { CodeModeProxy };
```

### Define Tool Router

```typescript
import { Agent } from "@cloudflare/agents";

export class MyAgent extends Agent<Env, State> {
  async callTool(name: string, args: unknown): Promise<unknown> {
    switch (name) {
      case "getWeather":
        return this.getWeather(args as { city: string });
      case "sendEmail":
        return this.sendEmail(args as { to: string; subject: string; body: string });
      case "searchDatabase":
        return this.searchDatabase(args as { query: string });
      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  }

  private async getWeather(args: { city: string }) {
    const response = await fetch(`https://api.weather.com/v1/current?city=${args.city}`);
    return response.json();
  }

  private async sendEmail(args: { to: string; subject: string; body: string }) {
    // Email implementation
    return { sent: true, timestamp: new Date().toISOString() };
  }

  private async searchDatabase(args: { query: string }) {
    // Database search implementation
    return this.sql`SELECT * FROM items WHERE name LIKE ${`%${args.query}%`}`;
  }
}
```

## Example Workflow

When a user requests: "Check the weather in San Francisco and email me if it's going to rain"

**Without Code Mode** (3 LLM calls):
1. LLM decides to call getWeather
2. LLM receives weather data, decides to check for rain
3. LLM decides to call sendEmail

**With Code Mode** (1 LLM call):
```javascript
// Generated code
const weather = await callTool("getWeather", { city: "San Francisco" });
if (weather.forecast.includes("rain")) {
  await callTool("sendEmail", {
    to: "user@example.com",
    subject: "Rain Alert",
    body: `Rain expected in San Francisco: ${weather.description}`
  });
}
return { checked: true, willRain: weather.forecast.includes("rain") };
```

## When to Use Code Mode

### Good Use Cases
- **Chained tool calls** - When output of one tool feeds into another
- **Conditional logic** - When actions depend on intermediate results
- **MCP multi-server** - Orchestrating tools across multiple MCP servers
- **Batch operations** - Processing multiple items in sequence

### When NOT to Use
- Single tool calls - Overhead not worth it
- Simple Q&A - No tools needed
- Streaming responses - Code Mode executes synchronously

## Limitations

- **Experimental** - API may change
- **Cloudflare Workers only** - Requires Workers runtime
- **JavaScript only** - Python support planned
- **Synchronous execution** - Generated code runs to completion
