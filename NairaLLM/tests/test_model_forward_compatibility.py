"""
Regression Test for NairaTransformer forward() output contract & training script import safety.

Verifies:
1. NairaTransformer.forward() returns a 3-tuple (logits, loss, kv_caches).
2. Logits extraction out[0] or tuple unpacking correctly yields [batch, seq_len, vocab_size].
3. Full single step: forward + loss + backward + optimizer step succeeds without TypeError.
4. Importing train_final_once does NOT execute training.
"""

from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

import pytest
from NairaLLM.model.config.model_config import NairaModelConfig

try:
    import torch
    import torch.nn as nn
    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False


def test_training_script_import_safety():
    """Verify that importing train_final_once does not execute training or side effects."""
    import NairaLLM.training.scripts.train_final_once as trainer_mod
    assert hasattr(trainer_mod, "OneShotFinalTrainer")
    assert hasattr(trainer_mod, "main")


@pytest.mark.skipif(not _HAS_TORCH, reason="PyTorch is required for forward/backward tensor tests")
def test_naira_transformer_forward_contract_and_backward_step():
    """Test NairaLLM-30M forward pass return type, logits shape, loss computation, backward pass, and optimizer step."""
    from NairaLLM.model.architecture.naira_transformer import NairaTransformer

    cfg_path = WORKSPACE_ROOT / "NairaLLM" / "configs" / "final_nairallm_v1.json"
    cfg = NairaModelConfig.load(cfg_path)
    
    # 1. Instantiate NairaLLM-30M
    model = NairaTransformer(cfg)
    assert model.count_parameters() == 29368832 or sum(p.numel() for p in model.parameters()) == 29368832

    # 2. Forward pass with dummy batch [2, 16]
    batch_size = 2
    seq_len = 16
    input_ids = torch.randint(0, cfg.vocab_size, (batch_size, seq_len), dtype=torch.long)
    targets = torch.randint(0, cfg.vocab_size, (batch_size, seq_len), dtype=torch.long)

    out = model(input_ids)
    assert isinstance(out, tuple), f"Expected tuple return from forward(), got {type(out)}"
    assert len(out) == 3, f"Expected 3-tuple (logits, loss, kv_caches), got len {len(out)}"

    logits = out[0] if isinstance(out, tuple) else out
    assert logits.shape == (batch_size, seq_len, cfg.vocab_size), (
        f"Expected logits shape ({batch_size}, {seq_len}, {cfg.vocab_size}), got {logits.shape}"
    )

    # 3. Loss calculation (shift logits vs shift labels)
    shift_logits = logits[..., :-1, :].contiguous()
    shift_labels = targets[..., 1:].contiguous()
    criterion = nn.CrossEntropyLoss(ignore_index=-100)
    loss = criterion(shift_logits.view(-1, cfg.vocab_size), shift_labels.view(-1))
    assert loss.item() > 0.0

    # 4. Backward pass
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    optimizer.zero_grad()
    loss.backward()

    # 5. Optimizer step
    optimizer.step()
    optimizer.zero_grad()
