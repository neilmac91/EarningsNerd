# Claude Skills Directory

This directory contains Claude Code skills that provide specialized knowledge and capabilities for development tasks. Skills follow the [Agent Skills open standard](https://github.com/anthropics/agent-skills).

## Available Skills

| Category | Skill | Description |
|----------|-------|-------------|
| **Meta** | [llm-council](./meta/llm-council/) | Run a decision through 5 AI advisors who peer-review each other, then a chairman synthesizes a verdict |
| **Payments** | [stripe-best-practices](./payments/stripe-best-practices/) | Stripe API integration patterns and best practices |
| **Infrastructure** | [cloudflare-agents-sdk](./infrastructure/cloudflare-agents-sdk/) | Building AI agents on Cloudflare Workers |
| **Frontend** | [react-best-practices](./frontend/react-best-practices/) | React/Next.js performance optimization (57 rules) |
| **Frontend** | [web-design-guidelines](./frontend/web-design-guidelines/) | UI code review against design standards |
| **Deployment** | [vercel-deploy](./deployment/vercel-deploy/) | Deploy applications to Vercel |
| **Subagents** | [voltagent](./subagents/voltagent/) | 126+ specialized Claude Code subagents |

## Skill Categories

### Meta (`/meta`)
Skills for reasoning and decision-making workflows:
- **llm-council** - Pressure-test a high-stakes decision through 5 independent advisors (Contrarian, First Principles, Expansionist, Outsider, Executor), anonymous peer review, and a chairman synthesis. Triggers: "council this", "pressure-test this", "war room this".

### Payments (`/payments`)
Skills for payment processing integrations:
- **stripe-best-practices** - Modern Stripe API patterns, avoiding deprecated APIs

### Infrastructure (`/infrastructure`)
Skills for cloud platforms and infrastructure:
- **cloudflare-agents-sdk** - Build stateful AI agents on Cloudflare Workers

### Frontend (`/frontend`)
Skills for frontend development:
- **react-best-practices** - Performance optimization rules ranked by impact
- **web-design-guidelines** - Audit UI against Vercel's design standards

### Deployment (`/deployment`)
Skills for CI/CD and deployment:
- **vercel-deploy** - Package and deploy projects to Vercel with claimable URLs

### Subagents (`/subagents`)
Collections of specialized Claude Code subagents:
- **voltagent** - 126+ subagents across 10 categories

## Using Skills

### Automatic Invocation
Claude can automatically load relevant skills based on context. For example, when discussing Stripe integration, the `stripe-best-practices` skill may be loaded.

### Manual Invocation
Use the skill name as a slash command:
```
/stripe-best-practices
/react-best-practices
/vercel-deploy
```

### Skill with Side Effects
Some skills (like `vercel-deploy`) have side effects and require manual invocation. These are marked with `disable-model-invocation: true` in their frontmatter.

## Adding New Skills

1. Create a new directory under the appropriate category
2. Add a `SKILL.md` file with frontmatter:
   ```yaml
   ---
   name: my-skill
   description: Brief description of the skill
   version: 1.0.0
   author: your-name
   ---
   ```
### Authoring recommendations

These are contextual design recommendations, not new machine-enforced repository invariants.
Apply judgment to the workflow and its risks:

- Prefer a short description that identifies the actual workflow. Broad triggers can pull a
  skill into unrelated tasks; explicit requirements remain useful for fragile operations.
- For substantial conditional detail, consider linked references with guidance on when to read
  each. A short, cohesive skill can remain self-contained; load shared context when it is needed.
- Favor guidance that changes decisions and leaves routine choices to the agent. Preserve
  existing operational invariants and approval boundaries, and consider contributors' models.
- Consider deterministic scripts for reusable operations where they improve reliability;
  validate changed scripts and reference links. Extra routers or directories are optional.

Review scope and relevance with realistic requests. A keyword or length check cannot establish
those qualities. If a future change introduces a concrete enforceable invariant, the existing
`CLAUDE.md` rule 12 still requires its machine gate; these recommendations do not relax that rule.

## Skill Frontmatter Reference

| Field | Description |
|-------|-------------|
| `name` | Skill identifier (used for invocation) |
| `description` | Brief description shown in skill listings |
| `version` | Semantic version |
| `author` | Skill author or organization |
| `allowed-tools` | Tools the skill can use (e.g., `Bash`, `WebFetch`) |
| `disable-model-invocation` | If `true`, requires manual invocation |
| `user-invocable` | If `false`, skill is background knowledge only |

## Sources

- [Stripe AI Skills](https://github.com/stripe/ai/tree/main/skills)
- [Cloudflare Skills](https://github.com/cloudflare/skills)
- [Vercel Agent Skills](https://github.com/vercel-labs/agent-skills)
- [VoltAgent Awesome Claude Code Subagents](https://github.com/VoltAgent/awesome-claude-code-subagents)
- [Claude Code Skills Documentation](https://code.claude.com/docs/en/skills)
