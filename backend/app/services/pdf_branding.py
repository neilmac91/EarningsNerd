"""Shared branded PDF shell — fonts, palette, page chrome — for every EarningsNerd PDF export.

Both `export_service.generate_pdf_html` (filing summary) and `generate_analysis_pdf_html`
(Multi-Period Analysis) delegate their document chrome here so the two exports can never drift
apart (owner decision D4, export-overhaul plan). The shell owns:

- ``@font-face`` for the vendored brand fonts (Inter variable + Geist Mono, OFL — files under
  ``app/assets/fonts/`` with absolute ``file://`` URLs, never cwd-relative: agent/CI/Cloud Run
  working directories differ).
- ``@page`` chrome: A4 portrait default with the running document title, the
  "EarningsNerd · earningsnerd.io" footer and "Page X of Y" counters, plus the
  ``metrics-landscape`` NAMED PAGE — a section carrying ``class="metrics-landscape"`` starts on
  a new A4 LANDSCAPE page (the fix for wide quarterly metric grids being clipped in portrait).
- The page-1 masthead: inline sage mark (font-independent SVG — the wordmark-lockup SVG needs
  Inter resolution inside the SVG and must NOT be inlined) + HTML wordmark + document kind.
- The design-token PALETTE (DESIGN_SYSTEM.md) — PDFs must never use off-token grays or the
  banned legacy blue.

The visual contract is pinned by tests/unit/test_export_service.py (shell assertions + a real
WeasyPrint render checking page orientation).
"""
from pathlib import Path

_ASSETS = Path(__file__).resolve().parent.parent / "assets"

# Design tokens (frontend/tailwind.config.js / DESIGN_SYSTEM.md) — single source for PDF color.
PALETTE = {
    "brand": "#4F7A63",
    "brand_strong": "#3C6650",
    "brand_weak": "#ECF2EE",
    "brand_border": "#CFE0D6",
    "panel": "#FBFAF6",
    "ink": "#1A1A17",
    "ink_secondary": "#374151",
    "ink_tertiary": "#6B7280",
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
    geist_mono = (_ASSETS / "fonts" / "GeistMono-latin.woff2").as_uri()
    return f"""
@font-face {{
  font-family: 'Inter Var';
  src: url('{inter}') format('woff2');
  font-weight: 100 900;
  font-style: normal;
}}
@font-face {{
  font-family: 'Geist Mono';
  src: url('{geist_mono}') format('woff2');
  font-weight: 100 900;
  font-style: normal;
}}
"""


def shell_css() -> str:
    """Page chrome + shared typography. Body builders add their own layout via extra_css."""
    p = PALETTE
    return f"""
@page {{
  size: A4;
  margin: 20mm 16mm 18mm 16mm;
  @top-left {{
    content: string(doc-title);
    font-family: 'Inter Var', 'DejaVu Sans', sans-serif;
    font-size: 8pt;
    color: {p["ink_tertiary"]};
  }}
  @bottom-left {{
    content: "EarningsNerd · earningsnerd.io";
    font-family: 'Inter Var', 'DejaVu Sans', sans-serif;
    font-size: 8pt;
    color: {p["ink_tertiary"]};
  }}
  @bottom-right {{
    content: "Page " counter(page) " of " counter(pages);
    font-family: 'Geist Mono', monospace;
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
    font-family: 'Inter Var', 'DejaVu Sans', sans-serif;
    font-size: 8pt;
    color: {p["ink_tertiary"]};
  }}
  @bottom-left {{
    content: "EarningsNerd · earningsnerd.io";
    font-family: 'Inter Var', 'DejaVu Sans', sans-serif;
    font-size: 8pt;
    color: {p["ink_tertiary"]};
  }}
  @bottom-right {{
    content: "Page " counter(page) " of " counter(pages);
    font-family: 'Geist Mono', monospace;
    font-size: 8pt;
    color: {p["ink_tertiary"]};
  }}
}}
section.metrics-landscape {{ page: metrics-landscape; break-before: page; }}

body {{
  font-family: 'Inter Var', 'DejaVu Sans', sans-serif;
  color: {p["ink"]};
  font-size: 10.5pt;
  line-height: 1.55;
}}
h1 {{ string-set: doc-title content(); }}
h1, h2, h3 {{ font-family: 'Inter Var', 'DejaVu Sans', sans-serif; font-weight: 600; color: {p["ink"]}; }}
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
  font-family: 'Inter Var', 'DejaVu Sans', sans-serif;
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
.meta .data {{ font-family: 'Geist Mono', monospace; }}

table {{ border-collapse: collapse; width: 100%; }}
thead {{ display: table-header-group; }}
tr {{ break-inside: avoid; }}
th {{
  background: {p["brand_weak"]};
  color: {p["brand_strong"]};
  font-weight: 600;
  font-size: 8pt;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  text-align: left;
  padding: 5px 7px;
  border: 1px solid {p["border"]};
}}
td {{
  padding: 4px 7px;
  border: 1px solid {p["border"]};
  font-size: 9pt;
  color: {p["ink_secondary"]};
}}
table {{ border: 1px solid {p["brand_border"]}; }}
td.num, .data {{
  font-family: 'Geist Mono', monospace;
  font-variant-numeric: tabular-nums;
}}
td.num, th.num {{ text-align: right; }}

blockquote {{
  margin: 10px 0;
  padding-left: 14px;
  border-left: 3px solid {p["brand_border"]};
  color: {p["ink_secondary"]};
  font-style: italic;
}}
ul, ol {{ margin: 0 0 10px 0; padding-left: 20px; color: {p["ink_secondary"]}; }}
li {{ margin: 3px 0; }}
.footnote {{ color: {p["ink_tertiary"]}; font-size: 8.5pt; }}
.ref {{ color: {p["ink_tertiary"]}; }}
"""


def render_branded_pdf(
    *,
    title: str,
    doc_kind: str,
    meta_html: str,
    body_html: str,
    extra_css: str = "",
) -> str:
    """Full HTML document: masthead band + title + meta line + body inside the branded shell.

    ``title`` must already be HTML-escaped by the caller (it interpolates into markup);
    ``meta_html``/``body_html`` are trusted pre-rendered fragments from the body builders.
    """
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
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
