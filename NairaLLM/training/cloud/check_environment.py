"""
Dynamic Hardware & Environment Diagnostic Checker for NairaLLM Cloud Training.

Inspects current runtime and dynamically reports:
- Python version & platform
- PyTorch version & CUDA availability
- GPU hardware name, VRAM capacity, compute capability
- System RAM and available disk space
- Recommended training configuration (Batch size, Gradient Accumulation, AMP mode)

Works in local environments, Google Colab, and Kaggle Notebooks.
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

# Ensure workspace root in sys.path
workspace_root = Path(__file__).resolve().parent.parent.parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))


# =============================================================================
# COST GUARD & FREE CLOUD RESOURCE POLICY
# =============================================================================
USE_PAID_COMPUTE: bool = False


def detect_cloud_provider() -> str:
    """Detect current cloud hosting provider dynamically."""
    if "google.colab" in sys.modules or os.path.exists("/content"):
        return "google_colab"
    elif os.path.exists("/kaggle") or "KAGGLE_KERNEL_RUN_TYPE" in os.environ:
        return "kaggle"
    elif os.path.exists("/workspace") or "RUNPOD_POD_ID" in os.environ:
        return "runpod_or_custom"
    elif "AWS_EXECUTION_ENV" in os.environ or os.path.exists("/opt/ml"):
        return "aws_sagemaker"
    else:
        return "local_workstation"


def inspect_environment() -> dict[str, Any]:
    provider = detect_cloud_provider()

    info: dict[str, Any] = {
        "provider": provider,
        "use_paid_compute": USE_PAID_COMPUTE,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "cpu_count": os.cpu_count() or 1,
    }

    # Cost Guard check
    if provider in ["runpod_or_custom", "aws_sagemaker"] and not USE_PAID_COMPUTE:
        info["cost_guard_alert"] = "PAID_RESOURCE_DETECTED_BLOCKED"
    else:
        info["cost_guard_alert"] = "PERMITTED_FREE_OR_LOCAL"

    # Disk space
    try:
        usage = shutil.disk_usage(".")
        info["disk_total_gb"] = round(usage.total / (1024 ** 3), 2)
        info["disk_free_gb"] = round(usage.free / (1024 ** 3), 2)
    except Exception:
        info["disk_total_gb"] = None
        info["disk_free_gb"] = None

    # Memory
    try:
        import psutil
        vm = psutil.virtual_memory()
        info["ram_total_gb"] = round(vm.total / (1024 ** 3), 2)
        info["ram_available_gb"] = round(vm.available / (1024 ** 3), 2)
    except ImportError:
        info["ram_total_gb"] = "psutil_not_installed"
        info["ram_available_gb"] = "psutil_not_installed"

    # PyTorch & GPU
    try:
        import torch
        info["torch_available"] = True
        info["torch_version"] = torch.__version__
        info["cuda_available"] = torch.cuda.is_available()
        info["cuda_version"] = getattr(torch.version, "cuda", "N/A")

        if torch.cuda.is_available():
            info["device_type"] = "cuda"
            info["device_count"] = torch.cuda.device_count()
            info["device_name"] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            info["vram_total_gb"] = round(props.total_memory / (1024 ** 3), 2)
            info["cuda_capability"] = f"{props.major}.{props.minor}"
            info["amp_supported"] = True
            info["bf16_supported"] = torch.cuda.is_bf16_supported()
            info["free_gpu_available"] = True
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            info["device_type"] = "mps"
            info["device_name"] = "Apple Silicon MPS"
            info["vram_total_gb"] = 0.0
            info["amp_supported"] = False
            info["bf16_supported"] = False
            info["free_gpu_available"] = False
        else:
            info["device_type"] = "cpu"
            info["device_name"] = "Host CPU"
            info["vram_total_gb"] = 0.0
            info["amp_supported"] = False
            info["bf16_supported"] = False
            info["free_gpu_available"] = False
    except ImportError:
        info["torch_available"] = False
        info["torch_version"] = "not_installed"
        info["cuda_available"] = False
        info["cuda_version"] = "N/A"
        info["device_type"] = "cpu_numpy_fallback"
        info["device_name"] = "Pure NumPy CPU Fallback"
        info["vram_total_gb"] = 0.0
        info["amp_supported"] = False
        info["bf16_supported"] = False
        info["free_gpu_available"] = False

    # Compute recommended training configuration
    info["recommended_config"] = compute_recommended_config(info)
    return info


def verify_free_gpu_or_stop(require_gpu: bool = False) -> bool:
    """Verify that a free GPU is present; if not and require_gpu is True, STOP execution."""
    env = inspect_environment()
    if not USE_PAID_COMPUTE and env.get("cost_guard_alert") == "PAID_RESOURCE_DETECTED_BLOCKED":
        raise PermissionError(
            f"Cost Guard: Detected paid/commercial cloud provider '{env['provider']}'. "
            "USE_PAID_COMPUTE is set to False. Operation halted to prevent unexpected billing."
        )

    if require_gpu and not env.get("free_gpu_available", False):
        print("\n" + "=" * 60)
        print(" [STOP] FREE CLOUD GPU NOT AVAILABLE")
        print("=" * 60)
        print(f" Current Provider:    {env['provider']}")
        print(f" Active Compute:     {env['device_name']} ({env['device_type']})")
        print(f" PyTorch Status:     {env.get('torch_version', 'Not installed')}")
        print(f" CUDA Available:     {env.get('cuda_available', False)}")
        print("\n Heavy training requires a free cloud GPU runtime (Google Colab / Kaggle).")
        print(" Execution halted to prevent silently overloading the local machine.")
        print("=" * 60 + "\n")
        raise RuntimeError("Free Cloud GPU unavailable for heavy training run.")

    return True


def compute_recommended_config(env: dict[str, Any]) -> dict[str, Any]:
    dev_type = env.get("device_type", "cpu")
    vram = env.get("vram_total_gb", 0.0) or 0.0

    if dev_type == "cuda":
        if vram >= 24.0:  # A10G / A100 / RTX 3090/4090
            return {
                "batch_size": 16,
                "gradient_accumulation_steps": 2,
                "precision": "bf16" if env.get("bf16_supported") else "fp16",
                "learning_rate": 5e-4,
                "context_length": 1024,
                "tier_class": "high_vram_gpu",
            }
        elif vram >= 14.0:  # T4 (16GB) / P100 (16GB) / L4 (24GB)
            return {
                "batch_size": 8,
                "gradient_accumulation_steps": 4,
                "precision": "fp16",
                "learning_rate": 4e-4,
                "context_length": 512,
                "tier_class": "standard_cloud_gpu",
            }
        elif vram >= 8.0:  # RTX 3060/4060 / T4 (8GB)
            return {
                "batch_size": 4,
                "gradient_accumulation_steps": 8,
                "precision": "fp16",
                "learning_rate": 3e-4,
                "context_length": 256,
                "tier_class": "mid_gpu",
            }
        else:  # < 8GB VRAM
            return {
                "batch_size": 2,
                "gradient_accumulation_steps": 16,
                "precision": "fp16",
                "learning_rate": 2e-4,
                "context_length": 256,
                "tier_class": "low_vram_gpu",
            }
    elif dev_type == "mps":
        return {
            "batch_size": 4,
            "gradient_accumulation_steps": 4,
            "precision": "fp32",
            "learning_rate": 3e-4,
            "context_length": 256,
            "tier_class": "apple_mps",
        }
    else:  # CPU / Pure NumPy
        return {
            "batch_size": 2,
            "gradient_accumulation_steps": 1,
            "precision": "fp32",
            "learning_rate": 1e-3,
            "context_length": 128,
            "tier_class": "cpu_development",
        }


def print_diagnostic_report(env: dict[str, Any]) -> None:
    print("==================================================")
    print("   NAIRALLM HARDWARE & CLOUD ENVIRONMENT REPORT   ")
    print("==================================================")
    print(f"Provider:             {env['provider']}")
    print(f"Cost Guard:           USE_PAID_COMPUTE={env['use_paid_compute']} ({env.get('cost_guard_alert', 'OK')})")
    print(f"Python Version:       {env['python_version']} ({env['platform']})")
    print(f"CPU Threads:          {env['cpu_count']}")
    print(f"System RAM:           {env.get('ram_total_gb', 'N/A')} GB (Available: {env.get('ram_available_gb', 'N/A')} GB)")
    print(f"Disk Space:           {env.get('disk_free_gb', 'N/A')} GB free / {env.get('disk_total_gb', 'N/A')} GB total")
    print(f"PyTorch Status:       {'Available (' + str(env.get('torch_version')) + ')' if env.get('torch_available') else 'Not Installed (NumPy Engine Active)'}")
    print(f"Active Compute Device:{env['device_name']} [Type: {env['device_type']}]")
    print(f"Free GPU Available:   {env.get('free_gpu_available', False)}")

    if env.get("cuda_available"):
        print(f"CUDA Version:         {env.get('cuda_version', 'N/A')}")
        print(f"CUDA VRAM Total:      {env.get('vram_total_gb')} GB (Compute: {env.get('cuda_capability')})")
        print(f"Automatic Mixed Prec: Supported (BF16: {env.get('bf16_supported')})")

    rec = env["recommended_config"]
    print("\n--- Recommended Training Configuration ---")
    print(f"Tier Profile:         {rec['tier_class']}")
    print(f"Batch Size:           {rec['batch_size']}")
    print(f"Gradient Accumulation:{rec['gradient_accumulation_steps']} (Effective Batch: {rec['batch_size'] * rec['gradient_accumulation_steps']})")
    print(f"Precision Mode:       {rec['precision']}")
    print(f"Context Length:       {rec['context_length']}")
    print(f"Learning Rate:        {rec['learning_rate']}")
    print("==================================================")


def main() -> None:
    env = inspect_environment()
    print_diagnostic_report(env)


if __name__ == "__main__":
    main()
