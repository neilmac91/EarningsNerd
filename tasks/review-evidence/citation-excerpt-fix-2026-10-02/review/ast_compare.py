"""Compare top-level function/constant ASTs between f6e79a50 and HEAD for the changed modules."""
import ast, subprocess, sys

REPO = "/home/user/wt/cite-rev"
BASE, HEAD = "f6e79a50", "a8a2d5a7"

def src(rev, path):
    return subprocess.run(["git", "-C", REPO, "show", f"{rev}:{path}"], capture_output=True, text=True, check=True).stdout

def defs(code):
    tree = ast.parse(code)
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[node.name] = ast.dump(node, include_attributes=False)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name):
                    out["=" + t.id] = ast.dump(node.value, include_attributes=False) if node.value else ""
    return out

for path in ["backend/app/services/provenance_service.py",
             "backend/app/services/ai/forward_quote_gate.py",
             "backend/app/services/copilot_service.py",
             "backend/app/services/ai/evidence_snap.py"]:
    a, b = defs(src(BASE, path)), defs(src(HEAD, path))
    changed = sorted(k for k in a.keys() & b.keys() if a[k] != b[k])
    print(f"## {path}\n  total base={len(a)} head={len(b)} unchanged={len([k for k in a.keys() & b.keys() if a[k]==b[k]])}")
    print("  changed:", changed)
    print("  removed:", sorted(a.keys() - b.keys()))
    print("  added:  ", sorted(b.keys() - a.keys()))

# Named checks
pb, ph = defs(src(BASE, "backend/app/services/provenance_service.py")), defs(src(HEAD, "backend/app/services/provenance_service.py"))
for name in ["build_evidence", "extract_quoted_span", "verify_excerpt_in_text", "normalize_for_match",
             "build_text_fragment_url", "project_risk_list", "_enrich_footnotes", "enrich_raw_summary",
             "=_QUOTED_RE", "=_MIN_VERIFIABLE_LEN", "=_TYPOGRAPHY_FOLDS"]:
    print(f"provenance {name}: identical={pb.get(name) == ph.get(name)} present={name in pb}")

# The moved helper: old forward_quote_gate._strip_wrapping_quotes vs new provenance_service.strip_wrapping_quotes
fb = ast.parse(src(BASE, "backend/app/services/ai/forward_quote_gate.py"))
old = next(n for n in fb.body if isinstance(n, ast.FunctionDef) and n.name == "_strip_wrapping_quotes")
nh = ast.parse(src(HEAD, "backend/app/services/provenance_service.py"))
new = next(n for n in nh.body if isinstance(n, ast.FunctionDef) and n.name == "strip_wrapping_quotes")
old.name = new.name = "X"
print("strip body identical (modulo name):", ast.dump(old) == ast.dump(new))
fbd = defs(src(BASE, "backend/app/services/ai/forward_quote_gate.py"))
print("_QUOTE_MARKS_OPEN identical:", fbd["=_QUOTE_MARKS_OPEN"] == ph["=_QUOTE_MARKS_OPEN"])
print("_QUOTE_MARKS_CLOSE identical:", fbd["=_QUOTE_MARKS_CLOSE"] == ph["=_QUOTE_MARKS_CLOSE"])
ns = {}
exec(compile(ast.Module(body=[n for n in fb.body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id.startswith("_QUOTE_MARKS")], type_ignores=[]), "x", "exec"), ns)
print("old OPEN codepoints:", [hex(ord(c)) for c in ns["_QUOTE_MARKS_OPEN"]], "CLOSE:", [hex(ord(c)) for c in ns["_QUOTE_MARKS_CLOSE"]])
