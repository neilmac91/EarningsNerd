# H01 native member inspection receipt

This local inspection is bound to frozen H01 submission `1aade6920a2dcda891c91c4ff774d311be6d98963e497e305c0f729a00f8d972`. It changes no source, manifest, disposition, coverage status, or E7 admission and made no network or model call.

## Exact extracted content spans

| Member | Frozen byte span | Bytes | SHA-256 |
|---|---:|---:|---|
| cat-20251231.xsd | 6656530:6780060 | 123530 | `0bf8551978e74336e7af7e23d703d12dd0fe0d5a7946bd1194f8166555833a04` |
| cat-20251231_cal.xml | 6780242:6960292 | 180050 | `c129cd63f6b4d6ae2d57ff0e0578e4b79d6caf4a07c865155434db9c46d37800` |
| cat-20251231_def.xml | 6960473:7796599 | 836126 | `49a195143eba6fee8dccedac56364f137227789910c79fa8d758c3cdd1c16926` |
| cat-20251231_lab.xml | 7796775:9307966 | 1511191 | `662b41de95124522acb104ff32d61f6962c641193fbd5edb0e51427b34cd2ecf` |
| cat-20251231_pre.xml | 9308149:10453976 | 1145827 | `92c62f40349bf34343f586eec7811ca92b8f5d2d386f23038413f2471387c98c` |
| Show.js | 21508135:21509107 | 972 | `27c7269045a14fe3b54c79ba7305bdd22e76f300fdf66f154f280243cb186024` |
| report.css | 21509224:21511875 | 2651 | `43aa2149480dc772a4626a39458734289ca384fcd07e4323f40a1e4fecf43cba` |
| FilingSummary.xml | 21512005:21597431 | 85426 | `7de70c54a0214f14254c09bc48151b4a165437b263b405dc2401d2f2c80e3da0` |
| MetaLinks.json | 21597560:23559981 | 1962421 | `39696d5294230041c43925af0a9e162eb0f6e7f9202beb48b293833b050c69ce` |
| cat-20251231_htm.xml | 25727464:33197432 | 7469968 | `090b49ce71c48fa359f7add6e0c1ba2e19d0dcd84ace92e3f7a18ccc42fe3274` |

Every extracted byte sequence rehashes to the document-map content hash.

## Native syntax and roots

| Member | Parsed root | Result |
|---|---|---|
| cat-20251231.xsd | http://www.w3.org/2001/XMLSchema}schema | valid |
| cat-20251231_cal.xml | http://www.xbrl.org/2003/linkbase}linkbase | valid |
| cat-20251231_def.xml | http://www.xbrl.org/2003/linkbase}linkbase | valid |
| cat-20251231_lab.xml | http://www.xbrl.org/2003/linkbase}linkbase | valid |
| cat-20251231_pre.xml | http://www.xbrl.org/2003/linkbase}linkbase | valid |
| FilingSummary.xml | FilingSummary | valid |
| MetaLinks.json | dict | valid |
| cat-20251231_htm.xml | http://www.xbrl.org/2003/instance}xbrl | valid |

The seven XML members are well formed under a streaming Expat parser with parameter entities disabled and an external-entity handler that fails closed. None contains a DOCTYPE or ENTITY declaration, and no external entity was requested. This is syntax validation only: referenced remote taxonomies were not fetched, and schema/linkbase validity is not established. `MetaLinks.json` parses as an object with top-level keys `instance`, `std_ref`, and `version`; this does not validate an SEC-specific schema. No malformed target input was found.

`FilingSummary.xml` contains 139 `<Report>` elements: 138 concrete `R1.htm`–`R138.htm` report references for `cat-20251231.htm`, plus one non-file `All Reports` book entry. The 138 concrete names exactly match the 138 `structured_rendering_review_required` source-map members. Categories are Cover 2, Statements 7, Notes 28, Policies 1, Tables 21, Details 79. The XBRL instance root contains 1,095 contexts, 11 units, and one schema reference; these counts are structural observations, not correctness or completeness.

## `Show.js` and `report.css`

`Show.js` is 972 bytes (`27c726…024`) and passes `node --check`. Its complete content is SEC Edgar renderer interaction code: it shows/hides authoritative-reference tables and toggles adjacent report-detail DIVs. `report.css` is 2,651 bytes (`43aa21…cba`); complete inspection found balanced rules and a `.report .text .more { display: none; }` rule plus styles for authoritative-reference tables and hide controls. Neither file embeds issuer facts or narrative.

They are native-renderer packaging, but their hiding behavior affects filing readers. All 138 generated reports reference both files, contain `Show.showAR` and `Show.toggleNext` calls, and contain initially hidden elements. Preserve both assets when reproducing the native reader. Any semantic review of a generated report must inspect hidden/toggled DOM content; visual absence is not evidence that content is absent.

## Unresolved limits

- XML imports, schema validity, linkbase semantics, MetaLinks schema validity, fact correctness, and report semantics remain unverified.
- This inspection does not disposition the 138 generated reports or prove hidden-content review.
- It makes no source-completeness, modality-completeness, coverage, or admission claim.

The full machine receipt remains in operator retention: SHA-256 `e6ff79ca308da90e154ad0efa3d3b9c059719d87fb8a04c07d52b2b1e22c8079`; extraction receipt SHA-256 `da567f7eaf4f723be1f19d266e946831a290c35100a041756f15a5b39db51a34`. This compact source-only inspection record contains no cloud observations.
