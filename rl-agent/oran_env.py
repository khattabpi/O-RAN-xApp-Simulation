import time
from typing import Any, Dict, List, Optional, Tuple

import gymnasium as gym
import numpy as np
import requests
import structlog
from gymnasium import spaces
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Observation layout constants
# One block of N_METRICS floats per cell, cells concatenated in order.
# ---------------------------------------------------------------------------
N_METRICS = 4
PRB_IDX, UES_IDX, CQI_IDX, TPUT_IDX = 0, 1, 2, 3  # Offsets within a cell block

# Reward normalisation anchors
MAX_TPUT_MBPS  = 900.0   # Slightly above 20 MHz peak (~800 Mbps) for headroom
CONGESTION_THR = 85.0    # PRB % above which we penalise
ACTION_COST    = 0.02    # Small penalty per non-idle action (discourages thrashing)

# Fallback metrics returned when an API call fails
_FALLBACK_METRICS = {
    "prb_utilization": 0.0,
    "active_ues":      0,
    "avg_cqi":         1.0,
    "throughput_mbps": 0.0,
}


def _build_session(retries: int = 3, backoff: float = 0.3) -> requests.Session:
    """Returns a Session with automatic retry on transient server errors."""
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    session.mount("http://",  HTTPAdapter(max_retries=retry))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _cell_slice(obs: np.ndarray, cell_idx: int) -> np.ndarray:
    """Returns the 4-element view for a given cell index."""
    base = cell_idx * N_METRICS
    return obs[base : base + N_METRICS]


class ORANEnv(gym.Env):
    """
    Custom Gymnasium environment for O-RAN xApp RL agent.

    Interacts with the FastAPI Metrics Simulator over HTTP.

    Observation space
    -----------------
    Flat float32 array: [prb, ues, cqi, throughput] × n_cells
    Indices within each cell block are PRB_IDX, UES_IDX, CQI_IDX, TPUT_IDX.

    Action space
    ------------
    Discrete(5):
        0 — do nothing
        1 — rebalance cell-1
        2 — rebalance cell-2
        3 — handover 20 % of UEs from cell-1 → cell-2
        4 — handover 20 % of UEs from cell-2 → cell-1

    Reward
    ------
    Normalised in roughly [−2, 1]:
        + throughput / MAX_TPUT_MBPS          (maximise)
        − congestion_penalty_cell1            (avoid PRB > 85 %)
        − congestion_penalty_cell2
        − ACTION_COST  (if action != 0)       (discourage thrashing)

    Notes
    -----
    - Randomness lives inside the API simulator; the `seed` arg is accepted
      for API compliance but does not make episodes reproducible unless the
      API is also seeded (pass RAN_RANDOM_SEED env var to the API process).
    - Wrap with SB3's VecNormalize for best training performance (see README).
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        api_url: str = "http://localhost:8001",
        cell_ids: Optional[List[str]] = None,
        max_steps: int = 100,
        step_delay_s: float = 0.0,
        handover_fraction: float = 0.20,
        request_timeout: float = 2.0,
    ):
        super().__init__()

        self.api_url          = api_url.rstrip("/")
        self.cell_ids         = cell_ids or ["cell-1", "cell-2"]
        self.max_steps        = max_steps
        self.step_delay_s     = step_delay_s      # Set to 0.001 to simulate 1 ms TTI
        self.handover_fraction = handover_fraction
        self.request_timeout  = request_timeout
        self.current_step     = 0

        self.session = _build_session()

        # Pre-register cells in the API (best-effort; non-fatal if unreachable)
        for cid in self.cell_ids:
            try:
                self.session.get(
                    f"{self.api_url}/metrics/cell/{cid}",
                    timeout=self.request_timeout,
                )
            except requests.exceptions.RequestException:
                logger.warning("api_not_reachable_during_init", cell_id=cid,
                               hint="Make sure the metrics-api service is running.")

        n_cells = len(self.cell_ids)

        # Observation bounds — one block of 4 per cell
        low  = np.tile([0.0,   0,    1.0, 0.0          ], n_cells).astype(np.float32)
        high = np.tile([100.0, 200., 15.0, MAX_TPUT_MBPS], n_cells).astype(np.float32)
        self.observation_space = spaces.Box(low=low, high=high, dtype=np.float32)

        # Action space: idle + 2 rebalances + 2 handover directions
        self.action_space = spaces.Discrete(5)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_cell(self, cell_id: str) -> Dict[str, Any]:
        """GETs one cell's metrics, advancing the random-walk simulation."""
        try:
            resp = self.session.get(
                f"{self.api_url}/metrics/cell/{cell_id}",
                timeout=self.request_timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("cell_fetch_failed", cell_id=cell_id, error=str(exc))
            return {**_FALLBACK_METRICS, "cell_id": cell_id}

    def _fetch_all_bulk(self) -> List[Dict[str, Any]]:
        """GETs all cells in one request (no random-walk tick). Used after reset."""
        try:
            resp = self.session.get(
                f"{self.api_url}/metrics/cells",
                timeout=self.request_timeout,
            )
            resp.raise_for_status()
            by_id = {m["cell_id"]: m for m in resp.json()}
            return [by_id.get(cid, {**_FALLBACK_METRICS, "cell_id": cid})
                    for cid in self.cell_ids]
        except Exception as exc:
            logger.warning("bulk_fetch_failed", error=str(exc))
            return [{**_FALLBACK_METRICS, "cell_id": cid} for cid in self.cell_ids]

    def _metrics_to_obs(self, metrics: List[Dict[str, Any]]) -> np.ndarray:
        obs = []
        for m in metrics:
            obs.extend([
                float(m["prb_utilization"]),
                float(m["active_ues"]),
                float(m["avg_cqi"]),
                float(m["throughput_mbps"]),
            ])
        return np.array(obs, dtype=np.float32)

    def _get_observation(self, advance: bool = True) -> np.ndarray:
        """
        Fetch the current state from the API.

        advance=True  — calls per-cell endpoints (ticks random walk, use in step()).
        advance=False — calls bulk endpoint (consistent snapshot, use after reset()).
        """
        if advance:
            metrics = [self._fetch_cell(cid) for cid in self.cell_ids]
        else:
            metrics = self._fetch_all_bulk()
        return self._metrics_to_obs(metrics)

    def _post(self, path: str, params: Optional[Dict] = None) -> None:
        """Fire-and-forget POST; logs failures without crashing."""
        try:
            resp = self.session.post(
                f"{self.api_url}{path}",
                params=params or {},
                timeout=self.request_timeout,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("control_call_failed", path=path, error=str(exc))

    # ------------------------------------------------------------------
    # Gymnasium interface
    # ------------------------------------------------------------------

    def step(
        self, action: int
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        self.current_step += 1

        # 1. Execute control action
        c1_id, c2_id = self.cell_ids[0], self.cell_ids[1]
        if action == 1:
            self._post(f"/control/cell/{c1_id}/rebalance")
        elif action == 2:
            self._post(f"/control/cell/{c2_id}/rebalance")
        elif action == 3:
            self._post(
                f"/control/cell/{c1_id}/handover",
                {"target_cell_id": c2_id, "ue_fraction": self.handover_fraction},
            )
        elif action == 4:
            self._post(
                f"/control/cell/{c2_id}/handover",
                {"target_cell_id": c1_id, "ue_fraction": self.handover_fraction},
            )
        # action == 0 → do nothing

        # Optional TTI delay (set step_delay_s=0.001 for realistic 1 ms TTI)
        if self.step_delay_s > 0:
            time.sleep(self.step_delay_s)

        # 2. Get new observation (advances random walk)
        obs = self._get_observation(advance=True)

        # 3. Compute reward using named cell slices — no magic index arithmetic
        c1 = _cell_slice(obs, 0)
        c2 = _cell_slice(obs, 1)

        total_throughput = float(c1[TPUT_IDX] + c2[TPUT_IDX])

        # Normalised throughput reward: 0 → 1
        tput_reward = total_throughput / (MAX_TPUT_MBPS * len(self.cell_ids))

        # Congestion penalty: 0 below threshold, 0 → 1 as PRB goes 85 → 100 %
        penalty_c1 = max(0.0, (float(c1[PRB_IDX]) - CONGESTION_THR) / (100.0 - CONGESTION_THR))
        penalty_c2 = max(0.0, (float(c2[PRB_IDX]) - CONGESTION_THR) / (100.0 - CONGESTION_THR))

        # Action cost discourages unnecessary interventions
        action_cost = 0.0 if action == 0 else ACTION_COST

        reward = float(tput_reward - penalty_c1 - penalty_c2 - action_cost)

        # 4. Episode boundaries
        terminated = False                                  # Network never "ends"
        truncated  = self.current_step >= self.max_steps   # Time-limit truncation

        info: Dict[str, Any] = {
            "total_throughput_mbps": total_throughput,
            "prb_cell1":             float(c1[PRB_IDX]),
            "prb_cell2":             float(c2[PRB_IDX]),
            "cqi_cell1":             float(c1[CQI_IDX]),
            "cqi_cell2":             float(c2[CQI_IDX]),
            "ues_cell1":             float(c1[UES_IDX]),
            "ues_cell2":             float(c2[UES_IDX]),
            "congestion_penalty":    penalty_c1 + penalty_c2,
            "action_taken":          action,
            "step":                  self.current_step,
        }

        return obs, reward, terminated, truncated, info

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict] = None,
    ) -> Tuple[np.ndarray, Dict]:
        super().reset(seed=seed)
        # NOTE: randomness lives inside the API simulator.
        # For reproducible episodes, restart the API with RAN_RANDOM_SEED=<n>.
        self.current_step = 0

        # Reset the simulator state
        self._post("/control/reset")

        # Use the bulk (no-tick) endpoint so the first observation is
        # consistent with the just-reset state
        obs  = self._get_observation(advance=False)
        info: Dict[str, Any] = {"reset": True, "seed": seed}
        logger.info("env_reset", seed=seed, obs_shape=obs.shape)
        return obs, info

    def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        super().close()
        self.session.close()
        logger.info("env_closed")

    def render(self) -> None:  # render_mode is None — nothing to do
        pass