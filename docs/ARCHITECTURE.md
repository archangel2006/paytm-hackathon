# Paytm Saathi architecture diagrams

These diagrams describe the implemented platform and its agentic decision
loop. They show the layers and responsibilities from an incoming event to a
response, action, handoff, or persisted result.

## Full platform architecture

<!-- mermaid-checked: no \n, no em-dash/en-dash, no {} in labels, subgraphs are id["label"], arrows are -->|"label"|, all subgraphs closed by end, ids unique -->
```mermaid
flowchart TD
    subgraph Experience["Experience layer"]
        Frontend["Next.js dashboard and simulator"]
        MerchantViews["Merchant, approvals, handoffs, scoreboard views"]
    end
    subgraph Channels["Channel and intake layer"]
        Rest["FastAPI REST and OpenAPI"]
        WhatsApp["WhatsApp webhook and outbound client"]
        Simulator["Phone simulator"]
        Uploads["Document and media uploads"]
        Timers["Scheduler and timer events"]
    end
    subgraph Composition["Application composition layer"]
        Main["Application composition root"]
        Ports["Typed ports and boundary models"]
        Clock["Real or simulated clock"]
    end
    subgraph Context["Context layer"]
        ContextBuilder["Merchant context builder"]
        Memory["Messages, lifecycle, documents, visits, settlements, tickets"]
        Score["Lead scoring"]
    end
    subgraph Understanding["Understanding layer"]
        Intent["Intent classification"]
        Language["Language detection"]
        Sentiment["Sentiment and human request detection"]
        LlmNlu["LLM classification for ambiguous language"]
    end
    subgraph Decision["Decision layer"]
        Lifecycle["Lifecycle rules and allowed actions"]
        Planner["Next best action planner"]
        LlmPlanner["LLM planner for unresolved decisions"]
    end
    subgraph Knowledge["Grounding layer"]
        Query["Policy query construction"]
        Retrieval["BM25 or keyword policy retrieval"]
        PolicyDocs["Markdown policy documents"]
        Reply["Grounded reply generation"]
    end
    subgraph Control["Safety and autonomy layer"]
        Guardrails["Consent, quiet hours, limits, confidence, claim checks"]
        Autonomy["L1 suggestion, L2 approval, L3 execution"]
        Approval["Approval queue"]
        Handoff["Human handoff and summary"]
    end
    subgraph Execution["Tool execution layer"]
        ToolContext["Get lead context"]
        ToolMessage["Send simulator or WhatsApp message"]
        ToolDocument["Validate document and mock KYC"]
        ToolVisit["Schedule field visit"]
        ToolSettlement["Check settlement"]
        ToolPolicy["Search policy"]
        ToolEscalate["Escalate to human"]
    end
    subgraph Integration["Integration layer"]
        Meta["Meta WhatsApp API"]
        DocumentServices["OCR, quality checks, PAN checks, mock KYC"]
        Outbound["Channel router and retry handling"]
    end
    subgraph Persistence["Persistence and observability layer"]
        Adapters["Agent and integration store adapters"]
        Database[("SQLite platform data")]
        Events["Event bus, SSE, polling"]
        Audit["Actions, audit logs, handoffs, timers"]
        Metrics["Scoreboard and simulation metrics"]
    end

    Frontend --> Rest
    MerchantViews --> Rest
    Frontend --> Simulator
    WhatsApp --> Main
    Simulator --> Rest
    Uploads --> Rest
    Timers --> Main
    Rest --> Main
    Main --> Ports
    Main --> ContextBuilder
    Ports --> ContextBuilder
    ContextBuilder --> Memory
    Memory --> Score
    ContextBuilder --> Intent
    Intent --> Language
    Language --> Sentiment
    Sentiment --> LlmNlu
    LlmNlu --> Planner
    Score --> Planner
    Lifecycle --> Planner
    Planner --> LlmPlanner
    LlmPlanner --> Query
    Query --> Retrieval
    PolicyDocs --> Retrieval
    Retrieval --> Reply
    Reply --> Guardrails
    Planner --> Guardrails
    Guardrails --> Autonomy
    Autonomy --> Approval
    Autonomy --> Handoff
    Autonomy --> ToolContext
    Autonomy --> ToolMessage
    Autonomy --> ToolDocument
    Autonomy --> ToolVisit
    Autonomy --> ToolSettlement
    Autonomy --> ToolPolicy
    Autonomy --> ToolEscalate
    ToolMessage --> Outbound
    Outbound --> Meta
    ToolDocument --> DocumentServices
    ToolContext --> Adapters
    ToolMessage --> Adapters
    ToolDocument --> Adapters
    ToolVisit --> Adapters
    ToolSettlement --> Adapters
    ToolPolicy --> Retrieval
    ToolEscalate --> Handoff
    Approval --> Adapters
    Handoff --> Adapters
    Adapters --> Database
    Adapters --> Audit
    Adapters --> Events
    Adapters --> Metrics
    Events --> Frontend
    Metrics --> MerchantViews
```

## Agent decision loop

<!-- mermaid-checked: no \n, no em-dash/en-dash, no {} in labels, subgraphs are id["label"], arrows are -->|"label"|, all subgraphs closed by end, ids unique -->
```mermaid
flowchart TD
    Event["Incoming message, media, timer, batch, or preview event"]
    Entrypoint["Agent entrypoint"]
    Bundle["Load merchant context bundle"]
    ContextModel["Build context model"]
    NluStage["NLU classification"]
    IntentNode["Intent"]
    LanguageNode["Language"]
    SentimentNode["Sentiment"]
    HumanNode["Human request and money detection"]
    ScoreNode["Lead score update"]
    LifecycleNode["Lifecycle state and legal actions"]
    PlannerNode["Planner"]
    RulesNode["Rule based decision"]
    PlannerModel["LLM structured planning"]
    FallbackNode["Fallback escalation"]
    RAGQuery["Build policy search query"]
    RAGSearch["Retrieve relevant passages"]
    RAGDocs["Policy Markdown documents"]
    GroundedReply["Generate grounded reply"]
    GuardNode["Guardrails evaluation"]
    ConsentNode["Consent and quiet hours"]
    ClaimNode["Confidence and claim validation"]
    AutonomyNode["Resolve autonomy level"]
    L1Node["L1 suggestion"]
    L2Node["L2 pending approval"]
    L3Node["L3 executable action"]
    ToolNode["Typed tool execution"]
    ToolSet["Context, message, document, visit, settlement, policy, escalation"]
    HandoffNode["Create human handoff"]
    PersistNode["Persist action, result, state, timer, and audit"]
    ResponseNode["Response through simulator or WhatsApp"]
    EventNode["Publish event to dashboard"]

    Event --> Entrypoint
    Entrypoint --> Bundle
    Bundle --> ContextModel
    ContextModel --> NluStage
    NluStage --> IntentNode
    IntentNode --> LanguageNode
    LanguageNode --> SentimentNode
    SentimentNode --> HumanNode
    ContextModel --> ScoreNode
    HumanNode --> LifecycleNode
    ScoreNode --> LifecycleNode
    LifecycleNode --> PlannerNode
    PlannerNode --> RulesNode
    RulesNode --> PlannerModel
    PlannerModel --> FallbackNode
    PlannerModel --> RAGQuery
    RAGQuery --> RAGSearch
    RAGDocs --> RAGSearch
    RAGSearch --> GroundedReply
    GroundedReply --> GuardNode
    FallbackNode --> GuardNode
    PlannerNode --> GuardNode
    GuardNode --> ConsentNode
    ConsentNode --> ClaimNode
    ClaimNode --> AutonomyNode
    AutonomyNode --> L1Node
    AutonomyNode --> L2Node
    AutonomyNode --> L3Node
    AutonomyNode --> HandoffNode
    L1Node --> PersistNode
    L2Node --> PersistNode
    L3Node --> ToolNode
    ToolNode --> ToolSet
    ToolSet --> PersistNode
    HandoffNode --> PersistNode
    PersistNode --> ResponseNode
    PersistNode --> EventNode
    EventNode --> ResponseNode
```

### Intents classified by NLU

The NLU layer classifies each incoming text message into one of these
implemented intents. It also emits language, sentiment, human-request,
money-mention, and confidence signals.

| Intent | Meaning | Typical planner result |
|---|---|---|
| `greeting` | Greeting or opening message | `ANSWER_QUERY` |
| `interest` | Product interest or request for more information | `ANSWER_QUERY` |
| `ask_fees` | Fees, rental, MDR, pricing, or charges | `ANSWER_QUERY` |
| `ask_documents` | Required documents or KYC requirements | `ANSWER_QUERY` |
| `send_document` | Merchant indicates that a document was sent | Document validation flow |
| `agree_visit` | Merchant agrees to or confirms a visit | `SCHEDULE_VISIT` |
| `settlement_query` | Settlement status, missing payment, or settlement timing | `EXPLAIN_SETTLEMENT` or support handoff |
| `device_issue` | Soundbox, QR, battery, network, or device problem | Planner or support handoff |
| `complaint` | Complaint, fraud, refund, chargeback, or legal concern | FSE or support handoff |
| `ask_discount` | Discount, waiver, reduced fee, or free request | `OFFER_DISCOUNT` with approval |
| `ask_human` | Explicit request for manager, FSE, or human | FSE handoff |
| `opt_out` | Stop, unsubscribe, or do-not-contact request | `WAIT` and outbound pause |
| `not_interested` | Declines the offer or says no | `WAIT` or lifecycle close |
| `other` | No supported intent match | `ESCALATE` for unsupported question |

### Planner actions and autonomy

The planner can select these structured actions. Lifecycle rules filter the
actions that are legal for the merchant's current state before execution.

| Planner action | What it does | Default control |
|---|---|---|
| `SEND_INTRO` | Starts outreach to a new lead | L3 when permitted |
| `ANSWER_QUERY` | Sends a policy-grounded response | L3 when permitted |
| `REQUEST_DOCS` | Requests PAN or address proof | L3 when permitted |
| `REREQUEST_DOC` | Requests a corrected document with specific issues | L3 when permitted |
| `SCHEDULE_VISIT` | Creates a clustered FSE visit slot | L3 when permitted |
| `SEND_ACTIVATION_NUDGE` | Nudges an installed but inactive merchant | L3 when permitted |
| `EXPLAIN_SETTLEMENT` | Looks up and explains settlement status | L3 when data exists |
| `WAIT` | Pauses messaging or waits for a future event | L3 when permitted |
| `ESCALATE` | Creates a human handoff with context | L3 handoff creation |
| `CLOSE_LEAD` | Marks a lead as closed after human-controlled review | L1 suggestion |
| `OFFER_DISCOUNT` | Proposes a discount request without changing price | L2 approval |

### Typed tools available to the agent

The model does not call tools directly. The executor invokes these typed,
wrapped functions after planning, guardrail evaluation, and autonomy checks.

| Tool | Inputs or lookup | Result |
|---|---|---|
| `get_lead_context` | Merchant ID | Current context bundle for the merchant |
| `send_whatsapp` | Merchant ID, text, language, optional template | Outbound simulator or WhatsApp send result |
| `validate_kyc_doc` | Document, merchant, file path, document type | Quality/PAN/name pre-check and mock KYC result |
| `schedule_visit` | Merchant ID and optional preferred slot | FSE, slot, cluster size, and lifecycle update |
| `check_settlement` | Merchant ID | Current settlement record or not-found result |
| `search_policy` | Query and language | Ranked policy passages with source and score |
| `escalate_to_human` | Merchant, action, target, reason, decision | Handoff ID and structured handoff summary |

## Layer responsibilities

| Layer | Responsibility | Current implementation |
|---|---|---|
| Experience | Operator and simulator views | Next.js frontend |
| Channel and intake | Receive messages, uploads, and scheduled events | FastAPI, WhatsApp webhook, simulator |
| Composition | Wire ports, adapters, clock, and handlers | `server/main.py` |
| Context | Build merchant memory and lead score | `context_builder.py`, `scoring.py` |
| Understanding | Convert language into structured signals | `nlu.py` |
| Decision | Select lifecycle-allowed next action | `lifecycle.py`, `planner.py` |
| Grounding | Retrieve verified policy passages and draft replies | `policy/retrieval.py`, reply prompt |
| Safety and autonomy | Block, escalate, request approval, or permit execution | `guardrails.py`, `autonomy.py` |
| Tools | Perform bounded business operations | `agent/tools/impl.py` |
| Integration | Connect channels and document services | `integrations/` |
| Persistence | Store state, actions, events, and measurements | SQLAlchemy adapters and SQLite |

## RAG knowledge sources

RAG uses the following actual Markdown documents under `agent/policy/docs/`.
The retriever loads each `##` and `###` section as a passage, expands Hindi
and Hinglish terms, ranks passages with BM25 when available, and falls back to
keyword overlap. The selected passages are passed to the reply-generation
prompt with their source labels.

| Document | Policy topics retrieved |
|---|---|
| [`fees.md`](../agent/policy/docs/fees.md) | Soundbox rental, UPI charges, card MDR, settlement timing, refunds, deposit, fee support |
| [`settlement.md`](../agent/policy/docs/settlement.md) | Settlement schedule, status checks, holiday delays, delay reasons, minimum amount, failed settlement, TDS |
| [`kyc_requirements.md`](../agent/policy/docs/kyc_requirements.md) | PAN, address proof, quality requirements, file limits, pre-check boundaries, rejection reasons |
| [`device_faq.md`](../agent/policy/docs/device_faq.md) | Soundbox setup, payment announcements, connectivity, QR, battery, charging, maintenance |
| [`escalation_policy.md`](../agent/policy/docs/escalation_policy.md) | Hard blocks, escalation triggers, handoff targets, handoff contents, response expectations |

For `ANSWER_QUERY`, the entrypoint calls policy retrieval using the merchant's
original question. If no passage passes the configured retrieval threshold,
the current implementation does not claim a verified answer and changes the
decision to a support escalation.
