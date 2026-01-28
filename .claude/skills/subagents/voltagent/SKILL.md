---
name: voltagent
description: Collection of 126+ specialized Claude Code subagents
version: 1.0.0
author: voltagent
source: https://github.com/VoltAgent/awesome-claude-code-subagents
user-invocable: false
---

# VoltAgent - Claude Code Subagents Collection

This skill provides reference documentation for 126+ specialized Claude Code subagents organized into 10 categories. These subagents extend Claude Code's capabilities with domain-specific expertise.

## Overview

Subagents are specialized AI assistants that operate with:
- **Isolated context windows** - Task details don't clutter main conversations
- **Domain-specific intelligence** - Specialized prompts for each domain
- **Granular tool permissions** - Configured per-agent tool access
- **Memory efficiency** - Focused context for better accuracy

## Categories

| Category | Count | Description |
|----------|-------|-------------|
| [Core Development](./agents/core-development.md) | 11 | Backend, frontend, fullstack, mobile |
| [Language Specialists](./agents/language-specialists.md) | 26 | TypeScript, Python, Go, Rust, etc. |
| [Infrastructure](./agents/infrastructure.md) | 14 | DevOps, cloud, Kubernetes |
| [Quality & Security](./agents/quality-security.md) | 14 | Testing, code review, security |
| [Data & AI](./agents/data-ai.md) | 12 | ML, data science, databases |
| [Developer Experience](./agents/developer-experience.md) | 13 | Build systems, docs, CLI tools |
| [Specialized Domains](./agents/specialized-domains.md) | 12 | Blockchain, fintech, IoT, gaming |
| [Business & Product](./agents/business-product.md) | 10 | PM, strategy, technical writing |
| [Meta & Orchestration](./agents/meta-orchestration.md) | 11 | Multi-agent coordination |
| [Research & Analysis](./agents/research-analysis.md) | 6 | Market research, competitive analysis |

## Installation

### Via Claude Code Plugin

```bash
# Install specific category
claude plugin install voltagent-lang    # Language specialists
claude plugin install voltagent-infra   # Infrastructure & DevOps
claude plugin install voltagent-qa      # Quality & Security
```

### Manual Installation

Copy agent files to:
- **Project-level**: `.claude/agents/` (takes precedence)
- **Global**: `~/.claude/agents/`

### Using the Agent Installer

From Claude Code, use the `/agents` command to:
1. Browse available subagents
2. Preview agent configurations
3. Install to project or global scope

## Subagent Architecture

Each subagent includes:

```yaml
name: backend-architect
description: API design and backend architecture specialist
tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
system_prompt: |
  You are an expert backend architect specializing in:
  - RESTful and GraphQL API design
  - Database schema optimization
  - Microservices architecture
  - Performance and scalability patterns

  When designing systems:
  1. Start with requirements analysis
  2. Propose architecture options with trade-offs
  3. Detail implementation approach
  4. Consider security implications
```

## Creating Custom Subagents

Use the `/agents` command in Claude Code:

1. **Draft with AI**: Describe your agent's purpose
2. **Configure tools**: Select required tool permissions
3. **Set scope**: Project-level or global
4. **Customize prompt**: Refine the system instructions

### Example Custom Agent

```yaml
name: earnings-analyst
description: SEC filing analysis specialist for EarningsNerd
tools:
  - Read
  - WebFetch
  - Grep
  - Glob
system_prompt: |
  You are an expert financial analyst specializing in SEC filings.

  Capabilities:
  - Parse 10-K and 10-Q filings
  - Extract key financial metrics
  - Identify risk factors and management commentary
  - Compare filings across periods

  Always cite specific sections when referencing filing content.
```

## Best Practices

### When to Use Subagents

- **Complex domain tasks** - Use specialists for their expertise
- **Parallel workflows** - Run multiple agents on different aspects
- **Isolated analysis** - Keep specific investigations separate
- **Consistent patterns** - Reuse agent configurations across projects

### Agent Selection

| Task | Recommended Agent |
|------|-------------------|
| API design | backend-architect |
| React optimization | frontend-specialist |
| CI/CD setup | devops-engineer |
| Security audit | penetration-tester |
| Code review | code-reviewer |
| Database design | database-architect |

## Tool Permissions

Common tool configurations:

| Agent Type | Typical Tools |
|-----------|---------------|
| Read-only analysis | Read, Grep, Glob |
| Code modification | Read, Write, Edit, Grep, Glob |
| Full development | All tools including Bash |
| Research | Read, WebFetch, WebSearch |

## See Also

- [Core Development Agents](./agents/core-development.md)
- [Language Specialists](./agents/language-specialists.md)
- [Infrastructure Agents](./agents/infrastructure.md)
- [Quality & Security Agents](./agents/quality-security.md)
- [Data & AI Agents](./agents/data-ai.md)
