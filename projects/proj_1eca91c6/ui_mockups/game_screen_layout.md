# Snake Game - Game Screen Layout Design

## Document Information
- **Project**: Snake Game MVP
- **Version**: 1.0
- **Status**: Design Complete
- **Date**: 2026-05-06
- **Designer**: Design Agent

---

## 1. Layout Overview

### 1.1 Screen Structure
```
┌─────────────────────────────────────────────────────────┐
│                     [Header Bar]                         │
│  Score: 000  │  High Score: 000  │  [Pause] [Reset]     │
├─────────────────────────────────────────────────────────┤
│                                                           │
│                   [Game Canvas Area]                     │
│                    (10x10 Grid)                          │
│                                                           │
│                                                           │
│                                                           │
├─────────────────────────────────────────────────────────┤
│                  [Controls/Status]                       │
│           Arrow Keys: Move  │  Space: Pause              │
└─────────────────────────────────────────────────────────┘
```

### 1.2 Layout Dimensions
- **Canvas Area**: 400x400px (40px per grid cell)
- **Header Height**: 60px
- **Footer/Controls Height**: 50px
- **Total Minimum Height**: 510px
- **Recommended Width**: 450px (including margins)

---

## 2. Component Specifications

### 2.1 Header Bar

#### Layout
```
┌─────────────────────────────────────────────────────────────┐
│  🐍 SNAKE                    Score: 12      Best: 45    ⏸ 🔄  │
└─────────────────────────────────────────────────────────────┘
```

#### Elements
1. **Logo/Title** (Left)
   - Icon: 🐍 emoji or 8-bit snake sprite
   - Text: "SNAKE" in pixel font
   - Color: #4CAF50

2. **Score Display** (Center-Left)
   - Label: "Score:"
   - Value: Current score (3 digits, zero-padded)
   - Font: Pixel art style, monospace
   - Color: White text on dark background

3. **High Score Display** (Center-Right)
   - Label: "Best:"
   - Value: Highest score (3 digits, zero-padded)
   - Font: Pixel art style, monospace
   - Color: Gold/Yellow (#FFD700) text on dark background

4. **Control Buttons** (Right)
   - Pause Button: ⏸ icon
   - Restart Button: 🔄 icon
   - Size: 32x32px
   - Hover state: Brighten by 20%
   - Active state: Scale down to 95%

#### Styling
- Background: #2C3E50 (Dark blue-grey)
- Border: 2px solid #34495E
- Height: 60px
- Padding: 10px horizontal
- Flexbox: Space-between layout

---

### 2.2 Game Canvas Area

#### Canvas Specifications
- **Dimensions**: 400x400px
- **Grid**: 10x10 cells (40px per cell)
- **Background**: #1A1A1A (Dark grey, nearly black)
- **Border**: 4px solid #4CAF50 (Green)
- **Corner Radius**: 4px
- **Shadow**: 
  - Box-shadow: 0 0 20px rgba(76, 175, 80, 0.3)

#### Grid Visual Guide
- **Grid Lines**: Optional subtle overlay
- **Line Color**: rgba(255, 255, 255, 0.05)
- **Line Width**: 1px
- **Purpose**: Helps players count grid positions

#### Canvas Content Layers
1. **Background Layer** (Bottom)
   - Solid color fill
   - Optional grid lines

2. **Food Layer**
   - Rendered before snake
   - Animated pulse effect

3. **Snake Layer** (Top)
   - Rendered last
   - Head distinct from body

---

### 2.3 Controls/Status Bar

#### Layout
```
┌─────────────────────────────────────────────────────────────┐
│    ⬆️⬇️⬅️➡️ Move         Status: Playing         Space: Pause   │
└─────────────────────────────────────────────────────────────┘
```

#### Elements
1. **Controls Help** (Left)
   - Arrow key icons: ⬆️⬇️⬅️➡️
   - Text: "Move"
   - Color: #BDC3C7

2. **Game Status** (Center)
   - Text: Current status (Playing, Paused, Game Over)
   - Font: Pixel art style
   - Colors by status:
     - Playing: #2ECC71 (Green)
     - Paused: #F39C12 (Orange)
     - Game Over: #E74C3C (Red)

3. **Keyboard Shortcuts** (Right)
   - Text: "Space: Pause"
   - Color: #BDC3C7

#### Styling
- Background: #34495E
- Height: 50px
- Padding: 12px horizontal
- Font-size: 14px

---

## 3. Visual Style Details

### 3.1 Snake Rendering

#### Head
- **Shape**: Rounded square with eyes
- **Size**: 40x40px (fills entire grid cell)
- **Color**: #4CAF50 (Vibrant green)
- **Border**: 2px solid #45A049 (Darker green)
- **Eyes**: Two 6x6px white circles with 3x3px black pupils
- **Eye Position**:
  - Looking UP: Top-left and top-right corners
  - Looking DOWN: Bottom-left and bottom-right corners
  - Looking LEFT: Top-left and bottom-left corners
  - Looking RIGHT: Top-right and bottom-right corners

#### Body Segments
- **Shape**: Rounded squares
- **Size**: 40x40px
- **Color Gradient**:
  - Segment 1 (nearest head): #4CAF50
  - Segment 2: #66BB6A
  - Segment 3: #81C784
  - Segment 4+: #A5D6A7 (Lightest)
- **Border**: 2px solid #388E3C
- **Spacing**: No gap (segments touch)

#### Tail
- **Shape**: Slightly smaller rounded square
- **Size**: 36x36px (centered in 40x40px cell)
- **Color**: #C8E6C9 (Lightest green)

---

### 3.2 Food Rendering

#### Apple Design
- **Shape**: Circle
- **Size**: 30x30px (centered in 40x40px cell)
- **Color**: #E74C3C (Bright red)
- **Border**: 2px solid #C0392B (Dark red)
- **Stem**: Small 4x8px brown rectangle at top
- **Leaf**: 6x4px green ellipse on stem

#### Animation
- **Pulse Effect**: 
  - Scale: 0.95 to 1.05
  - Duration: 500ms
  - Easing: Ease-in-out
  - Infinite loop

---

### 3.3 Wall Rendering (Visual Only)

#### Boundary Indication
- **Corner Markers**: 8x8px squares in each corner
- **Color**: #4CAF50 (Same as snake)
- **Purpose**: Visual cue for lethal boundaries

---

## 4. Responsive Design

### 4.1 Breakpoints

#### Desktop (≥768px)
- Canvas: 400x400px
- Layout as specified above
- Controls bar visible

#### Tablet (480px - 767px)
- Canvas: 320x320px (32px per cell)
- Header elements wrap to two rows if needed
- Controls text hidden, icons only

#### Mobile (<480px)
- Canvas: 280x280px (28px per cell)
- Stack all elements vertically
- Controls bar becomes collapsible/hidden
- Touch controls overlay (future enhancement)

### 4.2 Scaling Strategy
- Use CSS `transform: scale()` for canvas scaling
- Maintain aspect ratio
- Center canvas in viewport
- Maximum width: 90vw
- Maximum height: 70vh

---

## 5. Accessibility

### 5.1 Keyboard Navigation
- **Tab**: Focus buttons (Pause, Restart)
- **Enter/Space**: Activate focused button
- **Arrow Keys**: Control snake (global when game active)
- **Escape**: Pause game
- **R**: Restart game (when game over)

### 5.2 Focus States
- **Button Focus**: 2px yellow outline
- **Canvas Focus**: Green border brightens to #66BB6A

### 5.3 Screen Reader Support
- **Canvas**: ARIA label describing current game state
- **Score**: Live region with `aria-live="polite"`
- **Status**: Live region with `aria-live="assertive"`

---

## 6. Animation Specifications

### 6.1 Snake Movement
- **Type**: Discrete (no interpolation between grid cells)
- **Duration**: Instant (0ms)
- **Frame Rate**: Updates on game tick (500ms interval)

### 6.2 Button Animations
- **Hover**:
  - Duration: 150ms
  - Property: Brightness filter +20%
- **Click/Active**:
  - Duration: 100ms
  - Property: Scale 95%

### 6.3 Page Transitions
- **Fade In**: 300ms ease-in
- **Fade Out**: 200ms ease-out

---

## 7. Color Palette Reference

### Primary Colors
- **Background Dark**: #1A1A1A
- **Background Medium**: #2C3E50
- **Background Light**: #34495E
- **Snake Primary**: #4CAF50
- **Snake Dark**: #388E3C
- **Food**: #E74C3C
- **Food Dark**: #C0392B
- **Text White**: #FFFFFF
- **Text Grey**: #BDC3C7
- **Accent Gold**: #FFD700
- **Status Green**: #2ECC71
- **Status Orange**: #F39C12
- **Status Red**: #E74C3C

---

## 8. Typography

### Font Stack
```css
font-family: 'Press Start 2P', 'Courier New', monospace;
```

### Font Sizes
- **Logo/Title**: 24px
- **Score Values**: 18px
- **Labels**: 14px
- **Controls Text**: 12px

---

## 9. Implementation Notes

1. **Canvas rendering should use requestAnimationFrame** for smooth updates
2. **Grid size and colors should be configurable** via CSS variables
3. **All animations should respect `prefers-reduced-motion`** media query
4. **Game state should be clearly communicated** through visual feedback
5. **Score updates should animate** (count up effect) for positive reinforcement

---

## 10. Edge Cases

1. **Maximum Score**: 3-digit display supports up to 999 points
2. **Snake fills screen**: Visual indication when nearing maximum length
3. **Rapid key presses**: Buffer last direction change only
4. **Window resize**: Pause game if canvas would become too small
5. **Focus loss**: Auto-pause when window/tab loses focus
