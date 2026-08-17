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


def test_provenance_recording() -> None:
    """Test that benchmark execution generates comprehensive provenance metadata."""
    foundation_weights = workspace_root / "NairaLLM" / "training" / "checkpoints" / "foundation" / "naira_semantic_105k_numpy.npz"
    suite = FinalV1BenchmarkSuite(
        checkpoint_path=foundation_weights,
        stage="semantic_seed",
    )
    # Run small evaluation on first 5 cases
    suite.test_cases = suite.test_cases[:5]
    report = suite.run_benchmark(max_new_tokens=10)

    assert "provenance" in report, "Report missing provenance dictionary"
    prov = report["provenance"]

    required_keys = [
        "evaluated_checkpoint_path",
        "evaluated_checkpoint_sha256",
        "stage_name",
        "model_parameter_count",
        "git_commit",
        "tokenizer_hash",
        "dataset_hashes",
        "device",
        "backend",
        "real_checkpoint_evaluated",
    ]

    for k in required_keys:
        assert k in prov, f"Missing required provenance field: {k}"

    assert prov["stage_name"] == "semantic_seed"
    assert prov["real_checkpoint_evaluated"] is False  # Because it's numpy seed, not real .pt


if __name__ == "__main__":
    test_missing_stage_fails_loudly()
    print("test_missing_stage_fails_loudly: PASSED")
    test_provenance_recording()
    print("test_provenance_recording: PASSED")
    print("\nALL BENCHMARK CHECKPOINT RESOLUTION TESTS PASSED!")
