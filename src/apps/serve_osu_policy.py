from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch

from src.core.config.paths import PATHS
from src.skills.osu.policy.runtime import PPOPolicy, load_policy_from_checkpoint


DEFAULT_TCP_BIND = "tcp://127.0.0.1:5555"
DEFAULT_OBS_DIM = 59


@dataclass(slots=True)
class PolicyServerConfig:
    checkpoint_path: str = str(PATHS.phase8_easy_best_checkpoint)
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    bind: str = DEFAULT_TCP_BIND
    obs_dim: int = DEFAULT_OBS_DIM
    hidden_dim: int = 256
    warmup: bool = True
    log_every: int = 50


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve osu! policy actions over ZeroMQ REP.")
    parser.add_argument("--checkpoint", default=str(PATHS.phase8_easy_best_checkpoint))
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--bind", default=DEFAULT_TCP_BIND, help="ZeroMQ bind address, e.g. tcp://127.0.0.1:5555")
    parser.add_argument("--obs-dim", type=int, default=DEFAULT_OBS_DIM)
    parser.add_argument("--hidden-dim", type=int, default=256)
    parser.add_argument("--no-warmup", action="store_true")
    parser.add_argument("--log-every", type=int, default=50)
    return parser.parse_args()


def parse_obs(payload: dict, expected_dim: int) -> np.ndarray:
    raw_obs = payload.get("obs")
    if not isinstance(raw_obs, list):
        raise ValueError("payload must contain an 'obs' list")

    obs = np.asarray(raw_obs, dtype=np.float32)
    if obs.ndim != 1:
        raise ValueError("obs must be a flat float32 vector")
    if obs.shape[0] != expected_dim:
        raise ValueError(f"obs_dim mismatch: expected {expected_dim}, got {obs.shape[0]}")
    return obs


def action_payload(action) -> dict:
    return {
        "dx": float(action.dx),
        "dy": float(action.dy),
        "click_strength": float(action.click_strength),
    }


def warmup_policy(policy: PPOPolicy, obs_dim: int) -> None:
    zeros = np.zeros((obs_dim,), dtype=np.float32)
    for _ in range(2):
        policy.act_on_array(zeros)


def make_policy(cfg: PolicyServerConfig) -> PPOPolicy:
    device = torch.device(cfg.device)
    return load_policy_from_checkpoint(
        checkpoint_path=cfg.checkpoint_path,
        device=device,
        obs_dim=cfg.obs_dim,
        hidden_dim=cfg.hidden_dim,
    )


def main() -> None:
    args = parse_args()
    cfg = PolicyServerConfig(
        checkpoint_path=args.checkpoint,
        device=args.device,
        bind=args.bind,
        obs_dim=args.obs_dim,
        hidden_dim=args.hidden_dim,
        warmup=not args.no_warmup,
        log_every=max(1, args.log_every),
    )

    try:
        import zmq
    except ImportError as exc:
        raise SystemExit("pyzmq is required for serve_osu_policy.py. Install it before starting the bridge.") from exc

    checkpoint = Path(cfg.checkpoint_path)
    if not checkpoint.exists():
        raise SystemExit(f"checkpoint not found: {checkpoint}")

    policy = make_policy(cfg)
    if cfg.warmup:
        warmup_policy(policy, cfg.obs_dim)

    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind(cfg.bind)

    print(json.dumps({"event": "server_started", "config": asdict(cfg)}, ensure_ascii=False))

    request_count = 0
    started_at = time.perf_counter()

    try:
        while True:
            raw_message = socket.recv()
            request_started = time.perf_counter()

            try:
                payload = json.loads(raw_message.decode("utf-8"))
                command = payload.get("command", "act")

                if command == "ping":
                    response = {"ok": True, "pong": True}
                elif command == "describe":
                    response = {
                        "ok": True,
                        "obs_dim": cfg.obs_dim,
                        "checkpoint": str(checkpoint),
                        "device": cfg.device,
                        "bind": cfg.bind,
                    }
                elif command == "shutdown":
                    response = {"ok": True, "shutdown": True}
                    socket.send_json(response)
                    break
                else:
                    obs = parse_obs(payload, cfg.obs_dim)
                    action = policy.act_on_array(obs)
                    response = {
                        "ok": True,
                        **action_payload(action),
                        "latency_ms": (time.perf_counter() - request_started) * 1000.0,
                    }
            except Exception as exc:
                response = {"ok": False, "error": str(exc)}

            socket.send_json(response)
            request_count += 1

            if request_count % cfg.log_every == 0:
                uptime = time.perf_counter() - started_at
                rps = request_count / max(0.001, uptime)
                print(
                    json.dumps(
                        {
                            "event": "server_stats",
                            "requests": request_count,
                            "uptime_sec": round(uptime, 3),
                            "requests_per_sec": round(rps, 3),
                        },
                        ensure_ascii=False,
                    )
                )
    finally:
        socket.close(linger=0)
        context.term()


if __name__ == "__main__":
    main()
