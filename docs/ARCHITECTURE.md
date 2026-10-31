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

RAG uses Markdown policy documents under `agent/policy/docs/`. The retrieval
layer loads sections by heading, expands Hindi and Hinglish terms, ranks
passages with BM25 when available, and falls back to keyword overlap. Retrieved
passages are supplied to the reply prompt; an answer is not treated as
verified when no relevant policy passage is found.
