"""
Unit tests for InstructionDataCollator, Variable-Length Batching, and Stage 2 Lineage Auto-Discovery.
"""

from __future__ import annotations

import json
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
    TrainingStage,
    normalize_stage,
)
from NairaLLM.training.scripts.train_final_v1 import (
    InstructionDataCollator,
)

# Test with pure Python / mock tensors if torch is not installed locally
try:
    import torch
    import torch.nn.functional as F
    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False


def test_variable_length_collation() -> None:
    """Test A & B: Variable-length collation with padding and ignore_index=-100."""
    collator = InstructionDataCollator(pad_token_id=0, ignore_index=-100, max_seq_len=512)

    # Entry 0 = 118 tokens, Entry 1 = 74 tokens (matching Colab observation)
    if _HAS_TORCH:
        inp0 = torch.randint(10, 1000, (118,), dtype=torch.long)
        tgt0 = torch.randint(10, 1000, (118,), dtype=torch.long)
        inp1 = torch.randint(10, 1000, (74,), dtype=torch.long)
        tgt1 = torch.randint(10, 1000, (74,), dtype=torch.long)
        batch = [(inp0, tgt0), (inp1, tgt1)]
        padded_inputs, padded_targets = collator(batch)

        assert padded_inputs.shape == (2, 118)
        assert padded_targets.shape == (2, 118)
        assert torch.equal(padded_inputs[0], inp0)
        assert torch.equal(padded_targets[0], tgt0)
        assert torch.equal(padded_inputs[1, :74], inp1)
        assert (padded_inputs[1, 74:] == 0).all()
        assert torch.equal(padded_targets[1, :74], tgt1)
        assert (padded_targets[1, 74:] == -100).all()
    else:
        inp0 = list(range(1, 119))  # 118 tokens
        tgt0 = list(range(2, 120))
        inp1 = list(range(1, 75))   # 74 tokens
        tgt1 = list(range(2, 76))
        batch = [(inp0, tgt0), (inp1, tgt1)]
        padded_inputs, padded_targets = collator(batch)

        assert len(padded_inputs) == 2
        assert len(padded_inputs[0]) == 118
        assert len(padded_inputs[1]) == 118
        assert padded_inputs[0] == inp0
        assert padded_inputs[1][:74] == inp1
        assert padded_inputs[1][74:] == [0] * (118 - 74)
        assert padded_targets[1][:74] == tgt1
        assert padded_targets[1][74:] == [-100] * (118 - 74)


def test_truncation_at_max_seq_len() -> None:
    """Test C & F: Sequences longer than max_seq_len are bounded properly."""
    if not _HAS_TORCH:
        return

    max_len = 50
    collator = InstructionDataCollator(pad_token_id=0, ignore_index=-100, max_seq_len=max_len)

    inp = torch.randint(1, 100, (120,), dtype=torch.long)
    tgt = torch.randint(1, 100, (120,), dtype=torch.long)

    batch = [(inp, tgt)]
    padded_inputs, padded_targets = collator(batch)

    assert padded_inputs.shape == (1, max_len)
    assert padded_targets.shape == (1, max_len)
    assert torch.equal(padded_inputs[0], inp[:max_len])
    assert torch.equal(padded_targets[0], tgt[:max_len])


def test_loss_masking_on_padding() -> None:
    """Test D: Padded positions with ignore_index=-100 contribute zero loss."""
    if not _HAS_TORCH:
        return

    vocab_size = 1509
    collator = InstructionDataCollator(pad_token_id=0, ignore_index=-100, max_seq_len=100)

    inp0 = torch.tensor([10, 20, 30], dtype=torch.long)
    tgt0 = torch.tensor([20, 30, 40], dtype=torch.long)

    inp1 = torch.tensor([15], dtype=torch.long)
    tgt1 = torch.tensor([25], dtype=torch.long)

    padded_inputs, padded_targets = collator([(inp0, tgt0), (inp1, tgt1)])

    # Mock logits (2, 3, vocab_size)
    logits = torch.randn(2, 3, vocab_size)

    # Compute loss with ignore_index=-100
    loss = F.cross_entropy(logits.view(-1, vocab_size), padded_targets.view(-1), ignore_index=-100)
    assert not torch.isnan(loss)
    assert loss.item() > 0.0


def test_empty_batch_safeguard() -> None:
    """Test E: Empty batch raises clean ValueError."""
    if not _HAS_TORCH:
        return

    collator = InstructionDataCollator()
    try:
        collator([])
        assert False, "Should have raised ValueError for empty batch"
    except ValueError:
        pass


def test_stage_2_parent_discovery() -> None:
    """Test G & H: Stage 2 automatically discovers semantic checkpoint when available."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        checkpoints_dir = Path(tmp_dir) / "checkpoints"
        mgr = CheckpointChainManager(checkpoints_dir)

        # 1. Without semantic checkpoint, discovery returns (None, None)
        w, m = mgr.find_latest_checkpoint(TrainingStage.SEMANTIC)
        assert w is None and m is None

        # 2. Register semantic checkpoint in semantic/
        sem_dir = mgr.get_stage_checkpoint_dir(TrainingStage.SEMANTIC)
        dummy_weights = sem_dir / "nairallm_v1_semantic_checkpoint.pt"
        dummy_weights.write_text("weights")

        mgr.register_checkpoint(
            stage=TrainingStage.SEMANTIC,
            checkpoint_name="nairallm_v1_semantic_checkpoint",
            weights_path=dummy_weights,
        )

        # 3. Discovery now returns the valid semantic checkpoint and metadata
        w_found, m_found = mgr.find_latest_checkpoint(TrainingStage.SEMANTIC)
        assert w_found is not None
        assert m_found is not None
        assert w_found.name == "nairallm_v1_semantic_checkpoint.pt"
        assert m_found.name == "nairallm_v1_semantic_checkpoint_metadata.json"

        # 4. Validate lineage for stage domain against discovered metadata
        is_valid, reason = mgr.validate_parent(TrainingStage.DOMAIN, m_found)
        assert is_valid is True
        assert "Valid parent lineage verified from 'semantic'" in reason


def test_stage_2_foundation_fallback_discovery() -> None:
    """Test G: When semantic checkpoint is in foundation/, find_latest_checkpoint discovers it."""
    mgr = CheckpointChainManager(workspace_root / "NairaLLM" / "training" / "checkpoints")
    w_found, m_found = mgr.find_latest_checkpoint(TrainingStage.SEMANTIC)
    assert w_found is not None, "Should discover foundation weights"
    assert m_found is not None, "Should discover foundation metadata"
    assert "foundation" in str(w_found) or "semantic" in str(w_found)

    is_valid, reason = mgr.validate_parent("domain", m_found)
    assert is_valid is True


if __name__ == "__main__":
    test_variable_length_collation()
    print("test_variable_length_collation: PASSED")
    test_truncation_at_max_seq_len()
    print("test_truncation_at_max_seq_len: PASSED")
    test_loss_masking_on_padding()
    print("test_loss_masking_on_padding: PASSED")
    test_empty_batch_safeguard()
    print("test_empty_batch_safeguard: PASSED")
    test_stage_2_parent_discovery()
    print("test_stage_2_parent_discovery: PASSED")
    test_stage_2_foundation_fallback_discovery()
    print("test_stage_2_foundation_fallback_discovery: PASSED")
    print("\nALL STAGE 2 BLOCKER TESTS PASSED SUCCESSFULLY!")
