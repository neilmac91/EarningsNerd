# EarningsNerd Agentic Workforce

Welcome to the EarningsNerd AI Agent Framework. This directory contains detailed instruction files for each specialized AI agent that powers our development, product, marketing, design, project management, operations, and testing workflows.

## Overview

Each agent definition file serves as a "System Prompt" and "Operating Manual" that defines:
- **Identity & Persona** - The agent's role, voice, and worldview
- **Core Responsibilities** - Primary, secondary, and quality control functions
- **Knowledge Base** - Domain expertise and key files to monitor
- **Operational Workflow** - How the agent processes tasks
- **Interaction Guidelines** - Handoffs and communication patterns

## Agent Directory

### Engineering (7 Agents)
| Agent | File | Primary Focus |
|-------|------|---------------|
| Frontend Developer | [`engineering/frontend-developer.md`](engineering/frontend-developer.md) | React/TypeScript UI development |
| Backend Developer | [`engineering/backend-developer.md`](engineering/backend-developer.md) | FastAPI/Python services |
| AI Engineer | [`engineering/ai-engineer.md`](engineering/ai-engineer.md) | OpenAI integration, prompt engineering |
| DevOps Automator | [`engineering/devops-automator.md`](engineering/devops-automator.md) | CI/CD, deployment automation |
| Infrastructure Maintainer | [`engineering/infrastructure-maintainer.md`](engineering/infrastructure-maintainer.md) | Database, cloud infrastructure |
| API Architect | [`engineering/api-architect.md`](engineering/api-architect.md) | API design and standards |
| Database Specialist | [`engineering/database-specialist.md`](engineering/database-specialist.md) | PostgreSQL optimization |

### Product (5 Agents)
| Agent | File | Primary Focus |
|-------|------|---------------|
| Trend Researcher | [`product/trend-researcher.md`](product/trend-researcher.md) | Market and user trend analysis |
| Feedback Synthesizer | [`product/feedback-synthesizer.md`](product/feedback-synthesizer.md) | User feedback aggregation |
| Feature Prioritizer | [`product/feature-prioritizer.md`](product/feature-prioritizer.md) | Roadmap prioritization (RICE) |
| Competitive Analyst | [`product/competitive-analyst.md`](product/competitive-analyst.md) | Competitive intelligence |
| User Story Writer | [`product/user-story-writer.md`](product/user-story-writer.md) | Requirements translation |

### Marketing (6 Agents)
| Agent | File | Primary Focus |
|-------|------|---------------|
| TikTok Creator | [`marketing/tiktok-creator.md`](marketing/tiktok-creator.md) | Short-form video content |
| Twitter Strategist | [`marketing/twitter-strategist.md`](marketing/twitter-strategist.md) | FinTwit community building |
| Growth Hacker | [`marketing/growth-hacker.md`](marketing/growth-hacker.md) | Viral loops, user acquisition |
| Content Writer | [`marketing/content-writer.md`](marketing/content-writer.md) | Blog, email, landing pages |
| SEO Optimizer | [`marketing/seo-optimizer.md`](marketing/seo-optimizer.md) | Organic search visibility |
| Email Marketer | [`marketing/email-marketer.md`](marketing/email-marketer.md) | Email campaigns and automation |

### Design (5 Agents)
| Agent | File | Primary Focus |
|-------|------|---------------|
| UI Designer | [`design/ui-designer.md`](design/ui-designer.md) | Visual interface design |
| UX Researcher | [`design/ux-researcher.md`](design/ux-researcher.md) | User research and testing |
| Whimsy Injector | [`design/whimsy-injector.md`](design/whimsy-injector.md) | Delight and micro-interactions |
| Brand Guardian | [`design/brand-guardian.md`](design/brand-guardian.md) | Brand consistency |
| Accessibility Champion | [`design/accessibility-champion.md`](design/accessibility-champion.md) | WCAG compliance |

### Project Management (3 Agents)
| Agent | File | Primary Focus |
|-------|------|---------------|
| Sprint Coordinator | [`project-management/sprint-coordinator.md`](project-management/sprint-coordinator.md) | Agile ceremonies and execution |
| Task Tracker | [`project-management/task-tracker.md`](project-management/task-tracker.md) | Work item management |
| Dependency Mapper | [`project-management/dependency-mapper.md`](project-management/dependency-mapper.md) | Internal/external dependencies |

### Studio Operations (3 Agents)
| Agent | File | Primary Focus |
|-------|------|---------------|
| Resource Allocator | [`studio-operations/resource-allocator.md`](studio-operations/resource-allocator.md) | Capacity planning |
| Knowledge Curator | [`studio-operations/knowledge-curator.md`](studio-operations/knowledge-curator.md) | Documentation management |
| Process Optimizer | [`studio-operations/process-optimizer.md`](studio-operations/process-optimizer.md) | Workflow improvement |

### Testing (4 Agents)
| Agent | File | Primary Focus |
|-------|------|---------------|
| QA Engineer | [`testing/qa-engineer.md`](testing/qa-engineer.md) | Test strategy and execution |
| Security Auditor | [`testing/security-auditor.md`](testing/security-auditor.md) | Application security |
| Performance Tester | [`testing/performance-tester.md`](testing/performance-tester.md) | Load testing and optimization |
| Integration Tester | [`testing/integration-tester.md`](testing/integration-tester.md) | System integration validation |

## Total: 33 Specialized Agents

## Agent Interaction Model

```
                                    ┌─────────────────┐
                                    │ Sprint          │
                                    │ Coordinator     │
                                    └────────┬────────┘
                                             │
          ┌──────────────────────────────────┼──────────────────────────────────┐
          │                                  │                                  │
          ▼                                  ▼                                  ▼
┌─────────────────┐               ┌─────────────────┐               ┌─────────────────┐
│   ENGINEERING   │               │     PRODUCT     │               │    MARKETING    │
│                 │               │                 │               │                 │
│ Frontend Dev    │◄────────────► │ Feature         │◄────────────► │ Growth Hacker   │
│ Backend Dev     │               │ Prioritizer     │               │ Content Writer  │
│ AI Engineer     │               │ User Story      │               │ SEO Optimizer   │
│ DevOps          │               │ Writer          │               │ TikTok Creator  │
│ Infrastructure  │               │                 │               │ Twitter         │
│ API Architect   │               │                 │               │ Email Marketer  │
│ Database        │               │                 │               │                 │
└────────┬────────┘               └────────┬────────┘               └─────────────────┘
         │                                 │
         │    ┌────────────────────────────┤
         │    │                            │
         ▼    ▼                            ▼
┌─────────────────┐               ┌─────────────────┐
│     DESIGN      │               │     TESTING     │
│                 │               │                 │
│ UI Designer     │               │ QA Engineer     │
│ UX Researcher   │               │ Security        │
│ Whimsy Injector │               │ Performance     │
│ Brand Guardian  │               │ Integration     │
│ Accessibility   │               │                 │
└─────────────────┘               └─────────────────┘
         │                                 │
         └────────────────┬────────────────┘
                          ▼
               ┌─────────────────┐
               │ STUDIO          │
               │ OPERATIONS      │
               │                 │
               │ Resource        │
               │ Knowledge       │
               │ Process         │
               └─────────────────┘
```

## How to Use These Agents

### 1. Direct Invocation
Reference an agent's instruction file when starting a task:

```
"Acting as the Frontend Developer agent, implement the earnings comparison component..."
```

### 2. Handoff Protocol
When one agent completes work, they hand off to the next:

```
Frontend Developer → UI Designer (for visual review)
Backend Developer → QA Engineer (for testing)
Content Writer → SEO Optimizer (for optimization)
```

### 3. Collaborative Tasks
Multiple agents can work together on complex features:

```
New Feature Launch:
1. User Story Writer → defines requirements
2. UI Designer → creates designs
3. Frontend Developer → implements UI
4. Backend Developer → implements API
5. QA Engineer → tests functionality
6. Security Auditor → reviews security
7. DevOps Automator → deploys
8. Content Writer → writes announcements
9. Twitter Strategist → promotes
```

## Key Principles

1. **Specialization** - Each agent has deep expertise in their domain
2. **Collaboration** - Agents hand off work following defined protocols
3. **Consistency** - All agents follow the same communication format
4. **Quality Gates** - Every agent has self-correction checklists
5. **Accountability** - Clear ownership and deliverables
6. **Documentation** - All work is documented and traceable

## EarningsNerd-Specific Context

All agents are calibrated for EarningsNerd's domain:
- **SEC Filing Analysis** - 10-K, 10-Q, 8-K filings
- **AI Summarization** - OpenAI-powered summaries
- **Financial Data** - Earnings, metrics, comparisons
- **Subscription Model** - Free and premium tiers
- **Tech Stack** - React/Vite, FastAPI, PostgreSQL, Render/Vercel

## Maintaining This Framework

- Review agent definitions quarterly
- Update when tools or processes change
- Add new agents as needs emerge
- Retire agents when roles consolidate
- Keep EarningsNerd-specific patterns current

---

*This agentic workforce framework powers EarningsNerd's AI-assisted development.*
