"""
Unit and Regression Tests for NairaLLM CheckpointChain, TrainingStage Enum, and Sequential Lineage.
"""

from __future__ import annotations

import pytest
import sys
import tempfile
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
    normalize_stage,
)


def test_training_stage_enum() -> None:
    """Prove TrainingStage('semantic') works and all canonical values are defined."""
    assert TrainingStage("semantic") == TrainingStage.SEMANTIC
    assert TrainingStage.SEMANTIC.value == "semantic"
    assert TrainingStage.DOMAIN.value == "domain"
    assert TrainingStage.COGNITION.value == "cognition"
    assert TrainingStage.TOOLS.value == "tools"
    assert TrainingStage.BEHAVIOR.value == "behavior"
    assert TrainingStage.FINAL.value == "final"
    assert len(STAGE_ORDER) == 6


def test_stage_normalization_and_aliases() -> None:
    """Prove normalization handles strings, enum instances, and legacy 'foundation' alias."""
    assert normalize_stage("semantic") == TrainingStage.SEMANTIC
    assert normalize_stage("foundation") == TrainingStage.SEMANTIC
    assert normalize_stage(TrainingStage.DOMAIN) == TrainingStage.DOMAIN
    assert normalize_stage("DOMAIN") == TrainingStage.DOMAIN

    # Invalid stage name raises ValueError
    try:
        normalize_stage("unknown_invalid_stage")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_sequential_lineage_predecessors() -> None:
    """Prove canonical lineage order and exact predecessor requirements."""
    assert STAGE_PREDECESSORS[TrainingStage.SEMANTIC] is None
    assert STAGE_PREDECESSORS[TrainingStage.DOMAIN] == TrainingStage.SEMANTIC
    assert STAGE_PREDECESSORS[TrainingStage.COGNITION] == TrainingStage.DOMAIN
    assert STAGE_PREDECESSORS[TrainingStage.TOOLS] == TrainingStage.COGNITION
    assert STAGE_PREDECESSORS[TrainingStage.BEHAVIOR] == TrainingStage.TOOLS
    assert STAGE_PREDECESSORS[TrainingStage.FINAL] == TrainingStage.BEHAVIOR


def test_chain_manager_parent_validation() -> None:
    """Prove stage validation logic across all stages with mock checkpoints."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        mgr = CheckpointChainManager(Path(tmp_dir))

        # 1. Semantic (Stage 1) requires NO parent
        ok, msg = mgr.validate_parent(TrainingStage.SEMANTIC, None)
        assert ok is True, f"Semantic should need no parent: {msg}"

        ok, msg = mgr.validate_parent("semantic", None)
        assert ok is True

        # 2. Domain (Stage 2) requires semantic parent
        ok, msg = mgr.validate_parent(TrainingStage.DOMAIN, None)
        assert ok is False
        assert "requires a valid parent checkpoint from 'semantic'" in msg

        # Register semantic checkpoint
        dummy_weights = Path(tmp_dir) / "dummy.pt"
        dummy_weights.write_text("weights")
        semantic_meta = mgr.register_checkpoint(
            stage=TrainingStage.SEMANTIC,
            checkpoint_name="nairallm_v1_semantic_checkpoint",
            weights_path=dummy_weights,
        )
        semantic_meta_path = Path(tmp_dir) / "semantic" / "nairallm_v1_semantic_checkpoint_metadata.json"
        assert semantic_meta_path.exists()

        # Now Domain with valid semantic parent passes
        ok, msg = mgr.validate_parent(TrainingStage.DOMAIN, semantic_meta_path)
        assert ok is True, f"Domain with semantic parent should pass: {msg}"

        # Register domain checkpoint
        domain_meta = mgr.register_checkpoint(
            stage=TrainingStage.DOMAIN,
            checkpoint_name="nairallm_v1_domain_checkpoint",
            weights_path=dummy_weights,
            parent_metadata_path=semantic_meta_path,
        )
        domain_meta_path = Path(tmp_dir) / "domain" / "nairallm_v1_domain_checkpoint_metadata.json"

        # 3. Cognition (Stage 3) requires domain parent
        ok, msg = mgr.validate_parent(TrainingStage.COGNITION, None)
        assert ok is False

        ok, msg = mgr.validate_parent(TrainingStage.COGNITION, domain_meta_path)
        assert ok is True

        # Register cognition checkpoint
        cog_meta = mgr.register_checkpoint(
            stage=TrainingStage.COGNITION,
            checkpoint_name="nairallm_v1_cognition_checkpoint",
            weights_path=dummy_weights,
            parent_metadata_path=domain_meta_path,
        )
        cog_meta_path = Path(tmp_dir) / "cognition" / "nairallm_v1_cognition_checkpoint_metadata.json"

        # 4. Tools (Stage 4) requires cognition parent
        ok, msg = mgr.validate_parent(TrainingStage.TOOLS, cog_meta_path)
        assert ok is True

        # Tools with wrong parent (e.g. semantic) fails with clear message
        ok, msg = mgr.validate_parent(TrainingStage.TOOLS, semantic_meta_path)
        assert ok is False
        assert "Stage lineage mismatch" in msg

        # Register tools checkpoint
        tools_meta = mgr.register_checkpoint(
            stage=TrainingStage.TOOLS,
            checkpoint_name="nairallm_v1_tools_checkpoint",
            weights_path=dummy_weights,
            parent_metadata_path=cog_meta_path,
        )
        tools_meta_path = Path(tmp_dir) / "tools" / "nairallm_v1_tools_checkpoint_metadata.json"

        # 5. Behavior (Stage 5) requires tools parent
        ok, msg = mgr.validate_parent(TrainingStage.BEHAVIOR, tools_meta_path)
        assert ok is True

        ok, msg = mgr.validate_parent(TrainingStage.BEHAVIOR, domain_meta_path)
        assert ok is False


def test_foundation_checkpoint_stage_compatibility() -> None:
    """Verify that existing foundation checkpoint is recognized as valid semantic parent for Stage 2 (Domain)."""
    foundation_meta_path = workspace_root / "NairaLLM" / "training" / "checkpoints" / "foundation" / "foundation_checkpoint_metadata.json"
    assert foundation_meta_path.exists(), "Foundation checkpoint metadata must exist"

    mgr = CheckpointChainManager()
    ok, msg = mgr.validate_parent("domain", foundation_meta_path)
    assert ok is True, f"Domain stage must accept foundation_checkpoint_metadata.json as valid parent: {msg}"


if __name__ == "__main__":
    test_training_stage_enum()
    print("test_training_stage_enum: PASSED")
    test_stage_normalization_and_aliases()
    print("test_stage_normalization_and_aliases: PASSED")
    test_sequential_lineage_predecessors()
    print("test_sequential_lineage_predecessors: PASSED")
    test_chain_manager_parent_validation()
    print("test_chain_manager_parent_validation: PASSED")
    test_foundation_checkpoint_stage_compatibility()
    print("test_foundation_checkpoint_stage_compatibility: PASSED")
    print("\nALL 5 REGRESSION TESTS PASSED SUCCESSFULLY!")
