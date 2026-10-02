/** Read-only comparison of operator-supplied serving bindings and Stripe catalog readbacks.
 * No credentials, environment reads, network calls, checkout or catalog mutations.
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { PRO_PRICING } from '../app/pricing/prices.ts'

const record = (value) => value !== null && typeof value === 'object' && !Array.isArray(value)
const idMatches = (value, prefix) => typeof value === 'string' && new RegExp(`^${prefix}_[a-zA-Z0-9]+$`).test(value)

export function checkPricingAgreement(snapshot) {
  const errors = []
  const expected = { monthly: PRO_PRICING.monthly * 100, yearly: PRO_PRICING.yearly * 100 }
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

function main() {
  if (process.argv.length !== 3 || process.argv[2] === '--help') {
    console.log('Usage: npm run check:pricing -- /path/to/operator-readback.json')
    process.exitCode = process.argv[2] === '--help' ? 0 : 2
    return
  }
  try {
    const result = checkPricingAgreement(JSON.parse(readFileSync(process.argv[2], 'utf8')))
    console.log(JSON.stringify(result, null, 2))
    process.exitCode = result.ok ? 0 : 1
  } catch {
    console.error('Cannot read or parse the supplied JSON file. No agreement established.')
    process.exitCode = 2
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) main()
