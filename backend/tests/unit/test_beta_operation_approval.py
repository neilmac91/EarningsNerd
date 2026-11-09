"""The real beta approval reader refuses replay, edits and identity/source changes.

Provider reads are stubbed; no approval is posted, workflow dispatched, or cloud call made.
The API proves the owner account, not whether a human or an agent used its credentials.
"""
import copy
import importlib.util
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("beta_approval", ROOT / "ops/beta_approval.py")
approval = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(approval)
SHA = "a" * 40
ALLOWED = {"feedback-media-provision-apply", "feedback-media-verify-apply", "feedback-media-enable-apply",
           "feedback-media-disable-apply", "complimentary-access-apply"}
ENV = {"BETA_COMMENT_APPROVAL": "true", "BETA_COMMENT_APPROVAL_ENABLED": "true", "GITHUB_ACTIONS": "true",
       "GITHUB_REPOSITORY": approval.REPOSITORY, "GITHUB_REF": "refs/heads/main",
       "GITHUB_WORKFLOW_REF": approval.REPOSITORY + "/.github/workflows/ops.yml@refs/heads/main",
       "GITHUB_RUN_ID": "12345", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": SHA,
       "OP": "feedback-media-provision-apply", "CONFIRM_DIGEST": ""}


@pytest.mark.parametrize("operation", sorted(ALLOWED))
def test_only_the_five_beta_operations_can_request_the_optional_route(operation):
    assert approval.OPERATIONS == ALLOWED
    env = {**ENV, "OP": operation, "CONFIRM_DIGEST": "b" * 64 if operation == "complimentary-access-apply" else ""}
    wanted = approval.request(env)
    assert wanted["operation"] == operation
    assert wanted["confirm_digest"] == ("b" * 64 if operation == "complimentary-access-apply" else "none")


@pytest.mark.parametrize("change", [
    {"BETA_COMMENT_APPROVAL": "false"}, {"BETA_COMMENT_APPROVAL_ENABLED": ""},
    {"GITHUB_ACTIONS": "false"}, {"GITHUB_REPOSITORY": "another/repository"},
    {"GITHUB_REF": "refs/heads/a-branch"}, {"GITHUB_WORKFLOW_REF": "another/workflow"},
    {"GITHUB_RUN_ATTEMPT": "2"}, {"GITHUB_RUN_ID": "123\ncomment_id=9"}, {"GITHUB_SHA": "HEAD"},
    {"OP": "repair-quarterly-apply"}, {"OP": "describe-service"},
    {"OP": "complimentary-access-apply"}, {"CONFIRM_DIGEST": "b" * 64},
])
def test_dispatch_boundary_refuses_disabled_unsupported_or_ambiguous_requests(change):
    with pytest.raises(approval.Refused):
        approval.request({**ENV, **change})


@pytest.fixture
def provider(monkeypatch):
    wanted = approval.request(ENV)
    comment = {"id": 71, "node_id": "comment-node", "user": {"id": approval.OWNER_ID, "type": "User"},
               "author_association": "OWNER", "performed_via_github_app": None,
               "issue_url": f"https://api.github.com/repos/{approval.REPOSITORY}/issues/{approval.APPROVAL_ISSUE}",
               "body": approval.approval_text(wanted), "created_at": "2026-01-01T00:00:01Z",
               "updated_at": "2026-01-01T00:00:01Z"}
    state = {"comment": comment, "owner": approval.OWNER_ID, "head": SHA, "checkout": SHA, "attempt": 1,
             "edited": None, "deleted": False, "minimized": False, "calls": []}

    def read(endpoint, *arguments):
        state["calls"].append(endpoint)
        if endpoint == "repos/" + approval.REPOSITORY:
            return {"owner": {"id": state["owner"], "type": "User"}}
        if "/actions/runs/" in endpoint:
            return {"id": 12345, "run_attempt": state["attempt"], "event": "workflow_dispatch", "head_branch": "main",
                    "head_sha": SHA, "path": ".github/workflows/ops.yml", "created_at": "2026-01-01T00:00:00Z"}
        if endpoint.endswith("/git/ref/heads/main"):
            return {"object": {"sha": state["head"]}}
        if "/issues/comments/" in endpoint:
            if state["deleted"]:
                raise approval.Refused("GitHub approval state unavailable")
            return copy.deepcopy(state["comment"])
        if f"/issues/{approval.APPROVAL_ISSUE}/comments?" in endpoint:
            return [copy.deepcopy(state["comment"])]
        if endpoint == "graphql":
            return {"data": {"node": {"id": "comment-node", "lastEditedAt": state["edited"], "isMinimized": state["minimized"]}}}
        raise AssertionError(endpoint)

    monkeypatch.setattr(approval, "api", read)
    monkeypatch.setattr(approval.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout=state["checkout"]))
    return wanted, state


def test_the_exact_personal_owner_statement_is_rechecked_before_cloud_auth(provider):
    wanted, state = provider
    approval.verify(wanted, "71")
    assert state["calls"][-2:] == [f"repos/{approval.REPOSITORY}/issues/comments/71", "graphql"]


def test_wait_returns_the_exact_comment_id_and_a_fresh_verify_reads_it_again(monkeypatch, provider):
    wanted, state = provider
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    comment_id = approval.wait(wanted)
    assert comment_id == "71"
    prior_reads = state["calls"].count(f"repos/{approval.REPOSITORY}/issues/comments/71")
    approval.verify(wanted, comment_id)
    assert state["calls"].count(f"repos/{approval.REPOSITORY}/issues/comments/71") == prior_reads + 1


@pytest.mark.parametrize("failure", ["unreadable", "failed"])
def test_an_unreadable_or_failed_api_answer_is_a_closed_refusal(monkeypatch, failure):
    def run(*args, **kwargs):
        if failure == "failed":
            raise subprocess.CalledProcessError(1, "gh", output="PRIVATE", stderr="PRIVATE")
        return SimpleNamespace(stdout="<unreadable PRIVATE>")
    monkeypatch.setattr(approval.subprocess, "run", run)
    with pytest.raises(approval.Refused, match="state unavailable") as error:
        approval.api("repos/" + approval.REPOSITORY)
    assert "PRIVATE" not in str(error.value)


def test_missing_owner_metadata_cannot_authorize_a_run(monkeypatch, provider):
    wanted, _ = provider
    monkeypatch.setattr(approval, "api", lambda *args: {})
    with pytest.raises(approval.Refused):
        approval.verify(wanted, "71")


@pytest.mark.parametrize("field,value", [
    ("owner", 1), ("head", "b" * 40), ("checkout", "b" * 40), ("attempt", 2),
    ("edited", "2026-01-01T00:00:01Z"), ("deleted", True), ("minimized", True),
])
def test_later_deletion_same_second_edit_or_source_drift_revokes_the_match(provider, field, value):
    wanted, state = provider
    approval.verify(wanted, "71")
    state[field] = value
    with pytest.raises(approval.Refused):
        approval.verify(wanted, "71")


@pytest.mark.parametrize("change", [
    {"user": {"id": 1, "type": "User"}}, {"user": {"id": approval.OWNER_ID, "type": "Bot"}},
    {"author_association": "MEMBER"}, {"performed_via_github_app": {"id": 1}},
    {"issue_url": "https://api.github.com/repos/another/repository/issues/1954"},
    {"created_at": "2025-12-31T23:59:59Z", "updated_at": "2025-12-31T23:59:59Z"},
    {"updated_at": "2026-01-01T00:00:02Z"}, {"body": "approved"},
])
def test_another_author_thread_old_comment_or_edited_statement_is_not_approval(provider, change):
    wanted, state = provider
    state["comment"].update(change)
    with pytest.raises(approval.Refused):
        approval.verify(wanted, "71")


def test_a_statement_stored_with_crlf_line_endings_approves_as_its_lf_twin_does(monkeypatch, provider):
    # The founder's 2026-11-04 comment was stored with CRLF and matched nothing (#1954, 6638014487).
    wanted, state = provider
    state["comment"]["body"] = approval.approval_text(wanted).replace("\n", "\r\n") + "\r\n"
    approval.verify(wanted, "71")  # First, so a reader that refuses CRLF fails here and not after wait's 15 minutes.
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert approval.wait(wanted) == "71"


@pytest.mark.parametrize("damage", [
    lambda text: text.replace("\n", "\r"), lambda text: text.replace("\n", "\r\r\n", 1),
    lambda text: text.replace("\n", "\n\n", 1), lambda text: text.replace("\n", " \n", 1),
    lambda text: "```text\n" + text + "\n```", lambda text: text + "\nconfirm_digest: none",
    lambda text: text.replace("\n", "\r\n").replace("run: 12345", "run: 12346"),
])
def test_only_the_line_ending_pair_is_folded_and_every_other_difference_is_refused(provider, damage):
    wanted, state = provider
    state["comment"]["body"] = damage(approval.approval_text(wanted))
    with pytest.raises(approval.Refused):
        approval.verify(wanted, "71")


@pytest.mark.parametrize("field,value", [("run", "12346"), ("attempt", "2"), ("sha", "b" * 40),
                                         ("operation", "feedback-media-enable-apply"), ("confirm_digest", "c" * 64)])
def test_statement_cannot_be_replayed_for_another_run_source_action_or_manifest(provider, field, value):
    wanted, state = provider
    changed = {**wanted, field: value}
    state["comment"]["body"] = approval.approval_text(changed)
    with pytest.raises(approval.Refused):
        approval.verify(wanted, "71")


def test_no_comment_times_out_without_authorizing_anything(monkeypatch, provider):
    wanted, _ = provider
    monkeypatch.setattr(approval, "run_context", lambda wanted: approval.timestamp("2026-01-01T00:00:00Z"))
    monkeypatch.setattr(approval, "WAIT_SECONDS", 0)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    with pytest.raises(approval.Refused, match="within 15 minutes"):
        approval.wait(wanted)


def test_waiting_has_no_cloud_identity_or_ops_lock_and_recheck_is_immediately_before_wif():
    workflow = yaml.load((ROOT / ".github/workflows/ops.yml").read_text(), Loader=yaml.BaseLoader)
    waiter, ops = workflow["jobs"]["approve-comment"], workflow["jobs"]["ops"]
    assert "concurrency" not in waiter and "environment" not in waiter
    assert waiter["permissions"] == {"contents": "read", "actions": "read", "pull-requests": "read"}
    assert waiter["timeout-minutes"] == "20"
    assert workflow["on"]["workflow_dispatch"]["inputs"]["beta_comment_approval"]["default"] == "false"
    assert waiter["steps"][-1]["run"] == "python3 ops/beta_approval.py wait"
    assert waiter["steps"][-1]["env"]["BETA_COMMENT_APPROVAL_ENABLED"] == "${{ vars.BETA_COMMENT_APPROVAL_ENABLED }}"
    steps = ops["steps"]
    auth = next(i for i, step in enumerate(steps) if step.get("name") == "Authenticate to Google Cloud")
    recheck = steps[auth - 1]
    assert recheck["name"] == "Recheck the exact beta approval before cloud authentication"
    assert "python3 ops/beta_approval.py verify" in recheck["run"]
    assert recheck["env"]["APPROVAL_COMMENT_ID"] == "${{ needs.approve-comment.outputs.comment_id }}"
    assert not any(step.get("continue-on-error") for step in (*waiter["steps"], recheck))
