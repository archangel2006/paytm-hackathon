# Simulation Parameters and Assumptions
# All values represent modeling assumptions for synthetic comparison between
# Manual and Saathi-assisted merchant onboarding workflows.
# These are projections driven by stated assumptions, NOT real Paytm data.

from typing import Dict, Any

DEFAULT_ASSUMPTIONS: Dict[str, Any] = {
    # Speed of initial response to inbound / assigned leads
    "prob_contact_within_1h_manual": 0.25,      # FSE is in the field, calls late
    "prob_contact_within_1h_saathi": 0.95,      # Saathi contacts instantly via WhatsApp

    # Days from lead creation to first outbound contact
    "median_days_first_contact_manual": 2.0,
    "median_days_first_contact_saathi": 0.1,

    # Persistence of follow-ups before lead is abandoned
    "max_followups_manual": 2,                  # Manual process drops unresponsive leads quickly
    "max_followups_saathi": 4,                  # Saathi follows up up to 3-4 times within rate limits

    # Effectiveness of document collection re-requests
    "doc_completion_rate_manual": 0.40,         # Generic chase leads to application stall
    "doc_completion_rate_saathi": 0.60,         # Targeted re-request for specific document only

    # Median days to complete KYC documents
    "median_days_docs_manual": 4.0,
    "median_days_docs_saathi": 2.0,

    # Proactive Day-1 nudge sent after device install
    "activation_nudge_rate_manual": 0.15,       # Rarely monitored post-installation
    "activation_nudge_rate_saathi": 0.90,       # Automatic Day-1 transaction nudge

    # Customer service deflection of tier-1 inquiries
    "tier1_deflection_rate_manual": 0.00,       # All inquiries route to support agents
    "tier1_deflection_rate_saathi": 0.50,       # Tool-grounded policy & settlement answers

    # FSE share of time spent on admin vs visiting shops
    "fse_admin_time_manual": 0.50,              # 50% time lost on phone calls & paperwork
    "fse_admin_time_saathi": 0.25,              # 25% admin time, 75% field visits

    # Economics & Cost Inputs
    "fse_cost_per_lead": 200.0,                 # Incurred FSE salary & overhead per lead
    "agent_cost_per_lead": 15.0                 # Compute, LLM tokens, and messaging cost
}

