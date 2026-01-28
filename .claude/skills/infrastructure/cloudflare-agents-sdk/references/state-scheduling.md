# State, Scheduling & Queues Reference

This reference covers state management, scheduled tasks, task queues, and SQL access in Cloudflare Agents.

## State Management

State automatically persists to SQLite and broadcasts to connected clients via WebSocket.

### Defining State

```typescript
import { Agent } from "@cloudflare/agents";

interface MyState {
  counter: number;
  items: string[];
  lastUpdated: string | null;
}

export class MyAgent extends Agent<Env, MyState> {
  // Define initial state with types
  initialState: MyState = {
    counter: 0,
    items: [],
    lastUpdated: null,
  };
}
```

### Reading State

State is lazy-loaded from the database on first access:

```typescript
async handleRequest() {
  // First access loads from SQLite
  const current = this.state.counter;
  const items = this.state.items;

  return { current, itemCount: items.length };
}
```

### Updating State

Updates persist to SQLite and broadcast to all connected clients:

```typescript
async incrementCounter() {
  // Partial update - merges with existing state
  this.setState({
    counter: this.state.counter + 1,
    lastUpdated: new Date().toISOString(),
  });
}

async addItem(item: string) {
  this.setState({
    items: [...this.state.items, item],
  });
}
```

### State Change Hooks

```typescript
export class MyAgent extends Agent<Env, MyState> {
  // Called when state changes
  onStateUpdate(state: MyState, source: Connection | "server") {
    if (source === "server") {
      console.log("State updated by server");
    } else {
      console.log(`State updated by client: ${source.id}`);
    }
  }
}
```

### Client-Side State (React)

```typescript
import { useAgent } from "@cloudflare/agents/react";

function Counter() {
  const { state, setState } = useAgent<MyState>({
    agent: "my-agent",
  });

  return (
    <div>
      <p>Count: {state.counter}</p>
      <button onClick={() => setState({ counter: state.counter + 1 })}>
        Increment
      </button>
    </div>
  );
}
```

## Scheduling

Schedule tasks for future execution with three patterns.

### One-Time (Specific Date)

```typescript
// Schedule for specific date/time
await this.schedule(
  new Date("2024-12-25T09:00:00Z"),
  "sendHolidayGreeting",
  { userId: 123, message: "Happy Holidays!" }
);
```

### Delayed Execution

```typescript
// Execute after N seconds
await this.schedule(
  60, // 60 seconds from now
  "processQueuedItem",
  { itemId: 456 }
);

// Execute after 1 hour
await this.schedule(
  3600,
  "sendReminder",
  { userId: 123 }
);
```

### Recurring (Cron)

```typescript
// Every day at 9 AM UTC
await this.schedule(
  "0 9 * * *",
  "dailyReport",
  { reportType: "summary" }
);

// Every hour
await this.schedule(
  "0 * * * *",
  "hourlySync",
  {}
);

// Every Monday at 8 AM
await this.schedule(
  "0 8 * * 1",
  "weeklyDigest",
  { includeMetrics: true }
);
```

### Schedule Handlers

Define methods matching the scheduled task name:

```typescript
export class MyAgent extends Agent<Env, MyState> {
  // Handler receives payload and schedule metadata
  async sendHolidayGreeting(
    payload: { userId: number; message: string },
    schedule: ScheduleMetadata
  ) {
    await this.sendEmail(payload.userId, payload.message);
    console.log(`Executed schedule: ${schedule.id}`);
  }

  async dailyReport(payload: { reportType: string }) {
    const report = await this.generateReport(payload.reportType);
    await this.distributeReport(report);
  }
}
```

### Managing Schedules

```typescript
// Get all schedules
const schedules = await this.getSchedules();

// Filter by type
const cronSchedules = await this.getSchedules({ type: "cron" });

// Filter by time range
const upcoming = await this.getSchedules({
  after: new Date(),
  before: new Date(Date.now() + 86400000), // Next 24 hours
});

// Cancel a schedule
await this.cancelSchedule(schedule.id);
```

### Schedule Behavior

- **One-time schedules**: Deleted after execution
- **Cron schedules**: Automatically reschedule for next occurrence
- **Failed schedules**: Retry with exponential backoff

## Task Queue

Sequential task processing with automatic dequeue on success.

### Queuing Tasks

```typescript
// Queue a task for sequential processing
await this.queue("processOrder", { orderId: 123, priority: "high" });

// Queue multiple tasks
for (const item of items) {
  await this.queue("processItem", { itemId: item.id });
}
```

### Queue Handlers

```typescript
export class MyAgent extends Agent<Env, MyState> {
  // Auto-dequeues on successful completion
  async processOrder(payload: { orderId: number; priority: string }) {
    const order = await this.fetchOrder(payload.orderId);
    await this.validateOrder(order);
    await this.chargeCustomer(order);
    await this.fulfillOrder(order);
    // Task automatically removed from queue on success
  }

  async processItem(payload: { itemId: number }) {
    // If this throws, task remains in queue for retry
    await this.processItemInternal(payload.itemId);
  }
}
```

### Queue Management

```typescript
// Manual dequeue
await this.dequeue(taskId);

// Bulk dequeue
await this.dequeueBulk([taskId1, taskId2, taskId3]);

// Query queue
const pendingTasks = await this.queryQueue({
  callback: "processOrder",
  limit: 10,
});
```

## SQL Access

Direct SQLite access using template literals:

### Schema Creation

```typescript
async onStart() {
  await this.sql`
    CREATE TABLE IF NOT EXISTS analytics (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      event_type TEXT NOT NULL,
      user_id TEXT,
      data JSON,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
  `;
}
```

### Inserting Data

```typescript
async trackEvent(eventType: string, userId: string, data: object) {
  await this.sql`
    INSERT INTO analytics (event_type, user_id, data)
    VALUES (${eventType}, ${userId}, ${JSON.stringify(data)})
  `;
}
```

### Querying Data

```typescript
interface AnalyticsRow {
  id: number;
  event_type: string;
  user_id: string;
  data: string;
  created_at: string;
}

async getRecentEvents(userId: string, limit: number = 10) {
  const rows = await this.sql<AnalyticsRow>`
    SELECT * FROM analytics
    WHERE user_id = ${userId}
    ORDER BY created_at DESC
    LIMIT ${limit}
  `;

  return rows.map(row => ({
    ...row,
    data: JSON.parse(row.data),
  }));
}
```

## Lifecycle Callbacks

```typescript
export class MyAgent extends Agent<Env, MyState> {
  // Called when agent starts
  async onStart() {
    await this.initializeDatabase();
  }

  // Called when client connects
  async onConnect(connection: Connection) {
    console.log(`Client connected: ${connection.id}`);
  }

  // Called for each message
  async onMessage(message: string, connection: Connection) {
    const parsed = JSON.parse(message);
    await this.handleMessage(parsed);
  }

  // Called when state updates
  onStateUpdate(state: MyState, source: Connection | "server") {
    // React to state changes
  }

  // Called on errors
  onError(error: Error, connection?: Connection) {
    console.error("Agent error:", error);
    // Report to error tracking service
  }
}
```
