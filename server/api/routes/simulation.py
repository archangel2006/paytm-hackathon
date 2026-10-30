from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from server.db.session import get_db
from server.api.deps import APIError
from server.db.models import SimRun, SimResult
from server.simulation.report import generate_and_save_simulation

router = APIRouter(prefix="/simulation", tags=["simulation"])

class SimulationRunRequest(BaseModel):
    seeds: Optional[int] = 30
    population: Optional[int] = 300
    param_overrides: Optional[Dict[str, Any]] = None

@router.post("/run")
def trigger_simulation(req: SimulationRunRequest):
    data = generate_and_save_simulation(
        num_seeds=req.seeds or 30,
        population_size=req.population or 300,
        param_overrides=req.param_overrides
    )
    return data

@router.get("/{run_id}")
def get_simulation_run(run_id: str, db: Session = Depends(get_db)):
    run = db.query(SimRun).filter(SimRun.id == run_id).first()
    if not run:
        raise APIError("NOT_FOUND", f"Simulation run {run_id} not found", status_code=404)

    results = db.query(SimResult).filter(SimResult.run_id == run_id).all()
    # Group by metric
    metrics_map = {}
    for r in results:
        if r.metric not in metrics_map:
            metrics_map[r.metric] = {"name": r.metric, "manual": 0.0, "saathi": 0.0, "ci_low": 0.0, "ci_high": 0.0}
        if r.arm == "manual":
            metrics_map[r.metric]["manual"] = r.mean
        else:
            metrics_map[r.metric]["saathi"] = r.mean
            metrics_map[r.metric]["ci_low"] = r.ci_low
            metrics_map[r.metric]["ci_high"] = r.ci_high

    metrics_list = []
    for m in metrics_map.values():
        manual = m["manual"]
        saathi = m["saathi"]
        rel_lift = round(((saathi - manual) / max(0.01, manual)) * 100, 1) if manual > 0 else 0.0
        m["relative_lift_pct"] = rel_lift
        metrics_list.append(m)

    return {
        "run_id": run.id,
        "seeds": run.seeds,
        "assumptions": run.params,
        "metrics": metrics_list,
        "created_at": run.created_at.isoformat()
    }

