"""Apply one named mutation to the worktree (exact-string replace, must match exactly once)."""
import sys
B = "/home/user/wt/cite-rev/backend/app/services/"
P, C, G = B + "provenance_service.py", B + "copilot_service.py", B + "ai/forward_quote_gate.py"
M = {
 "M1a": [(C, "    strip_wrapping_quotes,\n    verify_whole_excerpt_in_text,\n)", "    strip_wrapping_quotes,\n    verify_excerpt_in_text,\n    verify_whole_excerpt_in_text,\n)"),
         (C, "verified = verify_whole_excerpt_in_text(excerpt, normalized_source) and not (", "verified = verify_excerpt_in_text(excerpt, normalized_source) and not (")],
 "M1b": [(C, "verified = verify_whole_excerpt_in_text(excerpt, normalized_source) and not (",
          "verified = getattr(__import__('app.services.provenance_service', fromlist=['x']), 'verify_' + 'excerpt_in_text')(excerpt, normalized_source) and verify_whole_excerpt_in_text(excerpt, normalized_source) is not None and not (")],
 "M2": [(P, "    needle = normalize_for_match(strip_wrapping_quotes(excerpt))\n", "    needle = strip_wrapping_quotes(excerpt)\n")],
 "M3": [(P, "    needle = normalize_for_match(strip_wrapping_quotes(excerpt))\n", "    needle = normalize_for_match(excerpt)\n")],
 "M4": [(P, "    needle = normalize_for_match(strip_wrapping_quotes(excerpt))\n", "    needle = normalize_for_match(extract_quoted_span(excerpt))\n")],
 "M5": [(P, "    needle = normalize_for_match(strip_wrapping_quotes(excerpt))\n    if len(needle) < _MIN_VERIFIABLE_LEN:", "    needle = normalize_for_match(strip_wrapping_quotes(excerpt))\n    if len(needle) < 0:")],
 "M6": [(P, "    needle = normalize_for_match(extract_quoted_span(excerpt))\n", "    needle = normalize_for_match(strip_wrapping_quotes(excerpt))\n")],
 "M7": [(C, "section_ref and any(mark in section_ref for mark in _SECTION_REF_QUOTE_MARKS)", "False")],
 "M7b": [(C, "section_ref and any(mark in section_ref for mark in _SECTION_REF_QUOTE_MARKS)",
          "cite.get('section_ref') and any(mark in cite.get('section_ref') for mark in _SECTION_REF_QUOTE_MARKS)")],
 "M7c": [(C, "_SECTION_REF_QUOTE_MARKS = '\"“”'", "_SECTION_REF_QUOTE_MARKS = '\"'")],
 "M8": [(P, "                text if whole else None, section_ref, base_url, normalized_source", "                text, section_ref, base_url, normalized_source")],
 "M9": [(C, "build_text_fragment_url(base_url, strip_wrapping_quotes(excerpt), source_span=True)", "build_text_fragment_url(base_url, excerpt)")],
 "M9b": [(C, "build_text_fragment_url(base_url, strip_wrapping_quotes(excerpt), source_span=True)", "build_text_fragment_url(base_url, excerpt, source_span=True)")],
 "M10": [(P, "_QUOTE_MARKS_OPEN = \"\\\"'“‘\"\n_QUOTE_MARKS_CLOSE = \"\\\"'”’\"", "_QUOTE_MARKS_OPEN = \"\\\"“\"\n_QUOTE_MARKS_CLOSE = \"\\\"”\"")],
 "M11": [(C, "            raise _UnpublishableAnswer(\"Unverified or ambiguous referenced citation\")", "            pass")],
 "M12": [(P, "    if not isinstance(excerpt, str) or not normalized_source:\n        return False\n    needle = normalize_for_match(strip_wrapping_quotes(excerpt))",
          "    if not isinstance(excerpt, str) or not normalized_source:\n        return False\n    needle = normalize_for_match(strip_wrapping_quotes(strip_wrapping_quotes(excerpt)))")],
}
name = sys.argv[1]
for path, old, new in M[name]:
    s = open(path, encoding="utf-8").read()
    assert s.count(old) == 1, (name, path, s.count(old), old)
    open(path, "w", encoding="utf-8").write(s.replace(old, new))
print("applied", name)
