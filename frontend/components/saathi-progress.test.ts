import { describe, expect, it } from "vitest";
import { getActivationTransactionProgress, getMerchantJourney } from "./saathi-progress";
import type { MerchantDetail } from "./saathi-data";

type JourneyMerchant = Parameters<typeof getMerchantJourney>[0];

const document = (
  docType: "pan" | "address_proof",
  precheckPassed: boolean,
  kycStatus: string,
): MerchantDetail["documents"][number] => ({
  id: `${docType}-${kycStatus}`,
  doc_type: docType,
  quality: "ok",
  precheck_passed: precheckPassed,
  attempts: 1,
  issues: [],
  kyc_status: kycStatus,
  kyc_reference: null,
});

const merchant = (overrides: Partial<JourneyMerchant> = {}): JourneyMerchant => ({
  state: "NEW",
  documents: [],
  visits: [],
  device: null,
  successful_txn_count: 0,
  ...overrides,
});

describe("merchant onboarding journey", () => {
  it("does not count recorded transactions toward activation while prerequisites are incomplete", () => {
    expect(getActivationTransactionProgress(19, false)).toBe(0);
    expect(getActivationTransactionProgress(19, true)).toBe(10);
  });

  it("shows the conversation as current for a new merchant", () => {
    const journey = getMerchantJourney(merchant());

    expect(journey.map(({ status }) => status)).toEqual([
      "complete",
      "current",
      "upcoming",
      "upcoming",
      "upcoming",
      "upcoming",
    ]);
  });

  it("does not treat a passed document pre-check as official or mock KYC approval", () => {
    const journey = getMerchantJourney(merchant({
      state: "DOCS_PENDING",
      documents: [document("pan", true, "pending"), document("address_proof", true, "pending")],
    }));

    expect(journey[2]).toMatchObject({ label: "Documents", status: "current" });
    expect(journey[3].status).toBe("upcoming");
  });

  it("marks the journey complete only after both required documents, visit, device and 10 transactions", () => {
    const journey = getMerchantJourney(merchant({
      state: "ACTIVATED",
      documents: [
        document("pan", true, "approved"),
        document("address_proof", true, "approved"),
      ],
      visits: [{ id: "visit-1", slot_start: "2025-01-01T10:00:00Z", status: "done", cluster_size: 1 }],
      device: { status: "active", installed_at: null, first_txn_at: null },
      successful_txn_count: 10,
    }));

    expect(journey.every(({ status }) => status === "complete")).toBe(true);
  });

  it("does not mark 10 recorded transactions complete if onboarding prerequisites are missing", () => {
    const journey = getMerchantJourney(merchant({
      state: "ACTIVATED",
      successful_txn_count: 19,
      device: { status: "active", installed_at: null, first_txn_at: null },
    }));

    expect(journey[2].status).toBe("current");
    expect(journey[5].status).toBe("upcoming");
  });

  it("uses the latest document submission when a required document is resubmitted", () => {
    const journey = getMerchantJourney(merchant({
      state: "DOCS_PENDING",
      documents: [
        document("pan", true, "approved"),
        document("address_proof", true, "approved"),
        document("pan", false, "rejected"),
      ],
    }));

    expect(journey[2].status).toBe("current");
  });
});
