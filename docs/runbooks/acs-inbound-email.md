# ACS Inbound Email — DEPRECATED

**Status:** the original v5 design assumed Azure Communication Services
would publish `Microsoft.Communication.EmailReceived` events to Event
Grid. That event type does NOT exist in ACS — ACS email is outbound-only
(delivery + engagement report events are the only email events it
publishes).

**Active implementation:** see
[`docs/runbooks/msgraph-inbound-email.md`](./msgraph-inbound-email.md).

The ACS webhook at `POST /webhooks/acs/email-received` remains deployed
but is dormant — nothing will ever POST to it. Left in place for future
rollback or reuse if Microsoft ships ACS inbound email in a future
preview.
