# Blind preference pack

Five companies (REGN, SNAP, JPM, COST, VRTX): the current production analysis against the proposed one (`claude-sonnet-5-5`, run `eval-v1`), A/B order drawn per company from a random seed kept in the key. Send each rater `index.html` and a copy of `scoring-sheet.csv` (rows for that rater only). Ratings are 1-5; preference is A, B or none.

The unblinding key was written outside the repository. Its SHA-256 is `430e51ade682f52a9dceec56e7de8706ffd9c6f92ae78b6ca28c8c38f25806d0`. Check the key against it before scoring, so the order cannot have been changed after the ratings arrived.

The two analyses differ visibly in length and style, so a rater who knows the current page may recognise it. Ask raters to judge what each analysis tells them and how far they trust it, not which one looks newer.

Scoring: count preferences for proposed vs current per company and overall; compare mean usefulness, trust and clarity; read every 'errors' entry against the sources and record whether it is a real error.
