<!-- MOCK POLICY: Demonstration purposes only, not real Paytm commercial terms -->
# Paytm Saathi: Escalation & Human Handoff Policy

## Overview
Defines mandatory trigger points, routing logic, SLA commitments, and handoff summary protocols when AI autonomy must yield to human teammates.

## 1. Mandatory Escalation Triggers
An escalation to a human teammate must be triggered immediately if any of the following occur:
1. **Explicit Request for Human:** Merchant asks for a manager, supervisor, or human representative (e.g., "baat karao", "manager se baat karni hai", "human").
2. **Persistent Negative Sentiment / Anger:** Abusive language, repeated complaints, or threats to return the Soundbox.
3. **Discount / Waiver Negotiation:** Demands for custom pricing, rental waivers, or free hardware (held at L2 approval; escalated if merchant remains insistent).
4. **Retry Limit Exhaustion:**
   - 2 failed activation nudges with zero transactions post-install.
   - 2 failed KYC document re-requests.
   - 3 consecutive unanswered outbound contacts on a high-scoring lead.
5. **Sensitive Inquiries:** Fraud claims, chargeback disputes, legal notices, or account freezing requests.

## 2. Team Routing Matrix
- **Field Sales Executive (FSE):**
  - Objections regarding hardware price, rental terms, or installation scheduling.
  - Idle device follow-up (device installed but 0 transactions after 24-48 hours).
- **Merchant Support Desk:**
  - Complex settlement discrepancies or missing bank payouts.
  - Device replacement or hardware defects.

## 3. Warm Handoff Summary Format
Every escalation ticket must contain a 1-page condensed contextual summary:
- **Headline:** Merchant name, shop name, category, area, language preference.
- **State & Lead Score:** Funnel status and priority.
- **What Happened:** Chronological summary of recent interactions.
- **Merchant Sentiment & Objection:** Explicit reason for dissatisfaction.
- **Recommended Next Action:** Clear next step for the human handler (e.g., "Call merchant within 2 hours, discuss pricing in person").
- **SLA:** Callback guaranteed within **2 business hours**.

