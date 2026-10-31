# Paytm Saathi agent architecture

This document is the detailed agentic architecture for the implemented Paytm
Saathi platform. It focuses on the agent loop rather than API endpoints:
understanding, context, planning, retrieval, guardrails, autonomy, tools,
handoffs, persistence, and channel responses.

## Complete top-to-bottom agent architecture

<!-- mermaid-checked: no \n, no em-dash/en-dash, no {} in labels, subgraphs are id["label"], arrows are -->|"label"|, all subgraphs closed by end, ids unique -->
```mermaid
flowchart TD
    subgraph Intake["1. Event intake"]
        Message["Merchant message"]
        Media["Document or media event"]
        Timer["Timer event"]
        Batch["Batch or preview event"]
    end

    subgraph Channels["2. Channel boundary"]
        Simulator["Phone simulator"]
        WhatsApp["WhatsApp webhook"]
        WebApi["FastAPI chat and control routes"]
        Parsed["Parsed incoming event"]
    end

    subgraph Entry["3. Agent entrypoint"]
        Idempotency["Check event idempotency"]
        MerchantLookup["Find or create merchant"]
        SaveInbound["Save inbound message"]
        AgentLoop["agent.handle_incoming"]
    end

    subgraph Context["4. Merchant context and memory"]
        ContextBundle["Load context bundle"]
        MerchantState["Lifecycle state"]
        MessageHistory["Recent messages and actions"]
        Documents["Document verification status"]
        Visits["Visits and FSE information"]
        Activity["Transactions and settlement data"]
        ContextModel["Build context model"]
        LeadScore["Calculate lead score"]
    end

    subgraph Nlu["5. Natural language understanding"]
        KeywordNlu["Keyword classification"]
        LlmNlu["LLM classification for ambiguity"]
        Intent["Intent classification"]
        Language["Hindi, Hinglish, or English"]
        Sentiment["Sentiment score"]
        HumanRequest["Human request detection"]
        MoneyMention["Money mention detection"]
        NluConfidence["NLU confidence"]
    end

    subgraph Planning["6. Planning and lifecycle policy"]
        AllowedActions["Lifecycle allowed actions"]
        RulePlanner["Rule first planner"]
        LlmPlanner["Structured LLM planner"]
        PlannerFallback["Fallback escalation"]
        ActionDecision["Planner decision"]
        ActionParams["Action parameters and reasoning"]
    end

    subgraph Retrieval["7. RAG and response grounding"]
        QueryBuild["Build query from merchant message"]
        Synonyms["Hindi and Hinglish synonym expansion"]
        Bm25["BM25 ranking"]
        KeywordSearch["Keyword overlap fallback"]
        PolicyPassages["Ranked policy passages"]
        ReplyPrompt["Grounded reply prompt"]
        ReplyText["Draft response text"]
        NoPolicy["No verified passage"]
    end

    subgraph Safety["8. Guardrails and autonomy"]
        Consent["Consent and opt out"]
        QuietHours["Quiet hours and rate limits"]
        ClaimCheck["Numerical and date claim checks"]
        Sensitive["Sensitive topic checks"]
        Confidence["Confidence and sentiment checks"]
        GuardrailDecision["Guardrail verdict"]
        L1["L1 suggestion only"]
        L2["L2 pending human approval"]
        L3["L3 bounded execution"]
        Blocked["Blocked response"]
    end

    subgraph Tools["9. Typed tool execution"]
        ContextTool["get_lead_context"]
        MessageTool["send_whatsapp"]
        DocumentTool["validate_kyc_doc"]
        VisitTool["schedule_visit"]
        SettlementTool["check_settlement"]
        PolicyTool["search_policy"]
        EscalationTool["escalate_to_human"]
        ToolResult["Validated tool result"]
    end

    subgraph Handoff["10. Human control"]
        ApprovalQueue["Approval queue"]
        HumanEdit["Approve, reject, or edit"]
        HandoffSummary["Structured handoff summary"]
        Fse["FSE handoff"]
        Support["Support handoff"]
    end

    subgraph Integrations["11. External and document integrations"]
        ChannelRouter["Channel router"]
        MetaApi["Meta WhatsApp API"]
        Ocr["OCR and image quality checks"]
        MockKyc["Mock KYC submission"]
        VisitPlanner["Clustered visit planning"]
    end

    subgraph Persistence["12. State, audit, and observability"]
        StoreAdapter["Agent and integration store adapters"]
        Sqlite[("SQLite database")]
        Actions["Agent actions and statuses"]
        Audit["Audit logs and guardrail notes"]
        Handoffs["Handoff records"]
        TimerStore["Follow up and activation timers"]
        EventBus["Event bus"]
        LiveStream["SSE stream and polling"]
        Scoreboard["Scoreboard and simulation metrics"]
    end

    subgraph Response["13. Response and feedback"]
        Outbound["Outbound message"]
        Dashboard["Dashboard and merchant views"]
        HumanOutcome["Human outcome or override"]
        NextEvent["Next message or timer"]
    end

    Message --> Simulator
    Message --> WhatsApp
    Media --> Simulator
    Media --> WhatsApp
    Timer --> WebApi
    Batch --> WebApi
    Simulator --> WebApi
    WhatsApp --> Parsed
    WebApi --> Parsed
    Parsed --> Idempotency
    Idempotency --> MerchantLookup
    MerchantLookup --> SaveInbound
    SaveInbound --> AgentLoop
    AgentLoop --> ContextBundle
    ContextBundle --> MerchantState
    ContextBundle --> MessageHistory
    ContextBundle --> Documents
    ContextBundle --> Visits
    ContextBundle --> Activity
    MerchantState --> ContextModel
    MessageHistory --> ContextModel
    Documents --> ContextModel
    Visits --> ContextModel
    Activity --> ContextModel
    ContextModel --> LeadScore
    ContextModel --> KeywordNlu
    KeywordNlu --> LlmNlu
    LlmNlu --> Intent
    LlmNlu --> Language
    LlmNlu --> Sentiment
    LlmNlu --> HumanRequest
    LlmNlu --> MoneyMention
    LlmNlu --> NluConfidence
    ContextModel --> AllowedActions
    Intent --> RulePlanner
    Language --> RulePlanner
    Sentiment --> RulePlanner
    HumanRequest --> RulePlanner
    LeadScore --> RulePlanner
    AllowedActions --> RulePlanner
    RulePlanner --> LlmPlanner
    LlmPlanner --> PlannerFallback
    RulePlanner --> ActionDecision
    LlmPlanner --> ActionDecision
    PlannerFallback --> ActionDecision
    ActionDecision --> ActionParams
    ActionDecision --> QueryBuild
    QueryBuild --> Synonyms
    Synonyms --> Bm25
    Synonyms --> KeywordSearch
    Bm25 --> PolicyPassages
    KeywordSearch --> PolicyPassages
    PolicyPassages --> ReplyPrompt
    ReplyPrompt --> ReplyText
    QueryBuild --> NoPolicy
    ReplyText --> Consent
    NoPolicy --> GuardrailDecision
    ActionParams --> GuardrailDecision
    Consent --> QuietHours
    QuietHours --> ClaimCheck
    ClaimCheck --> Sensitive
    Sensitive --> Confidence
    Confidence --> GuardrailDecision
    GuardrailDecision --> L1
    GuardrailDecision --> L2
    GuardrailDecision --> L3
    GuardrailDecision --> Blocked
    L1 --> Actions
    L2 --> ApprovalQueue
    ApprovalQueue --> HumanEdit
    HumanEdit --> L3
    HumanEdit --> Actions
    L3 --> ContextTool
    L3 --> MessageTool
    L3 --> DocumentTool
    L3 --> VisitTool
    L3 --> SettlementTool
    L3 --> PolicyTool
    L3 --> EscalationTool
    ContextTool --> ToolResult
    MessageTool --> ToolResult
    DocumentTool --> ToolResult
    VisitTool --> ToolResult
    SettlementTool --> ToolResult
    PolicyTool --> ToolResult
    EscalationTool --> ToolResult
    DocumentTool --> Ocr
    DocumentTool --> MockKyc
    VisitTool --> VisitPlanner
    MessageTool --> ChannelRouter
    ChannelRouter --> MetaApi
    EscalationTool --> HandoffSummary
    HandoffSummary --> Fse
    HandoffSummary --> Support
    Fse --> Handoffs
    Support --> Handoffs
    ToolResult --> StoreAdapter
    Blocked --> StoreAdapter
    Actions --> StoreAdapter
    Handoffs --> StoreAdapter
    StoreAdapter --> Sqlite
    StoreAdapter --> Audit
    StoreAdapter --> TimerStore
    StoreAdapter --> EventBus
    StoreAdapter --> Scoreboard
    EventBus --> LiveStream
    LiveStream --> Dashboard
    ChannelRouter --> Outbound
    Outbound --> NextEvent
    StoreAdapter --> Dashboard
    HumanOutcome --> StoreAdapter
    Dashboard --> HumanOutcome
    NextEvent --> AgentLoop
```

## Intent inventory

| Intent | Description | Main route |
|---|---|---|
| `greeting` | Greeting or opening message | `ANSWER_QUERY` |
| `interest` | Product interest or more information | `ANSWER_QUERY` |
| `ask_fees` | Fees, rental, MDR, pricing, or charges | `ANSWER_QUERY` |
| `ask_documents` | Required documents or KYC requirements | `ANSWER_QUERY` |
| `send_document` | Merchant says a document was sent | Document validation |
| `agree_visit` | Merchant agrees to a visit | `SCHEDULE_VISIT` |
| `settlement_query` | Settlement status or missing payment | `EXPLAIN_SETTLEMENT` or escalation |
| `device_issue` | Soundbox, QR, battery, or network issue | Answer or escalation |
| `complaint` | Complaint, fraud, refund, chargeback, or legal concern | FSE or support escalation |
| `ask_discount` | Discount, waiver, or reduced fee request | `OFFER_DISCOUNT` |
| `ask_human` | Manager, FSE, or human request | Human escalation |
| `opt_out` | Stop or unsubscribe request | `WAIT` and pause outbound |
| `not_interested` | Declines the offer | `WAIT` or close suggestion |
| `other` | Unsupported or unmatched question | `ESCALATE` |

## Planner actions and autonomy

| Action | Purpose | Control |
|---|---|---|
| `SEND_INTRO` | Start outreach to a new lead | L3 when allowed |
| `ANSWER_QUERY` | Send a grounded policy answer | L3 when allowed |
| `REQUEST_DOCS` | Request PAN or address proof | L3 when allowed |
| `REREQUEST_DOC` | Request a corrected document | L3 when allowed |
| `SCHEDULE_VISIT` | Create an FSE visit slot | L3 when allowed |
| `SEND_ACTIVATION_NUDGE` | Nudge an inactive installed device | L3 when allowed |
| `EXPLAIN_SETTLEMENT` | Check and explain settlement data | L3 when data exists |
| `WAIT` | Pause or schedule a future follow-up | L3 when allowed |
| `ESCALATE` | Create a human handoff | Handoff action |
| `CLOSE_LEAD` | Suggest lead closure | L1 |
| `OFFER_DISCOUNT` | Propose discount without changing price | L2 |

## Typed tools

| Tool | Responsibility | Main output |
|---|---|---|
| `get_lead_context` | Load current merchant context | Context bundle |
| `send_whatsapp` | Send simulator or WhatsApp message | Send result |
| `validate_kyc_doc` | Run document quality and mock KYC checks | Validation result |
| `schedule_visit` | Plan clustered FSE visit | Visit and slot |
| `check_settlement` | Look up settlement record | Settlement result |
| `search_policy` | Retrieve ranked policy passages | Sources and scores |
| `escalate_to_human` | Create a human handoff | Handoff ID and summary |

## RAG policy documents

| File | Retrieved policy areas |
|---|---|
| [`fees.md`](../agent/policy/docs/fees.md) | Soundbox rental, UPI charges, card MDR, refunds, deposits, fee support |
| [`settlement.md`](../agent/policy/docs/settlement.md) | Settlement timing, holidays, delays, minimum amount, failed settlement, TDS |
| [`kyc_requirements.md`](../agent/policy/docs/kyc_requirements.md) | PAN, address proof, image quality, file limits, pre-check boundaries |
| [`device_faq.md`](../agent/policy/docs/device_faq.md) | Setup, payment announcements, connectivity, QR, battery, charging, maintenance |
| [`escalation_policy.md`](../agent/policy/docs/escalation_policy.md) | Hard blocks, escalation triggers, handoff targets, response expectations |

Retrieval splits Markdown sections into passages, expands Hindi and Hinglish
terms, ranks with BM25 when installed, and falls back to keyword overlap. If
no passage meets the configured threshold, the current implementation routes
the query to support escalation instead of presenting an unverified answer.

## Layer responsibility table

| Layer | Responsibility | Implementation |
|---|---|---|
| Intake | Receive messages, media, timers, and batch events | Simulator, WhatsApp, FastAPI |
| Entry | Enforce idempotency and invoke the agent loop | `agent/core/entrypoint.py` |
| Context | Build merchant memory and lead score | `context_builder.py`, `scoring.py` |
| NLU | Classify intent and language signals | `nlu.py` |
| Planning | Select a lifecycle-legal next action | `lifecycle.py`, `planner.py` |
| RAG | Retrieve policy and generate grounded replies | `policy/retrieval.py`, reply prompt |
| Safety | Check consent, claims, confidence, and risk | `guardrails.py` |
| Autonomy | Resolve L1, L2, or L3 execution | `autonomy.py` |
| Tools | Perform bounded operations | `agent/tools/impl.py` |
| Human control | Approval and structured handoffs | Approval routes and handoff tool |
| Persistence | Save state, actions, audit, timers, and events | Store adapters and SQLite |
| Response | Send messages and refresh operator views | Channel router, SSE, polling |
