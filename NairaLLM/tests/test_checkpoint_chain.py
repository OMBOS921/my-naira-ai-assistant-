"""
Unit tests for NairaLLM CheckpointChain and Package Import Integrity.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure workspace root is in sys.path
workspace_root = Path(__file__).resolve().parent.parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

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


def test_checkpoint_chain_imports() -> None:
    assert CheckpointChainManager is not None
    assert CheckpointMetadata is not None
    assert TrainingStage.FOUNDATION.value == "foundation"
    assert TrainingStage.FINAL.value == "final"
    assert len(STAGE_ORDER) == 6
    assert STAGE_PREDECESSORS[TrainingStage.DOMAIN] == TrainingStage.FOUNDATION


def test_checkpoint_chain_validation(tmp_path: Path) -> None:
    mgr = CheckpointChainManager(tmp_path / "checkpoints")
    
    # Foundation requires no parent
    is_valid, msg = mgr.validate_parent(TrainingStage.FOUNDATION, None)
    assert is_valid is True
    
    # Domain requires foundation parent
    is_valid, msg = mgr.validate_parent(TrainingStage.DOMAIN, None)
    assert is_valid is False
    assert "requires a valid parent" in msg


def test_foundation_checkpoint_exists() -> None:
    foundation_weights = workspace_root / "NairaLLM" / "training" / "checkpoints" / "foundation" / "naira_semantic_105k_numpy.npz"
    foundation_meta = workspace_root / "NairaLLM" / "training" / "checkpoints" / "foundation" / "foundation_checkpoint_metadata.json"
    
    assert foundation_weights.exists(), f"Foundation weights missing: {foundation_weights}"
    assert foundation_meta.exists(), f"Foundation metadata missing: {foundation_meta}"
    assert foundation_weights.stat().st_size > 1000000, "Foundation weights size should be > 1MB"


if __name__ == "__main__":
    test_checkpoint_chain_imports()
    print("test_checkpoint_chain_imports: PASSED")
    test_foundation_checkpoint_exists()
    print("test_foundation_checkpoint_exists: PASSED")
