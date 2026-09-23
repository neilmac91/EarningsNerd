# Exporter guide correction

The exact-head review of `135182ac` identified a documentation P1: [discussion_r4079920147](https://github.com/neilmac91/EarningsNerd/pull/940#discussion_r4079920147).

First refutation: the exporter writes only compact.txt, reader.txt, source-view.json and manifest.json; its manifest enumerates the three content files. A helper named render_review exists, but the exporter does not publish its output.

Second refutation: the six retained H29 artifact manifests independently contain the same four files. No persisted review.txt is available through the documented CLI. The finding stands.

The guide now directs reviewers to the actual reader and structural JSON, identifies compact.txt as an invariant rather than sufficient table-review input, and describes the manifest accurately. No new generated artifact or source-review input is introduced. Documentation needs link/content checking, not an additional backend test.
