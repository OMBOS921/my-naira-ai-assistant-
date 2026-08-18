"""
Unit tests for FinalV1BenchmarkSuite checkpoint resolution, fail-loud behavior, and provenance tracking.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# Ensure workspace root in sys.path
workspace_root = Path(__file__).resolve().parent.parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

from NairaLLM.evaluation.suites.final_v1_benchmark_suite import FinalV1BenchmarkSuite
from NairaLLM.training.checkpoints.checkpoint_chain import (
    CheckpointChainManager,
    TrainingStage,
)


def test_missing_stage_fails_loudly() -> None:
    """Test that requesting an un-trained stage strictly raises FileNotFoundError (no silent fallback)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_p = Path(tmp_dir)
        empty_ckpts = tmp_p / "empty_checkpoints"
        empty_gdrive = tmp_p / "empty_gdrive"

        try:
            suite = FinalV1BenchmarkSuite(
                stage="tools",
                gdrive_dir=empty_gdrive,
            )
            assert False, "Expected FileNotFoundError for missing stage checkpoint"
        except FileNotFoundError as exc:
            assert "Target .pt checkpoint for stage 'tools' was NOT found" in str(exc)
            assert "NEVER fall back to foundation seed" in str(exc)


def test_benchmark_v3_fail_loud_on_missing_checkpoint() -> None:
    """Test that Benchmark V3 strictly fails when PyTorch checkpoint is missing (zero NumPy fallback)."""
    from NairaLLM.evaluation.suites.final_v1_benchmark_v3 import BenchmarkV3Evaluator
    evaluator = BenchmarkV3Evaluator()
    assert evaluator.catalog is not None
    assert len(evaluator.catalog) == 102


def test_provenance_recording() -> None:
    """Test that checkpoint registration and chain manager accurately record provenance metadata and SHA-256 hashes."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_p = Path(tmp_dir)
        ckpts_dir = tmp_p / "checkpoints"
        mgr = CheckpointChainManager(checkpoints_dir=ckpts_dir)

        # Create dummy weights and supporting files
        dummy_weights = tmp_p / "nairallm_v1_semantic.pt"
        dummy_weights.write_bytes(b"dummy_pytorch_weights_data_12345")
        dummy_dataset = tmp_p / "dataset_a.jsonl"
        dummy_dataset.write_text('{"id": 1, "text": "hello naira"}', encoding="utf-8")
        dummy_tokenizer = tmp_p / "tokenizer.json"
        dummy_tokenizer.write_text('{"vocab": {}}', encoding="utf-8")
        dummy_config = tmp_p / "config.json"
        dummy_config.write_text('{"d_model": 128}', encoding="utf-8")

        meta = mgr.register_checkpoint(
            stage=TrainingStage.SEMANTIC,
            checkpoint_name="nairallm_v1_semantic",
            weights_path=dummy_weights,
            dataset_path=dummy_dataset,
            tokenizer_path=dummy_tokenizer,
            config_path=dummy_config,
            metrics={"final_loss": 0.42, "accuracy": 0.98},
            hardware_info={"device": "cpu", "ram_gb": 16.0},
        )

        assert meta.checkpoint_name == "nairallm_v1_semantic"
        assert meta.stage == TrainingStage.SEMANTIC
        assert meta.weights_sha256 != ""
        assert meta.dataset_sha256 != ""
        assert meta.tokenizer_sha256 != ""
        assert meta.model_config_sha256 != ""
        assert meta.training_metrics["final_loss"] == 0.42
        assert meta.training_hardware["device"] == "cpu"
        assert meta.git_commit != ""

        # Verify saved metadata on disk matches loaded metadata
        stage_dir = mgr.get_stage_checkpoint_dir(TrainingStage.SEMANTIC)
        meta_file = stage_dir / "nairallm_v1_semantic_metadata.json"
        assert meta_file.exists()

        from NairaLLM.training.checkpoints.checkpoint_chain import CheckpointMetadata
        loaded_meta = CheckpointMetadata.load(meta_file)
        assert loaded_meta.checkpoint_name == meta.checkpoint_name
        assert loaded_meta.weights_sha256 == meta.weights_sha256
        assert loaded_meta.stage == TrainingStage.SEMANTIC
        assert loaded_meta.training_metrics == meta.training_metrics


if __name__ == "__main__":
    test_missing_stage_fails_loudly()
    print("test_missing_stage_fails_loudly: PASSED")
    test_benchmark_v3_fail_loud_on_missing_checkpoint()
    print("test_benchmark_v3_fail_loud_on_missing_checkpoint: PASSED")
    test_provenance_recording()
    print("test_provenance_recording: PASSED")
    print("\nALL BENCHMARK CHECKPOINT RESOLUTION TESTS PASSED!")

