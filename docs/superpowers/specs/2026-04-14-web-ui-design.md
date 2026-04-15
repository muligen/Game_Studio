# Game Studio Web UI Design

## Summary

Add a web-based user interface to the Game Studio collaboration kernel, providing board-centric visualization and interaction for requirements, design docs, balance tables, bugs, and logs. The UI is a thin visualization layer over the existing backend architecture, with real-time updates via WebSocket and file system monitoring.

## Goals

- Provide a visual, board-centric interface for the collaboration kernel
- Enable real-time collaboration for multiple users
- Maintain CLI parity - all CLI operations have UI equivalents
- Keep the existing backend architecture unchanged
- Prepare for future remote deployment while prioritizing local development

## Non-Goals

- No database migration - continue using JSON file storage
- No authentication in Phase 1 - localhost only
- No mobile responsive design - desktop-first
- No offline mode - requires active server connection

## Project Context

The existing Game Studio kernel has:

- **Domain layer**: `RequirementCard`, `DesignDoc`, `BalanceTable`, `BugCard`, `ActionLog` schemas
- **State machines**: Strict transition rules for requirements and bugs
- **Storage**: Local JSON files under `.studio-data/`
- **CLI**: Typer-based command-line interface
- **LangGraph integration`: Workflow execution graphs

The architecture is explicitly designed to be "ready for a later UI without requiring redesign."

## Architecture

### Overall Structure

```
┌─────────────────────────────────────────────────────────────┐
│                      Web UI Layer (New)                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────┐         ┌─────────────────────────┐    │
│  │   Frontend      │         │   Backend (FastAPI)     │    │
│  │   React +       │◄────────┤   /api/* endpoints      │    │
│  │   shadcn/ui     │  HTTP   │   WebSocket /ws         │    │
│  └─────────────────┘         └─────────────────────────┘    │
│                                       │                      │
│                                       ▼                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Existing Backend (No Changes)           │   │
│  │  studio/domain/    │  studio/storage/  │  schemas/  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
Game_Studio/
├── studio/
│   ├── api/                    # NEW: FastAPI backend
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI app factory
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── requirements.py
│   │   │   ├── design_docs.py
│   │   │   ├── balance_tables.py
│   │   │   ├── bugs.py
│   │   │   ├── logs.py
│   │   │   └── workflows.py
│   │   ├── websocket.py        # WebSocket + file watcher
│   │   └── models.py           # API request/response models
│   ├── domain/                 # EXISTING: no changes
│   ├── storage/                # EXISTING: no changes
│   ├── schemas/                # EXISTING: no changes
│   └── ...
├── web/                         # NEW: React frontend
│   ├── src/
│   │   ├── pages/
│   │   │   ├── RequirementsBoard.tsx
│   │   │   ├── RequirementDetail.tsx
│   │   │   ├── BugsBoard.tsx
│   │   │   └── Logs.tsx
│   │   ├── components/
│   │   │   ├── board/
│   │   │   │   ├── KanbanBoard.tsx
│   │   │   │   ├── KanbanColumn.tsx
│   │   │   │   └── Card.tsx
│   │   │   ├── editors/
│   │   │   │   ├── DesignEditor.tsx
│   │   │   │   └── BalanceTableEditor.tsx
│   │   │   └── common/
│   │   │       ├── StatusBadge.tsx
│   │   │       └── ActionButtons.tsx
│   │   ├── hooks/
│   │   │   ├── useWorkspace.ts
│   │   │   └── useWebSocket.ts
│   │   ├── lib/
│   │   │   ├── api.ts
│   │   │   └── types.ts         # Generated from Pydantic
│   │   └── main.tsx
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
├── pyproject.toml               # EXTENDED: add FastAPI deps
└── langgraph.json               # EXISTING: no changes
```

## Key Design Principles

### 1. Backend-First Preservation

The API layer is a **thin wrapper** around existing domain and storage logic:

```python
# studio/api/routes/requirements.py
from fastapi import APIRouter, HTTPException
from pathlib import Path
from studio.storage.workspace import StudioWorkspace
from studio.domain.requirement_flow import transition_requirement

router = APIRouter()

@router.post("/requirements/{req_id}/transition")
async def transition_requirement_status(
    workspace: str,
    req_id: str,
    next_status: str
) -> RequirementCard:
    """Reuses existing domain logic - no business rules here."""
    store = StudioWorkspace(Path(workspace) / ".studio-data")
    requirement = store.requirements.get(req_id)
    updated = transition_requirement(requirement, next_status)
    store.requirements.save(updated)
    return updated
```

### 2. Type Safety Across Boundary

Use openapi-typescript to generate TypeScript types from FastAPI's auto-generated OpenAPI schema:

```bash
# Step 1: Start FastAPI server (auto-generates /openapi.json)
uv run uvicorn studio.api.main:app

# Step 2: Generate TypeScript types from OpenAPI schema
npx openapi-typescript http://localhost:8000/openapi.json -o web/src/lib/types.ts
```

This creates end-to-end type safety: Pydantic models → OpenAPI → TypeScript types.

### 3. Real-Time Synchronization

File system watcher detects changes and broadcasts via WebSocket:

```python
# studio/api/websocket.py
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class WorkspaceWatcher(FileSystemEventHandler):
    def __init__(self, broadcaster: WebSocketBroadcaster):
        self.broadcaster = broadcaster

    def on_modified(self, event):
        if event.src_path.endswith('.json'):
            # Parse file path to determine entity type and ID
            # Broadcast update to all connected clients
            self.broadcaster.broadcast({
                "type": "entity_changed",
                "entity_type": extract_type(event.src_path),
                "entity_id": extract_id(event.src_path)
            })
```

## Pages and Components

### Page 1: Requirements Board (Kanban)

**Route:** `/requirements`

**Components:**
- `KanbanBoard` - Container with scrollable columns
- `KanbanColumn` - Single status column with cards
- `RequirementCard` - Individual requirement card

**Features:**
- Drag-and-drop for valid state transitions
- Real-time card movement synchronization
- Filter by priority, owner
- Search by title or ID

**State Transitions:**
Visual indicators for valid vs invalid transitions based on `studio/domain/requirement_flow.py`

### Page 2: Requirement Detail

**Route:** `/requirements/:id`

**Components:**
- `RequirementHeader` - Status, priority, actions
- `LinkedDesignDoc` - View/edit linked design doc
- `LinkedBalanceTables` - List of balance tables
- `LinkedBugs` - Bug cards referencing this requirement
- `ActionLogTimeline` - Chronological action history

**Features:**
- Inline status changes (valid options only)
- Quick actions: Run Design, Run Dev, Run QA
- Real-time updates when linked entities change

### Page 3: Design Editor

**Route:** `/design-docs/:id`

**Components:**
- `DesignEditor` - Main editor form
- `FieldListEditor` - For core_rules, acceptance_criteria, open_questions
- `ApprovalActions` - Approve/Send Back buttons

**Features:**
- Editable fields with validation
- Live preview
- Status badge and actions
- Comparison view (before/after)

### Page 4: Balance Table Editor

**Route:** `/balance-tables/:id`

**Components:**
- `SpreadsheetGrid` - Excel-like table interface
- `CellEditor` - Inline cell editing
- `ColumnManager` - Add/remove columns
- `LockIndicator` - Show locked cells

**Features:**
- Direct cell editing
- Lock/unlock cells
- Add/remove rows and columns
- Validation for numeric cells
- "Let AI rebalance" action

### Page 5: Bugs Board

**Route:** `/bugs`

**Similar to Requirements Board but with:**
- Severity color coding (low=gray, medium=yellow, high=orange, critical=red)
- Reopen count badge (≥3 flashes red)
- `needs_user_decision` cards highlighted

### Page 6: Logs

**Route:** `/logs`

**Components:**
- `LogTimeline` - Chronological log list
- `LogFilters` - Filter by actor, action, target type
- `LogDetails` - Expandable details for each log entry

## Real-Time Updates

### WebSocket Protocol

**Connection:** `ws://localhost:8000/ws`

**Client → Server Messages:**
```typescript
// Subscribe to workspace updates
{ "type": "subscribe", "workspace": ".runtime-data" }

// Unsubscribe
{ "type": "unsubscribe" }
```

**Server → Client Messages:**
```typescript
// Entity changed (create/update/delete)
{
  "type": "entity_changed",
  "entity_type": "requirement" | "design_doc" | "balance_table" | "bug" | "log",
  "entity_id": string,
  "action": "created" | "updated" | "deleted",
  "timestamp": string
}

// Workflow execution progress
{
  "type": "workflow_progress",
  "workflow": "design" | "dev" | "qa" | "quality",
  "requirement_id": string,
  "status": "started" | "running" | "completed" | "failed",
  "message": string
}
```

### File Watching Strategy

Use Python's `watchdog` library to monitor `.studio-data/`:

```python
observer = Observer()
watcher = WorkspaceWatcher(broadcaster)
observer.schedule(watcher, path=".studio-data", recursive=True)
observer.start()
```

**Debouncing:** Batch rapid file changes within 100ms windows to avoid excessive WebSocket traffic.

## Tech Stack

### Backend

- **FastAPI** - Async web framework with auto-generated OpenAPI docs
- **WebSocket** - Real-time bidirectional communication
- **watchdog** - File system monitoring
- **uvicorn** - ASGI server (dev: `uvicorn studio.api:app --reload`)

### Frontend

- **React 18** - UI framework
- **Vite** - Build tool and dev server
- **TypeScript** - Type safety
- **shadcn/ui** - Accessible component library built on Radix UI
- **Tanstack Query** - Server state management and caching
- **dnd-kit** - Drag and drop for kanban
- **zustand** - Lightweight client state
- **tailwindcss** - Utility-first CSS

### Development Tools

- ** concurrently** - Run frontend and backend together
- **openapi-typescript** - Generate API client types

## API Design

### REST Endpoints

```
GET    /api/requirements           - List all requirements
POST   /api/requirements           - Create requirement
GET    /api/requirements/:id       - Get requirement detail
PATCH  /api/requirements/:id       - Update requirement
POST   /api/requirements/:id/transition - Change status

GET    /api/design-docs            - List design docs
POST   /api/design-docs            - Create design doc
GET    /api/design-docs/:id        - Get design doc detail
PATCH  /api/design-docs/:id        - Update design doc
POST   /api/design-docs/:id/approve - Approve design
POST   /api/design-docs/:id/send-back - Send back with reason

GET    /api/balance-tables         - List balance tables
POST   /api/balance-tables         - Create balance table
GET    /api/balance-tables/:id     - Get balance table detail
PATCH  /api/balance-tables/:id     - Update balance table

GET    /api/bugs                   - List bugs
POST   /api/bugs                   - Create bug
GET    /api/bugs/:id               - Get bug detail
PATCH  /api/bugs/:id               - Update bug
POST   /api/bugs/:id/transition    - Change bug status

GET    /api/logs                   - List action logs
GET    /api/workflows/run-design   - Trigger design workflow
GET    /api/workflows/run-dev      - Trigger dev workflow
GET    /api/workflows/run-qa       - Trigger qa workflow
```

### Error Handling

All errors follow this format:

```json
{
  "error": {
    "code": "INVALID_TRANSITION",
    "message": "Cannot transition from 'draft' to 'done'",
    "details": {
      "current_status": "draft",
      "requested_status": "done",
      "valid_transitions": ["designing"]
    }
  }
}
```

## Authentication and Authorization (Phase 2 Preparation)

### Phase 1: No Auth

- All endpoints are public
- Server listens on `localhost:8000` only
- CORS configured for `localhost:5173` (Vite dev server)

### Phase 2: Auth Extension Points

Design the API with auth in mind:

```python
# studio/api/main.py
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer

security = HTTPBearer(auto_error=False)  # Optional for Phase 1

async def get_current_user(token: str = Depends(security)):
    """Phase 1: returns None. Phase 2: validate and return user."""
    if token is None:
        return None  # No auth in Phase 1
    # Phase 2: Validate token and return user
    return validate_token(token)

@app.get("/api/requirements")
async def list_requirements(
    workspace: str,
    user: dict | None = Depends(get_current_user)
):
    # user可用于日志记录，但Phase 1不用于权限检查
    ...
```

## Testing Strategy

### Backend Tests

- **API tests**: Use FastAPI's `TestClient`
- **WebSocket tests**: Mock file watcher, test broadcast behavior
- **Integration tests**: Verify API → domain → storage flow

### Frontend Tests

- **Component tests**: Vitest + React Testing Library
- **E2E tests**: Playwright (optional, for critical flows)

### Contract Tests

- Ensure TypeScript types match Pydantic models
- Run as part of CI pipeline

## Development Workflow

### Starting Development Server

```bash
# Terminal 1: Backend
uv run uvicorn studio.api.main:app --reload --port 8000

# Terminal 2: Frontend
cd web
npm run dev
```

### Combined Start (via npm script)

```json
// package.json
{
  "scripts": {
    "dev": "concurrently \"uv run uvicorn studio.api.main:app --reload --port 8000\" \"npm run dev:vite\"",
    "dev:vite": "vite"
  }
}
```

### Building for Production

```bash
# Build frontend
cd web && npm run build

# Copy built files to static dir
cp -r dist ../studio/api/static/
```

## Performance Considerations

### List Pagination

For large workspaces, implement cursor-based pagination:

```python
@app.get("/api/requirements")
async def list_requirements(
    workspace: str,
    cursor: str | None = None,
    limit: int = 50
):
    ...
```

### WebSocket Reconnection

Frontend should handle disconnections gracefully:

```typescript
const { reconnect } = useWebSocket();
// Auto-reconnect with exponential backoff
```

## Deployment Strategy (Phase 2+)

### Current (Phase 1)

- Single machine, local development
- `localhost:8000` for API
- `localhost:5173` for frontend

### Future (Phase 2)

- Backend deployed to cloud server
- Frontend built and served as static files
- Nginx reverse proxy for routing
- HTTPS via Let's Encrypt

## Success Criteria

Phase 1 is complete when:

1. All core pages are functional (Requirements, Bugs, Design, Balance Tables, Logs)
2. Real-time updates work when files change via CLI
3. Drag-and-drop state transitions enforce domain rules
4. All CRUD operations have both CLI and UI equivalents
5. TypeScript types match Pydantic models
6. WebSocket connection handles disconnections gracefully
7. API is well-documented with OpenAPI/Swagger

## Open Decisions

These are intentionally deferred:

- Whether to use a bundler for production or serve modules directly
- Exact WebSocket message format for complex updates
- Whether to include a LangGraph visualization page
- OAuth vs JWT vs API keys for Phase 2 authentication

## Migration Path

### From Phase 1 to Phase 2

1. Extract API to separate repository
2. Add authentication middleware
3. Deploy to cloud server
4. Configure CORS for production domain
5. Add database for better query performance
6. Keep file-based storage as backup/sync mechanism
