# Paytm Saathi architecture diagrams

This document is the Mermaid source for the implemented application. Diagrams
describe the current repository structure and runtime behavior; they are not
future-state specifications.

## 1. Full application architecture

```mermaid
flowchart TB
    Browser["Browser<br/>Next.js pages and components"]
    API["FastAPI application<br/>server/main.py"]
    Routes["REST routes<br/>health, briefing, merchants, chat, documents, actions, handoffs, autonomy, scoreboard, simulation, audit, demo"]
    Stream["Live events<br/>SSE /api/stream + polling /api/events"]
    Scheduler["Scheduler + simulated clock"]
    Agent["Agent package<br/>entrypoints and core decision loop"]
    Integrations["Integrations package<br/>simulator, WhatsApp, documents"]
    Ports["Ports and boundary models<br/>agent/ports.py + integrations/ports.py"]
    Repo["SQLAlchemy repository + store adapters"]
    SQLite[("SQLite database")]
    Policy["Policy Markdown files<br/>BM25 retrieval"]
    Simulation["Simulation engine<br/>synthetic population and confidence intervals"]
    External["Optional external boundary<br/>Meta WhatsApp API + HTTPS tunnel"]

    Browser --> Routes
    Browser --> Stream
    Routes --> Agent
    Routes --> Integrations
    Routes --> Repo
    Scheduler --> Agent
    Scheduler --> Repo
    Agent --> Ports
    Integrations --> Ports
    Agent --> Policy
    Agent --> Repo
    Integrations --> Repo
    Integrations --> External
    Repo --> SQLite
    Repo --> Stream
    Repo --> Simulation
    Simulation --> Browser
```

## 2. Agent-specific detailed architecture

```mermaid
flowchart TD
    Event["Incoming message, document upload, timer, or batch trigger"]
    Entry["agent/core/entrypoint.py"]
    Context["context_builder.py<br/>load merchant context"]
    NLU["nlu.py<br/>intent, language, sentiment"]
    Lifecycle["domain/lifecycle.py<br/>legal transitions and allowed actions"]
    Scoring["core/scoring.py<br/>0-100 lead score"]
    Planner["core/planner.py<br/>next-best action"]
    LLM["core/llm_client.py<br/>structured model calls + fallback"]
    Guard["core/guardrails.py<br/>hard blocks and escalation"]
    Autonomy["core/autonomy.py<br/>L1, L2, L3"]
    Executor["core/executor.py<br/>run or hold decision"]
    Tools["tools/impl.py<br/>typed tool implementations"]
    Policy["policy/retrieval.py<br/>BM25 policy search"]
    Handoff["core/handoff.py<br/>summary and recommended next step"]
    Templates["core/templates.py<br/>approved response templates"]
    Ports["agent/ports.py<br/>Store, Channel, DocumentChecker, Clock"]
    Result["Persist result, audit, timer, state change, and event"]

    Event --> Entry --> Context
    Context --> NLU
    Context --> Scoring
    NLU --> Planner
    Lifecycle --> Planner
    Scoring --> Planner
    Planner --> LLM
    Planner --> Guard
    Guard --> Autonomy
    Guard --> Handoff
    Autonomy --> Executor
    Executor --> Tools
    Tools --> Policy
    Tools --> Templates
    Tools --> Handoff
    Tools --> Ports
    Handoff --> Ports
    Executor --> Result
    Ports --> Result
```

## 3. All project layers

```mermaid
flowchart TB
    subgraph Experience["Experience layer"]
        Pages["Home, Dashboard, Merchants, Merchant detail, Approvals, Handoffs, Scoreboard, Phone simulator"]
    end
    subgraph Transport["Transport layer"]
        HTTP["FastAPI REST and OpenAPI"]
        Live["SSE stream and polling fallback"]
        Webhook["WhatsApp webhook"]
    end
    subgraph Orchestration["Orchestration layer"]
        Main["Composition root"]
        Clock["Demo clock"]
        Jobs["Background scheduler"]
        Demo["Reset, advance, scenario, device controls"]
    end
    subgraph Intelligence["Agent intelligence layer"]
        Memory["Context builder"]
        Understand["NLU"]
        Plan["Planner"]
        Score["Lead scoring"]
    end
    subgraph Safety["Safety and control layer"]
        Rules["Lifecycle and guardrails"]
        Levels["Autonomy levels"]
        Approval["Approval queue"]
        Handoff["Human handoffs"]
        Audit["Audit trail"]
    end
    subgraph Execution["Execution layer"]
        Tooling["Typed agent tools"]
        Channels["Simulator and WhatsApp"]
        Docs["OCR, quality, PAN, mock KYC"]
        Retrieval["Policy retrieval"]
    end
    subgraph Persistence["Persistence and measurement layer"]
        Adapters["Store adapters and repository"]
        DB[("SQLite")]
        Events["Event bus"]
        Metrics["Scoreboard and simulation"]
    end

    Pages --> HTTP
    Pages --> Live
    HTTP --> Main
    Webhook --> Main
    Main --> Memory
    Jobs --> Main
    Clock --> Jobs
    Demo --> Clock
    Memory --> Understand --> Plan
    Score --> Plan
    Plan --> Rules --> Levels
    Levels --> Approval
    Rules --> Handoff
    Levels --> Tooling
    Tooling --> Channels
    Tooling --> Docs
    Tooling --> Retrieval
    Tooling --> Adapters
    Channels --> Adapters
    Docs --> Adapters
    Adapters --> DB
    Adapters --> Events --> Live
    Adapters --> Audit
    Adapters --> Metrics --> Pages
```

## 4. End-to-end user flow

```mermaid
flowchart TD
    Start["FSE opens Saathi dashboard"] --> Brief["Review briefing, ranked merchants, and live feed"]
    Brief --> Select["Open merchant 360 or phone simulator"]
    Select --> Message["Merchant sends a message or FSE triggers a scenario"]
    Message --> Context["Saathi loads context and classifies intent/language/sentiment"]
    Context --> Action["Planner proposes a lifecycle-allowed action"]
    Action --> Guard{"Guardrails and autonomy"}
    Guard -->|Blocked| Refuse["Safe response + audit reason"]
    Guard -->|Escalated| Handoff["Create handoff with summary"]
    Guard -->|L1| Suggest["Show suggestion for human action"]
    Guard -->|L2| Approve{"Approval queue"}
    Guard -->|L3| Execute["Execute typed tool"]
    Approve -->|Approve| Execute
    Approve -->|Reject/Edit| Override["Record human override"]
    Execute --> State["Update merchant state, action, message, timer, audit"]
    State --> Live["Publish live event and refresh dashboard"]
    Live --> Progress{"Activation outcome reached?"}
    Progress -->|No| Brief
    Progress -->|Yes| Outcome["Scoreboard records outcome"]
    Refuse --> Live
    Handoff --> Live
    Suggest --> Live
    Override --> Live
```

## 5. Runtime application flow

```mermaid
sequenceDiagram
    autonumber
    participant U as Merchant or FSE
    participant FE as Next.js frontend
    participant API as FastAPI route
    participant MAIN as server/main.py
    participant AG as Agent entrypoint
    participant G as Guardrails/autonomy
    participant X as Typed tool
    participant R as Store adapter/repository
    participant DB as SQLite
    participant EV as Event bus
    participant SSE as SSE/polling endpoint

    U->>FE: Open page or send simulator message
    FE->>API: HTTP request
    API->>MAIN: Resolve configured dependencies
    MAIN->>AG: Pass event to agent
    AG->>R: Load merchant context
    R->>DB: Query current state and history
    DB-->>R: Context bundle
    R-->>AG: Context bundle
    AG->>AG: NLU, lifecycle filter, scoring, planner
    AG->>G: Proposed action
    alt Blocked
        G-->>AG: Block with safe reason
    else Human handoff
        G->>X: Execute escalation tool
    else Approval required
        G-->>API: Pending approval
        API-->>FE: Approval item
        FE->>API: Approve, reject, or edit
        API->>X: Execute approved action
    else Autonomous
        G->>X: Execute L3 tool
    end
    X->>R: Persist result and audit
    R->>DB: Commit state, action, message, or handoff
    R->>EV: Publish domain event
    EV->>SSE: Fan out live event
    SSE-->>FE: Refresh affected view
    API-->>FE: Return response
    FE-->>U: Show response, status, or handoff
```

## 6. Lifecycle and activation flow

```mermaid
stateDiagram-v2
    [*] --> NEW
    NEW --> CONTACTED: intro sent
    NEW --> ENGAGED: merchant messages first
    CONTACTED --> ENGAGED: reply received
    CONTACTED --> DORMANT: retry limit reached
    ENGAGED --> DOCS_PENDING: merchant interested
    ENGAGED --> LOST: merchant declines
    DOCS_PENDING --> DOCS_VERIFIED: document pre-check passes
    DOCS_PENDING --> DORMANT: document retries exhausted
    DOCS_VERIFIED --> VISIT_SCHEDULED: visit booked
    VISIT_SCHEDULED --> INSTALLED: device installed
    INSTALLED --> ACTIVATING: first activation check
    ACTIVATING --> ACTIVATED: activation threshold reached
    ACTIVATING --> AT_RISK: nudges exhausted
    AT_RISK --> ACTIVATING: issue fixed
    DORMANT --> CONTACTED: cooldown elapsed
    ACTIVATED --> [*]
    LOST --> [*]
```

