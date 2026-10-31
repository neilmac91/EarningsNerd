"""Product (head _verify_citations) vs main's verifier vs copilot eval scorer on realistic shapes."""
import os, sys
from types import SimpleNamespace
for k, v in {"SECRET_KEY": "test-secret-key-must-be-long-enough-123", "STRIPE_SECRET_KEY": "sk_test_mock_stripe_key_12345",
             "STRIPE_WEBHOOK_SECRET": "whsec_mock_stripe_webhook_12345", "SKIP_REDIS_INIT": "true"}.items():
    os.environ.setdefault(k, v)
for k in ("DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY"):
    os.environ.pop(k, None)
os.environ["OPENAI_API_KEY"] = "sk-test-key-for-mocking"; os.environ["OPENAI_BASE_URL"] = "http://127.0.0.1:9/v1"
sys.path.insert(0, "/home/user/wt/cite-rev/backend")
from app.services import copilot_service as cs, provenance_service as prov
from evals.copilot_scorers import score_citation_faithfulness
SRC = prov.normalize_for_match(
    "For the fiscal year ending January 31, 2027 (“fiscal 2027”), we project capital expenditures will be "
    "approximately $25 billion to $27 billion. Revenue increased to $391.0 billion in fiscal 2024.")
F = SimpleNamespace(document_url="https://www.sec.gov/Archives/edgar/data/1/2/d.htm", sec_url=None)
for ex in ['For the fiscal year ending January 31, 2027 ("fiscal 2027"), we project capital expenditures',
           "'Revenue increased to $391.0 billion in fiscal 2024.'",
           '"Revenue increased to $391.0 billion in fiscal 2024."',
           'We said "Revenue increased to $391.0 billion in fiscal 2024."']:
    head = cs._verify_citations([{"n": 1, "excerpt": ex, "section": "Item 7"}], F, SRC, set())["1"]
    main = prov.verify_excerpt_in_text(ex.strip(), SRC)
    ratio, unver = score_citation_faithfulness([{"excerpt": ex, "section_ref": "Item 7"}], SRC)
    print(f"head_product={head['verified']!s:5} main_product={main!s:5} scorer_ok={not unver!s:5} | {ex[:70]}")
    print("    head url:", head["fragment_url"].split("#")[-1][:90])
    if main:
        print("    main url:", prov.build_text_fragment_url(F.document_url, ex.strip()).split("#")[-1][:90])
