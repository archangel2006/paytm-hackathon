import pytest
from server.simulation.engine import run_simulation

def test_pl14_simulation_determinism():
    run1 = run_simulation(num_seeds=5, population_size=100)
    run2 = run_simulation(num_seeds=5, population_size=100)

    for m1, m2 in zip(run1["metrics"], run2["metrics"]):
        assert m1["metric_key"] == m2["metric_key"]
        assert m1["manual"] == m2["manual"], f"Determinism mismatch on {m1['name']}"
        assert m1["saathi"] == m2["saathi"], f"Determinism mismatch on {m1['name']}"

def test_pl15_simulation_sanity():
    res = run_simulation(num_seeds=10, population_size=150)
    metrics = {m["metric_key"]: m for m in res["metrics"]}

    # Contact within 1 hour: Saathi should be significantly higher
    contact = metrics["contact_within_1h"]
    assert contact["saathi"] > contact["manual"]
    assert contact["ci_low"] <= contact["saathi"] <= contact["ci_high"]

    # Lead to onboarded conversion: Saathi higher
    onboarding = metrics["lead_to_onboarded_conversion"]
    assert onboarding["saathi"] >= onboarding["manual"]

    # Activation within 7d: Saathi higher
    activation = metrics["activation_within_7d"]
    assert activation["saathi"] >= activation["manual"]

    # Tier-1 ticket deflection: Saathi > 0
    deflection = metrics["tier1_deflected"]
    assert deflection["saathi"] > 0.0

    # FSE admin time: Saathi is lower (less admin)
    admin = metrics["fse_admin_time"]
    assert admin["saathi"] < admin["manual"]

