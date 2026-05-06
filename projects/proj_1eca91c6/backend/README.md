# Snake Game API Backend

FastAPI-based REST API for the Snake Game MVP.

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

### Running the Server

```bash
# Development mode with auto-reload
cd backend
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API Base URL:** http://localhost:8000
- **Interactive Docs (Swagger):** http://localhost:8000/docs
- **Alternative Docs (ReDoc):** http://localhost:8000/redoc

### Testing

Run the integration test suite:

```bash
# From project root
pytest tests/integration/test_api_endpoints.py -v

# With coverage
pytest tests/integration/test_api_endpoints.py -v --cov=backend/api --cov-report=html
```

## API Endpoints

### Snake Game Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/snake/start` | Initialize new game session |
| GET | `/api/snake/state/{session_id}` | Get current game state |
| POST | `/api/snake/move` | Submit direction change |
| POST | `/api/snake/restart` | Restart game session |

### General Game Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/games/{game_type}/config` | Get game configuration |
| GET | `/api/games/{game_type}/sessions` | List active sessions |

### Utility Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API information |
| GET | `/health` | Health check |

## Project Structure

```
backend/
├── api/
│   ├── __init__.py           # FastAPI app setup
│   ├── schemas.py            # Pydantic models
│   ├── session_manager.py    # Session lifecycle management
│   └── routers/
│       ├── __init__.py
│       ├── snake.py          # Snake-specific endpoints
│       └── games.py          # General game endpoints
├── game_engine/
│   ├── interfaces/           # Abstract interfaces
│   └── core/                 # Game logic implementations
└── requirements.txt
```

## Configuration

Default game configuration (can be overridden per session):

```json
{
  "grid_size": 10,           // Grid dimension (5-30)
  "initial_speed": 500,      // Tick speed in ms (100-2000)
  "enable_walls": true,      // Wall collision enabled
  "enable_self_collision": true,  // Self collision enabled
  "food_growth_rate": 1      // Snake growth per food (1-5)
}
```

## Example Usage

### Start a Game

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

### Get Game State

```bash
curl http://localhost:8000/api/snake_state/{session_id}
```

### Submit Move

```bash
curl -X POST http://localhost:8000/api/snake/move \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "{session_id}",
    "direction": "UP"
  }'
```

### Restart Game

```bash
curl -X POST http://localhost:8000/api/snake/restart \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "{session_id}"
  }'
```

## Development

### Adding New Game Types

1. Implement `IGameLogic` interface in `game_engine/core/`
2. Add router in `api/routers/`
3. Register in `api/__init__.py`

### Running in Production

```bash
uvicorn api:app --host 0.0.0.0 --port 8000 --workers 4
```

## License

MIT License - See LICENSE file for details
