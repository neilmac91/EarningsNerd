"""Shared branded PDF shell — fonts, palette, page chrome — for every EarningsNerd PDF export.

Both `export_service.generate_pdf_html` (filing summary) and `generate_analysis_pdf_html`
(Multi-Period Analysis) delegate their document chrome here so the two exports can never drift
apart (owner decision D4, export-overhaul plan). The shell owns:

- ``@font-face`` for the vendored brand fonts (Inter variable, its roman and its italic, and Geist
  Mono, all OFL: files under ``app/assets/fonts/`` with absolute ``file://`` URLs, never
  cwd-relative, since agent/CI/Cloud Run working directories differ), plus Inter's symbols face, a family
  of its own, for the marks the latin subsets lack (SOURCES.txt records each file's source).
- ``@page`` chrome: A4 portrait default with the running document title, the
  "EarningsNerd · earningsnerd.io" footer and "Page X of Y" counters, plus the
  ``metrics-landscape`` NAMED PAGE — a section carrying ``class="metrics-landscape"`` starts on
  a new A4 LANDSCAPE page (the fix for wide quarterly metric grids being clipped in portrait).
- The page-1 masthead: inline sage mark (font-independent SVG — the wordmark-lockup SVG needs
  Inter resolution inside the SVG and must NOT be inlined) + HTML wordmark + document kind.
- The design-token PALETTE (DESIGN_SYSTEM.md) — PDFs must never use off-token grays or the
  banned legacy blue.
- Reader-table manners (D-041, applying D-030): headers in the tertiary ink on no fill, hairline
  rows, no cell grid; quotes on a neutral hairline. A link rests in its line's ink with a quiet
  underline, as the page's prose links do at rest: print has no pointer to turn it sage, and its
  text can carry an index ("Source filing 1"). Sage colours only the wordmark's "Nerd".

- The document's own metadata: ``<html lang="en">``, the title as ``<title>``, EarningsNerd as author
  and generator and an optional subject as the description, which WeasyPrint writes as the PDF's
  /Title, /Author, /Creator, /Subject and /Lang; and ``PDF_OPTIONS``, the ``write_pdf`` options every
  export passes (a tagged PDF, with a structure tree a screen reader can follow).

The visual contract is pinned by tests/unit/test_export_service.py (shell assertions + a real
WeasyPrint render checking page orientation), the mark by tests/unit/test_pdf_mark_geometry.py
and every colour, its token and its contrast by tests/unit/test_export_palette_parity.py.
"""
from html import escape
from pathlib import Path

_ASSETS = Path(__file__).resolve().parent.parent / "assets"

# The options every export hands WeasyPrint's write_pdf: a tagged PDF (/StructTreeRoot, /MarkInfo), so a
# screen reader reads the headings, lists and tables in order. Not PDF/UA (pdf_variant="pdf/ua-1"): no
# validator runs in CI to back that claim.
PDF_OPTIONS = {"pdf_tags": True}

# Design tokens (DESIGN.md's frontmatter, which designSnapshotParity holds equal to
# frontend/tailwind.config.js) — single source for PDF and workbook colour. Each key is one token's
# role: test_export_palette_parity.py maps it to that token by name.
PALETTE = {
    "brand": "#4F7A63",
    "brand_strong": "#3C6650",
    "brand_weak": "#ECF2EE",
    "brand_border": "#CFE0D6",
    "background": "#F4F3EE",
    "panel": "#FBFAF6",
    "ink": "#1A1A17",
    "ink_secondary": "#374151",
    "ink_tertiary": "#636A77",
    "border": "#E5E7EB",
}

# The "EN" monogram (public/assets/earningsnerd-mark-sage.svg) — fixed sage fill, no <text>,
# so it renders identically regardless of available fonts.
_MARK_PATHS = (
    '<g transform="translate(0,-14.8)">'
    '<path d="M2.8 28L26.2 28Q29 28 29 30.8L29 36.2Q29 39 26.2 39L12.9 39Q11.5 39 11.5 40.4'
    "L11.5 42.1Q11.5 43.5 12.9 43.5L23.2 43.5Q26 43.5 26 46.3L26 51.7Q26 54.5 23.2 54.5"
    "L12.9 54.5Q11.5 54.5 11.5 55.9L11.5 57.6Q11.5 59 12.9 59L26.2 59Q29 59 29 61.8L29 67.2"
    'Q29 70 26.2 70L2.8 70Q0 70 0 67.2L0 30.8Q0 28 2.8 28Z" fill="{fill}"></path>'
    '<g transform="translate(0.92,6.98) scale(0.9193)">'
    '<path d="M36.98 84.42L49.76 58.87Q50.65 57.08 51.54 58.87L65.21 86.2Q66.11 88 68.13 88'
    "L68.57 88Q70.59 88 71.49 86.2L93.87 41.43Q95.66 37.86 92.09 36.07L84.21 32.13"
    "Q80.64 30.34 78.85 33.92L69.24 53.13Q68.35 54.92 67.46 53.13L53.79 25.8Q52.89 24 50.87 24"
    'L50.43 24Q48.41 24 47.51 25.8L18.2 84.42Q16.41 88 20.41 88L31.19 88Q35.19 88 36.98 84.42Z"'
    ' fill="{fill}"></path>'
    '<path d="M101.76 42.95L101.05 12.49Q100.96 8.49 97.7 10.81L72.91 28.53Q69.65 30.85 '
    '73.23 32.64L98.27 45.16Q101.85 46.95 101.76 42.95Z" fill="{fill}"></path>'
    "</g></g>"
)
_MARK_VIEWBOX = "0 0 94.6 73.2"
_MARK_ASPECT = 94.6 / 73.2


def mark_svg(height_px: int = 34, fill: str = PALETTE["brand_strong"]) -> str:
    """The inline EN monogram at a given height (width follows the mark's aspect ratio)."""
    width_px = round(height_px * _MARK_ASPECT)
    return (
        f'<svg viewBox="{_MARK_VIEWBOX}" width="{width_px}" height="{height_px}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="EarningsNerd">'
        + _MARK_PATHS.replace("{fill}", fill)
        + "</svg>"
    )


def font_face_css() -> str:
    inter = (_ASSETS / "fonts" / "Inter-Variable-latin.woff2").as_uri()
    # WeasyPrint never slants a face it lacks, so the wordmark's "Nerd" and a quote print italic only
    # from Inter's own italic (the same 4.001 build, latin subset, as the roman).
    inter_italic = (_ASSETS / "fonts" / "Inter-Variable-Italic-latin.woff2").as_uri()
    # The marks the latin subsets lack (dagger and double dagger, the four arrows, the white bullet, "almost
    # equal to" for a convenience translation the 20-F and 6-K prompts ask for, the won and rupee signs a
    # summary figure may carry), cut from the same 4.001 build: without it they printed in DejaVu
    # (SOURCES.txt records the cut). It is a family of its own, after Inter in every stack: WeasyPrint keys
    # an embedded font by family, style and weight, never by file, so declared as a second 'Inter Var'
    # normal face it merged with the latin one, and a page drew "₩" as the latin "A" (the gid both share).
    inter_symbols = (_ASSETS / "fonts" / "Inter-Variable-symbols.woff2").as_uri()
    geist_mono = (_ASSETS / "fonts" / "GeistMono-latin.woff2").as_uri()
    return f"""
@font-face {{
  font-family: 'Inter Var';
  src: url('{inter}') format('woff2');
  font-weight: 100 900;
  font-style: normal;
}}
@font-face {{
  font-family: 'Inter Var Symbols';
  src: url('{inter_symbols}') format('woff2');
  font-weight: 100 900;
  font-style: normal;
  unicode-range: U+2020-2021, U+20A9, U+20B9, U+2190-2193, U+2248, U+25E6;
}}
@font-face {{
  font-family: 'Inter Var';
  src: url('{inter_italic}') format('woff2');
  font-weight: 100 900;
  font-style: italic;
}}
@font-face {{
  font-family: 'Geist Mono';
  src: url('{geist_mono}') format('woff2');
  font-weight: 100 900;
  font-style: normal;
}}
"""


def shell_css() -> str:
    """Page chrome + shared typography. Body builders add their own layout via extra_css.

    Every stack names Inter's symbols face after Inter, and the data face's stack names both before the
    system's monospace, so a mark the latin subsets lack (a dagger after a figure, "≈") prints in a vendored
    face, never DejaVu; 'DejaVu Sans' stays the sans stack's declared last resort."""
    p = PALETTE
    return f"""
@page {{
  size: A4;
  margin: 20mm 16mm 18mm 16mm;
  @top-left {{
    content: string(doc-title);
    font-family: 'Inter Var', 'Inter Var Symbols', 'DejaVu Sans', sans-serif;
    font-size: 8pt;
    color: {p["ink_tertiary"]};
  }}
  @bottom-left {{
    content: "EarningsNerd · earningsnerd.io";
    font-family: 'Inter Var', 'Inter Var Symbols', 'DejaVu Sans', sans-serif;
    font-size: 8pt;
    color: {p["ink_tertiary"]};
  }}
  @bottom-right {{
    content: "Page " counter(page) " of " counter(pages);
    font-family: 'Geist Mono', 'Inter Var', 'Inter Var Symbols', monospace;
    font-size: 8pt;
    color: {p["ink_tertiary"]};
  }}
}}
@page :first {{
  @top-left {{ content: none; }}
}}
/* Wide financial grids: a section with this class starts on a NEW LANDSCAPE page. */
@page metrics-landscape {{
  size: A4 landscape;
  margin: 16mm 14mm;
  @top-left {{
    content: string(doc-title);
    font-family: 'Inter Var', 'Inter Var Symbols', 'DejaVu Sans', sans-serif;
    font-size: 8pt;
    color: {p["ink_tertiary"]};
  }}
  @bottom-left {{
    content: "EarningsNerd · earningsnerd.io";
    font-family: 'Inter Var', 'Inter Var Symbols', 'DejaVu Sans', sans-serif;
    font-size: 8pt;
    color: {p["ink_tertiary"]};
  }}
  @bottom-right {{
    content: "Page " counter(page) " of " counter(pages);
    font-family: 'Geist Mono', 'Inter Var', 'Inter Var Symbols', monospace;
    font-size: 8pt;
    color: {p["ink_tertiary"]};
  }}
}}
section.metrics-landscape {{ page: metrics-landscape; break-before: page; }}

body {{
  font-family: 'Inter Var', 'Inter Var Symbols', 'DejaVu Sans', sans-serif;
  color: {p["ink"]};
  font-size: 10.5pt;
  line-height: 1.55;
}}
h1 {{ string-set: doc-title content(); }}
h1, h2, h3 {{ font-family: 'Inter Var', 'Inter Var Symbols', 'DejaVu Sans', sans-serif; font-weight: 600; color: {p["ink"]}; }}
h1 {{ font-size: 19pt; margin: 14px 0 4px 0; }}
h2 {{
  font-size: 13pt;
  margin: 22px 0 8px 0;
  padding-bottom: 4px;
  border-bottom: 2px solid {p["brand_border"]};
}}
h3 {{ font-size: 11pt; margin: 14px 0 6px 0; }}
p {{ margin: 0 0 9px 0; color: {p["ink_secondary"]}; }}

.masthead {{
  background: {p["brand_weak"]};
  border-bottom: 3px solid {p["brand"]};
  border-radius: 4px 4px 0 0;
  padding: 12px 16px;
  display: flex;
  align-items: center;
}}
.masthead .wordmark {{
  font-family: 'Inter Var', 'Inter Var Symbols', 'DejaVu Sans', sans-serif;
  font-size: 17pt;
  font-weight: 650;
  letter-spacing: -0.02em;
  color: {p["ink"]};
  margin-left: 10px;
}}
.masthead .wordmark em {{ font-style: italic; color: {p["brand_strong"]}; }}
.masthead .doc-kind {{
  margin-left: auto;
  font-size: 8pt;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: {p["ink_tertiary"]};
  text-align: right;
}}
.meta {{
  color: {p["ink_tertiary"]};
  font-size: 9pt;
  margin: 0 0 16px 0;
}}
.meta .data {{ font-family: 'Geist Mono', 'Inter Var', 'Inter Var Symbols', monospace; }}

/* With no outer frame, a table's last hairline would sit on the next block ("Profitability" under
   Financial Highlights): it keeps a list's spacing below it. */
table {{ border-collapse: collapse; width: 100%; border: 0; margin: 0 0 10px; }}
thead {{ display: table-header-group; }}
tr {{ break-inside: avoid; }}
th {{
  color: {p["ink_tertiary"]};
  font-weight: 600;
  font-size: 8pt;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  text-align: left;
  padding: 5px 7px;
  border: 0;
  border-bottom: 1px solid {p["border"]};
}}
td {{
  padding: 4px 7px;
  border: 0;
  border-bottom: 1px solid {p["border"]};
  font-size: 9pt;
  color: {p["ink_secondary"]};
}}
td.num, .data {{
  font-family: 'Geist Mono', 'Inter Var', 'Inter Var Symbols', monospace;
  font-variant-numeric: tabular-nums;
}}
td.num, th.num {{ text-align: right; }}
/* A figure keeps to one line, as the page's figure cells do ("+14.4 ppts" beside a long takeaway). */
td.num {{ white-space: nowrap; }}

blockquote {{
  margin: 10px 0;
  padding-left: 14px;
  border-left: 2px solid {p["border"]};
  color: {p["ink_secondary"]};
  font-style: italic;
}}
blockquote cite {{
  display: block;
  margin-top: 2px;
  font-size: 9pt;
  font-style: normal;
  color: {p["ink_tertiary"]};
}}
ul, ol {{ margin: 0 0 10px 0; padding-left: 20px; color: {p["ink_secondary"]}; }}
/* A nested list takes the disc too: WeasyPrint's default circle (U+25E6) is in no latin subset. */
ul ul {{ list-style-type: disc; }}
li {{ margin: 3px 0; }}
.footnote {{ color: {p["ink_tertiary"]}; font-size: 8.5pt; }}
.ref {{ color: {p["ink_tertiary"]}; }}
/* Every link rests in its line's ink with a quiet underline in the tertiary ink (D-041): print has
   no pointer to turn it sage. The rule also keeps WeasyPrint's default link blue off the page. */
a {{
  color: inherit;
  text-decoration: underline;
  text-decoration-color: {p["ink_tertiary"]};
}}
"""


def render_branded_pdf(
    *,
    title: str,
    doc_kind: str,
    meta_html: str,
    body_html: str,
    extra_css: str = "",
    subject: str = "",
) -> str:
    """Full HTML document: masthead band + title + meta line + body inside the branded shell.

    ``title`` must already be HTML-escaped by the caller (it interpolates into markup);
    ``meta_html``/``body_html`` are trusted pre-rendered fragments from the body builders. ``subject``
    is plain text (escaped here): the PDF's /Subject, through the description.
    """
    description = f'\n<meta name="description" content="{escape(subject, quote=True)}">' if subject else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<meta name="author" content="EarningsNerd">
<meta name="generator" content="EarningsNerd">{description}
<style>
{font_face_css()}
{shell_css()}
{extra_css}
</style>
</head>
<body>
  <div class="masthead">
    {mark_svg(30)}
    <span class="wordmark">Earnings<em>Nerd</em></span>
    <span class="doc-kind">{doc_kind}</span>
  </div>
  <h1>{title}</h1>
  <div class="meta">{meta_html}</div>
  {body_html}
</body>
</html>"""
