"""Prompt fix candidate: offline identity of the composed Copilot SYSTEM_PROMPT. No provider call, no network.

Usage (from the repository root; real provider keys unset, the import needs conftest's non-calling mock key):
  env -u OPENAI_API_KEY -u DEEPSEEK_API_KEY -u OPENAI_BASE_URL OPENAI_API_KEY=sk-test-key-for-mocking \
      SECRET_KEY=offline-identity-check-not-a-secret-0 SKIP_REDIS_INIT=true PYTHONDONTWRITEBYTECODE=1 \
      python tasks/review-evidence/prompt-candidate-2026-10-02/prompt_identity.py backend <BASE_SHA>

It imports the checked-out backend's copilot_service and asserts, failing on any mismatch:
1. _build_messages(...)[0] == {"role": "system", "content": SYSTEM_PROMPT}. That message is what the
   runner records as tool_trace.initial_messages[0] (path traced in g-stage2-2026-10-02/g2_prompt_hash.py).
2. The candidate's full sha256 and length equal the pinned values below.
3. Removing the two insertions (the RULES bullet and the not-disclosed template extension) gives arm B
   (G stage 2: 164570555f40..., 5006 characters).
4. Re-inserting the 51-character clause into arm B gives main (a88b6fb1de5b..., 5057 characters), and that
   string equals the base commit's own SYSTEM_PROMPT, evaluated from `git show <BASE>:<copilot_service.py>`
   with the imported module's globals (the f-string reads four module constants; scope_hashes.py proves
   every other top-level statement of the file is AST-identical to base).
5. Decision F's prose floor _MIN_QUOTED_LEN == 8 and the citation floor _MIN_VERIFIABLE_LEN == 24.
It also prints the counts, offsets, non-ASCII characters and the five step-3 pins of the owner test.
"""
import ast
import hashlib
import os
import subprocess
import sys
from types import SimpleNamespace

CANDIDATE_SHA256 = "a22fb4cd5472512f5867bad039feaef7400487869487fa94ae5d7a94073309f5"
CANDIDATE_CHARS, CANDIDATE_BYTES = 5289, 5313
ARM_B_SHA256, ARM_B_CHARS = "164570555f40de62e102c5b24e6fc6a80361aeb5767e37f80019faebc7c90087", 5006
MAIN_SHA256, MAIN_CHARS = "a88b6fb1de5b7f3103088f0795b04bea9b3216627e59dcb8bb9ebfd98ecd88cd", 5057

CLAUSE = ", including when all cited figures use tool markers"
CLAUSE_SITE = "output []\n   after the citations line"
RULE_BLOCK = ("\n- Each quotation in your answer prose must be one contiguous span copied verbatim from the filing. "
              "Keep table figures outside quotation marks, never quote a table row with cells left out, and never "
              "put an ellipsis inside a quotation.")
TEMPLATE_EXT = "; name the missing metric without quotation marks"
PINS = ["SHORTEST contiguous span", "at least 24 characters after whitespace is collapsed",
        "choose a longer contiguous source span; never pad or paraphrase it",
        "Never stitch separated table cells or sentences together, or insert an ellipsis",
        "reuse its existing [F#] marker; do not add a text citation"]
SERVICE = "backend/app/services/copilot_service.py"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def check(label: str, ok: bool) -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {label}")
    if not ok:
        raise SystemExit(f"identity mismatch: {label}")


backend, base = os.path.abspath(sys.argv[1]), sys.argv[2]
root = os.path.dirname(backend)
os.chdir(backend)
sys.path.insert(0, backend)
from app.services import copilot_service as cs  # noqa: E402
from app.services.provenance_service import _MIN_VERIFIABLE_LEN  # noqa: E402

head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
base_sha = subprocess.run(["git", "rev-parse", base], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
base_src = subprocess.run(["git", "show", f"{base_sha}:{SERVICE}"], cwd=root, capture_output=True, text=True,
                          check=True).stdout
node = next(n for n in ast.parse(base_src).body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "SYSTEM_PROMPT" for t in n.targets))
base_prompt = eval(compile(ast.Expression(node.value), "<base SYSTEM_PROMPT>", "eval"), dict(vars(cs)))  # noqa: S307

prompt = cs.SYSTEM_PROMPT
stub = SimpleNamespace(company=SimpleNamespace(name="X", ticker="X"), filing_type="10-K", filing_date=None,
                       accession_number="0000000000-00-000000", period_of_report=None, xbrl_data=None)
built = cs._build_messages(stub, "Filing source.", "Revenue?", None)[0]

print(f"checkout HEAD {head} (git rev-parse in {root})")
print(f"base          {base_sha}")
print(f"copilot_service.py sha256: worktree {hashlib.sha256(open(os.path.join(root, SERVICE), 'rb').read()).hexdigest()}"
      f" | base {hashlib.sha256(base_src.encode('utf-8')).hexdigest()}")
print("candidate SYSTEM_PROMPT")
print(f"  sha256 {sha(prompt)}  chars {len(prompt)}  utf-8 bytes {len(prompt.encode('utf-8'))}")
check("1. _build_messages(...)[0] == {'role': 'system', 'content': SYSTEM_PROMPT}",
      built == {"role": "system", "content": prompt})
check(f"2. candidate sha256 == {CANDIDATE_SHA256} and {CANDIDATE_CHARS} chars / {CANDIDATE_BYTES} bytes",
      sha(prompt) == CANDIDATE_SHA256 and len(prompt) == CANDIDATE_CHARS and len(prompt.encode("utf-8")) == CANDIDATE_BYTES)
print(f"  counts: clause {prompt.count(CLAUSE)}, rule block {prompt.count(RULE_BLOCK)}, template extension "
      f"{prompt.count(TEMPLATE_EXT)}, 'If there are no filing-text markers, output []' "
      f"{prompt.count('If there are no filing-text markers, output []')}")
check("   clause absent; rule block and template extension present exactly once",
      prompt.count(CLAUSE) == 0 and prompt.count(RULE_BLOCK) == 1 and prompt.count(TEMPLATE_EXT) == 1)
arm_b = prompt.replace(RULE_BLOCK, "", 1).replace(TEMPLATE_EXT, "", 1)
print(f"  minus both insertions: sha256 {sha(arm_b)}  chars {len(arm_b)}")
check(f"3. candidate minus (b) and (c) == arm B {ARM_B_SHA256[:8]} ({ARM_B_CHARS} chars)",
      sha(arm_b) == ARM_B_SHA256 and len(arm_b) == ARM_B_CHARS)
check("   arm B == base SYSTEM_PROMPT with the clause removed once", arm_b == base_prompt.replace(CLAUSE, "", 1))
main = arm_b.replace(CLAUSE_SITE, CLAUSE_SITE + CLAUSE, 1)
print(f"  plus the clause:       sha256 {sha(main)}  chars {len(main)}")
check(f"4. arm B plus clause == main {MAIN_SHA256[:8]} ({MAIN_CHARS} chars)",
      sha(main) == MAIN_SHA256 and len(main) == MAIN_CHARS)
check("   == base commit's own SYSTEM_PROMPT (git show <BASE>, evaluated)", main == base_prompt)
check(f"5. _MIN_QUOTED_LEN == 8 ({cs._MIN_QUOTED_LEN}) and _MIN_VERIFIABLE_LEN == 24 ({_MIN_VERIFIABLE_LEN})",
      cs._MIN_QUOTED_LEN == 8 and _MIN_VERIFIABLE_LEN == 24)
print("context")
print(f"  offsets: tool MUST {prompt.find('you MUST call the provided')}, rule block {prompt.find(RULE_BLOCK)}, "
      f"OUTPUT FORMAT {prompt.find('OUTPUT FORMAT')}, template extension {prompt.find(TEMPLATE_EXT)}")
print(f"  non-ASCII characters: {sorted({c for c in prompt if ord(c) > 127})}; braces in insertions: "
      f"{any(c in RULE_BLOCK + TEMPLATE_EXT for c in '{}')}")
print(f"  five step-3 pins present: {all(p in prompt for p in PINS)}")
print("all identity checks passed")
