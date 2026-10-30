import random
import math
from typing import Dict, List, Any, Tuple
import numpy as np
from server.simulation.params import DEFAULT_ASSUMPTIONS

CATEGORIES = ["kirana", "chai stall", "salon", "pharmacy", "mobile repair", "sweet shop", "restaurant", "clothing"]

class SimulationLead:
    def __init__(self, lead_id: int, rng: random.Random):
        self.lead_id = lead_id
        self.category = rng.choice(CATEGORIES)
        # Category multiplier
        cat_mult = {
            "kirana": 1.15,
            "sweet shop": 1.10,
            "restaurant": 1.05,
            "pharmacy": 1.05,
            "salon": 0.95,
            "clothing": 0.95,
            "chai stall": 0.90,
            "mobile repair": 0.85
        }.get(self.category, 1.0)

        # Inherent propensity (identical for both arms)
        self.propensity = min(0.95, max(0.05, rng.betavariate(2.5, 5.0) * cat_mult))
        self.doc_readiness = rng.uniform(0.3, 0.9)
        self.response_speed = rng.uniform(0.2, 0.9)

def run_single_arm(
    leads: List[SimulationLead],
    arm: str,
    params: Dict[str, Any],
    rng: random.Random
) -> Dict[str, float]:
    total_leads = len(leads)
    contacted_1h = 0
    onboarded = 0
    activated_7d = 0
    tier1_tickets = 0
    tickets_deflected = 0

    p_contact_1h = params[f"prob_contact_within_1h_{arm}"]
    doc_rate = params[f"doc_completion_rate_{arm}"]
    nudge_rate = params[f"activation_nudge_rate_{arm}"]
    max_followups = params[f"max_followups_{arm}"]

    for lead in leads:
        # Step 1: Contact
        if rng.random() < p_contact_1h:
            contacted_1h += 1

        # Follow-up engagement
        contacted = False
        for attempt in range(max_followups):
            chance = lead.response_speed * (0.6 if arm == "saathi" else 0.4)
            if rng.random() < chance:
                contacted = True
                break

        if not contacted:
            continue

        # Step 2: Document collection
        effective_doc_chance = doc_rate * lead.doc_readiness * (1.2 if arm == "saathi" else 1.0)
        docs_completed = rng.random() < min(0.95, effective_doc_chance)
        if not docs_completed:
            continue

        # Step 3: Installation / Onboarding
        install_chance = lead.propensity * (1.3 if arm == "saathi" else 1.0)
        is_installed = rng.random() < min(0.95, install_chance)
        if is_installed:
            onboarded += 1

            # Step 4: Activation (10 transactions within 7 days)
            nudge_sent = rng.random() < nudge_rate
            base_act_chance = 0.35 * (lead.propensity + 0.5)
            if nudge_sent:
                base_act_chance *= (1.35 if arm == "saathi" else 1.15)

            is_activated = rng.random() < min(0.90, base_act_chance)
            if is_activated:
                activated_7d += 1

        # Service ticket generation
        if rng.random() < 0.25:
            tier1_tickets += 1
            if arm == "saathi" and rng.random() < params["tier1_deflection_rate_saathi"]:
                tickets_deflected += 1

    pct_contact_1h = (contacted_1h / total_leads) * 100.0
    pct_onboarded = (onboarded / total_leads) * 100.0
    pct_activated_7d = (activated_7d / max(1, onboarded)) * 100.0
    pct_deflected = (tickets_deflected / max(1, tier1_tickets)) * 100.0 if tier1_tickets > 0 else 0.0
    fse_admin = params[f"fse_admin_time_{arm}"] * 100.0

    # Economics
    fse_cost = total_leads * params["fse_cost_per_lead"]
    agent_cost = (total_leads * params["agent_cost_per_lead"]) if arm == "saathi" else 0.0
    cost_per_activated = (fse_cost + agent_cost) / max(1, activated_7d)

    return {
        "contact_within_1h": pct_contact_1h,
        "lead_to_onboarded_conversion": pct_onboarded,
        "activation_within_7d": pct_activated_7d,
        "tier1_deflected": pct_deflected,
        "fse_admin_time": fse_admin,
        "cost_per_activated": cost_per_activated
    }

def run_simulation(
    num_seeds: int = 30,
    population_size: int = 300,
    param_overrides: Dict[str, Any] = None
) -> Dict[str, Any]:
    params = dict(DEFAULT_ASSUMPTIONS)
    if param_overrides:
        params.update(param_overrides)

    metrics_list = [
        "contact_within_1h",
        "lead_to_onboarded_conversion",
        "activation_within_7d",
        "tier1_deflected",
        "fse_admin_time",
        "cost_per_activated"
    ]

    manual_runs = {m: [] for m in metrics_list}
    saathi_runs = {m: [] for m in metrics_list}

    for seed_idx in range(num_seeds):
        # Generate identical lead pool with seed
        rng_lead = random.Random(seed_idx + 1000)
        leads = [SimulationLead(i, rng_lead) for i in range(population_size)]

        # Run Manual arm
        rng_manual = random.Random(seed_idx + 2000)
        res_m = run_single_arm(leads, "manual", params, rng_manual)
        for m in metrics_list:
            manual_runs[m].append(res_m[m])

        # Run Saathi arm
        rng_saathi = random.Random(seed_idx + 2000)
        res_s = run_single_arm(leads, "saathi", params, rng_saathi)
        for m in metrics_list:
            saathi_runs[m].append(res_s[m])

    comparison = []
    display_names = {
        "contact_within_1h": "Leads contacted within 1 hour (%)",
        "lead_to_onboarded_conversion": "Lead-to-onboarded conversion (%)",
        "activation_within_7d": "Devices activated within 7 days (%)",
        "tier1_deflected": "Tier-1 tickets resolved without human (%)",
        "fse_admin_time": "FSE admin time share (%)",
        "cost_per_activated": "Cost per activated merchant (INR)"
    }

    for m in metrics_list:
        m_vals = np.array(manual_runs[m])
        s_vals = np.array(saathi_runs[m])

        m_mean = float(np.mean(m_vals))
        s_mean = float(np.mean(s_vals))

        s_ci_low = float(np.percentile(s_vals, 2.5))
        s_ci_high = float(np.percentile(s_vals, 97.5))

        if m == "fse_admin_time" or m == "cost_per_activated":
            rel_lift = round(((s_mean - m_mean) / m_mean) * 100, 1)
        else:
            rel_lift = round(((s_mean - m_mean) / max(0.01, m_mean)) * 100, 1)

        comparison.append({
            "name": display_names.get(m, m),
            "metric_key": m,
            "manual": round(m_mean, 1),
            "saathi": round(s_mean, 1),
            "relative_lift_pct": rel_lift,
            "ci_low": round(s_ci_low, 1),
            "ci_high": round(s_ci_high, 1)
        })

    return {
        "seeds": num_seeds,
        "population": population_size,
        "assumptions": params,
        "metrics": comparison
    }
