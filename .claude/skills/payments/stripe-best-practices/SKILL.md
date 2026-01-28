---
name: stripe-best-practices
description: Best practices for Stripe API integrations
version: 1.0.0
author: stripe
source: https://github.com/stripe/ai/tree/main/skills/stripe-best-practices
---

# Stripe Best Practices

This skill provides guidance for building modern Stripe integrations, avoiding deprecated APIs, and following recommended patterns.

## Recommended APIs & Products

### Primary Payment APIs

**CheckoutSessions API** (Recommended)
- Stripe's primary API for modeling on-session payments
- Handles both one-time payments and subscriptions
- Supports Stripe-hosted or embedded checkout experiences

**PaymentIntents API**
- Use for off-session payments or custom checkout flows
- Required when you need full control over the payment UI
- Prioritize CheckoutSessions over PaymentIntents when possible

### Deprecated APIs (Avoid)

**Charges API** - Do not use
- Migrate existing integrations to CheckoutSessions or PaymentIntents
- Does not support modern payment methods or SCA requirements

**Card Element** - Legacy
- Migrate to Payment Element for new integrations
- Payment Element supports all payment methods dynamically

## Frontend Integration Patterns

### Web Integrations

**Stripe-hosted Checkout** (Simplest)
```javascript
// Redirect to Stripe-hosted checkout
const session = await stripe.checkout.sessions.create({
  mode: 'payment',
  line_items: [{ price: 'price_xxx', quantity: 1 }],
  success_url: 'https://example.com/success',
  cancel_url: 'https://example.com/cancel',
});
// Redirect customer to session.url
```

**Embedded Checkout** (Branded)
```javascript
// Embed checkout in your site
const checkout = await stripe.initEmbeddedCheckout({
  clientSecret: session.client_secret,
});
checkout.mount('#checkout');
```

**Payment Element** (Custom UI)
```javascript
// For advanced customization needs
const elements = stripe.elements({ clientSecret });
const paymentElement = elements.create('payment');
paymentElement.mount('#payment-element');
```

## Payment Method Handling

### Dynamic Payment Methods
Enable payment methods through the Stripe Dashboard rather than hardcoding:
- Allows A/B testing different payment methods
- Automatically shows relevant methods by geography
- No code changes needed to add new payment methods

### Saving Payment Methods
Use the **SetupIntents API** for saving payment methods:
```javascript
const setupIntent = await stripe.setupIntents.create({
  customer: 'cus_xxx',
  payment_method_types: ['card'],
});
```

## Subscriptions & Recurring Revenue

Use **Stripe Billing** with Checkout:
```javascript
const session = await stripe.checkout.sessions.create({
  mode: 'subscription',
  line_items: [{ price: 'price_monthly_xxx', quantity: 1 }],
  success_url: 'https://example.com/success',
  cancel_url: 'https://example.com/cancel',
});
```

## Platform & Marketplace (Connect)

For platforms connecting multiple parties:

**Direct Charges**
- Charge appears on connected account's statement
- Platform takes a fee via `application_fee_amount`

**Destination Charges**
- Charge appears on platform's statement
- Funds automatically transferred to connected account

Always use `on_behalf_of` parameter for proper liability shift:
```javascript
const paymentIntent = await stripe.paymentIntents.create({
  amount: 1000,
  currency: 'usd',
  on_behalf_of: 'acct_connected_xxx',
  transfer_data: { destination: 'acct_connected_xxx' },
});
```

## PCI Compliance

- Use Stripe.js and Elements to avoid handling raw card data
- If you must handle PANs, verify PCI compliance requirements
- Consider PAN migration process for transferring card data

## Pre-Launch Checklist

Before going live:
1. Review the [Go Live Checklist](https://stripe.com/docs/go-live-checklist)
2. Enable appropriate payment methods in Dashboard
3. Configure webhook endpoints for async events
4. Set up proper error handling and retry logic
5. Test with Stripe test mode thoroughly

## Common Mistakes to Avoid

1. **Using Charges API** - Always use PaymentIntents or Checkout
2. **Hardcoding payment methods** - Use dynamic payment methods
3. **Not handling webhooks** - Many events are asynchronous
4. **Missing idempotency keys** - Always include for retries
5. **Not validating webhook signatures** - Security requirement
