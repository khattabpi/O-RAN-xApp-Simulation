import asyncio
import random
import time
from datetime import datetime, timezone
from typing import Dict, List

import structlog
from fastapi import FastAPI, HTTPException, Query ,Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Gauge, make_asgi_app , generate_latest
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

# ---------------------------------------------------------------------------
# Configuration — override via environment variables (K8s ConfigMap / Secret)
# e.g. RAN_INITIAL_UES=30, RAN_MAX_UES=150
# ---------------------------------------------------------------------------
class Settings(BaseSettings):
    initial_ues: int = 20
    initial_prb: float = 40.0
    max_ues: int = 200
    noise_range: float = 5.0
    # Bandwidth class → number of PRBs (5G NR reference values)
    bandwidth_mhz: int = 20          # 10 | 20 | 100
    slots_per_second: int = 2000     # 5G NR numerology 1 → 2000 slots/s

    class Config:
        env_prefix = "RAN_"

settings = Settings()

# Bits-per-PRB lookup keyed by CQI (index 1-15, 3GPP TS 38.214 Table 5.2.2.1-3)
CQI_BITS_PER_RE = {
    1: 0.1523, 2: 0.2344, 3: 0.3770, 4: 0.6016, 5: 0.8770,
    6: 1.1758, 7: 1.4766, 8: 1.9141, 9: 2.4063, 10: 2.7305,
    11: 3.3223, 12: 3.9023, 13: 4.5234, 14: 5.1152, 15: 5.5547,
}
# Approx REs per PRB per slot (12 subcarriers × 14 OFDM symbols, minus DMRS overhead)
RES_PER_PRB_PER_SLOT = 156
BANDWIDTH_PRB_COUNT = {10: 52, 20: 106, 100: 132}

# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Prometheus Gauges  (labels include cell_id for per-cell dashboards)
# ---------------------------------------------------------------------------
prb_gauge        = Gauge("ran_prb_utilization_percent", "PRB utilization %",     ["cell_id"])
ues_gauge        = Gauge("ran_active_ues",               "Active UE count",       ["cell_id"])
cqi_gauge        = Gauge("ran_avg_cqi",                  "Average CQI (1-15)",    ["cell_id"])
throughput_gauge = Gauge("ran_throughput_mbps",          "Estimated throughput",  ["cell_id"])

# ---------------------------------------------------------------------------
# Per-cell state  (isolated so cell-A and cell-B never share data)
# ---------------------------------------------------------------------------
class CellState:
    def __init__(self):
        self.prb_utilization: float = settings.initial_prb
        self.active_ues: int       = settings.initial_ues
        self.lock: asyncio.Lock    = asyncio.Lock()

    def reset(self):
        self.prb_utilization = settings.initial_prb
        self.active_ues      = settings.initial_ues

cell_registry: Dict[str, CellState] = {}

def get_or_create_cell(cell_id: str) -> CellState:
    if cell_id not in cell_registry:
        cell_registry[cell_id] = CellState()
        logger.info("cell_registered", cell_id=cell_id)
    return cell_registry[cell_id]

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class CellMetrics(BaseModel):
    cell_id:          str
    timestamp:        str           # UTC ISO-8601 (Grafana-compatible)
    prb_utilization:  float = Field(..., ge=0.0, le=100.0, description="PRB utilization %")
    active_ues:       int   = Field(..., ge=0,   le=200,   description="Active UEs")
    avg_cqi:          float = Field(..., ge=1.0, le=15.0,  description="Channel Quality Indicator")
    throughput_mbps:  float = Field(..., ge=0.0,           description="Estimated throughput Mbps")

class ScaleResponse(BaseModel):
    status:          str
    cell_id:         str
    action:          str
    new_multiplier:  float
    new_prb:         float

class ResetResponse(BaseModel):
    status:  str
    cells:   List[str]

class HealthResponse(BaseModel):
    status:            str
    cells_initialized: int
    uptime_seconds:    float

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Simulated RAN Metrics API",
    description="O-RAN xApp simulation — metrics, control actions, and RL reset support.",
    version="1.1.0",
)

# CORS — allow the RL agent pod and Prometheus scraper (tighten origins in prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Replace with specific service URLs in production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Mount Prometheus scrape endpoint at /metrics
# app.mount("/metrics", make_asgi_app())
@app.get("/metrics", tags=["ops"])
def get_prometheus_metrics():
    """Endpoint for Prometheus to scrape."""
    return Response(content=generate_latest(), media_type="text/plain")
_start_time = time.time()

# ---------------------------------------------------------------------------
# Helper: compute metrics from cell state  (pure, no I/O)
# ---------------------------------------------------------------------------
def _compute_metrics(cell_id: str, state: CellState) -> CellMetrics:
    n_prbs     = BANDWIDTH_PRB_COUNT.get(settings.bandwidth_mhz, 106)
    cqi_int    = max(1, min(15, round(
        15.0 - (state.prb_utilization / 10.0) + random.uniform(-1.0, 1.0)
    )))
    bits_per_re   = CQI_BITS_PER_RE[cqi_int]
    used_prbs     = n_prbs * (state.prb_utilization / 100.0)
    throughput    = (used_prbs * RES_PER_PRB_PER_SLOT * bits_per_re
                     * settings.slots_per_second) / 1e6   # → Mbps

    return CellMetrics(
        cell_id          = cell_id,
        timestamp        = datetime.now(timezone.utc).isoformat(),
        prb_utilization  = round(state.prb_utilization, 2),
        active_ues       = state.active_ues,
        avg_cqi          = round(float(cqi_int), 1),
        throughput_mbps  = round(throughput, 2),
    )

# ---------------------------------------------------------------------------
# Lifecycle events
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def on_startup():
    logger.info("metrics_api_started", bandwidth_mhz=settings.bandwidth_mhz,
                initial_ues=settings.initial_ues)

@app.on_event("shutdown")
async def on_shutdown():
    logger.info("metrics_api_stopped")

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

# -- Health / readiness (required by Kubernetes liveness + readiness probes) --

@app.get("/health", response_model=HealthResponse, tags=["ops"])
def health():
    return HealthResponse(
        status            = "ok",
        cells_initialized = len(cell_registry),
        uptime_seconds    = round(time.time() - _start_time, 1),
    )

@app.get("/ready", tags=["ops"])
def ready():
    return {"status": "ready"}


# -- Single-cell metrics (random-walk step on each poll) --

@app.get("/metrics/cell/{cell_id}", response_model=CellMetrics, tags=["metrics"])
async def get_cell_metrics(cell_id: str):
    """
    Returns real-time KPIs for one cell.
    Each call advances the random-walk simulation by one step.
    """
    state = get_or_create_cell(cell_id)

    async with state.lock:
        # Random walk — UE count
        state.active_ues += random.randint(-2, 3)
        state.active_ues  = max(0, min(settings.max_ues, state.active_ues))

        # PRB scales with UE load + noise
        base_prb              = (state.active_ues / settings.max_ues) * 100.0
        state.prb_utilization = max(0.0, min(100.0,
            base_prb + random.uniform(-settings.noise_range, settings.noise_range)
        ))

        metrics = _compute_metrics(cell_id, state)

    # Update Prometheus gauges
    prb_gauge.labels(cell_id=cell_id).set(metrics.prb_utilization)
    ues_gauge.labels(cell_id=cell_id).set(metrics.active_ues)
    cqi_gauge.labels(cell_id=cell_id).set(metrics.avg_cqi)
    throughput_gauge.labels(cell_id=cell_id).set(metrics.throughput_mbps)

    logger.info("metrics_fetched", cell_id=cell_id,
                prb=metrics.prb_utilization, ues=metrics.active_ues,
                cqi=metrics.avg_cqi, throughput=metrics.throughput_mbps)
    return metrics


# -- Bulk metrics snapshot (RL agent uses this for a single-call observation) --

@app.get("/metrics/cells", response_model=List[CellMetrics], tags=["metrics"])
async def get_all_cell_metrics():
    """
    Returns the current metrics for all registered cells in one call.
    Intended for the RL agent's observation step — avoids N serial requests.
    No random-walk step is applied; use GET /metrics/cell/{id} to advance state.
    """
    if not cell_registry:
        return []

    results = []
    for cell_id, state in cell_registry.items():
        async with state.lock:
            results.append(_compute_metrics(cell_id, state))
    return results


# -- Control actions --

@app.post("/control/cell/{cell_id}/scale", response_model=ScaleResponse, tags=["control"])
async def scale_cell_capacity(
    cell_id: str,
    capacity_multiplier: float = Query(
        ..., gt=0.1, le=10.0,
        description="Scaling factor > 0.1 and ≤ 10. Values < 1 reduce, > 1 expand capacity."
    ),
):
    """
    Simulates an RL xApp scaling action.
    Dividing PRB utilization by the multiplier models additional resource allocation.
    """
    state = get_or_create_cell(cell_id)

    async with state.lock:
        state.prb_utilization = max(0.0, min(100.0,
            state.prb_utilization / capacity_multiplier
        ))
        new_prb = round(state.prb_utilization, 2)

    prb_gauge.labels(cell_id=cell_id).set(new_prb)
    logger.info("scale_action", cell_id=cell_id, multiplier=capacity_multiplier, new_prb=new_prb)

    return ScaleResponse(
        status           = "success",
        cell_id          = cell_id,
        action           = "scaled",
        new_multiplier   = capacity_multiplier,
        new_prb          = new_prb,
    )


@app.post("/control/cell/{cell_id}/handover", tags=["control"])
async def handover_recommendation(
    cell_id: str,
    target_cell_id: str = Query(..., description="Target cell to hand over UEs to"),
    ue_fraction: float  = Query(0.3, gt=0.0, le=1.0,
                                description="Fraction of UEs to hand over (0–1)"),
):
    """
    Simulates a handover action: moves a fraction of UEs from one cell to another.
    """
    source = get_or_create_cell(cell_id)
    target = get_or_create_cell(target_cell_id)

    # Lock both cells in a consistent order to avoid deadlock
    first, second = (source, target) if id(source) < id(target) else (target, source)
    async with first.lock:
        async with second.lock:
            transfer = max(1, int(source.active_ues * ue_fraction))
            transfer = min(transfer, source.active_ues)
            source.active_ues -= transfer
            target.active_ues  = min(settings.max_ues, target.active_ues + transfer)

    logger.info("handover_action", source=cell_id, target=target_cell_id,
                ues_transferred=transfer)
    return {
        "status": "success",
        "action": "handover",
        "source_cell": cell_id,
        "target_cell": target_cell_id,
        "ues_transferred": transfer,
    }


@app.post("/control/cell/{cell_id}/rebalance", tags=["control"])
async def rebalance_load(cell_id: str):
    """
    Simulates a load-balancing action: nudges PRB utilization toward the midpoint.
    Models a scheduler redistributing load across carriers.
    """
    state = get_or_create_cell(cell_id)

    async with state.lock:
        # Soft rebalance: move 20% toward 50% utilization baseline
        state.prb_utilization += (50.0 - state.prb_utilization) * 0.20
        state.prb_utilization  = round(max(0.0, min(100.0, state.prb_utilization)), 2)
        new_prb = state.prb_utilization

    prb_gauge.labels(cell_id=cell_id).set(new_prb)
    logger.info("rebalance_action", cell_id=cell_id, new_prb=new_prb)
    return {"status": "success", "action": "rebalanced", "cell_id": cell_id, "new_prb": new_prb}


# -- RL episode support --

@app.post("/control/reset", response_model=ResetResponse, tags=["rl"])
async def reset_all_cells():
    """
    Resets all registered cells to their initial state.
    Equivalent to Gym's env.reset() — call at the start of each RL episode.
    """
    reset_cells = []
    for cell_id, state in cell_registry.items():
        async with state.lock:
            state.reset()
        prb_gauge.labels(cell_id=cell_id).set(settings.initial_prb)
        ues_gauge.labels(cell_id=cell_id).set(settings.initial_ues)
        reset_cells.append(cell_id)

    logger.info("environment_reset", cells=reset_cells)
    return ResetResponse(status="reset", cells=reset_cells)