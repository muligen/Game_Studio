# Agent Profile Management Design

Date: 2026-04-20

## Goal

Introduce strict, repository-managed configuration for all Claude-backed agents so that:

- every agent has its own checked-in profile file
- each profile defines the agent's system prompt
- each profile defines the Claude SDK working directory used to load `CLAUDE.md`, skills, rules, and related context
- missing or invalid configuration fails fast with no fallback behavior
- developers can debug any individual agent from the CLI by talking to it directly

This design applies to the current managed agents:

- `worker`
- `reviewer`
- `design`
- `dev`
- `qa`
- `quality`
- `art`

## Non-Goals

- No web UI for agent management in this phase
- No profile editing UX in the browser
- No runtime fallback to built-in prompts or repo-root Claude context
- No profile inheritance or layered config system
- No automatic migration of old ad hoc prompt definitions beyond replacing them in code

## Current Problems

Today agent configuration is split across code and implicit runtime context:

- role prompts are hardcoded in `studio/llm/claude_roles.py`
- worker prompt is hardcoded in `studio/llm/claude_worker.py`
- Claude SDK context is inferred from `project_root`
- there is no first-class, per-agent configuration object
- there is no supported way to talk directly to one configured agent to verify its behavior

This causes three concrete issues:

1. Prompt behavior is not centrally managed or reviewable as configuration.
2. Claude context files such as skills and rules cannot be independently assigned per agent.
3. When an agent behaves unexpectedly, there is no clean debugging path to validate the exact configuration in isolation.

## Proposed Architecture

Add a strict agent profile system with four parts:

1. `AgentProfile` schema
2. `AgentProfileLoader`
3. adapter integration for role and worker Claude adapters
4. CLI debugging entrypoint

The profile becomes the only configuration source for agent prompt and Claude SDK context root.

## Repository Layout

Add a checked-in profile directory:

- `studio/agents/profiles/worker.yaml`
- `studio/agents/profiles/reviewer.yaml`
- `studio/agents/profiles/design.yaml`
- `studio/agents/profiles/dev.yaml`
- `studio/agents/profiles/qa.yaml`
- `studio/agents/profiles/quality.yaml`
- `studio/agents/profiles/art.yaml`

Each profile may point at a checked-in Claude context directory, for example:

- `.claude/agents/worker/`
- `.claude/agents/reviewer/`
- `.claude/agents/design/`
- `.claude/agents/dev/`
- `.claude/agents/qa/`
- `.claude/agents/quality/`
- `.claude/agents/art/`

Those directories are where `CLAUDE.md`, skills, rules, and other Claude Agent SDK context files live.

## Profile Schema

Create a strict schema in `studio/agents/profile_schema.py`.

Required fields:

- `name`
- `system_prompt`
- `claude_project_root`

Optional fields for this phase:

- `enabled`
- `model`
- `fallback_policy`

Example:

```yaml
name: reviewer
enabled: true
system_prompt: |
  You are the reviewer role.
  Return only JSON with decision, reason, and risks.
  decision must be continue or retry.
  risks must be a list of concrete issues.
claude_project_root: .claude/agents/reviewer
model: ""
fallback_policy: deterministic
```

Validation rules:

- `name` must be non-empty and match the requested agent name
- `system_prompt` must be a non-empty string
- `claude_project_root` must be a non-empty path string
- relative `claude_project_root` values are resolved relative to the repository root
- resolved `claude_project_root` must exist and must be a directory

Strictness rules:

- no missing profile fallback
- no missing field fallback
- no fallback to hardcoded prompts
- no fallback to repository root as Claude SDK working directory

## Profile Loader

Create `studio/agents/profile_loader.py`.

Responsibilities:

- locate `studio/agents/profiles/<agent>.yaml`
- parse and validate the YAML into `AgentProfile`
- resolve `claude_project_root` to an absolute path
- return a strongly typed profile object

Failure behavior:

- profile file missing: raise a dedicated configuration error
- malformed YAML: raise a dedicated configuration error
- missing required field: raise a dedicated configuration error
- missing Claude directory: raise a dedicated configuration error

Errors must be explicit because the operator is expected to fix configuration, not rely on fallback behavior.

## Adapter Integration

Update both Claude adapters to operate from a loaded profile instead of implicit prompt defaults:

- `ClaudeRoleAdapter`
- `ClaudeWorkerAdapter`

Required behavior:

- prompt text comes from `AgentProfile.system_prompt`
- Claude SDK execution root comes from `AgentProfile.claude_project_root`
- any prompt-building logic appends structured runtime context to the configured system prompt

Role adapter notes:

- output schema enforcement remains in code
- role payload models remain in code
- the prompt text source moves from `_ROLE_PROMPTS` to profile files

Worker adapter notes:

- worker prompt text also moves into the worker profile
- structured context such as the user prompt remains appended by code

After migration, hardcoded prompt maps should no longer be treated as configuration sources. If transitional constants remain temporarily, they should only exist until the migration is complete and should not be used at runtime.

## Agent Construction

Each managed agent class should load its own profile by agent name and pass that profile into the adapter.

Affected classes:

- `studio/agents/worker.py`
- `studio/agents/reviewer.py`
- `studio/agents/design.py`
- `studio/agents/dev.py`
- `studio/agents/qa.py`
- `studio/agents/quality.py`
- `studio/agents/art.py`

Target responsibility split:

- profile files define agent configuration
- Claude context directories define agent-local Claude SDK context
- adapters execute Claude SDK calls using that configuration
- agent classes map workflow state into prompt context and map model output back into workflow data
- graphs and workflows do not define prompts or Claude SDK roots

## CLI Debugging

Add a new CLI namespace for direct agent debugging:

- `studio agent chat --agent reviewer --message "Check this design"`
- `studio agent chat --agent reviewer --interactive`

Default behavior:

- single-turn mode
- `--message` is required unless `--interactive` is supplied
- command loads the agent profile
- command runs the target agent using its configured prompt and Claude root
- command prints the agent reply

Interactive behavior:

- enabled with `--interactive`
- starts a simple REPL
- each entered line is treated as a user message
- `exit` and `quit` close the session
- the same agent profile and Claude context root are reused for the whole session

Verbose mode:

- `--verbose` prints debugging metadata in addition to the reply

Verbose output should include:

- `agent`
- `profile_path`
- `claude_project_root`
- system prompt summary or full prompt
- final reply

Strict CLI behavior:

- unknown agent name: fail
- missing profile: fail
- invalid profile: fail
- missing Claude directory: fail
- Claude SDK execution error: fail
- direct debug chat must not auto-fallback to deterministic workflow behavior

The purpose of this command is to verify configuration exactly as configured.

## Runtime Data Flow

### Single Agent Execution

1. Caller requests agent `qa`.
2. Loader reads `studio/agents/profiles/qa.yaml`.
3. Loader validates `system_prompt` and resolves `claude_project_root`.
4. `QaAgent` constructs `ClaudeRoleAdapter(profile=qa_profile)`.
5. Adapter builds final prompt from:
   - profile system prompt
   - structured runtime context
6. Claude SDK runs with working directory equal to `qa_profile.claude_project_root`.
7. Adapter parses output using existing output contracts.
8. Agent returns workflow state patch or CLI reply.

### Workflow Execution

1. Workflow graph creates a managed agent class.
2. Agent class loads its checked-in profile.
3. Adapter executes under that profile's Claude root.
4. Workflow continues using parsed structured output.
5. If profile resolution fails, the workflow fails immediately instead of silently changing behavior.

## Error Handling

Introduce a dedicated configuration exception family, for example:

- `AgentProfileError`
- `AgentProfileNotFoundError`
- `AgentProfileValidationError`

Principles:

- configuration errors are operator-facing and must be actionable
- failures should name the agent and the exact invalid field or missing path
- direct debug commands should surface those errors without converting them into fallback replies

Example messages:

- `agent profile not found: reviewer`
- `agent profile 'qa' missing required field: system_prompt`
- `agent profile 'dev' claude_project_root does not exist: F:\...\.claude\agents\dev`

## Testing Strategy

Add tests in three groups.

### Profile Loader Tests

- loads a valid profile successfully
- rejects missing profile files
- rejects malformed YAML
- rejects missing `system_prompt`
- rejects missing `claude_project_root`
- rejects non-existent Claude root directories
- resolves relative Claude root paths against repository root

### Adapter and Agent Wiring Tests

- role adapter uses profile `system_prompt`
- worker adapter uses worker profile `system_prompt`
- adapters execute with profile Claude root instead of repo root
- managed agents load the expected profile for their role
- missing profile causes execution failure
- missing Claude root causes execution failure
- runtime does not fall back to built-in prompt definitions

### CLI Tests

- `agent chat --agent <name> --message ...` works in single-turn mode
- `agent chat --agent <name> --interactive` starts an interactive session
- `--verbose` includes configuration metadata
- unknown agent names fail clearly
- invalid profiles fail clearly
- Claude execution failures surface clearly

## Acceptance Criteria

This feature is complete when all of the following are true:

- every managed agent has a checked-in profile file
- each managed agent profile defines `system_prompt`
- each managed agent profile defines `claude_project_root`
- runtime fails fast when a required profile is missing or invalid
- runtime fails fast when the Claude context directory is missing
- role and worker prompt configuration comes from profiles, not hardcoded prompt maps
- Claude Agent SDK runs in the configured per-agent Claude directory
- operators can directly chat with any managed agent via CLI
- operators can use `--interactive` to hold a continuous debug conversation with a single agent
- operators can use `--verbose` to verify which profile and Claude root were used

## Migration Notes

Implementation should proceed in this order:

1. add schema and loader
2. add checked-in profiles for all managed agents
3. wire adapters to consume profiles
4. wire managed agents to load profiles
5. add CLI debug command
6. remove runtime reliance on hardcoded prompt definitions
7. add or update tests

This order minimizes ambiguity because the configuration source is established before adapter and CLI behavior are changed.
