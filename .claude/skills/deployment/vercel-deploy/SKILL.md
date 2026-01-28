---
name: vercel-deploy
description: Deploy applications and websites to Vercel
version: 1.0.0
author: vercel
source: https://github.com/vercel-labs/agent-skills/tree/main/skills/claude.ai/vercel-deploy-claimable
disable-model-invocation: true
allowed-tools:
  - Bash
---

# Vercel Deploy

This skill packages projects into compressed archives, detects frameworks automatically, and uploads them for deployment to Vercel. It produces a live preview URL and a claimable link for transferring deployments to personal Vercel accounts.

## Usage

Deploy projects using the included script:

```bash
bash .claude/skills/deployment/vercel-deploy/scripts/deploy.sh [path]
```

### Input Options

| Input | Description |
|-------|-------------|
| (none) | Deploy current working directory |
| `./path/to/project` | Deploy specific directory |
| `./project.tgz` | Deploy pre-packaged tarball |

## Output

The deployment returns structured JSON:

```json
{
  "previewUrl": "https://project-abc123.vercel.app",
  "claimUrl": "https://vercel.com/claim/...",
  "deploymentId": "dpl_...",
  "projectId": "prj_..."
}
```

| Field | Description |
|-------|-------------|
| `previewUrl` | Live deployment URL |
| `claimUrl` | Link to transfer ownership to your Vercel account |
| `deploymentId` | Unique deployment identifier |
| `projectId` | Project identifier |

## Framework Detection

The script automatically detects 50+ frameworks by inspecting `package.json`:

**Frontend Frameworks**
- Next.js, React, Vue, Angular, Svelte, SvelteKit
- Nuxt, Remix, Gatsby, Astro, Solid

**Backend Frameworks**
- Express, Fastify, NestJS, Hono
- Flask, Django, FastAPI (Python)

**Static Sites**
- HTML files (no package.json required)
- Single HTML files renamed to `index.html`

## Static Site Support

For projects without `package.json`:
1. Script checks for HTML files
2. Single HTML files are renamed to `index.html`
3. Framework is set to `null` for static deployment

## Network Requirements

If deployment fails due to network restrictions:
1. Check your network/firewall settings
2. Authorize `*.vercel.com` domains
3. Ensure outbound HTTPS (port 443) is allowed

## Example Workflows

### Deploy Current Project

```bash
# From project root
bash .claude/skills/deployment/vercel-deploy/scripts/deploy.sh
```

### Deploy Specific Directory

```bash
# Deploy a subdirectory
bash .claude/skills/deployment/vercel-deploy/scripts/deploy.sh ./frontend
```

### Deploy with Framework Override

```bash
# Pre-package with specific settings
tar -czf project.tgz --exclude=node_modules --exclude=.git .
bash .claude/skills/deployment/vercel-deploy/scripts/deploy.sh ./project.tgz
```

## Claiming Deployments

After deployment, use the `claimUrl` to:
1. Transfer the deployment to your Vercel account
2. Configure custom domains
3. Set up environment variables
4. Enable analytics and monitoring

The claimable link expires after 7 days.

## Troubleshooting

### Deployment Fails

1. **Missing dependencies**: Run `npm install` first
2. **Build errors**: Check `package.json` scripts
3. **Large files**: Ensure `node_modules` and `.git` are excluded

### Wrong Framework Detected

The script checks `package.json` dependencies in order of specificity. If detection is wrong:
1. Check your `package.json` dependencies
2. Use a pre-packaged tarball with correct structure

### Network Errors

```
Error: ECONNREFUSED
```

1. Check internet connectivity
2. Verify `*.vercel.com` is not blocked
3. Try again (transient failures)
