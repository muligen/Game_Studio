# Game Engine Module Layer Architecture

## 1. Overview

The Game Engine Module Layer is a foundational component of Game Studio that provides a generic, extensible framework for building browser-based games. This layer separates concerns between game logic, rendering, and state management while leveraging LangGraph for game state machine orchestration.

## 2. Architecture Principles

### 2.1 Separation of Concerns
- **Game Logic Layer**: Pure business rules, independent of presentation
- **Rendering Layer**: Visual presentation using Canvas API
- **State Management Layer**: Centralized state with LangGraph orchestration
- **Communication Layer**: REST/WebSocket abstraction

### 2.2 Modularity
- Each game type implements the same generic interfaces
- Pluggable rendering strategies (Canvas, DOM, WebGL)
- Configurable game parameters without code changes

### 2.3 Extensibility
- Easy to add new game types by implementing base interfaces
- Support for both single-player and multiplayer modes
- Frontend-backend communication protocol abstraction

## 3. Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (React)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Game UI    │  │   Canvas     │  │   Input      │      │
│  │  Components  │  │   Renderer   │  │   Handler    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                           ↕ REST/WebSocket
┌─────────────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │    API       │  │    Game      │  │   State      │      │
│  │   Endpoints  │→  │   Engine     │→  │   Manager   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                          ↓                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  WebSocket   │  │   Config     │  │   LangGraph  │      │
│  │   Handler    │  │   Manager    │  │   Orch.      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## 4. Core Components

### 4.1 Generic Game State Management Interface

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

class GameState(Enum):
    """Generic game states applicable to all game types"""
    IDLE = "idle"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    GAME_OVER = "game_over"
    ERROR = "error"

@dataclass
class GameSession:
    """Generic game session metadata"""
    session_id: str
    game_type: str
    player_id: str
    created_at: datetime
    state: GameState
    score: int = 0
    metadata: Dict[str, Any] = None

class IGameStateManager(ABC):
    """Interface for game state management"""
    
    @abstractmethod
    async def create_session(self, game_type: str, player_id: str, 
                           config: Dict[str, Any]) -> GameSession:
        """Create a new game session"""
        pass
    
    @abstractmethod
    async def get_state(self, session_id: str) -> Optional[GameSession]:
        """Get current game state"""
        pass
    
    @abstractmethod
    async def update_state(self, session_id: str, 
                          state_update: Dict[str, Any]) -> bool:
        """Update game state"""
        pass
    
    @abstractmethod
    async def transition_state(self, session_id: str, 
                              new_state: GameState) -> bool:
        """Transition to a new game state"""
        pass
    
    @abstractmethod
    async def delete_session(self, session_id: str) -> bool:
        """Delete a game session"""
        pass

class IGameLogic(ABC):
    """Interface for game-specific logic"""
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize game with configuration"""
        pass
    
    @abstractmethod
    async def process_action(self, session_id: str, 
                           action: Dict[str, Any]) -> Dict[str, Any]:
        """Process player action and return new state"""
        pass
    
    @abstractmethod
    async def validate_action(self, session_id: str, 
                            action: Dict[str, Any]) -> bool:
        """Validate if action is legal"""
        pass
    
    @abstractmethod
    async def check_game_over(self, session_id: str) -> tuple[bool, str]:
        """Check if game is over, return (is_over, reason)"""
        pass
    
    @abstractmethod
    async def get_render_state(self, session_id: str) -> Dict[str, Any]:
        """Get state formatted for rendering"""
        pass
```

### 4.2 LangGraph Integration Pattern

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator

class GameEngineState(TypedDict):
    """State schema for LangGraph game orchestration"""
    session_id: str
    current_state: GameState
    game_data: Annotated[Dict[str, Any], operator.ior]
    player_actions: Annotated[List[Dict[str, Any]], operator.add]
    render_state: Optional[Dict[str, Any]]
    error_message: Optional[str]
    timestamp: float

class LangGraphGameOrchestrator:
    """LangGraph-based game state machine orchestration"""
    
    def __init__(self, game_logic: IGameLogic):
        self.game_logic = game_logic
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build LangGraph state machine"""
        workflow = StateGraph(GameEngineState)
        
        # Add nodes for each state transition
        workflow.add_node("initialize", self._initialize_game)
        workflow.add_node("process_action", self._process_player_action)
        workflow.add_node("update_state", self._update_game_state)
        workflow.add_node("check_game_over", self._check_game_over)
        workflow.add_node("prepare_render", self._prepare_render_state)
        workflow.add_node("handle_error", self._handle_error)
        
        # Define state transitions
        workflow.set_entry_point("initialize")
        
        workflow.add_conditional_edges(
            "initialize",
            self._should_start_game,
            {
                "start": "update_state",
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "process_action",
            self._validate_action,
            {
                "valid": "update_state",
                "invalid": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "check_game_over",
            self._is_game_over,
            {
                "continue": "prepare_render",
                "game_over": "prepare_render"
            }
        )
        
        workflow.add_edge("update_state", "check_game_over")
        workflow.add_edge("prepare_render", END)
        workflow.add_edge("handle_error", END)
        
        return workflow.compile()
    
    async def _initialize_game(self, state: GameEngineState) -> GameEngineState:
        """Initialize game state"""
        try:
            game_data = await self.game_logic.initialize(
                state.get("config", {})
            )
            state["current_state"] = GameState.READY
            state["game_data"] = game_data
            return state
        except Exception as e:
            state["error_message"] = str(e)
            state["current_state"] = GameState.ERROR
            return state
    
    async def _process_player_action(self, state: GameEngineState) -> GameEngineState:
        """Process player input action"""
        action = state["player_actions"][-1]
        if await self.game_logic.validate_action(state["session_id"], action):
            result = await self.game_logic.process_action(
                state["session_id"], action
            )
            state["game_data"].update(result)
        return state
    
    async def _update_game_state(self, state: GameEngineState) -> GameEngineState:
        """Update game state after action"""
        state["current_state"] = GameState.RUNNING
        return state
    
    async def _check_game_over(self, state: GameEngineState) -> GameEngineState:
        """Check if game is over"""
        is_over, reason = await self.game_logic.check_game_over(
            state["session_id"]
        )
        if is_over:
            state["current_state"] = GameState.GAME_OVER
            state["game_data"]["game_over_reason"] = reason
        return state
    
    async def _prepare_render_state(self, state: GameEngineState) -> GameEngineState:
        """Prepare state for frontend rendering"""
        state["render_state"] = await self.game_logic.get_render_state(
            state["session_id"]
        )
        return state
    
    async def _handle_error(self, state: GameEngineState) -> GameEngineState:
        """Handle error state"""
        state["current_state"] = GameState.ERROR
        return state
    
    def _should_start_game(self, state: GameEngineState) -> str:
        """Conditional transition: should game start?"""
        return "start" if state["current_state"] != GameState.ERROR else "error"
    
    def _validate_action(self, state: GameEngineState) -> str:
        """Conditional transition: is action valid?"""
        return "valid"  # Simplified for MVP
    
    def _is_game_over(self, state: GameEngineState) -> str:
        """Conditional transition: is game over?"""
        return "game_over" if state["current_state"] == GameState.GAME_OVER else "continue"
```

### 4.3 API Endpoint Structure

#### REST API Endpoints

```python
from fastapi import FastAPI, HTTPException, WebSocket
from typing import Dict, Any
import uuid

app = FastAPI(title="Game Studio Engine API")

# Session Management
@app.post("/api/v1/games/{game_type}/sessions")
async def create_session(game_type: str, config: Dict[str, Any]):
    """Create new game session"""
    session_id = str(uuid.uuid4())
    # Implementation
    return {"session_id": session_id, "status": "created"}

@app.get("/api/v1/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session state"""
    # Implementation
    return {}

@app.delete("/api/v1/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete session"""
    # Implementation
    return {"status": "deleted"}

# Game Actions
@app.post("/api/v1/sessions/{session_id}/actions")
async def submit_action(session_id: str, action: Dict[str, Any]):
    """Submit player action"""
    # Implementation
    return {"status": "accepted", "new_state": {}}

@app.get("/api/v1/sessions/{session_id}/state")
async def get_game_state(session_id: str):
    """Get current game state for rendering"""
    # Implementation
    return {"render_state": {}}

# Configuration
@app.get("/api/v1/games/{game_type}/config")
async def get_game_config(game_type: str):
    """Get game configuration schema"""
    # Implementation
    return {"config_schema": {}}

@app.post("/api/v1/sessions/{session_id}/config")
async def update_session_config(session_id: str, config: Dict[str, Any]):
    """Update session-specific configuration"""
    # Implementation
    return {"status": "updated"}
```

#### WebSocket Support (Optional for MVP)

```python
@app.websocket("/ws/sessions/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket connection for real-time game updates"""
    await websocket.accept()
    try:
        while True:
            # Receive player actions
            data = await websocket.receive_json()
            
            # Process action through LangGraph
            # result = await orchestrator.ainvoke(...)
            
            # Send updated state
            await websocket.send_json({"state": result})
    except WebSocketDisconnect:
        # Cleanup
        pass
```

### 4.4 Frontend-Backend Communication Protocol

#### Polling-Based Approach (MVP Default)

```typescript
// Frontend polling implementation
interface GameStateClient {
  sessionId: string;
  pollInterval: number;
  
  startGame(config: GameConfig): Promise<GameState>;
  submitAction(action: PlayerAction): Promise<ActionResult>;
  pollState(): Promise<GameState>;
}

class PollingGameStateClient implements GameStateClient {
  private baseUrl: string;
  sessionId: string;
  pollInterval: number = 100; // 100ms default
  private pollTimer?: NodeJS.Timeout;
  
  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }
  
  async startGame(config: GameConfig): Promise<GameState> {
    const response = await fetch(`${this.baseUrl}/api/v1/games/snake/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    });
    const data = await response.json();
    this.sessionId = data.session_id;
    return data;
  }
  
  async submitAction(action: PlayerAction): Promise<ActionResult> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/sessions/${this.sessionId}/actions`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(action)
      }
    );
    return response.json();
  }
  
  async pollState(): Promise<GameState> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/sessions/${this.sessionId}/state`
    );
    return response.json();
  }
  
  startPolling(callback: (state: GameState) => void): void {
    this.pollTimer = setInterval(async () => {
      const state = await this.pollState();
      callback(state);
    }, this.pollInterval);
  }
  
  stopPolling(): void {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
    }
  }
}
```

#### Push-Based Approach (Post-MVP Enhancement)

```typescript
class WebSocketGameStateClient implements GameStateClient {
  private ws?: WebSocket;
  sessionId: string;
  pollInterval: number = 0;
  
  constructor(private baseUrl: string) {}
  
  async startGame(config: GameConfig): Promise<GameState> {
    // Create session via REST first
    const response = await fetch(`${this.baseUrl}/api/v1/games/snake/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    });
    const data = await response.json();
    this.sessionId = data.session_id;
    
    // Then establish WebSocket
    await this.connectWebSocket();
    return data;
  }
  
  private async connectWebSocket(): Promise<void> {
    const wsUrl = this.baseUrl.replace('http', 'ws')
      + `/ws/sessions/${this.sessionId}`;
    
    this.ws = new WebSocket(wsUrl);
    
    return new Promise((resolve, reject) => {
      this.ws!.onopen = () => resolve();
      this.ws!.onerror = (err) => reject(err);
    });
  }
  
  async submitAction(action: PlayerAction): Promise<ActionResult> {
    this.ws!.send(JSON.stringify(action));
    return new Promise((resolve) => {
      const handler = (event: MessageEvent) => {
        this.ws!.removeEventListener('message', handler);
        resolve(JSON.parse(event.data));
      };
      this.ws!.addEventListener('message', handler);
    });
  }
  
  onStateUpdate(callback: (state: GameState) => void): void {
    this.ws!.addEventListener('message', (event) => {
      const data = JSON.parse(event.data);
      callback(data.state);
    });
  }
}
```

### 4.5 Configuration System Design

```python
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import json
from pathlib import Path

@dataclass
class GameConfigSchema:
    """Configuration schema for a game type"""
    game_type: str
    version: str
    default_config: Dict[str, Any]
    config_constraints: Dict[str, Any]
    runtime_modifiable: List[str]

class ConfigManager:
    """Centralized configuration management"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.configs: Dict[str, GameConfigSchema] = {}
        self._load_configs()
    
    def _load_configs(self):
        """Load all game configurations"""
        for config_file in self.config_dir.glob("*.json"):
            with open(config_file) as f:
                data = json.load(f)
                schema = GameConfigSchema(**data)
                self.configs[schema.game_type] = schema
    
    def get_config_schema(self, game_type: str) -> Optional[GameConfigSchema]:
        """Get configuration schema for a game type"""
        return self.configs.get(game_type)
    
    def get_default_config(self, game_type: str) -> Dict[str, Any]:
        """Get default configuration for a game type"""
        schema = self.configs.get(game_type)
        return schema.default_config.copy() if schema else {}
    
    def validate_config(self, game_type: str, 
                       config: Dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate configuration against constraints"""
        schema = self.configs.get(game_type)
        if not schema:
            return False, ["Unknown game type"]
        
        errors = []
        constraints = schema.config_constraints
        
        for key, value in config.items():
            if key in constraints:
                constraint = constraints[key]
                
                # Type validation
                if "type" in constraint:
                    expected_type = constraint["type"]
                    if not isinstance(value, expected_type):
                        errors.append(
                            f"{key} must be {expected_type.__name__}"
                        )
                
                # Range validation
                if "range" in constraint and isinstance(value, (int, float)):
                    min_val, max_val = constraint["range"]
                    if not (min_val <= value <= max_val):
                        errors.append(
                            f"{key} must be between {min_val} and {max_val}"
                        )
                
                # Options validation
                if "options" in constraint:
                    if value not in constraint["options"]:
                        errors.append(
                            f"{key} must be one of {constraint['options']}"
                        )
        
        return len(errors) == 0, errors
    
    def can_modify_runtime(self, game_type: str, 
                          param: str) -> bool:
        """Check if parameter can be modified at runtime"""
        schema = self.configs.get(game_type)
        if not schema:
            return False
        return param in schema.runtime_modifiable
```

Example configuration file (`config/snake.json`):

```json
{
  "game_type": "snake",
  "version": "1.0.0",
  "default_config": {
    "grid_size": 10,
    "initial_speed": 500,
    "speed_increment": 0,
    "enable_walls": true,
    "enable_self_collision": true,
    "food_growth_rate": 1,
    "max_score": null
  },
  "config_constraints": {
    "grid_size": {
      "type": "int",
      "range": [5, 30]
    },
    "initial_speed": {
      "type": "int",
      "range": [100, 2000]
    },
    "speed_increment": {
      "type": "float",
      "range": [0, 0.5]
    },
    "enable_walls": {
      "type": "bool"
    },
    "enable_self_collision": {
      "type": "bool"
    },
    "food_growth_rate": {
      "type": "int",
      "range": [1, 5]
    },
    "max_score": {
      "type": "int",
      "min": 0
    }
  },
  "runtime_modifiable": [
    "initial_speed"
  ]
}
```

## 5. Implementation Roadmap

### Phase 1: Core Infrastructure (Week 1)
- [ ] Implement IGameStateManager interface
- [ ] Implement IGameLogic interface
- [ ] Create LangGraph orchestrator skeleton
- [ ] Set up basic FastAPI endpoints
- [ ] Implement ConfigManager

### Phase 2: Snake Game Implementation (Week 2)
- [ ] Implement SnakeGameLogic class
- [ ] Create LangGraph workflow for Snake
- [ ] Implement REST API handlers
- [ ] Create frontend Canvas renderer
- [ ] Implement input handling

### Phase 3: Testing & Refinement (Week 3)
- [ ] Unit tests for core components
- [ ] E2E tests with Playwright
- [ ] Performance optimization
- [ ] Documentation completion

## 6. Technology Stack

### Backend
- **Python 3.12+**: Core language
- **FastAPI**: REST API framework
- **LangGraph**: State machine orchestration
- **Pydantic**: Data validation
- **Redis**: Session state storage (optional for MVP)

### Frontend
- **React 18+**: UI framework
- **TypeScript**: Type safety
- **Canvas API**: Game rendering
- **Vite**: Build tool

### Testing
- **Playwright**: E2E testing
- **Pytest**: Backend testing
- **Jest**: Frontend testing

## 7. Security Considerations

1. **Session Security**: UUID-based session IDs with expiration
2. **Input Validation**: All player actions validated on server
3. **Rate Limiting**: Prevent abuse of action submissions
4. **CORS**: Configured for allowed origins only

## 8. Performance Targets

- **API Response Time**: < 50ms for state queries
- **Action Processing**: < 20ms for action validation and processing
- **Frame Rate**: Target 30 FPS minimum for game rendering
- **Session Capacity**: Support 100+ concurrent sessions (MVP)

## 9. Future Enhancements

1. **WebSocket Support**: Real-time bidirectional communication
2. **Multiplayer Mode**: Support for competitive and cooperative play
3. **Replay System**: Record and replay game sessions
4. **Analytics**: Player behavior tracking and game telemetry
5. **AI Opponents**: Bot players using LangGraph agents
6. **Leaderboards**: Global score tracking

## 10. Conclusion

This architecture provides a solid foundation for Game Studio's game engine module layer, emphasizing modularity, extensibility, and separation of concerns. The generic interfaces and LangGraph integration make it easy to add new game types while maintaining consistent behavior across the platform.
