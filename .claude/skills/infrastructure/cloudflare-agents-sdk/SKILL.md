---
name: cloudflare-agents-sdk
description: Build AI agents on Cloudflare Workers with the Agents SDK
version: 1.0.0
author: cloudflare
source: https://github.com/cloudflare/skills/tree/main/agents-sdk
---

# Cloudflare Agents SDK

This skill provides guidance for building AI agents on Cloudflare Workers using the Agents SDK. The SDK enables stateful, persistent agents with built-in scheduling, state management, and real-time communication.

## Overview

The Cloudflare Agents SDK allows you to build:
- Stateful AI agents with automatic persistence
- Real-time streaming chat applications
- Scheduled and recurring task execution
- Multi-tool orchestration with Code Mode

## Agent Types

### Base Agent
For custom agent implementations:
```typescript
import { Agent } from "@cloudflare/agents";

export class MyAgent extends Agent<Env, State> {
  initialState = { counter: 0 };

  async onMessage(message: string) {
    // Handle incoming messages
  }
}
```

### AIChatAgent
For conversational AI with automatic message persistence:
```typescript
import { AIChatAgent } from "@cloudflare/agents";

export class ChatAgent extends AIChatAgent<Env> {
  async onChatMessage(messages: Message[], onChunk: StreamCallback) {
    const result = await streamText({
      model: openai("gpt-4"),
      messages: convertToModelMessages(messages),
    });
    return result.textStream;
  }
}
```

### McpAgent
For Model Context Protocol server implementations:
```typescript
import { McpAgent } from "@cloudflare/agents";

export class MyMcpAgent extends McpAgent<Env> {
  // Implements MCP protocol
}
```

## Core Features

### State Management
State automatically persists to SQLite and broadcasts to connected clients:
```typescript
// Define initial state
initialState = { count: 0, items: [] };

// Update state (persists and broadcasts)
this.setState({ count: this.state.count + 1 });

// React to state changes
onStateUpdate(state: State, source: Connection | "server") {
  console.log("State updated:", state);
}
```

### Scheduling
Schedule one-time, delayed, or recurring tasks:
```typescript
// One-time at specific date
await this.schedule(new Date("2024-12-25"), "sendReminder", { userId: 123 });

// Delayed execution
await this.schedule(60, "processQueue", {}); // 60 seconds

// Recurring (cron)
await this.schedule("0 9 * * *", "dailyReport", {}); // 9 AM daily

// Handler
async sendReminder(payload: { userId: number }) {
  // Execute scheduled task
}
```

### Task Queue
Sequential task processing with automatic dequeue:
```typescript
// Queue a task
await this.queue("processOrder", { orderId: 123 });

// Handler (auto-dequeues on success)
async processOrder(payload: { orderId: number }) {
  await this.processOrderInternal(payload.orderId);
}
```

## Configuration

### wrangler.jsonc
```jsonc
{
  "name": "my-agent",
  "main": "src/index.ts",
  "compatibility_date": "2024-12-01",
  "durable_objects": {
    "bindings": [{ "name": "MY_AGENT", "class_name": "MyAgent" }]
  },
  "migrations": [
    { "tag": "v1", "new_sqlite_classes": ["MyAgent"] }
  ]
}
```

### Dependencies
```bash
npm install @cloudflare/agents agents-sdk ai @ai-sdk/openai
```

## Client Integration

### React Hook
```typescript
import { useAgent, useAgentChat } from "@cloudflare/agents/react";

function Chat() {
  const { messages, input, handleInputChange, handleSubmit, status } =
    useAgentChat({ agent: "chat-agent" });

  return (
    <div>
      {messages.map(m => <Message key={m.id} message={m} />)}
      <form onSubmit={handleSubmit}>
        <input value={input} onChange={handleInputChange} />
      </form>
    </div>
  );
}
```

### Status Values
- `ready` - Connected and ready
- `streaming` - Receiving streamed response
- `submitted` - Request sent, awaiting response
- `error` - Error occurred

## Code Mode (Experimental)

Code Mode generates executable JavaScript to orchestrate multiple tools in a single execution, reducing token consumption:

```typescript
import { CodeModeProxy } from "@cloudflare/codemode";

export { CodeModeProxy };

export class MyAgent extends Agent<Env> {
  async callTool(name: string, args: unknown) {
    switch (name) {
      case "getWeather": return this.getWeather(args);
      case "sendEmail": return this.sendEmail(args);
    }
  }
}
```

### When to Use Code Mode
- Chained tool calls with dependencies
- Conditional logic across multiple tools
- MCP multi-server workflows

### When NOT to Use
- Single tool calls
- Simple Q&A without tools

## References

See the reference documents for detailed implementations:
- [Code Mode](./references/codemode.md) - Multi-tool orchestration
- [Streaming Chat](./references/streaming-chat.md) - AIChatAgent patterns
- [State & Scheduling](./references/state-scheduling.md) - Persistence and tasks

## Best Practices

1. **Use appropriate agent type** - AIChatAgent for chat, base Agent for custom logic
2. **Define initial state** - Always provide typed initial state
3. **Handle reconnection** - Leverage automatic stream resumption
4. **Use scheduling for background work** - Don't block request handlers
5. **Implement proper error handling** - Use onError lifecycle hook
