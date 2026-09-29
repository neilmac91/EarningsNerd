# FIGS reconciliation-direction withholding — local implementation

The retained run-0 middle sentence assigns one deduction direction to all five
adjusted-EBITDA components. The application now withholds that complete sentence
only when its finite three-sentence envelope and bounded native operands match.
The first and third sentences remain exact, independent model-authored prose.
The only new text is: “This summary could not independently verify the stated
directions of the adjusted EBITDA reconciliation.” No financial reconstruction,
source-absence finding, or source-assertion authority is emitted.

## Scope and evidence

Implementation began on reviewed local tax head `9ffd444c`, then incorporated the
reviewed leap-period correction `90c52bc14f8aa9e9e86cd70c0afda737b64ef6f4` at merge
`ef9e63abd5f2b134fba31f6fa30631865bf8181c`. Its docs-only evidence
head `a13b46a85f5d873ad67f19733c721983c86fffcb` was merged at `b76ae383`.
The final reviewed correction is `e237f11a`, restored after proofs at
`c7d4bc7e3e0c58e0815e532ed194172999abc9a3`. Publication and subsequent verified-main/JPM
reconciliation belong to the root task. No external calls or publication occurred.

The new [reconciliation_operands.py](../../backend/app/services/edgar/reconciliation_operands.py) selector reuses the parsed
`TableUnitIndex` document and reviewed tax namespace/duration validators. It owns
one finite table layout, complete local introduction/footnotes, column geometry,
USD issuer anchor, periods and bounded integer operands. Unknown or ambiguous
source stays unavailable. An independent numeric-cell count prevents adjacent
subcolumns from inventing an amount; separate currency and parentheses remain
supported. The same invariant checks each bounded cell lexeme before whitespace
compaction, rejecting `8 502` while preserving `$ 8,502`. Complete local scope
accounts for all wrapper text, row companions, tail revenue/margin cells and bare
text between the preceding Table of Contents and following Free Cash Flow heading.
The heading's following text remains outside this finite scope. Tail values are
checked only for bounded lexical structure; no financial assertion is derived.
The selected anchor's start must equal the reviewed calendar-quarter helper,
replacing the former 75–105 day heuristic. All annual and tax helpers are unchanged
relative to the reviewed tax base. No broader parsing framework or generation path was introduced.

[reconciliation_directions.py](../../backend/app/services/ai/reconciliation_directions.py) matches the entire authored envelope, follows
actual canonical/camel truthy fallback, abstains for populated conflicts and
recovered sections, and removes the raw companion alias only on successful binding.
The existing service hooks run it before evidence repair and on complete previews.
Form context defaults to abstention and is supplied only with native source context,
preserving legacy two-argument callbacks. Recursive removal of the reserved audit
key prevents model metadata from reaching private audit or judge channels. The
first and third sentences are separately retained in the private preservation audit;
no new renderer authority marker certifies their financial content.

The native source is reused byte-for-byte from the existing tax fixture, SHA256
`513789f462c784068a92153e69ccfd46a1f1029b4e449f284de34e463b3c2272` (1,331,149 characters).
The report SHA256 is `deaa1b52c85bbab1bbcd19b7e55ab483b58ec465d6523272931cbd67e6c7f80b`.
The historical generation source was ten characters longer with a different hash;
this is native-source consumer replay, not byte-identical historical replay.
The retained 70-row grammar census selects row 12 only. Actual native consumer
replay covers rows 12 and 13 only; row 13's reconciliation prose stays unchanged.
Global hypothetical/withdrawn source wrappers may select only the capability
limitation; source assertion status remains explicitly unestablished.

All 87 assessment controls and adverse prototype history remain retained by the
operator. The CI fixture freezes those inputs; 42 additional integration/review
controls make 129 reconciliation cases in the existing complete-interpretation
consumer gate. The renamed gate preserves its pre-existing tax test body, including
both leap-year directions. All other existing tests and original source fixtures
are unchanged. Held positive-reconstruction proposals and formal E7 decisions are
unchanged; no stored-summary regeneration, prompt/model/flag/cache/baseline change
or source-reference/blind-directory access occurred.

## Verification and corrections

Focused source/consumer coverage passed 241 tests before the four numeric-layout
controls were added. The numeric-layout and legacy-preview correction passed all
10 selected checks. The actual armed evidence-repair control confirms admission
has already occurred before repair, while the original unsupported tax impact
retains its own separate boundary.

Final pinned gate at `c7d4bc7e3e0c58e0815e532ed194172999abc9a3`, using the validation
venv and `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` with fresh Python caches:

- Ruff 0.16.9: `All checks passed!`
- Bandit 1.9.4, `bandit -r app -ll`: exit 0, no medium/high severity findings.
- pytest 9.1.1: **4,161 passed, 39 skipped, 2 deselected, 40 warnings in 207.15s**,
  exit 0. Post-summary asyncio/Yahoo cleanup logging diagnostics remain in the log.

Two earlier green full gates remain preserved: `ef9e63ab` had 4,130 passed in
199.17s; `b76ae383` had 4,137 passed in 203.48s. Both had 39 skipped and 2 deselected.
Subsequent review findings were reproduced and repaired before the final gate.

The first full gate at `52306a03` is preserved: Ruff/Bandit passed; pytest had
4,117 passed and five failures because an unconditional new preview keyword broke
legacy callbacks. Runtime now supplies that keyword only with native context; the
existing failing tests were not edited. A separate source review reproduced
adjacent `8` and `502` cells being joined into `8,502` despite intact headers,
bridges and tagged net income. Both refutations upheld the issue; the new local
numeric-token guard and three adverse cases plus a symbol-format positive control
close it without changing the annual amount owner. Invalid/reversed DEI starts
also had two concrete counterexamples; reusing complete duration validation closes
that gap in the same consumer gate. Independent reviews subsequently reproduced
unknown local qualifiers in row 5, trailing rows, label gaps and inter-node tails,
as well as early/late tagged anchor dates still inside the old day range. The new
local closure and exact calendar comparison each have independent refutations
and a separate committed proof. The initial new focused run caught a fixture-helper
prefix collision with the existing period-caption case; exact dispatch corrected
that helper, and all 129 reconciliation cases then passed. That failed log remains
preserved.

## Committed fault/restoration proofs

Each fault is committed, measured, restored byte-for-byte and committed again.
The nine distinct invariants reuse the same consumer gate, with no second test
owner. Exact logs, commands and full hashes are retained in operator receipts.

| Rule | Committed fault | Committed restoration |
| --- | --- | --- |
| whole_authored_scope | `b9b1cae8`: 1 failed, 1 passed, 153 deselected | `b0561e62`: 2 passed, 153 deselected |
| source_namespace | `81293f23`: 2 failed, 1 passed, 152 deselected | `c6b3e16b`: 3 passed, 152 deselected |
| caption_geometry | `1fcbdfef`: 2 failed, 1 passed, 152 deselected | `4edcacd3`: 3 passed, 152 deselected |
| qualified_context_and_unit | `be9b4bd4`: 4 failed, 1 passed, 150 deselected | `ffb7aa55`: 5 passed, 150 deselected |
| model_metadata | `ffcdd984`: 2 failed, 153 deselected | `bb364b16`: 2 passed, 153 deselected |
| independent_sentence_preservation | `1a040bd7`: 2 failed, 153 deselected | `52306a03`: 2 passed, 153 deselected |
| independent_numeric_token | `4954924b`: 3 failed, 2 passed, 154 deselected | `346cbae9`: 5 passed, 154 deselected |
| same numeric-token rule, pre-compaction continuation | `f71f0fbc`: 5 failed, 7 passed, 156 deselected | `8ad5fc19`: 12 passed, 156 deselected |
| complete_local_scope | `9d43a074`: 17 failed, 3 passed, 172 deselected | `a4384a0d`: 20 passed, 172 deselected |
| exact_quarter_period | `dcbdac5f`: 4 failed, 2 passed, 186 deselected | `c7d4bc7e`: 6 passed, 186 deselected |

The runtime after every proof matches the intended correction commit. The final
merge audit verifies 11 protected source/tax/annual/pipeline/render/eval/Copilot
anchors against the reviewed tax base and preserves all 11 pre-existing integration
function bodies after removing only the new dispatch. All 283 other existing test/fixture
files, four frozen original inputs and 52 assessment artifacts are unchanged. Locked
tests are unchanged.

Offline real service replay verifies final, complete preview, shared Markdown,
PDF HTML and CSV, plus an actual PDF export. The consumer gate additionally exercises
incomplete preview, recovered sections, raw aliases, exact sentence preservation,
actual judge invocation and Copilot context privacy. Provider-return stubs replace
network generation; source selection and application/rendering consumers are real.
No semantic judgment or 70-document consumer replay is claimed.

Root and the independent reviewer cleared the immutable `e237f11a` correction;
`c7d4bc7e` restores exactly those backend bytes. The independent receipt is
`quality/figs-reconciliation-final-independent/correction-e237f11a/README.md` in
the operator evidence tree. Publication and verified tax/JPM main integration
remain separate root-owned steps.

Operator receipts are under
`outputs/overnight-2026-09-28/quality/figs-reconciliation-successor/implementation/`:
`closed-full-gate.json`, `closed-scope-audit.json`, `closed-replay/native-replay.json`,
all fault/restoration logs and the preserved initial failed gate. The assessment
and every adverse prototype remain in the parent directory.
