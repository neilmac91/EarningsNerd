import os, sys
from types import SimpleNamespace
for k, v in {"SECRET_KEY": "test-secret-key-must-be-long-enough-123", "STRIPE_SECRET_KEY": "sk_test_mock_stripe_key_12345",
             "STRIPE_WEBHOOK_SECRET": "whsec_mock_stripe_webhook_12345", "SKIP_REDIS_INIT": "true"}.items():
    os.environ.setdefault(k, v)
os.environ["OPENAI_API_KEY"] = "sk-test-key-for-mocking"; os.environ["OPENAI_BASE_URL"] = "http://127.0.0.1:9/v1"
sys.path.insert(0, "/home/user/wt/cite-rev/backend")
from app.services import copilot_service as cs, provenance_service as prov
K = "Revenue increased to $391.0 billion in fiscal 2024."
SRC = prov.normalize_for_match(K)
F = SimpleNamespace(document_url="https://x/d.htm", sec_url=None)
cases = [
    {"section": "Item 7", "section_ref": 'Item 7 "Fake words"'},
    {"section": None, "section_ref": 'Item 7 "Fake words"'},
    {"section": "", "section_ref": "Item 7 “Fake words”"},
    {"section": 'Item 7 ”x', "section_ref": "Item 7"},
    {"section": "Item 7 „Fake words‟"},
    {"section": "Item 7 ＂Fake words＂"},
    {"section": "Item 7 ‘Fake words’"},
    {"section": "Item 7 «Fake words»"},
]
for extra in cases:
    out = cs._verify_citations([{"n": 1, "excerpt": K, **extra}], F, SRC, set())["1"]
    raised = None
    try:
        cs._verify_citations([{"n": 1, "excerpt": K, **extra}], F, SRC, {"1"})
    except cs._UnpublishableAnswer as e:
        raised = str(e)
    print(f"published_label={out['section_ref']!r:28} verified={out['verified']!s:5} referenced_raises={raised!r}")
