/** Read-only comparisons of the Pro offer with what checkout charges: an operator's readback of the
 * serving bindings and Stripe catalog (checkPricingAgreement), or the serving backend's public charge
 * report, GET /api/subscriptions/prices (checkServingCharge). Each reads one supplied JSON file: no
 * credentials, environment reads, network calls, checkout or catalog mutations.
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { PRO_PRICING } from '../app/pricing/prices.ts'

const record = (value) => value !== null && typeof value === 'object' && !Array.isArray(value)
const idMatches = (value, prefix) => typeof value === 'string' && new RegExp(`^${prefix}_[a-zA-Z0-9]+$`).test(value)

const expectedCents = () => ({ monthly: Math.round(PRO_PRICING.monthly * 100), yearly: Math.round(PRO_PRICING.yearly * 100) })

export function checkPricingAgreement(snapshot) {
  const errors = []
  const expected = expectedCents()
  const result = () => ({
    ok: errors.length === 0,
    scope: 'Supplied snapshot only; not live checkout verification or activation approval.',
    expected: { currency: 'usd', monthly_cents: expected.monthly, yearly_cents: expected.yearly },
    errors,
  })
  if (!record(snapshot) || !record(snapshot.bindings) || !record(snapshot.prices) || !record(snapshot.product)) {
    errors.push('Supply bindings, prices and product objects from one operator readback.')
    return result()
  }
  const { bindings, prices, product } = snapshot
  const ids = { monthly: bindings.STRIPE_PRICE_MONTHLY_ID, yearly: bindings.STRIPE_PRICE_YEARLY_ID }
  for (const cycle of ['monthly', 'yearly']) {
    if (!idMatches(ids[cycle], 'price')) errors.push(`${cycle}: effective serving price binding is missing or malformed.`)
  }
  if (ids.monthly === ids.yearly) errors.push('Monthly and yearly bindings must select different prices.')
  if (!idMatches(bindings.product_id, 'prod')) errors.push('The intended approved product ID is missing or malformed.')
  if (product.object !== 'product' || product.id !== bindings.product_id || !idMatches(product.id, 'prod')) {
    errors.push('Product readback must match the intended approved product ID.')
  }
  if (product.active !== true || product.livemode !== true || product.deleted === true) {
    errors.push('Product must be active in live mode.')
  }
  for (const cycle of ['monthly', 'yearly']) {
    const price = prices[cycle]
    if (!record(price)) {
      errors.push(`${cycle}: a Stripe Price readback is required.`)
      continue
    }
    if (price.object !== 'price' || price.id !== ids[cycle] || !idMatches(price.id, 'price')) {
      errors.push(`${cycle}: Price readback does not match the effective serving binding.`)
    }
    if (price.product !== bindings.product_id) errors.push(`${cycle}: Price belongs to another product; supply an unexpanded product ID.`)
    if (price.active !== true || price.livemode !== true) errors.push(`${cycle}: Price must be active in live mode.`)
    if (price.currency !== 'usd') errors.push(`${cycle}: Price currency must be USD.`)
    if (price.type !== 'recurring' || !record(price.recurring) || price.recurring.interval !== (cycle === 'monthly' ? 'month' : 'year') || price.recurring.interval_count !== 1 || price.recurring.usage_type !== 'licensed') {
      errors.push(`${cycle}: Price must recur once per ${cycle === 'monthly' ? 'month' : 'year'} with licensed usage.`)
    }
    if (price.billing_scheme !== 'per_unit' || price.custom_unit_amount !== null || price.transform_quantity !== null) {
      errors.push(`${cycle}: Price must use a fixed per-unit amount without quantity transformation.`)
    }
    if (!Number.isSafeInteger(price.unit_amount) || price.unit_amount !== expected[cycle]) {
      errors.push(`${cycle}: Price amount disagrees with PRO_PRICING.`)
    }
    if (price.unit_amount_decimal != null && (typeof price.unit_amount_decimal !== 'string' || !/^\d+(?:\.0{1,12})?$/.test(price.unit_amount_decimal) || Number(price.unit_amount_decimal) !== expected[cycle])) {
      errors.push(`${cycle}: Decimal amount disagrees with the whole-cent offer.`)
    }
  }
  return result()
}

// The report's problem codes (backend/app/services/billing_serving_prices.py). "unavailable" leaves
// the check without evidence; the others mean checkout has no fixed charge for that cycle.
const PROBLEMS = new Set(['unconfigured', 'unavailable', 'inactive', 'test_mode', 'not_fixed_recurring'])
const INTERVALS = { monthly: 'month', yearly: 'year' }

/** Compare the serving backend's charge report with PRO_PRICING; by default they must agree. With
 * `publishing`, the check before a page goes live, it passes while checkout charges no more than the
 * page shows (backend first; docs/PRICING_OFFER.md). `usable` is false when the report is no evidence.
 */
export function checkServingCharge(report, { publishing = false } = {}) {
  const errors = []
  const notes = []
  let usable = record(report)
  const expected = expectedCents()
  for (const cycle of ['monthly', 'yearly']) {
    const charge = record(report) ? report[cycle] : undefined
    const interval = INTERVALS[cycle]
    if (!record(charge) || (charge.problem !== undefined && !PROBLEMS.has(charge.problem))) {
      usable = false
      errors.push(`${cycle}: the report carries no readable charge.`)
    } else if (charge.problem !== undefined) {
      if (charge.problem === 'unavailable') usable = false
      errors.push(`${cycle}: checkout has no fixed charge (${charge.problem}).`)
    } else if (!Number.isSafeInteger(charge.amount_cents) || charge.amount_cents < 0) {
      usable = false
      errors.push(`${cycle}: the report's amount is not a whole number of cents.`)
    } else if (charge.currency !== 'usd' || charge.interval !== interval || charge.interval_count !== 1) {
      errors.push(`${cycle}: checkout must charge in USD once per ${interval}.`)
    } else if (charge.amount_cents > expected[cycle]) {
      errors.push(`${cycle}: checkout charges ${charge.amount_cents} cents, more than the ${expected[cycle]} the page shows.`)
    } else if (charge.amount_cents < expected[cycle]) {
      const lower = `${cycle}: checkout charges ${charge.amount_cents} cents, less than the ${expected[cycle]} the page shows.`
      if (publishing) notes.push(lower)
      else errors.push(lower)
    }
  }
  return {
    ok: errors.length === 0,
    usable,
    scope: publishing
      ? 'Before publishing: checkout must charge no more than this page shows, so a lower price is bound on the backend first.'
      : 'The serving charge report only; not a catalog readback, live checkout verification or activation approval.',
    expected: { currency: 'usd', monthly_cents: expected.monthly, yearly_cents: expected.yearly },
    errors,
    notes,
  }
}

const USAGE = [
  'Usage: npm run check:pricing -- /path/to/operator-readback.json',
  '       npm run check:pricing -- --serving [--publishing] /path/to/serving-prices.json',
].join('\n')

function parseArgs(args) {
  const file = (arg) => typeof arg === 'string' && arg !== '' && !arg.startsWith('--')
  if (args.length === 1 && file(args[0])) return { file: args[0], check: checkPricingAgreement }
  if (args.length === 2 && args[0] === '--serving' && file(args[1])) return { file: args[1], check: (input) => checkServingCharge(input) }
  if (args.length === 3 && args[0] === '--serving' && args[1] === '--publishing' && file(args[2])) {
    return { file: args[2], check: (input) => checkServingCharge(input, { publishing: true }) }
  }
  return null
}

function main() {
  const args = process.argv.slice(2)
  const call = parseArgs(args)
  if (!call) {
    console.log(USAGE)
    process.exitCode = args.length === 1 && args[0] === '--help' ? 0 : 2
    return
  }
  try {
    const result = call.check(JSON.parse(readFileSync(call.file, 'utf8')))
    console.log(JSON.stringify(result, null, 2))
    process.exitCode = result.usable === false ? 2 : result.ok ? 0 : 1
  } catch {
    console.error('Cannot read or parse the supplied JSON file. No agreement established.')
    process.exitCode = 2
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) main()
