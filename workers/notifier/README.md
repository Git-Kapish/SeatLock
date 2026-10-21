# TicketRush Notifier Worker

Asynchronous SQS event consumer daemon and background hold sweeper for TicketRush.

## Responsibilities
1. Consumes `booking.confirmed` events from SQS queue (`ticketrush-booking-events`).
2. Renders and dispatches order confirmation emails via SMTP (MailHog) / SES.
3. Implements exponential backoff retry and forwards failed events to DLQ (`ticketrush-booking-events-dlq`).
4. Reconciles expired holds in the database every 30 seconds and releases associated Redis lock keys.
