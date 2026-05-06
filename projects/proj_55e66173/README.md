# 贪吃蛇游戏 - Snake Game

Classic Snake Game implemented with React and TypeScript.

## Features

- **State Management**: Uses `useReducer` for managing 4 game states (Menu/Playing/Paused/GameOver)
- **Canvas Rendering**: Optimized Canvas API rendering for smooth gameplay
- **Performance**: Achieves ≥30fps with requestAnimationFrame
- **Input Handling**: Responsive keyboard controls with ≤100ms latency
- **High Score**: Persists high score using localStorage
- **Responsive Design**: Adapts to different screen sizes

## Tech Stack

- **React 18**: Component-based UI
- **TypeScript**: Type-safe development
- **Canvas API**: Hardware-accelerated rendering
- **CSS**: Modern styling with CSS variables

## Architecture

### Component Structure

```
GameContainer (useReducer state management)
├── GameCanvas (Canvas rendering)
└── GameUI (UI overlays)
    ├── Start Screen
    ├── HUD (score display)
    ├── Pause Screen
    └── Game Over Screen
```

### Separation of Concerns

- **Game Logic** (`gameLogic.ts`): Pure functions for game mechanics
  - Snake movement and collision detection
  - Food generation
  - Score calculation
  - High score persistence

- **State Management** (`GameContainer.tsx`): React state with useReducer
  - UI state (Menu/Playing/Paused/GameOver)
  - Game physics state
  - Keyboard event handling

- **Rendering** (`GameCanvas.tsx`): Canvas rendering logic
  - Snake visualization with gradient effect
  - Food with pulsing animation
  - Background and grid rendering

- **UI Components** (`GameUI.tsx`): Overlay UI elements
  - Start screen with high score
  - HUD for score display
  - Pause/Game Over screens

## Development

### Install Dependencies

```bash
npm install
```

### Run Development Server

```bash
npm run dev
```

### Build for Production

```bash
npm run build
```

### Run Tests

```bash
npm test
```

### Test Coverage

```bash
npm run test:coverage
```

## Game Controls

- **Arrow Keys** or **WASD**: Change direction
- **Esc** or **P**: Pause/Resume game

## Performance Metrics

- **Target FPS**: ≥30fps (achieves 60fps on modern devices)
- **Input Latency**: ≤100ms
- **Grid System**: 20x20 grid
- **Canvas Size**: Responsive (min(90vw, 80vmin))

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

## File Structure

```
src/
├── types.ts           # TypeScript type definitions
├── gameLogic.ts       # Pure game logic functions
├── GameCanvas.tsx     # Canvas rendering component
├── GameUI.tsx         # UI overlay components
├── GameContainer.tsx  # Main container with state management
├── Game.css           # Component styles
└── index.tsx          # Entry point
```

## Integration

To integrate this game into your React application:

```tsx
import { GameContainer } from '@game-studio/snake-game';

function App() {
  return <GameContainer />;
}
```

With custom configuration:

```tsx
import { GameContainer } from '@game-studio/snake-game';

const customConfig = {
  gridSize: 25,
  initialSpeed: 120,
  speedIncrement: 3,
  minSpeed: 40,
  foodScore: 15,
  canvasSize: 800
};

function App() {
  return <GameContainer config={customConfig} />;
}
```

## License

MIT
