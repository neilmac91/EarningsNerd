"""Prompt fix candidate: scope proof. Everything the qualification depends on, other than the prompt, is
byte-identical to base. Reads git only; no app import, no provider call, no network.

Usage (from the repository root): python tasks/review-evidence/prompt-candidate-2026-10-02/scope_hashes.py <BASE> [<HEAD>]

Checks, failing (exit 1) on any violation:
1. For each scoped path (files, or every tracked file under a directory): `git diff --exit-code <BASE> <HEAD> -- <path>`
   exits 0, and the sha256 of the blob at BASE equals the sha256 at HEAD (both printed).
2. Allowed diff: `git diff --name-only <BASE> <HEAD>` lists only copilot_service.py, the owner test and new files
   in this evidence folder (no existing tasks/ file, no tasks/todo.md).
3. AST scope: in copilot_service.py every top-level statement except the SYSTEM_PROMPT assignment is identical
   (ast.dump) at BASE and HEAD; in the owner test every top-level statement except
   test_contiguous_citation_instruction_reaches_actual_service_messages is identical.
"""
import ast
import hashlib
import subprocess
import sys

SERVICE = "backend/app/services/copilot_service.py"
OWNER_TEST = "backend/tests/unit/test_copilot_live_regressions.py"
FOLDER = "tasks/review-evidence/prompt-candidate-2026-10-02/"
SCOPE = [
    ("scorer", "backend/evals/copilot_scorers.py"),
    ("runner", "backend/evals/copilot_runner.py"),
    ("bootstrap", "backend/evals/copilot_bootstrap.py"),
    ("schema", "backend/evals/copilot_schema.py"),
    ("golden set", "backend/evals/copilot_golden_set.json"),
    ("sources", "backend/evals/copilot_sources.json"),
    ("baseline", "backend/evals/baseline_scores.json"),
    ("baseline", "backend/evals/golden_set.json"),
    ("baseline", "backend/evals/baselines"),
    ("regression gate", "backend/evals/regression_gate.py"),
    ("RUNBOOK", "backend/evals/RUNBOOK.md"),
    ("runtime pins", "backend/requirements.txt"),
    ("runtime pins", "backend/requirements.in"),
    ("runtime pins", "backend/requirements-dev.txt"),
    ("runtime pins", "backend/requirements-eval.txt"),
    ("model/flags", ".github/ai-model.env"),
    ("model/flags", "backend/app/config.py"),
    ("workflow", ".github/workflows/ci.yml"),
    ("workflow", ".github/workflows/copilot-eval.yml"),
    ("tool path", "backend/app/services/copilot_tools.py"),
    ("tool path", "backend/app/services/ai/copilot_chat.py"),
    ("tool path", "backend/app/services/citation_markers.py"),
    ("citation floor", "backend/app/services/provenance_service.py"),
    ("F owner test (byte-identical)", "backend/tests/unit/test_copilot_prose_quotations.py"),
    ("locked T1", "backend/tests/integration/test_summary_stream_contract.py"),
    ("locked T1/T10 fixture", "backend/tests/fixtures/summary_stream_frames.json"),
    ("locked T1/T10 fixture", "backend/tests/fixtures/summary_stream_frames.README"),
    ("locked T1 harness", "backend/tests/support/summary_stream_harness.py"),
    ("locked heartbeat", "backend/tests/integration/test_summary_stream_heartbeat.py"),
    ("locked T2", "backend/tests/unit/test_background_generation_characterization.py"),
    ("locked T3 successor", "backend/tests/unit/test_generation_requires_account.py"),
    ("locked T4", "backend/tests/unit/test_subscription_webhook_sync.py"),
    ("locked T5", "backend/tests/unit/test_expired_trial_gating.py"),
    ("locked T7", "backend/tests/unit/test_filing_scan.py"),
    ("locked T8", "backend/tests/unit/test_refresh_replay.py"),
    ("locked T9", "backend/tests/unit/test_companyfacts_fixture.py"),
    ("locked T10", "frontend/tests/unit/summaryStream.contract.spec.ts"),
    ("locked SSE parser", "frontend/tests/unit/summaryStream.spec.ts"),
    ("locked auth", "backend/tests/unit/test_auth_flow.py"),
    ("locked auth", "backend/tests/unit/test_auth_cookies.py"),
    ("locked Stripe", "backend/tests/unit/test_stripe_webhook.py"),
    ("locked serializer pin", "backend/tests/unit/test_export_service.py"),
    ("locked serializer pin", "backend/tests/unit/test_structured_markdown_render.py"),
    ("locked serializer pin", "backend/tests/unit/test_markdown_render_bullets.py"),
    ("measurement tool", "tasks/review-evidence/f-quote-containment-2026-10-01/f1-attribution-2026-10-02/f_attribution.py"),
    ("measurement tool", "tasks/review-evidence/pr1021-qualification-2026-10-01/prose_quote_audit.py"),
    ("measurement tool", "tasks/review-evidence/g-stage1-2026-10-02/g_decide.py"),
    ("measurement tool", "tasks/review-evidence/g-stage1-2026-10-02/g_precheck.py"),
    ("measurement tool", "tasks/review-evidence/g-stage2-2026-10-02/copilot_cost_runnerlog.py"),
]


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, check=check)


def blob(ref: str, path: str) -> bytes:
    return git("show", f"{ref}:{path}").stdout


def top_level(ref: str, path: str, keep: str) -> tuple[list[str], list[str]]:
    """(dumps of every top-level statement except the one named `keep`, dumps of `keep`)."""
    others, kept = [], []
    for node in ast.parse(blob(ref, path).decode("utf-8")).body:
        names = [t.id for t in getattr(node, "targets", []) if isinstance(t, ast.Name)] + [getattr(node, "name", None)]
        (kept if keep in names else others).append(ast.dump(node))
    return others, kept


base = git("rev-parse", sys.argv[1]).stdout.decode().strip()
head = git("rev-parse", sys.argv[2] if len(sys.argv) > 2 else "HEAD").stdout.decode().strip()
print(f"base {base}\nhead {head}\n")
failures = []

print("1. byte identity (git diff --exit-code BASE HEAD -- path; sha256 at BASE | at HEAD)")
for label, path in SCOPE:
    files = git("ls-tree", "-r", "--name-only", base, "--", path).stdout.decode().split()
    if not files:
        failures.append(f"{path}: not tracked at base")
        print(f"  MISSING  {path}")
        continue
    diff_rc = git("diff", "--exit-code", "--quiet", base, head, "--", path, check=False).returncode
    for f in files:
        a = hashlib.sha256(blob(base, f)).hexdigest()
        b_proc = git("show", f"{head}:{f}", check=False)
        b = hashlib.sha256(b_proc.stdout).hexdigest() if b_proc.returncode == 0 else "<absent at head>"
        same = a == b and diff_rc == 0
        if not same:
            failures.append(f"{f}: differs")
        print(f"  {'same' if same else 'DIFF'}  diff-rc={diff_rc}  {f}  ({label})\n        {a} | {b}")

print("\n2. allowed diff (git diff --name-status BASE HEAD)")
for line in git("diff", "--name-status", base, head).stdout.decode().splitlines():
    status, path = line.split("\t", 1)
    allowed = (path in (SERVICE, OWNER_TEST) and status == "M") or (path.startswith(FOLDER) and status == "A")
    if not allowed:
        failures.append(f"unexpected change: {line}")
    print(f"  {'ok ' if allowed else 'BAD'}  {status}  {path}")

print("\n3. AST scope")
for path, keep in ((SERVICE, "SYSTEM_PROMPT"), (OWNER_TEST, "test_contiguous_citation_instruction_reaches_actual_service_messages")):
    (base_other, base_kept), (head_other, head_kept) = top_level(base, path, keep), top_level(head, path, keep)
    same_other = base_other == head_other
    if not same_other or len(base_kept) != 1 or len(head_kept) != 1:
        failures.append(f"{path}: statements other than {keep} changed")
    print(f"  {path}: {len(base_other)} other top-level statements at base, {len(head_other)} at head, identical: "
          f"{same_other}; {keep} changed: {base_kept != head_kept}")

print("\nRESULT:", "PASS" if not failures else "FAIL\n  " + "\n  ".join(failures))
sys.exit(1 if failures else 0)
