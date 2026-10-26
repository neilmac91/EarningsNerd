# Export inspection (report §5, verification §9d)

**What was inspected.** The REGN annual analysis (FY2016–FY2025), downloaded through the real UI in
light and in dark theme by clicking Export PDF, Export Excel and Download chart as PNG. The run used
the local reproduction described in §1.4. The files are in [`../exports/`](../exports/).

**How.**
- The PDFs were opened with pdfplumber: text, glyph fonts and sizes, catalog keys and metadata.
- The workbooks were opened with openpyxl: cells, comments, number formats, fonts, images,
  properties, and a zip-part comparison across the two themes.
- The PNGs were opened with Pillow: size, background pixel against the panel tokens, and ink
  contrast. No OCR tool is installed here, so the words in a PNG were read from the rendered image
  and are marked "read by eye".

The script is in the [methods appendix](../methods.md#export-inspection-script). PARTIAL means the
artefact carries the item, but a reader looking for it would miss it or misread it.

| Artefact | Theme | Check | Result | Evidence |
|---|---|---|---|---|
| Excel | dark | company name | PARTIAL | Overview A7 'REGENERON PHARMACEUTICALS, INC. · Multi-Period Analysis' (EDGAR capitals) |
| Excel | light | company name | PARTIAL | Overview A7 'REGENERON PHARMACEUTICALS, INC. · Multi-Period Analysis' (EDGAR capitals) |
| Excel | dark | period range | PASS | Overview 'Periods: FY2016–FY2025 · 10 periods'; Metrics header FY2016..FY2025 |
| Excel | light | period range | PASS | Overview 'Periods: FY2016–FY2025 · 10 periods'; Metrics header FY2016..FY2025 |
| Excel | dark | notation legend | PASS | Overview A26–A29 states the counts and notes a/b; † appears only in that count line |
| Excel | light | notation legend | PASS | Overview A26–A29 states the counts and notes a/b; † appears only in that count line |
| Excel | dark | notation visible in the grid | FAIL | 14 review cells and 52 calculated cells both carry only a comment triangle; 0 cells show a mark, 0 review cells are styled: a reviewed figure looks like any calculated one |
| Excel | light | notation visible in the grid | FAIL | 14 review cells and 52 calculated cells both carry only a comment triangle; 0 cells show a mark, 0 review cells are styled: a reviewed figure looks like any calculated one |
| Excel | dark | sources | PASS | Sources & methods sheet, 1006 rows, Source URL and Accession columns |
| Excel | light | sources | PASS | Sources & methods sheet, 1006 rows, Source URL and Accession columns |
| Excel | dark | disclaimer | PASS | Overview A31 |
| Excel | light | disclaimer | PASS | Overview A31 |
| Excel | dark | branding | PASS | Logo image at Overview A1; 'EarningsNerd · earningsnerd.io' source line |
| Excel | light | branding | PASS | Logo image at Overview A1; 'EarningsNerd · earningsnerd.io' source line |
| Excel | dark | theme correctness | PASS | Parts that differ between the two downloads: ['docProps/core.xml', 'xl/worksheets/sheet1.xml'] (export timestamps only) |
| Excel | light | theme correctness | PASS | Parts that differ between the two downloads: ['docProps/core.xml', 'xl/worksheets/sheet1.xml'] (export timestamps only) |
| Excel | dark | legibility at print size | PARTIAL | font sizes {15.0: 1, 9.0: 12, 10.0: 46, 11.0: 13230}; Metrics freezes B2; no print area, fit-to-width or landscape setup: default orientation, fitToWidth=None; raw concept keys in column B |
| Excel | light | legibility at print size | PARTIAL | font sizes {15.0: 1, 9.0: 12, 10.0: 46, 11.0: 13230}; Metrics freezes B2; no print area, fit-to-width or landscape setup: default orientation, fitToWidth=None; raw concept keys in column B |
| Excel | dark | document metadata | FAIL | title=None, creator='openpyxl' |
| Excel | light | document metadata | FAIL | title=None, creator='openpyxl' |
| PDF | dark | company name | PARTIAL | Present on every page header, but as EDGAR capitals 'REGENERON PHARMACEUTICALS, INC.'; the web page and chart PNG print 'Regeneron Pharmaceuticals, Inc.' |
| PDF | light | company name | PARTIAL | Present on every page header, but as EDGAR capitals 'REGENERON PHARMACEUTICALS, INC.'; the web page and chart PNG print 'Regeneron Pharmaceuticals, Inc.' |
| PDF | dark | period range | PASS | 'FY2016–FY2025' 19x; title block 'REGN · Annual · FY2016–FY2025' |
| PDF | light | period range | PASS | 'FY2016–FY2025' 19x; title block 'REGN · Annual · FY2016–FY2025' |
| PDF | dark | notation legend | PARTIAL | Data notes a/b on p1; the letters/† key is on p4, not on the table's page p3; summary says '16 comparisons need review' where the web says 'carry note a' |
| PDF | light | notation legend | PARTIAL | Data notes a/b on p1; the letters/† key is on p4, not on the table's page p3; summary says '16 comparisons need review' where the web says 'carry note a' |
| PDF | dark | sources | PASS | Narrative sources list + Sources & methods p4–p45 (42 of 46 pages); legacy calculated sources [8]–[11],[13] carry no filing link and print raw keys ('operating_margin') |
| PDF | light | sources | PASS | Narrative sources list + Sources & methods p4–p45 (42 of 46 pages); legacy calculated sources [8]–[11],[13] carry no filing link and print raw keys ('operating_margin') |
| PDF | dark | disclaimer | PASS | About this document, p45 |
| PDF | light | disclaimer | PASS | About this document, p45 |
| PDF | dark | branding | PASS | Logo lockup in the p1 header; 'EarningsNerd · earningsnerd.io' footer on every page |
| PDF | light | branding | PASS | Logo lockup in the p1 header; 'EarningsNerd · earningsnerd.io' footer on every page |
| PDF | dark | theme correctness | PASS | Text identical across themes once timestamps are masked: the PDF is always the light print layout |
| PDF | light | theme correctness | PASS | Text identical across themes once timestamps are masked: the PDF is always the light print layout |
| PDF | dark | legibility at print size | PARTIAL | A4/A4-landscape; smallest text 7.2pt (note letters), body 8.5pt; 46 pages; glyphs set in a fallback font: {'†': 52, '→': 2, '◦': 614, ' ': 614}; timestamps print as raw ISO with microseconds |
| PDF | light | legibility at print size | PARTIAL | A4/A4-landscape; smallest text 7.2pt (note letters), body 8.5pt; 46 pages; glyphs set in a fallback font: {'†': 52, '→': 2, '◦': 614, ' ': 614}; timestamps print as raw ISO with microseconds |
| PDF | dark | document metadata / tagging | FAIL | metadata {'Producer': 'WeasyPrint 70.0'}; tagged=False |
| PDF | light | document metadata / tagging | FAIL | metadata {'Producer': 'WeasyPrint 70.0'}; tagged=False |
| PNG (margins) | dark | company name | PASS | Title 'Regeneron Pharmaceuticals, Inc.' (read by eye) |
| PNG (margins) | light | company name | PASS | Title 'Regeneron Pharmaceuticals, Inc.' (read by eye) |
| PNG (margins) | dark | period range | FAIL | No fiscal-year range in the image; only '16–'25 ticks; the range is in the file name alone |
| PNG (margins) | light | period range | FAIL | No fiscal-year range in the image; only '16–'25 ticks; the range is in the file name alone |
| PNG (margins) | dark | notation legend | PARTIAL | 'Note a: …' with its figures, 'Includes figures calculated by EarningsNerd'; the hollow-ring marker for a noted point is not explained; letters are grey, not the review colour (read by eye) |
| PNG (margins) | light | notation legend | PARTIAL | 'Note a: …' with its figures, 'Includes figures calculated by EarningsNerd'; the hollow-ring marker for a noted point is not explained; letters are grey, not the review colour (read by eye) |
| PNG (margins) | dark | sources | PASS | 'Source: SEC filings via EarningsNerd · data as of Oct 24, 2026' (read by eye) |
| PNG (margins) | light | sources | PASS | 'Source: SEC filings via EarningsNerd · data as of Oct 24, 2026' (read by eye) |
| PNG (margins) | dark | disclaimer | PASS | 'Research only. Not investment advice…' + earningsnerd.io/terms (read by eye) |
| PNG (margins) | light | disclaimer | PASS | 'Research only. Not investment advice…' + earningsnerd.io/terms (read by eye) |
| PNG (margins) | dark | branding | PASS | EN mark + wordmark bottom right (read by eye) |
| PNG (margins) | light | branding | PASS | EN mark + wordmark bottom right (read by eye) |
| PNG (margins) | dark | theme correctness | PASS | background (31, 41, 55) = panel token (31, 41, 55); footer ink contrast 5.8:1. The image follows the page theme while the PDF and workbook stay light |
| PNG (margins) | light | theme correctness | PASS | background (251, 250, 246) = panel token (251, 250, 246); footer ink contrast 9.9:1. The image follows the page theme while the PDF and workbook stay light |
| PNG (margins) | dark | legibility at print size | PARTIAL | 1004x962px, no DPI tag; at 6.5in wide it prints at 154dpi, where the ~20px axis text is ~9.3pt |
| PNG (margins) | light | legibility at print size | PARTIAL | 1004x962px, no DPI tag; at 6.5in wide it prints at 154dpi, where the ~20px axis text is ~9.3pt |
| PNG (revenue) | dark | company name | PASS | Title 'Regeneron Pharmaceuticals, Inc.' (read by eye) |
| PNG (revenue) | light | company name | PASS | Title 'Regeneron Pharmaceuticals, Inc.' (read by eye) |
| PNG (revenue) | dark | period range | FAIL | No fiscal-year range in the image; only '16–'25 ticks; the range is in the file name alone |
| PNG (revenue) | light | period range | FAIL | No fiscal-year range in the image; only '16–'25 ticks; the range is in the file name alone |
| PNG (revenue) | dark | notation legend | PASS | No noted figure on this chart, so no legend is needed (read by eye) |
| PNG (revenue) | light | notation legend | PASS | No noted figure on this chart, so no legend is needed (read by eye) |
| PNG (revenue) | dark | sources | PASS | 'Source: SEC filings via EarningsNerd · data as of Oct 24, 2026' (read by eye) |
| PNG (revenue) | light | sources | PASS | 'Source: SEC filings via EarningsNerd · data as of Oct 24, 2026' (read by eye) |
| PNG (revenue) | dark | disclaimer | PASS | 'Research only. Not investment advice…' + earningsnerd.io/terms (read by eye) |
| PNG (revenue) | light | disclaimer | PASS | 'Research only. Not investment advice…' + earningsnerd.io/terms (read by eye) |
| PNG (revenue) | dark | branding | PASS | EN mark + wordmark bottom right (read by eye) |
| PNG (revenue) | light | branding | PASS | EN mark + wordmark bottom right (read by eye) |
| PNG (revenue) | dark | theme correctness | PASS | background (31, 41, 55) = panel token (31, 41, 55); footer ink contrast 5.8:1. The image follows the page theme while the PDF and workbook stay light |
| PNG (revenue) | light | theme correctness | PASS | background (251, 250, 246) = panel token (251, 250, 246); footer ink contrast 9.9:1. The image follows the page theme while the PDF and workbook stay light |
| PNG (revenue) | dark | legibility at print size | PARTIAL | 1004x818px, no DPI tag; at 6.5in wide it prints at 154dpi, where the ~20px axis text is ~9.3pt |
| PNG (revenue) | light | legibility at print size | PARTIAL | 1004x818px, no DPI tag; at 6.5in wide it prints at 154dpi, where the ~20px axis text is ~9.3pt |

**Totals:** 70 checks: 44 pass, 16 partial, 10 fail.
