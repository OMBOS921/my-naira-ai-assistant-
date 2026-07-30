"""Cryptographic Security Registrar & Action Risk Engine.

Handles JSON command payload signing with master private keys, replay attack protection via timestamps & nonces,
signature verification, and risk evaluation for sensitive actions.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import os
import secrets
from typing import Any, Dict, Optional

DEFAULT_MASTER_KEY = "naira-os-remote-bridge-master-key-2026"
MAX_TIMESTAMP_AGE_SECONDS = 300  # 5 minutes replay window


class SecurityRegistrar:
    """Handles payload cryptographic signing and verification."""

    def __init__(self, master_key: Optional[str] = None) -> None:
        """Initialize SecurityRegistrar with a master private key.

        If master_key is not provided, tries reading REMOTE_BRIDGE_MASTER_KEY from env
        or falls back to DEFAULT_MASTER_KEY.
        """
        self.master_key = (
            master_key
            or os.environ.get("REMOTE_BRIDGE_MASTER_KEY")
            or DEFAULT_MASTER_KEY
        )

    def _canonicalize_payload(self, data: Dict[str, Any], timestamp: str, nonce: str) -> bytes:
        """Create a deterministic byte representation of payload data for signing."""
        clean_data = {k: v for k, v in data.items() if k not in ("signature", "timestamp", "nonce")}
        canonical_str = json.dumps(clean_data, sort_keys=True, separators=(",", ":"))
        signing_base = f"{timestamp}:{nonce}:{canonical_str}"
        return signing_base.encode("utf-8")

    def sign_command(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Inject timestamp, nonce, and cryptographic signature into payload.

        Args:
            action_data: Outgoing command payload dictionary.

        Returns:
            Dict containing action_data merged with timestamp, nonce, and signature.
        """
        payload = dict(action_data)
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        timestamp = now_utc.isoformat()
        nonce = secrets.token_hex(16)

        signing_base = self._canonicalize_payload(payload, timestamp, nonce)
        signature = hmac.new(
            self.master_key.encode("utf-8"),
            signing_base,
            hashlib.sha256,
        ).hexdigest()

        payload["timestamp"] = timestamp
        payload["nonce"] = nonce
        payload["signature"] = signature
        return payload

    def verify_signature(
        self, payload: Dict[str, Any], max_age_seconds: int = MAX_TIMESTAMP_AGE_SECONDS
    ) -> bool:
        """Verify signature, timestamp freshness, and nonce presence.

        Args:
            payload: Payload dictionary containing timestamp, nonce, and signature.
            max_age_seconds: Maximum allowed age for timestamp in seconds.

        Returns:
            True if signature is valid and payload is fresh; False otherwise.
        """
        if not isinstance(payload, dict):
            return False

        signature = payload.get("signature")
        timestamp = payload.get("timestamp")
        nonce = payload.get("nonce")

        if not signature or not timestamp or not nonce:
            return False

        # Validate timestamp freshness
        try:
            ts_dt = datetime.datetime.fromisoformat(timestamp)
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            if ts_dt.tzinfo is None:
                ts_dt = ts_dt.replace(tzinfo=datetime.timezone.utc)
            age = (now_dt - ts_dt).total_seconds()
            if abs(age) > max_age_seconds:
                return False
        except (ValueError, TypeError):
            return False

        # Re-compute expected signature
        signing_base = self._canonicalize_payload(payload, timestamp, nonce)
        expected_signature = hmac.new(
            self.master_key.encode("utf-8"),
            signing_base,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(signature, expected_signature)


# Module-level default registrar instance
_default_security_registrar = SecurityRegistrar()


def sign_command(action_data: Dict[str, Any], master_key: Optional[str] = None) -> Dict[str, Any]:
    """Sign JSON payload using master key, injecting timestamp, nonce, and signature.

    Args:
        action_data: Payload dictionary to sign.
        master_key: Optional custom key; uses default if omitted.

    Returns:
        Signed payload dictionary.
    """
    if master_key:
        registrar = SecurityRegistrar(master_key=master_key)
        return registrar.sign_command(action_data)
    return _default_security_registrar.sign_command(action_data)


# Predefined action risk scores
DEFAULT_RISK_SCORES: Dict[str, int] = {
    "TOGGLE_WIFI": 10,
    "TOGGLE_BLUETOOTH": 10,
    "SET_VOLUME": 15,
    "GET_BATTERY": 5,
    "TAKE_SCREENSHOT": 30,
    "READ_CONTACTS": 35,
    "READ_SMS": 40,
    "SEND_SMS": 70,
    "LOCATION_GET": 50,
    "LOCK_DEVICE": 20,
    "OPEN_APP": 25,
    "OPEN_BANK_APP": 95,
    "TRANSFER_FUNDS": 95,
    "CHANGE_PASSWORD": 90,
    "FACTORY_RESET": 100,
    "MAKE_CALL": 60,
}

DEFAULT_UNKNOWN_RISK_SCORE = 50
BIOMETRIC_RISK_THRESHOLD = 80


class RiskEngine:
    """Evaluates risk levels for remote control actions."""

    def __init__(self, risk_scores: Optional[Dict[str, int]] = None) -> None:
        """Initialize RiskEngine with a custom scoring dict or default scores."""
        self.risk_scores = dict(risk_scores or DEFAULT_RISK_SCORES)

    def evaluate_risk(self, action: str) -> Dict[str, Any]:
        """Evaluate risk score and biometric requirement for an action.

        Args:
            action: Action string name (e.g. 'TOGGLE_WIFI', 'OPEN_BANK_APP').

        Returns:
            Dict with action name, risk_score (0-100), and requires_biometric (bool).
        """
        normalized_action = str(action).strip().upper() if action else ""
        risk_score = self.risk_scores.get(normalized_action, DEFAULT_UNKNOWN_RISK_SCORE)
        requires_biometric = risk_score > BIOMETRIC_RISK_THRESHOLD

        return {
            "action": action,
            "risk_score": risk_score,
            "requires_biometric": requires_biometric,
        }


# Module-level default risk engine instance
_default_risk_engine = RiskEngine()


def evaluate_risk(action: str) -> Dict[str, Any]:
    """Module-level function to evaluate action risk score and biometric requirement.

    Args:
        action: Action name string.

    Returns:
        Dict with action, risk_score, and requires_biometric.
    """
    return _default_risk_engine.evaluate_risk(action)
