import os
import time
import numpy as np
import structlog
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

from oran_env import ORANEnv

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Configuration — all overridable via environment variables (K8s ConfigMap)
# ---------------------------------------------------------------------------
API_URL             = os.environ.get("RAN_API_URL",  "http://metrics-api-service:8001")
MODEL_PATH          = os.environ.get("MODEL_PATH",   "/app/models/ppo_oran_final.zip")
STATS_PATH          = os.environ.get("STATS_PATH",   "/app/models/vec_normalize.pkl")
CONTROL_LOOP_DELAY  = float(os.environ.get("LOOP_DELAY_S", "2.0"))
API_READY_TIMEOUT   = float(os.environ.get("API_READY_TIMEOUT_S", "60.0"))

ACTION_NAMES = {
    0: "idle",
    1: "rebalance_cell1",
    2: "rebalance_cell2",
    3: "handover_c1_to_c2",
    4: "handover_c2_to_c1",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wait_for_api(api_url: str, timeout: float) -> None:
    """
    Polls /health until the metrics-api responds or timeout is reached.
    Replaces the blind time.sleep(5) — works whether the API is fast or slow.
    """
    import urllib.request
    import urllib.error

    health_url = f"{api_url.rstrip('/')}/health"
    deadline = time.monotonic() + timeout
    attempt  = 0

    while time.monotonic() < deadline:
        attempt += 1
        try:
            urllib.request.urlopen(health_url, timeout=2)
            logger.info("api_ready", attempts=attempt, url=health_url)
            return
        except Exception:
            logger.debug("api_not_ready_yet", attempt=attempt, url=health_url)
            time.sleep(2.0)

    raise RuntimeError(
        f"metrics-api did not become healthy within {timeout}s ({health_url})"
    )


def make_env() -> ORANEnv:
    return ORANEnv(api_url=API_URL)


def _load_env_and_model():
    """Loads VecNormalize stats and PPO weights; raises on any failure."""
    env = DummyVecEnv([make_env])
    env = VecNormalize.load(STATS_PATH, env)
    env.training    = False   # Freeze running mean/var — never update during inference
    env.norm_reward = False   # Raw rewards only; normalisation is for training

    # PPO.load must receive the env so the policy knows the observation space
    model = PPO.load(MODEL_PATH, env=env)

    logger.info("model_loaded",
                model_path=MODEL_PATH,
                stats_path=STATS_PATH)
    return env, model


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("initializing_oran_xapp", api_url=API_URL)

    # 1. Wait for the metrics-api to be ready (replaces blind sleep)
    _wait_for_api(API_URL, timeout=API_READY_TIMEOUT)

    # 2. Load environment + model
    try:
        env, model = _load_env_and_model()
    except FileNotFoundError as exc:
        logger.error("model_or_stats_not_found", error=str(exc),
                     hint="Run train.py first and make sure the models/ volume is mounted.")
        return
    except Exception as exc:
        logger.error("load_failed", error=str(exc))
        return

    # 3. Control loop
    obs = env.reset()
    logger.info("xapp_control_loop_started", loop_delay_s=CONTROL_LOOP_DELAY)

    consecutive_errors = 0
    MAX_CONSECUTIVE_ERRORS = 10

    while True:
        try:
            action, _ = model.predict(obs, deterministic=True)

            # action comes out as a numpy array from VecEnv — extract the scalar
            action_val = int(action[0]) if isinstance(action, np.ndarray) else int(action)

            # step() returns a 4-tuple from VecEnv (obs, reward, done, info)
            obs, rewards, dones, infos = env.step([action_val])

            info        = infos[0]
            action_name = ACTION_NAMES.get(action_val, str(action_val))
            reward      = float(rewards[0])

            if action_val != 0:
                logger.info(
                    "action_executed",
                    action=action_name,
                    reward=round(reward, 4),
                    throughput_mbps=round(info.get("total_throughput_mbps", 0.0), 2),
                    prb_cell1=round(info.get("prb_cell1", 0.0), 2),
                    prb_cell2=round(info.get("prb_cell2", 0.0), 2),
                    cqi_cell1=info.get("cqi_cell1"),
                    cqi_cell2=info.get("cqi_cell2"),
                    congestion_penalty=round(info.get("congestion_penalty", 0.0), 4),
                )
            else:
                logger.debug(
                    "idle",
                    throughput_mbps=round(info.get("total_throughput_mbps", 0.0), 2),
                    prb_cell1=round(info.get("prb_cell1", 0.0), 2),
                    prb_cell2=round(info.get("prb_cell2", 0.0), 2),
                )

            # VecEnv auto-resets on done — nothing to do manually
            consecutive_errors = 0
            time.sleep(CONTROL_LOOP_DELAY)

        except KeyboardInterrupt:
            logger.info("xapp_shutdown_requested")
            break

        except Exception as exc:
            consecutive_errors += 1
            logger.error("control_loop_error",
                         error=str(exc),
                         consecutive=consecutive_errors)

            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                logger.error("too_many_consecutive_errors_aborting",
                             limit=MAX_CONSECUTIVE_ERRORS)
                break

            time.sleep(CONTROL_LOOP_DELAY)

    env.close()
    logger.info("xapp_stopped")


if __name__ == "__main__":
    main()