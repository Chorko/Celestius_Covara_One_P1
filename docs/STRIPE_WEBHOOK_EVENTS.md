# Stripe Webhook Events — Covara One

## Endpoint Configuration

| Setting | Value |
|---|---|
| **Endpoint URL** | `https://covara-backend.onrender.com/payouts/webhooks/http_gateway` |
| **Signing Secret** | `whsec_rC6aKQoVQ4cpS8KCkxjndjvLCuu2YiHM` — stored in Render env as `PAYOUT_PROVIDER_WEBHOOK_SECRET` |
| **Mode** | Test Mode |
| **Created** | 2026-04-12 |

---

## Registered Events (61 total)

### 💰 Payment Intents (7)
| Event | Purpose |
|---|---|
| `payment_intent.created` | Track when payment starts |
| `payment_intent.succeeded` | Premium payment confirmed |
| `payment_intent.payment_failed` | Premium payment declined |
| `payment_intent.canceled` | Payment canceled by user/system |
| `payment_intent.requires_action` | 3D Secure or additional auth needed |
| `payment_intent.processing` | Payment in progress (async methods) |
| `payment_intent.partially_funded` | Partial payment edge case |

### 🔋 Charges (6)
| Event | Purpose |
|---|---|
| `charge.succeeded` | Charge went through |
| `charge.failed` | Charge declined |
| `charge.captured` | Auth-then-capture flow completed |
| `charge.expired` | Uncaptured authorization expired |
| `charge.refunded` | Charge was refunded |
| `charge.refund.updated` | Refund status updated |

### 🔄 Refunds (3)
| Event | Purpose |
|---|---|
| `refund.created` | New refund initiated |
| `refund.updated` | Refund status changed |
| `refund.failed` | Refund could not be processed |

### ⚠️ Disputes & Fraud (7)
| Event | Purpose |
|---|---|
| `charge.dispute.created` | Customer disputed a charge (chargeback) |
| `charge.dispute.updated` | Dispute status changed |
| `charge.dispute.closed` | Dispute resolved |
| `charge.dispute.funds_reinstated` | Won dispute — funds returned |
| `charge.dispute.funds_withdrawn` | Lost dispute — funds taken |
| `radar.early_fraud_warning.created` | Stripe detected potential fraud |
| `radar.early_fraud_warning.updated` | Fraud warning status changed |

### 💸 Payouts (5)
| Event | Purpose |
|---|---|
| `payout.paid` | Claim payout delivered to worker's bank |
| `payout.failed` | Payout failed (bad account, insufficient balance) |
| `payout.canceled` | Payout was canceled |
| `payout.updated` | Payout status changed |
| `payout.reconciliation_completed` | Payout batch reconciled |

### 🔁 Subscriptions (6)
| Event | Purpose |
|---|---|
| `customer.subscription.created` | New insurance plan subscription |
| `customer.subscription.updated` | Plan changed (upgrade/downgrade) |
| `customer.subscription.deleted` | Subscription canceled |
| `customer.subscription.paused` | Subscription paused |
| `customer.subscription.resumed` | Subscription resumed |
| `customer.subscription.trial_will_end` | Trial ending — prompt for payment |

### 🧾 Invoices (7)
| Event | Purpose |
|---|---|
| `invoice.paid` | Invoice successfully paid |
| `invoice.payment_failed` | Invoice payment failed |
| `invoice.payment_action_required` | Invoice needs manual action (3DS) |
| `invoice.upcoming` | Invoice will be generated soon |
| `invoice.finalized` | Invoice finalized and ready |
| `invoice.voided` | Invoice voided |
| `invoice.marked_uncollectible` | Invoice written off as uncollectable |

### 👤 Customer (4)
| Event | Purpose |
|---|---|
| `customer.created` | New customer registered |
| `customer.updated` | Customer details changed |
| `customer.deleted` | Customer removed |
| `customer.source.expiring` | Saved payment method expiring soon |

### 💳 Payment Methods (4)
| Event | Purpose |
|---|---|
| `payment_method.attached` | Card/UPI linked to customer |
| `payment_method.detached` | Payment method removed |
| `payment_method.updated` | Payment method details changed |
| `payment_method.automatically_updated` | Card auto-updated by network (new expiry) |

### 🏦 Balance & Transfers (4)
| Event | Purpose |
|---|---|
| `balance.available` | Funds available for payout |
| `transfer.created` | Internal transfer initiated |
| `transfer.updated` | Transfer status changed |
| `transfer.reversed` | Transfer reversed |

### 🏗️ Account (1)
| Event | Purpose |
|---|---|
| `account.updated` | Stripe account status/capability changed |

### 🛒 Checkout Sessions (4)
| Event | Purpose |
|---|---|
| `checkout.session.completed` | User completed Stripe Checkout |
| `checkout.session.expired` | User abandoned Stripe Checkout |
| `checkout.session.async_payment_succeeded` | Delayed payment method succeeded |
| `checkout.session.async_payment_failed` | Delayed payment method failed |

### 🏦 Mandates (1)
| Event | Purpose |
|---|---|
| `mandate.updated` | Bank debit/UPI mandate status changed (India-specific) |

### 💾 Setup Intents (2)
| Event | Purpose |
|---|---|
| `setup_intent.succeeded` | Card saved for future auto-charge |
| `setup_intent.setup_failed` | Card save failed |

---

## Stripe API Keys

| Key | Location | Usage |
|---|---|---|
| `sk_test_...` (Secret) | Render env `PAYOUT_PROVIDER_API_KEY` | Backend API calls |
| `pk_test_...` (Publishable) | Frontend env `STRIPE_PUBLISHABLE_KEY` | Frontend checkout |
| `whsec_...` (Webhook) | Render env `PAYOUT_PROVIDER_WEBHOOK_SECRET` | Webhook signature verification |

## Test Cards

| Card Number | Scenario |
|---|---|
| `4242 4242 4242 4242` | Success |
| `4000 0000 0000 0002` | Decline |
| `4000 0000 0000 3220` | 3D Secure required |
| `4000 0000 0000 9995` | Insufficient funds |
| `4000 0000 0000 0069` | Expired card |

> Use any future expiry date and any 3-digit CVC for all test cards.

---

## Backend Webhook Handler

| Item | Value |
|---|---|
| Route | `POST /webhooks/{provider_key}` |
| File | `backend/app/routers/payouts.py` (line 184) |
| Signature verification | `backend/app/services/payout_provider.py` |
| Business logic | `backend/app/services/payout_workflow.py` |
