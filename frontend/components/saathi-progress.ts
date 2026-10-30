import type { MerchantDetail } from "./saathi-data";

export type JourneyStepStatus = "complete" | "current" | "upcoming";

export type JourneyStep = {
  label: string;
  detail: string;
  status: JourneyStepStatus;
};

export function getActivationTransactionProgress(
  successfulTransactions: number,
  prerequisitesMet: boolean,
): number {
  return prerequisitesMet ? Math.min(Math.max(0, successfulTransactions), 10) : 0;
}

export function getMerchantJourney(
  merchant: Pick<MerchantDetail, "state" | "documents" | "visits" | "device" | "successful_txn_count">,
): JourneyStep[] {
  const latestDocument = (type: string) =>
    merchant.documents.slice().reverse().find((document) => document.doc_type === type);
  const requiredDocumentsApproved = ["pan", "address_proof"].every((type) => {
    const document = latestDocument(type);
    return document?.precheck_passed && document.kyc_status === "approved";
  });
  const visitComplete = merchant.visits.some((visit) => visit.status === "done");
  const deviceInstalled = merchant.device?.status === "installed" || merchant.device?.status === "active";
  const transactionsComplete = requiredDocumentsApproved
    && visitComplete
    && deviceInstalled
    && merchant.successful_txn_count >= 10;

  const completed = [
    true,
    merchant.state !== "NEW",
    requiredDocumentsApproved,
    visitComplete,
    deviceInstalled,
    transactionsComplete,
  ];
  const currentIndex = completed.findIndex((isComplete) => !isComplete);
  const steps = [
    ["Lead", "Merchant record created"],
    ["Conversation", "First merchant interaction"],
    ["Documents", "PAN and address proof submitted"],
    ["Field visit", "Visit completed"],
    ["Device", "Device installed"],
    ["First 10 transactions", "10 successful payments"],
  ] as const;

  return steps.map(([stepLabel, detail], index) => ({
    label: stepLabel,
    detail,
    status: completed[index] ? "complete" : index === currentIndex ? "current" : "upcoming",
  }));
}
