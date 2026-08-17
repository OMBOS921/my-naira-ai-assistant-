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
    SEMANTIC = "semantic"
    DOMAIN = "domain"
    COGNITION = "cognition"
    TOOLS = "tools"
    BEHAVIOR = "behavior"
    FINAL = "final"


def normalize_stage(stage: TrainingStage | str) -> TrainingStage:
    if isinstance(stage, TrainingStage):
        return stage
    s = str(stage).strip().lower()
    if s == "foundation":
        return TrainingStage.SEMANTIC
    return TrainingStage(s)


STAGE_ORDER: list[TrainingStage] = [
    TrainingStage.SEMANTIC,
    TrainingStage.DOMAIN,
    TrainingStage.COGNITION,
    TrainingStage.TOOLS,
    TrainingStage.BEHAVIOR,
    TrainingStage.FINAL,
]

STAGE_PREDECESSORS: dict[TrainingStage, TrainingStage | None] = {
    TrainingStage.SEMANTIC: None,
    TrainingStage.DOMAIN: TrainingStage.SEMANTIC,
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
        if "stage" in data_copy and data_copy["stage"] is not None:
            data_copy["stage"] = normalize_stage(data_copy["stage"])
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


import shutil

DEFAULT_GDRIVE_PERSISTENT_DIR = "/content/drive/MyDrive/Naira-Training/checkpoints/final_v1"


class CheckpointChainManager:
    """Manages the canonical checkpoint chain, lineage validation, and persistent storage synchronization."""

    def __init__(
        self,
        checkpoints_dir: str | Path | None = None,
        persistent_dir: str | Path | None = None,
    ) -> None:
        if checkpoints_dir is None:
            self.checkpoints_dir = Path(__file__).resolve().parent
        else:
            self.checkpoints_dir = Path(checkpoints_dir)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

        env_persistent = os.environ.get("NAIRA_GDRIVE_CHECKPOINT_DIR")
        if persistent_dir is not None:
            self.persistent_dir = Path(persistent_dir)
        elif env_persistent:
            self.persistent_dir = Path(env_persistent)
        elif Path("/content/drive/MyDrive").exists():
            self.persistent_dir = Path(DEFAULT_GDRIVE_PERSISTENT_DIR)
        else:
            self.persistent_dir = None

    def get_stage_checkpoint_dir(self, stage: TrainingStage | str) -> Path:
        st = normalize_stage(stage)
        p = self.checkpoints_dir / st.value
        p.mkdir(parents=True, exist_ok=True)
        return p

    def backup_checkpoint_to_persistent(
        self,
        stage: TrainingStage | str,
        weights_path: str | Path,
        metadata_path: str | Path,
        stage_manifest: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Copies .pt weights, metadata.json, and stage_manifest.json to persistent storage
        (e.g., Google Drive /content/drive/MyDrive/Naira-Training/checkpoints/final_v1/<stage>/).
        """
        st = normalize_stage(stage)
        w_path = Path(weights_path)
        m_path = Path(metadata_path)

        result: dict[str, Any] = {
            "stage": st.value,
            "backed_up": False,
            "persistent_dir": None,
            "files_copied": [],
            "error": None,
        }

        if self.persistent_dir is None:
            _LOG.info("Persistent storage directory not configured or Google Drive not mounted. Skipping persistent copy.")
            return result

        try:
            stage_persistent_dir = self.persistent_dir / st.value
            stage_persistent_dir.mkdir(parents=True, exist_ok=True)

            # Copy weights .pt
            if w_path.exists():
                dst_w = stage_persistent_dir / w_path.name
                shutil.copy2(w_path, dst_w)
                if not dst_w.exists() or dst_w.stat().st_size != w_path.stat().st_size:
                    raise IOError(f"Weights copy verification failed: {dst_w}")
                result["files_copied"].append(str(dst_w))

            # Copy metadata .json
            if m_path.exists():
                dst_m = stage_persistent_dir / m_path.name
                shutil.copy2(m_path, dst_m)
                if not dst_m.exists() or dst_m.stat().st_size != m_path.stat().st_size:
                    raise IOError(f"Metadata copy verification failed: {dst_m}")
                result["files_copied"].append(str(dst_m))

            # Write stage manifest
            manifest_file = stage_persistent_dir / f"nairallm_v1_{st.value}_manifest.json"
            manifest_payload = stage_manifest or {
                "stage": st.value,
                "weights_filename": w_path.name,
                "weights_bytes": w_path.stat().st_size if w_path.exists() else 0,
                "metadata_filename": m_path.name,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                "git_commit": get_current_git_commit(self.checkpoints_dir.parent.parent.parent),
            }
            with open(manifest_file, "w", encoding="utf-8") as f:
                json.dump(manifest_payload, f, indent=2, ensure_ascii=False)
            result["files_copied"].append(str(manifest_file))

            result["backed_up"] = True
            result["persistent_dir"] = str(stage_persistent_dir)
            _LOG.info("Successfully backed up stage [%s] checkpoint to persistent directory: %s", st.value, stage_persistent_dir)
        except Exception as exc:
            _LOG.error("Failed to backup checkpoint to persistent storage: %s", exc)
            result["error"] = str(exc)

        return result

    def restore_checkpoint_from_persistent(self, stage: TrainingStage | str) -> tuple[Path | None, Path | None]:
        """
        Attempts to restore missing .pt weights and metadata from persistent storage
        (e.g., Google Drive) into the local workspace checkpoints directory.
        """
        st = normalize_stage(stage)
        if self.persistent_dir is None or not self.persistent_dir.exists():
            return None, None

        stage_persistent_dir = self.persistent_dir / st.value
        if not stage_persistent_dir.exists():
            return None, None

        local_stage_dir = self.get_stage_checkpoint_dir(st)

        # Look for .pt weights in persistent dir
        pt_candidates = list(stage_persistent_dir.glob("*.pt")) + list(stage_persistent_dir.glob("*.npz"))
        if not pt_candidates:
            return None, None

        src_w = pt_candidates[0]
        dst_w = local_stage_dir / src_w.name

        # Copy weights if not present locally or size differs
        if not dst_w.exists() or dst_w.stat().st_size != src_w.stat().st_size:
            _LOG.info("Auto-restoring [%s] weights from persistent storage: %s -> %s", st.value, src_w, dst_w)
            shutil.copy2(src_w, dst_w)

        # Copy metadata if present in persistent dir
        meta_candidates = list(stage_persistent_dir.glob("*_metadata.json"))
        dst_m = None
        if meta_candidates:
            src_m = meta_candidates[0]
            dst_m = local_stage_dir / src_m.name
            if not dst_m.exists() or dst_m.stat().st_size != src_m.stat().st_size:
                _LOG.info("Auto-restoring [%s] metadata from persistent storage: %s -> %s", st.value, src_m, dst_m)
                shutil.copy2(src_m, dst_m)
        else:
            dst_m = local_stage_dir / f"{src_w.stem}_metadata.json"

        return (dst_w if dst_w.exists() else None, dst_m if (dst_m and dst_m.exists()) else None)

    def find_latest_checkpoint(self, stage: TrainingStage | str) -> tuple[Path | None, Path | None]:
        """
        Finds the latest weights and metadata for a stage.
        First checks local directory, then checks persistent Google Drive and auto-restores.
        Returns (weights_path, metadata_path) or (None, None) if not found.
        """
        st = normalize_stage(stage)
        workspace_root = self.checkpoints_dir.parent.parent.parent

        # 1. Search direct stage directory: checkpoints/{stage}/
        stage_dir = self.get_stage_checkpoint_dir(st)
        meta_candidates = list(stage_dir.glob("*_metadata.json"))
        if meta_candidates:
            meta_candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            for meta_path in meta_candidates:
                try:
                    meta = CheckpointMetadata.load(meta_path)
                    w_path = Path(meta.weights_path)
                    if not w_path.exists():
                        for cand in [stage_dir / w_path.name, workspace_root / meta.weights_path]:
                            if cand.exists():
                                w_path = cand
                                break
                    if w_path.exists():
                        return w_path, meta_path
                except Exception:
                    continue

        # 2. Check for .pt / .npz weights directly in stage directory
        weight_candidates = list(stage_dir.glob("*.pt")) + list(stage_dir.glob("*.npz"))
        if weight_candidates:
            weight_candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            w_path = weight_candidates[0]
            # Look for matching metadata
            m_path = stage_dir / f"{w_path.stem}_metadata.json"
            return w_path, m_path if m_path.exists() else None

        # 3. If missing locally, try auto-restoring from persistent storage (Google Drive)
        restored_w, restored_m = self.restore_checkpoint_from_persistent(st)
        if restored_w is not None and restored_w.exists():
            return restored_w, restored_m

        # 4. For SEMANTIC stage, fallback to foundation directory
        if st == TrainingStage.SEMANTIC:
            foundation_dir = self.checkpoints_dir / "foundation"
            if foundation_dir.exists():
                meta_candidates = list(foundation_dir.glob("*_metadata.json"))
                if meta_candidates:
                    meta_candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                    for meta_path in meta_candidates:
                        try:
                            meta = CheckpointMetadata.load(meta_path)
                            w_path = Path(meta.weights_path)
                            if not w_path.exists():
                                for cand in [foundation_dir / w_path.name, workspace_root / meta.weights_path]:
                                    if cand.exists():
                                        w_path = cand
                                        break
                            if w_path.exists():
                                return w_path, meta_path
                        except Exception:
                            continue

                weight_candidates = list(foundation_dir.glob("*.npz")) + list(foundation_dir.glob("*.pt"))
                if weight_candidates:
                    weight_candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                    w_path = weight_candidates[0]
                    m_path = foundation_dir / f"{w_path.stem}_metadata.json"
                    return w_path, m_path if m_path.exists() else None

        return None, None

    def validate_parent(
        self,
        current_stage: TrainingStage | str,
        parent_metadata_path: str | Path | None,
    ) -> tuple[bool, str]:
        st = normalize_stage(current_stage)
        expected_parent_stage = STAGE_PREDECESSORS.get(st)

        if expected_parent_stage is None:
            return True, f"Initial stage '{st.value}' requires no parent checkpoint."

        if parent_metadata_path is None or not Path(parent_metadata_path).exists():
            return False, f"Stage '{st.value}' requires a valid parent checkpoint from '{expected_parent_stage.value}', but none was found."

        try:
            parent_meta = CheckpointMetadata.load(parent_metadata_path)
            parent_st = normalize_stage(parent_meta.stage)
            if parent_st != expected_parent_stage:
                return False, f"Stage lineage mismatch: Expected parent stage '{expected_parent_stage.value}', got '{parent_st.value}'."
            return True, f"Valid parent lineage verified from '{parent_st.value}'."
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
        st = normalize_stage(stage)
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
