from typing import Dict, Any
from server.simulation.engine import run_simulation
from server.db.session import SessionLocal
from server.db.models import SimRun, SimResult
from datetime import datetime, timezone

def generate_and_save_simulation(
    num_seeds: int = 30,
    population_size: int = 300,
    param_overrides: Dict[str, Any] = None
) -> Dict[str, Any]:
    sim_data = run_simulation(num_seeds, population_size, param_overrides)
    run_id = f"sim_{int(datetime.now(timezone.utc).timestamp())}"
    sim_data["run_id"] = run_id

    # Persist into DB
    db = SessionLocal()
    try:
        run_record = SimRun(
            id=run_id,
            params=sim_data["assumptions"],
            seeds=num_seeds,
            created_at=datetime.now(timezone.utc)
        )
        db.add(run_record)

        for met in sim_data["metrics"]:
            res_manual = SimResult(
                run_id=run_id,
                metric=met["name"],
                arm="manual",
                mean=met["manual"],
                ci_low=met["manual"],
                ci_high=met["manual"]
            )
            res_saathi = SimResult(
                run_id=run_id,
                metric=met["name"],
                arm="saathi",
                mean=met["saathi"],
                ci_low=met["ci_low"],
                ci_high=met["ci_high"]
            )
            db.add(res_manual)
            db.add(res_saathi)

        db.commit()
    finally:
        db.close()

    return sim_data

def print_simulation_report():
    print("\n" + "=" * 80)
    print("PAYTM SAATHI: SIMULATION REPORT (Synthetic Data Projections)")
    print("All values reflect modeled comparison under stated assumptions.")
    print("=" * 80)

    sim = generate_and_save_simulation(num_seeds=30, population_size=300)

    print(f"\nRun ID: {sim['run_id']} | Population: {sim['population']} leads | Seeds: {sim['seeds']}")
    print("-" * 80)
    print(f"{'Metric':<45} | {'Manual':<8} | {'Saathi':<8} | {'Relative Lift':<14} | {'95% CI':<12}")
    print("-" * 80)

    for m in sim["metrics"]:
        ci_str = f"[{m['ci_low']}, {m['ci_high']}]"
        lift_str = f"{m['relative_lift_pct']:+}%"
        print(f"{m['name']:<45} | {m['manual']:<8} | {m['saathi']:<8} | {lift_str:<14} | {ci_str:<12}")

    print("-" * 80)
    print("\nKey Modeling Assumptions:")
    for k, v in sim["assumptions"].items():
        print(f"  - {k}: {v}")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    print_simulation_report()

