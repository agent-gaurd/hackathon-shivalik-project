"""Project 3: Model Analytics & Decision Intelligence Backend.
FastAPI service on Port 8003.
"""
import os
import sys
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
STATIC_DIR = PROJECT_ROOT / "static"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from engine import engine

app = FastAPI(
    title="AgentGuard Project 3 — Model Analytics & Decision Intelligence",
    version="1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Upstream engine URLs for live synchronization
P1_BACKEND = os.getenv("P1_URL", "http://127.0.0.1:8001")
P2_BACKEND = os.getenv("P2_URL", "http://127.0.0.1:8002")


class SimulateRequest(BaseModel):
    scenario: str = "normal"
    count: int = 10


@app.get("/health")
def health():
    stats = engine.get_stats()
    return {
        "status": "ok",
        "service": "project3-analytics",
        "total_evaluated": stats.get("total_count", 0)
    }


@app.get("/stats")
def get_stats(engine_filter: Optional[str] = Query(None)):
    return engine.get_stats(engine_filter)


@app.get("/models")
def get_models(engine_filter: Optional[str] = Query(None)):
    return engine.get_models_analytics(engine_filter)


@app.get("/distribution")
def get_distribution(engine_filter: Optional[str] = Query(None)):
    return engine.get_score_distribution(engine_filter)


@app.get("/typologies")
def get_typologies(engine_filter: Optional[str] = Query(None)):
    return engine.get_typology_breakdown(engine_filter)


@app.get("/signals")
def get_signals(engine_filter: Optional[str] = Query(None)):
    return engine.get_signals_analytics(engine_filter)


@app.get("/timeseries")
def get_timeseries(
    engine_filter: Optional[str] = Query(None),
    points: int = Query(24, ge=6, le=60)
):
    return engine.get_timeseries(engine_filter, points)


@app.get("/transactions")
def get_transactions(
    category: Optional[str] = Query(None),
    engine_filter: Optional[str] = Query(None),
    typology: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None),
    max_score: Optional[float] = Query(None),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0)
):
    return engine.get_transactions(
        category=category,
        engine_filter=engine_filter,
        typology=typology,
        search=search,
        min_score=min_score,
        max_score=max_score,
        limit=limit,
        offset=offset
    )


@app.get("/transactions/{txn_id}")
def get_transaction_detail(txn_id: str):
    rec = engine.get_transaction_detail(txn_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return rec


@app.post("/sync")
async def sync_all():
    p1_synced = await engine.sync_from_project1(P1_BACKEND)
    p2_synced = await engine.sync_from_project2(P2_BACKEND)
    stats = engine.get_stats()
    return {
        "status": "ok",
        "synced_project1": p1_synced,
        "synced_project2": p2_synced,
        "total_records": stats.get("total_count", 0)
    }


@app.post("/simulate")
def simulate(req: SimulateRequest):
    created = engine.simulate_batch(scenario=req.scenario, count=req.count)
    return {
        "status": "ok",
        "simulated": len(created),
        "scenario": req.scenario,
        "items": created[:5]
    }


@app.post("/reset")
def reset():
    engine.reset_dataset()
    return {"status": "ok", "message": "Dataset reset to baseline seed"}


@app.get("/")
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"status": "ok", "service": "Project 3 Analytics"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8003"))
    print(f"\n   AgentGuard Project 3 running at http://localhost:{port} (Ctrl+C to stop)\n")
    uvicorn.run("main:app", host="127.0.0.1", port=port, reload=False)
