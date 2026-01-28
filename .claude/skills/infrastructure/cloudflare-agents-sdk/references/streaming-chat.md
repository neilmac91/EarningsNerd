# Streaming Chat Reference

The `AIChatAgent` class provides real-time streaming chat with automatic message persistence and resumable streams.

## Basic Implementation

```typescript
import { AIChatAgent, Message } from "@cloudflare/agents";
import { streamText, convertToModelMessages } from "ai";
import { openai } from "@ai-sdk/openai";

export class ChatAgent extends AIChatAgent<Env> {
  async onChatMessage(
    messages: Message[],
    onChunk: (chunk: string) => void
  ): Promise<ReadableStream<string>> {
    const result = await streamText({
      model: openai("gpt-4"),
      messages: convertToModelMessages(messages),
    });

    return result.textStream;
  }
}
```

## Adding System Prompts

```typescript
export class ChatAgent extends AIChatAgent<Env> {
  async onChatMessage(messages: Message[], onChunk: StreamCallback) {
    const result = await streamText({
      model: openai("gpt-4"),
      system: `You are a helpful assistant for EarningsNerd,
               an SEC filing analysis platform. Help users
               understand financial reports and investment insights.`,
      messages: convertToModelMessages(messages),
    });

    return result.textStream;
  }
}
```

## Tool Integration

```typescript
import { tool } from "ai";
import { z } from "zod";

export class ChatAgent extends AIChatAgent<Env> {
  async onChatMessage(messages: Message[], onChunk: StreamCallback) {
    const result = await streamText({
      model: openai("gpt-4"),
      messages: convertToModelMessages(messages),
      tools: {
        getStockPrice: tool({
          description: "Get current stock price for a ticker",
          parameters: z.object({
            ticker: z.string().describe("Stock ticker symbol"),
          }),
          execute: async ({ ticker }) => {
            const response = await fetch(
              `https://api.example.com/stock/${ticker}`
            );
            return response.json();
          },
        }),
        getFilingSummary: tool({
          description: "Get AI summary of an SEC filing",
          parameters: z.object({
            filingId: z.number().describe("Filing ID"),
          }),
          execute: async ({ filingId }) => {
            // Fetch summary from your API
            return { summary: "..." };
          },
        }),
      },
    });

    return result.textStream;
  }
}
```

## Resumable Streams

Streams automatically resume if a client disconnects and reconnects:

```typescript
export class ChatAgent extends AIChatAgent<Env> {
  // Resumable streaming is enabled by default
  // Chunks are buffered to SQLite during transmission

  // To disable:
  resumableStreams = false;
}
```

### How It Works
1. As chunks stream, they're buffered to SQLite
2. If client disconnects, buffered chunks are preserved
3. On reconnection, buffered chunks sent immediately
4. Live streaming continues from where it left off

## Custom UI Message Streams

For granular control over response handling:

```typescript
import { createUIMessageStream } from "@cloudflare/agents";

export class ChatAgent extends AIChatAgent<Env> {
  async onChatMessage(messages: Message[], onChunk: StreamCallback) {
    const stream = createUIMessageStream({
      onStart: () => {
        // Called when stream starts
      },
      onToken: (token) => {
        // Called for each token
        onChunk(token);
      },
      onFinish: (message) => {
        // Called when stream completes
        this.saveToHistory(message);
      },
    });

    // Process with AI
    const result = await streamText({
      model: openai("gpt-4"),
      messages: convertToModelMessages(messages),
    });

    // Pipe to custom stream
    result.textStream.pipeTo(stream.writable);

    return stream.readable;
  }
}
```

## Client Integration

### React Hook

```typescript
import { useAgentChat } from "@cloudflare/agents/react";

function ChatInterface() {
  const {
    messages,
    input,
    handleInputChange,
    handleSubmit,
    status,
    error,
  } = useAgentChat({
    agent: "chat-agent",
    // Optional: provide initial messages
    initialMessages: [],
  });

  return (
    <div className="chat-container">
      <div className="messages">
        {messages.map((message) => (
          <div key={message.id} className={`message ${message.role}`}>
            {message.content}
          </div>
        ))}
      </div>

      {status === "streaming" && <div className="typing-indicator" />}

      {error && <div className="error">{error.message}</div>}

      <form onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={handleInputChange}
          placeholder="Type a message..."
          disabled={status === "streaming"}
        />
        <button type="submit" disabled={status !== "ready"}>
          Send
        </button>
      </form>
    </div>
  );
}
```

### Status Values

| Status | Description |
|--------|-------------|
| `ready` | Connected and ready for input |
| `submitted` | Request sent, awaiting response |
| `streaming` | Receiving streamed response |
| `error` | Error occurred |

## Non-Chat Streaming (RPC)

For streaming outside of chat contexts:

```typescript
import { Agent, callable } from "@cloudflare/agents";

export class DataAgent extends Agent<Env> {
  @callable({ streaming: true })
  async *streamData(params: { query: string }) {
    const results = await this.fetchLargeDataset(params.query);

    for (const item of results) {
      yield JSON.stringify(item) + "\n";
      // Allow other work between yields
      await scheduler.wait(0);
    }
  }
}
```

Client usage:
```typescript
const agent = useAgent({ agent: "data-agent" });

const stream = await agent.call("streamData", { query: "SELECT *" });
for await (const chunk of stream) {
  console.log(JSON.parse(chunk));
}
```
