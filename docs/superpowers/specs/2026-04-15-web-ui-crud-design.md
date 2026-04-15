# Web UI CRUD 补全设计

**日期:** 2026-04-15
**状态:** Draft
**前置:** Web UI 实现计划 Tasks 1-20 已完成（只读视图阶段）

## 目标

为 Web UI 补全创建和状态转换功能，使所有主要实体支持基本 CRUD 操作。

## 背景

当前 Web UI 处于只读阶段：用户可以查看需求、缺陷、设计文档和日志，但无法通过 UI 创建数据或变更状态。后端 API 已全部就绪（POST /requirements、POST /bugs、POST /transition 等），前端只需补全 UI 组件。

## 功能清单

### 1. 创建需求对话框

**触发:** RequirementsBoard 页面 "Create Requirement" 按钮

**表单字段:**
- 标题（必填，文本输入）
- 优先级（选择：low / medium / high，默认 medium）

**行为:**
- 点击 "Create" 后调用 `requirementsApi.create(workspace, title, priority)`
- 成功后关闭对话框，React Query 自动刷新列表
- 失败显示错误消息

### 2. 创建缺陷对话框

**触发:** BugsBoard 页面新增 "Create Bug" 按钮

**表单字段:**
- 标题（必填，文本输入）
- 严重程度（选择：low / medium / high / critical，默认 medium）
- 关联需求 ID（文本输入，选填）

**行为:**
- 调用 `bugsApi.create(workspace, requirementId, title, severity)`
- 成功后关闭对话框并刷新列表

### 3. 需求状态转换

**触发:** RequirementCard 上新增下拉按钮

**行为:**
- 点击后显示可选的目标状态列表
- 当前状态不可选
- 选择后调用 `requirementsApi.transition(workspace, id, nextStatus)`
- 成功后刷新看板

**状态列表（按工作流顺序）:**
draft → designing → pending_user_review → approved → implementing → self_test_passed → testing → pending_user_acceptance → quality_check → done

### 4. 缺陷状态转换

**触发:** BugCard 上新增下拉按钮

**行为:**
- 同需求状态转换模式
- 调用 `bugsApi.transition(workspace, id, nextStatus)`

**状态列表:**
new → fixing → fixed → verifying → closed | reopened → needs_user_decision

## 组件设计

### 新增组件

```
web/src/components/common/
├── CreateRequirementDialog.tsx   # 创建需求表单对话框
├── CreateBugDialog.tsx           # 创建缺陷表单对话框
└── TransitionMenu.tsx            # 状态转换下拉菜单
```

### 修改组件

- `RequirementsBoard.tsx` — 接入 CreateRequirementDialog
- `BugsBoard.tsx` — 新增 "Create Bug" 按钮，接入 CreateBugDialog
- `RequirementCard.tsx` — 接入 TransitionMenu
- `BugsBoard.tsx` 卡片部分 — 接入 TransitionMenu

### 依赖

- 使用 shadcn/ui Dialog 组件（需新增）
- 使用 Radix UI DropdownMenu（已有 @radix-ui/react-dropdown-menu 依赖）
- 复用现有 Button、Input、Badge 组件

## 不做的功能

- 删除操作（无后端支持）
- 拖拽排序（需要 dnd-kit 集成，复杂度高）
- 内联编辑（双击编辑标题等）
- 批量操作
- 表单验证之外的错误恢复

## 测试策略

- TypeScript 编译检查
- Vite 生产构建验证
- 手动验收：创建需求、创建缺陷、状态转换
- 后端 pytest 回归测试（确保不破坏现有 API）
