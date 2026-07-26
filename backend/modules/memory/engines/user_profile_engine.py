"""
UserProfileEngine — manages explicit and inferred user preferences and settings.

Uses the central SQLiteStore instance for persistence.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.modules.memory.sqlite_store import SQLiteStore


class UserProfileEngine:
    """Engine for persisting and querying key-value user profile information.

    Parameters
    ----------
    store : SQLiteStore
        Shared SQLite store instance.
    logger : logging.Logger | None
        Module logger instance.
    """

    def __init__(self, store: SQLiteStore, logger: logging.Logger | None = None) -> None:
        self._store = store
        self._logger = logger

    def set(
        self,
        key: str,
        value: Any,
        data_type: str = "string",
        source: str = "stated",
        confidence: float = 1.0,
    ) -> bool:
        """Store a user profile key-value pair.

        Parameters
        ----------
        key : str
            Profile key.
        value : Any
            Profile value.
        data_type : str
            Type hint ('string', 'int', 'float', 'bool', 'json').
        source : str
            Source of profile entry.
        confidence : float
            Confidence score (0.0 to 1.0).

        Returns
        -------
        bool
            True if stored successfully.
        """
        now = time.time()
        # Automatically adjust data_type and string representation if complex types passed
        if isinstance(value, (dict, list)):
            val_str = json.dumps(value)
            data_type = "json"
        elif isinstance(value, bool):
            val_str = str(value).lower()
            data_type = "bool"
        elif isinstance(value, (int, float)):
            val_str = str(value)
            data_type = "int" if isinstance(value, int) else "float"
        else:
            val_str = str(value)

        try:
            conn = self._store._require_conn()
            with self._store._write_lock:
                conn.execute(
                    """
                    INSERT INTO user_profile (
                        profile_key, profile_value, data_type, confidence, source, updated_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(profile_key) DO UPDATE SET
                        profile_value = excluded.profile_value,
                        data_type = excluded.data_type,
                        confidence = excluded.confidence,
                        source = excluded.source,
                        updated_at = excluded.updated_at
                    """,
                    (key, val_str, data_type, confidence, source, now, now),
                )
                conn.commit()
            return True
        except Exception as exc:
            if self._logger:
                self._logger.warning("UserProfileEngine.set failed for key %s: %s", key, exc)
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Fetch value for a profile key, deserializing to original type.

        Parameters
        ----------
        key : str
            Profile key.
        default : Any
            Default value if key does not exist.

        Returns
        -------
        Any
            Deserialized value or default.
        """
        try:
            conn = self._store._require_conn()
            row = conn.execute(
                "SELECT * FROM user_profile WHERE profile_key = ?", (key,)
            ).fetchone()

            if not row:
                return default

            val_str = row["profile_value"]
            row_dict = dict(row)
            dtype = row_dict.get("data_type", "string")

            if dtype == "json":
                try:
                    return json.loads(val_str)
                except Exception:
                    return val_str
            elif dtype == "int":
                try:
                    return int(val_str)
                except ValueError:
                    return val_str
            elif dtype == "float":
                try:
                    return float(val_str)
                except ValueError:
                    return val_str
            elif dtype == "bool":
                return val_str.lower() in ("true", "1", "yes")
            return val_str
        except Exception as exc:
            if self._logger:
                self._logger.warning("UserProfileEngine.get failed for key %s: %s", key, exc)
            return default

    def get_all(self, source: str | None = None) -> dict[str, Any]:
        """Return all user profile entries as a dictionary of key-value pairs.

        Parameters
        ----------
        source : str | None
            Optional source filter.

        Returns
        -------
        dict[str, Any]
            Key-value profile dictionary.
        """
        try:
            conn = self._store._require_conn()
            if source:
                rows = conn.execute(
                    "SELECT * FROM user_profile WHERE source = ? ORDER BY profile_key",
                    (source,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM user_profile ORDER BY profile_key"
                ).fetchall()

            result = {}
            for row in rows:
                r_dict = dict(row)
                key = r_dict["profile_key"]
                val_str = r_dict["profile_value"]
                dtype = r_dict.get("data_type", "string")

                if dtype == "json":
                    try:
                        val = json.loads(val_str)
                    except Exception:
                        val = val_str
                elif dtype == "int":
                    try:
                        val = int(val_str)
                    except ValueError:
                        val = val_str
                elif dtype == "float":
                    try:
                        val = float(val_str)
                    except ValueError:
                        val = val_str
                elif dtype == "bool":
                    val = val_str.lower() in ("true", "1", "yes")
                else:
                    val = val_str

                result[key] = val
            return result
        except Exception as exc:
            if self._logger:
                self._logger.warning("UserProfileEngine.get_all failed: %s", exc)
            return {}

    def set_bulk(self, data: dict[str, Any], source: str = "stated") -> int:
        """Bulk set key-value profile items.

        Parameters
        ----------
        data : dict
            Key-value items to set.
        source : str
            Source attribution.

        Returns
        -------
        int
            Count of successfully set keys.
        """
        count = 0
        for k, v in data.items():
            if self.set(k, v, source=source):
                count += 1
        return count

    def delete(self, key: str) -> bool:
        """Delete a profile key.

        Parameters
        ----------
        key : str
            Profile key to remove.

        Returns
        -------
        bool
            True if deleted.
        """
        try:
            conn = self._store._require_conn()
            with self._store._write_lock:
                conn.execute("DELETE FROM user_profile WHERE profile_key = ?", (key,))
                conn.commit()
            return True
        except Exception as exc:
            if self._logger:
                self._logger.warning("UserProfileEngine.delete failed for key %s: %s", key, exc)
            return False

    def get_summary_for_prompt(self) -> str:
        """Generate formatted user profile summary for system prompts.

        Format:
        User profile:
        • [key]: [value]

        Returns
        -------
        str
            Formatted summary or empty string.
        """
        profile = self.get_all()
        if not profile:
            return ""

        lines = ["User profile:"]
        for key, val in profile.items():
            lines.append(f"• {key}: {val}")

        return "\n".join(lines)

    def bootstrap_from_config(self, config_path: str = "config/user.json") -> bool:
        """Load initial profile settings from user JSON config if file exists.

        Parameters
        ----------
        config_path : str
            Path to user JSON configuration file.

        Returns
        -------
        bool
            True if loaded successfully, False if file doesn't exist or failed.
        """
        p = Path(config_path)
        if not p.is_file():
            return False

        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict):
                self.set_bulk(data, source="config")
                return True
            return False
        except Exception as exc:
            if self._logger:
                self._logger.warning(
                    "UserProfileEngine.bootstrap_from_config failed for %s: %s",
                    config_path,
                    exc,
                )
            return False
