import os
import structlog
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from stable_baselines3.common.callbacks import EvalCallback, CheckpointCallback, CallbackList
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.env_checker import check_env

from oran_env import ORANEnv

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
LOG_DIR   = "./logs/tensorboard/"
MODEL_DIR = "./models/"
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

FINAL_MODEL_PATH = os.path.join(MODEL_DIR, "ppo_oran_final")
STATS_PATH       = os.path.join(MODEL_DIR, "vec_normalize.pkl")

# ---------------------------------------------------------------------------
# Hyperparameters
# ---------------------------------------------------------------------------
TOTAL_TIMESTEPS = 50_000
API_URL         = os.environ.get("RAN_API_URL", "http://localhost:8001")


def make_env(api_url: str = API_URL):
    """Factory used by DummyVecEnv — returns a Monitor-wrapped ORANEnv."""
    def _init():
        env = ORANEnv(api_url=api_url)
        return Monitor(env)
    return _init


def main():
    logger.info("initializing_training_pipeline", api_url=API_URL)

    # 1. Sanity-check the environment before spending time on training
    logger.info("running_env_check")
    raw_env = ORANEnv(api_url=API_URL)
    check_env(raw_env, warn=True)
    raw_env.close()

    # 2. Training environment
    train_env = DummyVecEnv([make_env()])
    train_env = VecNormalize(
        train_env,
        norm_obs=True,
        norm_reward=True,
        clip_obs=10.0,
    )

    # 3. Evaluation environment
    #    - norm_reward=False: evaluate on raw rewards so scores are interpretable
    #    - training=False + norm_obs=True: observations are still normalised so
    #      the policy sees the same input distribution as during training
    eval_env = DummyVecEnv([make_env()])
    eval_env = VecNormalize(
        eval_env,
        norm_obs=True,
        norm_reward=False,
        clip_obs=10.0,
    )
    eval_env.training = False   # Freeze running stats — must be set AFTER construction

    # 4. Callbacks
    eval_callback = EvalCallback(
        eval_env,
        best_model_save_path=MODEL_DIR,
        log_path=LOG_DIR,
        eval_freq=2000,
        n_eval_episodes=5,          # Average over multiple episodes for a stable signal
        deterministic=True,
        render=False,
    )

    checkpoint_callback = CheckpointCallback(
        save_freq=10_000,
        save_path=MODEL_DIR,
        name_prefix="ppo_oran_checkpoint",
        save_vecnormalize=True,     # Saves the VecNormalize stats alongside each checkpoint
    )

    # 5. PPO model
    model = PPO(
        "MlpPolicy",
        train_env,
        verbose=1,
        tensorboard_log=LOG_DIR,
        # --- Hyperparameters ---
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,              # Encourages exploration; tune down if policy converges too slowly
        vf_coef=0.5,
        max_grad_norm=0.5,
        # --- Policy network ---
        policy_kwargs=dict(
            net_arch=[dict(pi=[128, 128], vf=[128, 128])]
        ),
    )

    # 6. Train
    logger.info("starting_training", total_timesteps=TOTAL_TIMESTEPS)
    model.learn(
        total_timesteps=TOTAL_TIMESTEPS,
        callback=CallbackList([eval_callback, checkpoint_callback]),
        tb_log_name="PPO_ORAN",
        reset_num_timesteps=True,
    )

    # 7. Save final model + normalisation statistics
    #    Both files are required for correct inference — load them together.
    model.save(FINAL_MODEL_PATH)
    train_env.save(STATS_PATH)
    logger.info("training_completed",
                model_path=FINAL_MODEL_PATH,
                stats_path=STATS_PATH)

    # 8. Quick smoke-test: run one episode with the saved model
    logger.info("running_inference_smoke_test")
    _smoke_test(FINAL_MODEL_PATH, STATS_PATH)

    train_env.close()
    eval_env.close()


def _smoke_test(model_path: str, stats_path: str) -> None:
    """
    Load the saved model and VecNormalize stats, then run one full episode.
    Verifies that the save/load round-trip works before you ship anything.
    """
    inf_env = DummyVecEnv([make_env()])
    inf_env = VecNormalize.load(stats_path, inf_env)
    inf_env.training = False        # Do not update running stats during inference
    inf_env.norm_reward = False     # Reward normalisation is only for training

    model = PPO.load(model_path, env=inf_env)

    obs = inf_env.reset()
    total_reward = 0.0
    done = False
    steps = 0

    while not done:
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, done_vec, info = inf_env.step(action)
        total_reward += float(reward[0])
        steps += 1
        done = bool(done_vec[0])

    logger.info("smoke_test_complete", steps=steps, total_reward=round(total_reward, 4))
    inf_env.close()


if __name__ == "__main__":
    main()