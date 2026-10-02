"""G stage 2 (arm B) offline prompt-hash check. No provider calls; no network.

Usage (keys unset):
  env -u OPENAI_API_KEY -u DEEPSEEK_API_KEY -u OPENAI_BASE_URL OPENAI_API_KEY=sk-test-key-for-mocking \
      SECRET_KEY=offline-hash-check-not-a-secret-0000 \
      SKIP_REDIS_INIT=true <venv>/bin/python g2_prompt_hash.py <backend_dir> [copilot-eval.json ...]

Hashes exactly as g_precheck.py does for the system prompt: sha256(content.encode('utf-8')).hexdigest()[:8],
where content is initial_messages[0].content. The runner records initial_messages as the `messages`
argument handed to openai_service.stream_chat_with_tools (evals/copilot_runner.py:176), which is
copilot_service._build_messages(...) (copilot_service.py:1571, :1617), whose [0] is
{"role": "system", "content": SYSTEM_PROMPT} (copilot_service.py:349) and is never merged because [1] is a
user message (_merge_consecutive_roles, copilot_service.py:334-341).
"""
import hashlib, json, os, sys
from types import SimpleNamespace

CLAUSE = ", including when all cited figures use tool markers"


def h8(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


backend = os.path.abspath(sys.argv[1])
os.chdir(backend)
sys.path.insert(0, backend)
from app.services import copilot_service as cs  # noqa: E402

stub = SimpleNamespace(company=SimpleNamespace(name="X", ticker="X"), filing_type="10-K", filing_date=None,
                       accession_number="0000000000-00-000000", period_of_report=None, xbrl_data=None)
built = cs._build_messages(stub, "Filing source.", "Revenue?", None)[0]
assert built == {"role": "system", "content": cs.SYSTEM_PROMPT}, "messages[0] is not SYSTEM_PROMPT verbatim"

print(f"backend={backend}")
print(f"  SYSTEM_PROMPT               sha256[:8]={h8(cs.SYSTEM_PROMPT)}  chars={len(cs.SYSTEM_PROMPT)}  clause_count={cs.SYSTEM_PROMPT.count(CLAUSE)}")
print(f"  _build_messages()[0].content sha256[:8]={h8(built['content'])}")
if cs.SYSTEM_PROMPT.count(CLAUSE) == 1:
    arm_b = cs.SYSTEM_PROMPT.replace(CLAUSE, "", 1)
    print(f"  derived arm B (in-memory replace of {CLAUSE!r}) sha256[:8]={h8(arm_b)}  chars={len(arm_b)}")

for path in sys.argv[2:]:
    d = json.load(open(path))
    seen = {}
    for r in d["results"]:
        im = (r.get("tool_trace") or {}).get("initial_messages") or []
        if im:
            c = im[0]["content"]
            seen.setdefault(h8(c), [0, c == cs.SYSTEM_PROMPT])[0] += 1
    print(f"  artifact {path.split('/')[-2]}: " + ", ".join(
        f"{k} x{v[0]} (== this SYSTEM_PROMPT: {v[1]})" for k, v in seen.items()))
