# When an error class is invisible to deterministic scorers (currency/units), add a dedicated guard; inspect worst per-item cases

**Area:** ai-evals · **Date:** 2026-07-01

Wave 3's 20-F prose looked clean on every aggregate (recall +0.012, no regression, judge dims flat).
Only drilling into the judge's recorded per-run gate_failures surfaced it: one NVO (Novo Nordisk / DKK)
run rendered its figures as bare `$` ("$309,064M" where the source is DKK) — a ~7x distortion. Root
cause was NOT extraction (DKK was captured in the XBRL grounding) — the model *intermittently* (~1/3
of NVO runs) ignored the "never render non-USD as `$`" directive. Critically, `numeric_precision`
stayed 1.0 the whole time because it matches the VALUE and is **currency-agnostic** — it never checks
the unit — so the deterministic gate literally cannot see a currency mislabel; only the judge/eyeball
can. **Rule:** (1) when a class of error is invisible to the deterministic scorers (currency label,
units, sign-on-derived-metrics), add a dedicated deterministic guard — don't rely on the LLM judge as
the only catcher. (2) Aggregate metrics + "no regression" can hide a rare, severe per-item defect; for
go/no-go on a user-facing launch, inspect the worst per-item cases, not just the means. Added
`score_currency_consistency` (bare-`$` on non-USD filers; US$/NT$/HK$ excluded via letter-lookbehind;
native counted via a currency-alias map since CNY renders "RMB", TWD renders "NT$"). WARN-gated, not
hard — the slip is intermittent and a hard gate would flake CI until the underlying model slip is fixed.
