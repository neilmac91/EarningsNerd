"""CI and the deploy build pull no image anonymously from Docker Hub (rule 12).

On 2026-10-09 Docker Hub's unauthenticated pull limit ("toomanyrequests") failed the required
``migrations-postgres`` job on every PR and on main, and so skipped ``deploy-backend``: GitHub-hosted
runners share IPs, so an anonymous Docker Hub pull can fail for reasons no PR controls. Every
workflow service or job container and every backend Dockerfile ``FROM`` therefore names a registry
host explicitly, and Docker Hub (a bare official name, a ``user/image`` namespace, ``docker.io``,
``index.docker.io``, ``registry-1.docker.io``) is not one of them. ``mirror.gcr.io`` serves Docker
Hub's official images with the same digests. See ``lessons/ops-ci-images-avoid-docker-hub.md``.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
DOCKER_HUB_HOSTS = {"docker.io", "index.docker.io", "registry-1.docker.io"}
_FROM = re.compile(r"^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", re.IGNORECASE)


def registry_host(image: str) -> str | None:
    """The registry an image reference pulls from, or None when it resolves to Docker Hub."""
    first, _, rest = image.partition("/")
    if rest and ("." in first or ":" in first or first == "localhost"):
        return None if first.lower() in DOCKER_HUB_HOSTS else first
    return None  # "postgres:15" (official image) or "user/image" (a Docker Hub namespace)


def workflow_images() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in sorted((REPO / ".github" / "workflows").glob("*.y*ml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for job_name, job in (doc.get("jobs") or {}).items():
            container = job.get("container")
            if container:
                found.append((f"{path.name} {job_name} container",
                              str(container if isinstance(container, str) else container.get("image"))))
            for service_name, service in (job.get("services") or {}).items():
                found.append((f"{path.name} {job_name} services.{service_name}", str(service.get("image"))))
            for step in job.get("steps") or []:
                uses = str(step.get("uses") or "")
                if uses.startswith("docker://"):
                    found.append((f"{path.name} {job_name} step {step.get('name') or uses}", uses[len("docker://"):]))
    return found


def dockerfile_bases() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in sorted((REPO / "backend").rglob("Dockerfile*")):
        stages: set[str] = set()
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = _FROM.match(line)
            if not match:
                continue
            image, alias = match.group(1), match.group(2)
            if image.lower() not in stages and image.lower() != "scratch":
                found.append((f"{path.relative_to(REPO)}:{lineno}", image))
            if alias:
                stages.add(alias.lower())
    return found


def test_the_scan_sees_the_known_pulls():
    workflows = dict(workflow_images())
    assert "ci.yml migrations-postgres services.postgres" in workflows, workflows
    assert any(where.startswith("backend/Dockerfile:") for where, _ in dockerfile_bases())


def test_registry_host_reads_docker_hub_references_as_docker_hub():
    assert registry_host("postgres:15") is None
    assert registry_host("library/postgres:15") is None
    assert registry_host("docker.io/library/postgres:15") is None
    assert registry_host("registry-1.docker.io/library/python:3.11-slim") is None
    assert registry_host("mirror.gcr.io/library/postgres:15") == "mirror.gcr.io"
    assert registry_host("us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend") == "us-west1-docker.pkg.dev"


def test_no_ci_or_deploy_image_is_pulled_from_docker_hub():
    offenders = [f"{where}: {image}" for where, image in workflow_images() + dockerfile_bases()
                 if registry_host(image) is None]
    assert not offenders, (
        "pull these through a registry host (mirror.gcr.io/library/<name>:<tag> for official images), "
        "never anonymous Docker Hub:\n  " + "\n  ".join(offenders)
    )
