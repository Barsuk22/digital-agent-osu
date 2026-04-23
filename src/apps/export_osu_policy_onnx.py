from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from src.core.config.paths import PATHS
from src.skills.osu.policy.runtime import ActorCritic, load_model_state_compatible


DEFAULT_OUTPUT = PATHS.artifacts_dir / "exports" / "onnx" / "best_easy_generalization.onnx"


class ExportableDeterministicPolicy(nn.Module):
    def __init__(self, model: ActorCritic) -> None:
        super().__init__()
        self.model = model

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        action = self.model.deterministic_action(obs)
        click_strength = (action[..., 2:3] + 1.0) * 0.5
        return torch.cat([action[..., :2], click_strength], dim=-1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the osu! policy checkpoint to ONNX.")
    parser.add_argument("--checkpoint", default=str(PATHS.phase8_easy_best_checkpoint))
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--obs-dim", type=int, default=59)
    parser.add_argument("--hidden-dim", type=int, default=256)
    parser.add_argument("--opset", type=int, default=17)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--skip-verify", action="store_true")
    return parser.parse_args()


def load_export_model(checkpoint_path: Path, device: torch.device, obs_dim: int, hidden_dim: int) -> ExportableDeterministicPolicy:
    model = ActorCritic(obs_dim=obs_dim, hidden_dim=hidden_dim).to(device)
    checkpoint = torch.load(checkpoint_path, map_location=device)
    load_model_state_compatible(model, checkpoint)
    model.eval()
    return ExportableDeterministicPolicy(model).to(device)


def verify_export(model: ExportableDeterministicPolicy, output_path: Path, obs_dim: int, device: torch.device) -> dict:
    try:
        import onnxruntime as ort
    except ImportError:
        return {"verified": False, "reason": "onnxruntime_not_installed"}

    sample = np.random.uniform(-1.0, 1.0, size=(4, obs_dim)).astype(np.float32)
    sample_t = torch.from_numpy(sample).to(device)
    with torch.no_grad():
        torch_out = model(sample_t).cpu().numpy()

    session = ort.InferenceSession(str(output_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name
    onnx_out = session.run([output_name], {input_name: sample})[0]

    max_abs_diff = float(np.max(np.abs(torch_out - onnx_out)))
    mean_abs_diff = float(np.mean(np.abs(torch_out - onnx_out)))
    return {
        "verified": True,
        "max_abs_diff": max_abs_diff,
        "mean_abs_diff": mean_abs_diff,
    }


def main() -> None:
    args = parse_args()
    checkpoint_path = Path(args.checkpoint).resolve()
    output_path = Path(args.out).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not checkpoint_path.exists():
        raise SystemExit(f"checkpoint not found: {checkpoint_path}")

    device = torch.device(args.device)
    model = load_export_model(checkpoint_path, device=device, obs_dim=args.obs_dim, hidden_dim=args.hidden_dim)
    dummy = torch.zeros((1, args.obs_dim), dtype=torch.float32, device=device)

    torch.onnx.export(
        model,
        dummy,
        output_path,
        input_names=["obs"],
        output_names=["action"],
        dynamic_axes={"obs": {0: "batch"}, "action": {0: "batch"}},
        opset_version=args.opset,
    )

    verification = {"verified": False, "reason": "skipped"}
    if not args.skip_verify:
        verification = verify_export(model, output_path, obs_dim=args.obs_dim, device=device)

    print(
        json.dumps(
            {
                "event": "onnx_exported",
                "checkpoint": str(checkpoint_path),
                "output": str(output_path),
                "obs_dim": args.obs_dim,
                "hidden_dim": args.hidden_dim,
                "opset": args.opset,
                **verification,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
