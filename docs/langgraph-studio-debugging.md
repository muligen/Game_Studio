# LangGraph Studio Debugging

This guide is a quick reminder for debugging Game Studio graphs in LangGraph Studio.

## Start Studio

From the repo root:

```powershell
uvx --refresh --from "langgraph-cli[inmem]" --with-editable . --python 3.12 langgraph dev
```

If `langgraph` is already installed locally, this also works:

```powershell
langgraph dev
```

Open the local Studio URL printed by the command.

## Available Graphs

Graphs are registered in `langgraph.json`.

- `game_studio_demo`: demo planner -> worker -> reviewer flow
- `studio_design_workflow`: design workflow
- `studio_delivery_workflow`: delivery workflow
- `studio_meeting_workflow`: multi-agent kickoff meeting graph

For meeting debugging, choose `studio_meeting_workflow`.

## Prepare Meeting Workspace

Create a requirement first. Example:

```powershell
$ws = ".runtime-data/langgraph-meeting-acceptance"

uv run python -m studio.interfaces.cli requirement create `
  --workspace $ws `
  --title "Turn-based combat kickoff acceptance"
```

Copy the printed requirement id, for example `req_8fab476c`.

The graph input expects `workspace_root` to point at the internal `.studio-data` directory:

```text
F:\projs\Game_Studio\.runtime-data\langgraph-meeting-acceptance\.studio-data
```

## Meeting Graph Input

Paste this into Studio when invoking `studio_meeting_workflow`.

Update `requirement_id` if your generated id is different.

```json
{
  "workspace_root": "F:\\projs\\Game_Studio\\.runtime-data\\langgraph-meeting-acceptance\\.studio-data",
  "project_root": "F:\\projs\\Game_Studio",
  "requirement_id": "req_8fab476c",
  "user_intent": "为回合制战斗系统召开 kickoff meeting。请重点讨论 MVP 范围、战斗节奏、数值风险和验收标准。当前存在明确冲突：设计希望首版包含行动顺序条和元素克制，开发认为这会超出 MVP，QA 担心验收标准无法量化。请在总结阶段保留需要二轮讨论的 conflict_resolution_needed。",
  "meeting_context": {
    "summary": "用户想做一个轻量但有策略深度的回合制战斗系统。核心体验是 3 名玩家单位对抗 3 名敌人，强调技能选择、行动顺序和资源消耗。",
    "requirement": {
      "id": "req_8fab476c",
      "title": "Turn-based combat kickoff acceptance",
      "status": "draft",
      "priority": "medium"
    },
    "design_context": {
      "core_loop": "玩家选择单位行动，使用普通攻击、技能或防御，击败全部敌人后进入结算。",
      "mvp_scope": [
        "3v3 回合制战斗",
        "基础行动顺序",
        "普通攻击、技能、防御",
        "战斗胜负结算"
      ],
      "out_of_scope": [
        "复杂装备词条",
        "多人联机",
        "大型关卡编辑器"
      ]
    },
    "goals": [
      "确认 MVP 是否包含行动顺序条",
      "确认是否首版加入元素克制",
      "确认数值验收标准",
      "确认开发和 QA 的最小可交付边界"
    ],
    "constraints": [
      "首版必须控制在两周内完成",
      "优先保证战斗循环可玩",
      "不要引入过多 UI 和数值复杂度"
    ],
    "open_questions": [
      "行动顺序条是 MVP 必需，还是可以先用固定速度排序？",
      "元素克制是否会显著增加 QA 组合测试成本？",
      "技能数值验收应该用固定样例战斗，还是用胜率区间？"
    ],
    "known_conflicts": [
      "Design wants action timeline and elemental counters in MVP.",
      "Dev wants to defer elemental counters and keep only deterministic turn order.",
      "QA needs measurable acceptance criteria before approving combat balance."
    ],
    "validated_attendees": [
      "design",
      "moderator",
      "producer",
      "dev",
      "qa",
      "design"
    ]
  }
}
```

## What To Inspect

Use Studio's node state/output panels after each node.

- After `moderator_prepare`, inspect `attendees`.
- Expected attendee result: only registered participant agents remain, usually `design`, `dev`, `qa`.
- `moderator` and `producer` should be filtered out because they are not participant agents in the meeting fan-out.
- Duplicate `design` should be removed.
- After `agent_opinion`, inspect `opinions`.
- Expected opinions keys should match the filtered attendees.
- After `moderator_summarize`, inspect `conflict_resolution_needed`.
- If it is truthy/non-empty, the next node should be `moderator_discussion`.
- After `moderator_discussion`, inspect `supplementary` and `unresolved_conflicts`.
- After `moderator_minutes`, inspect `minutes.pending_user_decisions` and `minutes.supplementary`.

## Saved Output

Meeting minutes are saved under:

```text
<workspace>/.studio-data/meetings/
```

For the example workspace:

```powershell
Get-ChildItem .runtime-data/langgraph-meeting-acceptance/.studio-data/meetings
Get-Content (Get-ChildItem .runtime-data/langgraph-meeting-acceptance/.studio-data/meetings/*.json | Select-Object -First 1).FullName
```

## LLM Prompt Logs

Workflow LLM prompt/reply logs are stored when the graph path records them.

For demo runtime logs:

```text
<workspace>/logs/
```

For graph-specific or workflow-specific logs, check the workspace runtime folders first:

```powershell
Get-ChildItem .runtime-data -Recurse -Filter *.json | Where-Object { $_.FullName -match "llm|log" } | Select-Object FullName
```

If a node used deterministic fallback because Claude failed, the LLM call may not have produced a useful prompt/reply log. In Studio, inspect node output for `fallback_used` or missing LLM telemetry.

## Common Problems

If Studio says `requirement_id` cannot be loaded, check that `workspace_root` points to `.studio-data`, not the outer workspace directory.

If `moderator_discussion` does not run, inspect `moderator_summarize.conflict_resolution_needed`. The graph only enters the second discussion round when that value is truthy.

If all unknown attendees disappear and the graph still runs `design/dev/qa`, that is expected. Empty attendee validation falls back to the default supported attendees.

If you want project-scoped Claude sessions, initialize through:

```powershell
uv run python -m studio.interfaces.cli project kickoff `
  --workspace .runtime-data/project-session-demo `
  --requirement-id <req_id> `
  --user-intent "为这个项目召开 kickoff meeting"
```

Then debug an individual agent with:

```powershell
uv run python -m studio.interfaces.cli agent chat `
  --agent design `
  --workspace .runtime-data/project-session-demo `
  --project-id <project_id> `
  --message "刚才会议里我的职责是什么？" `
  --verbose
```
