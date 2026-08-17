"""
NairaLLM Checkpoints Management & Sequential Lineage Tracking.
"""

from __future__ import annotations

from NairaLLM.training.checkpoints.checkpoint_chain import (
    CheckpointChainManager,
    CheckpointMetadata,
    STAGE_ORDER,
    STAGE_PREDECESSORS,
    TrainingStage,
    compute_dict_sha256,
    compute_file_sha256,
    get_current_git_commit,
)

__all__ = [
    "CheckpointChainManager",
    "CheckpointMetadata",
    "STAGE_ORDER",
    "STAGE_PREDECESSORS",
    "TrainingStage",
    "compute_dict_sha256",
    "compute_file_sha256",
    "get_current_git_commit",
]
