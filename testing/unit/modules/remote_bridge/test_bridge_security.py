"""Unit tests for Cryptographic Security Registrar & Action Risk Engine."""

from __future__ import annotations

import datetime
from typing import Any, Dict

import pytest

from backend.modules.remote_bridge.bridge_security import (
    DEFAULT_RISK_SCORES,
    RiskEngine,
    SecurityRegistrar,
    evaluate_risk,
    sign_command,
)


class TestSecurityRegistrar:
    """Test cryptographic payload signing and verification."""

    def test_sign_command_injects_security_fields(self) -> None:
        """Verify sign_command injects timestamp, nonce, and signature."""
        payload = {"action": "TOGGLE_WIFI", "device_id": "android_123"}
        signed = sign_command(payload)

        assert "timestamp" in signed
        assert "nonce" in signed
        assert "signature" in signed
        assert signed["action"] == "TOGGLE_WIFI"
        assert signed["device_id"] == "android_123"
        assert len(signed["nonce"]) == 32  # 16 bytes hex token
        assert len(signed["signature"]) == 64  # SHA256 hex digest length

    def test_sign_command_nonce_uniqueness(self) -> None:
        """Verify nonces generated across calls are unique."""
        payload = {"action": "READ_SMS"}
        signed1 = sign_command(payload)
        signed2 = sign_command(payload)

        assert signed1["nonce"] != signed2["nonce"]
        assert signed1["signature"] != signed2["signature"]

    def test_verify_signature_success(self) -> None:
        """Verify valid signed payload passes signature verification."""
        registrar = SecurityRegistrar(master_key="secret-key-test")
        payload = {"action": "OPEN_BANK_APP", "amount": 1000}
        signed = registrar.sign_command(payload)

        assert registrar.verify_signature(signed) is True

    def test_verify_signature_detects_data_tampering(self) -> None:
        """Verify modifying payload content invalidates signature verification."""
        registrar = SecurityRegistrar(master_key="secret-key-test")
        payload = {"action": "OPEN_BANK_APP", "amount": 1000}
        signed = registrar.sign_command(payload)

        # Tamper with payload data
        signed["amount"] = 99999
        assert registrar.verify_signature(signed) is False

    def test_verify_signature_detects_invalid_signature(self) -> None:
        """Verify corrupted signature string fails verification."""
        registrar = SecurityRegistrar(master_key="secret-key-test")
        payload = {"action": "LOCK_DEVICE"}
        signed = registrar.sign_command(payload)

        signed["signature"] = "a" * 64
        assert registrar.verify_signature(signed) is False

    def test_verify_signature_rejects_expired_timestamp(self) -> None:
        """Verify expired timestamp fails replay protection check."""
        registrar = SecurityRegistrar(master_key="secret-key-test")
        payload = {"action": "READ_SMS"}
        signed = registrar.sign_command(payload)

        # Set timestamp to 10 minutes in the past
        past_dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=600)
        signed["timestamp"] = past_dt.isoformat()

        assert registrar.verify_signature(signed, max_age_seconds=300) is False

    def test_verify_signature_missing_fields(self) -> None:
        """Verify missing timestamp, nonce, or signature fields fail verification."""
        registrar = SecurityRegistrar()

        assert registrar.verify_signature({}) is False
        assert registrar.verify_signature({"timestamp": "2026-01-01T00:00:00Z", "nonce": "abc"}) is False

    def test_custom_master_key_isolation(self) -> None:
        """Verify signature signed with key A fails verification with key B."""
        registrar_a = SecurityRegistrar(master_key="key-a")
        registrar_b = SecurityRegistrar(master_key="key-b")

        signed_a = registrar_a.sign_command({"action": "TOGGLE_WIFI"})
        assert registrar_a.verify_signature(signed_a) is True
        assert registrar_b.verify_signature(signed_a) is False


class TestRiskEngine:
    """Test action risk score evaluation and biometric requirements."""

    def test_evaluate_risk_low_risk_action(self) -> None:
        """Verify low-risk action (TOGGLE_WIFI) score and biometric flag."""
        res = evaluate_risk("TOGGLE_WIFI")

        assert res["action"] == "TOGGLE_WIFI"
        assert res["risk_score"] == 10
        assert res["requires_biometric"] is False

    def test_evaluate_risk_medium_risk_action(self) -> None:
        """Verify medium-risk action (READ_SMS) score and biometric flag."""
        res = evaluate_risk("READ_SMS")

        assert res["action"] == "READ_SMS"
        assert res["risk_score"] == 40
        assert res["requires_biometric"] is False

    def test_evaluate_risk_high_risk_action(self) -> None:
        """Verify high-risk action (OPEN_BANK_APP) score > 80 triggers biometric flag."""
        res = evaluate_risk("OPEN_BANK_APP")

        assert res["action"] == "OPEN_BANK_APP"
        assert res["risk_score"] == 95
        assert res["requires_biometric"] is True

    def test_evaluate_risk_case_insensitive_and_whitespace(self) -> None:
        """Verify action string is normalized for dictionary lookup."""
        res = evaluate_risk("  open_bank_app  ")

        assert res["risk_score"] == 95
        assert res["requires_biometric"] is True

    def test_evaluate_risk_unknown_action(self) -> None:
        """Verify unlisted action returns default risk score."""
        res = evaluate_risk("CUSTOM_UNKNOWN_ACTION")

        assert res["risk_score"] == 50
        assert res["requires_biometric"] is False

    def test_custom_risk_scores_engine(self) -> None:
        """Verify RiskEngine accepts custom risk score mappings."""
        custom_engine = RiskEngine({"CUSTOM_SAFE": 5, "CUSTOM_DANGEROUS": 85})

        res_safe = custom_engine.evaluate_risk("CUSTOM_SAFE")
        assert res_safe["risk_score"] == 5
        assert res_safe["requires_biometric"] is False

        res_danger = custom_engine.evaluate_risk("CUSTOM_DANGEROUS")
        assert res_danger["risk_score"] == 85
        assert res_danger["requires_biometric"] is True
