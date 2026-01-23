# SSE Stream Protocol Verification Guide

This guide outlines how to verify the async stream protocol integrity and error handling for the summary generation heartbeat mechanism.

## Protocol Verification Checklist

### 1. Heartbeat Event Frequency
**Objective**: Verify that `progress` events are emitted every ~5 seconds during long-running AI operations.

**Manual Test Steps**:
1. Start the backend server locally
2. Open browser DevTools > Network tab
3. Navigate to a filing page and trigger summary generation
4. Filter network requests to show only the event stream (look for `generate-stream` endpoint)
5. Observe the stream events in the Network tab
6. Verify that `progress` events with `stage: "analyzing"` appear approximately every 5 seconds

**Expected Behavior**:
- Progress events should appear every 4-6 seconds (allowing for network latency)
- Each event should have format: `data: {"type":"progress","stage":"analyzing","message":"Processing financial data with AI..."}`
- The connection should remain open throughout the wait period

### 2. Stream Remains Open During Wait
**Objective**: Verify the SSE connection stays active during the entire AI processing time.

**Manual Test Steps**:
1. Trigger a summary generation for a filing
2. Monitor the network request status
3. Wait for 2-3 minutes (simulating a long AI operation)
4. Verify the connection status remains "Pending" or "200 OK" (not closed)

**Expected Behavior**:
- Connection status should remain active
- No timeout errors should appear
- Heartbeat events should continue throughout

### 3. Final Output Delivery
**Objective**: Verify that after AI completion, the final summary is correctly streamed.

**Manual Test Steps**:
1. Complete steps 1-2 above
2. Wait for AI processing to complete (or simulate completion)
3. Verify a `chunk` event is received with the summary content
4. Verify a `complete` event is received with `summary_id`

**Expected Behavior**:
- `chunk` event contains the markdown summary
- `complete` event signals successful completion
- Connection closes cleanly after completion

### 4. Error Handling During Wait
**Objective**: Verify that errors during AI processing are handled gracefully.

**Test Scenarios**:

#### Scenario A: AI Service Timeout
1. Simulate an AI operation that exceeds timeout
2. Verify error event is streamed to client
3. Verify connection closes with error message

#### Scenario B: AI Service Failure
1. Simulate an AI service exception
2. Verify error event format: `{"type":"error","message":"..."}`
3. Verify user-friendly error message is displayed

**Expected Behavior**:
- Error events are properly formatted
- User sees clear error message
- Connection closes gracefully
- No unhandled exceptions in server logs

### 5. Concurrent Connection Handling
**Objective**: Verify multiple simultaneous connections work correctly.

**Manual Test Steps**:
1. Open 3-5 browser tabs/windows
2. In each, navigate to different filing pages
3. Trigger summary generation in all tabs simultaneously
4. Monitor all connections in DevTools
5. Verify all connections receive heartbeat events
6. Verify all connections complete successfully

**Expected Behavior**:
- All connections remain open
- Each connection receives its own heartbeat events
- No connection interferes with others
- All complete independently

## Automated Test Execution

Run the integration tests:

```bash
# Run heartbeat protocol tests
pytest backend/tests/integration/test_summary_stream_heartbeat.py -v

# Run with coverage
pytest backend/tests/integration/test_summary_stream_heartbeat.py --cov=app.routers.summaries --cov-report=html
```

## Protocol Event Format Reference

### Progress Event (Heartbeat)
```json
{
  "type": "progress",
  "stage": "analyzing",
  "message": "Processing financial data with AI..."
}
```

### Chunk Event (Summary Content)
```json
{
  "type": "chunk",
  "content": "# Summary Markdown Content..."
}
```

### Complete Event
```json
{
  "type": "complete",
  "summary_id": 123
}
```

### Error Event
```json
{
  "type": "error",
  "message": "Unable to retrieve this filing at the moment — please try again shortly."
}
```

## Troubleshooting

### Issue: No heartbeat events received
- Check backend logs for errors
- Verify `asyncio.create_task` is being used
- Verify `while not task.done()` loop is executing
- Check network tab for connection status

### Issue: Connection closes prematurely
- Verify frontend timeout is set to 600000ms (10 minutes)
- Check backend for exceptions during heartbeat loop
- Verify Render/Vercel timeout settings allow long connections

### Issue: Heartbeat events not updating UI
- Verify frontend `onProgress` callback is being called
- Check `StreamingSummaryDisplay` component state updates
- Verify `streamingStage` and `streamingMessage` state variables
