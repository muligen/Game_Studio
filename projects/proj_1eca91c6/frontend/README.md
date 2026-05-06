# Snake Game UI - React Components

Classic Snake Game built with React, TypeScript, and Canvas API.

## Features

- 🎮 **Classic Snake Gameplay** - Navigate the snake to eat food and grow longer
- 🎨 **Pixel Retro Style** - 8-bit arcade aesthetic with modern CSS
- ⌨️ **Keyboard Controls** - Arrow keys or WASD for movement
- ⏸️ **Pause/Resume** - Pause the game at any time
- 🔄 **Restart** - Quick restart functionality
- 📊 **Score Tracking** - Current score and high score display
- 🏆 **High Score Detection** - Celebrates new high scores
- 📱 **Responsive Design** - Works on desktop and tablet screens
- ♿ **Accessible** - ARIA labels and keyboard navigation support
- 🧪 **Fully Tested** - Unit tests with Vitest and Testing Library

## Installation

```bash
npm install
```

## Development

```bash
npm run dev
```

## Build

```bash
npm run build
```

## Testing

```bash
npm run test
```

Run tests with UI:

```bash
npm run test:ui
```

## Usage

### Basic Usage

```tsx
import { SnakeGame } from 'snake-game-ui';

function App() {
  return (
    <SnakeGame
      config={{
        gridSize: 10,
        initialSpeed: 500,
        enableWalls: true,
        enableSelfCollision: true,
        foodGrowthRate: 1,
      }}
    />
  );
}
```

### With Callbacks

```tsx
import { SnakeGame } from 'snake-game-ui';
import { GameState } from 'snake-game-ui';

function App() {
  const handleStateChange = (state: GameState) => {
    console.log('Game state:', state);
  };

  const handleScoreChange = (score: number) => {
    console.log('Score:', score);
  };

  return (
    <SnakeGame
      onStateChange={handleStateChange}
      onScoreChange={handleScoreChange}
    />
  );
}
```

### Individual Components

You can also use individual components:

```tsx
import {
  GameCanvas,
  ScoreDisplay,
  GameControls,
  GameOverScreen,
} from 'snake-game-ui';
```

## Controls

- **Arrow Keys** or **WASD** - Move the snake
- **Space** - Start/Pause/Resume game
- **Enter** or **R** - Restart game

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `gridSize` | number | 10 | Size of the game grid (NxN) |
| `initialSpeed` | number | 500 | Game tick speed in milliseconds |
| `enableWalls` | boolean | true | Enable wall collision |
| `enableSelfCollision` | boolean | true | Enable self-collision |
| `foodGrowthRate` | number | 1 | Snake growth per food eaten |
| `maxScore` | number | undefined | Optional maximum score |

## Components

### SnakeGame

Main game component that integrates all UI elements.

### GameCanvas

Renders the game canvas with snake, food, and grid.

### ScoreDisplay

Displays current score and high score with animations.

### GameControls

Pause and restart control buttons.

### GameOverScreen

Overlay displayed when the game ends.

## Customization

### Styling

The components use CSS custom properties for theming:

```css
:root {
  --color-bg-dark: #0F380F;
  --color-snake-head: #4CAF50;
  --color-food-primary: #E74C3C;
  /* ... more variables */
}
```

### Custom Styles

You can override styles by:

1. Modifying CSS custom properties
2. Providing custom `className` props to components
3. Creating a custom stylesheet

## TypeScript

This project is written in TypeScript and includes full type definitions:

```tsx
import type {
  GameData,
  GameConfig,
  GameState,
  Position,
} from 'snake-game-ui';
```

## Testing

The project includes comprehensive unit tests:

- Component rendering tests
- User interaction tests
- Accessibility tests
- Game logic tests

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
