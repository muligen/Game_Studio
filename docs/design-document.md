# Game Studio 设计文档

> 最后更新: 2026-05-09

## 1. 项目定位

Game Studio 是一个**多 Agent 协作的游戏生产运行时内核**。它围绕 LangGraph 构建，编排多个 AI Agent（设计、开发、QA、美术、评审等）协作完成游戏需求的全生命周期：从需求收集、多 Agent 会议评审、交付计划生成、任务执行，到自动化验收测试。

核心理念：将游戏生产中的创意决策和重复性工程任务交给专业化的 AI Agent，人类在关键决策点介入（human-in-the-loop）。

---

## 2. 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 工作流引擎 | LangGraph | 图执行模型，支持条件分支、并行 fan-out、循环重试 |
| LLM 调用 | Claude Agent SDK | 支持 SDK 直调和子进程 fallback 双路径 |
| 后端 API | FastAPI | REST + WebSocket，11 个路由模块 |
| 数据验证 | Pydantic v2 (strict) | 全量 `extra="forbid"`，自定义 `StrippedNonEmptyStr` |
| 持久化 | JSON 文件 | 无数据库依赖，`JsonRepository[T]` 泛型仓库 |
| 可观测性 | Langfuse | 两套独立上报机制（主动埋点 + hook 解析） |
| 前端 | React + TypeScript (Vite) | TanStack React Query + WebSocket 实时更新 |
| 前端类型 | openapi-typescript | 从 FastAPI OpenAPI spec 自动生成 |
| E2E 测试 | Playwright | 浏览器冒烟测试 + 验收验证 |
| 包管理 | uv | Python 3.12+，Hatchling 构建 |

---

## 3. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React/TS)                       │
│  RequirementsBoard · DeliveryBoard · AgentChat · DesignEditor│
│  TanStack Query (缓存) + WebSocket (实时)                    │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST + WebSocket
┌───────────────────────────▼─────────────────────────────────┐
│                    API Layer (FastAPI)                        │
│  11 路由模块 + WebSocket Manager + Lifespan                  │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                  Domain Layer (纯函数)                        │
│  requirement_flow · bug_flow · approvals · services          │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│              Application Services                            │
│  DeliveryPlanService · KickoffService · SessionRegistry      │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌──────────────┬────────────┴──────────────┬──────────────────┐
│   Storage    │      Runtime Kernel       │    LLM Layer     │
│ JsonRepo[T]  │  LangGraph StateGraphs    │ ClaudeRoleAdapter│
│ Workspace    │  Dispatcher · Pool        │ ClaudeWorkerAdpt │
│ GitTracker   │  Policy · Checkpoints     │ ProjectScope     │
│ MemoryStore  │  ProcessRegistry          │                  │
└──────────────┴───────────────────────────┴──────────────────┘
                            │
              ┌─────────────┴─────────────┐
              │     Agent Layer            │
              │ Design · Dev · QA · Art    │
              │ Reviewer · Quality         │
              │ Planner · Worker · Moderator│
              │ DeliveryPlanner             │
              └───────────────────────────┘
```

---

## 4. 核心模块设计

### 4.1 Runtime Kernel（运行时内核）

运行时内核是系统的核心引擎，围绕 LangGraph 的 `StateGraph` 构建了 4 张执行图：

#### 4.1.1 图拓扑

| 图 | 节点 | 拓扑 | 用途 |
|---|---|---|---|
| Demo | planner → worker → reviewer | 线性 | 遗留演示管线 |
| Design | design | 单节点 | 需求设计文档生成 |
| Meeting | moderator_prepare → [agent_opinion × N] → moderator_summarize → moderator_discussion → moderator_minutes | fan-out/fan-in | 多 Agent 会议模拟 |
| Delivery | prepare_context → run_task → acceptance_gate → (循环) → finalize_delivery | 有环 DAG | 交付任务执行 + 自动验收 |

#### 4.1.2 状态管理

- **`RuntimeState`**：Demo/Design/Delivery 图的通用状态载体，Pydantic strict model，包含 goal、plan（PlanState）、artifacts、memory_refs、risks、human_gates、telemetry。
- **`_DeliveryState`**：Delivery 图专用 TypedDict，含 plan_id、task_results、runner_status。
- **`_MeetingState`**：Meeting 图专用 TypedDict，使用 `Annotated` + `operator.add` 实现并行分支的自动合并。
- **`CheckpointManager`**：每个节点执行后以 JSON 快照保存 RuntimeState，用于故障恢复。

#### 4.1.3 并发控制

- **`agent_pool`**（`pool.py`）：模块级 `ThreadPoolExecutor`，默认 max_workers=3，通过 `GAME_STUDIO_AGENT_POOL_SIZE` 配置。每个提交的任务记录 `ActiveTask` 跟踪信息，状态变化时通过 WebSocket 广播。
- **`SessionLeaseManager`**（`session_lease.py`）：基于文件的互斥锁，确保同一 (project_id, agent) 对不会被并发占用。1 小时 TTL 自动过期。
- **`_parallel_ready_batch`**（`graph.py`）：Delivery 图内的任务调度器，保证同一 (project, agent) 对最多一个任务同时运行。

#### 4.1.4 错误恢复

- **`RecoveryPolicy`**（`policy.py`）：根据错误类型（tool_failure / quality_gate_failure / state_conflict / missing_dependency）和重试次数决定恢复策略（RETRY / ESCALATE / RESUME / STOP）。
- **Delivery 循环重试**：验收失败后自动生成 bug_fix 任务，循环最多 3 次（`max_acceptance_attempts`），之后标记 `needs_attention`。
- **Agent fallback**：每个 Agent 内置 `_fallback_patch()` 返回确定性数据，确保 LLM 不可用时管线不崩溃。

#### 4.1.5 进程管理

- **`ProcessRegistry`**（`process_registry.py`）：全局子进程生命周期管理，注册所有 spawn 的子进程，支持超时杀死（Windows 用 `taskkill /T /F`，Unix 用 `os.killpg`），服务关闭时 kill-all。

### 4.2 LLM Layer（大模型调用层）

#### 4.2.1 双路径调用架构

`ClaudeRoleAdapter` 和 `ClaudeWorkerAdapter` 都实现了相同的双路径模式：

```
generate(role_name, context)
    │
    ├── 有运行中的 event loop？
    │     └── 是 → 子进程模式 (python -m studio.llm.claude_roles)
    │
    ├── asyncio.run() 调用 SDK
    │     └── 遇到 "Blocking call to os.getcwd"？
    │           └── 是 → 降级到子进程模式
    │
    └── 返回结构化输出
```

- **SDK 路径**（优先）：使用 `claude_agent_sdk.query()` + `ClaudeAgentOptions`，支持 `output_format`（JSON Schema 结构化输出）和 session 管理（session_id / resume）。
- **子进程路径**（fallback）：spawn Python 子进程，context 通过 stdin 传递，JSON 输出通过 stdout 返回。通过 `process_registry.run()` 注册管理。

#### 4.2.2 Role 分派机制

`ClaudeRoleAdapter` 通过 role name 字符串分派到不同的配置：

- **`_ROLE_PAYLOAD_MODELS`**：14 个 role → 对应的 Pydantic 输出模型（如 `DesignPayload`、`DevPayload`、`QaPayload` 等）
- **`_ROLE_OUTPUT_FORMATS`**：14 个 role → 对应的 JSON Schema（传给 Claude SDK 的 `output_format`）
- **`_ROLE_PROMPTS`**：7 个 role → 中文系统提示词片段

#### 4.2.3 Prompt 组装

每次 LLM 调用的完整 prompt 由 4 部分拼接：

1. **system_prompt**：来自 Agent Profile YAML
2. **project_scope context**：工作目录、配置目录、作用域限制（不修改 Game Studio 仓库自身）、CLAUDE.md 内容
3. **role-specific instruction**：角色专属指令
4. **JSON Schema + context**：输出格式约束 + 序列化的上下文

#### 4.2.4 Project Scope 隔离

`project_scope.py` 确保每个 Agent 只在对应的项目目录内操作：
- `resolve_agent_project_dir()`：从 context 中解析目标项目目录，fallback 到 `GitTracker.ensure_project_dir()`
- `load_agent_settings()`：读取 `.claude/settings.local.json`，将 hook 命令中的相对路径改写为绝对路径
- `agent_prompt_context()`：生成 guardrail 文本，明确告知 Claude 不要访问 Game Studio 仓库

### 4.3 Agent Layer（Agent 层）

#### 4.3.1 Agent 继承体系

```
RuntimeAgent (Protocol)
  │  run(state, **kwargs) -> NodeResult
  │
  ├── PlannerAgent          # 纯确定性，不调 LLM
  ├── WorkerAgent           # 使用 ClaudeWorkerAdapter（遗留路径）
  ├── DesignAgent           # ┐
  ├── DevAgent              # │
  ├── ArtAgent              # │ 使用 ClaudeRoleAdapter
  ├── QaAgent               # │ 每个 Agent 加载对应的 profile YAML
  ├── ReviewerAgent         # │ 内置 _fallback_patch() 兜底
  ├── QualityAgent          # ┘
  ├── DeliveryPlannerAgent  # 生成交付计划（DAG 任务 + 决策门）
  └── ModeratorAgent        # 4 个独立方法（prepare/summarize/discuss/minutes）
```

#### 4.3.2 Agent 配置

每个 Agent 对应一个 YAML Profile 文件（`studio/agents/profiles/<name>.yaml`），包含：
- `name`：Agent 名称
- `system_prompt`：系统提示词
- `enabled`：是否启用
- `model`：默认模型（如 "sonnet"）
- `fallback_policy`：降级策略
- `claude_project_root`：Agent 的 Claude 配置目录（解析为仓库内绝对路径）

`AgentProfileLoader` 负责加载和验证，包含安全检查（路径穿越防护、目录必须在仓库内）。

#### 4.3.3 懒加载注册

`RuntimeDispatcher` 维护 8 个 agent name → `"module_path:ClassName"` 的映射，首次 `get(name)` 时才 import 和实例化，避免循环依赖和不必要的加载。

### 4.4 Storage Layer（存储层）

#### 4.4.1 泛型 JSON 仓库

`JsonRepository[ModelT]` 是整个持久化层的基础：
- 每个 Pydantic 模型实例 → 一个 JSON 文件（`<id>.json`）
- 线程安全：per-path `threading.Lock`
- 原子写入：先写临时文件，再 `os.replace()`，最多重试 6 次（Windows `PermissionError` 兼容）
- ID 验证：拒绝路径分隔符、`..` 穿越、Windows 保留设备名

#### 4.4.2 工作空间聚合根

`StudioWorkspace` 是数据访问入口，管理 20 个 `JsonRepository` 实例：

```
requirements · design_docs · balance_tables · bugs · logs
meetings · meeting_transcripts · sessions · delivery_plans
delivery_tasks · decision_gates · execution_results
session_leases · clarifications · kickoff_tasks
delivery_task_events · acceptance_contracts · acceptance_runs
project_assumptions · needs_attention_items
```

#### 4.4.3 文件变更追踪

`GitTracker` 使用 SHA-256 文件哈希（而非 git diff）进行变更检测：
- `capture_state()`：遍历项目目录，哈希所有文件
- `detect_changes(pre_state)`：对比前后快照
- `add_and_commit()`：git add + commit
- `ensure_project_dir()`：初始化 git 仓库，可选配置远程

### 4.5 Domain Layer（领域层）

领域层是纯函数设计，无类，所有操作返回不可变副本 + 审计日志。

#### 4.5.1 需求状态机

```
draft → designing → pending_user_review → approved → implementing
→ self_test_passed → testing → pending_user_acceptance → quality_check → done
```

共 10 个状态，`transition_requirement()` 校验转换合法性。

#### 4.5.2 Bug 状态机

```
new → fixing → fixed → verifying → closed
                                    ↗ reopened → fixing
                  needs_user_decision ↘
```

`advance_bug()` 内置升级逻辑：重开 3 次以上或严重性高时自动升级为 `needs_user_decision`。

#### 4.5.3 交付计划状态机

```
awaiting_user_decision → active → validating → accepted → completed
                                → repairing → needs_attention
                                → cancelled
```

#### 4.5.4 交付任务状态机

```
preview → blocked → ready → in_progress → review → done | failed | cancelled
```

任务通过 `depends_on_task_ids` 构成 DAG。`DeliveryPlanService.start_task()` 校验所有前置条件（计划活跃、门已解、依赖完成、租约可用、session 存在）。

### 4.6 Application Services（应用服务）

#### 4.6.1 DeliveryPlanService

系统中最复杂的服务，编排交付全流程：

- **`generate_plan()`**：获取会议记录 + 需求 + 设计文档 + session，调用 planner agent，构建依赖图，校验无环，创建任务和可选决策门。分类 needs_attention 项（blocking vs assumable）。
- **`resolve_gate()`**：应用用户对决策门的决议，将 preview 任务推进为 blocked/ready。
- **`start_task()`**：校验 5 项前置条件，获取租约，设置 in_progress。
- **`complete_task()`**：保存执行结果，释放租约，自动推进被阻塞任务，全部完成时推进计划到 validating。
- **`accept_plan()`**：标记计划 accepted，自动推进需求到 done。

#### 4.6.2 KickoffService

异步会议执行器：
- `start_kickoff()`：创建 KickoffTask 记录，注册 7 个 agent session，启动 `asyncio.create_task` 执行会议图。
- `_run_meeting_graph()`：调用 `build_meeting_graph().ainvoke()`，逐步记录进度，生成交付计划（最多重试 2 次），推进需求到 approved，更新澄清 session 到 completed，WebSocket 广播。
- 启动时 `_recover_stuck_tasks()`：将上次服务崩溃遗留的 running 任务标记为 failed。

### 4.7 Observability（可观测性）

两套独立的 Langfuse 上报机制：

#### 4.7.1 主动埋点（`LangfuseTelemetry`）

在业务代码中通过上下文管理器主动埋点：

- `graph_trace()`：整图执行的 trace 级别
- `node_span()`：每个图节点
- `llm_observation()`：每次 LLM 调用（generation 级别）

所有 metadata/input/output 经过 `redact()` 脱敏（过滤 api_key/secret/token，长文本截断）。

#### 4.7.2 Hook 解析（`langfuse_tracer`）

Claude Code CLI 的 hook 事件触发：
- 从 stdin 读取 payload（sessionId + transcriptPath）
- 增量读取 transcript JSONL 文件（基于 offset 状态持久化）
- 组装 Turn（user → assistant → tool_results），逐 turn 上报
- 使用文件锁 + JSON 状态文件跟踪进度

### 4.8 API Layer（接口层）

#### 4.8.1 REST API

FastAPI 应用，11 个路由模块挂在 `/api` 下：

| 模块 | 路径前缀 | 职责 |
|---|---|---|
| requirements | /api/requirements | 需求 CRUD + 状态转换 |
| design_docs | /api/design-docs | 设计文档管理 |
| balance_tables | /api/balance-tables | 数值平衡表 |
| bugs | /api/bugs | Bug CRUD + 状态流转 |
| delivery | /api/delivery | 交付计划/任务/决策门/验收 |
| clarifications | /api/clarifications | 需求澄清对话 |
| meetings | /api/meetings | 会议记录 + transcript |
| workflows | /api/workflows | 遗留工作流触发 |
| sessions | /api/sessions | Agent session 管理 |
| agents | /api/agents | Agent 对话 |
| pool | /api/pool | 线程池状态 |
| logs | /api/logs | 审计日志 |

所有端点通过 `workspace` 查询参数选择数据目录。

#### 4.8.2 WebSocket

`/ws` 端点实现实时推送：
- 客户端 `subscribe(workspace)` 加入订阅
- 服务端 `broadcast_entity_changed(entity_type, entity_id, workspace, action)` 广播变更
- 客户端收到后通过 `queryClient.invalidateQueries()` 触发 React Query 重新获取

### 4.9 Frontend（前端）

#### 4.9.1 页面结构

| 页面 | 职责 |
|---|---|
| RequirementsBoard | 主工作台，需求生命周期管理，澄清对话 → kickoff → 交付 |
| DeliveryBoard | 看板视图（Blocked/Ready/In Progress/Review/Done），决策门、验收、假设展示 |
| DesignEditor | 设计文档编辑/审批 |
| BugsBoard | Bug 管理 |
| AgentChat | 与 Agent 直接对话 |
| Agents | Agent 列表 |
| Logs | 审计日志查看 |

#### 4.9.2 实时更新策略

WebSocket + React Query Invalidation 混合模式：
- WebSocket 推送实体变更事件
- React Query 按需重新获取受影响的数据
- 避免了全量轮询的开销

#### 4.9.3 类型安全

`web/src/lib/types.ts` 从 FastAPI OpenAPI spec 自动生成，确保前后端类型一致。

---

## 5. 核心数据流

### 5.1 完整生命周期

```
用户创建需求 (draft)
    │
    ▼
需求澄清对话 (ClarificationSession)
    │  多轮 user/assistant 对话，积累 meeting context
    │  readiness check 通过后 → ready
    ▼
Kickoff (异步)
    │  KickoffService.start_kickoff()
    │  注册 7 个 agent session
    │  执行 Meeting Graph:
    │    moderator_prepare → [agent_opinion × N] → moderator_summarize
    │    → moderator_discussion → moderator_minutes
    │  生成 DeliveryPlan（含 DAG 任务 + 决策门 + 假设）
    │  需求 → approved
    ▼
交付执行 (Delivery Graph)
    │  prepare_context → run_task (循环)
    │  每个任务：获取租约 → 调用 Agent → 记录结果 → 释放租约
    │  自动推进阻塞任务
    ▼
验收 (Acceptance Gate)
    │  构建验收契约（需求 criteria + 会议共识 + 系统检查）
    │  运行自动化验证：
    │    npm install → build → test → Playwright 冒烟测试
    │  评估每个 criterion → passed / failed / inconclusive
    │  失败 → 生成 bug_fix 任务 → 循环回 run_task（最多 3 次）
    │  超限 → needs_attention（人工介入）
    ▼
完成
    │  计划 accepted → 需求 → done
    │  所有状态变更记录到 ActionLog
    │  WebSocket 实时通知前端
```

### 5.2 实体关系

```
Requirement (根聚合)
  ├── DesignDoc (1:1)
  ├── BalanceTable[] (1:N)
  ├── BugCard[] (1:N)
  ├── RequirementClarificationSession (1:1)
  │     ├── ClarificationMessage[] (embedded)
  │     └── MeetingContextDraft (embedded)
  ├── KickoffTask (1:1)
  ├── MeetingMinutes (1:1)
  │     ├── AgentOpinion[] (embedded)
  │     └── MeetingTranscript (1:1)
  ├── DeliveryPlan (1:N)
  │     ├── KickoffDecisionGate (1:1)
  │     │     └── GateItem[] (embedded)
  │     ├── DeliveryTask[] (1:N, DAG via depends_on_task_ids)
  │     │     ├── TaskExecutionResult (0:1)
  │     │     └── DeliveryTaskEvent[] (1:N)
  │     ├── AcceptanceContract (1:1)
  │     │     └── AcceptanceCriterion[] (embedded)
  │     └── AcceptanceRun[] (1:N)
  │           ├── AcceptanceEvidence[] (embedded)
  │           └── AcceptanceCriterionResult[] (embedded)
  ├── ProjectAssumption[] (1:N)
  └── NeedsAttentionItem[] (1:N)
```

---

## 6. 状态机汇总

| 实体 | 状态数 | 终态 |
|---|---|---|
| Requirement | 10 | done |
| DesignDoc | 4 | approved / sent_back(循环) |
| Bug | 7 | closed |
| DeliveryPlan | 8 | completed / cancelled / needs_attention |
| DeliveryTask | 8 | done / failed / cancelled |
| ClarificationSession | 5 | completed / failed |
| AcceptanceRun | 4 | passed / failed / needs_attention |
| KickoffTask | 4 | completed / failed |
| BalanceTable | 4 | approved / sent_back(循环) |
| KickoffDecisionGate | 3 | resolved / cancelled |

---

## 7. 设计决策记录

| 决策 | 理由 |
|---|---|
| JSON 文件而非数据库 | 本地开发工具场景，零运维依赖，Git 可追踪 |
| Pydantic strict + extra="forbid" | 防止字段注入，数据契约严格 |
| 双路径 LLM 调用 | FastAPI 已在 asyncio event loop 中，SDK 直调会冲突 |
| Agent Profile YAML | 将系统提示词与代码解耦，非开发者可调整 |
| 文件哈希而非 git diff 做变更检测 | 不依赖 git 追踪状态，对新文件同样有效 |
| 线程池而非 asyncio 并发 | Claude SDK 内部有 blocking 调用，线程池更安全 |
| Session Lease 互斥 | Claude CLI session 不支持并发使用，必须串行化 |

---

## 8. 评价与建议

### 8.1 优点

1. **架构层次清晰**：Runtime / LLM / Agent / Storage / Domain / API 六层分离，职责明确。Domain 层纯函数设计，无副作用，易于测试。
2. **状态机完备**：10 个实体有明确的状态机定义，转换校验集中，不会出现非法状态。
3. **防御性编程到位**：Agent 全部内置 fallback，LLM 不可用时管线不崩溃。子进程管理有超时和 kill-all。ID 验证防路径穿越。
4. **可观测性双轨**：主动埋点覆盖业务层粒度，hook 解析覆盖 CLI 会话粒度，互补不重叠。
5. **类型安全贯穿**：Pydantic strict 模式 + 前端 OpenAPI 生成 + TypeScript strict，全链路类型约束。
6. **事件溯源可审计**：DeliveryTaskEvent 和 ActionLog 提供不可变审计轨迹，任何操作可追溯。

### 8.2 问题与风险

1. **graph.py 过度集中**：该文件是系统的"上帝模块"，导入了几乎所有其他模块，包含 4 张图的完整定义、任务调度逻辑、状态合并逻辑。单文件超过 1500 行，任何修改都有高冲突风险。

   **建议**：将每张图拆分为独立模块（`graphs/demo.py`、`graphs/meeting.py`、`graphs/delivery.py`、`graphs/design.py`），共享的辅助函数抽取到 `graphs/common.py`。

2. **ClaudeWorkerAdapter 与 ClaudeRoleAdapter 功能重叠**：WorkerAdapter 是遗留产物，功能被 RoleAdapter 完全覆盖。两套并存的 adapter 增加维护负担，且修复往往需要改两处（如本次 Langfuse output undefined 的 bug）。

   **建议**：将 WorkerAgent 迁移到 ClaudeRoleAdapter，统一为单一路径，移除 `claude_worker.py`。

3. **DeliveryPlanService 职责过重**：该服务包含了计划生成、门解、任务生命周期（start/complete/fail/retry）、bug fix 任务创建、验收、board 聚合等所有逻辑。它直接操作 6 种以上的 repository，是系统中最大的单一类。

   **建议**：按关注点拆分：`PlanGenerationService`、`TaskLifecycleService`、`AcceptanceService`、`BoardQueryService`。DeliveryPlanService 保留为编排门面。

4. **JSON 文件存储的扩展性上限**：`list_all()` 每次全量 glob + 读取所有文件，无索引。当实体数量达到数千级别时（长期运行的 workspace），性能会成为瓶颈。

   **建议**：短期可接受（本地工具场景）。若需扩展，考虑引入 SQLite 作为本地索引层，保持 JSON 文件作为真实数据源（SQLite 仅存索引和元数据）。

5. **Meeting Graph 的 fan-out 并行度受限于 agent_pool**：虽然 LangGraph 的 `Send` 可以同时触发多个 agent_opinion 节点，但 `agent_pool` 的默认 max_workers=3 限制了实际并行度。当参会 Agent 超过 3 个时会排队。

   **建议**：将 pool size 与实际 agent 数量对齐（可通过配置读取），或为 meeting 场景使用独立的轻量级 pool。

6. **子进程 fallback 的错误信息丢失**：子进程模式通过 stderr 传递错误，但 stderr 内容可能被截断或丢失（如子进程崩溃）。`claude_roles.py` 的 `_main()` 中 `sys.stderr` 输出只有错误消息字符串，丢失了完整 traceback。

   **建议**：子进程模式增加 `--verbose` 标志输出完整 traceback 到文件，或在 subprocess 调用端增加 stderr 日志记录。

7. **前端轮询与 WebSocket 并存**：部分页面（如 KickoffTask 进度）使用定时轮询而非完全依赖 WebSocket 推送。两者并存增加了前端复杂度。

   **建议**：统一使用 WebSocket 推送 KickoffTask/DeliveryTask 进度，移除轮询逻辑。WebSocket 断连时 fallback 到低频轮询。

8. **缺少集成测试的 LLM mock 策略**：测试中大量使用 `LangfuseTelemetry.fake()` 和 agent 构造器注入来绕过 LLM 调用，但缺少统一的 LLM mock 框架。部分测试的 mock 方式不一致。

   **建议**：引入统一的 `FakeClaudeRoleAdapter` 作为测试基础设施，所有 agent 测试通过它注入确定性输出。

9. **配置分散**：LLM 配置（API key、model、mode）在 `.env` 中，Agent 配置在 YAML profile 中，graph 配置硬编码在 `graph.py` 中，pool 配置在环境变量中。缺少统一的配置模型。

   **建议**：创建 `StudioConfig` Pydantic 模型，统一加载和校验所有配置来源，提供单一入口。

10. **验收测试与业务逻辑耦合**：`acceptance_verifier.py` 直接调用 Playwright，与 `acceptance_evaluator.py` 的评估逻辑紧密耦合。验收测试的扩展（如添加移动端测试、性能测试）需要修改核心模块。

    **建议**：引入 `VerificationProvider` Protocol，将验证执行与评估逻辑解耦。Playwright 验证作为一个 provider 实现，新的验证类型只需增加 provider。
