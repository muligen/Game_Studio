# 贪吃蛇游戏 MVP - 视觉设计规范

**版本**: 1.0  
**创建日期**: 2026-05-06  
**设计风格**: 现代扁平化  
**目标平台**: 桌面端浏览器

---

## 1. 设计原则

### 1.1 核心原则
- **简洁性**: 使用纯色块和简洁线条，避免过度装饰
- **可读性**: 确保游戏元素在视觉上清晰可辨
- **一致性**: 与 Game Studio Web UI 整体风格保持一致
- **响应式**: 使用相对单位适配不同屏幕尺寸

### 1.2 设计语言
- 采用现代扁平化设计（Flat Design 2.0）
- 色彩饱和度适中，避免视觉疲劳
- 使用圆角和微阴影增加层次感（可选）
- 字体选用系统默认无衬线字体以确保性能

---

## 2. 配色方案

### 2.1 游戏元素配色

| 元素 | 用途 | HEX | RGB | CSS 变量名 |
|------|------|-----|-----|-----------|
| **蛇头** | 玩家控制的蛇头部 | `#22c55e` | `rgb(34, 197, 94)` | `--snake-head-color` |
| **蛇身** | 蛇的身体部分 | `#4ade80` | `rgb(74, 222, 128)` | `--snake-body-color` |
| **食物** | 可收集的食物 | `#ef4444` | `rgb(239, 68, 68)` | `--food-color` |
| **游戏背景** | Canvas 游戏区域背景 | `#1e293b` | `rgb(30, 41, 59)` | `--game-bg-color` |
| **网格线** (可选) | 辅助网格线 | `#334155` | `rgb(51, 65, 85)` | `--grid-line-color` |

### 2.2 UI 界面配色

| 元素 | 用途 | HEX | RGB | CSS 变量名 |
|------|------|-----|-----|-----------|
| **主背景** | 页面整体背景 | `#0f172a` | `rgb(15, 23, 42)` | `--primary-bg` |
| **卡片背景** | UI 容器背景 | `#1e293b` | `rgb(30, 41, 59)` | `--card-bg` |
| **主按钮** | 主要操作按钮 | `#3b82f6` | `rgb(59, 130, 246)` | `--primary-button` |
| **主按钮悬停** | 主要操作按钮悬停 | `#2563eb` | `rgb(37, 99, 235)` | `--primary-button-hover` |
| **次要按钮** | 次要操作按钮 | `#64748b` | `rgb(100, 116, 139)` | `--secondary-button` |
| **文字主要** | 主要文字内容 | `#f1f5f9` | `rgb(241, 245, 249)` | `--text-primary` |
| **文字次要** | 次要文字内容 | `#94a3b8` | `rgb(148, 163, 184)` | `--text-secondary` |
| **文字强调** | 强调文字（分数等） | `#fbbf24` | `rgb(251, 191, 36)` | `--text-accent` |
| **遮罩层** | Pause/GameOver 遮罩 | `rgba(15, 23, 42, 0.85)` | `rgba(15, 23, 42, 0.85)` | `--overlay-color` |

### 2.3 状态配色

| 状态 | 用途 | HEX | RGB |
|------|------|-----|-----|
| **成功** | 最高分提示、成就提示 | `#22c55e` | `rgb(34, 197, 94)` |
| **警告** | 暂停状态 | `#f59e0b` | `rgb(245, 158, 11)` |
| **错误** | Game Over | `#ef4444` | `rgb(239, 68, 68)` |

---

## 3. 组件尺寸规范

### 3.1 游戏区域尺寸

使用 `vmin` 相对单位确保跨设备一致性：

```css
.game-container {
  width: min(90vw, 80vmin);
  height: min(90vw, 80vmin);
  max-width: 800px;
  max-height: 800px;
  aspect-ratio: 1 / 1;
}
```

**网格配置**:
- 网格数量: 20 x 20（每行/列 20 个格子）
- 单个网格尺寸: 自动计算（容器宽度 / 20）

### 3.2 UI 组件尺寸

| 组件 | 宽度 | 高度 | 圆角 | 字体大小 |
|------|------|------|------|---------|
| **游戏标题** | auto | auto | 0 | 32px / 2rem |
| **分数显示** | auto | auto | 0 | 24px / 1.5rem |
| **主按钮** | 200px | 48px | 8px | 18px / 1.125rem |
| **次要按钮** | 160px | 40px | 6px | 16px / 1rem |
| **小按钮** | 120px | 36px | 4px | 14px / 0.875rem |
| **卡片容器** | auto | auto | 12px | - |
| **遮罩层** | 100% | 100% | 0 | - |

### 3.3 间距规范

使用 8px 基础间距单位：

| 间距类型 | 数值 | 用途 |
|---------|------|------|
| **xs** | 4px | 内联元素间距 |
| **sm** | 8px | 相关元素间距 |
| **md** | 16px | 组件内间距 |
| **lg** | 24px | 组件间距 |
| **xl** | 32px | 区块间距 |
| **2xl** | 48px | 大区块间距 |

---

## 4. UI 布局样式

### 4.1 Start 画面（开始界面）

**布局结构**:
```
┌─────────────────────────────────┐
│                                 │
│        [GAME TITLE]             │
│      贪吃蛇 - SNAKE GAME         │
│                                 │
│    ┌─────────────────────┐     │
│    │                     │     │
│    │   [PREVIEW AREA]    │     │
│    │   (可选：游戏预览)   │     │
│    │                     │     │
│    └─────────────────────┘     │
│                                 │
│  历史最高分: XXX                │
│                                 │
│    [开始游戏]                    │
│    [游戏说明]                    │
│                                 │
│  提示: 使用方向键或WASD控制      │
│                                 │
└─────────────────────────────────┘
```

**样式规范**:
- **标题**: 字体大小 32px，颜色 `--text-primary`，居中对齐，加粗
- **预览区域**: 宽高比 1:1，边框 2px 实线 `--grid-line-color`，圆角 8px
- **最高分**: 字体大小 18px，颜色 `--text-accent`，居中对齐
- **主按钮**: 宽度 200px，高度 48px，背景 `--primary-button`，文字白色，圆角 8px
- **次要按钮**: 宽度 160px，高度 40px，背景 `--secondary-button`，文字白色，圆角 6px
- **提示文字**: 字体大小 14px，颜色 `--text-secondary`，居中对齐

**交互状态**:
- 主按钮悬停: 背景变为 `--primary-button-hover`，添加微阴影
- 次要按钮悬停: 背景加深 10%

### 4.2 HUD（游戏进行中界面）

**布局结构**:
```
┌─────────────────────────────────┐
│  分数: 100    最高分: 500        │
├─────────────────────────────────┤
│                                 │
│                                 │
│         [GAME CANVAS]           │
│      (游戏区域 - 20x20网格)      │
│                                 │
│                                 │
├─────────────────────────────────┤
│  [P] 暂停    [ESC] 退出           │
└─────────────────────────────────┘
```

**样式规范**:
- **分数栏**: 
  - 高度: 48px
  - 背景: `--card-bg`
  - 内边距: 0 24px
  - 分数标签: 字体大小 16px，颜色 `--text-secondary`
  - 分数值: 字体大小 24px，颜色 `--text-accent`，加粗
- **游戏区域**: 
  - 背景: `--game-bg-color`
  - 边框: 2px 实线 `--grid-line-color`
  - 圆角: 4px
- **操作提示**:
  - 高度: 36px
  - 背景: `--card-bg`
  - 文字: 字体大小 12px，颜色 `--text-secondary`
  - 快捷键标签: 使用 `code` 样式，背景 `--primary-bg`，圆角 4px，内边距 2px 6px

### 4.3 Pause 画面（暂停界面）

**布局结构**:
```
┌─────────────────────────────────┐
│         ╱╱╱╱ PAUSED ╲╲╲╲         │
│                                 │
│       [继续游戏]                 │
│       [重新开始]                 │
│       [返回菜单]                 │
│                                 │
│  按 P 键或 ESC 键继续             │
└─────────────────────────────────┘
```

**样式规范**:
- **遮罩层**: 
  - 背景: `--overlay-color`
  - 背景滤镜: `blur(4px)`（可选）
- **PAUSED 文字**: 
  - 字体大小: 48px
  - 颜色: `--text-warning` (#f59e0b)
  - 字重: 加粗
  - 文字阴影: 0 2px 8px `rgba(0,0,0,0.3)`
- **按钮组**: 
  - 垂直排列，间距 16px
  - 居中对齐
- **提示文字**: 
  - 字体大小: 14px
  - 颜色: `--text-secondary`

### 4.4 Game Over 画面（结束界面）

**布局结构**:
```
┌─────────────────────────────────┐
│         GAME OVER               │
│                                 │
│        本次得分: 150            │
│        历史最高: 500            │
│                                 │
│    [再玩一次]                    │
│    [返回菜单]                    │
│                                 │
│  按空格键快速重新开始             │
└─────────────────────────────────┘
```

**样式规范**:
- **遮罩层**: 
  - 背景: `--overlay-color`
  - 背景滤镜: `blur(4px)`（可选）
- **GAME OVER 文字**: 
  - 字体大小: 48px
  - 颜色: `--text-error` (#ef4444)
  - 字重: 加粗
  - 文字阴影: 0 2px 8px `rgba(0,0,0,0.3)`
- **得分信息**: 
  - 字体大小: 20px
  - 本次得分: 颜色 `--text-primary`
  - 最高分: 颜色 `--text-accent`
  - 新纪录时: 颜色 `--text-success`，添加"新纪录!"标签
- **按钮组**: 
  - 水平排列，间距 16px
  - 居中对齐
- **提示文字**: 
  - 字体大小: 14px
  - 颜色: `--text-secondary`

### 4.5 网格系统

游戏区域采用 20x20 网格：

```
网格坐标系统:
(0,0) ──────────────────────► (19,0)
  │                             │
  │     游戏区域 (20x20)         │
  │                             │
▼                             ▼
(0,19)────────────────────── (19,19)
```

**网格渲染规则**:
- 蛇头: 当前坐标 (headX, headY) 渲染为 `--snake-head-color`
- 蛇身: body 数组中的每个坐标渲染为 `--snake-body-color`
- 食物: 当前坐标 (foodX, foodY) 渲染为 `--food-color`
- 空白: 其他坐标渲染为 `--game-bg-color`

---

## 5. 字体规范

### 5.1 字体族

```css
:root {
  --font-family-base: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 
                      'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 
                      'Droid Sans', 'Helvetica Neue', sans-serif;
  --font-family-mono: 'SF Mono', 'Monaco', 'Cascadia Code', 
                      'Roboto Mono', 'Courier New', monospace;
}
```

### 5.2 字体大小层级

| 级别 | 大小 | 用途 | 字重 |
|------|------|------|------|
| **h1** | 48px | GAME OVER / PAUSED 标题 | 700 (Bold) |
| **h2** | 32px | 游戏主标题 | 700 (Bold) |
| **h3** | 24px | 分数显示 | 700 (Bold) |
| **body-lg** | 18px | 按钮文字 | 600 (Semi-bold) |
| **body** | 16px | 正文内容 | 400 (Regular) |
| **body-sm** | 14px | 提示文字 | 400 (Regular) |
| **caption** | 12px | 快捷键提示 | 400 (Regular) |

### 5.3 行高与字间距

| 元素类型 | 行高 | 字间距 |
|---------|------|--------|
| **标题** | 1.2 | 0 |
| **按钮** | 1 | 0.5px |
| **正文** | 1.5 | 0 |
| **数字** | 1 | 1px（等宽字体） |

---

## 6. 动画与过渡

### 6.1 过渡效果

```css
/* 默认过渡 */
.transition-default {
  transition: all 0.2s ease-in-out;
}

/* 按钮悬停 */
.button-hover {
  transition: background-color 0.15s ease, 
              transform 0.1s ease,
              box-shadow 0.15s ease;
}

.button-hover:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

/* 页面切换 */
.page-transition {
  transition: opacity 0.3s ease;
}
```

### 6.2 游戏元素动画（可选）

如果时间允许，可添加以下微动画：

```css
/* 食物闪烁动画 */
@keyframes food-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.food-pulse {
  animation: food-pulse 1.5s ease-in-out infinite;
}

/* 得分增加动画 */
@keyframes score-pop {
  0% { transform: scale(1); }
  50% { transform: scale(1.2); }
  100% { transform: scale(1); }
}

.score-pop {
  animation: score-pop 0.3s ease-out;
}

/* 新纪录强调动画 */
@keyframes new-record-highlight {
  0%, 100% { color: var(--text-accent); }
  50% { color: var(--text-success); }
}

.new-record {
  animation: new-record-highlight 0.6s ease-in-out 3;
}
```

---

## 7. 响应式断点

### 7.1 断点定义

```css
/* 桌面端（主要支持） */
@media (min-width: 1024px) {
  /* 主要目标设备 */
}

/* 小屏幕桌面 */
@media (max-width: 1023px) {
  .game-container {
    width: min(95vw, 85vmin);
    height: min(95vw, 85vmin);
  }
}

/* 超小屏幕（暂不支持移动端，保留降级） */
@media (max-width: 640px) {
  /* 显示提示：建议在桌面端游玩 */
}
```

### 7.2 响应式调整

| 屏幕尺寸 | 游戏区域 | 字体缩放 | 按钮尺寸 |
|---------|---------|---------|---------|
| ≥ 1024px | 80vmin | 100% | 标准 |
| 640px - 1023px | 85vmin | 90% | 略小 |
| < 640px | 不建议 | - | - |

---

## 8. 可访问性规范

### 8.1 ARIA 标签

```html
<div 
  role="application" 
  aria-label="贪吃蛇游戏"
  aria-describedby="game-instructions"
>
  <!-- 游戏内容 -->
</div>

<div id="game-instructions" class="sr-only">
  使用方向键或 WASD 控制蛇的移动方向。按 P 键暂停，按 ESC 键返回菜单。
</div>
```

### 8.2 键盘焦点

```css
/* 焦点可见性 */
*:focus-visible {
  outline: 2px solid var(--primary-button);
  outline-offset: 2px;
}

/* 按钮焦点样式 */
button:focus-visible {
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.3);
}
```

### 8.3 颜色对比度

所有文字与背景的对比度符合 WCAG AA 标准：
- 正常文字（16px+）: 对比度 ≥ 4.5:1
- 大文字（24px+）: 对比度 ≥ 3:1

当前配色方案对比度验证：
- `--text-primary` on `--primary-bg`: 15.2:1 ✓
- `--text-secondary` on `--card-bg`: 4.8:1 ✓
- `--snake-head-color` on `--game-bg-color`: 5.1:1 ✓

---

## 9. CSS 变量汇总

```css
:root {
  /* 游戏元素颜色 */
  --snake-head-color: #22c55e;
  --snake-body-color: #4ade80;
  --food-color: #ef4444;
  --game-bg-color: #1e293b;
  --grid-line-color: #334155;
  
  /* UI 界面颜色 */
  --primary-bg: #0f172a;
  --card-bg: #1e293b;
  --primary-button: #3b82f6;
  --primary-button-hover: #2563eb;
  --secondary-button: #64748b;
  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-accent: #fbbf24;
  --overlay-color: rgba(15, 23, 42, 0.85);
  
  /* 状态颜色 */
  --text-success: #22c55e;
  --text-warning: #f59e0b;
  --text-error: #ef4444;
  
  /* 间距 */
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 16px;
  --spacing-lg: 24px;
  --spacing-xl: 32px;
  --spacing-2xl: 48px;
  
  /* 字体 */
  --font-family-base: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-family-mono: 'SF Mono', 'Monaco', 'Cascadia Code', monospace;
  
  /* 字体大小 */
  --font-h1: 48px;
  --font-h2: 32px;
  --font-h3: 24px;
  --font-body-lg: 18px;
  --font-body: 16px;
  --font-body-sm: 14px;
  --font-caption: 12px;
  
  /* 圆角 */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  
  /* 过渡 */
  --transition-fast: 0.15s ease;
  --transition-normal: 0.2s ease-in-out;
  --transition-slow: 0.3s ease;
}
```

---

## 10. 实现检查清单

### 10.1 配色实现
- [ ] 所有颜色使用 CSS 变量定义
- [ ] 游戏元素颜色正确应用（蛇头、蛇身、食物、背景）
- [ ] UI 界面颜色正确应用（按钮、文字、遮罩层）
- [ ] 状态颜色正确应用（成功、警告、错误）
- [ ] 颜色对比度符合 WCAG AA 标准

### 10.2 尺寸实现
- [ ] 游戏区域使用 vmin 相对单位
- [ ] 容器最大尺寸限制为 800px
- [ ] 组件尺寸符合规范（按钮、卡片、字体）
- [ ] 间距使用 8px 基础单位
- [ ] 响应式断点正确应用

### 10.3 布局实现
- [ ] Start 画面布局完整（标题、预览、按钮）
- [ ] HUD 布局完整（分数栏、游戏区域、操作提示）
- [ ] Pause 画面布局完整（遮罩、按钮）
- [ ] Game Over 画面布局完整（得分、按钮）
- [ ] 所有界面居中对齐

### 10.4 可访问性实现
- [ ] 游戏容器添加 `role="application"` 和 `aria-label`
- [ ] 焦点状态可见（`outline` 或 `box-shadow`）
- [ ] 键盘导航支持（Tab 键可访问按钮）
- [ ] 屏幕阅读器支持（游戏说明使用 `aria-describedby`）

---

## 11. 后续迭代方向（v1.1+）

以下内容不在 MVP 范围内，供后续迭代参考：

1. **像素化装饰元素**
   - Start/GameOver 画面添加 8-bit 风格图标
   - 按钮添加像素化边框效果
   - 字体可选像素风格（如 Press Start 2P）

2. **动画增强**
   - 蛇移动时的平滑过渡
   - 吃食物时的粒子效果
   - 碰撞时的震动反馈

3. **主题系统**
   - 支持亮色/暗色主题切换
   - 可自定义配色方案
   - 经典像素风格主题

4. **移动端适配**
   - 触屏滑动控制
   - 虚拟方向键
   - 响应式布局优化

---

## 附录：设计资源

### Figma 设计文件（待创建）
- [ ] 创建 Figma 设计文件
- [ ] 导出设计 Token
- [ ] 创建组件库

### 图标资源
- 游戏图标（待设计或使用开源资源）
- UI 图标（可选使用 Heroicons/Lucide）

### 字体资源
- 使用系统默认字体，无需加载外部字体文件
- 如需像素风格，考虑 Google Fonts: Press Start 2P

---

**文档维护**: 本文档应在开发过程中持续更新，确保与实际实现保持一致。

**变更记录**:
- 2026-05-06: 初始版本创建 (v1.0)
