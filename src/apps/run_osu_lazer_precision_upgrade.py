from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from src.core.config.paths import PATHS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="End-to-end launcher: precision fine-tune -> eval -> ONNX export -> runtime config."
    )
    parser.add_argument("--run-name", default="osu_lazer_precision_spinner_v2")
    parser.add_argument("--source-checkpoint", default=str(PATHS.phase8_easy_best_checkpoint))
    parser.add_argument("--updates", type=int, default=450)
    parser.add_argument("--save-every", type=int, default=10)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--cursor-speed", type=float, default=10.5)
    parser.add_argument("--levels", nargs="+", default=["beginner", "easy"])
    parser.add_argument("--maps-dir", default=str(PATHS.maps_dir))
    parser.add_argument("--max-maps", type=int, default=0)
    parser.add_argument("--eval-map", default=str(PATHS.sentiment_easy_map))
    parser.add_argument("--skip-eval", action="store_true")
    parser.add_argument("--skip-train", action="store_true")
    parser.add_argument("--skip-export", action="store_true")
    parser.add_argument("--device", default="cpu", help="ONNX export device")
    parser.add_argument(
        "--onnx-out",
        default="",
        help=(
            "Absolute or project-relative path for exported ONNX. "
            "Default: artifacts/exports/onnx/lazer_transfer_generalization.onnx (same as agent_observed.gu.json)."
        ),
    )
    parser.add_argument(
        "--runtime-template",
        default=str(PATHS.project_root / "external" / "osu_lazer_controller" / "configs" / "runtime.onnx.live_play.auto.json"),
    )
    parser.add_argument(
        "--runtime-out",
        default="",
        help=(
            "Absolute or project-relative output for runtime config. "
            "Default: external/osu_lazer_controller/configs/runtime.onnx.live_play.<run-name>.json"
        ),
    )
    parser.add_argument(
        "--write-runtime",
        action="store_true",
        help="Write a new runtime JSON from --runtime-template (off by default; use agent_observed.gu and stable ONNX).",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def resolve_under_project(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return (PATHS.project_root / path).resolve()


def run_step(command: list[str], env: dict[str, str] | None = None) -> None:
    cmd_text = " ".join(command)
    print(f"[step] {cmd_text}")
    subprocess.run(command, check=True, env=env)


def build_onnx_out(args: argparse.Namespace) -> Path:
    if args.onnx_out.strip():
        return resolve_under_project(args.onnx_out)
    return (PATHS.artifacts_dir / "exports" / "onnx" / "lazer_transfer_generalization.onnx").resolve()


def build_runtime_out(args: argparse.Namespace) -> Path:
    if args.runtime_out.strip():
        return resolve_under_project(args.runtime_out)
    return (
        PATHS.project_root
        / "external"
        / "osu_lazer_controller"
        / "configs"
        / f"runtime.onnx.live_play.{args.run_name}.json"
    ).resolve()


def best_checkpoint_path(run_name: str) -> Path:
    return (PATHS.runs_dir / run_name / "checkpoints" / "best_lazer_transfer.pt").resolve()


def write_runtime_config(template_path: Path, output_path: Path, onnx_model_path: Path) -> None:
    template = json.loads(template_path.read_text(encoding="utf-8"))
    template.setdefault("policyBridge", {})
    template["policyBridge"]["mode"] = "onnx"
    template["policyBridge"]["modelPath"] = str(onnx_model_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[runtime-config] saved: {output_path}")


def main() -> None:
    args = parse_args()

    template_path = resolve_under_project(args.runtime_template)
    run_best_ckpt = best_checkpoint_path(args.run_name)
    onnx_out = build_onnx_out(args)
    runtime_out = build_runtime_out(args)

    print("=" * 100)
    print("OSU LAZER PRECISION UPGRADE PIPELINE")
    print(f"run_name: {args.run_name}")
    print(f"source_checkpoint: {Path(args.source_checkpoint).resolve()}")
    print(f"target_best_checkpoint: {run_best_ckpt}")
    print(f"eval_map: {Path(args.eval_map).resolve()}")
    print(f"onnx_out: {onnx_out}")
    print(f"runtime_template: {template_path}")
    print(f"runtime_out: {runtime_out}")
    print("=" * 100)

    if args.dry_run:
        print("[dry-run] no commands executed.")
        return

    if not args.skip_train:
        # train_cmd = [
        #     sys.executable,
        #     "-m",
        #     "src.apps.train_osu_lazer_transfer",
        #     "--run-name",
        #     args.run_name,
        #     "--source-checkpoint",
        #     str(Path(args.source_checkpoint).resolve()), 
        #     "--profile",
        #     "precision",
        #     "--updates",
        #     str(args.updates),
        #     "--save-every",
        #     str(args.save_every),
        #     "--learning-rate",
        #     str(args.learning_rate),
        #     "--cursor-speed",
        #     str(args.cursor_speed),
        #     "--maps-dir",
        #     str(Path(args.maps_dir).resolve()),
        #     "--max-maps",
        #     str(args.max_maps),
        # ]
        train_cmd = [
            sys.executable,
            "-m",
            "src.apps.train_osu_lazer_transfer",
            "--run-name",
            args.run_name,
            "--source-checkpoint",
            str(Path(args.source_checkpoint).resolve()), 
            "--profile",
            "precision_spinner",
            # "--resume-latest",
            "--updates",
            str(args.updates),
            "--save-every",
            str(args.save_every),
            "--learning-rate",
            str(args.learning_rate),
            "--cursor-speed",
            str(args.cursor_speed),
            "--maps-dir",
            str(Path(args.maps_dir).resolve()),
            "--max-maps",
            str(args.max_maps),
        ]
        if args.levels:
            train_cmd.extend(["--levels", *args.levels])
        run_step(train_cmd)

    if not run_best_ckpt.exists():
        raise SystemExit(f"best checkpoint not found: {run_best_ckpt}")

    if not args.skip_eval:
        eval_env = dict(os.environ)
        eval_env["OSU_EVAL_CHECKPOINT"] = str(run_best_ckpt)
        eval_env["OSU_EVAL_MAP"] = str(Path(args.eval_map).resolve())
        run_step([sys.executable, "-m", "src.apps.eval_osu"], env=eval_env)

    if not args.skip_export:
        onnx_out.parent.mkdir(parents=True, exist_ok=True)
        run_step(
            [
                sys.executable,
                "-m",
                "src.apps.export_osu_policy_onnx",
                "--checkpoint",
                str(run_best_ckpt),
                "--out",
                str(onnx_out),
                "--device",
                args.device,
            ]
        )

    if not onnx_out.exists():
        raise SystemExit(f"ONNX model not found: {onnx_out}")

    if args.write_runtime:
        if not template_path.exists():
            raise SystemExit(f"runtime template not found: {template_path}")
        write_runtime_config(template_path=template_path, output_path=runtime_out, onnx_model_path=onnx_out)
    else:
        print(
            f"[onnx] ready at {onnx_out}; use configs/runtime.onnx.live_play.agent_observed.gu.json (modelPath should match)."
        )

    print("[done] precision upgrade pipeline completed.")


if __name__ == "__main__":
    main()
