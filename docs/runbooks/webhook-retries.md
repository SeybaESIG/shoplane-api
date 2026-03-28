# Runbook: Webhook Retries

## Background

Stripe retries webhook delivery up to 3 days if the endpoint does not return a `2xx` status. The application handles this safely:

- Each event is identified by its `stripe_event_id` stored in `PaymentLog.data`
- Before processing, the view checks whether a log entry with that event id already exists
- If it does, the event is acknowledged (`200`) and no state change is made

This means duplicate deliveries are harmless by design.

## Symptoms indicating a real problem

- A payment is stuck in `PENDING` despite the customer completing payment
- Sentry receives `IntegrityError` or `KeyError` from `webhook_views.py`
- Stripe dashboard shows the webhook endpoint returning `5xx` repeatedly

## Diagnosing a stuck payment

### 1. Check the payment status

```bash
docker compose exec web python manage.py shell -c "
from shoplane.models import Payment
p = Payment.objects.get(order__order_number='ORD-XXXXXXXXXXXX')
print(p.status, p.transaction_ref)
"
```

### 2. Review the payment log

```bash
docker compose exec web python manage.py shell -c "
from shoplane.models import Payment, PaymentLog
p = Payment.objects.get(order__order_number='ORD-XXXXXXXXXXXX')
for log in PaymentLog.objects.filter(payment=p).order_by('created_at'):
    print(log.event_type, log.message, log.data)
"
```

### 3. Check whether the event was received

Look for the Stripe event id in the logs:

```bash
docker compose logs web | grep evt_xxxxxxxxxxxx
```

## Manually replaying a webhook event

From the Stripe dashboard:
1. Go to **Developers → Webhooks → your endpoint**
2. Find the failed event under **Recent deliveries**
3. Click **Resend**

The application will process it if it has not been processed yet, or silently acknowledge it if it has.

## Manually updating a payment status (last resort)

Only do this if you have confirmed via the Stripe dashboard that the payment succeeded and the webhook cannot be replayed:

```bash
docker compose exec web python manage.py shell -c "
from django.db import transaction
from shoplane.models import Payment, PaymentLog, PaymentStatus, PaymentLogEventType
from django.utils import timezone

with transaction.atomic():
    p = Payment.objects.select_for_update().get(order__order_number='ORD-XXXXXXXXXXXX')
    p.status = PaymentStatus.PAID
    p.paid_at = timezone.now()
    p.save(update_fields=['status', 'paid_at'])
    PaymentLog.objects.create(
        payment=p,
        event_type=PaymentLogEventType.INFO,
        message='Status manually corrected after confirmed Stripe payment.',
        data={'manual_correction': True},
    )
print('done')
"
```

## Idempotency guarantee

The application stores `stripe_event_id` in `PaymentLog.data` and checks for its presence before processing. Even if Stripe delivers the same event 10 times concurrently, only one status update will be written. This is enforced by a `select_for_update` lock on the `Payment` row inside an atomic transaction.
