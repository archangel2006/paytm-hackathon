<!-- MOCK POLICY: Demonstration purposes only, not real Paytm commercial terms -->
# Paytm Merchant Settlement Policy

## Overview
This document outlines payout schedules, auto-settlement rules, holiday delays, and on-demand settlement mechanisms for registered Paytm device merchants.

## 1. Daily Settlement Schedule
- **Cycle:** All successful customer payments collected from 00:00:00 to 23:59:59 are batched and transferred automatically.
- **Payout Timing:** Funds are credited directly to the merchant's registered bank account next morning by **08:00 AM (T+1 schedule)**.
- **Minimum Settlement Threshold:** ₹50. Accumulated amounts below ₹50 roll over into the following day's cycle.

## 2. Bank Holidays & Weekend Delays
- **RBI / National Banking Holidays:** When commercial banks or clearing houses are closed, settlements are deferred to the **next official banking working day**.
- **Customer Facing Communication:** When a merchant queries a delayed payout falling on or adjacent to a bank holiday, the agent must check the settlement calendar tool and reassure the merchant with the exact expected date.

## 3. Instant Settlement Feature
- **On-Demand Payout:** Merchants needing immediate liquidity can trigger Instant Settlement anytime via the Paytm for Business app.
- **Processing Time:** Credited within 15 minutes via IMPS / UPI.
- **Convenience Fee:** Nominal fee of 0.10% applied to the settled amount.

## 4. Failed or Delayed Settlement Protocol
- If a settlement shows status `delayed` due to bank server timeouts or account verification issues, the system automatically retries 3 times in 12 hours.
- If uncredited after 24 hours without a scheduled holiday, the case escalates directly to Merchant Support.

