# Config Panel Policy-First Redesign (Team Admin)

Date: 2026-04-10  
Status: Proposed  
Audience: Team admins operating OpenClaw in real environments

## Context

The current configuration panel works, but it exposes implementation details before operational intent. For team admins, this creates high cognitive load and frequent ambiguity:

- `Profile` vs `Tools` precedence is not explicit.
- Effective runtime behavior is hard to infer from current form values.
- Invalid schema states may only be noticed after reload/log inspection.
- Admins cannot quickly answer: "What can this bot actually do right now?"

This redesign shifts the product from "edit config values" to "define and validate bot policy."

## Product Goals

1. Make effective bot behavior immediately understandable.
2. Remove ambiguity between baseline profile and manual overrides.
3. Prevent invalid config from being applied.
4. Reduce admin time-to-confidence before publish.
5. Add explainability and runtime validation as first-class capabilities.

## Non-Goals

- Replacing OpenClaw gateway internals.
- Building a generic config editor for unrelated products.
- Adding non-admin end-user features.

## Design Principles

- Intent before mechanics: show policy outcome before raw fields.
- Source transparency: every effective rule shows where it came from.
- Safe by default: invalid states blocked pre-apply.
- Runtime truth: logs and effective state integrated in UI.
- Admin speed: common tasks done in fewer steps with lower uncertainty.

## Target Mental Model

The panel should teach and enforce this model:

`System defaults < Profile baseline < Team policy < Manual overrides < Runtime safety guards`

Each relevant field in the UI must display:

- Current effective value
- Source of value (profile/manual/system)
- Override/conflict state (if any)
- Reason label for blocked behavior

## Key UX Problems and Resolutions

### Problem 1: Profile vs Tools ambiguity

Admins currently cannot tell if profile selection supersedes manual tool toggles.

Resolution:

- Introduce explicit precedence banner in `Capabilities` section.
- Add per-tool metadata:
  - state: `inherited | allowed | denied`
  - source: `profile | manual | guardrail`
  - runtime: `active | blocked`

### Problem 2: Hidden effective behavior

Forms show raw values but not operational behavior.

Resolution:

- Add "Effective Behavior Summary" at top-level Overview:
  - who can message bot
  - allowed tools
  - denied high-risk actions
  - sandbox mode/scope
  - model + auth posture

### Problem 3: Late error detection

Invalid config can be applied and only discovered in logs.

Resolution:

- Add preflight validation gate before apply/publish:
  - schema checks
  - semantic checks (allowlist requires allowFrom, enum constraints, etc.)
- Block apply if invalid.

### Problem 4: Poor explainability

No direct way to explain "why action X is denied."

Resolution:

- Add "Explain My Bot" panel:
  - natural language summary of active capabilities/restrictions
  - reason chain for key decisions

## Information Architecture (Proposed)

```text
Overview
Policy & Profile
Capabilities (Tools)
Channels & Access
Session & Memory
Safety Guards
Runtime Validation
Change History
```

## Wireframe (Textual)

```text
[Header]
Bot | Environment | Config Health | Last Reload | Effective Hash | Explain My Bot

[Overview]
- Effective Behavior Summary cards
- Conflicts & Overrides table
- Pending Changes vs Applied
- Validate + Publish actions

[Capabilities]
- Tool matrix grouped by category
- Per-tool chips: State / Source / Runtime
- Usage signal (last 24h)
- Risk tier badges

[Runtime Validation]
- Preflight validator result
- Gateway acceptance timeline
- Reload status stream
- Invalid config blocker details
```

## Feature Proposals

### 1) Effective Config View

Collapsible panel showing resolved final config (post precedence), with source annotations.

### 2) Explain My Bot

Human-readable operational summary and decision traces:

- "Tool `exec` denied by manual override"
- "Discord DM allowed via profile baseline"

### 3) Runtime Simulation

Input scenario (`actor`, `channel`, `requested capability`) and receive expected decision + rationale.

### 4) Decision Logs (Productized)

Curated UI log stream focused on policy/reload decisions, not raw technical noise.

### 5) Override Review Queue

For high-risk overrides, require explicit reason + optional second approver.

## Delivery Plan (Phased)

### Phase 1: Quick Wins (Low Risk, Immediate Clarity)

- Add precedence banner (`Profile` vs `Tools`).
- Add effective summary cards in Overview.
- Add preflight validation before apply.
- Add schema guardrails for known brittle fields:
  - `logging.redactSensitive`
  - `session.reset.mode`
  - `session.dmScope`
  - `channels.* allowlist/allowFrom`
  - `tools.elevated.*` shape constraints

Acceptance:

- No invalid config apply through UI for guarded fields.
- Admin can identify active tool policy source in <= 10 seconds.

### Phase 2: Policy-First Core Redesign

- Restructure nav and page hierarchy to proposed architecture.
- Build effective config resolver view.
- Add per-field source/override indicators.
- Refactor tools section into state/source/runtime matrix.

Acceptance:

- Admin can answer "what can bot do now?" without reading raw JSON.
- Profile/tool conflicts are explicit and deterministic.

### Phase 3: Explainability + Simulation

- Implement Explain My Bot.
- Add runtime simulation panel.
- Add decision log stream and change history UX.

Acceptance:

- Admin can explain denial/allow reasons from UI alone.
- Pre-deploy simulation catches risky policy mistakes.

## Risks and Mitigations

- Risk: Increased UI complexity from richer state.
  - Mitigation: progressive disclosure + collapsed advanced panels.
- Risk: Drift between UI resolver and gateway runtime truth.
  - Mitigation: continuous gateway log validation and effective-hash checks.
- Risk: Migration confusion for existing users.
  - Mitigation: onboarding callouts and side-by-side legacy mapping.

## Success Metrics

- Reduction in invalid reload incidents from config UI.
- Time-to-validate configuration before publish.
- Reduction in support/debug cycles caused by precedence confusion.
- Higher admin confidence score in qualitative feedback.

## Validation Strategy

Use the existing validation skill workflow:

- `openclaw-validate-config-reload`
- `openclaw-full-project-validation`

Must pass before marking each phase done.

## Open Questions

1. Should high-risk overrides be hard-blocked or just approval-gated?
2. Should runtime simulation operate purely from effective config or include live gateway probes?
3. What minimum audit trail is required for team compliance?

