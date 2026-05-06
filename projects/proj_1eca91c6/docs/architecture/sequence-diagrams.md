# Game Engine Module Layer - Sequence Diagrams

## 1. Game Session Initialization Flow

```
Player                Frontend (React)          Backend (FastAPI)         LangGraph          State Manager
  |                          |                          |                      |                    |
  |---Click "Start Game"---->|                          |                      |                    |
  |                          |                          |                      |                    |
  |                          |---POST /sessions-------->|                      |                    |
  |                          |      {game_type, config} |                      |                    |
  |                          |                          |                      |                    |
  |                          |                          |---create_session()-->|                    |
  |                          |                          |                      |                    |
  |                          |                          |                      |---new session----->|
  |                          |                          |                      |                    |
  |                          |                          |<--session_id---------|                    |
  |                          |                          |                      |                    |
  |                          |                          |---initialize_game()-->|                   |
  |                          |                          |                      |                    |
  |                          |                          |<--game_data-----------|                    |
  |                          |                          |                      |                    |
  |                          |<--{session_id, state}----|                      |                    |
  |                          |                          |                      |                    |
  |<--Render Game UI---------|                          |                      |                    |
```

## 2. Player Action Processing Flow (Polling Mode)

```
Player                Frontend (React)          Backend (FastAPI)         LangGraph          Game Logic
  |                          |                          |                      |                    |
  |---Press Arrow Key--------|                          |                      |                    |
  |                          |                          |                      |                    |
  |                          |---POST /actions--------->|                      |                    |
  |                          |    {direction: "UP"}     |                      |                    |
  |                          |                          |                      |                    |
  |                          |                          |---process_action()--->|                   |
  |                          |                          |                      |                    |
  |                          |                          |                      |--validate_action()-->|
  |                          |                          |                      |                    |
  |                          |                          |                      |<--valid-------------|
  |                          |                          |                      |                    |
  |                          |                          |                      |--update_position()-->|
  |                          |                          |                      |                    |
  |                          |                          |                      |<--new_state---------|
  |                          |                          |                      |                    |
  |                          |                          |<--ActionResult---------|                    |
  |                          |                          |                      |                    |
  |                          |<--{status: "accepted"}---|                      |                    |
  |                          |                          |                      |                    |
  |                          |---GET /state------------>|                      |                    |
  |                          |                          |                      |                    |
  |                          |                          |---get_render_state()-->|                   |
  |                          |                          |                      |                    |
  |                          |                          |<--render_state---------|                    |
  |                          |                          |                      |                    |
  |                          |<--{render_state}----------|                      |                    |
  |                          |                          |                      |                    |
  |<--Render Updated Game-----|                          |                      |                    |
```

## 3. Game Over Detection Flow

```
Player                Frontend (React)          Backend (FastAPI)         LangGraph          Game Logic
  |                          |                          |                      |                    |
  |                          |                          |                      |                    |
  |                          |                          |---check_game_over()-->|                   |
  |                          |                          |                      |                    |
  |                          |                          |                      |--check_collision()-->|
  |                          |                          |                      |                    |
  |                          |                          |                      |<--collision_detected|
  |                          |                          |                      |                    |
  |                          |                          |                      |--calculate_score()-->|
  |                          |                          |                      |                    |
  |                          |                          |                      |<--final_score-------|
  |                          |                          |                      |                    |
  |                          |                          |<--(true, "wall_hit")---|                    |
  |                          |                          |                      |                    |
  |                          |                          |---transition_to(GAME_OVER)               |
  |                          |                          |                      |                    |
  |                          |<--{state: "game_over",   |                      |                    |
  |                          |    score: 15,            |                      |                    |
  |                          |    reason: "wall_hit"}---|                      |                    |
  |                          |                          |                      |                    |
  |<--Show Game Over Screen---|                          |                      |                    |
```

## 4. WebSocket Communication Flow (Future Enhancement)

```
Player                Frontend (React)          Backend (FastAPI)         WebSocket Conn.     Game Logic
  |                          |                          |                      |                    |
  |---Connect to Game--------|                          |                      |                    |
  |                          |                          |                      |                    |
  |                          |---WebSocket Connect----->|                      |                    |
  |                          |      /ws/sessions/{id}   |                      |                    |
  |                          |                          |                      |                    |
  |                          |                          |<--Connection Established--               |
  |                          |                          |                      |                    |
  |---Press Arrow Key--------|                          |                      |                    |
  |                          |                          |                      |                    |
  |                          |---WS: {action: "UP"}---->|---------------------->|                    |
  |                          |                          |                      |                    |
  |                          |                          |                      |--process_action()-->|
  |                          |                          |                      |                    |
  |                          |                          |                      |<--new_state---------|
  |                          |                          |                      |                    |
  |                          |                          |<--WS: {state: {...}}---|                    |
  |                          |                          |                      |                    |
  |<--Render Updated Game-----|                          |                      |                    |
```

## 5. Configuration Update Flow

```
Admin                Frontend (React)          Backend (FastAPI)         Config Manager
  |                          |                          |                      |
  |---Open Config Panel------|                          |                      |
  |                          |                          |                      |
  |---Change Speed to 300ms--|                          |                      |
  |                          |                          |                      |
  |                          |---POST /config---------->|                      |
  |                          |    {speed: 300}          |                      |
  |                          |                          |                      |
  |                          |                          |---validate_config()-->|
  |                          |                          |                      |
  |                          |                          |<--valid---------------|
  |                          |                          |                      |
  |                          |                          |---update_config()---->|
  |                          |                          |                      |
  |                          |<--{status: "updated"}----|                      |
  |                          |                          |                      |
  |<--Show Success Message----|                          |                      |
```

## 6. State Transition Diagram (LangGraph)

```
                    [Entry Point]
                          |
                          v
                    [Initialize Game]
                          |
                    +-----+-----+
                    |           |
                Error?         No
                    |           |
                    v           v
              [Handle Error] [Update State]
                    |           |
                    |           v
                    |     [Check Game Over]
                    |           |
                    |     +-----+-----+
                    |     |           |
                    |   Continue    Game Over
                    |     |           |
                    |     v           v
                    |  [Process      [Prepare Render]
                    |   Action]            |
                    |     |                |
                    |     +------->--------+
                    |                |
                    +------->-------+
                            |
                            v
                     [Prepare Render]
                            |
                            v
                          [END]
```

## 7. Error Handling Flow

```
Player                Frontend (React)          Backend (FastAPI)         LangGraph
  |                          |                          |                      |
  |---Submit Invalid Action--|                          |                      |
  |                          |                          |                      |
  |                          |---POST /actions--------->|                      |
  |                          |    {direction: "LEFT"}   |                      |
  |                          |   (when going RIGHT)     |                      |
  |                          |                          |                      |
  |                          |                          |---validate_action()-->|
  |                          |                          |                      |
  |                          |                          |                      |<--invalid-----------|
  |                          |                          |                      |
  |                          |                          |---transition_to(ERROR)|                   |
  |                          |                          |                      |
  |                          |                          |<--error_response-------|                    |
  |                          |                          |                      |
  |                          |<--{error: "Invalid       |                      |
  |                          |    action: 180 turn"}----|                      |
  |                          |                          |                      |
  |<--Show Error Message-----|                          |                      |
```

## Key Interaction Patterns

1. **Polling Pattern**: Frontend periodically requests state updates
2. **Event-Driven**: Player actions trigger immediate backend processing
3. **State Machine**: LangGraph manages all state transitions
4. **Validation Layer**: All actions validated before state changes
5. **Error Recovery**: Graceful handling of invalid states and actions
