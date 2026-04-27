# Frontend MVP Cycle

本文档描述当前 Web 端从 `Clarifying MVP` 到 `Kickoff Meeting` 再到 `Delivery` 的一整轮用户操作流程。

适用范围：

- 当前主线 `main`
- 当前前端产品工作台
- 当前 kickoff 自动生成 delivery 的实现

## 总览

当前这一轮的用户路径是：

1. 在 `Current Product Workbench` 创建 MVP requirement
2. 进入 `Clarify MVP` 对话框补全需求上下文
3. 点击 `Start Kickoff Meeting`
4. 系统运行 kickoff meeting，并在后端直接生成 delivery plan
5. 用户查看会议结果、会议 transcript、会议 minutes
6. 进入 `Delivery Board`
7. 如果存在决策项，先处理 `Kickoff Decision Needed`
8. 任务从 `preview` 进入 `ready / blocked`

## 1. 创建 MVP Requirement

进入前端首页后，页面标题是 `Current Product Workbench`。

如果当前还没有产品基线，顶部会显示：

- `No product baseline yet`
- `Create MVP Requirement`

点击 `Create MVP Requirement` 后，创建第一条 requirement。

这条 requirement 在当前语义里会被视为：

- `product_mvp`

它最开始一般处于：

- `draft`

## 2. Clarifying MVP

在 requirement 卡片上点击：

- `Clarify MVP`

会打开澄清对话框。

这个阶段的目标是把 kickoff 所需的最小上下文补齐。对话框主要分成两部分：

- 左侧：聊天区
- 右侧：`MVP Brief Preview`

右侧会逐步汇总这些字段：

- `MVP Summary`
- `MVP Must-haves`
- `Success Criteria`
- `Risks / Unknowns`

当系统判断上下文足够时：

- `readiness.ready = true`
- `Start Kickoff Meeting` 按钮可点击

## 3. Start Kickoff Meeting

点击：

- `Start Kickoff Meeting`

之后，前端会切换到 kickoff 状态面板，而不是继续停留在普通聊天输入状态。

当前会看到这些状态之一：

- `Kickoff Running`
- `Generating Delivery Plan`
- `Kickoff Failed`
- `Delivery Generation Failed`
- `Kickoff Complete`

当前面板会展示的结果信息包括：

- `Project ID`
- `Meeting ID`
- `Meeting Summary`
- `Attendees`
- `Consensus`
- `Conflicts`

## 4. Kickoff 与 Delivery 的后端行为

现在的实现里，kickoff 不再只是“开会结束后返回 meeting”。

当前后端行为是：

1. 运行 kickoff meeting graph
2. 产出 meeting minutes
3. 后端立刻生成 delivery plan

这意味着：

- 不再依赖前端额外再调用一次 delivery API 才能落库
- 即使前端后续状态丢失，meeting 完成后也应该已经有 delivery 产物

## 5. Kickoff 完成后的可见入口

如果 kickoff 成功，面板里当前会提供这些入口：

- `Open Delivery Board`
- `View Meeting Transcript`
- `View Meeting Minutes`

其中：

- `View Meeting Transcript` 用于查看会议聊天式 transcript
- `View Meeting Minutes` 用于查看最终会议纪要
- `Open Delivery Board` 进入交付看板

## 6. Delivery Board

进入 `Delivery Board` 后，当前看板会展示这些列：

- `Kickoff Decision Needed`
- `Preview`
- `Blocked`
- `Ready`
- `In Progress`
- `Review`
- `Done`

这里有一个关键点：

如果 kickoff 后存在尚未解决的用户决策项，系统会：

- 生成 `decision gate`
- 将任务先放在 `Preview`
- plan 状态为 `awaiting_user_decision`

所以：

- “看见了 gate 和 preview task” 代表 delivery 已经生成
- 这不是失败，而是等待用户做决策

## 7. 处理 Kickoff Decision

如果看板顶部有：

- `Kickoff Decision Needed`

点击卡片上的：

- `Resolve Decisions`

会打开决策对话框。

用户需要给每个问题选择一个方向。

提交后：

- `decision gate` 从 `open` 变为 `resolved`
- plan 从 `awaiting_user_decision` 变为 `active`
- 任务从 `preview` 变为：
  - 无依赖任务：`ready`
  - 有依赖任务：`blocked`

## 8. Start Agent Work

在 `Ready` 列里的任务会显示：

- `Start Agent Work`

点击之后，当前系统会：

- 校验依赖和 session
- 将任务状态改为 `in_progress`

注意：

当前系统里，`Start Agent Work` 还不是“自动开始实现代码”的完整闭环。

它现在更接近：

- 领取任务
- 锁定对应 agent session
- 把任务推进到 `in_progress`

## 当前这一轮里用户能看到什么

当前一轮完整体验里，用户能看到：

- requirement 澄清对话
- kickoff 结果状态面板
- 会议 transcript
- 会议 minutes
- delivery board
- decision gate
- preview / ready / blocked 任务

## 已知边界

当前还有这些已知边界：

### 1. Kickoff 进行中仍然不够实时

现在 kickoff 面板会显示状态和结果，但还没有做到“会议进行中实时滚动显示 moderator 提问和 agent 回答”。

也就是说：

- 当前更偏结果可见
- 还不是会议直播视图

### 2. Change Request 还不是完整后端模型

前端已经有：

- `product_mvp`
- `change_request`

这套语义。

但目前 `change_request` 主要还是前端工作台层的推导语义，还不是完整的后端一等字段模型。

### 3. Start Agent Work 不是自动执行实现

当前点击 `Start Agent Work` 后：

- 任务进入 `in_progress`

但还没有完整接上：

- agent 自动执行任务
- 自动回填 execution result
- 自动推进后续任务

## 一轮最短操作清单

如果只想最短走通一轮，可以按下面做：

1. 创建第一条 MVP requirement
2. 点击 `Clarify MVP`
3. 聊到右侧上下文足够
4. 点击 `Start Kickoff Meeting`
5. 等待状态进入 `Kickoff Complete`
6. 点击 `Open Delivery Board`
7. 如果有 `Kickoff Decision Needed`，先处理决策
8. 在 `Ready` 列里点击 `Start Agent Work`

## 相关文档

如果你要调试 agent 或图执行，也可以看这些文档：

- [agent-debugging.md](F:/projs/Game_Studio/docs/agent-debugging.md)
- [langgraph-studio-debugging.md](F:/projs/Game_Studio/docs/langgraph-studio-debugging.md)
