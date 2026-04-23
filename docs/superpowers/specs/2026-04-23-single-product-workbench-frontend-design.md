# Single Product Workbench Frontend Design

## Summary

Change the web board from a generic requirements Kanban into a single-product workbench. The workspace represents exactly one product. The first requirement establishes the product MVP baseline; every later requirement is treated as a change request against that existing product.

This spec is frontend-focused. It defines what the user should see and how the UI should express the lifecycle. Backend fields and APIs are referenced as dependencies, but the implementation branch can start with frontend structure and mock/derived state where backend support is not available yet.

## Product Model

Do not support multiple products in this iteration.

The current workspace is the product.

```text
workspace = one product
first requirement = Product MVP
later requirements = Change Request
```

The frontend should avoid showing product switchers, product lists, or product creation flows.

## User Mental Model

The user should understand three things immediately:

- whether the product MVP baseline exists
- whether a card is defining the product or changing an existing product
- what the next action is: clarify, meet, decide, deliver, review, or done

The board should not imply every requirement starts a brand-new product. After the product baseline is active, new requirements should read as additions to the existing product.

## Page Structure

Replace the current "Requirements Board" heading with a product workbench layout.

Recommended page title:

```text
Current Product Workbench
```

Top area:

- product status card
- MVP baseline summary
- primary action button

Main area:

- lifecycle board
- clarification dialog
- optional selected-card side panel in a later iteration

Footer/secondary area:

- agent pool status

## Product Status Card

Add a top-level status card above the board.

States:

### No Product Baseline

Shown when no MVP baseline exists.

Copy:

```text
No product baseline yet
Create and clarify the first requirement to define the MVP.
```

Primary action:

```text
Create MVP Requirement
```

### Defining MVP

Shown when there is an active initial requirement that has not completed kickoff/baseline creation.

Copy:

```text
MVP definition in progress
Clarify the product goal, MVP scope, constraints, and acceptance criteria before kickoff.
```

Primary action:

```text
Continue Clarifying MVP
```

### Product Active

Shown after the MVP baseline exists.

Copy:

```text
Product baseline active
New requirements are treated as change requests against the current product.
```

Primary action:

```text
Add Change Request
```

## Requirement Kinds

Cards should visually distinguish two requirement kinds.

### Product MVP

The first requirement in a workspace before product baseline activation.

Badge:

```text
Product MVP
```

Clarify dialog title:

```text
Clarify MVP
```

Preview title:

```text
MVP Brief Preview
```

Clarification goal:

```text
Collect enough information to start a kickoff meeting for the initial product MVP.
```

### Change Request

Every requirement created after the product baseline exists.

Badge:

```text
Change Request
```

Clarify dialog title:

```text
Clarify Change
```

Preview title:

```text
Change Request Preview
```

Clarification goal:

```text
Clarify how this request changes the existing product and whether it needs a meeting.
```

## Lifecycle Board Columns

Replace raw backend workflow columns with product lifecycle columns.

Recommended columns:

```text
Product Setup
Clarifying
Ready for Meeting
Decision Needed
Ready for Delivery
In Progress
Review / Acceptance
Done
```

The first frontend iteration can map existing backend statuses into these columns.

Suggested mapping:

| Frontend Column | Existing Sources |
| --- | --- |
| Product Setup | first `draft` requirement when no baseline exists |
| Clarifying | `draft` or `designing` cards with an active clarification session |
| Ready for Meeting | clarification session `ready`, no meeting started |
| Decision Needed | future kickoff decision gate, unresolved meeting conflicts |
| Ready for Delivery | `approved` or future delivery tasks ready |
| In Progress | `implementing`, `testing`, `quality_check` |
| Review / Acceptance | `pending_user_review`, `self_test_passed`, `pending_user_acceptance` |
| Done | `done` |

If backend support for clarification sessions or product baseline status is missing from a list endpoint, the frontend may initially derive a minimal view from requirements only, but the UI should be designed around the lifecycle columns above.

## Card Design

Each requirement card should show:

- requirement id
- title
- kind badge: `Product MVP` or `Change Request`
- lifecycle badge
- priority
- next action
- linked design doc if available

Next action examples:

- `Clarify MVP`
- `Clarify Change`
- `Start Kickoff`
- `Resolve Decision`
- `Start Delivery`
- `Review`

Do not show technical backend statuses as the primary label if a clearer lifecycle label exists. Backend status can remain as a small secondary label for debugging.

## Clarification Dialog Changes

The existing clarification dialog should become mode-aware.

Inputs:

- `requirementKind`: `product_mvp | change_request`
- `productBaselineStatus`: `not_started | defining_mvp | active`

Mode behavior:

### Product MVP Mode

The dialog should tell the user:

```text
Goal: define enough MVP context to start a kickoff meeting.
```

Context preview sections:

- MVP summary
- MVP must-haves
- Out of scope
- Success criteria
- Constraints
- Risks / unknowns
- Suggested attendees

### Change Request Mode

The dialog should tell the user:

```text
Goal: clarify how this request changes the current product.
```

Context preview sections:

- Change summary
- Affected systems
- User value
- Acceptance criteria
- Dependencies / conflicts
- Suggested attendees
- Meeting needed?

The dialog should not ask broad MVP questions for change requests.

## Product Baseline Visibility

Even before backend has full system documents, the frontend should reserve a section for product baseline.

Display:

- baseline status
- MVP requirement link
- latest kickoff meeting link if available
- known system docs if available

Empty state:

```text
The product baseline will appear here after the MVP kickoff meeting.
```

Future system docs can appear here:

- Gameplay Requirements
- UI/UX Requirements
- Technical Requirements
- QA Acceptance Requirements
- Art/Content Requirements

These should be shown as baseline artifacts, not as separate products.

## Creation Flow

Button label depends on baseline state.

When no baseline exists:

```text
Create MVP Requirement
```

When baseline exists:

```text
Add Change Request
```

The create dialog can remain simple, but its title and helper text should change:

- MVP: "Describe the product you want to build."
- Change request: "Describe what you want to add or change."

## Backend Dependencies

The clean backend model is:

```text
.studio-data/product_baseline.json
```

Expected shape:

```json
{
  "status": "not_started | defining_mvp | active",
  "mvp_requirement_id": "req_xxx",
  "mvp_brief": {},
  "system_docs": [],
  "latest_meeting_id": "meeting_xxx",
  "created_at": "...",
  "updated_at": "..."
}
```

Frontend can be implemented in two phases:

### Phase 1: Derived Frontend State

If no product baseline endpoint exists, derive:

- no requirements means `not_started`
- first non-done requirement is likely `Product MVP`
- additional requirements are shown as `Change Request`

This is acceptable only as a temporary UI bridge.

### Phase 2: Real Product Baseline API

Add/use an API endpoint:

```http
GET /api/product-baseline?workspace=<workspace>
```

The board should use this endpoint as the source of truth.

## Non-Goals

- Do not add multi-product support.
- Do not add a product switcher.
- Do not build a full document editor in this frontend pass.
- Do not generate system requirement documents directly from the clarify chat.
- Do not replace Meeting Graph or delivery planning.

## Acceptance Criteria

- The page is framed as a single product workbench, not a generic requirements board.
- The UI distinguishes initial `Product MVP` from later `Change Request` cards.
- The first requirement guides the user toward MVP clarification and kickoff.
- Later requirements guide the user toward change clarification against the existing product.
- Board columns use lifecycle language: clarify, meeting, decision, delivery, review, done.
- The clarification dialog preview title and sections change based on requirement kind.
- The page reserves visible space for product baseline artifacts.
- No UI suggests multiple products are supported.
- Existing requirement listing, clarify dialog opening, and build behavior remain intact.

## Open Implementation Notes

- If backend does not yet expose `product_baseline`, the implementation branch should create a small frontend helper such as `deriveProductWorkbenchState(requirements)`.
- Keep the helper isolated so it can be replaced by a real API later.
- Avoid spreading lifecycle mapping logic across multiple components.
- Prefer a dedicated `ProductWorkbenchHeader` and `ProductLifecycleBoard` wrapper over making `RequirementsBoard.tsx` larger.
