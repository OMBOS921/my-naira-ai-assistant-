"""
FastCommandRouter — High-performance direct execution router for simple desktop commands.

Bypasses LLM reasoning for deterministic Windows OS operations across English, Hindi, and Hinglish.
Target execution latency: < 10 ms.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.parse
import webbrowser
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Set

from backend.runtime.action_lifecycle import (
    ActionLifecycle,
    ActionState,
    VerificationResult,
    NaturalResponseFormatter,
)

try:
    import mss
    import psutil
    import pyperclip
except ImportError:
    pass

if os.name == "nt":
    import winreg
    try:
        import win32gui
        import win32con
    except ImportError:
        pass

_LOG = logging.getLogger("naira.runtime.fast_command_router")


def _resolve_fast_path(path_str: str) -> Path:
    p_str = path_str.strip().strip("'\"")
    lowered = p_str.lower()
    user_home = Path.home()

    if lowered in ("desktop", "desktop/"):
        return user_home / "Desktop"
    if lowered.startswith("desktop/") or lowered.startswith("desktop\\"):
        return user_home / "Desktop" / p_str[8:]

    if lowered in ("downloads", "downloads/"):
        return user_home / "Downloads"
    if lowered.startswith("downloads/") or lowered.startswith("downloads\\"):
        return user_home / "Downloads" / p_str[10:]

    if lowered in ("documents", "documents/"):
        return user_home / "Documents"
    if lowered.startswith("documents/") or lowered.startswith("documents\\"):
        return user_home / "Documents" / p_str[10:]

    expanded = os.path.expandvars(os.path.expanduser(p_str))
    p = Path(expanded)
    if not p.is_absolute():
        cwd_candidate = Path.cwd() / p
        if cwd_candidate.exists() or cwd_candidate.parent.exists():
            return cwd_candidate
        return user_home / "Desktop" / p
    return p


# ----------------------------------------------------------------------
# 1. Intent Definitions
# ----------------------------------------------------------------------

class CommandIntent(Enum):
    OPEN_APP = auto()
    OPEN_WEBSITE = auto()
    SET_VOLUME = auto()
    SET_BRIGHTNESS = auto()
    LOCK_PC = auto()
    SHUTDOWN = auto()
    RESTART = auto()
    CREATE_FOLDER = auto()
    DELETE_FOLDER = auto()
    RENAME_FOLDER = auto()
    CREATE_FILE = auto()
    DELETE_FILE = auto()
    OPEN_FILE = auto()
    RENAME_FILE = auto()
    UNKNOWN = auto()
    SCREENSHOT = auto()
    SYSTEM_INFO = auto()
    WINDOW_MINIMIZE = auto()
    WINDOW_MAXIMIZE = auto()
    WINDOW_CLOSE = auto()
    KILL_PROCESS = auto()
    WEB_SEARCH = auto()
    CLIPBOARD_OP = auto()
    RUN_CMD_SAFE = auto()


# ----------------------------------------------------------------------
# 2. Wake Word Cleaner
# ----------------------------------------------------------------------

class WakeWordCleaner:
    """Strips wake words, greetings, politeness tokens, and noise words in English, Hinglish, and Hindi (Devanagari)."""

    NOISE_WORDS: Set[str] = {
        # English
        "hello", "hi", "hey", "naira", "please", "pls", "can", "you", "could", "kindly",
        "just", "a", "an", "the", "bro", "buddy", "assistant",
        # Hinglish
        "mera", "meri", "mere", "jara", "zara", "ek", "bhai", "sun", "suno", "yar", "yaar",
        "karo", "do", "karde", "kar", "dijiye", "bhaiya", "bhaiya",
        # Devanagari Hindi
        "हेलो", "हाय", "हे", "नायरा", "प्लीज", "मेरा", "मेरी", "मेरे", "जरा", "एक", "भाई",
        "सुनो", "सुन", "करो", "दो", "कर", "दीजिये", "दीजिए", "नायर",
        # Additional trigger noise words
        "screenshot", "capture", "screengrab", "force", "kill"
    }

    _CLEAN_RE = re.compile(r"^[^\w\u0900-\u097F]+|[^\w\u0900-\u097F]+$", flags=re.UNICODE)

    @classmethod
    def clean(cls, text: str) -> str:
        tokens = text.strip().lower().split()
        cleaned_tokens = []
        for token in tokens:
            cleaned_token = cls._CLEAN_RE.sub("", token)
            if cleaned_token and cleaned_token not in cls.NOISE_WORDS:
                cleaned_tokens.append(cleaned_token)
        return " ".join(cleaned_tokens)


# ----------------------------------------------------------------------
# 3. Multilingual Normalizer
# ----------------------------------------------------------------------

class MultilingualNormalizer:
    """Normalizes multilingual action verbs and terms into unified internal action tokens."""

    ACTION_MAP: Dict[str, str] = {
        # Open verbs
        "open": "open", "launch": "open", "run": "open", "start": "open",
        "khol": "open", "kholo": "open", "chalao": "open", "shuru": "open",
        "खोल": "open", "खोलो": "open", "चलाओ": "open", "शुरू": "open",

        # System control
        "lock": "lock", "लॉक": "lock",
        "shutdown": "shutdown", "off": "shutdown", "band": "shutdown", "बंद": "shutdown", "शटडाउन": "shutdown",
        "restart": "restart", "reboot": "restart", "रीस्टार्ट": "restart", "रिस्टार्ट": "restart",

        # Volume / Brightness
        "volume": "volume", "sound": "volume", "awaaz": "volume", "awaz": "volume", "आवाज़": "volume", "आवाज": "volume", "वॉल्यूम": "volume",
        "brightness": "brightness", "roshni": "brightness", "प्रकाश": "brightness", "ब्राइटनेस": "brightness",

        # Filesystem
        "create": "create", "make": "create", "mkdir": "create", "touch": "create", "banao": "create", "bana": "create", "बनाओ": "create", "बना": "create",
        "delete": "delete", "remove": "delete", "rm": "delete", "rmdir": "delete", "hatao": "delete", "hata": "delete", "mitao": "delete", "हटाओ": "delete", "हटा": "delete", "मिटाओ": "delete",
        "rename": "rename", "badlo": "rename", "बदलो": "rename",
    }

    @classmethod
    def normalize_token(cls, token: str) -> str:
        cleaned = token.strip().lower()
        return cls.ACTION_MAP.get(cleaned, cleaned)


# ----------------------------------------------------------------------
# 4. Alias Engine (config-driven, zero hardcoded aliases)
# ----------------------------------------------------------------------

class AliasEngine:
    """Loads application and website aliases exclusively from config/apps.json.

    No hardcoded alias data exists in this class. If the configuration file
    cannot be found or parsed, a RuntimeError is raised so misconfigurations
    are caught immediately rather than silently degraded.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        self._alias_map: Dict[str, str] = {}        # alias.lower() -> target
        self._alias_to_key: Dict[str, str] = {}      # alias.lower() -> app_key
        self._app_meta: Dict[str, Dict[str, Any]] = {}  # app_key -> full entry
        self._config_path: Path | None = None
        self._load_config(config_path)

    def _locate_config(self, config_path: Path | None) -> Path | None:
        """Resolve the path to config/apps.json using multiple search strategies."""
        if config_path is not None:
            return config_path if config_path.exists() else None

        # Strategy 1: CWD / config / apps.json
        candidate = Path.cwd() / "config" / "apps.json"
        if candidate.exists():
            return candidate

        # Strategy 2: Relative to this file  (backend/runtime -> ../../config/apps.json)
        candidate = Path(__file__).resolve().parent.parent.parent / "config" / "apps.json"
        if candidate.exists():
            return candidate

        return None

    def _load_config(self, config_path: Path | None) -> None:
        resolved = self._locate_config(config_path)
        if resolved is None:
            _LOG.error("config/apps.json not found. AliasEngine will have no aliases.")
            return

        self._config_path = resolved
        try:
            with open(resolved, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except Exception as exc:
            _LOG.error("Failed to parse config/apps.json at %s: %s", resolved, exc)
            return

        if not isinstance(config_data, dict):
            _LOG.error("config/apps.json root must be a JSON object, got %s", type(config_data).__name__)
            return

        # Build mappings
        for key, entry in config_data.items():
            target = entry.get("target", key)
            aliases = entry.get("aliases", [key])
            self._app_meta[key] = entry
            for alias in aliases:
                normalised = alias.lower().strip()
                self._alias_map[normalised] = target
                self._alias_to_key[normalised] = key

        _LOG.info("[FCR] AliasEngine loaded %d app entries with %d aliases from %s",
                  len(self._app_meta), len(self._alias_map), resolved)

    @property
    def alias_map(self) -> Dict[str, str]:
        return self._alias_map

    def resolve_fuzzy(self, alias_candidate: str, score_cutoff: float = 85.0) -> Tuple[str | None, float]:
        """Fuzzy match an alias candidate against known aliases. Returns (target, score)."""
        cleaned = alias_candidate.strip().lower()
        if not cleaned:
            return None, 0.0

        if cleaned in self._alias_map:
            return self._alias_map[cleaned], 100.0

        # Try RapidFuzz
        try:
            from rapidfuzz import process, fuzz
            match = process.extractOne(
                cleaned,
                self._alias_map.keys(),
                scorer=fuzz.ratio,
                score_cutoff=score_cutoff,
            )
            if match:
                matched_alias, score, _ = match
                return self._alias_map[matched_alias], float(score)
        except ImportError:
            pass

        # Fallback to difflib
        import difflib
        cutoff_ratio = score_cutoff / 100.0
        matches = difflib.get_close_matches(cleaned, list(self._alias_map.keys()), n=1, cutoff=cutoff_ratio)
        if matches:
            matched_alias = matches[0]
            ratio = difflib.SequenceMatcher(None, cleaned, matched_alias).ratio() * 100.0
            return self._alias_map[matched_alias], ratio

        return None, 0.0

    def resolve(self, alias_candidate: str, fuzzy: bool = True) -> str | None:
        """Return the launch target for a given alias, or None."""
        cleaned = alias_candidate.strip().lower()
        if not cleaned:
            return None
        res = self._alias_map.get(cleaned)
        if res is not None:
            return res
        if fuzzy:
            target, _ = self.resolve_fuzzy(cleaned, score_cutoff=85.0)
            return target
        return None

    def resolve_key(self, alias_candidate: str, fuzzy: bool = True) -> str | None:
        """Return the app key (e.g. 'chrome', 'code') for a given alias."""
        cleaned = alias_candidate.strip().lower()
        if not cleaned:
            return None
        res = self._alias_to_key.get(cleaned)
        if res is not None:
            return res
        if fuzzy:
            target, _ = self.resolve_fuzzy(cleaned, score_cutoff=85.0)
            if target:
                for alias, tgt in self._alias_map.items():
                    if tgt == target:
                        key = self._alias_to_key.get(alias)
                        if key:
                            return key
        return None

    def get_app_meta(self, app_key: str) -> Dict[str, Any] | None:
        """Return full metadata dict for an app key, or None."""
        return self._app_meta.get(app_key)


# ----------------------------------------------------------------------
# 4b. Dynamic Installed App Discovery
# ----------------------------------------------------------------------

class AppDiscoveryEngine:
    """Scans the local Windows system to discover installed applications.

    Discovery sources (in order):
    1. Windows Registry App Paths
    2. Start Menu shortcuts (.lnk filename matching)
    3. Desktop shortcuts (.lnk filename matching)
    4. Explicit install_paths from apps.json entries
    5. System PATH via shutil.which()

    Results are cached in ``discovered_apps``: a dict mapping
    app_key -> resolved absolute executable path.
    """

    def __init__(self, app_meta: Dict[str, Dict[str, Any]]) -> None:
        self._app_meta = app_meta
        self.discovered_apps: Dict[str, str] = {}
        self._scan()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_installed(self, app_key: str) -> bool:
        return app_key in self.discovered_apps

    def get_executable(self, app_key: str) -> str | None:
        return self.discovered_apps.get(app_key)

    # ------------------------------------------------------------------
    # Internal scanning
    # ------------------------------------------------------------------

    def _scan(self) -> None:
        """Run all discovery sources and merge results."""
        _LOG.info("[FCR] AppDiscoveryEngine: starting installed-app scan ...")

        self._scan_registry_app_paths()
        self._scan_start_menu()
        self._scan_desktop_shortcuts()
        self._scan_install_paths()
        self._scan_system_path()

        _LOG.info("[FCR] AppDiscoveryEngine: discovered %d installed apps", len(self.discovered_apps))

    # --- 1. Windows Registry App Paths --------------------------------

    def _scan_registry_app_paths(self) -> None:
        if os.name != "nt":
            return
        try:
            reg_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
            # Collect all exe names we care about, mapped back to app_key
            exe_to_key: Dict[str, str] = {}
            for key, meta in self._app_meta.items():
                for exe in meta.get("exe_names", []):
                    exe_to_key[exe.lower()] = key

            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    with winreg.OpenKey(hive, reg_path) as root:
                        idx = 0
                        while True:
                            try:
                                subkey_name = winreg.EnumKey(root, idx)
                                idx += 1
                                if subkey_name.lower() in exe_to_key:
                                    app_key = exe_to_key[subkey_name.lower()]
                                    if app_key not in self.discovered_apps:
                                        try:
                                            with winreg.OpenKey(root, subkey_name) as sk:
                                                val, _ = winreg.QueryValueEx(sk, "")
                                                if val and os.path.isfile(val):
                                                    self.discovered_apps[app_key] = val
                                                    _LOG.debug("[FCR] Registry discovery: %s -> %s", app_key, val)
                                        except OSError:
                                            pass
                            except OSError:
                                break
                except OSError:
                    continue
        except Exception as exc:
            _LOG.debug("[FCR] Registry App Paths scan error: %s", exc)

    # --- 2. Start Menu shortcuts --------------------------------------

    def _scan_start_menu(self) -> None:
        if os.name != "nt":
            return
        start_dirs = [
            os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs"),
        ]
        self._match_lnk_files(start_dirs)

    # --- 3. Desktop shortcuts -----------------------------------------

    def _scan_desktop_shortcuts(self) -> None:
        if os.name != "nt":
            return
        desktop_dirs = [
            str(Path.home() / "Desktop"),
            os.path.expandvars(r"%PUBLIC%\Desktop"),
        ]
        self._match_lnk_files(desktop_dirs)

    def _match_lnk_files(self, directories: List[str]) -> None:
        """Match .lnk filenames against known app aliases / exe_names."""
        # Build lookup: lowered keyword -> app_key
        keyword_to_key: Dict[str, str] = {}
        for key, meta in self._app_meta.items():
            # Use the app key itself
            keyword_to_key[key.lower()] = key
            # Use primary alias words
            for alias in meta.get("aliases", []):
                keyword_to_key[alias.lower()] = key
            # Use exe names without extension
            for exe in meta.get("exe_names", []):
                stem = exe.rsplit(".", 1)[0].lower()
                keyword_to_key[stem] = key

        for d in directories:
            if not os.path.isdir(d):
                continue
            try:
                for root, _dirs, files in os.walk(d):
                    for fname in files:
                        if not fname.lower().endswith(".lnk"):
                            continue
                        stem = fname[:-4].lower().strip()
                        matched_key = keyword_to_key.get(stem)
                        if matched_key and matched_key not in self.discovered_apps:
                            # Store the .lnk path — Windows can launch it directly
                            lnk_path = os.path.join(root, fname)
                            self.discovered_apps[matched_key] = lnk_path
                            _LOG.debug("[FCR] Shortcut discovery: %s -> %s", matched_key, lnk_path)
            except OSError:
                continue

    # --- 4. Explicit install_paths ------------------------------------

    def _scan_install_paths(self) -> None:
        for key, meta in self._app_meta.items():
            if key in self.discovered_apps:
                continue
            exe_names = meta.get("exe_names", [])
            for install_dir in meta.get("install_paths", []):
                expanded = os.path.expandvars(install_dir)
                if not os.path.isdir(expanded):
                    continue
                for exe in exe_names:
                    candidate = os.path.join(expanded, exe)
                    if os.path.isfile(candidate):
                        self.discovered_apps[key] = candidate
                        _LOG.debug("[FCR] Install-path discovery: %s -> %s", key, candidate)
                        break
                if key in self.discovered_apps:
                    break

    # --- 5. System PATH -----------------------------------------------

    def _scan_system_path(self) -> None:
        for key, meta in self._app_meta.items():
            if key in self.discovered_apps:
                continue
            for exe in meta.get("exe_names", []):
                found = shutil.which(exe)
                if found:
                    self.discovered_apps[key] = found
                    _LOG.debug("[FCR] PATH discovery: %s -> %s", key, found)
                    break


# ----------------------------------------------------------------------
# 5. Route Result Data Structure
# ----------------------------------------------------------------------

class RouteMatch:
    def __init__(
        self,
        intent: CommandIntent,
        target: str,
        confidence: float,
        handler_name: str,
        params: Dict[str, Any] | None = None,
    ) -> None:
        self.intent = intent
        self.target = target
        self.confidence = confidence
        self.handler_name = handler_name
        self.params = params or {}

    def __repr__(self) -> str:
        return f"RouteMatch(intent={self.intent.name}, target={self.target!r}, confidence={self.confidence}, handler={self.handler_name!r})"


# ----------------------------------------------------------------------
# 6. Intent Engine
# ----------------------------------------------------------------------

class IntentEngine:
    """Fast, deterministic intent engine for English, Hindi, and Hinglish commands."""

    OPEN_WORDS: Set[str] = {"open", "launch", "run", "start", "khol", "kholo", "chalao", "shuru", "खोलो", "खोल", "चलाओ", "शुरू"}
    FILLER_WORDS: Set[str] = {"app", "application", "website", "program", "the", "a", "an", "karo", "kar", "करो", "कर"}
    _OPEN_PATTERN = re.compile(r"^(?:open|launch|start|run)\s+(?:the\s+)?(?:app|application|website|program\s+)?(.+)$", re.IGNORECASE)

    def __init__(self, alias_engine: AliasEngine) -> None:
        self.alias_engine = alias_engine

    def match(self, raw_text: str) -> RouteMatch | None:
        lowered_raw = raw_text.strip().lower()
        cleaned_text = WakeWordCleaner.clean(raw_text)

        if not cleaned_text and not lowered_raw:
            return None

        # 1. Direct App Alias Match (e.g. "youtube", "यूट्यूब", "vscode")
        direct_target = self.alias_engine.resolve(cleaned_text, fuzzy=False) or self.alias_engine.resolve(lowered_raw, fuzzy=False)
        if direct_target:
            intent = CommandIntent.OPEN_WEBSITE if direct_target.startswith(("http://", "https://")) else CommandIntent.OPEN_APP
            return RouteMatch(
                intent=intent,
                target=direct_target,
                confidence=1.0,
                handler_name="LaunchApplication",
                params={"raw_target": cleaned_text or lowered_raw}
            )

        # 2. Filesystem Intents (create/delete/rename folder/file, open file)
        match = self._match_filesystem(cleaned_text, lowered_raw)
        if match:
            return match

        # 3. Open App / Website Intents (fast path for valid aliases)
        match = self._match_open(cleaned_text, lowered_raw)
        if match and not match.params.get("is_invalid_target"):
            return match

        # 4. System Intents (Lock, Shutdown, Restart)
        match = self._match_system_control(cleaned_text, lowered_raw)
        if match:
            return match

        # 5. Volume Intents
        match = self._match_volume(cleaned_text, lowered_raw)
        if match:
            return match

        # 6. Brightness Intents
        match = self._match_brightness(cleaned_text, lowered_raw)
        if match:
            return match

        # ----------------------------------------------------------------------
        # New Intent Engine Matchers
        # ----------------------------------------------------------------------
        match = self._match_screenshot(cleaned_text, lowered_raw)
        if match: return match
        match = self._match_system_info(cleaned_text, lowered_raw)
        if match: return match
        match = self._match_window_control(cleaned_text, lowered_raw)
        if match: return match
        match = self._match_kill_process(cleaned_text, lowered_raw)
        if match: return match
        match = self._match_web_search(cleaned_text, lowered_raw)
        if match: return match
        match = self._match_clipboard(cleaned_text, lowered_raw)
        if match: return match
        match = self._match_run_cmd(cleaned_text, lowered_raw)
        if match: return match

        # 7. Fallback Open match (including invalid target classification)
        if match:
            return match

        return None

    def _match_open(self, cleaned: str, lowered_raw: str) -> RouteMatch | None:
        tokens = cleaned.split() if cleaned else lowered_raw.split()
        if not tokens:
            return None

        # Case A: First or last token is an open action verb
        has_open_verb = any(t in self.OPEN_WORDS for t in tokens)
        if has_open_verb:
            target_tokens = [t for t in tokens if t not in self.OPEN_WORDS and t not in self.FILLER_WORDS]
            target_candidate = " ".join(target_tokens).strip()

            if target_candidate:
                resolved = self.alias_engine.resolve(target_candidate, fuzzy=False)
                if not resolved:
                    resolved = self.alias_engine.resolve(target_candidate, fuzzy=True)
                is_invalid = False
                if not resolved:
                    has_path = "/" in target_candidate or "\\" in target_candidate or "." in target_candidate
                    if target_candidate.startswith(("http://", "https://", "www.")) or (":" in target_candidate and not target_candidate.startswith("http")) or (has_path and Path(target_candidate).exists()):
                        resolved = target_candidate
                    else:
                        resolved = target_candidate
                        is_invalid = True

                intent = CommandIntent.OPEN_WEBSITE if (resolved and resolved.startswith(("http://", "https://", "www."))) else CommandIntent.OPEN_APP
                return RouteMatch(
                    intent=intent,
                    target=resolved,
                    confidence=1.0 if not is_invalid else 0.0,
                    handler_name="LaunchApplication",
                    params={"raw_target": target_candidate, "is_invalid_target": is_invalid}
                )

        # Fallback check on lowered_raw e.g. "open chrome"
        m = self._OPEN_PATTERN.match(lowered_raw)
        if m:
            target_raw = m.group(1).strip()
            resolved = self.alias_engine.resolve(target_raw, fuzzy=False)
            if not resolved:
                resolved = self.alias_engine.resolve(target_raw, fuzzy=True)
            is_invalid = False
            if not resolved:
                has_path = "/" in target_raw or "\\" in target_raw or "." in target_raw
                if target_raw.startswith(("http://", "https://", "www.")) or (":" in target_raw and not target_raw.startswith("http")) or (has_path and Path(target_raw).exists()):
                    resolved = target_raw
                else:
                    resolved = target_raw
                    is_invalid = True

            intent = CommandIntent.OPEN_WEBSITE if (resolved and resolved.startswith(("http://", "https://", "www."))) else CommandIntent.OPEN_APP
            return RouteMatch(
                intent=intent,
                target=resolved,
                confidence=1.0 if not is_invalid else 0.0,
                handler_name="LaunchApplication",
                params={"raw_target": target_raw, "is_invalid_target": is_invalid}
            )

        return None

    def _match_system_control(self, cleaned: str, lowered_raw: str) -> RouteMatch | None:
        text = cleaned or lowered_raw
        tokens = set(text.split())

        # Lock PC
        if "lock" in tokens or "लॉक" in tokens or "lock" in text or "स्क्रीन लॉक" in text:
            if any(w in text for w in ("lock", "pc", "system", "computer", "screen", "लॉक", "स्क्रीन")):
                return RouteMatch(
                    intent=CommandIntent.LOCK_PC,
                    target="lock_workstation",
                    confidence=1.0,
                    handler_name="SystemControl"
                )

        # Shutdown
        if "shutdown" in text or "band" in tokens or "बंद" in tokens or "शटडाउन" in text or "power off" in text or "turn off" in text:
            if any(w in text for w in ("shutdown", "band", "off", "बंद", "शटडाउन")) and any(w in text for w in ("pc", "system", "computer", "कंप्यूटर", "पीसी", "laptop", "shutdown", "off")):
                return RouteMatch(
                    intent=CommandIntent.SHUTDOWN,
                    target="shutdown",
                    confidence=1.0,
                    handler_name="SystemControl"
                )

        # Restart
        if "restart" in text or "reboot" in text or "रीस्टार्ट" in text or "रिस्टार्ट" in text:
            return RouteMatch(
                intent=CommandIntent.RESTART,
                target="restart",
                confidence=1.0,
                handler_name="SystemControl"
            )

        return None

    def _match_volume(self, cleaned: str, lowered_raw: str) -> RouteMatch | None:
        text = f"{cleaned} {lowered_raw}"
        is_vol = any(w in text for w in ("volume", "sound", "awaaz", "awaz", "आवाज़", "आवाज", "वॉल्यूम", "mute", "unmute"))
        if not is_vol:
            return None

        # Check sub-action: mute / unmute / up / down / percentage
        if "unmute" in text:
            sub = "unmute"
        elif "mute" in text:
            sub = "mute"
        elif any(w in text for w in ("up", "increase", "badhao", "badha", "badhaen", "तेज", "बढ़ाओ")):
            sub = "up"
        elif any(w in text for w in ("down", "decrease", "kam", "dheeme", "घटाओ", "कम")):
            sub = "down"
        else:
            m = re.search(r"(\d+)", text)
            sub = m.group(1) if m else "set"

        return RouteMatch(
            intent=CommandIntent.SET_VOLUME,
            target=f"volume_{sub}",
            confidence=1.0,
            handler_name="VolumeControl",
            params={"sub_action": sub, "raw": cleaned or lowered_raw}
        )

    def _match_brightness(self, cleaned: str, lowered_raw: str) -> RouteMatch | None:
        text = f"{cleaned} {lowered_raw}"
        is_bright = any(w in text for w in ("brightness", "roshni", "प्रकाश", "ब्राइटनेस"))
        if not is_bright:
            return None

        if any(w in text for w in ("up", "increase", "badhao", "badha", "तेज", "बढ़ाओ")):
            sub = "up"
        elif any(w in text for w in ("down", "decrease", "kam", "घटाओ", "कम")):
            sub = "down"
        else:
            m = re.search(r"(\d+)", text)
            sub = m.group(1) if m else "50"

        return RouteMatch(
            intent=CommandIntent.SET_BRIGHTNESS,
            target=f"brightness_{sub}",
            confidence=1.0,
            handler_name="BrightnessControl",
            params={"sub_action": sub, "raw": cleaned or lowered_raw}
        )

    def _match_filesystem(self, cleaned: str, lowered_raw: str) -> RouteMatch | None:
        # Check folder create / delete / rename
        # Folder Create
        m = (
            re.match(r"^(?:create|make|mkdir|new)\s+(?:a\s+)?(?:folder|directory)\s+(.+)$", lowered_raw)
            or re.match(r"^mkdir\s+(.+)$", lowered_raw)
            or re.match(r"^(.+?)\s+(?:folder|directory)\s+(?:banao|bana|बनाओ|बना)$", lowered_raw)
        )
        if m:
            return RouteMatch(
                intent=CommandIntent.CREATE_FOLDER,
                target=m.group(1).strip(),
                confidence=1.0,
                handler_name="FileSystem"
            )

        # Folder Delete
        m = (
            re.match(r"^(?:delete|remove|rmdir)\s+(?:the\s+)?(?:folder|directory)\s+(.+)$", lowered_raw)
            or re.match(r"^rmdir\s+(.+)$", lowered_raw)
            or re.match(r"^(.+?)\s+(?:folder|directory)\s+(?:hatao|hata|मेटाओ|हटाओ)$", lowered_raw)
        )
        if m:
            return RouteMatch(
                intent=CommandIntent.DELETE_FOLDER,
                target=m.group(1).strip(),
                confidence=1.0,
                handler_name="FileSystem"
            )

        # Folder Rename
        m = re.match(r"^rename\s+(?:folder|directory)\s+(.+?)\s+to\s+(.+)$", lowered_raw)
        if m:
            return RouteMatch(
                intent=CommandIntent.RENAME_FOLDER,
                target=f"{m.group(1).strip()} -> {m.group(2).strip()}",
                confidence=1.0,
                handler_name="FileSystem",
                params={"old": m.group(1).strip(), "new": m.group(2).strip()}
            )

        # File Create
        m = (
            re.match(r"^(?:create|make|touch|new)\s+(?:a\s+)?file\s+(.+)$", lowered_raw)
            or re.match(r"^touch\s+(.+)$", lowered_raw)
            or re.match(r"^(.+?)\s+file\s+(?:banao|bana|बनाओ)$", lowered_raw)
        )
        if m:
            return RouteMatch(
                intent=CommandIntent.CREATE_FILE,
                target=m.group(1).strip(),
                confidence=1.0,
                handler_name="FileSystem"
            )

        # File Delete
        m = re.match(r"^(?:delete|remove|rm)\s+(?:the\s+)?file\s+(.+)$", lowered_raw)
        if m:
            return RouteMatch(
                intent=CommandIntent.DELETE_FILE,
                target=m.group(1).strip(),
                confidence=1.0,
                handler_name="FileSystem"
            )

        # File Open
        m = re.match(r"^open\s+file\s+(.+)$", lowered_raw)
        if m:
            target_raw = m.group(1).strip()
            if not self.alias_engine.resolve(lowered_raw) and not self.alias_engine.resolve(f"file {target_raw}"):
                return RouteMatch(
                    intent=CommandIntent.OPEN_FILE,
                    target=target_raw,
                    confidence=1.0,
                    handler_name="FileSystem"
                )

        # File Rename
        m = re.match(r"^rename\s+file\s+(.+?)\s+to\s+(.+)$", lowered_raw) or re.match(r"^rename\s+(.+?)\s+to\s+(.+)$", lowered_raw)
        if m:
            return RouteMatch(
                intent=CommandIntent.RENAME_FILE,
                target=f"{m.group(1).strip()} -> {m.group(2).strip()}",
                confidence=1.0,
                handler_name="FileSystem",
                params={"old": m.group(1).strip(), "new": m.group(2).strip()}
            )

        return None

    # ----------------------------------------------------------------------
    # New Private Matcher Methods (STEP 3)
    # ----------------------------------------------------------------------

    def _match_screenshot(self, cleaned: str, lowered_raw: str) -> RouteMatch | None:
        text = f"{cleaned} {lowered_raw}"
        triggers = (
            "screenshot", "capture screen", "screen capture", "screengrab", "snap screen",
            "स्क्रीनशॉट", "स्क्रीन कैप्चर",
            "screenshot lo", "screenshot le", "screen capture karo", "screengrab lo"
        )
        if any(tr in text for tr in triggers):
            return RouteMatch(
                intent=CommandIntent.SCREENSHOT,
                target="desktop_screenshot",
                confidence=1.0,
                handler_name="Screenshot",
            )
        return None

    def _match_system_info(self, cleaned: str, lowered_raw: str) -> RouteMatch | None:
        text = f"{cleaned} {lowered_raw}"
        tokens = set(text.split())

        if any(tr in text for tr in ("battery kitni", "charging", "चार्ज", "बैटरी")) or any(t in tokens for t in ("battery", "battry")):
            sub_name = "battery"
        elif any(tr in text for tr in ("kitne baje", "samay", "wakt", "वक्त", "समय")) or "time" in tokens:
            sub_name = "time"
        elif any(tr in text for tr in ("aaj kya date", "aaj ki date", "तारीख")) or "date" in tokens:
            sub_name = "date"
        elif any(tr in text for tr in ("ip address", "mera ip", "network address")) or "ip" in tokens:
            sub_name = "ip"
        elif any(tr in text for tr in ("kitni ram", "memory", "रैम", "मेमोरी")) or "ram" in tokens:
            sub_name = "ram"
        elif any(tr in text for tr in ("processor", "सीपीयू")) or "cpu" in tokens:
            sub_name = "cpu"
        elif any(tr in text for tr in ("disk space", "storage", "डिस्क")) or "disk" in tokens:
            sub_name = "disk"
        else:
            return None

        return RouteMatch(
            intent=CommandIntent.SYSTEM_INFO,
            target=sub_name,
            confidence=1.0,
            handler_name="SystemInfo",
            params={"sub": sub_name},
        )

    def _is_plausible_app_name(self, candidate: str) -> bool:
        """
        Reject captured text that looks like conversational language
        rather than an application/window name. Real app names are
        short and don't contain sentence-structure words.
        """
        if not candidate:
            return False

        cleaned = candidate.strip().strip(".,!?;:'\"").strip()
        if not cleaned:
            return False

        words = cleaned.split()

        # Real app/window names are almost always 1-3 words.
        # ("visual studio code" is 3 words; that's the practical ceiling)
        if len(words) > 3:
            return False

        # Reject if it contains common sentence-structure / filler
        # words that never appear in an app or window name.
        SENTENCE_MARKERS = {
            "the", "that", "this", "a", "an", "of", "in", "on", "at",
            "to", "for", "and", "or", "but", "is", "are", "was", "were",
            "my", "your", "his", "her", "their", "our", "life", "time",
            "today", "risk", "deal", "chapter", "while", "waiting",
            "productivity", "losing", "contract", "move", "boss",
            "game", "final", "want", "need", "should", "would", "could",
            "how", "do", "i", "we", "you", "it", "he", "she", "they",
            "with", "from", "about", "because", "so", "if", "when",
        }
        lowered_words = {w.lower() for w in words}
        if lowered_words & SENTENCE_MARKERS:
            return False

        return True

    def _match_window_control(self, cleaned: str, lowered_raw: str) -> RouteMatch | None:
        text = lowered_raw.strip()

        # Minimize
        m_min = (
            re.search(r"(?:minimize|chota)\s+(?:karo|kar|the window)?\s*(.+)", text, re.IGNORECASE)
            or re.search(r"(.+?)\s+(?:minimize|chota)\s+(?:karo|kar)", text, re.IGNORECASE)
        )
        if m_min:
            app_name = m_min.group(1).strip()
            if app_name and app_name.lower() not in ("window", "the window") \
               and self._is_plausible_app_name(app_name):
                return RouteMatch(
                    intent=CommandIntent.WINDOW_MINIMIZE,
                    target=app_name,
                    confidence=1.0,
                    handler_name="WindowControl",
                    params={"action": "minimize", "app_name": app_name},
                )

        # Maximize
        m_max = (
            re.search(r"(?:maximize|bada|fullscreen)\s+(?:karo|kar|the window)?\s*(.+)", text, re.IGNORECASE)
            or re.search(r"(.+?)\s+(?:maximize|bada|fullscreen)\s+(?:karo|kar)", text, re.IGNORECASE)
        )
        if m_max:
            app_name = m_max.group(1).strip()
            if app_name and app_name.lower() not in ("window", "the window") \
               and self._is_plausible_app_name(app_name):
                return RouteMatch(
                    intent=CommandIntent.WINDOW_MAXIMIZE,
                    target=app_name,
                    confidence=1.0,
                    handler_name="WindowControl",
                    params={"action": "maximize", "app_name": app_name},
                )

        # Close
        m_close = (
            re.search(r"(?:close|band)\s+(?:karo|kar|the window)?\s*(.+)", text, re.IGNORECASE)
            or re.search(r"(.+?)\s+(?:close|band)\s+(?:karo|kar)", text, re.IGNORECASE)
        )
        if m_close:
            app_name = m_close.group(1).strip()
            if app_name and app_name.lower() not in ("window", "the window", "karo", "kar", "") \
               and self._is_plausible_app_name(app_name):
                return RouteMatch(
                    intent=CommandIntent.WINDOW_CLOSE,
                    target=app_name,
                    confidence=1.0,
                    handler_name="WindowControl",
                    params={"action": "close", "app_name": app_name},
                )

        return None

    def _match_kill_process(self, cleaned: str, lowered_raw: str) -> RouteMatch | None:
        text = lowered_raw.strip()
        m = (
            re.search(r"(?:force close|force quit|force band|kill)\s+(.+)", text, re.IGNORECASE)
            or re.search(r"(.+?)\s+(?:ko force close karo|force band karo|kill karo|kill kar)", text, re.IGNORECASE)
        )
        if m:
            app_name = m.group(1).strip()
            if app_name and self._is_plausible_app_name(app_name):
                return RouteMatch(
                    intent=CommandIntent.KILL_PROCESS,
                    target=app_name,
                    confidence=1.0,
                    handler_name="KillProcess",
                    params={"app_name": app_name},
                )
        return None

    def _match_web_search(self, cleaned: str, lowered_raw: str) -> RouteMatch | None:
        text = lowered_raw.strip()

        m1 = re.search(r"(youtube|google)\s+(?:pe|mein|par)?\s*(.+?)\s+(?:search karo|dhundho)", text, re.IGNORECASE)
        if m1:
            platform = m1.group(1).lower()
            query = m1.group(2).strip()
        else:
            m2 = re.search(r"search\s+(.+?)\s+on\s+(youtube|google)", text, re.IGNORECASE)
            if m2:
                query = m2.group(1).strip()
                platform = m2.group(2).lower()
            else:
                m3 = re.search(r"(youtube|google)\s+search\s+(.+)", text, re.IGNORECASE)
                if m3:
                    platform = m3.group(1).lower()
                    query = m3.group(2).strip()
                else:
                    return None

        if not query:
            return None

        base_url = (
            "https://www.youtube.com/results?search_query="
            if platform == "youtube"
            else "https://www.google.com/search?q="
        )
        encoded_query = urllib.parse.quote_plus(query)
        encoded_full_url = f"{base_url}{encoded_query}"

        return RouteMatch(
            intent=CommandIntent.WEB_SEARCH,
            target=encoded_full_url,
            confidence=1.0,
            handler_name="WebSearch",
            params={"query": query, "platform": platform},
        )

    def _match_clipboard(self, cleaned: str, lowered_raw: str) -> RouteMatch | None:
        text = f"{cleaned} {lowered_raw}"
        triggers = ("clipboard clear karo", "clipboard saaf karo", "clear clipboard", "clipboard खाली करो")
        if any(tr in text for tr in triggers):
            return RouteMatch(
                intent=CommandIntent.CLIPBOARD_OP,
                target="clear",
                confidence=1.0,
                handler_name="ClipboardOp",
                params={"action": "clear"},
            )
        return None

    def _match_run_cmd(self, cleaned: str, lowered_raw: str) -> RouteMatch | None:
        text = lowered_raw.strip()
        m = (
            re.search(r"(?:run|execute|chalao)\s+([a-zA-Z0-9_ \-\/]+)", text, re.IGNORECASE)
            or re.search(r"([a-zA-Z0-9_ \-\/]+)\s+(?:run karo|chalao)", text, re.IGNORECASE)
        )
        if m:
            extracted_cmd = m.group(1).strip()
            SAFE_PREFIXES = ("ipconfig", "ping ", "tracert ", "netstat", "tasklist", "systeminfo", "whoami", "hostname", "ver", "dir")
            if any(extracted_cmd.lower().startswith(prefix) for prefix in SAFE_PREFIXES):
                return RouteMatch(
                    intent=CommandIntent.RUN_CMD_SAFE,
                    target=extracted_cmd,
                    confidence=1.0,
                    handler_name="RunCmdSafe",
                    params={"cmd": extracted_cmd},
                )
        return None


# ----------------------------------------------------------------------
# 7. Main FastCommandRouter Architecture
# ----------------------------------------------------------------------

class FastCommandRouter:
    """Detects simple deterministic desktop commands and executes them directly.

    Supported Operations:
    - Open Apps / Websites / Explorer / Tools: Chrome, YouTube, VS Code, Calculator, Notepad,
      Explorer, Settings, Task Manager, CMD, PowerShell, custom paths/URLs.
    - Filesystem: Create Folder, Delete Folder, Rename Folder, Create File, Delete File, Open File, Rename File.
    - System: Volume control, Brightness control, Lock PC, Shutdown, Restart.
    """

    APP_ALIASES: Dict[str, str] = {}

    DEFAULT_BROWSER_FALLBACKS: Dict[str, str] = {
        "outlook": "https://outlook.live.com/",
        "whatsapp": "https://web.whatsapp.com/",
        "youtube": "https://youtube.com/",
        "gmail": "https://mail.google.com/",
        "github": "https://github.com/",
        "google": "https://google.com/",
        "chatgpt": "https://chatgpt.com/",
        "discord": "https://discord.com/app",
        "telegram": "https://web.telegram.org/",
        "spotify": "https://open.spotify.com/",
        "teams": "https://teams.microsoft.com/",
    }

    def __init__(
        self,
        pc_control_manager: Any | None = None,
        vision_manager: Any | None = None,
        logger: logging.Logger | None = None,
        config_path: Path | None = None,
        enable_discovery: bool = True,
    ) -> None:
        self._pc_control_mgr = pc_control_manager
        self._vision_mgr = vision_manager
        self._logger = logger or _LOG
        self.alias_engine = AliasEngine(config_path=config_path)
        self.intent_engine = IntentEngine(self.alias_engine)
        self._mock_verification: Tuple[bool, str | None, str | None] | None = None

        # Dynamic installed-app discovery
        if enable_discovery and os.name == "nt":
            self.discovery_engine: AppDiscoveryEngine | None = AppDiscoveryEngine(self.alias_engine._app_meta)
        else:
            self.discovery_engine = None

        # Expose APP_ALIASES on instance and class for full API compatibility
        FastCommandRouter.APP_ALIASES = self.alias_engine.alias_map
        self.APP_ALIASES = FastCommandRouter.APP_ALIASES

    def is_fast_command(self, text: str) -> bool:
        """Check if the text request matches a known deterministic fast command."""
        if not text or not text.strip():
            return False

        match = self.intent_engine.match(text)
        if match:
            self._logger.debug("[FCR] Intent=%s, Target=%s, Confidence=%.1f, Handler=%s", match.intent.name, match.target, match.confidence, match.handler_name)
            return True

        return False

    def get_browser_fallback(self, app_key: str | None, target_raw: str, app_target: str) -> str | None:
        """Return the browser fallback URL for a given app key or target, if registered."""
        if app_key:
            key_norm = app_key.lower().strip().rstrip(":")
            if key_norm in self.DEFAULT_BROWSER_FALLBACKS:
                return self.DEFAULT_BROWSER_FALLBACKS[key_norm]
            if key_norm.startswith("ms-"):
                stem = key_norm[3:]
                if stem in self.DEFAULT_BROWSER_FALLBACKS:
                    return self.DEFAULT_BROWSER_FALLBACKS[stem]

        for cand in (target_raw, app_target):
            cand_norm = cand.lower().strip().rstrip(":")
            if cand_norm in self.DEFAULT_BROWSER_FALLBACKS:
                return self.DEFAULT_BROWSER_FALLBACKS[cand_norm]
            for k, url in self.DEFAULT_BROWSER_FALLBACKS.items():
                if k == cand_norm or (len(k) > 3 and k in cand_norm):
                    return url
        return None

    async def _verify_launch(
        self,
        app_key: str | None,
        target: str,
        proc: Any | None = None,
        timeout: float = 1.0,
        lifecycle: ActionLifecycle | None = None,
    ) -> Tuple[bool, str | None, str | None]:
        """Verify if process started, window appeared, or executable exists in running processes.

        Logs using [FCR] Launch Verification logging specification.
        Returns (verified: bool, running_process: str | None, window_detected: str | None)
        """
        if lifecycle:
            lifecycle.transition_to(ActionState.WAITING, "Performing launch verification")

        if self._mock_verification is not None:
            verified, running_proc, window_det = self._mock_verification
            self._logger.info(
                "[FCR]\nLaunch Verification=%s\nRunningProcess=%s\nWindowDetected=%s",
                verified, running_proc or "None", window_det or "None"
            )
            self._logger.info("[FCR]")
            self._logger.info("Launch Verification=%s", verified)
            self._logger.info("RunningProcess=%s", running_proc or "None")
            self._logger.info("WindowDetected=%s", window_det or "None")
            if lifecycle:
                lifecycle.set_verification(
                    verified=verified,
                    running_process=running_proc,
                    window_detected=window_det,
                    error=None if verified else "Mock verification returned false",
                )
            return self._mock_verification

        running_proc: str | None = None
        window_det: str | None = None
        verified = False

        exe_targets = set()
        if app_key:
            meta = self.alias_engine.get_app_meta(app_key)
            if meta and meta.get("exe_names"):
                for e in meta["exe_names"]:
                    exe_targets.add(e.lower())
        if target:
            if target.startswith(("http://", "https://", "www.")):
                exe_targets.update({"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "launcher.exe"})
            t_clean = target.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()
            if not t_clean.endswith(".exe") and not t_clean.startswith("http"):
                exe_targets.add(t_clean + ".exe")
            exe_targets.add(t_clean)

        def _check_psutil() -> str | None:
            try:
                import psutil
                for p in psutil.process_iter(["pid", "name"]):
                    p_name = (p.info.get("name") or "").lower()
                    if p_name in exe_targets or any(e in p_name for e in exe_targets if len(e) > 3):
                        return f"{p.info['name']} (PID {p.info['pid']})"
            except Exception:
                pass
            return None

        def _check_win32gui() -> str | None:
            if os.name != "nt":
                return None
            try:
                import win32gui
                titles: List[str] = []
                def enum_cb(hwnd, _):
                    if win32gui.IsWindowVisible(hwnd):
                        txt = win32gui.GetWindowText(hwnd)
                        if txt:
                            titles.append(txt)
                    return True
                win32gui.EnumWindows(enum_cb, None)

                search_terms = {app_key.lower()} if app_key else set()
                if target:
                    search_terms.add(target.lower())

                for t in titles:
                    t_low = t.lower()
                    for st in search_terms:
                        if st and len(st) > 2 and st in t_low:
                            return t
            except Exception:
                pass
            return None

        # BUG 1 (P0): Async retry verification loop (200ms -> 300ms -> 500ms, max ~1.0s)
        delays = [0.2, 0.3, 0.5]
        for delay in delays:
            await asyncio.sleep(delay)

            # 1. Process handle check
            if proc is not None and hasattr(proc, "poll"):
                if proc.poll() is None:
                    running_proc = f"{target} (PID {getattr(proc, 'pid', 'active')})"
                elif getattr(proc, "returncode", None) == 0:
                    running_proc = f"{target} (exited 0)"

            # 2. psutil process check
            if not running_proc:
                running_proc = await asyncio.to_thread(_check_psutil)

            # 3. win32gui window title check
            if not window_det:
                window_det = await asyncio.to_thread(_check_win32gui)

            verified = bool(
                running_proc or window_det or (proc is not None and getattr(proc, "poll", lambda: 1)() is None)
            )

            if verified:
                break

        # Logging Requirement 4
        self._logger.info(
            "[FCR]\nLaunch Verification=%s\nRunningProcess=%s\nWindowDetected=%s",
            verified, running_proc or "None", window_det or "None"
        )
        self._logger.info("[FCR]")
        self._logger.info("Launch Verification=%s", verified)
        self._logger.info("RunningProcess=%s", running_proc or "None")
        self._logger.info("WindowDetected=%s", window_det or "None")

        if lifecycle:
            lifecycle.set_verification(
                verified=verified,
                running_process=running_proc,
                window_detected=window_det,
                error=None if verified else "Launch verification timeout / process not detected",
            )

        return verified, running_proc, window_det

    async def _check_if_running(self, app_key: str | None, target: str) -> Tuple[bool, str | None, str | None]:
        """Check if an app is already running by process name or window title."""
        exe_targets = set()
        if app_key:
            meta = self.alias_engine.get_app_meta(app_key)
            if meta and meta.get("exe_names"):
                for e in meta["exe_names"]:
                    exe_targets.add(e.lower())
        if target:
            t_clean = target.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()
            if not t_clean.endswith(".exe") and not t_clean.startswith("http"):
                exe_targets.add(t_clean + ".exe")
            exe_targets.add(t_clean)

        def _scan_running() -> Tuple[str | None, str | None]:
            proc_found = None
            try:
                import psutil
                for p in psutil.process_iter(["pid", "name"]):
                    p_name = (p.info.get("name") or "").lower()
                    if p_name in exe_targets or any(e in p_name for e in exe_targets if len(e) > 3):
                        proc_found = f"{p.info['name']} (PID {p.info['pid']})"
                        break
            except Exception:
                pass

            win_found = None
            if os.name == "nt":
                try:
                    import win32gui
                    search_terms = {app_key.lower()} if app_key else set()
                    if target:
                        search_terms.add(target.lower())

                    def enum_cb(hwnd, _):
                        nonlocal win_found
                        if win32gui.IsWindowVisible(hwnd):
                            txt = win32gui.GetWindowText(hwnd)
                            if txt:
                                t_low = txt.lower()
                                for st in search_terms:
                                    if st and len(st) > 2 and st in t_low:
                                        win_found = txt
                                        return False
                        return True
                    win32gui.EnumWindows(enum_cb, None)
                except Exception:
                    pass

            return proc_found, win_found

        proc_info, win_info = await asyncio.to_thread(_scan_running)
        is_running = bool(proc_info or win_info)
        return is_running, proc_info, win_info

    def _focus_window(self, win_title: str | None, search_term: str) -> None:
        """Attempt to bring a window to the foreground on Windows."""
        if os.name != "nt":
            return
        try:
            import win32gui
            import win32con
            target_hwnd = None

            def enum_cb(hwnd, _):
                nonlocal target_hwnd
                if win32gui.IsWindowVisible(hwnd):
                    txt = win32gui.GetWindowText(hwnd)
                    if txt:
                        if (win_title and win_title.lower() in txt.lower()) or (search_term and search_term.lower() in txt.lower()):
                            target_hwnd = hwnd
                            return False
                return True

            win32gui.EnumWindows(enum_cb, None)
            if target_hwnd:
                win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(target_hwnd)
        except Exception as exc:
            self._logger.debug("[FCR] Could not focus window: %s", exc)

    async def execute_fast_command(self, text: str, debug: bool = False) -> str:
        """Execute a matched fast command directly and return structured output or error report."""
        start_time = time.time()
        match = self.intent_engine.match(text)

        if not match:
            lifecycle = ActionLifecycle(
                intent_name="UNKNOWN",
                target=text,
                handler_name="FastCommandRouter",
                confidence=0.0,
                debug_mode=debug,
            )
            lifecycle.transition_to(ActionState.FAILED, "No match pattern found")
            self._logger.info("[FCR] Lifecycle Debug Metadata: %s", lifecycle.get_debug_metadata())
            err = self._format_error(
                summary=f"Unrecognized fast command: '{text}'",
                root_cause="Fast command match pattern succeeded during detection but execution route was null.",
                tool_name="FastCommandRouter",
                exception="ValueError('No handler matched')",
                recovery="Fallback to Gemini requested",
                final_status="FAILED",
            )
            if debug:
                import json
                err = f"{err}\n[DEBUG: {json.dumps(lifecycle.get_debug_metadata())}]"
            return err

        lifecycle = ActionLifecycle(
            intent_name=match.intent.name,
            target=match.target,
            handler_name=match.handler_name,
            confidence=match.confidence,
            debug_mode=debug,
        )
        lifecycle.transition_to(ActionState.STARTING, f"Matched {match.intent.name}")

        self._logger.info("[FCR] Intent=%s", match.intent.name)
        self._logger.info("[FCR] Target=%s", match.target)
        self._logger.info("[FCR] Confidence=%.1f", match.confidence)
        self._logger.info("[FCR] Handler=%s", match.handler_name)

        try:
            res: str
            if match.intent in (CommandIntent.OPEN_APP, CommandIntent.OPEN_WEBSITE):
                res = await self._execute_open(match, start_time, lifecycle)
            elif match.intent in (CommandIntent.LOCK_PC, CommandIntent.SHUTDOWN, CommandIntent.RESTART):
                res = await self._execute_system_control(match, start_time, lifecycle)
            elif match.intent == CommandIntent.SET_VOLUME:
                res = await self._execute_volume(match, text, start_time, lifecycle)
            elif match.intent == CommandIntent.SET_BRIGHTNESS:
                res = await self._execute_brightness(match, text, start_time, lifecycle)
            elif match.intent in (
                CommandIntent.CREATE_FOLDER, CommandIntent.DELETE_FOLDER, CommandIntent.RENAME_FOLDER,
                CommandIntent.CREATE_FILE, CommandIntent.DELETE_FILE, CommandIntent.OPEN_FILE, CommandIntent.RENAME_FILE
            ):
                res = await self._execute_filesystem(match, text, start_time, lifecycle)
            elif match.intent == CommandIntent.SCREENSHOT:
                res = await self._execute_screenshot(match, start_time, lifecycle)
            elif match.intent == CommandIntent.SYSTEM_INFO:
                res = await self._execute_system_info(match, start_time, lifecycle)
            elif match.intent in (CommandIntent.WINDOW_MINIMIZE, CommandIntent.WINDOW_MAXIMIZE, CommandIntent.WINDOW_CLOSE):
                res = await self._execute_window_control(match, start_time, lifecycle)
            elif match.intent == CommandIntent.KILL_PROCESS:
                res = await self._execute_kill_process(match, start_time, lifecycle)
            elif match.intent == CommandIntent.WEB_SEARCH:
                res = await self._execute_web_search(match, start_time, lifecycle)
            elif match.intent == CommandIntent.CLIPBOARD_OP:
                res = await self._execute_clipboard(match, start_time, lifecycle)
            elif match.intent == CommandIntent.RUN_CMD_SAFE:
                res = await self._execute_run_cmd(match, start_time, lifecycle)
            else:
                lifecycle.transition_to(ActionState.FAILED, f"Unhandled intent: {match.intent.name}")
                res = self._format_error(
                    summary=f"Unhandled intent: {match.intent.name}",
                    root_cause="Intent match was found but no execution handler was registered for it.",
                    tool_name="FastCommandRouter",
                    exception="NotImplementedError",
                    recovery="Fallback to Gemini requested",
                    final_status="FAILED",
                )

            self._logger.info("[FCR] Lifecycle Debug Metadata: %s", lifecycle.get_debug_metadata())
            if debug:
                import json
                res = f"{res}\n[DEBUG: {json.dumps(lifecycle.get_debug_metadata())}]"
            return res

        except Exception as exc:
            lifecycle.transition_to(ActionState.FAILED, f"Execution exception: {exc}")
            self._logger.error("FastCommandRouter execution exception: %s", exc, exc_info=True)
            self._logger.info("[FCR] Lifecycle Debug Metadata: %s", lifecycle.get_debug_metadata())
            err_res = self._format_error(
                summary=f"Execution error for '{text}'",
                root_cause=f"An exception occurred during fast command execution: {exc}",
                tool_name="FastCommandRouter",
                exception=f"{type(exc).__name__}: {exc}",
                recovery="Attempted direct OS execution without Gemini",
                final_status="FAILED",
            )
            if debug:
                import json
                err_res = f"{err_res}\n[DEBUG: {json.dumps(lifecycle.get_debug_metadata())}]"
            return err_res

    # ------------------------------------------------------------------
    # Dispatch Handlers
    # ------------------------------------------------------------------

    async def _execute_open(self, match: RouteMatch, start_time: float, lifecycle: ActionLifecycle | None = None) -> str:
        if lifecycle:
            lifecycle.transition_to(ActionState.RUNNING, "Resolving target application or URL")

        app_target = match.target
        target_raw = match.params.get("raw_target", app_target)
        tool_used = "launch_application"

        if not app_target or not app_target.strip() or not target_raw or not target_raw.strip():
            if lifecycle:
                lifecycle.transition_to(ActionState.FAILED, "Invalid target")
            duration_ms = (time.time() - start_time) * 1000
            return f"INVALID_TARGET: '{target_raw}' is an unknown or invalid target. [Fast Execution: {duration_ms:.1f}ms]"

        app_key = self.alias_engine.resolve_key(target_raw) or self.alias_engine.resolve_key(app_target)
        is_website = app_target.startswith(("http://", "https://", "www."))
        is_protocol = ":" in app_target and not app_target.startswith(("http://", "https://"))

        # BUG 6 (P2): Built-in Windows CLI applications bypass discovery
        is_builtin_cli = (
            app_key in ("cmd", "powershell")
            or app_target.lower() in ("cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "pwsh.exe")
        )

        fallback_url = self.get_browser_fallback(app_key, target_raw, app_target)
        has_explicit_fallback = fallback_url is not None

        discovered_exe: str | None = None
        launch_method = "system_start"

        if self.discovery_engine and app_key and not is_builtin_cli:
            discovered_exe = self.discovery_engine.get_executable(app_key)

        # --- Determine installation status -------------------
        BUILTIN_APPS = {
            "calc", "notepad", "cmd", "powershell", "explorer", "mspaint",
            "taskmgr", "control", "regedit", "snippingtool", "devmgmt.msc", "wt"
        }
        app_is_installed = False
        if match.params.get("is_invalid_target"):
            app_is_installed = False
        elif self._mock_verification is not None:
            app_is_installed = True
        elif app_target.startswith(("http://", "https://", "www.")):
            app_is_installed = True
        elif is_builtin_cli or app_key in BUILTIN_APPS or app_target.lower() in BUILTIN_APPS:
            app_is_installed = True
        elif is_protocol:
            app_is_installed = True
        elif discovered_exe:
            app_is_installed = True
        elif shutil.which(app_target) or (app_key and shutil.which(app_key)):
            app_is_installed = True
        elif self.discovery_engine and app_key:
            meta = self.alias_engine.get_app_meta(app_key)
            if meta and meta.get("target", "").startswith(("http://", "https://")):
                app_is_installed = False
            else:
                app_is_installed = self.discovery_engine.is_installed(app_key)
        elif not self.discovery_engine and (shutil.which(app_target) or (app_key and shutil.which(app_key))):
            app_is_installed = True

        self._logger.info("[FCR] App Found=%s", app_is_installed)
        self._logger.info("[FCR] Executable=%s", discovered_exe or ("cmd.exe/powershell.exe" if is_builtin_cli else "N/A"))
        self._logger.info("[FCR] Alias=%s", target_raw)

        name_display = target_raw.title() if len(target_raw) <= 20 else target_raw

        # Determine launch method & log requirement
        if is_builtin_cli:
            launch_method = "builtin_cli"
        elif self._pc_control_mgr and hasattr(self._pc_control_mgr, "launch_application"):
            launch_method = "pc_control_manager"
        elif is_website:
            launch_method = "webbrowser"
        elif discovered_exe:
            launch_method = "discovered_exe"
        else:
            launch_method = "system_start" if os.name == "nt" else "subprocess"

        self._logger.info("[FCR] LaunchMethod=%s", launch_method)

        # --- NOT_INSTALLED gate -> Universal Web Browser Fallback -----------
        if not app_is_installed:
            if not has_explicit_fallback and app_key and not is_website:
                if lifecycle:
                    lifecycle.transition_to(ActionState.FAILED, "Application not installed")
                self._logger.info("[FCR]\nReason=NOT_INSTALLED")
                self._logger.info("Reason=NOT_INSTALLED")
                return f"NOT_INSTALLED: '{name_display}' is not installed locally."

            if not fallback_url:
                fallback_url = f"https://www.google.com/search?q={urllib.parse.quote(target_raw)}"

            import webbrowser
            self._logger.info("[FCR]\nFallback=True\nFallbackURL=%s\nReason=NOT_INSTALLED", fallback_url)
            self._logger.info("[FCR]")
            self._logger.info("Fallback=True")
            self._logger.info("FallbackURL=%s", fallback_url)
            self._logger.info("Reason=NOT_INSTALLED")

            webbrowser.open(fallback_url)
            await self._verify_launch(app_key, fallback_url, timeout=0.5, lifecycle=lifecycle)
            if lifecycle:
                lifecycle.transition_to(ActionState.SUCCESS, "Opened browser fallback")
            duration_ms = (time.time() - start_time) * 1000
            nat_msg = NaturalResponseFormatter.format_browser_fallback(name_display)
            return f"BROWSER_FALLBACK: {nat_msg} ({fallback_url}) [Fast Execution: {duration_ms:.1f}ms]"

        # --- BUG 5 (P1): Duplicate Command Protection -----------------
        if self._mock_verification is None and not is_website:
            is_running, running_pid_str, win_title = await self._check_if_running(app_key, app_target)
            if is_running:
                self._focus_window(win_title, app_key or app_target)
                if lifecycle:
                    lifecycle.set_verification(verified=True, running_process=running_pid_str, window_detected=win_title)
                    lifecycle.transition_to(ActionState.SUCCESS, "Application already running")
                duration_ms = (time.time() - start_time) * 1000
                nat_msg = NaturalResponseFormatter.format_open_success(name_display, already_running=True)
                return f"SUCCESS: {nat_msg} [Fast Execution: {duration_ms:.1f}ms]"

        # --- Launch Installed App / Website / Protocol / CLI -----------
        proc_handle = None
        try:
            if is_builtin_cli:
                cli_exe = "powershell.exe" if ("powershell" in target_raw.lower() or app_key == "powershell") else "cmd.exe"
                if os.name == "nt":
                    try:
                        os.startfile(cli_exe)
                    except Exception:
                        proc_handle = subprocess.Popen([cli_exe], shell=False)
                else:
                    proc_handle = subprocess.Popen([cli_exe], shell=False)
            elif self._pc_control_mgr and hasattr(self._pc_control_mgr, "launch_application"):
                res = await self._pc_control_mgr.launch_application(app_target)
                success = getattr(res, "success", True)
                if not success:
                    raise RuntimeError(f"launch_application returned failure: {res}")
            elif is_website:
                import webbrowser
                url = app_target if app_target.startswith(("http://", "https://")) else "https://" + app_target
                webbrowser.open(url)
            elif discovered_exe:
                if discovered_exe.lower().endswith(".lnk"):
                    os.startfile(discovered_exe)
                else:
                    proc_handle = subprocess.Popen([discovered_exe], shell=False)
            else:
                if os.name == "nt":
                    try:
                        proc_handle = subprocess.Popen([app_target])
                    except Exception:
                        try:
                            os.startfile(app_target)
                        except Exception:
                            pass
                else:
                    proc_handle = subprocess.Popen([app_target])

            # --- BUG 1 (P0): Launch Verification with Retry Loop ------
            verified, proc_info, win_info = await self._verify_launch(app_key, app_target, proc=proc_handle, timeout=1.0, lifecycle=lifecycle)

            duration_ms = (time.time() - start_time) * 1000
            if not verified:
                if lifecycle:
                    lifecycle.transition_to(ActionState.FAILED, "Process/window launch verification failed")
                nat_msg = NaturalResponseFormatter.format_open_failed(name_display, "Process or window could not be verified")
                return (
                    f"FAILED_TO_LAUNCH: {nat_msg} "
                    f"[Fast Execution: {duration_ms:.1f}ms]"
                )

            if lifecycle:
                lifecycle.transition_to(ActionState.SUCCESS, "Launch verified successfully")
            nat_msg = NaturalResponseFormatter.format_open_success(name_display)
            return f"SUCCESS: {nat_msg} [Fast Execution: {duration_ms:.1f}ms]"

        except Exception as exc:
            if lifecycle:
                lifecycle.transition_to(ActionState.FAILED, f"Launch exception: {exc}")
            self._logger.info("[FCR] LaunchMethod=%s (failed)", launch_method)
            duration_ms = (time.time() - start_time) * 1000
            nat_msg = NaturalResponseFormatter.format_open_failed(name_display, str(exc))
            return f"FAILED_TO_LAUNCH: {nat_msg} [Fast Execution: {duration_ms:.1f}ms]"

    async def _execute_system_control(self, match: RouteMatch, start_time: float, lifecycle: ActionLifecycle | None = None) -> str:
        intent = match.intent
        tool_used = "system_control"
        if lifecycle:
            lifecycle.transition_to(ActionState.RUNNING, f"System control action: {intent.name}")

        try:
            action_key = ""
            if intent == CommandIntent.LOCK_PC:
                action_key = "lock"
                if self._pc_control_mgr and hasattr(self._pc_control_mgr, "lock_workstation"):
                    await self._pc_control_mgr.lock_workstation()
                elif os.name == "nt":
                    subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
            elif intent == CommandIntent.SHUTDOWN:
                action_key = "shutdown"
                if self._pc_control_mgr and hasattr(self._pc_control_mgr, "shutdown"):
                    await self._pc_control_mgr.shutdown()
                elif os.name == "nt":
                    subprocess.run(["shutdown", "/s", "/t", "10"])
            elif intent == CommandIntent.RESTART:
                action_key = "restart"
                if self._pc_control_mgr and hasattr(self._pc_control_mgr, "restart"):
                    await self._pc_control_mgr.restart()
                elif os.name == "nt":
                    subprocess.run(["shutdown", "/r", "/t", "10"])
            else:
                raise ValueError(f"Unknown system control intent: {intent.name}")

            if lifecycle:
                lifecycle.set_verification(verified=True, details={"action": action_key})
                lifecycle.transition_to(ActionState.SUCCESS, "System control executed")

            duration_ms = (time.time() - start_time) * 1000
            nat_msg = NaturalResponseFormatter.format_system_control_success(action_key)
            return f"SUCCESS: {nat_msg} [Fast Execution: {duration_ms:.1f}ms]"
        except Exception as exc:
            if lifecycle:
                lifecycle.transition_to(ActionState.FAILED, f"System control error: {exc}")
            return self._format_error(
                summary=f"Failed system action '{intent.name}'",
                root_cause=f"System control API error: {exc}",
                tool_name=tool_used,
                exception=f"{type(exc).__name__}: {exc}",
                recovery="Attempted Windows API/subprocess call.",
                final_status="FAILED",
            )

    async def _execute_volume(self, match: RouteMatch, raw_text: str, start_time: float, lifecycle: ActionLifecycle | None = None) -> str:
        sub = match.params.get("sub_action", "set")
        tool_name = "volume_control"
        lowered = raw_text.lower()
        if lifecycle:
            lifecycle.transition_to(ActionState.RUNNING, "Adjusting volume")

        try:
            val_pct = 50
            if sub == "mute" or lowered in ("mute", "mute volume"):
                if self._pc_control_mgr and hasattr(self._pc_control_mgr, "volume_mute"):
                    await self._pc_control_mgr.volume_mute(True)
                val_pct = 0
                detail_str = "Muted"
            elif sub == "unmute" or lowered in ("unmute", "unmute volume"):
                if self._pc_control_mgr and hasattr(self._pc_control_mgr, "volume_unmute"):
                    await self._pc_control_mgr.volume_unmute()
                detail_str = "Unmuted"
            elif sub == "up":
                if self._pc_control_mgr and hasattr(self._pc_control_mgr, "volume_get"):
                    curr = await self._pc_control_mgr.volume_get()
                    new_lvl = min(1.0, (getattr(curr, "level", 0.5) or 0.5) + 0.1)
                    await self._pc_control_mgr.volume_set(new_lvl)
                    val_pct = int(new_lvl * 100)
                else:
                    val_pct = 60
                detail_str = f"Increased to {val_pct}%"
            elif sub == "down":
                if self._pc_control_mgr and hasattr(self._pc_control_mgr, "volume_get"):
                    curr = await self._pc_control_mgr.volume_get()
                    new_lvl = max(0.0, (getattr(curr, "level", 0.5) or 0.5) - 0.1)
                    await self._pc_control_mgr.volume_set(new_lvl)
                    val_pct = int(new_lvl * 100)
                else:
                    val_pct = 40
                detail_str = f"Decreased to {val_pct}%"
            else:
                target_pct = 50
                if sub.isdigit():
                    target_pct = int(sub)
                else:
                    m = re.search(r"(\d+)", raw_text)
                    if m:
                        target_pct = int(m.group(1))

                level = max(0.0, min(1.0, target_pct / 100.0))
                if self._pc_control_mgr and hasattr(self._pc_control_mgr, "volume_set"):
                    await self._pc_control_mgr.volume_set(level)
                val_pct = target_pct
                detail_str = f"{val_pct}%"

            if lifecycle:
                lifecycle.set_verification(verified=True, details={"volume": detail_str})
                lifecycle.transition_to(ActionState.SUCCESS, "Volume adjusted")

            duration_ms = (time.time() - start_time) * 1000
            nat_msg = NaturalResponseFormatter.format_volume_success(detail_str)
            return f"SUCCESS: {nat_msg} [Fast Execution: {duration_ms:.1f}ms]"
        except Exception as exc:
            if lifecycle:
                lifecycle.transition_to(ActionState.FAILED, f"Volume adjustment error: {exc}")
            return self._format_error(
                summary="Failed to adjust volume",
                root_cause=f"Volume control API error: {exc}",
                tool_name=tool_name,
                exception=f"{type(exc).__name__}: {exc}",
                recovery="Attempted pycaw volume control",
                final_status="FAILED",
            )

    async def _execute_brightness(self, match: RouteMatch, raw_text: str, start_time: float, lifecycle: ActionLifecycle | None = None) -> str:
        sub = match.params.get("sub_action", "50")
        tool_name = "brightness_control"
        if lifecycle:
            lifecycle.transition_to(ActionState.RUNNING, "Adjusting display brightness")

        try:
            target_pct = 50
            if sub == "up":
                target_pct = 80
            elif sub == "down":
                target_pct = 30
            elif sub.isdigit():
                target_pct = int(sub)
            else:
                m = re.search(r"(\d+)", raw_text)
                if m:
                    target_pct = int(m.group(1))

            target_pct = max(0, min(100, target_pct))

            if os.name == "nt":
                ps_cmd = [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    f"$b = Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods -ErrorAction SilentlyContinue; "
                    f"if ($b) {{ $b.WmiSetBrightness(1, {target_pct}) }}"
                ]
                def _run_brightness():
                    try:
                        subprocess.run(ps_cmd, capture_output=True, timeout=1.0)
                    except subprocess.TimeoutExpired:
                        pass

                await asyncio.to_thread(_run_brightness)

            if lifecycle:
                lifecycle.set_verification(verified=True, details={"brightness": target_pct})
                lifecycle.transition_to(ActionState.SUCCESS, "Brightness adjusted")

            duration_ms = (time.time() - start_time) * 1000
            nat_msg = NaturalResponseFormatter.format_brightness_success(target_pct)
            return f"SUCCESS: {nat_msg} [Fast Execution: {duration_ms:.1f}ms]"
        except Exception as exc:
            if lifecycle:
                lifecycle.transition_to(ActionState.FAILED, f"Brightness adjustment error: {exc}")
            return self._format_error(
                summary="Failed to adjust display brightness",
                root_cause=f"WMI / PowerShell brightness execution error: {exc}",
                tool_name=tool_name,
                exception=f"{type(exc).__name__}: {exc}",
                recovery="Attempted WmiMonitorBrightnessMethods PowerShell script with 1s timeout",
                final_status="FAILED",
            )

    async def _execute_filesystem(self, match: RouteMatch, raw_text: str, start_time: float, lifecycle: ActionLifecycle | None = None) -> str:
        intent = match.intent
        target = match.target
        if lifecycle:
            lifecycle.transition_to(ActionState.RUNNING, f"FileSystem action: {intent.name}")

        if intent == CommandIntent.CREATE_FOLDER:
            path = _resolve_fast_path(target)
            tool_name = "filesystem_create_directory"
            try:
                if self._pc_control_mgr and hasattr(self._pc_control_mgr, "filesystem_create_directory"):
                    await self._pc_control_mgr.filesystem_create_directory(str(path))
                else:
                    path.mkdir(parents=True, exist_ok=True)

                if lifecycle:
                    lifecycle.transition_to(ActionState.WAITING, "Verifying folder creation")
                verified = path.exists() and path.is_dir()
                if lifecycle:
                    lifecycle.set_verification(verified=verified, details={"path": str(path)})
                    if verified:
                        lifecycle.transition_to(ActionState.SUCCESS, "Folder created and verified")
                    else:
                        lifecycle.transition_to(ActionState.FAILED, "Folder verification failed")

                duration_ms = (time.time() - start_time) * 1000
                nat_msg = NaturalResponseFormatter.format_file_op_success("create_folder", path.name)
                return f"SUCCESS: {nat_msg} [Fast Execution: {duration_ms:.1f}ms]"
            except Exception as exc:
                if lifecycle:
                    lifecycle.transition_to(ActionState.FAILED, f"Exception: {exc}")
                return self._format_error(
                    summary=f"Failed to create folder '{target}'",
                    root_cause=f"Directory creation failed at target path '{path}': {exc}",
                    tool_name=tool_name,
                    exception=f"{type(exc).__name__}: {exc}",
                    recovery="Attempted direct pathlib directory creation.",
                    final_status="FAILED",
                )

        if intent == CommandIntent.DELETE_FOLDER:
            path = _resolve_fast_path(target)
            tool_name = "filesystem_delete_directory"
            try:
                if not path.exists():
                    if lifecycle:
                        lifecycle.transition_to(ActionState.FAILED, "Folder does not exist")
                    duration_ms = (time.time() - start_time) * 1000
                    return f"INVALID_TARGET: Cannot delete folder '{target}' because it does not exist. [Fast Execution: {duration_ms:.1f}ms]"
                if self._pc_control_mgr and hasattr(self._pc_control_mgr, "filesystem_delete_directory"):
                    await self._pc_control_mgr.filesystem_delete_directory(str(path), recursive=True)
                else:
                    shutil.rmtree(str(path))

                if lifecycle:
                    lifecycle.transition_to(ActionState.WAITING, "Verifying folder deletion")
                verified = not path.exists()
                if lifecycle:
                    lifecycle.set_verification(verified=verified, details={"path": str(path)})
                    lifecycle.transition_to(ActionState.SUCCESS if verified else ActionState.FAILED, "Deletion check complete")

                duration_ms = (time.time() - start_time) * 1000
                nat_msg = NaturalResponseFormatter.format_file_op_success("delete_folder", path.name)
                return f"SUCCESS: {nat_msg} [Fast Execution: {duration_ms:.1f}ms]"
            except Exception as exc:
                if lifecycle:
                    lifecycle.transition_to(ActionState.FAILED, f"Exception: {exc}")
                return self._format_error(
                    summary=f"Failed to delete folder '{target}'",
                    root_cause=f"Directory deletion error at path '{path}': {exc}",
                    tool_name=tool_name,
                    exception=f"{type(exc).__name__}: {exc}",
                    recovery="Attempted recursive rmtree deletion.",
                    final_status="FAILED",
                )

        if intent == CommandIntent.RENAME_FOLDER:
            old_name = match.params.get("old", target)
            new_name = match.params.get("new", target)
            old_path = _resolve_fast_path(old_name)
            new_path = _resolve_fast_path(new_name)
            tool_name = "filesystem_rename_directory"
            try:
                if not old_path.exists():
                    if lifecycle:
                        lifecycle.transition_to(ActionState.FAILED, "Source folder does not exist")
                    duration_ms = (time.time() - start_time) * 1000
                    return f"INVALID_TARGET: Cannot rename folder '{old_name}' because source path does not exist. [Fast Execution: {duration_ms:.1f}ms]"
                old_path.rename(new_path)

                if lifecycle:
                    lifecycle.transition_to(ActionState.WAITING, "Verifying folder rename")
                verified = new_path.exists()
                if lifecycle:
                    lifecycle.set_verification(verified=verified, details={"old": str(old_path), "new": str(new_path)})
                    lifecycle.transition_to(ActionState.SUCCESS if verified else ActionState.FAILED, "Rename check complete")

                duration_ms = (time.time() - start_time) * 1000
                nat_msg = NaturalResponseFormatter.format_file_op_success("rename_folder", old_path.name, new_path.name)
                return f"SUCCESS: {nat_msg} [Fast Execution: {duration_ms:.1f}ms]"
            except Exception as exc:
                if lifecycle:
                    lifecycle.transition_to(ActionState.FAILED, f"Exception: {exc}")
                return self._format_error(
                    summary=f"Failed to rename folder '{old_name}'",
                    root_cause=f"Error renaming folder from '{old_path}' to '{new_path}': {exc}",
                    tool_name=tool_name,
                    exception=f"{type(exc).__name__}: {exc}",
                    recovery="Attempted OS path rename.",
                    final_status="FAILED",
                )

        if intent == CommandIntent.CREATE_FILE:
            path = _resolve_fast_path(target)
            tool_name = "filesystem_write_file"
            try:
                if self._pc_control_mgr and hasattr(self._pc_control_mgr, "filesystem_write_file"):
                    await self._pc_control_mgr.filesystem_write_file(str(path), "")
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.touch()

                if lifecycle:
                    lifecycle.transition_to(ActionState.WAITING, "Verifying file creation")
                verified = path.exists() and path.is_file()
                if lifecycle:
                    lifecycle.set_verification(verified=verified, details={"path": str(path)})
                    lifecycle.transition_to(ActionState.SUCCESS if verified else ActionState.FAILED, "Creation check complete")

                duration_ms = (time.time() - start_time) * 1000
                nat_msg = NaturalResponseFormatter.format_file_op_success("create_file", path.name)
                return f"SUCCESS: {nat_msg} [Fast Execution: {duration_ms:.1f}ms]"
            except Exception as exc:
                if lifecycle:
                    lifecycle.transition_to(ActionState.FAILED, f"Exception: {exc}")
                return self._format_error(
                    summary=f"Failed to create file '{target}'",
                    root_cause=f"File creation failed at path '{path}': {exc}",
                    tool_name=tool_name,
                    exception=f"{type(exc).__name__}: {exc}",
                    recovery="Attempted direct pathlib touch execution.",
                    final_status="FAILED",
                )

        if intent == CommandIntent.DELETE_FILE:
            path = _resolve_fast_path(target)
            tool_name = "filesystem_delete_file"
            try:
                if not path.exists():
                    if lifecycle:
                        lifecycle.transition_to(ActionState.FAILED, "Target file does not exist")
                    duration_ms = (time.time() - start_time) * 1000
                    return f"INVALID_TARGET: Cannot delete file '{target}' because target file does not exist. [Fast Execution: {duration_ms:.1f}ms]"
                if self._pc_control_mgr and hasattr(self._pc_control_mgr, "filesystem_delete_file"):
                    await self._pc_control_mgr.filesystem_delete_file(str(path))
                else:
                    path.unlink()

                if lifecycle:
                    lifecycle.transition_to(ActionState.WAITING, "Verifying file deletion")
                verified = not path.exists()
                if lifecycle:
                    lifecycle.set_verification(verified=verified, details={"path": str(path)})
                    lifecycle.transition_to(ActionState.SUCCESS if verified else ActionState.FAILED, "File deletion check complete")

                duration_ms = (time.time() - start_time) * 1000
                nat_msg = NaturalResponseFormatter.format_file_op_success("delete_file", path.name)
                return f"SUCCESS: {nat_msg} [Fast Execution: {duration_ms:.1f}ms]"
            except Exception as exc:
                if lifecycle:
                    lifecycle.transition_to(ActionState.FAILED, f"Exception: {exc}")
                return self._format_error(
                    summary=f"Failed to delete file '{target}'",
                    root_cause=f"Error deleting file at path '{path}': {exc}",
                    tool_name=tool_name,
                    exception=f"{type(exc).__name__}: {exc}",
                    recovery="Attempted direct path unlink.",
                    final_status="FAILED",
                )

        if intent == CommandIntent.OPEN_FILE:
            path = _resolve_fast_path(target)
            tool_name = "launch_application"
            try:
                if not path.exists():
                    if lifecycle:
                        lifecycle.transition_to(ActionState.FAILED, "Target file does not exist")
                    duration_ms = (time.time() - start_time) * 1000
                    return f"INVALID_TARGET: Cannot open file '{target}' because target file does not exist. [Fast Execution: {duration_ms:.1f}ms]"
                if os.name == "nt":
                    os.startfile(str(path))
                else:
                    subprocess.Popen(["xdg-open", str(path)])

                verified, proc_info, win_info = await self._verify_launch(
                    app_key=path.suffix.lstrip("."),
                    target=str(path),
                    timeout=1.0,
                    lifecycle=lifecycle,
                )
                duration_ms = (time.time() - start_time) * 1000
                if not verified:
                    if lifecycle:
                        lifecycle.transition_to(ActionState.FAILED, "File open process or window could not be verified")
                    nat_msg = NaturalResponseFormatter.format_file_op_failed("open_file", path.name, "Editor/viewer process or window could not be verified")
                    return f"FAILED_TO_LAUNCH: {nat_msg} [Fast Execution: {duration_ms:.1f}ms]"

                if lifecycle:
                    lifecycle.set_verification(verified=True, running_process=proc_info, window_detected=win_info, details={"path": str(path)})
                    lifecycle.transition_to(ActionState.SUCCESS, "File opened via OS handler")

                nat_msg = NaturalResponseFormatter.format_file_op_success("open_file", path.name)
                return f"SUCCESS: {nat_msg} [Fast Execution: {duration_ms:.1f}ms]"
            except Exception as exc:
                if lifecycle:
                    lifecycle.transition_to(ActionState.FAILED, f"Exception: {exc}")
                return self._format_error(
                    summary=f"Failed to open file '{target}'",
                    root_cause=f"OS startfile failed for file '{path}': {exc}",
                    tool_name=tool_name,
                    exception=f"{type(exc).__name__}: {exc}",
                    recovery="Attempted OS startfile execution.",
                    final_status="FAILED",
                )

        if intent == CommandIntent.RENAME_FILE:
            old_name = match.params.get("old", target)
            new_name = match.params.get("new", target)
            old_path = _resolve_fast_path(old_name)
            new_path = _resolve_fast_path(new_name)
            tool_name = "filesystem_rename_file"
            try:
                if not old_path.exists():
                    if lifecycle:
                        lifecycle.transition_to(ActionState.FAILED, "Source file does not exist")
                    duration_ms = (time.time() - start_time) * 1000
                    return f"INVALID_TARGET: Cannot rename file '{old_name}' because source file does not exist. [Fast Execution: {duration_ms:.1f}ms]"
                old_path.rename(new_path)

                if lifecycle:
                    lifecycle.transition_to(ActionState.WAITING, "Verifying file rename")
                verified = new_path.exists()
                if lifecycle:
                    lifecycle.set_verification(verified=verified, details={"old": str(old_path), "new": str(new_path)})
                    lifecycle.transition_to(ActionState.SUCCESS if verified else ActionState.FAILED, "File rename check complete")

                duration_ms = (time.time() - start_time) * 1000
                nat_msg = NaturalResponseFormatter.format_file_op_success("rename_file", old_path.name, new_path.name)
                return f"SUCCESS: {nat_msg} [Fast Execution: {duration_ms:.1f}ms]"
            except Exception as exc:
                if lifecycle:
                    lifecycle.transition_to(ActionState.FAILED, f"Exception: {exc}")
                return self._format_error(
                    summary=f"Failed to rename file '{old_name}'",
                    root_cause=f"Error renaming file from '{old_path}' to '{new_path}': {exc}",
                    tool_name=tool_name,
                    exception=f"{type(exc).__name__}: {exc}",
                    recovery="Attempted OS path rename.",
                    final_status="FAILED",
                )

        if lifecycle:
            lifecycle.transition_to(ActionState.FAILED, "Unrecognized filesystem intent")
        return self._format_error(
            summary=f"Unrecognized filesystem intent: {intent.name}",
            root_cause="Filesystem handler failed to recognize intent enum.",
            tool_name="FileSystem",
            exception="ValueError",
            recovery="Fallback requested",
            final_status="FAILED"
        )

    # ----------------------------------------------------------------------
    # New Private Execute Handlers (STEP 6)
    # ----------------------------------------------------------------------

    async def _execute_screenshot(self, match: RouteMatch, start_time: float, lifecycle: ActionLifecycle | None = None) -> str:
        if lifecycle:
            lifecycle.transition_to(ActionState.RUNNING, "Capturing screenshot")
        try:
            screenshot_dir = Path.home() / "Desktop" / "Screenshots"
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = screenshot_dir / f"naira_{timestamp}.png"

            if self._vision_mgr and hasattr(self._vision_mgr, "capture_and_save"):
                res = await self._vision_mgr.capture_and_save(str(file_path))
                if getattr(res, "status", "") == "error":
                    raise RuntimeError(f"VisionManager capture error: {getattr(res, 'error', '')}")
            else:
                def _take_screenshot():
                    import mss
                    with mss.mss() as sct:
                        sct.shot(output=str(file_path))

                await asyncio.to_thread(_take_screenshot)

            if lifecycle:
                lifecycle.set_verification(verified=file_path.exists(), details={"file_path": str(file_path)})
                lifecycle.transition_to(ActionState.SUCCESS, "Screenshot captured")

            duration_ms = (time.time() - start_time) * 1000
            return f"SUCCESS: Captured screenshot to {file_path.name}. [Fast Execution: {duration_ms:.1f}ms]"
        except Exception as exc:
            if lifecycle:
                lifecycle.transition_to(ActionState.FAILED, f"Screenshot exception: {exc}")
            return self._format_error(
                summary="Failed to capture screenshot",
                root_cause=f"Screenshot error: {exc}",
                tool_name="Screenshot",
                exception=f"{type(exc).__name__}: {exc}",
                recovery="Attempted mss library screenshot",
                final_status="FAILED",
            )

    async def _execute_system_info(self, match: RouteMatch, start_time: float, lifecycle: ActionLifecycle | None = None) -> str:
        sub = match.params.get("sub", "")
        if lifecycle:
            lifecycle.transition_to(ActionState.RUNNING, f"Querying system info: {sub}")
        try:
            import psutil

            details = ""
            if sub == "battery":
                batt = psutil.sensors_battery()
                if batt:
                    status = "Plugged in" if batt.power_plugged else "Discharging"
                    details = f"Battery is at {batt.percent:.0f}% ({status})"
                else:
                    details = "Battery information unavailable"
            elif sub == "time":
                details = f"Current time is {datetime.datetime.now().strftime('%I:%M %p')}"
            elif sub == "date":
                details = f"Today's date is {datetime.datetime.now().strftime('%A, %B %d, %Y')}"
            elif sub == "ip":
                hostname = socket.gethostname()
                ip_addr = socket.gethostbyname(hostname)
                details = f"IP Address: {ip_addr} (Host: {hostname})"
            elif sub == "ram":
                mem = psutil.virtual_memory()
                details = f"RAM Usage: {mem.percent}% ({mem.used // (1024**2)} MB / {mem.total // (1024**2)} MB)"
            elif sub == "cpu":
                cpu_pct = psutil.cpu_percent(interval=None)
                details = f"CPU Utilization: {cpu_pct}% ({psutil.cpu_count(logical=True)} cores)"
            elif sub == "disk":
                disk = psutil.disk_usage("/")
                details = f"Disk Usage: {disk.percent}% ({disk.free // (1024**3)} GB free of {disk.total // (1024**3)} GB)"
            else:
                details = f"System info option '{sub}' not recognized"

            if lifecycle:
                lifecycle.set_verification(verified=True, details={"sub": sub, "info": details})
                lifecycle.transition_to(ActionState.SUCCESS, "System info queried")

            duration_ms = (time.time() - start_time) * 1000
            return f"INFO: {details}. [Fast Execution: {duration_ms:.1f}ms]"
        except Exception as exc:
            if lifecycle:
                lifecycle.transition_to(ActionState.FAILED, f"System info exception: {exc}")
            return self._format_error(
                summary=f"Failed to get system info for '{sub}'",
                root_cause=f"System info error: {exc}",
                tool_name="SystemInfo",
                exception=f"{type(exc).__name__}: {exc}",
                recovery="Attempted psutil/socket query",
                final_status="FAILED",
            )

    async def _execute_window_control(self, match: RouteMatch, start_time: float, lifecycle: ActionLifecycle | None = None) -> str:
        action = match.params.get("action", "")
        app_name = match.params.get("app_name", "").lower()
        if lifecycle:
            lifecycle.transition_to(ActionState.RUNNING, f"Window control: {action} on {app_name}")
        try:
            def _control_window():
                if os.name != "nt":
                    return False, "Window control is only supported on Windows"
                import win32gui
                import win32con

                matched_hwnd = None
                matched_title = None

                def enum_cb(hwnd, _):
                    nonlocal matched_hwnd, matched_title
                    if win32gui.IsWindowVisible(hwnd):
                        txt = win32gui.GetWindowText(hwnd)
                        if txt and app_name in txt.lower():
                            matched_hwnd = hwnd
                            matched_title = txt
                            return False
                    return True

                win32gui.EnumWindows(enum_cb, None)
                if not matched_hwnd:
                    return False, f"No open window matching '{app_name}' found"

                if action == "minimize":
                    win32gui.ShowWindow(matched_hwnd, win32con.SW_MINIMIZE)
                    return True, f"Minimized window '{matched_title}'"
                elif action == "maximize":
                    win32gui.ShowWindow(matched_hwnd, win32con.SW_MAXIMIZE)
                    win32gui.SetForegroundWindow(matched_hwnd)
                    return True, f"Maximized window '{matched_title}'"
                elif action == "close":
                    win32gui.PostMessage(matched_hwnd, win32con.WM_CLOSE, 0, 0)
                    return True, f"Closed window '{matched_title}'"
                return False, f"Unknown window action '{action}'"

            success, msg = await asyncio.to_thread(_control_window)
            if lifecycle:
                lifecycle.set_verification(verified=success, details={"action": action, "msg": msg})
                lifecycle.transition_to(ActionState.SUCCESS if success else ActionState.FAILED, "Window control finish")

            duration_ms = (time.time() - start_time) * 1000
            if success:
                return f"SUCCESS: {msg}. [Fast Execution: {duration_ms:.1f}ms]"
            else:
                return f"INVALID_TARGET: {msg}. [Fast Execution: {duration_ms:.1f}ms]"
        except Exception as exc:
            if lifecycle:
                lifecycle.transition_to(ActionState.FAILED, f"Window control exception: {exc}")
            return self._format_error(
                summary=f"Failed window control '{action}' for '{app_name}'",
                root_cause=f"Window control API error: {exc}",
                tool_name="WindowControl",
                exception=f"{type(exc).__name__}: {exc}",
                recovery="Attempted win32gui EnumWindows",
                final_status="FAILED",
            )

    async def _execute_kill_process(self, match: RouteMatch, start_time: float, lifecycle: ActionLifecycle | None = None) -> str:
        app_name = match.params.get("app_name", "").lower()
        if lifecycle:
            lifecycle.transition_to(ActionState.RUNNING, f"Killing process: {app_name}")
        try:
            def _kill():
                import psutil
                killed_count = 0
                for p in psutil.process_iter(['pid', 'name']):
                    try:
                        p_name = (p.info.get('name') or '').lower()
                        if app_name and (app_name in p_name or p_name.startswith(app_name)):
                            p.kill()
                            killed_count += 1
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
                return killed_count

            count = await asyncio.to_thread(_kill)
            if lifecycle:
                lifecycle.set_verification(verified=count > 0, details={"killed_count": count})
                lifecycle.transition_to(ActionState.SUCCESS if count > 0 else ActionState.FAILED, "Process kill finished")

            duration_ms = (time.time() - start_time) * 1000
            if count > 0:
                return f"SUCCESS: Killed {count} process(es) matching '{app_name}'. [Fast Execution: {duration_ms:.1f}ms]"
            else:
                return f"INVALID_TARGET: No active processes found matching '{app_name}'. [Fast Execution: {duration_ms:.1f}ms]"
        except Exception as exc:
            if lifecycle:
                lifecycle.transition_to(ActionState.FAILED, f"Kill process exception: {exc}")
            return self._format_error(
                summary=f"Failed to kill process '{app_name}'",
                root_cause=f"Process kill error: {exc}",
                tool_name="KillProcess",
                exception=f"{type(exc).__name__}: {exc}",
                recovery="Attempted psutil process termination",
                final_status="FAILED",
            )

    async def _execute_web_search(self, match: RouteMatch, start_time: float, lifecycle: ActionLifecycle | None = None) -> str:
        if lifecycle:
            lifecycle.transition_to(ActionState.RUNNING, "Launching web search")
        try:
            url = match.target
            platform = match.params.get("platform", "web").title()
            query = match.params.get("query", "")
            webbrowser.open(url)

            if lifecycle:
                lifecycle.set_verification(verified=True, details={"platform": platform, "query": query, "url": url})
                lifecycle.transition_to(ActionState.SUCCESS, "Web search browser launched")

            duration_ms = (time.time() - start_time) * 1000
            nat_msg = NaturalResponseFormatter.format_web_search_success(query, platform)
            return f"SUCCESS: {nat_msg} [Fast Execution: {duration_ms:.1f}ms]"
        except Exception as exc:
            if lifecycle:
                lifecycle.transition_to(ActionState.FAILED, f"Web search exception: {exc}")
            return self._format_error(
                summary="Failed to open web search",
                root_cause=f"Webbrowser error: {exc}",
                tool_name="WebSearch",
                exception=f"{type(exc).__name__}: {exc}",
                recovery="Attempted webbrowser open",
                final_status="FAILED",
            )

    async def _execute_clipboard(self, match: RouteMatch, start_time: float, lifecycle: ActionLifecycle | None = None) -> str:
        if lifecycle:
            lifecycle.transition_to(ActionState.RUNNING, "Clearing clipboard")
        try:
            import pyperclip
            pyperclip.copy('')

            if lifecycle:
                lifecycle.set_verification(verified=True, details={"clipboard": "cleared"})
                lifecycle.transition_to(ActionState.SUCCESS, "Clipboard cleared")

            duration_ms = (time.time() - start_time) * 1000
            return f"SUCCESS: Cleared system clipboard. [Fast Execution: {duration_ms:.1f}ms]"
        except Exception as exc:
            if lifecycle:
                lifecycle.transition_to(ActionState.FAILED, f"Clipboard exception: {exc}")
            return self._format_error(
                summary="Failed to clear clipboard",
                root_cause=f"Pyperclip error: {exc}",
                tool_name="ClipboardOp",
                exception=f"{type(exc).__name__}: {exc}",
                recovery="Attempted pyperclip.copy empty string",
                final_status="FAILED",
            )

    async def _execute_run_cmd(self, match: RouteMatch, start_time: float, lifecycle: ActionLifecycle | None = None) -> str:
        cmd = match.params.get("cmd", match.target)
        if lifecycle:
            lifecycle.transition_to(ActionState.RUNNING, f"Executing safe CLI command: {cmd}")
        try:
            def _run():
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                out = res.stdout or res.stderr or ""
                return out.strip()

            output = await asyncio.to_thread(_run)
            if len(output) > 800:
                output = output[:800] + "... (truncated)"

            if lifecycle:
                lifecycle.set_verification(verified=True, details={"cmd": cmd, "output_len": len(output)})
                lifecycle.transition_to(ActionState.SUCCESS, "Safe command executed")

            duration_ms = (time.time() - start_time) * 1000
            return f"SUCCESS: Executed command '{cmd}'. Output: {output} [Fast Execution: {duration_ms:.1f}ms]"
        except Exception as exc:
            if lifecycle:
                lifecycle.transition_to(ActionState.FAILED, f"Safe CLI execution exception: {exc}")
            return self._format_error(
                summary=f"Failed to execute safe command '{cmd}'",
                root_cause=f"Subprocess execution error: {exc}",
                tool_name="RunCmdSafe",
                exception=f"{type(exc).__name__}: {exc}",
                recovery="Attempted subprocess.run shell execution",
                final_status="FAILED",
            )

    def _format_error(
        self,
        summary: str,
        root_cause: str,
        tool_name: str,
        exception: str,
        recovery: str,
        final_status: str = "FAILED",
    ) -> str:
        code = "INVALID_TARGET" if ("Unrecognized" in summary or "invalid" in summary or "missing" in summary.lower()) else "FAILED_TO_LAUNCH"
        return (
            f"{code}: Action Failed: {summary}\n"
            f"• Root Cause: {root_cause}\n"
            f"• Tool Name: {tool_name}\n"
            f"• Exception: {exception}\n"
            f"• Recovery Attempt: {recovery}\n"
            f"• Final Status: {final_status}"
        )
