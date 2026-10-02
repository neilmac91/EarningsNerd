"""(a) Differential fuzz: base forward_quote_gate._strip_wrapping_quotes/_needle vs head.
(b) Adversarial probes of verify_whole_excerpt_in_text: displayed text must be contiguous."""
import ast, random, subprocess, sys
sys.path.insert(0, "/home/user/wt/cite-rev/backend")
from app.services import provenance_service as prov
from app.services.ai import forward_quote_gate as gate
from app.services.summary_sections import _strip_inline_markdown

base_src = subprocess.run(["git", "-C", "/home/user/wt/cite-rev", "show",
                           "f6e79a50:backend/app/services/ai/forward_quote_gate.py"],
                          capture_output=True, text=True, check=True).stdout
tree = ast.parse(base_src)
keep = [n for n in tree.body if (isinstance(n, ast.Assign) and n.targets[0].id.startswith("_QUOTE_MARKS"))
        or (isinstance(n, ast.FunctionDef) and n.name in ("_strip_wrapping_quotes", "_needle"))]
ns = {"normalize_for_match": prov.normalize_for_match, "_strip_inline_markdown": _strip_inline_markdown}
exec(compile(ast.Module(body=keep, type_ignores=[]), "base_gate", "exec"), ns)
old_strip, old_needle = ns["_strip_wrapping_quotes"], ns["_needle"]

alphabet = list("ab ") + list("\"'“”‘’„‟«»") + [" ", "\n", "\t", "*", "_", "…", ".", "[1]"]
rng = random.Random(1029)
n = 0
for _ in range(200_000):
    s = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 9)))
    assert old_strip(s) == prov.strip_wrapping_quotes(s), repr(s)
    assert old_needle(s) == gate._needle(s), repr(s)
    n += 1
print(f"(a) strip/_needle differential: {n} random strings, 0 differences")

SRC_RAW = ("ITEM 7. MANAGEMENT’S DISCUSSION AND ANALYSIS\n"
           "Revenue increased to $391.0 billion in fiscal 2024, driven by strong iPhone and Services demand. "
           "The Company’s “Tier 1” suppliers remain concentrated in Asia. "
           "Gross margin was 46.2 percent. Operating expenses rose modestly.")
SRC = prov.normalize_for_match(SRC_RAW)
K = "Revenue increased to $391.0 billion in fiscal 2024"
cases = {
    # displayed text NOT contiguous -> must be False
    "prefix + quoted real":            ('Invented words and "' + K + '"', False),
    "quoted real + suffix":            ('"' + K + '" and then invented words', False),
    "partial wrap open only":          ('"' + K + ' plus invented tail', False),
    "nested wrap, invented between":   ('"Made up "' + K + '""', False),
    "double pair":                     ('""' + K + '""', False),
    "mismatched pair + invented":      ('“' + K + '’ said nobody', False),
    "ellipsis elision ...":            ("Revenue increased to ... in fiscal 2024, driven by strong iPhone", False),
    "ellipsis elision …":              ("Revenue increased to $391.0 billion … driven by strong iPhone", False),
    "[n] marker inside":               ("Revenue increased to $391.0 billion [1] in fiscal 2024", False),
    "two real spans stitched":         ("Revenue increased to $391.0 billion. Gross margin was 46.2 percent.", False),
    "stitched with inner quotes":      ('"Revenue increased to $391.0 billion" "Gross margin was 46.2 percent"', False),
    "long invented excerpt":           (K + " " + "x" * 50_000, False),
    "below floor":                     ("Gross margin was 46.2 pe", None),
    "only quote marks":                ('""', False),
    "whitespace only":                 ("   ", False),
    # displayed text contiguous (modulo shared normalization) -> True
    "plain":                           (K, True),
    "straight wrap":                   ('"' + K + '"', True),
    "curly wrap":                      ("“" + K + "”", True),
    "single wrap":                     ("'" + K + "'", True),
    "mismatched wrap “…'":             ("“" + K + "'", True),
    "NBSP + newline":                  ("Revenue increased to $391.0\nbillion in fiscal 2024", True),
    "curly vs straight inner":         ("The Company's \"Tier 1\" suppliers remain concentrated", True),
    "em dash folded":                  ("Management’s Discussion and Analysis Revenue", None),
}
bad = []
for name, (ex, want) in cases.items():
    got = prov.verify_whole_excerpt_in_text(ex, SRC)
    # oracle: whole displayed text minus ONE optional wrapping pair, normalized, contiguous and >= floor
    oracle_needle = prov.normalize_for_match(prov.strip_wrapping_quotes(ex))
    oracle = len(oracle_needle) >= prov._MIN_VERIFIABLE_LEN and oracle_needle in SRC
    old = prov.verify_excerpt_in_text(ex, SRC)
    flag = "" if (want is None or got == want) else "  <-- UNEXPECTED"
    if want is not None and got != want:
        bad.append(name)
    print(f"  {name:32s} whole={got!s:5s} prefix_tolerant(old)={old!s:5s} oracle={oracle!s:5s}{flag}")
print("(b) unexpected:", bad or "none")

# (c) property: whole=True implies the stripped displayed text is a normalized substring of SRC
rng = random.Random(7)
words = SRC_RAW.split()
viol = 0
for _ in range(50_000):
    i = rng.randrange(len(words)); j = min(len(words), i + rng.randint(1, 12))
    piece = " ".join(words[i:j])
    mut = rng.choice([lambda s: s, lambda s: '"' + s + '"', lambda s: "x " + s,
                      lambda s: s + " y", lambda s: '"' + s + '" z', lambda s: 'z "' + s + '"',
                      lambda s: s.replace(" ", " … ", 1), lambda s: "“" + s + "’"])
    ex = mut(piece)
    if prov.verify_whole_excerpt_in_text(ex, SRC):
        disp = prov.normalize_for_match(ex)
        core = prov.normalize_for_match(prov.strip_wrapping_quotes(ex))
        # Everything displayed except at most one leading and one trailing quote mark must be in SRC.
        if core not in SRC or len(disp) - len(core) > 2:
            viol += 1
print("(c) property violations over 50k random excerpts:", viol)
