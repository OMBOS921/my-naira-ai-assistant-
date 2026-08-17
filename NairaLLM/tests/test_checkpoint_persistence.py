"""
Unit test suite for Checkpoint Persistence, Google Drive Backup, and Auto-Restore.
"""

from __future__ import annotations

import json
import shutil
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
)


def test_persistent_backup_and_restore_cycle() -> None:
    """Test full cycle: local save -> persistent backup -> local wipe -> auto-restore."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_p = Path(tmp_dir)
        local_ckpts = tmp_p / "local_checkpoints"
        mock_gdrive = tmp_p / "mock_gdrive" / "checkpoints" / "final_v1"

        mgr = CheckpointChainManager(checkpoints_dir=local_ckpts, persistent_dir=mock_gdrive)

        # 1. Create a dummy domain checkpoint locally
        domain_dir = mgr.get_stage_checkpoint_dir(TrainingStage.DOMAIN)
        dummy_weights = domain_dir / "nairallm_v1_domain_checkpoint.pt"
        dummy_weights.write_text("DUMMY_DOMAIN_WEIGHTS_BINARY_CONTENT")

        meta = mgr.register_checkpoint(
            stage=TrainingStage.DOMAIN,
            checkpoint_name="nairallm_v1_domain_checkpoint",
            weights_path=dummy_weights,
            metrics={"final_loss": 7.3058},
        )
        meta_file = domain_dir / "nairallm_v1_domain_checkpoint_metadata.json"

        # 2. Trigger persistent backup to mock Google Drive
        backup_res = mgr.backup_checkpoint_to_persistent(
            stage=TrainingStage.DOMAIN,
            weights_path=dummy_weights,
            metadata_path=meta_file,
        )
        assert backup_res["backed_up"] is True, f"Backup failed: {backup_res}"

        gdrive_domain_dir = mock_gdrive / "domain"
        assert (gdrive_domain_dir / "nairallm_v1_domain_checkpoint.pt").exists()
        assert (gdrive_domain_dir / "nairallm_v1_domain_checkpoint_metadata.json").exists()
        assert (gdrive_domain_dir / "nairallm_v1_domain_manifest.json").exists()

        # 3. Simulate Colab Runtime Reset (wipe local domain directory)
        shutil.rmtree(domain_dir)
        assert not dummy_weights.exists()

        # 4. Run auto-discovery on new session with same persistent Google Drive mount
        mgr_new_session = CheckpointChainManager(checkpoints_dir=local_ckpts, persistent_dir=mock_gdrive)
        w_found, m_found = mgr_new_session.find_latest_checkpoint(TrainingStage.DOMAIN)

        assert w_found is not None, "Failed to restore weights from mock Google Drive"
        assert m_found is not None, "Failed to restore metadata from mock Google Drive"
        assert w_found.exists(), f"Restored weights file does not exist: {w_found}"
        assert w_found.read_text() == "DUMMY_DOMAIN_WEIGHTS_BINARY_CONTENT"

        # 5. Verify lineage validation for next stage (cognition)
        is_valid, reason = mgr_new_session.validate_parent(TrainingStage.COGNITION, m_found)
        assert is_valid is True, f"Lineage validation failed: {reason}"
        assert "Valid parent lineage verified from 'domain'" in reason


def test_missing_predecessor_strictly_fails() -> None:
    """Test that missing predecessor in both local and Drive returns None (blocking uninitialized training)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_p = Path(tmp_dir)
        local_ckpts = tmp_p / "empty_local"
        mock_gdrive = tmp_p / "empty_gdrive"

        mgr = CheckpointChainManager(checkpoints_dir=local_ckpts, persistent_dir=mock_gdrive)

        w_found, m_found = mgr.find_latest_checkpoint(TrainingStage.COGNITION)
        assert w_found is None and m_found is None

        is_valid, reason = mgr.validate_parent(TrainingStage.TOOLS, m_found)
        assert is_valid is False
        assert "requires a valid parent checkpoint from 'cognition', but none was found" in reason


if __name__ == "__main__":
    test_persistent_backup_and_restore_cycle()
    print("test_persistent_backup_and_restore_cycle: PASSED")
    test_missing_predecessor_strictly_fails()
    print("test_missing_predecessor_strictly_fails: PASSED")
    print("\nALL CHECKPOINT PERSISTENCE TESTS PASSED SUCCESSFULLY!")
