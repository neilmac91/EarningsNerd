"""Independent offline replay: base (f6e79a50) vs head provenance enrichment on retained summary evals.

Loads base provenance_service source (git show) as a separate module; all its imports resolve to the
head package, whose dependencies are untouched by the diff. Compares (1) _enrich_forward_quotes on each
row's real forward_signals block and (2) the full enrich_raw_summary output per row (all surfaces).
Referent: grounding_excerpt (proxy for the cached filing text)."""
import copy, glob, importlib.util, json, os, subprocess, sys, types
from types import SimpleNamespace
for k, v in {"SECRET_KEY": "test-secret-key-must-be-long-enough-123", "STRIPE_SECRET_KEY": "sk_test_mock_stripe_key_12345",
             "STRIPE_WEBHOOK_SECRET": "whsec_mock_stripe_webhook_12345", "SKIP_REDIS_INIT": "true"}.items():
    os.environ.setdefault(k, v)
for k in ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_BASE_URL", "ANTHROPIC_API_KEY"):
    os.environ.pop(k, None)
sys.path.insert(0, "/home/user/wt/cite-rev/backend")
from app.services import provenance_service as head  # noqa: E402

src = subprocess.run(["git", "-C", "/home/user/wt/cite-rev", "show", "f6e79a50:backend/app/services/provenance_service.py"],
                     capture_output=True, text=True, check=True).stdout
base = types.ModuleType("base_provenance_service")
base.__dict__["__name__"] = "base_provenance_service"
exec(compile(src, "base_provenance_service.py", "exec"), base.__dict__)

SP = sys.argv[1]
BASE_URL = "https://www.sec.gov/Archives/edgar/data/0/0/doc.htm"
fq_total = fq_equal = fq_verified = 0
unverified = []
rows = rows_equal = 0
diffs = []
for path in sorted(glob.glob(os.path.join(SP, "eval-*", "eval_*.json"))):
    data = json.load(open(path))
    for r in data.get("results") or []:
        excerpt, sections = r.get("grounding_excerpt"), r.get("raw_sections")
        if not isinstance(excerpt, str) or not excerpt or not isinstance(sections, dict):
            continue
        norm = head.normalize_for_match(excerpt)
        fwd = sections.get("forward_signals")
        if isinstance(fwd, dict) and isinstance(fwd.get("quotes"), list):
            sb, sh = copy.deepcopy(sections), copy.deepcopy(sections)
            base._enrich_forward_quotes(sb, BASE_URL, norm)
            head._enrich_forward_quotes(sh, BASE_URL, norm)
            for qb, qh in zip(sb["forward_signals"]["quotes"], sh["forward_signals"]["quotes"]):
                if not (isinstance(qb, dict) and "evidence" in qb):
                    continue
                fq_total += 1
                fq_equal += qb == qh
                fq_verified += qh["evidence"]["verified"] is True
                if qh["evidence"]["verified"] is not True:
                    text = qh.get("quote") or qh.get("text")
                    unverified.append({"ticker": r.get("ticker"), "quote": text[:200],
                                       "whole": head.verify_whole_excerpt_in_text(text, norm),
                                       "inner_span": head.extract_quoted_span(text)[:60],
                                       "base_evidence": qb["evidence"], "head_evidence": qh["evidence"]})
        raw = {"schema_version": r.get("schema_version") or 2, "sections": sections}
        filing = SimpleNamespace(id=1, document_url=BASE_URL, sec_url=BASE_URL,
                                 content_cache=SimpleNamespace(filing_id=1, critical_excerpt=excerpt, markdown_content=None))
        ob = base.enrich_raw_summary(copy.deepcopy(raw), filing)
        oh = head.enrich_raw_summary(copy.deepcopy(raw), filing)
        rows += 1
        if json.dumps(ob, sort_keys=True, default=str) == json.dumps(oh, sort_keys=True, default=str):
            rows_equal += 1
        else:
            diffs.append(r.get("ticker"))
print(f"forward quotes: {fq_total} enriched; equal to base: {fq_equal}; verified at head: {fq_verified}")
for u in unverified:
    print("  UNVERIFIED", json.dumps(u, ensure_ascii=False)[:600])
print(f"full enrich_raw_summary rows: {rows}; byte-equal base vs head: {rows_equal}; differing: {diffs}")
