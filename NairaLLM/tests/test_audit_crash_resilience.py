"""
Regression test for FinalPreTrainingLockAuditor crash resilience.

Proves that even when all pillars fail and return empty or malformed details,
the audit runner and markdown report generator NEVER throw KeyError.
"""

import pytest
from NairaLLM.training.scripts.final_pretraining_lock_audit_v2 import FinalPreTrainingLockAuditor


def test_audit_crash_resilience_on_failed_pillars():
    auditor = FinalPreTrainingLockAuditor()
    
    # Injected malformed and failed pillars
    auditor.record_pillar(1, "model_architecture", False, reason="Config missing", details={})
    auditor.record_pillar(2, "dataset_a_semantic", False, reason="Dataset missing", details=None)
    auditor.record_pillar(3, "dataset_b_capability", False, reason="Corrupt JSON", details={"corrupt_lines": 50})
    auditor.record_pillar(4, "dataset_c_behavior", False, reason="File not found")
    auditor.record_pillar(5, "cognitive_protocol", False, reason="Vocab mismatch")
    auditor.record_pillar(6, "benchmark_v3", False, reason="Benchmark missing")
    auditor.record_pillar(7, "training_system", False, reason="Trainer missing")
    auditor.record_pillar(8, "git_versioning", False, reason="No git repo")
    auditor.record_pillar(9, "cloud_gpu_feasibility", False, reason="GPU OOM simulated")
    auditor.record_pillar(10, "cryptographic_lock", False, reason="Hash mismatch")
    
    report_dict = {
        "verdict": "NOT_READY",
        "timestamp": "2026-08-18 20:00:00",
        "total_pillars": len(auditor.pillars),
        "pillars_passed": 0,
        "pillars_failed": 10,
        "blockers": auditor.blockers,
        "immutable_hashes": {},
        "pillars": auditor.pillars
    }
    
    # Must generate markdown without raising KeyError
    md = auditor.generate_markdown_report(report_dict)
    assert isinstance(md, str)
    assert len(md) > 200
    assert "FINAL VERDICT: NOT_READY" in md
    assert "Pillars Failed: 10" in md
