# WebSocket API Documentation

## Overview

The Snake Game API supports real-time game state updates through WebSocket connections. This allows clients to receive instant updates when the game state changes, without the need for polling.

**WebSocket Endpoint:** `ws://localhost:8000/api/snake/ws/{session_id}`

**Protocol:** JSON messages over WebSocket

---

## Connection

### Connecting to a Game Session

To connect to a game session via WebSocket:

```javascript
const session_id = "your-session-id";
const ws = new WebSocket(`ws://localhost:8000/api/snake/ws/${session_id}`);

ws.onopen = () => {
  console.log("Connected to game session");
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log("Received:", message);
};

ws.onerror = (error) => {
  console.error("WebSocket error:", error);
};

ws.onclose = (event) => {
  console.log("Disconnected:", event.code, event.reason);
};
```

### Connection Validation

- The WebSocket will only accept connections for valid session IDs
- If the session doesn't exist, the connection will be closed with code `1008` (Policy Violation)
- After connecting, you'll immediately receive the current game state

---

## Message Protocol

All messages sent and received over the WebSocket are JSON objects with a `type` field indicating the message type.

### Client Messages (Sent to Server)

#### 1. Subscribe

Subscribe to receive state updates (automatically done on connection):

```json
{
  "type": "subscribe"
}
```

**Response:**
```json
{
  "type": "subscribed",
  "session_id": "abc-123",
  "connection_count": 2
}
```

#### 2. Unsubscribe

Stop receiving state updates (connection remains open):

```json
{
  "type": "unsubscribe"
}
```

**Response:**
```json
{
  "type": "unsubscribed",
  "session_id": "abc-123"
}
```

#### 3. Submit Move

Submit a direction change for the snake:

```json
{
  "type": "move",
  "direction": "UP"
}
```

**Valid directions:** `UP`, `DOWN`, `LEFT`, `RIGHT`

**Success Response:**
```json
{
  "type": "move_accepted",
  "direction": "UP"
}
```

**Error Response:**
```json
{
  "type": "move_error",
  "message": "Cannot reverse direction"
}
```

#### 4. Ping

Test connection liveness:

```json
{
  "type": "ping",
  "timestamp": 1234567890
}
```

**Response:**
```json
{
  "type": "pong",
  "timestamp": 1234567890
}
```

### Server Messages (Received from Server)

#### 1. State Update

Broadcast whenever the game state changes (after moves, restart, etc.):

```json
{
  "type": "state_update",
  "session_id": "abc-123",
  "data": {
    "grid_size": 10,
    "snake": [
      {"x": 5, "y": 5},
      {"x": 4, "y": 5},
      {"x": 3, "y": 5}
    ],
    "food": {"x": 2, "y": 7},
    "direction": "RIGHT",
    "score": 5,
    "game_over": false,
    "game_over_reason": null
  }
}
```

#### 2. Error

Sent when an error occurs:

```json
{
  "type": "error",
  "message": "Error description"
}
```

#### 3. Subscribed/Unsubscribed

Confirmation of subscription status changes (see above).

#### 4. Move Accepted/Move Error

Confirmation of move processing (see above).

---

## Usage Examples

### Example 1: Complete Game Session

```javascript
const session_id = "your-session-id";
const ws = new WebSocket(`ws://localhost:8000/api/snake/ws/${session_id}`);

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  switch (message.type) {
    case "state_update":
      // Update UI with new game state
      renderGame(message.data);
      break;

    case "move_accepted":
      console.log("Move accepted:", message.direction);
      break;

    case "move_error":
      console.error("Move failed:", message.message);
      break;

    case "error":
      console.error("Error:", message.message);
      break;
  }
};

// Submit a move
function submitMove(direction) {
  ws.send(JSON.stringify({
    type: "move",
    direction: direction
  }));
}

// Example: Move up
submitMove("UP");
```

### Example 2: Multi-Player Observation

Multiple clients can connect to the same session to observe the game:

```javascript
// Observer 1 - Watch only
const observer1 = new WebSocket(`ws://localhost:8000/api/snake/ws/${session_id}`);

// Observer 2 - Watch only
const observer2 = new WebSocket(`ws://localhost:8000/api/snake/ws/${session_id}`);

// Player - Can control the game
const player = new WebSocket(`ws://localhost:8000/api/snake/ws/${session_id}`);

player.onopen = () => {
  // Player submits moves
  player.send(JSON.stringify({
    type: "move",
    direction: "RIGHT"
  }));
};

// Both observers will receive the same state updates
```

### Example 3: React Integration

```jsx
import { useEffect, useState, useRef } from 'react';

function GameWebSocket({ sessionId }) {
  const [gameState, setGameState] = useState(null);
  const [error, setError] = useState(null);
  const wsRef = useRef(null);

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/api/snake/ws/${sessionId}`);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('Connected to game');
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);

      if (message.type === 'state_update') {
        setGameState(message.data);
      } else if (message.type === 'error') {
        setError(message.message);
      }
    };

    ws.onerror = (event) => {
      setError('WebSocket error');
    };

    ws.onclose = () => {
      console.log('Disconnected from game');
    };

    return () => {
      ws.close();
    };
  }, [sessionId]);

  const sendMove = (direction) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'move',
        direction
      }));
    }
  };

  if (error) return <div>Error: {error}</div>;
  if (!gameState) return <div>Loading...</div>;

  return (
    <div>
      <div>Score: {gameState.score}</div>
      <button onClick={() => sendMove('UP')}>Up</button>
      <button onClick={() => sendMove('DOWN')}>Down</button>
      <button onClick={() => sendMove('LEFT')}>Left</button>
      <button onClick={() => sendMove('RIGHT')}>Right</button>
    </div>
  );
}
```

---

## Error Handling

### Connection Errors

- **1008 Policy Violation**: Session ID doesn't exist
- **1011 Internal Error**: Server error during connection

### Message Errors

Invalid messages will receive an error response:

```json
{
  "type": "error",
  "message": "Invalid JSON format"
}
```

or

```json
{
  "type": "error",
  "message": "Unknown message type: invalid_type"
}
```

---

## Polling Fallback

For clients that cannot use WebSockets, the REST API provides polling-based state retrieval:

```javascript
// Poll for state updates every 100ms
async function pollGameState(sessionId) {
  const response = await fetch(`/api/snake/state/${sessionId}`);
  const data = await response.json();
  return data.game_state;
}

setInterval(async () => {
  const state = await pollGameState(sessionId);
  renderGame(state);
}, 100);
```

---

## Best Practices

1. **Reconnection**: Implement automatic reconnection with exponential backoff
2. **Heartbeat**: Send periodic ping messages to detect stale connections
3. **State Sync**: Always use the latest state update, don't assume message order
4. **Error Recovery**: Handle disconnections gracefully and restore game state
5. **Move Validation**: Validate moves on the client side before sending to reduce server load

---

## Testing

The WebSocket API can be tested using the integrated test suite:

```bash
# Run WebSocket tests
pytest tests/integration/test_websocket.py -v

# Run with coverage
pytest tests/integration/test_websocket.py -v --cov=backend/api --cov-report=html
```

---

## Performance Considerations

- **Connection Limits**: The server can handle multiple concurrent connections per session
- **Message Size**: Game state messages are typically < 1KB
- **Latency**: WebSocket updates have significantly lower latency than polling
- **Bandwidth**: WebSockets use less bandwidth than polling for real-time updates

---

## Security Notes

- In production, implement authentication for WebSocket connections
- Validate session IDs on the server side
- Use WSS (WebSocket Secure) for encrypted connections
- Implement rate limiting for move submissions
- Consider connection limits per user/IP to prevent abuse
