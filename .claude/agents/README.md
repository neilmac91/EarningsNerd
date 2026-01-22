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

| Agent                     | File                                            | Primary Focus                          |
| ------------------------- | ----------------------------------------------- | -------------------------------------- |
| Frontend Developer        | [`engineering/frontend-developer.md`][1]        | React/TypeScript UI development        |
| Backend Developer         | [`engineering/backend-developer.md`][2]         | FastAPI/Python services                |
| AI Engineer               | [`engineering/ai-engineer.md`][3]               | OpenAI integration, prompt engineering |
| DevOps Automator          | [`engineering/devops-automator.md`][4]          | CI/CD, deployment automation           |
| Infrastructure Maintainer | [`engineering/infrastructure-maintainer.md`][5] | Database, cloud infrastructure         |
| API Architect             | [`engineering/api-architect.md`][6]             | API design and standards               |
| Database Specialist       | [`engineering/database-specialist.md`][7]       | PostgreSQL optimization                |

### Product (5 Agents)

| Agent                | File                                   | Primary Focus                  |
| -------------------- | -------------------------------------- | ------------------------------ |
| Trend Researcher     | [`product/trend-researcher.md`][8]     | Market and user trend analysis |
| Feedback Synthesizer | [`product/feedback-synthesizer.md`][9] | User feedback aggregation      |
| Feature Prioritizer  | [`product/feature-prioritizer.md`][10] | Roadmap prioritization (RICE)  |
| Competitive Analyst  | [`product/competitive-analyst.md`][11] | Competitive intelligence       |
| User Story Writer    | [`product/user-story-writer.md`][12]   | Requirements translation       |

### Marketing (6 Agents)

| Agent              | File                                    | Primary Focus                  |
| ------------------ | --------------------------------------- | ------------------------------ |
| TikTok Creator     | [`marketing/tiktok-creator.md`][13]     | Short-form video content       |
| Twitter Strategist | [`marketing/twitter-strategist.md`][14] | FinTwit community building     |
| Growth Hacker      | [`marketing/growth-hacker.md`][15]      | Viral loops, user acquisition  |
| Content Writer     | [`marketing/content-writer.md`][16]     | Blog, email, landing pages     |
| SEO Optimizer      | [`marketing/seo-optimizer.md`][17]      | Organic search visibility      |
| Email Marketer     | [`marketing/email-marketer.md`][18]     | Email campaigns and automation |

### Design (5 Agents)

| Agent                  | File                                     | Primary Focus                  |
| ---------------------- | ---------------------------------------- | ------------------------------ |
| UI Designer            | [`design/ui-designer.md`][19]            | Visual interface design        |
| UX Researcher          | [`design/ux-researcher.md`][20]          | User research and testing      |
| Whimsy Injector        | [`design/whimsy-injector.md`][21]        | Delight and micro-interactions |
| Brand Guardian         | [`design/brand-guardian.md`][22]         | Brand consistency              |
| Accessibility Champion | [`design/accessibility-champion.md`][23] | WCAG compliance                |

### Project Management (3 Agents)

| Agent              | File                                             | Primary Focus                  |
| ------------------ | ------------------------------------------------ | ------------------------------ |
| Sprint Coordinator | [`project-management/sprint-coordinator.md`][24] | Agile ceremonies and execution |
| Task Tracker       | [`project-management/task-tracker.md`][25]       | Work item management           |
| Dependency Mapper  | [`project-management/dependency-mapper.md`][26]  | Internal/external dependencies |

### Studio Operations (3 Agents)

| Agent              | File                                            | Primary Focus            |
| ------------------ | ----------------------------------------------- | ------------------------ |
| Resource Allocator | [`studio-operations/resource-allocator.md`][27] | Capacity planning        |
| Knowledge Curator  | [`studio-operations/knowledge-curator.md`][28]  | Documentation management |
| Process Optimizer  | [`studio-operations/process-optimizer.md`][29]  | Workflow improvement     |

### Testing (4 Agents)

| Agent              | File                                  | Primary Focus                 |
| ------------------ | ------------------------------------- | ----------------------------- |
| QA Engineer        | [`testing/qa-engineer.md`][30]        | Test strategy and execution   |
| Security Auditor   | [`testing/security-auditor.md`][31]   | Application security          |
| Performance Tester | [`testing/performance-tester.md`][32] | Load testing and optimization |
| Integration Tester | [`testing/integration-tester.md`][33] | System integration validation |

## Total: 33 Specialized Agents

## Agent Interaction Model

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

## How to Use These Agents

### 1. Direct Invocation
Reference an agent's instruction file when starting a task:

	"Acting as the Frontend Developer agent, implement the earnings comparison component..."

### 2. Handoff Protocol
When one agent completes work, they hand off to the next:

	Frontend Developer → UI Designer (for visual review)
	Backend Developer → QA Engineer (for testing)
	Content Writer → SEO Optimizer (for optimization)

### 3. Collaborative Tasks
Multiple agents can work together on complex features:

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

## Key Principles

1. **Specialization** - Each agent has deep expertise in their domain
2. **Collaboration** - Agents hand off work following defined protocols
3. **Consistency** - All agents follow the same communication format
4. **Quality Gates** - Every agent has self-correction checklists
5. **Accountability** - Clear ownership and deliverables
6. **Documentation** - All work is documented and traceable

## EarningsNerd-Specific Context

All agents are calibrated for EarningsNerd's domain:
- **SEC Filing Analysis** - 10-K, 10-Q filings
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

[1]:	engineering/frontend-developer.md
[2]:	engineering/backend-developer.md
[3]:	engineering/ai-engineer.md
[4]:	engineering/devops-automator.md
[5]:	engineering/infrastructure-maintainer.md
[6]:	engineering/api-architect.md
[7]:	engineering/database-specialist.md
[8]:	product/trend-researcher.md
[9]:	product/feedback-synthesizer.md
[10]:	product/feature-prioritizer.md
[11]:	product/competitive-analyst.md
[12]:	product/user-story-writer.md
[13]:	marketing/tiktok-creator.md
[14]:	marketing/twitter-strategist.md
[15]:	marketing/growth-hacker.md
[16]:	marketing/content-writer.md
[17]:	marketing/seo-optimizer.md
[18]:	marketing/email-marketer.md
[19]:	design/ui-designer.md
[20]:	design/ux-researcher.md
[21]:	design/whimsy-injector.md
[22]:	design/brand-guardian.md
[23]:	design/accessibility-champion.md
[24]:	project-management/sprint-coordinator.md
[25]:	project-management/task-tracker.md
[26]:	project-management/dependency-mapper.md
[27]:	studio-operations/resource-allocator.md
[28]:	studio-operations/knowledge-curator.md
[29]:	studio-operations/process-optimizer.md
[30]:	testing/qa-engineer.md
[31]:	testing/security-auditor.md
[32]:	testing/performance-tester.md
[33]:	testing/integration-tester.md