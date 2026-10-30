"""Ordinary CI deployments preserve the held summary/SEC controls on every reader.

The five current image-update commands omit these keys and use additive env/secret
updates. Adding even a false/zero pin resets a live value; replacement/removal can
erase one. A coordinated, approved activation must revise this guard with its
complete producer matrix, not sneak a value into an ordinary release.

This reads direct gcloud commands in ci.yml and literal key mentions in workflow
source. It is not a shell interpreter or a check of console settings, image ENV,
external scripts, dynamically constructed command/key names, or old executions.
The operational inventory and live readbacks remain necessary.
"""
from __future__ import annotations

import copy
from pathlib import Path
import re
import shlex

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / ".github/workflows"
HELD_CONTROLS = frozenset({
    "SUMMARY_DURABLE_GENERATION_ENABLED", "SUMMARY_NEW_JOBS_PAUSED",
    "SUMMARY_PREWARM_MAX_PER_DAY", "SUMMARY_PREWARM_MAX_PER_SCAN",
    "SUMMARY_JOB_FAILED_RETRY_SECONDS", "SUMMARY_JOB_MAX_PENDING_PER_ACCOUNT",
    "SUMMARY_JOB_MAX_ATTEMPTS", "SUMMARY_JOB_LEASE_SECONDS",
    "SUMMARY_JOB_RECOVERY_SECONDS", "SUMMARY_JOB_MAX_AGE_SECONDS",
    "SEC_DISTRIBUTED_LIMIT_ENABLED", "SEC_DISTRIBUTED_WAIT_SECONDS",
})
DEPLOY_STEPS = frozenset({
    "Update configured private task worker",
    "Deploy Cloud Run service",
    "Update pregenerate job image",
    "Update filing-scan + digest + calendar + alert + notable + retention job images",
    "Update backfill-facts job image and scheduled entrypoint",
})
REPLACING_OPTIONS = frozenset({
    "--set-env-vars", "--clear-env-vars", "--env-vars-file",
    "--set-secrets", "--clear-secrets", "--flags-file",
})
MAP_OPTIONS = frozenset({"--update-env-vars", "--update-secrets"})
REMOVE_OPTIONS = frozenset({"--remove-env-vars", "--remove-secrets"})
KEY = re.compile(r"[A-Z][A-Z0-9_]*\Z")


def _commands(script: str) -> list[list[str]]:
    """Read direct commands, including continued/quoted flags and shell separators."""
    commands = []
    for line in re.sub(r"\\\r?\n", " ", script).splitlines():
        lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        tokens = list(lexer)
        start = 0
        for position, token in enumerate(tokens + [";"]):
            if token and all(char in ";&|()" for char in token):
                command = tokens[start:position]
                if "gcloud" in command:
                    commands.append(command[command.index("gcloud"):])
                start = position + 1
    return commands


def _mutates_run(command: list[str]) -> bool:
    # Global options may occur before or inside the command group. A direct
    # invocation with an environment/secret write, or literal Run mutation words,
    # requires review even when its shape is unfamiliar. Conservatively refusing
    # an ambiguous command is safer than dropping it from this finite inventory.
    options = {token.split("=", 1)[0] for token in command}
    return bool(options & (REPLACING_OPTIONS | MAP_OPTIONS | REMOVE_OPTIONS)) or (
        "run" in command and bool(set(command) & {"create", "deploy", "update", "replace", "delete"})
    )


def preservation_problems(job: dict) -> list[str]:
    problems = []
    seen = set()
    for step in job["steps"]:
        name = step.get("name", "unnamed")
        commands = [command for command in _commands(step.get("run", "")) if _mutates_run(command)]
        if not commands:
            continue
        if name not in DEPLOY_STEPS or len(commands) != 1 or name in seen:
            problems.append(f"{name}: image-update command inventory changed; review every producer")
        seen.add(name)
        for command in commands:
            if "replace" in command:
                problems.append(f"{name}: resource replacement does not preserve controls")
            env_maps = 0
            for index, token in enumerate(command):
                option, equals, inline = token.partition("=")
                if option in REPLACING_OPTIONS:
                    problems.append(f"{name}: {option} can erase held controls")
                if option not in MAP_OPTIONS | REMOVE_OPTIONS:
                    continue
                value = inline if equals else (command[index + 1] if index + 1 < len(command) else "")
                if option == "--update-env-vars":
                    env_maps += 1
                entries = value.split(",")
                keys = [entry.split("=", 1)[0] for entry in entries]
                if not entries or any(not KEY.fullmatch(key) for key in keys):
                    problems.append(f"{name}: {option} keys are not a literal bounded map")
                if option in MAP_OPTIONS and any("=" not in entry for entry in entries):
                    problems.append(f"{name}: {option} is not an explicit additive map")
                for key in sorted(set(keys) & HELD_CONTROLS):
                    problems.append(f"{name}: {option} changes held {key}")
            if env_maps != 1:
                problems.append(f"{name}: expected one additive environment map")
    if seen != DEPLOY_STEPS:
        problems.append("image-update step inventory differs from the five reviewed deployment maps")
    return problems


def _job() -> dict:
    workflow = yaml.load((WORKFLOWS / "ci.yml").read_text(), Loader=yaml.BaseLoader)
    return workflow["jobs"]["deploy-backend"]


def test_ordinary_deployments_preserve_summary_and_shared_sec_controls():
    assert not (problems := preservation_problems(_job())), "\n".join(problems)
    # A separate workflow or a shell/env source must not introduce a held key
    # outside the reviewed command inventory, even when its value is false/zero.
    for path in sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")]):
        executable = "\n".join(line for line in path.read_text().splitlines() if not line.lstrip().startswith("#"))
        mentions = [key for key in sorted(HELD_CONTROLS) if re.search(r"\b" + key + r"\b", executable)]
        assert not mentions, f"{path.name} changes held controls outside their coordinated activation: {mentions}"


@pytest.mark.parametrize("name", sorted(DEPLOY_STEPS))
@pytest.mark.parametrize("replacement", [
    "--set-env-vars=DB_POOL_SIZE=1",
    "--update-env-vars=SUMMARY_DURABLE_GENERATION_ENABLED=false",
    "--update-env-vars=SUMMARY_PREWARM_MAX_PER_DAY=0",
    "--update-env-vars=SEC_DISTRIBUTED_LIMIT_ENABLED=true",
    "--update-env-vars=${UNINSPECTED_MAP}",
])
def test_every_reader_rejects_replacement_or_even_disabled_control_pins(name, replacement):
    job = copy.deepcopy(_job())
    step = next(step for step in job["steps"] if step.get("name") == name)
    step["run"] = re.sub(r"--update-env-vars=\S+", lambda _: replacement, step["run"])
    assert preservation_problems(job)


@pytest.mark.parametrize("flag", [
    "--remove-env-vars SUMMARY_NEW_JOBS_PAUSED",
    "--remove-secrets=SEC_DISTRIBUTED_LIMIT_ENABLED",
    "--update-secrets=SUMMARY_DURABLE_GENERATION_ENABLED=resource:latest",
    "--clear-env-vars", "--clear-secrets", "--env-vars-file=config.yml",
    "--flags-file=deploy.yml",
])
def test_extra_deploy_arguments_cannot_erase_or_hide_held_controls(flag):
    job = copy.deepcopy(_job())
    step = next(step for step in job["steps"] if step.get("name") == "Deploy Cloud Run service")
    step["run"] = step["run"].replace("--remove-env-vars=ENABLE_GUEST_DAILY_QUOTA", flag)
    assert preservation_problems(job)


@pytest.mark.parametrize("prefix", [
    "gcloud", "gcloud --quiet", "gcloud --project=earnings-nerd",
    "gcloud --project earnings-nerd beta",
])
def test_new_or_replaced_mutation_command_requires_inventory_review(prefix):
    job = copy.deepcopy(_job())
    job["steps"].append({"name": "New writer", "run": f"{prefix} run services replace config.yml"})
    assert preservation_problems(job)


@pytest.mark.parametrize("command", [
    "gcloud run --quiet services update earningsnerd-backend --clear-env-vars",
    "gcloud run services --project=earnings-nerd update earningsnerd-backend --clear-env-vars",
    "gcloud run services --quiet replace config.yml",
    "gcloud run jobs delete earningsnerd-pregenerate",
])
def test_interleaved_options_or_unfamiliar_writers_are_not_silently_skipped(command):
    job = copy.deepcopy(_job())
    job["steps"].append({"name": "Unreviewed writer", "run": command})
    assert preservation_problems(job)


def test_shell_reader_keeps_quoted_space_flags_and_additive_legacy_removal():
    job = copy.deepcopy(_job())
    step = next(step for step in job["steps"] if step.get("name") == "Deploy Cloud Run service")
    step["run"] = step["run"].replace(
        "--remove-env-vars=ENABLE_GUEST_DAILY_QUOTA", '--remove-env-vars "ENABLE_GUEST_DAILY_QUOTA"',
    )
    assert not preservation_problems(job)
    assert _commands("# gcloud run deploy ignored\ngcloud run deploy x \\\n --update-env-vars 'A=1'; gcloud run services update y --clear-env-vars") == [
        ["gcloud", "run", "deploy", "x", "--update-env-vars", "A=1"],
        ["gcloud", "run", "services", "update", "y", "--clear-env-vars"],
    ]
