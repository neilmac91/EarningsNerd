# Hold a count-up's frames in the unit its value ends in; a frame that changes unit is wider than the value the layout was sized for

Date: 2026-10-25   Area: frontend

**Context**: The KPI strip's cards count each value up from zero (`hooks/useCountUp`), whose contract asks for a
format "so width never jitters", with ``(v) => `$${v.toFixed(1)}B` `` as its example. The strip passed compact notation
instead, which picks a unit per frame: on its way to "CHF 22.8B" the value showed "CHF 999.9M", a glyph wider than the
final value. E197's fix sizes the strip's columns from its widest final value (138.2px for "CA$968.0M†"), so a wider
frame would have run past its card for most of the 600ms tween at 360px, where the final value fits; sizing for the
widest frame instead would have put every strip whose values pass a unit boundary in one column. Formatting every
frame in the final value's unit (`compactCurrencyCountUp`: "CHF 0.0B" … "CHF 22.8B") makes the final value the widest
frame, so the layout measures one string, and the last frame stays the compact text the page printed before.

**Rule**: When a layout is sized from a value that animates in, format every frame in the unit the value ends in, so
no frame is wider than the final value, and keep the last frame byte-identical to the static format. Count from zero:
a tween from a larger old value passes frames wider than the new one ("$999.9M" between $1.0B and $80.0M), so key the
element by its value and let a change remount it. Check the frames across currencies, signs and unit boundaries
(999.96B prints "1.0T"), not one value.

**Evidence**: E197's pull request: `frontend/lib/format.ts` `compactCurrencyCountUp`, `frontend/features/analysis/components/KpiStrip.tsx`
and `frontend/tests/unit/kpi-strip-layout.spec.tsx` ("counts up in the unit its value ends in", which formats 201
frames for each of six currencies and nine final values, and "remounts a card whose value changes"). Gated for the KPI strip by that spec; other count-ups are
review-checked.
