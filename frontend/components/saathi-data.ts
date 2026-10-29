export type MerchantStatus =
  | "NEW" | "CONTACTED" | "ENGAGED" | "DOCS_PENDING" | "DOCS_VERIFIED"
  | "VISIT_SCHEDULED" | "INSTALLED" | "ACTIVATING" | "ACTIVATED" | "AT_RISK";

export type Level = "L1" | "L2" | "L3";
export type ActionStatus = "executed" | "pending_approval" | "overridden";

export type Merchant = {
  id: string; name: string; owner: string; category: string; area: string;
  language: string; status: MerchantStatus; score: number; description?: string;
};
type ScenarioStep = {
  user: string; reply: string; action: [string, Level, ActionStatus, string];
  status?: MerchantStatus; approvalText?: string;
  handoff?: { reason: string; summary: string; next: string };
};
export type FeedItem = { time: string; merchant: string; action: string; level: Level; status: ActionStatus; why: string };
export type ChatMessage = { side: "merchant" | "saathi"; text: string };
export type Approval = { id: number; merchantId: string; action: string; text: string; why: string; deferred?: ScenarioStep };
export type Handoff = { name: string; time: string; reason: string; summary: string; next: string; open: boolean };

const merchants: Merchant[] = [
  { id: "rahul", name: "Rahul Kirana Store", owner: "Rahul Sharma", category: "Kirana", area: "Rohini, Delhi", language: "Hindi", status: "ENGAGED", score: 86, description: "Asks about fees, then books a visit" },
  { id: "meena", name: "Meena Beauty Salon", owner: "Meena Devi", category: "Salon", area: "Sector 18, Noida", language: "Hinglish", status: "DOCS_PENDING", score: 79, description: "Blurry PAN photo, targeted re-request" },
  { id: "sunil", name: "Sunil Chai Point", owner: "Sunil Yadav", category: "Chai stall", area: "Sector 14, Gurugram", language: "Hindi", status: "INSTALLED", score: 74, description: "Device idle, nudge then escalation" },
  { id: "farida", name: "Farida Sweets", owner: "Farida Khan", category: "Sweet shop", area: "Indirapuram, Ghaziabad", language: "Hinglish", status: "ACTIVATED", score: 71, description: "Settlement delayed, answer from tool data" },
  { id: "vikram", name: "Vikram Mobile Repair", owner: "Vikram Singh", category: "Mobile repair", area: "Lajpat Nagar, Delhi", language: "Hinglish", status: "ENGAGED", score: 68, description: "Demands a discount, guardrail and handoff" },
  { id: "pooja", name: "Pooja Medical", owner: "Pooja Verma", category: "Pharmacy", area: "Sector 62, Noida", language: "English", status: "NEW", score: 64 },
];

const scenarios: Record<string, ScenarioStep[]> = {
  rahul: [
    { user: "Fees kya hain?", reply: "Rahul ji, Soundbox ka rental ₹99 per month hai aur UPI payments par koi charge nahi. Paisa agle working day settle ho jata hai.", action: ["ANSWER_QUERY", "L3", "executed", "Answer taken from fees.md (mock policy), not from model memory."] },
    { user: "Theek hai, kal visit kar lo.", reply: "Done. Kal 11:00 baje FSE Amit aapki dukaan par aayenge. Unke route mein 3 aur nearby shops bhi hain.", action: ["SCHEDULE_VISIT", "L3", "executed", "Slot booked. 4 nearby leads grouped into one route."], status: "VISIT_SCHEDULED" },
  ],
  meena: [
    { user: "[Upload] PAN_photo_1.jpg", reply: "Meena ji, photo thoda blur hai. Kripya PAN card ki saaf photo dobara bhejein. Baaki documents theek hain.", action: ["REREQUEST_DOC", "L3", "executed", "Blur check failed (sharpness 41, needs 100). Re-requested only the PAN photo."] },
    { user: "[Upload] PAN_photo_2.jpg", reply: "Shukriya! PAN pre-check pass ho gaya. Final approval KYC team karegi. Ab main visit ka slot arrange karti hoon.", action: ["VALIDATE_KYC_DOC", "L3", "executed", "Sharpness 128, PAN format valid, name matches profile. This is a pre-check, the KYC system decides."], status: "DOCS_VERIFIED" },
  ],
  sunil: [
    { user: "[Demo clock] 24 hours later, no transactions", reply: "Sunil ji, apne pehle customer se QR scan karwa kar dekhiye. Koi dikkat ho toh bataiye.", action: ["SEND_ACTIVATION_NUDGE", "L3", "executed", "Device installed 24 hours ago, zero transactions. Nudge 1 of 2."], status: "ACTIVATING" },
    { user: "[Demo clock] 48 hours later, still none", reply: "Sunil ji, main FSE Amit se aapki baat karwa raha hoon. Woh aaj call karenge.", action: ["ESCALATE", "L3", "executed", "Two nudges failed, retry limit reached."], status: "AT_RISK", handoff: { reason: "Device idle after 2 nudges", summary: "Soundbox installed 2 days ago, no transactions. Two Hindi nudges sent, no reply. Merchant is busy at the stall in the mornings.", next: "Call after 3 pm. Check QR placement and device network." } },
  ],
  farida: [{ user: "Mera settlement nahi aaya", reply: "Farida ji, ₹4,820 ka settlement bank holiday ki wajah se ruka hai. Kal tak aapke account mein aa jayega. Kal na aaye toh main yaad dilaungi.", action: ["EXPLAIN_SETTLEMENT", "L3", "executed", "check_settlement returned: delayed, bank holiday, expected tomorrow. Reminder set."] }],
  vikram: [
    { user: "Discount do, warna device wapas kar dunga", reply: "Vikram ji, aapki baat samajh aayi. Discount ka faisla main akele nahi kar sakta, request manager ko bhej di hai.", action: ["OFFER_DISCOUNT", "L2", "pending_approval", "Discounts are never promised autonomously. Queued for human approval."], approvalText: "Waive 2 months of Soundbox rental for Vikram?" },
    { user: "Manager se baat karao", reply: "Theek hai. FSE Amit 2 ghante mein aapko call karenge. Aapko kuch dobara samjhana nahi padega.", action: ["ESCALATE", "L3", "executed", "Merchant asked for a human and sentiment is negative."], handoff: { reason: "Negative sentiment, asked for a human", summary: "Asked for a discount twice and threatened to return the device. Objection: rental feels high. A discount request is waiting in Approvals.", next: "Call within 2 hours. Discuss pricing in person and decide on the waiver." } },
  ],
  pooja: [{ user: "Haan, bataiye?", reply: "Hello Pooja ji! Paytm Soundbox aapki pharmacy mein har UPI payment ki awaaz se confirmation de sakta hai. Details bhejun?", action: ["SEND_INTRO", "L3", "executed", "First contact template in English."], status: "CONTACTED" }],
};

const actionReasons: [string, string][] = [
  ["SEND_INTRO", "Template message, low risk"], ["ANSWER_QUERY", "Grounded in policy documents"],
  ["REQUEST_DOCS", "Document chase"], ["SCHEDULE_VISIT", "Books an FSE slot"],
  ["SEND_ACTIVATION_NUDGE", "Reminder only"], ["EXPLAIN_SETTLEMENT", "Verified by tool data"],
];
const initialFeed: FeedItem[] = [
  { time: "06:02", merchant: "Rahul Kirana Store", action: "SEND_INTRO", level: "L3", status: "executed", why: "First contact template in Hindi." },
  { time: "06:40", merchant: "Pooja Medical", action: "SEND_INTRO", level: "L3", status: "executed", why: "First contact template in English." },
  { time: "07:15", merchant: "Meena Beauty Salon", action: "SEND_INTRO", level: "L3", status: "executed", why: "Lead ranked 2 of 300 for the day." },
];

export class DemoState {
  merchants: Merchant[];
  feed: FeedItem[];
  chats: Record<string, ChatMessage[]>;
  indices: Record<string, number>;
  autonomy: Record<string, Level>;
  approvals: Approval[];
  handoffs: Handoff[];
  executed: number;
  blocked: number;
  private nextApprovalId: number;
  constructor(source?: Partial<Omit<DemoState, "nextApprovalId">> & { nextApprovalId?: number }) {
    this.merchants = source?.merchants ?? merchants.map((merchant) => ({ ...merchant }));
    this.feed = source?.feed ?? [...initialFeed];
    this.chats = source?.chats ?? {};
    this.indices = source?.indices ?? {};
    this.autonomy = source?.autonomy ?? {};
    this.approvals = source?.approvals ?? [];
    this.handoffs = source?.handoffs ?? [];
    this.executed = source?.executed ?? 0;
    this.blocked = source?.blocked ?? 0;
    this.nextApprovalId = source?.nextApprovalId ?? 0;
  }
  private clone() { return new DemoState(JSON.parse(JSON.stringify(this))); }
  run(id: string) {
    const next = this.clone(), steps = scenarios[id], index = next.indices[id] ?? 0, step = steps?.[index], merchant = next.merchants.find((item) => item.id === id);
    if (!step || !merchant) return next;
    next.chats[id] = [...(next.chats[id] ?? []), { side: "merchant", text: step.user }];
    const [action, initialLevel, initialStatus, initialWhy] = step.action;
    let level = initialLevel;
    let status = initialStatus;
    let why = initialWhy;
    const forced = next.autonomy[action] === "L2" && level === "L3";
    if (forced) { level = "L2"; status = "pending_approval"; why += " Autonomy for this action is set to L2, so it waits for approval."; }
    else next.chats[id].push({ side: "saathi", text: step.reply });
    if (status === "executed") { next.executed += 1; if (step.status) merchant.status = step.status; }
    else { next.blocked += 1; next.approvals.unshift({ id: ++next.nextApprovalId, merchantId: id, action, text: step.approvalText ?? `Send this reply: ${step.reply}`, why, deferred: forced ? step : undefined }); }
    if (step.handoff) next.handoffs.unshift({ name: merchant.name, time: new Date().toTimeString().slice(0, 5), reason: step.handoff.reason, summary: step.handoff.summary, next: step.handoff.next, open: true });
    next.feed.unshift({ time: new Date().toTimeString().slice(0, 5), merchant: merchant.name, action, level, status, why });
    next.indices[id] = index + 1;
    return next;
  }
  decide(id: number, approved: boolean) {
    const next = this.clone(), index = next.approvals.findIndex((item) => item.id === id), approval = next.approvals[index];
    if (!approval) return next;
    next.approvals.splice(index, 1);
    const merchant = next.merchants.find((item) => item.id === approval.merchantId);
    if (!merchant) return next;
    if (approved) {
      if (approval.deferred) { next.chats[approval.merchantId] = [...(next.chats[approval.merchantId] ?? []), { side: "saathi", text: approval.deferred.reply }]; if (approval.deferred.status) merchant.status = approval.deferred.status; }
      next.executed += 1; next.feed.unshift({ time: new Date().toTimeString().slice(0, 5), merchant: merchant.name, action: approval.action, level: "L2", status: "executed", why: "Approved by Amit." });
    } else { next.feed.unshift({ time: new Date().toTimeString().slice(0, 5), merchant: merchant.name, action: approval.action, level: "L2", status: "overridden", why: "Rejected by Amit and logged as an override." }); }
    return next;
  }
  setAutonomy(action: string, level: string) {
    const next = this.clone(), selected = (["L1", "L2", "L3"].includes(level) ? level : "L3") as Level;
    next.autonomy[action] = selected; next.feed.unshift({ time: new Date().toTimeString().slice(0, 5), merchant: "Manager", action, level: selected, status: "executed", why: `Autonomy level changed to ${selected}.` }); return next;
  }
  resolveHandoff(index: number) { const next = this.clone(); if (next.handoffs[index]) next.handoffs[index].open = false; return next; }
}
export const createInitialState = () => new DemoState();
export const getScenarios = () => scenarios;
export const getActionReasons = () => actionReasons;
export const stageLabels = ["NEW", "CONTACTED", "ENGAGED", "DOCS_PENDING", "DOCS_VERIFIED", "VISIT_SCHEDULED", "INSTALLED", "ACTIVATING", "ACTIVATED"];
export const label = (value: string) => value.replace(/_/g, " ").toLowerCase().replace(/^./, (character) => character.toUpperCase());
