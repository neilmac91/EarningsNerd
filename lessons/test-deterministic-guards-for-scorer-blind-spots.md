# Add a dedicated deterministic guard for every error class invisible to existing scorers

Date: 2026-07-01   Area: test

**Context**: Wave 3's 20-F prose looked clean on every aggregate; only drilling into per-run gate_failures surfaced one NVO (DKK) run rendering figures as bare `$` — a ~7x distortion. Root cause was not extraction (DKK was in the XBRL grounding); the model intermittently (~1/3 of NVO runs) ignored the currency directive. `numeric_precision` stayed 1.0 because it matches the VALUE and is currency-agnostic. Added `score_currency_consistency`, WARN-gated (not hard) because the slip is intermittent and a hard gate would flake CI.

**Rule**: (1) When a class of error is invisible to the deterministic scorers (currency label, units, sign-on-derived-metrics), add a dedicated deterministic guard — don't rely on the LLM judge as the only catcher. (2) Aggregate metrics + "no regression" can hide a rare, severe per-item defect; for go/no-go on a user-facing launch, inspect the worst per-item cases, not just the means.

**Evidence**: NVO (Novo Nordisk / DKK) rendered "$309,064M" where the source is DKK; recall +0.012 with no visible regression; `score_currency_consistency` added (US$/NT$/HK$ excluded via letter-lookbehind; CNY renders "RMB", TWD renders "NT$").
