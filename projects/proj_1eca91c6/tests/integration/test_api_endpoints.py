"""
Integration tests for Snake Game API endpoints.

Tests REST API functionality end-to-end using FastAPI TestClient.
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from api import app


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def session_id(client):
    """Create a game session and return its ID."""
    response = client.post("/api/snake/start", json={
        "player_id": "test_player",
        "config": {
            "grid_size": 10,
            "initial_speed": 500,
        }
    })
    assert response.status_code == 201
    return response.json()["session_id"]


class TestGameStart:
    """Tests for POST /api/snake/start endpoint."""

    def test_start_game_default_config(self, client):
        """Test starting a game with default configuration."""
        response = client.post("/api/snake/start", json={
            "player_id": "test_player"
        })

        assert response.status_code == 201

        data = response.json()
        assert "session_id" in data
        assert "session_info" in data
        assert "game_state" in data

        # Verify session info
        assert data["session_info"]["game_type"] == "snake"
        assert data["session_info"]["player_id"] == "test_player"
        assert data["session_info"]["state"] in ["ready", "idle"]
        assert data["session_info"]["score"] == 0

        # Verify initial game state
        game_state = data["game_state"]
        assert "snake" in game_state
        assert "food" in game_state
        assert len(game_state["snake"]) == 3  # Initial snake length
        assert game_state["score"] == 0
        assert game_state["grid_size"] == 10

    def test_start_game_custom_config(self, client):
        """Test starting a game with custom configuration."""
        response = client.post("/api/snake/start", json={
            "player_id": "test_player",
            "config": {
                "grid_size": 15,
                "initial_speed": 300,
                "enable_walls": False,
            }
        })

        assert response.status_code == 201

        data = response.json()
        game_state = data["game_state"]
        assert game_state["grid_size"] == 15

    def test_start_game_invalid_config(self, client):
        """Test starting a game with invalid configuration."""
        response = client.post("/api/snake/start", json={
            "player_id": "test_player",
            "config": {
                "grid_size": 50,  # Exceeds max of 30
            }
        })

        # FastAPI returns 422 for validation errors
        assert response.status_code in [400, 422]


class TestGameState:
    """Tests for GET /api/snake/state/{session_id} endpoint."""

    def test_get_game_state_success(self, client, session_id):
        """Test getting game state for valid session."""
        response = client.get(f"/api/snake/state/{session_id}")

        assert response.status_code == 200

        data = response.json()
        assert data["session_id"] == session_id
        assert "session_info" in data
        assert "game_state" in data

        # Verify game state structure
        game_state = data["game_state"]
        assert "snake" in game_state
        assert "food" in game_state
        assert "score" in game_state
        assert "game_over" in game_state

    def test_get_game_state_not_found(self, client):
        """Test getting game state for non-existent session."""
        response = client.get("/api/snake/state/nonexistent_session")

        assert response.status_code == 404

        data = response.json()
        # Error is in detail field for HTTPException
        assert "error" in data.get("detail", data)


class TestMoveSubmission:
    """Tests for POST /api/snake/move endpoint."""

    def test_submit_valid_move(self, client, session_id):
        """Test submitting a valid direction change."""
        response = client.post("/api/snake/move", json={
            "session_id": session_id,
            "direction": "UP"
        })

        assert response.status_code == 200

        data = response.json()
        assert data["session_id"] == session_id
        assert data["success"] is True
        assert "game_state" in data

    def test_submit_invalid_session(self, client):
        """Test submitting move for non-existent session."""
        response = client.post("/api/snake/move", json={
            "session_id": "nonexistent",
            "direction": "UP"
        })

        assert response.status_code == 404

    def test_submit_all_directions(self, client, session_id):
        """Test submitting all valid directions."""
        directions = ["UP", "DOWN", "LEFT", "RIGHT"]

        for direction in directions:
            response = client.post("/api/snake/move", json={
                "session_id": session_id,
                "direction": direction
            })

            # Some directions may be invalid (180° turns), but request should be processed
            assert response.status_code in [200, 400]


class TestGameRestart:
    """Tests for POST /api/snake/restart endpoint."""

    def test_restart_game(self, client, session_id):
        """Test restarting a game session."""
        # Make some moves first
        client.post("/api/snake/move", json={
            "session_id": session_id,
            "direction": "UP"
        })

        # Restart
        response = client.post("/api/snake/restart", json={
            "session_id": session_id
        })

        assert response.status_code == 200

        data = response.json()
        assert data["session_id"] == session_id
        assert "session_info" in data
        assert "game_state" in data

        # Verify reset state
        assert data["session_info"]["score"] == 0
        assert data["game_state"]["score"] == 0
        assert len(data["game_state"]["snake"]) == 3  # Initial length

    def test_restart_with_new_config(self, client, session_id):
        """Test restarting with new configuration."""
        response = client.post("/api/snake/restart", json={
            "session_id": session_id,
            "config": {
                "grid_size": 15,
            }
        })

        assert response.status_code == 200

        data = response.json()
        assert data["game_state"]["grid_size"] == 15

    def test_restart_nonexistent_session(self, client):
        """Test restarting non-existent session."""
        response = client.post("/api/snake/restart", json={
            "session_id": "nonexistent"
        })

        assert response.status_code == 404


class TestGameConfig:
    """Tests for GET /api/games/{game_type}/config endpoint."""

    def test_get_snake_config(self, client):
        """Test getting Snake game configuration."""
        response = client.get("/api/games/snake/config")

        assert response.status_code == 200

        data = response.json()
        assert data["game_type"] == "snake"
        assert "config" in data
        assert "constraints" in data

        # Verify config structure
        config = data["config"]
        assert "grid_size" in config
        assert "initial_speed" in config
        assert "enable_walls" in config

        # Verify constraints
        constraints = data["constraints"]
        assert "grid_size" in constraints
        assert constraints["grid_size"]["type"] == "int"
        assert constraints["grid_size"]["range"] == [5, 30]

    def test_get_config_unsupported_game(self, client):
        """Test getting config for unsupported game type."""
        response = client.get("/api/games/tetris/config")

        assert response.status_code == 404


class TestSessionListing:
    """Tests for GET /api/games/{game_type}/sessions endpoint."""

    def test_list_snake_sessions(self, client):
        """Test listing Snake game sessions."""
        # Create a few sessions
        client.post("/api/snake/start", json={"player_id": "player1"})
        client.post("/api/snake/start", json={"player_id": "player2"})

        response = client.get("/api/games/snake/sessions")

        assert response.status_code == 200

        data = response.json()
        assert data["game_type"] == "snake"
        assert "count" in data
        assert "sessions" in data
        assert isinstance(data["sessions"], list)

    def test_list_unsupported_game_sessions(self, client):
        """Test listing sessions for unsupported game type."""
        response = client.get("/api/games/tetris/sessions")

        assert response.status_code == 404


class TestErrorHandling:
    """Tests for API error handling."""

    def test_invalid_direction_format(self, client, session_id):
        """Test submitting invalid direction format."""
        response = client.post("/api/snake/move", json={
            "session_id": session_id,
            "direction": "DIAGONAL"  # Invalid direction
        })

        # Should be rejected
        assert response.status_code in [400, 422]

    def test_missing_required_fields(self, client):
        """Test requests with missing required fields."""
        # Missing direction
        response = client.post("/api/snake/move", json={
            "session_id": "some_id"
        })
        assert response.status_code == 422

    def test_malformed_json(self, client):
        """Test malformed JSON requests."""
        response = client.post(
            "/api/snake/start",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_root_endpoint(self, client):
        """Test root endpoint returns API info."""
        response = client.get("/")

        assert response.status_code == 200

        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "status" in data

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
