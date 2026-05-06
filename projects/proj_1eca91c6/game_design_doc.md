# Snake Game MVP - Game Design Document

## Document Information
- **Project**: Snake Game MVP
- **Version**: 1.0
- **Status**: Approved
- **Date**: 2026-05-06
- **Platform**: Web Browser

---

## 1. Game Overview

### 1.1 Concept
A classic Snake game implementation as a demonstration of the Game Studio multi-agent architecture. The MVP focuses on core gameplay mechanics while showcasing the collaboration between design, development, and QA agents.

### 1.2 Target Audience
- Internal stakeholders evaluating Game Studio capabilities
- Technical team members demonstrating multi-agent workflow
- Potential users seeking a nostalgic retro gaming experience

### 1.3 Design Philosophy
- **Simplicity First**: Focus on polished core mechanics over feature breadth
- **Retro Aesthetic**: Classic pixel art style for nostalgic appeal
- **Technical Showcase**: Demonstrate clean separation of concerns between frontend (React), backend (FastAPI), and game logic (LangGraph)

---

## 2. Core Game Mechanics

### 2.1 Movement System
- **Grid-Based Movement**: Snake moves one grid cell at a time
- **Continuous Movement**: Snake automatically moves in the current direction every game tick
- **Direction Control**: Player changes direction using keyboard inputs
- **Anti-Reversal Rule**: Snake cannot reverse direction (180° turn)
  - If moving UP, cannot move DOWN
  - If moving LEFT, cannot move RIGHT
  - Attempted reversal is ignored, not game-ending

### 2.2 Snake Structure
- **Head Segment**: Leading segment that determines movement direction
- **Body Segments**: Trail segments following the head
- **Initial State**: Snake starts with 3 segments (head + 2 body segments)
- **Growth Mechanism**: Snake grows by 1 segment each time food is consumed

### 2.3 Food System
- **Spawning**: Food appears at a random grid position
- **Collision Rule**: Food cannot spawn on any snake segment (head or body)
- **Consumption**: When snake head occupies food cell:
  - Snake grows by 1 segment
  - Score increases by 1 point
  - Food immediately respawns at new random location
- **Visual Representation**: Distinct color/icon from snake and background

### 2.4 Collision Detection
#### Wall Collision
- Game ends when snake head attempts to move outside grid boundaries
- No wraparound (walls are lethal)

#### Self Collision
- Game ends when snake head collides with any body segment
- Includes collision with tail end

### 2.5 Scoring System
- **Point Value**: 1 point per food item consumed
- **Score Display**: Real-time score shown on game UI
- **Final Score**: Displayed on game over screen

### 2.6 Game States
1. **IDLE**: Initial state, waiting for game start
2. **PLAYING**: Active gameplay
3. **GAME_OVER**: Collision detected, game ended
4. **RESTART_READY**: Game over state awaiting restart

---

## 3. Grid Configuration

### 3.1 Grid Dimensions
- **Size**: 10x10 grid
- **Rationale**: Compact and simple, ideal for quick games and mobile screens
- **Cell Representation**: Square cells of equal size
- **Total Cells**: 100 cells

### 3.2 Coordinate System
- **Origin**: Top-left corner (0, 0)
- **X Axis**: Horizontal (left to right, 0-9)
- **Y Axis**: Vertical (top to bottom, 0-9)

### 3.3 Grid Visualization
```
  0 1 2 3 4 5 6 7 8 9
0 . . . . . . . . . .
1 . . . . . . . . . .
2 . . . . . . . . . .
3 . . . . . . . . . .
4 . . . . . . . . . .
5 . . . . . . . . . .
6 . . . . . . . . . .
7 . . . . . . . . . .
8 . . . . . . . . . .
9 . . . . . . . . . .
```

---

## 4. Speed Settings

### 4.1 Game Speed
- **Fixed Tick Rate**: 500ms per step (2 steps per second)
- **Rationale**: Simpler MVP implementation, balanced gameplay pace
- **Performance Target**: Minimum 30 FPS for smooth rendering

### 4.2 Timing Mechanism
- **Frontend-Driven**: Client uses `requestAnimationFrame` for rendering loop
- **Server Validation**: Game state validation requested from server
- **Tick Accumulator**: Frontend tracks time since last game tick to maintain consistent speed

---

## 5. Control Scheme

### 5.1 Primary Controls (Keyboard)
- **Arrow Keys**: Primary directional control
  - ↑ / Up Arrow: Move UP
  - ↓ / Down Arrow: Move DOWN
  - ← / Left Arrow: Move LEFT
  - → / Right Arrow: Move RIGHT
- **WASD Keys**: Alternative directional control
  - W: Move UP
  - S: Move DOWN
  - A: Move LEFT
  - D: Move RIGHT

### 5.2 Game Control Buttons
- **Start Game Button**: Initiates gameplay from IDLE state
- **Restart Button**: Resets game and starts new game after GAME_OVER

### 5.3 Input Handling
- **Focus Requirement**: Game window must have focus for keyboard input
- **Event Buffering**: Prevent multiple direction changes in single tick
- **Queue System**: Input queued for next tick if received during tick processing

### 5.4 Excluded Controls (Post-MVP)
- Mobile touch/swipe controls
- Game pause functionality
- Speed adjustment controls
- High score recording

---

## 6. Visual Style

### 6.1 Art Direction
- **Style**: Pixel Retro (8-bit aesthetic)
- **Inspiration**: Classic arcade games (late 1970s - early 1980s)
- **Emotional Tone**: Nostalgic, fun, approachable

### 6.2 Color Palette
- **Background**: Dark green/black (#0F380F)
- **Snake Head**: Bright green (#9BBC0F)
- **Snake Body**: Medium green (#8BAC0F)
- **Food**: Red/magenta (#E0F8CF with red accent)
- **Grid Lines**: Subtle dark green (#306230)
- **UI Text**: Light green (#9BBC0F)

### 6.3 Visual Elements
#### Snake Rendering
- **Pixel-Art Style**: Blocky, square segments
- **Head Distinction**: Slightly larger or different shade from body
- **Body Segments**: Uniform size, connected appearance

#### Food Rendering
- **Distinct Icon**: Apple or simple pixel art shape
- **Animation**: Subtle pulse or glow effect (if time permits)

#### UI Design
- **Retro Font**: Pixel-style font (e.g., Press Start 2P or similar)
- **Button Style**: Chunky, pixel-border buttons
- **Score Display**: Large, prominent numbers in retro style

### 6.4 Canvas vs DOM
- **Rendering Method**: HTML5 Canvas API
- **Rationale**: Better performance for frequent updates, pixel-perfect control

---

## 7. User Interface Layout

### 7.1 Screen Layout
```
┌─────────────────────────────────┐
│      GAME STUDIO SNAKE          │
├─────────────────────────────────┤
│                                 │
│         Score: 15               │
│                                 │
│  ┌─────────────────────────┐   │
│  │                         │   │
│  │     [GAME CANVAS]       │   │
│  │       10x10 GRID        │   │
│  │                         │   │
│  └─────────────────────────┘   │
│                                 │
│  [START GAME] [RESTART]        │
│                                 │
│  Arrow Keys or WASD to Move    │
└─────────────────────────────────┘
```

### 7.2 Game Over Screen
```
┌─────────────────────────────────┐
│      GAME OVER!                 │
│                                 │
│      Final Score: 15            │
│                                 │
│      [PLAY AGAIN]               │
└─────────────────────────────────┘
```

---

## 8. Technical Architecture Integration

### 8.1 Component Responsibilities
- **React (Frontend)**:
  - Canvas rendering
  - User input capture
  - Game loop management (requestAnimationFrame)
  - UI state display

- **FastAPI (Backend)**:
  - Game state validation API
  - Initial game configuration
  - Game session management

- **LangGraph (Game Logic)**:
  - State machine for game states
  - Movement validation
  - Collision detection
  - Score tracking

### 8.2 Data Flow
1. User presses direction key
2. Frontend captures input
3. Frontend sends move request to backend
4. Backend validates move via LangGraph
5. Backend returns updated game state
6. Frontend renders new state

---

## 9. MVP Feature Scope

### 9.1 Included Features ✓
- Single-player gameplay
- 10x10 grid
- Classic snake movement and growth
- Food consumption and scoring
- Wall and self-collision detection
- Game over and restart functionality
- Keyboard controls (Arrow keys + WASD)
- Fixed game speed (500ms/tick)
- Pixel retro visual style
- Real-time score display
- Canvas-based rendering

### 9.2 Explicitly Excluded Features ✗
- Mobile touch/swipe controls
- Pause functionality
- High score persistence
- Multiple difficulty levels
- Speed adjustment during gameplay
- Sound effects and music
- Multiplayer mode
- Leaderboards
- Game save/load
- Tutorial or help screens
- Settings/configuration screen
- Achievements or badges

---

## 10. Game Balance Considerations

### 10.1 Difficulty Factors
- **Grid Size**: 10x10 provides quick games with moderate difficulty
- **Speed**: 500ms per tick is accessible for beginners
- **Growth Rate**: 1 segment per food creates steady difficulty increase

### 10.2 Play Session Length
- **Estimated Duration**: 30-90 seconds per game
- **Target Score Range**: 10-30 points typical for casual play

### 10.3 Skill Progression
- **Beginner**: Can achieve scores of 5-10 with minimal practice
- **Intermediate**: Scores of 15-25 require understanding of space management
- **Advanced**: Scores above 30 require planning and precise control

---

## 11. Acceptance Criteria

The Snake Game MVP is considered complete when:

### 11.1 Core Mechanics
- [ ] Snake moves smoothly in four directions (UP, DOWN, LEFT, RIGHT)
- [ ] Snake cannot reverse direction (180° turn)
- [ ] Snake grows by 1 segment when consuming food
- [ ] Food spawns at random valid locations (not on snake)
- [ ] Score increments by 1 for each food consumed
- [ ] Game ends on wall collision
- [ ] Game ends on self-collision
- [ ] Final score displayed on game over

### 11.2 Grid and Speed
- [ ] Grid is exactly 10x10 cells
- [ ] Game tick occurs every 500ms (±50ms tolerance)
- [ ] Visual rendering maintains ≥30 FPS

### 11.3 Controls
- [ ] Arrow keys control snake direction
- [ ] WASD keys control snake direction
- [ ] Start button begins game
- [ ] Restart button resets and starts new game
- [ ] Input properly buffered (no rapid-fire glitches)

### 11.4 Visual Style
- [ ] Pixel retro aesthetic implemented
- [ ] Color palette matches specification
- [ ] Snake head visually distinct from body
- [ ] Food clearly visible and distinct
- [ ] Score clearly displayed
- [ ] Game over screen shows final score

### 11.5 Technical Integration
- [ ] FastAPI backend provides game state validation
- [ ] React frontend renders Canvas UI
- [ ] LangGraph manages game state machine
- [ ] Game playable end-to-end without errors
- [ ] No console errors or warnings during gameplay

---

## 12. Open Questions for Future Iterations

### 12.1 Post-MVP Features
1. Should we add difficulty levels (slow/medium/fast)?
2. Is high score persistence (localStorage) desired?
3. Should we implement pause functionality?
4. Would mobile touch controls increase accessibility?
5. Are sound effects worth adding for gameplay feedback?

### 12.2 Technical Enhancements
1. Should we add WebSocket support for real-time multiplayer?
2. Would a generalized game engine module benefit the framework?
3. Should we implement replay/recording functionality?
4. Is procedural map generation worth exploring?

### 12.3 Design Refinements
1. Should we add power-ups or special food types?
2. Would obstacle courses add variety?
3. Should we implement daily challenges or modes?
4. Is a level progression system desirable?

---

## 13. Risk Mitigation

### 13.1 Identified Risks
- **Risk**: LangGraph state machine complexity may introduce bugs in simple game
- **Mitigation**: Thorough unit testing of state transitions, extensive playtesting

- **Risk**: Rapid keyboard input may cause state inconsistency
- **Mitigation**: Implement proper input buffering and queue system

- **Risk**: Browser compatibility issues with Canvas
- **Mitigation**: Test on Chrome, Firefox, Safari, Edge; use standard Canvas API

- **Risk**: Food generation algorithm may create positions on snake body
- **Mitigation**: Validate food spawn position against all snake segments

### 13.2 Performance Considerations
- Ensure 500ms tick rate is consistent across different devices
- Optimize Canvas rendering for smooth 30+ FPS
- Monitor memory usage for potential leaks in long play sessions

---

## 14. Success Metrics

### 14.1 Technical Success
- Game runs without critical bugs
- Frame rate maintains ≥30 FPS
- State management is predictable and reliable
- Multi-agent architecture is clearly demonstrated

### 14.2 User Experience Success
- Controls feel responsive and intuitive
- Visual style is coherent and appealing
- Game length is appropriate for quick sessions
- Rules are clear without needing explanation

### 14.3 Framework Demonstration Success
- Clean separation between frontend, backend, and game logic
- Easy to understand for new developers
- Shows potential for more complex games
- Successfully showcases multi-agent collaboration

---

## Appendix A: Game Flow Diagram

```
[USER LAUNCHES GAME]
        ↓
[INITIAL STATE: IDLE]
        ↓
[USER CLICKS "START GAME"]
        ↓
[GAME STATE: PLAYING]
        ↓
[GAME LOOP]
  ├─→ [WAIT FOR TICK (500ms)]
  ├─→ [PROCESS USER INPUT]
  ├─→ [UPDATE SNAKE POSITION]
  ├─→ [CHECK COLLISIONS]
  │   ├─→ [WALL COLLISION?] → GAME OVER
  │   ├─→ [SELF COLLISION?] → GAME OVER
  │   └─→ [FOOD COLLISION?] → GROW + SCORE + RESPAWN FOOD
  └─→ [RENDER TO CANVAS]
        ↓
[GAME OVER DETECTED]
        ↓
[DISPLAY FINAL SCORE]
        ↓
[USER CLICKS "RESTART"]
        ↓
[RESET AND RETURN TO PLAYING]
```

---

## Appendix B: Keyboard Input Matrix

| Current Direction | Valid Inputs | Invalid Inputs |
|------------------|--------------|----------------|
| UP               | LEFT, RIGHT  | DOWN           |
| DOWN             | LEFT, RIGHT  | UP             |
| LEFT             | UP, DOWN     | RIGHT          |
| RIGHT            | UP, DOWN     | LEFT           |

---

## Document Revision History

| Version | Date       | Author      | Changes               |
|---------|------------|-------------|-----------------------|
| 1.0     | 2026-05-06 | Design Agent | Initial MVP release   |

---

*This document is approved for implementation as the MVP specification for the Snake Game project in the Game Studio framework.*
