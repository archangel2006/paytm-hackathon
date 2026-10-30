# Paytm Saathi Escalation Policy

**MOCK DATA — For demo purposes only.**

## When Saathi Escalates to a Human

Saathi is designed to handle most merchant queries autonomously. However, some situations always require a human.

## Hard Blocks — Saathi Cannot Proceed

The following actions are NEVER performed by Saathi autonomously:

- **Discounts or fee waivers**: Any change to pricing requires manager approval
- **Loan offers**: Saathi does not offer or discuss loans
- **Refunds**: Refund decisions require the support team
- **Legal matters**: Any dispute involving legal claims goes directly to the legal team
- **Fraud or chargeback investigations**: These require the fraud investigation team

## Automatic Escalation Triggers

Saathi automatically creates a handoff to a human when:

| Trigger | Who Gets the Handoff |
|---|---|
| Merchant uses angry or abusive language | Field Sales Executive (FSE) |
| Merchant explicitly asks to speak to a manager or human | FSE |
| Saathi is not confident in the answer | FSE |
| Settlement issue cannot be resolved from tool data | Support team |
| Merchant has not transacted after 2 activation nudges | FSE |
| Merchant has not submitted documents after 2 re-requests | FSE |
| Merchant does not respond after 3 contact attempts (high-value lead) | FSE |
| Sensitive topics: fraud, chargeback, legal matter | Support team |

## What the Handoff Contains

Every handoff includes:
- Merchant name, shop, area, and language
- Current lifecycle state and lead score
- What happened so far (last 5 actions and messages)
- Merchant sentiment and specific objection or concern
- Document status
- Recommended next step for the human

The receiving human should be able to act within 1 minute without asking the merchant to repeat anything.

## Response Time Expectations

- FSE escalations: call the merchant within 2 hours
- Support escalations: respond within 4 hours during business hours
- Angry merchant: call within 30 minutes

## Closing a Handoff

Once the human has resolved the issue, they mark the handoff as resolved in the system. Saathi does not take further action on that issue unless the handoff is closed.

