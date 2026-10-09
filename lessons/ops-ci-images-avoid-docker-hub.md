# Pull CI and deploy images through a mirror, never anonymously from Docker Hub

Date: 2026-10-09   Area: ops / CI

**Context**: From about 20:52Z on 2026-10-09, every `migrations-postgres` run failed at "Initialize
containers": `docker pull postgres:15` returned `toomanyrequests: You have reached your
unauthenticated pull rate limit`. The job is required, so every PR went red for a reason no PR
controlled, and `deploy-backend` (which needs it) was skipped on main. #1144 and #1152 merged but did
not deploy. GitHub-hosted runners share IP addresses, so an anonymous Docker Hub pull can hit the
limit whatever this repository does. The deploy build's `FROM python:3.11-slim` was exposed the same way.

**Rule**: Every workflow service or job container, and every backend Dockerfile `FROM`, names a
registry host. Official images come through `mirror.gcr.io/library/<name>:<tag>`, Google's mirror of
Docker Hub, which serves the same digests. Never use a bare official name (`postgres:15`), a Docker
Hub namespace (`user/image`) or `docker.io` in CI or the deploy image. `docker-compose.yml` is local
development only and is out of scope.

**Evidence**: main run 37992221738 (job 114029055368: three pull attempts, then "Docker pull failed
with exit code 1"); the gate `backend/tests/unit/test_ci_images_avoid_docker_hub.py`;
`.github/workflows/ci.yml` (`migrations-postgres` service) and `backend/Dockerfile`.
