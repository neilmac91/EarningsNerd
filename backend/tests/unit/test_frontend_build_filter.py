"""Run the frontend's Vercel build filter on real Git histories; it builds unless it proves it need not.

Vercel builds the frontend project on every push to every branch and bills each build, and most pushes
change nothing that build reads. So frontend/vercel.json's ``ignoreCommand`` runs
frontend/scripts/vercel-ignore-build.sh before the build, and Vercel cancels the build when it exits 0.
A wrong 0 leaves production, or a pull request's preview, on an older frontend with no failing check
anywhere. The script therefore exits 0 only when this commit and the commit of the branch's last successful
deployment (VERCEL_GIT_PREVIOUS_SHA) hold the same build inputs: everything under frontend/, and each file
outside it that a shipped frontend file imports. Whatever else it meets, it builds.

Each case runs the command as vercel.json words it, in frontend/, which is where Vercel runs it
(the project's Root Directory, docs/DEPLOYMENT.md).
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.unit.test_ci_cost_controls import BROWSER_INPUTS_OUTSIDE_FRONTEND, outside_frontend_references

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = "frontend/scripts/vercel-ignore-build.sh"
NOT_DEPLOYED = "f" * 40


@pytest.fixture
def project(tmp_path):
    """A repository with a frontend/ that holds the filter, and one commit, standing for a deployed one."""
    repo = tmp_path / "repo"
    repo.mkdir()
    # An empty global config of its own, never /dev/null: a config write would rename git's lock file over it.
    global_config = tmp_path / "gitconfig"
    global_config.write_text("", encoding="utf-8")
    env = {
        **{name: value for name, value in os.environ.items() if not name.startswith("VERCEL")},
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": str(global_config),
        "GIT_AUTHOR_NAME": "Build filter test", "GIT_AUTHOR_EMAIL": "ci@example.invalid",
        "GIT_COMMITTER_NAME": "Build filter test", "GIT_COMMITTER_EMAIL": "ci@example.invalid",
    }

    def git(*args):
        return subprocess.check_output(
            ["git", "-c", "commit.gpgsign=false", *args], cwd=repo, env=env,
            text=True, stderr=subprocess.PIPE, timeout=20,
        ).strip()

    def commit(*paths, delete=False):
        """Change, add or delete each path in one commit; returns the commit."""
        for path in paths:
            target = repo / path
            if delete:
                target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("a", encoding="utf-8") as handle:
                    handle.write(f"changed {path}\n")
        git("add", "-A")
        git("commit", "-qm", "change")
        return git("rev-parse", "HEAD")

    git("init", "-q", "-b", "main")
    (repo / SCRIPT).parent.mkdir(parents=True)
    shutil.copy(ROOT / SCRIPT, repo / SCRIPT)
    commit("frontend/app/page.tsx", "frontend/package-lock.json", "backend/main.py",
           *BROWSER_INPUTS_OUTSIDE_FRONTEND)
    return repo, env, git, commit


def decide(project, previous):
    """Run vercel.json's ignoreCommand as Vercel does. Returns whether it builds, and the line it printed."""
    repo, env, _, _ = project
    command = json.loads((ROOT / "frontend/vercel.json").read_text(encoding="utf-8"))["ignoreCommand"]
    if previous is not None:
        env = {**env, "VERCEL_GIT_PREVIOUS_SHA": previous}
    result = subprocess.run(
        ["sh", "-c", command], cwd=repo / "frontend", env=env, capture_output=True, text=True, timeout=20, check=False,
    )
    said = result.stdout.strip()
    # Vercel builds on any exit but 0; the script's own answers are 0 and 1, each with its one line.
    assert result.returncode in (0, 1), (result.returncode, said, result.stderr)
    assert said.startswith("ignore-build: skip: " if result.returncode == 0 else "ignore-build: build: "), said
    assert "\n" not in said, said
    return result.returncode != 0, said


@pytest.mark.parametrize("paths", [
    ("backend/main.py",),
    ("docs/DEPLOYMENT.md", "tasks/todo.md", ".github/workflows/ci.yml", "README.md"),
    # Beside an input, not one: a directory and a file whose names only start as an input's does.
    ("frontendish/app/page.tsx",),
    ("backend/app/public_email_addresses.json.bak",),
])
def test_a_change_to_nothing_the_build_reads_skips_the_build(project, paths):
    _, _, git, commit = project
    deployed = git("rev-parse", "HEAD")
    for path in paths:
        commit(path)
    builds, said = decide(project, deployed)
    assert not builds and deployed in said and git("rev-parse", "HEAD") in said, said


@pytest.mark.parametrize("path, delete", [
    ("frontend/app/page.tsx", False),
    ("frontend/app/page.tsx", True),
    ("frontend/package-lock.json", False),
    ("frontend/public/new-file.svg", False),
    ("frontend/vercel.json", False),
    # Everything under frontend/ is an input, the specs included: narrowing that is a change to the script and
    # to this case together.
    ("frontend/tests/unit/some.spec.ts", False),
    ("backend/app/public_email_addresses.json", False),
    ("backend/app/public_email_addresses.json", True),
])
def test_a_change_to_a_build_input_builds(project, path, delete):
    _, _, git, commit = project
    deployed = git("rev-parse", "HEAD")
    commit(path, delete=delete)
    builds, said = decide(project, deployed)
    assert builds and path in said, said


def test_the_whole_range_since_the_last_deployment_decides_not_the_last_commit(project):
    # Vercel cancels the builds of the commits this script skips, so the last deployment can be several
    # commits back: an input changed in any of them builds, whatever the newest commit touches.
    _, _, git, commit = project
    deployed = git("rev-parse", "HEAD")
    commit("frontend/app/page.tsx")
    commit("backend/main.py")
    commit("docs/DEPLOYMENT.md")
    builds, said = decide(project, deployed)
    assert builds and "frontend/app/page.tsx" in said, said


def test_it_builds_whenever_it_cannot_prove_the_inputs_unchanged(project, tmp_path):
    repo, env, git, commit = project
    deployed = git("rev-parse", "HEAD")
    head = commit("backend/main.py")
    assert not decide(project, deployed)[0], "the baseline: this change alone skips the build"

    # A branch's first deployment has no earlier one: Vercel leaves the variable empty, or unset.
    for previous in (None, ""):
        builds, said = decide(project, previous)
        assert builds and "no earlier successful deployment" in said, said
    # Only a whole commit id is compared. A name git would resolve is not one: against HEAD itself, or a
    # shortened id, the comparison would run and find nothing changed.
    for previous in ("HEAD", "main", deployed[:12]):
        builds, said = decide(project, previous)
        assert builds and "no earlier successful deployment" in said, (previous, said)
    # A redeploy of the commit already deployed is how a changed dashboard variable reaches a build.
    builds, said = decide(project, head)
    assert builds and "redeploy" in said, said
    # A commit this clone does not hold: one that never existed, and one a shallow clone left behind.
    builds, said = decide(project, NOT_DEPLOYED)
    assert builds and "could not compare" in said, said
    shallow = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth=1", f"file://{repo}", str(shallow)],
        env=env, check=True, capture_output=True, timeout=20,
    )
    builds, said = decide((shallow, env, None, None), deployed)
    assert builds and "could not compare" in said, said
    # No repository at all.
    bare = tmp_path / "no-repository"
    (bare / SCRIPT).parent.mkdir(parents=True)
    shutil.copy(ROOT / SCRIPT, bare / SCRIPT)
    builds, said = decide((bare, {**env, "GIT_CEILING_DIRECTORIES": str(tmp_path)}, None, None), deployed)
    assert builds and "could not read HEAD" in said, said


def test_every_file_the_build_reads_outside_frontend_is_a_build_input(project):
    # The filter names its inputs outside frontend/ one by one, so a shipped file that starts to import another
    # must add it there: the scan below finds each, and a change to it alone has to build. The files only the
    # browser specs read are not the build's, and a change to one alone skips it.
    _, _, git, commit = project
    references = outside_frontend_references(specs=False)
    assert references, "the scan found no reference at all: its pattern or its file walk is broken"
    read_by_the_build = set()
    for target, source in references.items():
        assert ROOT in target.parents and target.is_file(), (
            f"frontend/{source} names {target}, which is not a file in the repository: write the whole path as one "
            "literal, so this gate can read which file the build depends on")
        read_by_the_build.add(target.relative_to(ROOT).as_posix())
    assert read_by_the_build <= set(BROWSER_INPUTS_OUTSIDE_FRONTEND), (
        "the build reads a file the browser jobs' scope does not know: test_ci_cost_controls.py fails on it too")
    for path in sorted(BROWSER_INPUTS_OUTSIDE_FRONTEND):
        deployed = git("rev-parse", "HEAD")
        commit(path)
        builds, said = decide(project, deployed)
        assert builds == (path in read_by_the_build), (
            f"{path} is {'read' if path in read_by_the_build else 'not read'} by the build, but the filter says: "
            f"{said}. Name in BUILD_INPUTS ({SCRIPT}) exactly the files outside frontend/ that the build reads")
