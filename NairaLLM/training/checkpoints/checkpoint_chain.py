"""
Canonical Checkpoint Chain for NairaLLM V1.

Enforces strict sequential lineage:
foundation -> domain -> cognition -> tools -> behavior -> final

Each checkpoint records:
- parent checkpoint & parent hash
- git commit SHA
- dataset version & SHA-256
- tokenizer version & SHA-256
- model config SHA-256
- stage name
- training metrics
- hardware environment
- timestamp
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    from enum import StrEnum
except ImportError:
    from enum import Enum
    class StrEnum(str, Enum):
        pass

_LOG = logging.getLogger("nairallm.checkpoint_chain")


class TrainingStage(StrEnum):
    FOUNDATION = "foundation"
    DOMAIN = "domain"
    COGNITION = "cognition"
    TOOLS = "tools"
    BEHAVIOR = "behavior"
    FINAL = "final"


STAGE_ORDER: list[TrainingStage] = [
    TrainingStage.FOUNDATION,
    TrainingStage.DOMAIN,
    TrainingStage.COGNITION,
    TrainingStage.TOOLS,
    TrainingStage.BEHAVIOR,
    TrainingStage.FINAL,
]

STAGE_PREDECESSORS: dict[TrainingStage, TrainingStage | None] = {
    TrainingStage.FOUNDATION: None,
    TrainingStage.DOMAIN: TrainingStage.FOUNDATION,
    TrainingStage.COGNITION: TrainingStage.DOMAIN,
    TrainingStage.TOOLS: TrainingStage.COGNITION,
    TrainingStage.BEHAVIOR: TrainingStage.TOOLS,
    TrainingStage.FINAL: TrainingStage.BEHAVIOR,
}


def compute_file_sha256(path: str | Path) -> str:
    """Compute SHA-256 hash of a file."""
    path = Path(path)
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_dict_sha256(data: dict[str, Any]) -> str:
    """Compute SHA-256 hash of a dictionary (canonical JSON)."""
    serialized = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get_current_git_commit(cwd: str | Path | None = None) -> str:
    """Get current git commit hash."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN_GIT_COMMIT"


@dataclass
class CheckpointMetadata:
    checkpoint_name: str
    stage: TrainingStage
    parent_checkpoint: str | None = None
    parent_checkpoint_sha256: str | None = None
    weights_path: str = ""
    weights_sha256: str = ""
    git_commit: str = field(default_factory=get_current_git_commit)
    dataset_name: str = ""
    dataset_version: str = "1.0.0"
    dataset_sha256: str = ""
    tokenizer_name: str = "NairaTokenizer"
    tokenizer_version: str = "1.0.0"
    tokenizer_sha256: str = ""
    model_config_sha256: str = ""
    training_metrics: dict[str, Any] = field(default_factory=dict)
    training_hardware: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["stage"] = self.stage.value if isinstance(self.stage, TrainingStage) else str(self.stage)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CheckpointMetadata:
        data_copy = dict(data)
        if "stage" in data_copy and isinstance(data_copy["stage"], str):
            data_copy["stage"] = TrainingStage(data_copy["stage"])
        return cls(**{k: v for k, v in data_copy.items() if k in cls.__dataclass_fields__})

    def save(self, file_path: str | Path) -> None:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, file_path: str | Path) -> CheckpointMetadata:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


class CheckpointChainManager:
    """Manages the canonical checkpoint chain and lineage validation."""

    def __init__(self, checkpoints_dir: str | Path | None = None) -> None:
        if checkpoints_dir is None:
            self.checkpoints_dir = Path(__file__).resolve().parent
        else:
            self.checkpoints_dir = Path(checkpoints_dir)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def get_stage_checkpoint_dir(self, stage: TrainingStage | str) -> Path:
        st = TrainingStage(stage) if isinstance(stage, str) else stage
        p = self.checkpoints_dir / st.value
        p.mkdir(parents=True, exist_ok=True)
        return p

    def validate_parent(
        self,
        current_stage: TrainingStage | str,
        parent_metadata_path: str | Path | None,
    ) -> tuple[bool, str]:
        st = TrainingStage(current_stage) if isinstance(current_stage, str) else current_stage
        expected_parent_stage = STAGE_PREDECESSORS.get(st)

        if expected_parent_stage is None:
            return True, "Foundation stage requires no parent."

        if parent_metadata_path is None or not Path(parent_metadata_path).exists():
            return False, f"Stage '{st.value}' requires a valid parent checkpoint from '{expected_parent_stage.value}', but none was found."

        try:
            parent_meta = CheckpointMetadata.load(parent_metadata_path)
            if parent_meta.stage != expected_parent_stage:
                return False, f"Stage lineage mismatch: Expected parent stage '{expected_parent_stage.value}', got '{parent_meta.stage.value}'."
            return True, f"Valid parent lineage verified from '{parent_meta.stage.value}'."
        except Exception as exc:
            return False, f"Failed to load and validate parent metadata: {exc}"

    def register_checkpoint(
        self,
        stage: TrainingStage | str,
        checkpoint_name: str,
        weights_path: str | Path,
        parent_metadata_path: str | Path | None = None,
        dataset_path: str | Path | None = None,
        tokenizer_path: str | Path | None = None,
        config_path: str | Path | None = None,
        metrics: dict[str, Any] | None = None,
        hardware_info: dict[str, Any] | None = None,
    ) -> CheckpointMetadata:
        st = TrainingStage(stage) if isinstance(stage, str) else stage
        weights_p = Path(weights_path)

        parent_meta: CheckpointMetadata | None = None
        parent_sha256: str | None = None
        parent_name: str | None = None

        if parent_metadata_path is not None and Path(parent_metadata_path).exists():
            parent_meta = CheckpointMetadata.load(parent_metadata_path)
            parent_name = parent_meta.checkpoint_name
            parent_sha256 = parent_meta.weights_sha256

        dataset_sha256 = compute_file_sha256(dataset_path) if dataset_path else ""
        tokenizer_sha256 = compute_file_sha256(tokenizer_path) if tokenizer_path else ""
        config_sha256 = compute_file_sha256(config_path) if config_path else ""
        weights_sha256 = compute_file_sha256(weights_p) if weights_p.exists() else ""

        meta = CheckpointMetadata(
            checkpoint_name=checkpoint_name,
            stage=st,
            parent_checkpoint=parent_name,
            parent_checkpoint_sha256=parent_sha256,
            weights_path=str(weights_p),
            weights_sha256=weights_sha256,
            dataset_name=Path(dataset_path).name if dataset_path else "",
            dataset_sha256=dataset_sha256,
            tokenizer_name="NairaTokenizer",
            tokenizer_sha256=tokenizer_sha256,
            model_config_sha256=config_sha256,
            training_metrics=metrics or {},
            training_hardware=hardware_info or {},
        )

        stage_dir = self.get_stage_checkpoint_dir(st)
        meta_file = stage_dir / f"{checkpoint_name}_metadata.json"
        meta.save(meta_file)
        _LOG.info("Registered checkpoint [%s] at %s", st.value, meta_file)
        return meta
