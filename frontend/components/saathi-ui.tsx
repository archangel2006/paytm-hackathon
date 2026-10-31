"use client";

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import type {
  AgentAction,
  AutonomySettings,
  Handoff,
  Health,
  Merchant,
  MerchantDetail,
  Message,
  Scoreboard,
} from "./saathi-data";
import { label } from "./saathi-data";
import { getActivationTransactionProgress, getMerchantJourney } from "./saathi-progress";

const levelClass = (level: string) => ({ L1: "gy", L2: "wn", L3: "bl" }[level] ?? "gy");
const statusClass = (status: string) => ({
  executed: "ok",
  pending_approval: "wn",
  blocked: "wn",
  failed: "bd",
  rejected: "gy",
  overridden: "gy",
  open: "wn",
  AT_RISK: "bd",
  LOST: "gy",
  DORMANT: "gy",
  ACTIVATED: "ok",
  DOCS_VERIFIED: "ok",
  INSTALLED: "ok",
  ACTIVATING: "wn",
  DOCS_PENDING: "wn",
  VISIT_SCHEDULED: "bl",
  CONTACTED: "bl",
  ENGAGED: "bl",
}[status] ?? "bl");
const timeLabel = (value: string) => new Date(value).toLocaleString([], { dateStyle: "short", timeStyle: "short" });
const displayStatus = (value: string) => label(value);

type SpeechResultEvent = {
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
  resultIndex: number;
};

type SpeechRecognitionErrorEvent = { error: string };

type BrowserSpeechRecognition = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((event: SpeechResultEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechRecognitionWindow = Window & {
  SpeechRecognition?: new () => BrowserSpeechRecognition;
  webkitSpeechRecognition?: new () => BrowserSpeechRecognition;
};

function guardrailSummary(action: AgentAction) {
  if (action.status === "blocked") return "Blocked by a guardrail";
  if (action.status === "pending_approval" || action.status === "proposed") return "Human review required";
  if (action.status === "failed") return "Action failed";
  if (action.guardrail_notes.length) return "Guardrail note recorded";
  if (action.status === "executed" || action.status === "approved") return "No guardrail exceptions";
  return "Check recorded";
}

export function Badge({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <span className={`b ${className}`}>{children}</span>;
}

export function Feed({ items, limit }: { items: AgentAction[]; limit?: number }) {
  const visible = limit ? items.slice(0, limit) : items;
  return <>{visible.length ? visible.map((item) => (
    <div className="action-row" key={item.id}>
      <div className="action-main">
        <div className="action-title"><b>{item.shop_name}</b><Badge className="gy">{label(item.action_type)}</Badge><Badge className={levelClass(item.autonomy_level)}>{item.autonomy_level}</Badge><Badge className={statusClass(item.status)}>{displayStatus(item.status)}</Badge></div>
        <p className="sm m action-reason">{item.reasoning || "No reasoning was returned."}</p>
        <details className="guardrail-details">
          <summary className={item.guardrail_notes.length || item.status === "blocked" ? "guardrail-alert" : ""}>
            Guardrails Â· {guardrailSummary(item)}
          </summary>
          {item.guardrail_notes.length
            ? <ul>{item.guardrail_notes.map((note) => <li key={note}>{note}</li>)}</ul>
            : <p className="sm m">{item.status === "executed" || item.status === "approved" ? "No blocking or escalation rule was triggered for this action." : "No additional guardrail notes were recorded."}</p>}
        </details>
      </div>
      <span className="tm action-time">{timeLabel(item.created_at)}</span>
    </div>
  )) : <p className="m">No recorded actions yet.</p>}</>;
}

function Shell({ children }: { children: ReactNode }) {
  return <div className="wrap">{children}</div>;
}

function Grid({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`gr ${className}`}>{children}</div>;
}

export function SiteHeader({
  hash,
  health,
  pendingApprovals,
  openHandoffs,
  busy,
  onReset,
  onRefresh,
}: {
  hash: string;
  health: Health | null;
  pendingApprovals: number;
  openHandoffs: number;
  busy: boolean;
  onReset: () => void;
  onRefresh: () => void;
}) {
  const links = [
    ["home", "Home"],
    ["dashboard", "Dashboard"],
    ["merchants", "Merchants"],
    ["approvals", `Approvals${pendingApprovals ? ` (${pendingApprovals})` : ""}`],
    ["handoffs", `Handoffs${openHandoffs ? ` (${openHandoffs})` : ""}`],
    ["scoreboard", "Scoreboard"],
  ];
  return <header><div className="hd">
    <a className="logo" href="#home"><span className="mk" aria-hidden="true">S</span><span>Paytm Saathi</span></a>
    <nav aria-label="Main navigation">{links.map(([href, text]) => <a key={href} href={`#${href}`} className={hash === href || ((hash.startsWith("m-") || hash.startsWith("chat-")) && href === "merchants") ? "on" : ""}>{text}</a>)}</nav>
    <span className={`tag ${health?.status === "ok" ? "connected" : "disconnected"}`} role="status">{health?.status === "ok" ? "Backend connected" : "Connecting to backend"}</span>
    <button className="refresh-button" onClick={onRefresh} disabled={busy} aria-label="Refresh" title="Refresh"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 7v5h-5M4 17v-5h5" /><path d="M5.6 9a7 7 0 0 1 11.7-2L20 12M4 12l2.7 5a7 7 0 0 0 11.7-2" /></svg></button>
    <button className="hl" onClick={onReset} disabled={busy}>{busy ? "Workingâ€¦" : "Reset backend demo"}</button>
  </div></header>;
}

const STAGE_ICONS = [
  <path key="0" d="M3 4h18l-7 8v6l-4 2v-8z" />,
  <path key="1" d="M4 5h16v11H9l-5 4z" />,
  <g key="2"><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4M10 13h5M10 17h5" /></g>,
  <g key="3"><rect x="4" y="5" width="16" height="15" rx="2" /><path d="M4 10h16M9 3v4M15 3v4" /></g>,
  <path key="4" d="M13 3L5 14h6l-1 7 8-11h-6z" />,
  <g key="5"><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="3" /><path d="M6.3 6.3l3.5 3.5M17.7 6.3l-3.5 3.5M6.3 17.7l3.5-3.5M17.7 17.7l-3.5-3.5" /></g>,
];

const TRUST_ICONS = [
  <g key="0"><path d="M4 8h10M18 8h2M4 16h2M10 16h10" /><circle cx="16" cy="8" r="2" /><circle cx="8" cy="16" r="2" /></g>,
  <g key="1"><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" /><path d="M9 12l2 2 4-4" /></g>,
  <g key="2"><path d="M8 4h8v3H8z" /><path d="M6 6H5v15h14V6h-1M9 12h6M9 16h6" /></g>,
];

function CardIcon({ children }: { children: ReactNode }) {
  return (
    <div className="ico">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        {children}
      </svg>
    </div>
  );
}

export function HomeView() {
  const stages = [
    ["Lead triage", "Scores leads and builds a ranked call list.", "Works from a plan, not a raw list."],
    ["Outreach", "Pitches in Hinglish and answers fee questions from policy documents.", "Takes over hot leads."],
    ["Onboarding", "Chases documents, flags blurry photos, asks only for what is missing.", "The official KYC system approves."],
    ["Visit scheduling", "Groups nearby shops into one route and confirms slots.", "Visits and installs the device."],
    ["Activation", "Nudges the first scan and detects idle devices.", "Steps in when a device stays idle."],
    ["Service", "Looks up settlements and tickets, explains status plainly.", "Handles complex disputes."],
  ];

  const trustCards = [
    ["Autonomy levels", "Every action type is set to suggest only, act after approval, or act alone. Managers can change it."],
    ["Grounded answers", "Fees, timelines and statuses come from policy documents and tools, never from model memory."],
    ["Full audit trail", "Each action is logged with its reasoning. Overrides are recorded and visible."],
  ];

  return (
    <Shell>
      <div className="hero">
        <h1>The AI teammate that takes every merchant from first call to first transaction.</h1>
        <p className="m hero-copy">
          Saathi handles the follow-ups, document chasing and status checks in a field sales funnel. Field sales executives keep the visits, the negotiation and the trust.
        </p>
        <a className="btn" href="#dashboard">Open the live demo</a>{" "}
        <a className="btn s" href="#scoreboard">See the results</a>
      </div>

      <h2>One owner for six stages</h2>
      <p className="m" style={{ margin: "6px 0 16px" }}>
        Saathi does the repetitive work. People keep the moments that need trust.
      </p>
      <Grid>
        {stages.map((stage, i) => (
          <div className="box stage-card" key={stage[0]}>
            <CardIcon>{STAGE_ICONS[i]}</CardIcon>
            <h3>{stage[0]}</h3>
            <p>{stage[1]}</p>
            <p className="stage-human">Human: {stage[2]}</p>
          </div>
        ))}
      </Grid>

      <h2 style={{ marginTop: 40 }}>Built so a manager would let it run</h2>
      <Grid style={{ marginTop: 14 }}>
        {trustCards.map((card, i) => (
          <div className="box trust-card" key={card[0]}>
            <CardIcon>{TRUST_ICONS[i]}</CardIcon>
            <h3>{card[0]}</h3>
            <p>{card[1]}</p>
          </div>
        ))}
      </Grid>

      <p className="sm m ln footer-note">
        Hackathon prototype. All merchants, messages, fees and results on this site are synthetic demo data.
      </p>
    </Shell>
  );
}

export function DashboardView({
  scoreboard,
  actions,
  merchants,
}: {
  scoreboard: Scoreboard | null;
  actions: AgentAction[];
  merchants: Merchant[];
}) {
  const counters = scoreboard?.counters;
  const activationCompleted = merchants.filter((merchant) =>
    merchant.activation_eligible && merchant.successful_txn_count >= 10
  ).length;
  return <Shell>
    <Grid className="stats-grid">{[
      ["Awaiting approval", counters?.pending_approvals ?? 0],
      ["Open handoffs", counters?.handoffs_open ?? 0],
      ["Actions executed", counters?.actions_executed ?? 0],
      ["Blocked by guardrails", counters?.blocked ?? 0],
      ["Reached 10 transactions", activationCompleted],
    ].map(([text, value]) => <div className="kp" key={String(text)}><b>{value}</b><span className="sm m">{text}</span></div>)}</Grid>
    <p className="data-caption">Live demo data Â· synthetic merchant records</p>
    <Grid className="g2 dashboard-panels">
      <div className="box"><h3>Priority merchants</h3><p className="sm m scenario-intro">Open a record for the full onboarding checklist and safety review.</p>{merchants.slice(0, 8).map((merchant) => {
        const successful = Math.max(0, merchant.successful_txn_count);
        const progress = getActivationTransactionProgress(successful, merchant.activation_eligible);
        const countLabel = successful > 0 && !merchant.activation_eligible
          ? `${progress} / 10 activation goal Â· ${successful} recorded; prerequisites incomplete`
          : `${progress} / 10 goal${successful > 10 ? ` Â· ${successful} recorded` : successful === 10 ? " Â· goal reached" : ""}`;
        return <div className="row scenario-row" key={merchant.id}><div className="merchant-row-head"><a className="lk" href={`#m-${merchant.id}`}>{merchant.shop_name}</a><Badge className={statusClass(merchant.state)}>{displayStatus(merchant.state)}</Badge></div><div className="mini-progress"><span className="sm m">{countLabel}</span><div className="bar" role="progressbar" aria-label={`${merchant.shop_name} transaction goal`} aria-valuemin={0} aria-valuemax={10} aria-valuenow={progress}><b style={{ width: `${progress * 10}%` }} /></div></div></div>;
      })}{!merchants.length && <p className="m">No merchants were returned by the backend.</p>}</div>
      <div className="box"><h3>Recent actions</h3><div className="feed-space"><Feed items={actions} limit={8} /></div></div>
    </Grid>
  </Shell>;
}

export function MerchantsView({ merchants, actions }: { merchants: Merchant[]; actions: AgentAction[] }) {
  const [query, setQuery] = useState("");
  const [stateFilter, setStateFilter] = useState("all");
  const states = [...new Set(merchants.map((merchant) => merchant.state))].sort();
  const normalizedQuery = query.trim().toLowerCase();
  const filtered = merchants.filter((merchant) => {
    const matchesText = !normalizedQuery || [
      merchant.shop_name,
      merchant.owner_name,
      merchant.category,
      merchant.area,
      merchant.city,
    ].some((value) => value.toLowerCase().includes(normalizedQuery));
    return matchesText && (stateFilter === "all" || merchant.state === stateFilter);
  });
  const latestAction = (merchantId: string) => actions
    .filter((action) => action.merchant_id === merchantId)
    .sort((left, right) => right.created_at.localeCompare(left.created_at))[0];
  return <Shell>
    <div className="page-heading"><div><p className="eyebrow">MERCHANT OPERATIONS</p><h2>Merchant portfolio</h2><p className="m intro">Follow each merchant from first contact to 10 successful transactions. Counts are live synthetic demo data.</p></div><Badge className="bl">{merchants.length} records</Badge></div>
    <div className="filter-bar">
      <label className="search-field"><span>Search merchants</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Shop, owner, category, or area" /></label>
      <label className="state-field"><span>Lifecycle status</span><select value={stateFilter} onChange={(event) => setStateFilter(event.target.value)}><option value="all">All statuses</option>{states.map((state) => <option value={state} key={state}>{displayStatus(state)}</option>)}</select></label>
      <span className="sm m results-count">{filtered.length} shown</span>
    </div>
    <div className="box tw table-box"><table className="merchant-table"><thead><tr>{["Merchant", "Lifecycle", "Documents", "Activation progress", "Latest guardrail check", "Lead score"].map((heading) => <th key={heading}>{heading}</th>)}</tr></thead><tbody>{filtered.map((merchant) => {
      const recentAction = latestAction(merchant.id);
      const documentStatus = merchant.docs_status === "verified" ? "Mock KYC approved" : merchant.docs_status === "pending" ? "Review in progress" : "Not submitted";
      const documentClass = merchant.docs_status === "verified" ? "ok" : merchant.docs_status === "pending" ? "wn" : "gy";
      const activationProgress = getActivationTransactionProgress(merchant.successful_txn_count, merchant.activation_eligible);
      const guardrailStatus = recentAction ? guardrailSummary(recentAction) : "Not checked";
      const guardrailClass = !recentAction ? "gy" : recentAction.status === "blocked" || recentAction.status === "failed" ? "bd" : recentAction.status === "pending_approval" || recentAction.status === "proposed" ? "wn" : "ok";
      return <tr key={merchant.id}>
        <td><a className="lk merchant-link" href={`#m-${merchant.id}`}><b>{merchant.shop_name}</b></a><span className="sm m merchant-owner">{merchant.owner_name} Â· {merchant.category} Â· {merchant.area || merchant.city}</span></td>
        <td><Badge className={statusClass(merchant.state)}>{displayStatus(merchant.state)}</Badge></td>
        <td><Badge className={documentClass}>{documentStatus}</Badge><span className="sm m cell-note">Pre-check is not official KYC</span></td>
        <td className="activation-cell"><div className="activation-count"><b>{activationProgress} / 10</b><span>{merchant.activation_eligible ? " activation goal" : " goal Â· prerequisites incomplete"}</span></div>{merchant.successful_txn_count > 0 && <span className="sm m cell-note">{merchant.successful_txn_count} recorded</span>}<div className="bar"><b style={{ width: `${activationProgress * 10}%` }} /></div></td>
        <td><Badge className={guardrailClass}>{guardrailStatus}</Badge>{recentAction && <span className="sm m cell-note">{label(recentAction.action_type)} Â· {timeLabel(recentAction.created_at)}</span>}</td>
        <td className="score-cell"><b>{Math.round(merchant.lead_score)}</b><div className="bar"><b style={{ width: `${merchant.lead_score}%` }} /></div></td>
      </tr>;
    })}</tbody></table>{!filtered.length && <p className="m empty-state">{merchants.length ? "No merchants match these filters." : "No merchant records were returned by the backend."}</p>}</div>
  </Shell>;
}

function JourneyProgress({ merchant }: { merchant: MerchantDetail }) {
  const steps = getMerchantJourney(merchant);
  return <ol className="journey" aria-label="Merchant onboarding journey">
    {steps.map((step, index) => (
      <li className={`journey-step ${step.status}`} key={step.label}>
        <span className="journey-marker" aria-hidden="true">{step.status === "complete" ? "âœ“" : index + 1}</span>
        <span className="journey-copy"><b>{step.label}</b><span>{step.detail}</span><small>{label(step.status)}</small></span>
      </li>
    ))}
  </ol>;
}

function DocumentCard({
  docType,
  document,
}: {
  docType: "pan" | "address_proof";
  document: MerchantDetail["documents"][number] | undefined;
}) {
  const title = docType === "pan" ? "PAN card" : "Business / address proof";
  let state = "Not submitted";
  let className = "gy";
  if (document?.kyc_status === "approved") {
    state = "Mock KYC approved";
    className = "ok";
  } else if (document?.kyc_status === "rejected") {
    state = "Mock KYC rejected";
    className = "bd";
  } else if (document?.precheck_passed) {
    state = "Pre-check passed";
    className = "ok";
  } else if (document) {
    state = document.quality === "blurry" ? "Retake Â· image blurry"
      : document.quality === "unreadable" ? "Retake Â· unreadable"
        : "Review required";
    className = "wn";
  }
  return <div className="document-card">
    <div className="document-card-head"><div><b>{title}</b><span className="sm m">{docType === "pan" ? "Mandatory identity document" : "Mandatory proof of business address"}</span></div><Badge className={className}>{state}</Badge></div>
    {document ? <div className="document-result">
      <span>Image quality: <b>{label(document.quality)}</b></span>
      <span>Automated pre-check: <b>{document.precheck_passed ? "Passed" : "Not passed"}</b></span>
      <span>Mock KYC: <b>{label(document.kyc_status)}</b></span>
      <span>Submission attempts: <b>{document.attempts}</b></span>
      {document.issues.length > 0 && <span className="document-issues">Needs attention: {document.issues.map(label).join(", ")}</span>}
    </div> : <p className="sm m document-empty">Upload a clear image or PDF to start this check.</p>}
  </div>;
}

function MerchantConversation({
  merchant,
  messages,
  busy,
  isChat,
  onSend,
  onUpload,
}: {
  merchant: MerchantDetail;
  messages: Message[];
  busy: boolean;
  isChat: boolean;
  onSend: (text: string) => Promise<boolean>;
  onUpload: (file: File, docType: "pan" | "address_proof") => void;
}) {
  const [text, setText] = useState("");
  const [docType, setDocType] = useState<"pan" | "address_proof">("pan");
  const [listening, setListening] = useState(false);
  const [voiceError, setVoiceError] = useState("");
  const recognition = useRef<BrowserSpeechRecognition | null>(null);
  const voiceBaseText = useRef("");

  useEffect(() => {
    return () => recognition.current?.stop();
  }, []);

  const startVoiceInput = () => {
    const speechWindow = window as SpeechRecognitionWindow;
    const SpeechRecognition = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoiceError("Voice input is not supported by this browser. You can type your message instead.");
      return;
    }
    setVoiceError("");
    voiceBaseText.current = text.trim();
    const instance = new SpeechRecognition();
    instance.lang = "en-IN";
    instance.continuous = true;
    instance.interimResults = true;
    instance.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0]?.transcript ?? "")
        .join(" ")
        .trim();
      setText([voiceBaseText.current, transcript].filter(Boolean).join(" "));
    };
    instance.onerror = (event) => {
      setVoiceError(`Voice input stopped (${event.error}). You can continue by typing.`);
      setListening(false);
    };
    instance.onend = () => setListening(false);
    recognition.current = instance;
    try {
      instance.start();
      setListening(true);
    } catch (error) {
      setVoiceError(error instanceof Error ? error.message : "Could not start voice input.");
    }
  };

  const submitMessage = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = text.trim();
    if (!value || busy) return;
    void onSend(value).then((sent) => {
      if (sent) setText("");
    });
  };
  const submitFile = (event: FormEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0];
    if (file) onUpload(file, docType);
    event.currentTarget.value = "";
  };

  return <section className={`conversation-section ${isChat ? "conversation-page" : ""}`}>
    <div className="section-heading conversation-heading">
      <div><p className="eyebrow">{isChat ? "WHATSAPP CHAT" : "MERCHANT CONVERSATION"}</p><h3>{isChat ? `Chat with ${merchant.shop_name}` : "Simulator messages"}</h3></div>
      <span className="sm m">Persisted by backend Â· {label(merchant.preferred_channel)} channel</span>
    </div>
    {isChat && <a className="lk sm chat-back" href={`#m-${merchant.id}`}>â† Back to merchant overview</a>}
    <div className="ph"><div className="t">Paytm Saathi Â· {label(merchant.preferred_channel)}</div><div className="ms" aria-live="polite">{messages.length ? messages.map((message) => <div className={`bu ${message.direction === "in" ? "m" : ""}`} key={message.id}>{message.text}<div className="message-time">{timeLabel(message.created_at)}</div></div>) : <p className="sm m phone-empty">No messages saved yet. Send a message to the backend agent.</p>}</div>
      <form className="in" onSubmit={submitMessage}><label className="sr-only" htmlFor="merchant-message">Message</label><div className="message-controls"><input id="merchant-message" value={text} onChange={(event) => setText(event.target.value)} placeholder="Write a merchant messageâ€¦" maxLength={4000} disabled={busy} /><button className="btn x" type="submit" disabled={busy || !text.trim()}>{busy ? "Sendingâ€¦" : "Send"}</button><button className="voice-button" type="button" onClick={listening ? () => recognition.current?.stop() : startVoiceInput} disabled={busy} aria-label={listening ? "Stop voice input" : "Start voice input"} title={listening ? "Stop voice input" : "Dictate message"}>{listening ? "â– " : "ðŸŽ™"}</button></div>{listening && <span className="sm voice-status" role="status">Listeningâ€¦ speak now, then review and send.</span>}{voiceError && <span className="sm voice-error" role="status">{voiceError}</span>}</form>
      <div className="upload-control"><label htmlFor="document-type">Document type</label><select id="document-type" value={docType} onChange={(event) => setDocType(event.target.value === "address_proof" ? "address_proof" : "pan")} disabled={busy}><option value="pan">PAN card</option><option value="address_proof">Business / address proof</option></select><label htmlFor="merchant-document">Upload a clear document image</label><input id="merchant-document" type="file" accept="image/jpeg,image/png,image/webp" onChange={submitFile} disabled={busy} /><span className="sm m">Accepted: JPG, PNG or WebP. Use synthetic demo documents only; do not upload real identity documents.</span></div>
    </div>
  </section>;
}

export function MerchantDetailView({
  merchant,
  messages,
  actions,
  isChat,
  busy,
  onDeviceEvent,
  onAdvanceClock,
  onSend,
  onUpload,
}: {
  merchant: MerchantDetail;
  messages: Message[];
  actions: AgentAction[];
  isChat: boolean;
  busy: boolean;
  onDeviceEvent: (event: "installed" | "transaction") => void;
  onAdvanceClock: () => void;
  onSend: (text: string) => Promise<boolean>;
  onUpload: (file: File, docType: "pan" | "address_proof") => void;
}) {
  const latestDocument = (type: string) => merchant.documents.slice().reverse().find((document) => document.doc_type === type);
  const latestAction = actions[0];
  const successfulTransactions = Math.max(0, merchant.successful_txn_count);
  const journey = getMerchantJourney(merchant);
  const activationPrerequisitesMet = journey.slice(2, 5).every((step) => step.status === "complete");
  const transactionProgress = getActivationTransactionProgress(successfulTransactions, activationPrerequisitesMet);
  const activationComplete = journey[5].status === "complete";
  const deviceInstalled = merchant.device?.status === "installed" || merchant.device?.status === "active";
  const isPaused = merchant.state === "DORMANT" || merchant.state === "LOST";
  return <Shell>
    <a className="lk sm" href={isChat ? `#m-${merchant.id}` : "#merchants"}>{isChat ? "â† Back to merchant overview" : "â† Back to portfolio"}</a>
    <div className="detail-hero">
      <div><p className="eyebrow">MERCHANT 360</p><div className="detail-title-row"><h2>{merchant.shop_name}</h2><Badge className={statusClass(merchant.state)}>{displayStatus(merchant.state)}</Badge></div><p className="m detail-subtitle">{merchant.owner_name} Â· {label(merchant.category)} Â· {merchant.area || merchant.city} Â· {label(merchant.language)}</p>{!isChat && <a className="whatsapp-launch merchant-chat-launch" href={`#chat-${merchant.id}`} aria-label={`Open WhatsApp chat with ${merchant.shop_name}`} title="Open WhatsApp chat"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.5 11.8a8.5 8.5 0 0 1-12.6 7.4L3 20.5l1.3-4.7A8.5 8.5 0 1 1 20.5 11.8Z" /><path d="M8.2 7.8c.2-.4.4-.4.7-.4h.4c.2 0 .4.1.5.4l.7 1.6c.1.2.1.4 0 .5l-.5.6c-.2.2-.2.4-.1.6.4.7 1 1.3 1.7 1.7.2.1.4.1.6-.1l.6-.7c.2-.2.3-.2.6-.1l1.5.7c.3.1.4.3.4.5 0 .3-.2 1.2-.7 1.6-.5.5-1.2.7-1.9.5-.7-.2-1.6-.5-2.7-1.5-1.4-1.2-2.3-2.6-2.5-3.5-.2-.9.1-1.7.7-2.4Z" /></svg><span>WhatsApp chat</span></a>}</div>
      <div className="detail-quick-stats"><div><span>Lead score</span><b>{Math.round(merchant.lead_score)}<small> / 100</small></b></div><div><span>Consent</span><b className={merchant.consent ? "text-ok" : "text-bad"}>{merchant.consent ? "Active" : "Opted out"}</b></div></div>
    </div>
    {!isChat && isPaused && <div className="notice inline-notice warning" role="status">{merchant.state === "LOST" ? "This lead was closed. Outbound messaging should remain stopped." : "This merchant is dormant. Re-engagement depends on the configured cooldown and agent workflow."}</div>}
    {!isChat && merchant.state === "AT_RISK" && <div className="notice inline-notice warning" role="status">Activation needs human attention. Review the latest handoff and guardrail notes below.</div>}
    {!isChat && <section className="journey-panel box">
      <div className="section-heading"><div><p className="eyebrow">ONBOARDING JOURNEY</p><h3>From first contact to 10 successful transactions</h3></div><span className="sm m">Milestones use persisted backend events</span></div>
      <JourneyProgress merchant={merchant} />
    </section>}
    {!isChat && <Grid className="detail-grid">
      <div className="detail-column">
        <section className="box detail-box">
          <div className="section-heading"><div><p className="eyebrow">KYC DOCUMENTS</p><h3>Required document checklist</h3></div><Badge className="gy">2 required</Badge></div>
          <div className="document-list">
            <DocumentCard docType="pan" document={latestDocument("pan")} />
            <DocumentCard docType="address_proof" document={latestDocument("address_proof")} />
          </div>
          <p className="disclaimer"><b>Important:</b> The automated check only reviews image quality and available fields. â€œMock KYCâ€ is demo data; neither result is official Paytm KYC approval.</p>
        </section>
        <section className="box detail-box">
          <div className="section-heading"><div><p className="eyebrow">DEVICE ACTIVATION</p><h3>First 10 successful transactions</h3></div><Badge className={activationComplete ? "ok" : transactionProgress >= 10 ? "wn" : "bl"}>{transactionProgress} / 10</Badge></div>
          <div className="activation-summary"><span>Device status</span><Badge className={deviceInstalled ? "ok" : "gy"}>{deviceInstalled ? label(merchant.device?.status ?? "installed") : "Not installed"}</Badge><strong>{transactionProgress}<small> of 10 goal Â· {successfulTransactions} recorded</small></strong></div>
          <div className="bar activation-bar" role="progressbar" aria-label="Successful transactions toward activation" aria-valuemin={0} aria-valuemax={10} aria-valuenow={transactionProgress}><b style={{ width: `${transactionProgress * 10}%` }} /></div>
          <p className="sm m transaction-context">{activationComplete ? "Activation milestone reached." : !activationPrerequisitesMet && successfulTransactions >= 10 ? `${successfulTransactions} transactions are recorded, but are not counted toward activation until both documents are approved, the field visit is complete, and the device is installed.` : !activationPrerequisitesMet ? "Transactions can be counted toward activation after both documents are approved, the field visit is completed, and the device is installed." : `${10 - transactionProgress} more successful transaction(s) needed to reach the activation milestone.`}</p>
          {merchant.device?.first_txn_at && <p className="sm m">First successful transaction: {timeLabel(merchant.device.first_txn_at)}</p>}
          <div className="demo-controls">
            <div className="demo-button-row">
              {merchant.state === "VISIT_SCHEDULED" && !deviceInstalled && <button className="btn x s" onClick={() => onDeviceEvent("installed")} disabled={busy}>Record completed visit and device installation</button>}
              {activationPrerequisitesMet && transactionProgress < 10 && <button className="btn x s" onClick={() => onDeviceEvent("transaction")} disabled={busy}>Record 1 successful transaction</button>}
              {!deviceInstalled && merchant.state !== "VISIT_SCHEDULED" && <span className="sm m">Device events become available after a field visit is scheduled.</span>}
              {activationPrerequisitesMet && transactionProgress < 10 && <button className="hl" onClick={onAdvanceClock} disabled={busy}>Advance demo clock 24h</button>}
              {activationComplete && <span className="sm text-ok">10-transaction activation goal reached. {successfulTransactions} successful transactions are recorded.</span>}
            </div>
          </div>
        </section>
        <section className="box detail-box">
          <div className="section-heading"><div><p className="eyebrow">FIELD OPERATIONS</p><h3>Visits and assignment</h3></div></div>
          {merchant.visits.length ? merchant.visits.map((visit) => <div className="visit-card" key={visit.id}><div><b>{label(visit.status)} visit</b><span className="sm m">{timeLabel(visit.slot_start)}</span></div><Badge className="bl">Route cluster Â· {visit.cluster_size}</Badge></div>) : <p className="sm m">No field visit has been scheduled yet.</p>}
          <p className="sm m detail-meta">Assigned FSE: {merchant.fse_id ? label(merchant.fse_id) : "Not assigned"}</p>
        </section>
      </div>
      <div className="detail-column">
        <section className="box detail-box safety-panel">
          <div className="section-heading"><div><p className="eyebrow">SAFETY & AUTONOMY</p><h3>Latest guardrail check</h3></div>{latestAction ? <Badge className={statusClass(latestAction.status)}>{guardrailSummary(latestAction)}</Badge> : <Badge className="gy">Not checked</Badge>}</div>
          {latestAction ? <><p className="sm m">Action: <b>{label(latestAction.action_type)}</b> Â· autonomy {latestAction.autonomy_level} Â· {label(latestAction.source)} Â· confidence {Math.round(latestAction.confidence * 100)}%</p>{latestAction.guardrail_notes.length ? <ul className="safety-notes">{latestAction.guardrail_notes.map((note) => <li key={note}>{note}</li>)}</ul> : <p className="sm m safety-clear">No blocking or escalation guardrail was recorded for the latest action.</p>}</> : <p className="sm m">No agent action has been recorded for this merchant yet.</p>}
          <p className="sm m safety-footnote">The agent checks consent, quiet hours, daily limits, message claims, confidence, sensitive topics, and action autonomy before acting.</p>
        </section>
        <section className="box detail-box">
          <div className="section-heading"><div><p className="eyebrow">ACTION HISTORY</p><h3>Recent decisions</h3></div></div>
          <div className="feed-space"><Feed items={actions} limit={8} /></div>
        </section>
      </div>
    </Grid>}
    {isChat && <MerchantConversation merchant={merchant} messages={messages} busy={busy} isChat onSend={onSend} onUpload={onUpload} />}
  </Shell>;
}

export function ApprovalsView({
  actions,
  autonomy,
  busy,
  onDecide,
  onAutonomyChange,
}: {
  actions: AgentAction[];
  autonomy: AutonomySettings;
  busy: boolean;
  onDecide: (id: string, approved: boolean) => void;
  onAutonomyChange: (action: string, level: string) => void;
}) {
  const pending = actions.filter((action) => action.status === "pending_approval");
  return <Shell><h2>Approvals</h2><p className="m intro">Review pending actions persisted by the agent before approving or rejecting them.</p><div className="box">{pending.map((action) => <div className="row approval-row" key={action.id}><div className="approval-copy"><b>{action.shop_name}</b> <Badge className="gy">{action.action_type}</Badge> <Badge className={levelClass(action.autonomy_level)}>{action.autonomy_level}</Badge><div className="approval-text">{action.reasoning}</div>{action.guardrail_notes.map((note) => <div className="sm m" key={note}>{note}</div>)}</div><div><button className="btn x" onClick={() => onDecide(action.id, true)} disabled={busy}>Approve</button>{" "}<button className="btn x r" onClick={() => onDecide(action.id, false)} disabled={busy}>Reject</button></div></div>)}{!pending.length && <p className="m">No actions are awaiting approval.</p>}</div>
    <h2 className="section-title">Autonomy levels</h2><p className="m intro">These values are loaded from and saved to the backend.</p><div className="box tw table-box"><table><thead><tr><th>Action</th><th>Last updated</th><th>Level</th></tr></thead><tbody>{Object.entries(autonomy).map(([action, config]) => <tr key={action}><td><b>{action}</b></td><td>{config.updated_at ? timeLabel(config.updated_at) : "Not updated"}</td><td><select aria-label={`${action} autonomy`} value={config.level} onChange={(event) => onAutonomyChange(action, event.target.value)} disabled={busy}><option>L1</option><option>L2</option><option>L3</option></select></td></tr>)}</tbody></table>{!Object.keys(autonomy).length && <p className="m empty-state">No autonomy settings were returned by the backend.</p>}</div>
  </Shell>;
}

export function HandoffsView({
  handoffs,
  busy,
  onResolve,
}: {
  handoffs: Handoff[];
  busy: boolean;
  onResolve: (id: string, note: string) => void;
}) {
  const [notes, setNotes] = useState<Record<string, string>>({});
  return <Shell><h2>Handoffs</h2><p className="m intro">Escalations from the backend agent. Add a resolution note when closing a handoff.</p>{handoffs.map((handoff) => <div className="box handoff-box" key={handoff.id}><div className="handoff-heading"><h3>{handoff.shop_name}</h3><Badge className={statusClass(handoff.status)}>{label(handoff.status)}</Badge></div><p className="sm m">{timeLabel(handoff.created_at)} Â· {handoff.target} Â· {handoff.reason}</p><p className="handoff-copy"><b>Summary.</b> {typeof handoff.summary === "string" ? handoff.summary : JSON.stringify(handoff.summary)}</p>{handoff.resolution_note && <p className="sm m"><b>Resolution:</b> {handoff.resolution_note}</p>}{handoff.status === "open" && <form className="resolve-form" onSubmit={(event) => { event.preventDefault(); const note = notes[handoff.id]?.trim(); if (note) onResolve(handoff.id, note); }}><input aria-label={`Resolution note for ${handoff.shop_name}`} value={notes[handoff.id] ?? ""} onChange={(event) => setNotes((current) => ({ ...current, [handoff.id]: event.target.value }))} placeholder="Resolution note" required /><button className="btn x" type="submit" disabled={busy || !notes[handoff.id]?.trim()}>{busy ? "Savingâ€¦" : "Resolve"}</button></form>}</div>)}{!handoffs.length && <div className="box"><p className="m">No handoffs are recorded.</p></div>}</Shell>;
}

export function ScoreboardView() {
  const metrics = [
    { title: "Leads contacted within 1 hour", change: "+280%", manual: 25, saathi: 95 },
    { title: "Lead to onboarded conversion", change: "+30%", manual: 20, saathi: 26 },
    { title: "Devices activated within 7 days", change: "+24%", manual: 38, saathi: 47 },
    { title: "Tier-1 tickets resolved without a human", change: "from none", manual: 0, saathi: 50 },
    { title: "FSE time spent on admin", change: "-50%, lower is better", manual: 50, saathi: 25 },
  ];
  return <Shell><h2>Scoreboard</h2><p className="m scoreboard-intro">Manual workflow compared with Saathi-assisted, on 300 synthetic leads over 30 days. These are simulated projections from stated assumptions, not Paytm results.</p><section className="box scoreboard-box" aria-label="Simulated workflow comparison">
    {metrics.map((metric) => <article className="score-metric" key={metric.title}>
      <div className="metric-title"><h3>{metric.title}</h3><span>{metric.change}</span></div>
      <div className="score-bar-row"><span>Manual {metric.manual}%</span><div className="score-bar" role="img" aria-label={`Manual: ${metric.manual}%`}><span className="score-bar-fill manual-fill" style={{ width: `${metric.manual}%` }} /></div></div>
      <div className="score-bar-row"><span>Saathi {metric.saathi}%</span><div className="score-bar" role="img" aria-label={`Saathi: ${metric.saathi}%`}><span className="score-bar-fill saathi-fill" style={{ width: `${metric.saathi}%` }} /></div></div>
    </article>)}
    <p className="score-assumptions"><b>Assumptions:</b> manual first contact within 1 hour 25%, Saathi 95%. Document completion after a re-request 40% manual, 60% Saathi. Same lead pool and conversion propensity in both arms.</p>
  </section></Shell>;
}

