# Paytm Saathi platform users

Paytm Saathi is a two-sided platform. Merchants communicate with the Saathi
agent, while internal Paytm operations users review, approve, execute, or
resolve the resulting work.

## User and role architecture

<!-- mermaid-checked: no \n, no em-dash/en-dash, no {} in labels, subgraphs are id["label"], arrows are -->|"label"|, all subgraphs closed by end, ids unique -->
```mermaid
flowchart TD
    subgraph MerchantSide["Merchant side"]
        Merchant["Merchant"]
        MerchantWhatsApp["WhatsApp messages"]
        MerchantSimulator["Phone simulator"]
        MerchantDocuments["Document uploads"]
        MerchantQueries["Fee, device, KYC, and settlement queries"]
    end

    subgraph AgentSide["Saathi agent layer"]
        Intake["Message and event intake"]
        Context["Merchant context and memory"]
        Nlu["Intent, language, and sentiment classification"]
        Planner["Lifecycle-aware planning"]
        Rag["Policy retrieval and grounded replies"]
        Guardrails["Guardrails and safety checks"]
        Autonomy["L1 suggestion, L2 approval, L3 execution"]
        Tools["Typed tools and integrations"]
    end

    subgraph OperationsSide["Paytm operations side"]
        Fse["Field Sales Executive"]
        Support["Support Agent"]
        Manager["Operations Manager"]
        Dashboard["Operations dashboard"]
        Approvals["Approval queue"]
        Handoffs["Handoff queue"]
        Metrics["Scoreboard and audit views"]
    end

    Merchant --> MerchantWhatsApp
    Merchant --> MerchantSimulator
    Merchant --> MerchantDocuments
    Merchant --> MerchantQueries
    MerchantWhatsApp --> Intake
    MerchantSimulator --> Intake
    MerchantDocuments --> Intake
    MerchantQueries --> Intake
    Intake --> Context
    Context --> Nlu
    Nlu --> Planner
    Planner --> Rag
    Rag --> Guardrails
    Guardrails --> Autonomy
    Autonomy --> Tools
    Autonomy --> Approvals
    Autonomy --> Handoffs
    Tools --> MerchantWhatsApp
    Tools --> MerchantSimulator
    Tools --> MerchantDocuments
    Dashboard --> Fse
    Dashboard --> Support
    Dashboard --> Manager
    Approvals --> Manager
    Approvals --> Fse
    Handoffs --> Fse
    Handoffs --> Support
    Metrics --> Manager
    Fse --> Dashboard
    Support --> Dashboard
    Manager --> Dashboard
```

## User roles and responsibilities

| User or role | Side | Main responsibilities |
|---|---|---|
| Merchant | External user | Onboarding, documents, visits, device activation, support queries |
| Field Sales Executive | Internal user | Visit merchants, install devices, resolve assigned handoffs, review priorities |
| Support Agent | Internal user | Handle settlement, refund, fraud, chargeback, legal, and complex support cases |
| Operations Manager | Internal user | Approve discounts, review overrides, monitor metrics, govern autonomy |
| Saathi agent | Agent layer | Understand messages, retrieve policies, plan actions, apply guardrails, and execute bounded tools |

## Important implementation boundary

The current repository models merchants, FSE assignment, actions, approvals,
and handoffs. It does not yet implement authenticated accounts or role-based
access control for FSEs, support agents, or operations managers. The diagram
shows the intended platform user roles and the currently implemented
operational interaction surfaces.
