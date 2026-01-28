# Claude Skills Directory

This directory contains Claude Code skills that provide specialized knowledge and capabilities for development tasks. Skills follow the [Agent Skills open standard](https://github.com/anthropics/agent-skills).

## Available Skills

| Category | Skill | Description |
|----------|-------|-------------|
| **Payments** | [stripe-best-practices](./payments/stripe-best-practices/) | Stripe API integration patterns and best practices |
| **Infrastructure** | [cloudflare-agents-sdk](./infrastructure/cloudflare-agents-sdk/) | Building AI agents on Cloudflare Workers |
| **Frontend** | [react-best-practices](./frontend/react-best-practices/) | React/Next.js performance optimization (57 rules) |
| **Frontend** | [web-design-guidelines](./frontend/web-design-guidelines/) | UI code review against design standards |
| **Deployment** | [vercel-deploy](./deployment/vercel-deploy/) | Deploy applications to Vercel |
| **Subagents** | [voltagent](./subagents/voltagent/) | 126+ specialized Claude Code subagents |

## Skill Categories

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
3. Include instructions and reference content
4. Optionally add supporting files in subdirectories

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
