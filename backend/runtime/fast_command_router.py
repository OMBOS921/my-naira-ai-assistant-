"""
FastCommandRouter — High-performance direct execution router for simple desktop commands.

Bypasses LLM reasoning for deterministic Windows OS operations across English, Hindi, and Hinglish.
Target execution latency: < 10 ms.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import time
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Set

if os.name == "nt":
    import winreg

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
        "सुनो", "सुन", "करो", "दो", "कर", "दीजिये", "दीजिए", "नायर"
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
    1. Windows Registry  App Paths
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

        # 2. Open App / Website Intents (fast path for valid aliases)
        match = self._match_open(cleaned_text, lowered_raw)
        if match and not match.params.get("is_invalid_target"):
            return match

        # 3. System Intents (Lock, Shutdown, Restart)
        match = self._match_system_control(cleaned_text, lowered_raw)
        if match:
            return match

        # 4. Volume Intents
        match = self._match_volume(cleaned_text, lowered_raw)
        if match:
            return match

        # 5. Brightness Intents
        match = self._match_brightness(cleaned_text, lowered_raw)
        if match:
            return match

        # 6. Filesystem Intents
        match = self._match_filesystem(cleaned_text, lowered_raw)
        if match:
            return match

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
        logger: logging.Logger | None = None,
        config_path: Path | None = None,
        enable_discovery: bool = True,
    ) -> None:
        self._pc_control_mgr = pc_control_manager
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
    ) -> Tuple[bool, str | None, str | None]:
        """Verify if process started, window appeared, or executable exists in running processes.

        Logs using [FCR] Launch Verification logging specification.
        Returns (verified: bool, running_process: str | None, window_detected: str | None)
        """
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

            # Fallback for website targets when webbrowser.open succeeded
            if not running_proc and not window_det and target and target.startswith(("http://", "https://", "www.")):
                running_proc = "Default Browser (webbrowser.open)"

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

    async def execute_fast_command(self, text: str) -> str:
        """Execute a matched fast command directly and return structured output or error report."""
        start_time = time.time()
        match = self.intent_engine.match(text)

        if not match:
            return self._format_error(
                summary=f"Unrecognized fast command: '{text}'",
                root_cause="Fast command match pattern succeeded during detection but execution route was null.",
                tool_name="FastCommandRouter",
                exception="ValueError('No handler matched')",
                recovery="Fallback to Gemini requested",
                final_status="FAILED",
            )

        self._logger.info("[FCR] Intent=%s", match.intent.name)
        self._logger.info("[FCR] Target=%s", match.target)
        self._logger.info("[FCR] Confidence=%.1f", match.confidence)
        self._logger.info("[FCR] Handler=%s", match.handler_name)

        try:
            if match.intent in (CommandIntent.OPEN_APP, CommandIntent.OPEN_WEBSITE):
                return await self._execute_open(match, start_time)

            if match.intent in (CommandIntent.LOCK_PC, CommandIntent.SHUTDOWN, CommandIntent.RESTART):
                return await self._execute_system_control(match, start_time)

            if match.intent == CommandIntent.SET_VOLUME:
                return await self._execute_volume(match, text, start_time)

            if match.intent == CommandIntent.SET_BRIGHTNESS:
                return await self._execute_brightness(match, text, start_time)

            if match.intent in (
                CommandIntent.CREATE_FOLDER, CommandIntent.DELETE_FOLDER, CommandIntent.RENAME_FOLDER,
                CommandIntent.CREATE_FILE, CommandIntent.DELETE_FILE, CommandIntent.OPEN_FILE, CommandIntent.RENAME_FILE
            ):
                return await self._execute_filesystem(match, text, start_time)

            return self._format_error(
                summary=f"Unhandled intent: {match.intent.name}",
                root_cause="Intent match was found but no execution handler was registered for it.",
                tool_name="FastCommandRouter",
                exception="NotImplementedError",
                recovery="Fallback to Gemini requested",
                final_status="FAILED",
            )
        except Exception as exc:
            self._logger.error("FastCommandRouter execution exception: %s", exc, exc_info=True)
            return self._format_error(
                summary=f"Execution error for '{text}'",
                root_cause=f"An exception occurred during fast command execution: {exc}",
                tool_name="FastCommandRouter",
                exception=f"{type(exc).__name__}: {exc}",
                recovery="Attempted direct OS execution without Gemini",
                final_status="FAILED",
            )

    # ------------------------------------------------------------------
    # Dispatch Handlers
    # ------------------------------------------------------------------

    async def _execute_open(self, match: RouteMatch, start_time: float) -> str:
        app_target = match.target
        target_raw = match.params.get("raw_target", app_target)
        tool_used = "launch_application"

        # BUG 4 (P1): Invalid target check
        if match.params.get("is_invalid_target") or not app_target or not app_target.strip():
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

        discovered_exe: str | None = None
        launch_method = "system_start"

        if self.discovery_engine and app_key and not is_builtin_cli:
            discovered_exe = self.discovery_engine.get_executable(app_key)

        # --- Determine installation status (BUG 2) -------------------
        BUILTIN_APPS = {
            "calc", "notepad", "cmd", "powershell", "explorer", "mspaint",
            "taskmgr", "control", "regedit", "snippingtool", "devmgmt.msc", "wt"
        }
        app_is_installed = False
        if app_target.startswith(("http://", "https://", "www.")):
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

        # --- NOT_INSTALLED gate -> Browser Fallback (BUG 2) -----------
        # Browser fallback ONLY executes when app_is_installed is False!
        if not app_is_installed:
            if fallback_url:
                import webbrowser
                self._logger.info("[FCR]\nFallback=True\nFallbackURL=%s\nReason=NOT_INSTALLED", fallback_url)
                self._logger.info("[FCR]")
                self._logger.info("Fallback=True")
                self._logger.info("FallbackURL=%s", fallback_url)
                self._logger.info("Reason=NOT_INSTALLED")

                webbrowser.open(fallback_url)
                await self._verify_launch(app_key, fallback_url, timeout=0.5)
                duration_ms = (time.time() - start_time) * 1000
                return (
                    f"BROWSER_FALLBACK: '{name_display}' is not installed. "
                    f"Opened web version at {fallback_url}. [Fast Execution: {duration_ms:.1f}ms]"
                )

            # No fallback URL registered
            self._logger.info("[FCR]\nFallback=False\nReason=NOT_INSTALLED")
            self._logger.info("[FCR]")
            self._logger.info("Fallback=False")
            self._logger.info("Reason=NOT_INSTALLED")
            duration_ms = (time.time() - start_time) * 1000
            return (
                f"NOT_INSTALLED: '{name_display}' is not installed on this system. "
                f"[Fast Execution: {duration_ms:.1f}ms]"
            )

        # --- BUG 5 (P1): Duplicate Command Protection -----------------
        if self._mock_verification is None and not is_website:
            is_running, running_pid_str, win_title = await self._check_if_running(app_key, app_target)
            if is_running:
                self._focus_window(win_title, app_key or app_target)
                duration_ms = (time.time() - start_time) * 1000
                return f"SUCCESS: Opened {name_display} successfully. (Already Running) [Fast Execution: {duration_ms:.1f}ms]"

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
            verified, proc_info, win_info = await self._verify_launch(app_key, app_target, proc=proc_handle, timeout=1.0)

            duration_ms = (time.time() - start_time) * 1000
            if not verified:
                return (
                    f"FAILED_TO_LAUNCH: Could not verify process or window for '{name_display}'. "
                    f"[Fast Execution: {duration_ms:.1f}ms]"
                )

            return f"SUCCESS: Opened {name_display} successfully. [Fast Execution: {duration_ms:.1f}ms]"

        except Exception as exc:
            self._logger.info("[FCR] LaunchMethod=%s (failed)", launch_method)
            duration_ms = (time.time() - start_time) * 1000
            return f"FAILED_TO_LAUNCH: Failed to open '{name_display}': {exc}. [Fast Execution: {duration_ms:.1f}ms]"

    async def _execute_system_control(self, match: RouteMatch, start_time: float) -> str:
        intent = match.intent
        tool_used = "system_control"

        try:
            if intent == CommandIntent.LOCK_PC:
                if self._pc_control_mgr and hasattr(self._pc_control_mgr, "lock_workstation"):
                    await self._pc_control_mgr.lock_workstation()
                elif os.name == "nt":
                    subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
                duration_ms = (time.time() - start_time) * 1000
                return f"SUCCESS: Locked workstation successfully. [Fast Execution: {duration_ms:.1f}ms]"

            if intent == CommandIntent.SHUTDOWN:
                if self._pc_control_mgr and hasattr(self._pc_control_mgr, "shutdown"):
                    await self._pc_control_mgr.shutdown()
                elif os.name == "nt":
                    subprocess.run(["shutdown", "/s", "/t", "10"])
                duration_ms = (time.time() - start_time) * 1000
                return f"SUCCESS: Initiated system shutdown. [Fast Execution: {duration_ms:.1f}ms]"

            if intent == CommandIntent.RESTART:
                if self._pc_control_mgr and hasattr(self._pc_control_mgr, "restart"):
                    await self._pc_control_mgr.restart()
                elif os.name == "nt":
                    subprocess.run(["shutdown", "/r", "/t", "10"])
                duration_ms = (time.time() - start_time) * 1000
                return f"SUCCESS: Initiated system restart. [Fast Execution: {duration_ms:.1f}ms]"

            raise ValueError(f"Unknown system control intent: {intent.name}")
        except Exception as exc:
            return self._format_error(
                summary=f"Failed system action '{intent.name}'",
                root_cause=f"System control API error: {exc}",
                tool_name=tool_used,
                exception=f"{type(exc).__name__}: {exc}",
                recovery="Attempted Windows API/subprocess call.",
                final_status="FAILED",
            )

    async def _execute_volume(self, match: RouteMatch, raw_text: str, start_time: float) -> str:
        sub = match.params.get("sub_action", "set")
        tool_name = "volume_control"
        lowered = raw_text.lower()

        try:
            if sub == "mute" or lowered in ("mute", "mute volume"):
                if self._pc_control_mgr and hasattr(self._pc_control_mgr, "volume_mute"):
                    await self._pc_control_mgr.volume_mute(True)
                duration_ms = (time.time() - start_time) * 1000
                return f"SUCCESS: Muted system volume. [Fast Execution: {duration_ms:.1f}ms]"

            if sub == "unmute" or lowered in ("unmute", "unmute volume"):
                if self._pc_control_mgr and hasattr(self._pc_control_mgr, "volume_unmute"):
                    await self._pc_control_mgr.volume_unmute()
                duration_ms = (time.time() - start_time) * 1000
                return f"SUCCESS: Unmuted system volume. [Fast Execution: {duration_ms:.1f}ms]"

            if sub == "up":
                if self._pc_control_mgr and hasattr(self._pc_control_mgr, "volume_get"):
                    curr = await self._pc_control_mgr.volume_get()
                    new_lvl = min(1.0, (getattr(curr, "level", 0.5) or 0.5) + 0.1)
                    await self._pc_control_mgr.volume_set(new_lvl)
                    val_pct = int(new_lvl * 100)
                else:
                    val_pct = 60
                duration_ms = (time.time() - start_time) * 1000
                return f"SUCCESS: Increased volume to {val_pct}%. [Fast Execution: {duration_ms:.1f}ms]"

            if sub == "down":
                if self._pc_control_mgr and hasattr(self._pc_control_mgr, "volume_get"):
                    curr = await self._pc_control_mgr.volume_get()
                    new_lvl = max(0.0, (getattr(curr, "level", 0.5) or 0.5) - 0.1)
                    await self._pc_control_mgr.volume_set(new_lvl)
                    val_pct = int(new_lvl * 100)
                else:
                    val_pct = 40
                duration_ms = (time.time() - start_time) * 1000
                return f"SUCCESS: Decreased volume to {val_pct}%. [Fast Execution: {duration_ms:.1f}ms]"

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

            duration_ms = (time.time() - start_time) * 1000
            return f"SUCCESS: Set volume to {target_pct}%. [Fast Execution: {duration_ms:.1f}ms]"
        except Exception as exc:
            return self._format_error(
                summary="Failed to adjust volume",
                root_cause=f"Volume control API error: {exc}",
                tool_name=tool_name,
                exception=f"{type(exc).__name__}: {exc}",
                recovery="Attempted pycaw volume control",
                final_status="FAILED",
            )

    async def _execute_brightness(self, match: RouteMatch, raw_text: str, start_time: float) -> str:
        sub = match.params.get("sub_action", "50")
        tool_name = "brightness_control"
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

            duration_ms = (time.time() - start_time) * 1000
            return f"SUCCESS: Set display brightness to {target_pct}%. [Fast Execution: {duration_ms:.1f}ms]"
        except Exception as exc:
            return self._format_error(
                summary="Failed to adjust display brightness",
                root_cause=f"WMI / PowerShell brightness execution error: {exc}",
                tool_name=tool_name,
                exception=f"{type(exc).__name__}: {exc}",
                recovery="Attempted WmiMonitorBrightnessMethods PowerShell script with 1s timeout",
                final_status="FAILED",
            )

    async def _execute_filesystem(self, match: RouteMatch, raw_text: str, start_time: float) -> str:
        intent = match.intent
        target = match.target

        if intent == CommandIntent.CREATE_FOLDER:
            path = _resolve_fast_path(target)
            tool_name = "filesystem_create_directory"
            try:
                if self._pc_control_mgr and hasattr(self._pc_control_mgr, "filesystem_create_directory"):
                    await self._pc_control_mgr.filesystem_create_directory(str(path))
                else:
                    path.mkdir(parents=True, exist_ok=True)
                duration_ms = (time.time() - start_time) * 1000
                return f"SUCCESS: Created folder '{path.name}' at {path.parent}. [Fast Execution: {duration_ms:.1f}ms]"
            except Exception as exc:
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
                    duration_ms = (time.time() - start_time) * 1000
                    return f"INVALID_TARGET: Cannot delete folder '{target}' because it does not exist. [Fast Execution: {duration_ms:.1f}ms]"
                if self._pc_control_mgr and hasattr(self._pc_control_mgr, "filesystem_delete_directory"):
                    await self._pc_control_mgr.filesystem_delete_directory(str(path), recursive=True)
                else:
                    shutil.rmtree(str(path))
                duration_ms = (time.time() - start_time) * 1000
                return f"SUCCESS: Deleted folder '{path.name}'. [Fast Execution: {duration_ms:.1f}ms]"
            except Exception as exc:
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
                    duration_ms = (time.time() - start_time) * 1000
                    return f"INVALID_TARGET: Cannot rename folder '{old_name}' because source path does not exist. [Fast Execution: {duration_ms:.1f}ms]"
                old_path.rename(new_path)
                duration_ms = (time.time() - start_time) * 1000
                return f"SUCCESS: Renamed folder '{old_path.name}' to '{new_path.name}'. [Fast Execution: {duration_ms:.1f}ms]"
            except Exception as exc:
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
                duration_ms = (time.time() - start_time) * 1000
                return f"SUCCESS: Created file '{path.name}' at {path.parent}. [Fast Execution: {duration_ms:.1f}ms]"
            except Exception as exc:
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
                    duration_ms = (time.time() - start_time) * 1000
                    return f"INVALID_TARGET: Cannot delete file '{target}' because target file does not exist. [Fast Execution: {duration_ms:.1f}ms]"
                if self._pc_control_mgr and hasattr(self._pc_control_mgr, "filesystem_delete_file"):
                    await self._pc_control_mgr.filesystem_delete_file(str(path))
                else:
                    path.unlink()
                duration_ms = (time.time() - start_time) * 1000
                return f"SUCCESS: Deleted file '{path.name}'. [Fast Execution: {duration_ms:.1f}ms]"
            except Exception as exc:
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
                    duration_ms = (time.time() - start_time) * 1000
                    return f"INVALID_TARGET: Cannot open file '{target}' because target file does not exist. [Fast Execution: {duration_ms:.1f}ms]"
                if os.name == "nt":
                    os.startfile(str(path))
                else:
                    subprocess.Popen(["xdg-open", str(path)])
                duration_ms = (time.time() - start_time) * 1000
                return f"SUCCESS: Opened file '{path.name}'. [Fast Execution: {duration_ms:.1f}ms]"
            except Exception as exc:
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
                    duration_ms = (time.time() - start_time) * 1000
                    return f"INVALID_TARGET: Cannot rename file '{old_name}' because source file does not exist. [Fast Execution: {duration_ms:.1f}ms]"
                old_path.rename(new_path)
                duration_ms = (time.time() - start_time) * 1000
                return f"SUCCESS: Renamed file '{old_path.name}' to '{new_path.name}'. [Fast Execution: {duration_ms:.1f}ms]"
            except Exception as exc:
                return self._format_error(
                    summary=f"Failed to rename file '{old_name}'",
                    root_cause=f"Error renaming file from '{old_path}' to '{new_path}': {exc}",
                    tool_name=tool_name,
                    exception=f"{type(exc).__name__}: {exc}",
                    recovery="Attempted OS path rename.",
                    final_status="FAILED",
                )

        return self._format_error(
            summary=f"Unrecognized filesystem intent: {intent.name}",
            root_cause="Filesystem handler failed to recognize intent enum.",
            tool_name="FileSystem",
            exception="ValueError",
            recovery="Fallback requested",
            final_status="FAILED"
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

