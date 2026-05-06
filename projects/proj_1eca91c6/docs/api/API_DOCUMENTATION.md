# Snake Game API Documentation

## Overview

The Snake Game REST API provides endpoints for game session management, player action submission, and state queries. All endpoints return JSON responses.

**Base URL:** `http://localhost:8000`

**API Version:** v1.0.0

---

## Authentication

Currently, the API does not require authentication. Session IDs are used to track game sessions.

---

## Common Response Format

### Success Response
```json
{
  "data": { ... }
}
```

### Error Response
```json
{
  "error": "error_type",
  "message": "Human-readable error message",
  "details": { ... }
}
```

### HTTP Status Codes
- `200 OK` - Successful request
- `201 Created` - Resource created successfully
- `400 Bad Request` - Invalid request parameters
- `404 Not Found` - Resource not found
- `422 Unprocessable Entity` - Validation error
- `500 Internal Server Error` - Server error

---

## Endpoints

### 1. Start Game

Initialize a new Snake game session.

**Endpoint:** `POST /api/snake/start`

**Request Body:**
```json
{
  "player_id": "string (optional, default: 'default')",
  "config": {
    "grid_size": "int (5-30, default: 10)",
    "initial_speed": "int (100-2000, default: 500)",
    "enable_walls": "bool (default: true)",
    "enable_self_collision": "bool (default: true)",
    "food_growth_rate": "int (1-5, default: 1)"
  }
}
```

**Response (201 Created):**
```json
{
  "session_id": "uuid-string",
  "session_info": {
    "session_id": "uuid-string",
    "game_type": "snake",
    "player_id": "string",
    "created_at": "ISO-8601-timestamp",
    "state": "ready",
    "score": 0
  },
  "game_state": {
    "grid_size": 10,
    "snake": [
      {"x": 2, "y": 5},
      {"x": 1, "y": 5},
      {"x": 0, "y": 5}
    ],
    "food": {"x": 7, "y": 3},
    "direction": "RIGHT",
    "score": 0,
    "game_over": false,
    "game_over_reason": null
  }
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/snake/start \
  -H "Content-Type: application/json" \
  -d '{
    "player_id": "player1",
    "config": {
      "grid_size": 15
    }
  }'
```

---

### 2. Get Game State

Retrieve the current game state for a session.

**Endpoint:** `GET /api/snake/state/{session_id}`

**Parameters:**
- `session_id` (path) - Game session identifier

**Response (200 OK):**
```json
{
  "session_id": "uuid-string",
  "session_info": {
    "session_id": "uuid-string",
    "game_type": "snake",
    "player_id": "string",
    "created_at": "ISO-8601-timestamp",
    "state": "running",
    "score": 5
  },
  "game_state": {
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

**Example:**
```bash
curl http://localhost:8000/api/snake/state/abc-123-def
```

---

### 3. Submit Move

Submit a direction change for the snake.

**Endpoint:** `POST /api/snake/move`

**Request Body:**
```json
{
  "session_id": "uuid-string",
  "direction": "UP|DOWN|LEFT|RIGHT"
}
```

**Response (200 OK):**
```json
{
  "session_id": "uuid-string",
  "success": true,
  "game_state": {
    "grid_size": 10,
    "snake": [...],
    "food": {...},
    "direction": "UP",
    "score": 5,
    "game_over": false
  },
  "message": null
}
```

**Error Response (400 Bad Request):**
```json
{
  "error": "invalid_move",
  "message": "Cannot reverse direction"
}
```

**Game Over State:**
```json
{
  "session_id": "uuid-string",
  "success": true,
  "game_state": {
    "game_over": true,
    "game_over_reason": "wall_collision",
    "score": 10
  }
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/snake/move \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "abc-123-def",
    "direction": "UP"
  }'
```

---

### 4. Restart Game

Restart a game session with the same session ID.

**Endpoint:** `POST /api/snake/restart`

**Request Body:**
```json
{
  "session_id": "uuid-string",
  "config": {
    "grid_size": "int (optional)",
    "initial_speed": "int (optional)",
    ...
  }
}
```

**Response (200 OK):**
```json
{
  "session_id": "uuid-string",
  "session_info": {
    "session_id": "uuid-string",
    "game_type": "snake",
    "player_id": "string",
    "created_at": "ISO-8601-timestamp",
    "state": "ready",
    "score": 0
  },
  "game_state": {
    "grid_size": 10,
    "snake": [
      {"x": 2, "y": 5},
      {"x": 1, "y": 5},
      {"x": 0, "y": 5}
    ],
    "food": {"x": 7, "y": 3},
    "direction": "RIGHT",
    "score": 0,
    "game_over": false
  }
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/snake/restart \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "abc-123-def"
  }'
```

---

### 5. Get Game Configuration

Get configuration schema and defaults for Snake game.

**Endpoint:** `GET /api/games/snake/config`

**Response (200 OK):**
```json
{
  "game_type": "snake",
  "config": {
    "grid_size": 10,
    "initial_speed": 500,
    "enable_walls": true,
    "enable_self_collision": true,
    "food_growth_rate": 1
  },
  "constraints": {
    "grid_size": {"type": "int", "range": [5, 30]},
    "initial_speed": {"type": "int", "range": [100, 2000]},
    "enable_walls": {"type": "bool"},
    "enable_self_collision": {"type": "bool"},
    "food_growth_rate": {"type": "int", "range": [1, 5]}
  }
}
```

**Example:**
```bash
curl http://localhost:8000/api/games/snake/config
```

---

### 6. List Sessions

List all active Snake game sessions.

**Endpoint:** `GET /api/games/snake/sessions`

**Response (200 OK):**
```json
{
  "game_type": "snake",
  "count": 2,
  "sessions": [
    {
      "session_id": "uuid-string-1",
      "player_id": "player1",
      "state": "running",
      "score": 5,
      "created_at": "2026-05-06T10:30:00"
    },
    {
      "session_id": "uuid-string-2",
      "player_id": "player2",
      "state": "game_over",
      "score": 12,
      "created_at": "2026-05-06T10:25:00"
    }
  ]
}
```

**Example:**
```bash
curl http://localhost:8000/api/games/snake/sessions
```

---

### 7. Health Check

Check API health status.

**Endpoint:** `GET /health`

**Response (200 OK):**
```json
{
  "status": "healthy"
}
```

---

## Game State Values

The `state` field in session_info can have the following values:

| State | Description |
|-------|-------------|
| `idle` | Session created but not initialized |
| `ready` | Game initialized and ready to start |
| `running` | Game actively running |
| `paused` | Game paused by player |
| `game_over` | Game ended with win/loss condition |
| `error` | Game encountered an error |

## Game Over Reasons

| Reason | Description |
|--------|-------------|
| `wall_collision` | Snake hit a wall |
| `self_collision` | Snake hit itself |

## Direction Values

Valid direction values for move submission:
- `UP` - Move upward
- `DOWN` - Move downward
- `LEFT` - Move left
- `RIGHT` - Move right

**Note:** 180° turns are not allowed (e.g., cannot go directly from UP to DOWN).

---

## Configuration Constraints

### Grid Size
- **Type:** Integer
- **Range:** 5-30
- **Default:** 10

### Initial Speed
- **Type:** Integer (milliseconds per tick)
- **Range:** 100-2000
- **Default:** 500

### Enable Walls
- **Type:** Boolean
- **Default:** true

When enabled, snake dies when hitting the grid boundary.

### Enable Self Collision
- **Type:** Boolean
- **Default:** true

When enabled, snake dies when hitting its own body.

### Food Growth Rate
- **Type:** Integer
- **Range:** 1-5
- **Default:** 1

Number of segments the snake grows when eating food.

---

## Error Codes

| Error Code | Description |
|------------|-------------|
| `session_not_found` | Session ID does not exist |
| `invalid_move` | Move is invalid (e.g., 180° turn) |
| `invalid_config` | Configuration parameters are invalid |
| `restart_failed` | Failed to restart game |
| `unsupported_game` | Game type is not supported |

---

## Testing the API

### Using cURL

```bash
# Start a game
curl -X POST http://localhost:8000/api/snake/start \
  -H "Content-Type: application/json" \
  -d '{"player_id": "test"}'

# Get state (replace SESSION_ID)
curl http://localhost:8000/api/snake/state/SESSION_ID

# Submit move (replace SESSION_ID)
curl -X POST http://localhost:8000/api/snake/move \
  -H "Content-Type: application/json" \
  -d '{"session_id": "SESSION_ID", "direction": "UP"}'
```

### Using Python

```python
import requests

# Start game
response = requests.post(
    "http://localhost:8000/api/snake/start",
    json={"player_id": "player1"}
)
session_id = response.json()["session_id"]

# Get state
response = requests.get(f"http://localhost:8000/api/snake/state/{session_id}")
print(response.json())

# Submit move
response = requests.post(
    "http://localhost:8000/api/snake/move",
    json={
        "session_id": session_id,
        "direction": "UP"
    }
)
print(response.json())
```

### Interactive API Documentation

FastAPI provides interactive API documentation:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## Running the Server

```bash
# Install dependencies
pip install -r backend/requirements.txt

# Run server
cd backend
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

---

## Integration Tests

Run the integration test suite:

```bash
pytest tests/integration/test_api_endpoints.py -v
```
