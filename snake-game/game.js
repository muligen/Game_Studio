// Game Configuration
const CONFIG = {
    canvasSize: 400,
    gridSize: 20,
    cellCount: 20,
    initialSpeed: 150,
    speedIncrement: 5,
    minSpeed: 50
};

// Game State
const state = {
    snake: [],
    direction: { x: 1, y: 0 },
    nextDirection: { x: 1, y: 0 },
    food: null,
    score: 0,
    gameOver: false,
    isRunning: false,
    gameLoop: null,
    currentSpeed: CONFIG.initialSpeed
};

// DOM Elements
const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');
const scoreElement = document.getElementById('score');
const startBtn = document.getElementById('startBtn');
const restartBtn = document.getElementById('restartBtn');

// Initialize Canvas
function initCanvas() {
    canvas.width = CONFIG.canvasSize;
    canvas.height = CONFIG.canvasSize;
}

// Initialize Game State
function initGame() {
    // Start with snake in the middle
    const startX = Math.floor(CONFIG.cellCount / 2);
    const startY = Math.floor(CONFIG.cellCount / 2);

    state.snake = [
        { x: startX, y: startY }
    ];

    state.direction = { x: 1, y: 0 };
    state.nextDirection = { x: 1, y: 0 };
    state.score = 0;
    state.gameOver = false;
    state.currentSpeed = CONFIG.initialSpeed;

    updateScore();
    spawnFood();
    draw();
}

// Spawn Food
function spawnFood() {
    let newFood;
    do {
        newFood = {
            x: Math.floor(Math.random() * CONFIG.cellCount),
            y: Math.floor(Math.random() * CONFIG.cellCount)
        };
    } while (isOnSnake(newFood));

    state.food = newFood;
}

// Check if position is on snake
function isOnSnake(pos) {
    return state.snake.some(segment => segment.x === pos.x && segment.y === pos.y);
}

// Update Score Display
function updateScore() {
    scoreElement.textContent = state.score;
}

// Draw Game
function draw() {
    // Clear canvas
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw grid (subtle)
    ctx.strokeStyle = '#2a2a4e';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= CONFIG.cellCount; i++) {
        const pos = i * CONFIG.gridSize;
        ctx.beginPath();
        ctx.moveTo(pos, 0);
        ctx.lineTo(pos, canvas.height);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(0, pos);
        ctx.lineTo(canvas.width, pos);
        ctx.stroke();
    }

    // Draw food
    if (state.food) {
        ctx.fillStyle = '#ff6b6b';
        ctx.shadowColor = '#ff6b6b';
        ctx.shadowBlur = 10;
        drawCell(state.food.x, state.food.y);
        ctx.shadowBlur = 0;
    }

    // Draw snake
    state.snake.forEach((segment, index) => {
        if (index === 0) {
            // Head
            ctx.fillStyle = '#4ecdc4';
            ctx.shadowColor = '#4ecdc4';
            ctx.shadowBlur = 8;
        } else {
            // Body
            ctx.fillStyle = '#45b7aa';
            ctx.shadowBlur = 0;
        }
        drawCell(segment.x, segment.y);
        ctx.shadowBlur = 0;
    });

    // Draw game over overlay
    if (state.gameOver) {
        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        ctx.fillStyle = '#fff';
        ctx.font = 'bold 32px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('游戏结束!', canvas.width / 2, canvas.height / 2 - 20);

        ctx.font = '18px Arial';
        ctx.fillText(`最终得分: ${state.score}`, canvas.width / 2, canvas.height / 2 + 20);
    }
}

// Draw single cell
function drawCell(x, y) {
    const padding = 2;
    ctx.beginPath();
    ctx.roundRect(
        x * CONFIG.gridSize + padding,
        y * CONFIG.gridSize + padding,
        CONFIG.gridSize - padding * 2,
        CONFIG.gridSize - padding * 2,
        4
    );
    ctx.fill();
}

// Update Game State
function update() {
    if (state.gameOver) return;

    // Apply direction change
    state.direction = { ...state.nextDirection };

    // Calculate new head position
    const head = state.snake[0];
    const newHead = {
        x: head.x + state.direction.x,
        y: head.y + state.direction.y
    };

    // Check wall collision
    if (newHead.x < 0 || newHead.x >= CONFIG.cellCount ||
        newHead.y < 0 || newHead.y >= CONFIG.cellCount) {
        endGame();
        return;
    }

    // Check self collision
    if (isOnSnake(newHead)) {
        endGame();
        return;
    }

    // Add new head
    state.snake.unshift(newHead);

    // Check food collision
    if (newHead.x === state.food.x && newHead.y === state.food.y) {
        state.score++;
        updateScore();
        spawnFood();

        // Increase speed slightly
        state.currentSpeed = Math.max(
            CONFIG.minSpeed,
            state.currentSpeed - CONFIG.speedIncrement
        );

        // Restart game loop with new speed
        clearInterval(state.gameLoop);
        state.gameLoop = setInterval(gameStep, state.currentSpeed);
    } else {
        // Remove tail if no food eaten
        state.snake.pop();
    }

    draw();
}

// Game Step
function gameStep() {
    update();
}

// Start Game
function startGame() {
    initGame();
    state.isRunning = true;
    startBtn.style.display = 'none';
    restartBtn.style.display = 'none';

    state.gameLoop = setInterval(gameStep, state.currentSpeed);
}

// End Game
function endGame() {
    state.gameOver = true;
    state.isRunning = false;
    clearInterval(state.gameLoop);
    draw();
    restartBtn.style.display = 'inline-block';
}

// Restart Game
function restartGame() {
    startGame();
}

// Handle Keyboard Input
function handleKeydown(e) {
    if (!state.isRunning) return;

    const key = e.key.toLowerCase();

    // Prevent default scrolling for arrow keys and space
    if (['arrowup', 'arrowdown', 'arrowleft', 'arrowright', ' '].includes(key) ||
        ['w', 'a', 's', 'd'].includes(key)) {
        e.preventDefault();
    }

    // Calculate direction change (prevent 180-degree turns)
    const currentDir = state.direction;

    switch (key) {
        case 'arrowup':
        case 'w':
            if (currentDir.y !== 1) {
                state.nextDirection = { x: 0, y: -1 };
            }
            break;
        case 'arrowdown':
        case 's':
            if (currentDir.y !== -1) {
                state.nextDirection = { x: 0, y: 1 };
            }
            break;
        case 'arrowleft':
        case 'a':
            if (currentDir.x !== 1) {
                state.nextDirection = { x: -1, y: 0 };
            }
            break;
        case 'arrowright':
        case 'd':
            if (currentDir.x !== -1) {
                state.nextDirection = { x: 1, y: 0 };
            }
            break;
    }
}

// Event Listeners
startBtn.addEventListener('click', startGame);
restartBtn.addEventListener('click', restartGame);
document.addEventListener('keydown', handleKeydown);

// Initialize
initCanvas();
initGame();
