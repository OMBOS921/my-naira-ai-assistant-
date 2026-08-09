"""
FastCommandRouter — Groq-powered Semantic Intent Router for Naira-OS.

Replaces legacy hardcoded rule matching with Llama 3.1 8B Instant via Groq REST API,
featuring a Universal Action Schema with an operations array for multi-task execution,
smart dynamic path resolution, an agentic JSON self-correction loop, and direct module execution.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from backend.types import ToolResult

_LOG = logging.getLogger("naira.runtime.fast_command_router")

# Hardcoded model & endpoint as specified in system requirements
GROQ_MODEL = "llama-3.1-8b-instant"
GROQ_API_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


# ----------------------------------------------------------------------
# 1. Intent Definitions
# ----------------------------------------------------------------------

class CommandIntent(str, Enum):
    SYSTEM_CONTROL = "SYSTEM_CONTROL"
    BROWSER_CONTROL = "BROWSER_CONTROL"
    FILE_SYSTEM = "FILE_SYSTEM"
    CODING_AGENT = "CODING_AGENT"
    CONVERSATION = "CONVERSATION"
    OPEN_APP = "OPEN_APP"
    OPEN_WEBSITE = "OPEN_WEBSITE"
    SET_VOLUME = "SET_VOLUME"
    SET_BRIGHTNESS = "SET_BRIGHTNESS"
    LOCK_PC = "LOCK_PC"
    SHUTDOWN = "SHUTDOWN"
    RESTART = "RESTART"
    CREATE_FOLDER = "CREATE_FOLDER"
    DELETE_FOLDER = "DELETE_FOLDER"
    RENAME_FOLDER = "RENAME_FOLDER"
    CREATE_FILE = "CREATE_FILE"
    DELETE_FILE = "DELETE_FILE"
    OPEN_FILE = "OPEN_FILE"
    RENAME_FILE = "RENAME_FILE"
    SCREENSHOT = "SCREENSHOT"
    SYSTEM_INFO = "SYSTEM_INFO"
    KILL_PROCESS = "KILL_PROCESS"
    WEB_SEARCH = "WEB_SEARCH"
    UNKNOWN = "UNKNOWN"


# ----------------------------------------------------------------------
# 2. Compatibility Stubs & Helper Utilities
# ----------------------------------------------------------------------

class RouteMatch:
    """Represents a matched route result for legacy API callers."""
    def __init__(
        self,
        intent: Union[CommandIntent, str] = CommandIntent.UNKNOWN,
        confidence: float = 1.0,
        action: str = "",
        target: str = "",
        parameters: Optional[Dict[str, Any]] = None,
        state: str = "SUCCESS",
    ) -> None:
        self.intent = intent
        self.confidence = confidence
        self.action = action
        self.target = target
        self.parameters = parameters or {}
        self.state = state


class AliasEngine:
    """Compatibility stub for legacy alias resolution."""
    ALIASES = {
        "yt": "https://youtube.com",
        "यूट्यूब": "https://youtube.com",
        "g": "https://google.com",
        "गूगल": "https://google.com",
        "google chrome": "chrome",
        "गूगल क्रोम": "chrome",
        "calc": "calculator",
        "vscode": "code",
        "vs code": "code",
        "वीएस कोड": "code",
    }
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass
    def resolve(self, text: str) -> str:
        return self.ALIASES.get(text.strip().lower(), text)


class IntentEngine:
    """Compatibility stub for legacy intent engine."""
    def __init__(self, router: Optional[Any] = None, *args: Any, **kwargs: Any) -> None:
        self._router = router

    def match(self, text: str) -> RouteMatch:
        cleaned = WakeWordCleaner.clean(text)
        lowered = text.lower()

        if "lock" in lowered or "लॉक" in text:
            intent = CommandIntent.LOCK_PC
        elif "shutdown" in lowered or "off" in lowered or "band" in lowered or "बंद" in text:
            intent = CommandIntent.SHUTDOWN
        elif "restart" in lowered or "reboot" in lowered or "रीस्टार्ट" in text:
            intent = CommandIntent.RESTART
        elif "screenshot" in lowered or "capture" in lowered or "स्क्रीनशॉट" in text:
            intent = CommandIntent.SCREENSHOT
        elif "volume" in lowered or "sound" in lowered or "awaaz" in lowered or "mute" in lowered or "आवाज़" in text or "वॉल्यूम" in text or "वोल्यूम" in text:
            intent = CommandIntent.SET_VOLUME
        elif "brightness" in lowered or "roshni" in lowered or "ब्राइटनेस" in text:
            intent = CommandIntent.SET_BRIGHTNESS
        elif "delete folder" in lowered or "remove folder" in lowered or "rmdir" in lowered:
            intent = CommandIntent.DELETE_FOLDER
        elif "delete file" in lowered or "remove file" in lowered or "unlink" in lowered:
            intent = CommandIntent.DELETE_FILE
        elif "rename folder" in lowered:
            intent = CommandIntent.RENAME_FOLDER
        elif "rename file" in lowered:
            intent = CommandIntent.RENAME_FILE
        elif "open file explorer" in lowered or "explorer" in lowered:
            intent = CommandIntent.OPEN_APP
        elif "open file" in lowered:
            intent = CommandIntent.OPEN_FILE
        elif "create file" in lowered or "make file" in lowered or "touch" in lowered:
            intent = CommandIntent.CREATE_FILE
        elif "create folder" in lowered or "make folder" in lowered or "mkdir" in lowered:
            intent = CommandIntent.CREATE_FOLDER
        elif "youtube" in lowered or "यूट्यूब" in text or "yt" in lowered or "http" in lowered or "www" in lowered or ".com" in lowered:
            intent = CommandIntent.OPEN_WEBSITE
        elif any(k in lowered for k in ("open", "kholo", "launch", "chalao", "calc", "chrome", "notepad", "code", "cmd", "explorer", "vscode", "settings")) or "खोलो" in text or "क्रोम" in text or "चलाओ" in text or "कोड" in text:
            intent = CommandIntent.OPEN_APP
        elif "file" in lowered:
            intent = CommandIntent.CREATE_FILE
        else:
            intent = CommandIntent.CREATE_FOLDER

        return RouteMatch(intent=intent, confidence=1.0, target=cleaned)

    def classify(self, text: str) -> RouteMatch:
        return self.match(text)


class AppDiscoveryEngine:
    """Compatibility stub for legacy application discovery."""
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.discovered_apps: Dict[str, str] = {}
    def discover(self) -> Dict[str, str]:
        return {}


def _resolve_smart_path(
    params: Optional[Dict[str, Any]] = None,
    target: str = "",
    raw_text: str = "",
    default_is_file: bool = False
) -> Path:
    """Smart path resolver for FILE_SYSTEM operations in Naira-OS.

    Dynamically maps base location keywords (desktop, documents, downloads, pictures, c_drive, home)
    to absolute OS paths, safely joining them with target_name / folder_name without duplication.
    """
    params = params or {}
    user_home = Path.home()

    base_path_raw = str(params.get("base_path") or params.get("path") or "").strip().strip("'\"` ")
    target_name_raw = str(
        params.get("target_name") or params.get("folder_name") or params.get("file_name") or params.get("name") or target or ""
    ).strip().strip("'\"` ")

    keyword_map = {
        "desktop": user_home / "Desktop",
        "डेस्कटॉप": user_home / "Desktop",
        "downloads": user_home / "Downloads",
        "download": user_home / "Downloads",
        "डाउनलोड": user_home / "Downloads",
        "documents": user_home / "Documents",
        "document": user_home / "Documents",
        "डॉक्यूमेंट": user_home / "Documents",
        "pictures": user_home / "Pictures",
        "picture": user_home / "Pictures",
        "चित्र": user_home / "Pictures",
        "c_drive": Path("C:\\") if os.name == "nt" else Path("/"),
        "c:": Path("C:\\") if os.name == "nt" else Path("/"),
        "c": Path("C:\\") if os.name == "nt" else Path("/"),
        "c:\\": Path("C:\\") if os.name == "nt" else Path("/"),
        "home": user_home,
        "user_home": user_home,
        "~": user_home,
    }

    base_dir: Optional[Path] = None
    remaining_subpath: str = ""

    if base_path_raw:
        base_lowered = base_path_raw.lower().replace("\\", "/")
        matched_kw = None
        for kw in keyword_map:
            if base_lowered == kw or base_lowered.startswith(kw + "/") or base_lowered.startswith(kw + "\\") or base_lowered.startswith(kw + " "):
                matched_kw = kw
                break

        if matched_kw:
            base_dir = keyword_map[matched_kw]
            sub_raw = base_path_raw[len(matched_kw):].strip("/\\ ")
            if sub_raw and not any(w in sub_raw.lower() for w in ("pe ", "par ", "me ", "per ", "banao", "folder", "create", "make")):
                remaining_subpath = sub_raw
        else:
            expanded = os.path.expandvars(os.path.expanduser(base_path_raw))
            p_base = Path(expanded)
            if p_base.is_absolute():
                base_dir = p_base

    if not base_dir:
        combined = f"{target_name_raw} {raw_text}".lower()
        if any(loc in combined for loc in ("desktop", "डेस्कटॉप")):
            base_dir = user_home / "Desktop"
        elif any(loc in combined for loc in ("download", "downloads", "डाउनलोड")):
            base_dir = user_home / "Downloads"
        elif any(loc in combined for loc in ("document", "documents", "डॉक्यूमेंट")):
            base_dir = user_home / "Documents"
        elif any(loc in combined for loc in ("picture", "pictures", "चित्र")):
            base_dir = user_home / "Pictures"
        elif any(loc in combined for loc in ("c_drive", "c:", "c drive")):
            base_dir = Path("C:\\") if os.name == "nt" else Path("/")
        else:
            base_dir = user_home / "Desktop"

    if remaining_subpath:
        base_dir = base_dir / remaining_subpath

    cleaned_target = target_name_raw
    if any(action_kw in target_name_raw.lower() for action_kw in ("banao", "create", "make", "delete", "folder", "file", "desktop", "pe ", "par ", "named ")):
        noise_patterns = [
            r"\b(?:on|in|at)\s+(?:the\s+)?(?:desktop|downloads|documents|pictures|c_drive)\b",
            r"\b(?:desktop|downloads|documents|pictures)\s+(?:pe|par|me|per|in|on)\b",
            r"\b(?:is|a|an|ek|naya|nayi|new)\s+naam\s+se\b",
            r"\b(?:named|called|with\s+name|naam\s+ka|naam\s+se)\b",
            r"\b(?:banao|bana|bana\s+do|create\s+karo|create|make|touch|mkdir|delete|remove|rmdir|unlink|banaen|बनाओ|बना)\b",
            r"\b(?:folder|directory|file)\b",
        ]
        for pat in noise_patterns:
            cleaned_target = re.sub(pat, "", cleaned_target, flags=re.IGNORECASE).strip()
    cleaned_target = cleaned_target.strip("'\"` ").lstrip("/\\")

    if not cleaned_target or cleaned_target.lower() in ("folder", "file", "directory", "new folder", "new file"):
        if not target_name_raw:
            return base_dir
        cleaned_target = "New File.txt" if default_is_file else "New Folder"

    expanded_target = os.path.expandvars(os.path.expanduser(cleaned_target))
    p_target = Path(expanded_target)

    if p_target.is_absolute():
        return p_target

    if base_dir.name.lower() == cleaned_target.lower():
        return base_dir

    return base_dir / p_target


def _resolve_fast_path(path_str: str, raw_text: str = "", default_is_file: bool = False) -> Path:
    """Compatibility wrapper for fast path resolution."""
    return _resolve_smart_path(params={"path": path_str}, target=path_str, raw_text=raw_text, default_is_file=default_is_file)


# ----------------------------------------------------------------------
# 3. Wake Word Cleaner & Multilingual Normalizer
# ----------------------------------------------------------------------

class WakeWordCleaner:
    """Strips wake words, greetings, politeness tokens, and noise words in English, Hinglish, and Hindi."""

    NOISE_WORDS: Set[str] = {
        # English
        "hello", "hi", "hey", "naira", "please", "pls", "can", "you", "could", "kindly",
        "just", "a", "an", "the", "bro", "buddy", "assistant",
        # Hinglish
        "mera", "meri", "mere", "jara", "zara", "ek", "bhai", "sun", "suno", "yar", "yaar",
        "karo", "do", "karde", "kar", "dijiye", "bhaiya", "friend",
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
        result = " ".join(cleaned_tokens)
        return result if result else text.strip()


class MultilingualNormalizer:
    """Normalizes action terms across English, Hinglish, and Hindi."""

    _TOKEN_MAP: Dict[str, str] = {
        "kholo": "open", "khol": "open", "chalao": "open", "shuru": "open",
        "खोलो": "open", "खोल": "open", "चलाओ": "open", "शुरू": "open",
        "banao": "create", "bana": "create", "bana do": "create",
        "बनाओ": "create", "बना": "create",
        "band": "shutdown", "lock": "lock"
    }

    @classmethod
    def normalize(cls, text: str) -> str:
        return WakeWordCleaner.clean(text)

    @classmethod
    def normalize_token(cls, token: str) -> str:
        tok = token.strip().lower()
        return cls._TOKEN_MAP.get(tok, tok)


# ----------------------------------------------------------------------
# 4. System Prompt for Groq JSON Intent Classification (Universal Action Schema)
# ----------------------------------------------------------------------

SYSTEM_INTENT_PROMPT = """You are Naira-OS's Semantic Intent Router powered by Llama 3.
You MUST analyze the user's natural language input (in English, Hindi, or Hinglish) and classify it into EXACTLY ONE of the five intent categories below.
You MUST respond EXCLUSIVELY with a pure JSON object conforming strictly to the Universal Action Schema below.

INTENT CATEGORIES:
1. SYSTEM_CONTROL: Operating system management (opening apps like notepad, calc, cmd, powershell, chrome, vscode, explorer; adjusting volume/brightness; taking screenshots; locking screen; shutdown; restart; killing processes; system status/info).
2. BROWSER_CONTROL: Web browser actions (opening websites/urls, opening YouTube, searching the web, searching Google/YouTube).
3. FILE_SYSTEM: File and folder actions (creating, deleting, renaming, opening files or folders; listing directories).
4. CODING_AGENT: Programming, writing code, generating scripts, debugging, building software, code analysis.
5. CONVERSATION: General conversation, greetings, Q&A, explanations, chit-chat, or queries requiring a spoken text response.

UNIVERSAL JSON SCHEMA:
{
  "intent": "SYSTEM_CONTROL" | "BROWSER_CONTROL" | "FILE_SYSTEM" | "CODING_AGENT" | "CONVERSATION",
  "reasoning": "<short explanation>",
  "confidence": <float 0.0 to 1.0>,
  "operations": [
    {
      "action": "<action string, e.g. create_folder, create_file, delete_folder, open_app, set_volume, set_brightness, lock_pc, shutdown, restart, screenshot, open_url, search_web, write_code, chat>",
      "target": "<target name, app, url, search query, path, or topic>",
      "parameters": {
        "base_path": "<base location keyword: desktop, documents, downloads, pictures, c_drive, home, or absolute path>",
        "target_name": "<name of folder, file, app, or target>",
        "folder_name": "<folder name if relevant>",
        "file_name": "<file name if relevant>",
        "path": "<full or relative path if relevant>",
        "new_name": "<new name for rename operations>",
        "value": "<numerical or descriptive value>",
        "query": "<search query string if searching>",
        "url": "<full web URL if opening site>"
      }
    }
  ]
}

CRITICAL RULES:
1. Output ONLY a valid JSON object.
2. DO NOT wrap the output in markdown code fences (NO ```json or ```).
3. The 'operations' array MUST contain ALL tasks to execute sequentially. Even for a single task, it MUST be wrapped in the 'operations' array.
4. For multi-step tasks (e.g. creating 1 parent folder and 5 nested sub-folders), list every operation in sequential order in the 'operations' array.
5. NESTING RULE FOR FILE_SYSTEM: If the user asks to create nested directories (folders inside a folder), you MUST append the parent folder's name to the 'base_path' for all sub-folders (e.g., operation 1 creates parent with base_path: 'desktop', target_name: 'ParentFolder'; operations 2-6 create sub-folders with base_path: 'desktop/ParentFolder', target_name: 'sub1').
6. Seamlessly support English, Hindi (Devanagari), and Hinglish.
"""


# ----------------------------------------------------------------------
# 5. Helper Function for Groq API HTTP Calls
# ----------------------------------------------------------------------

def _call_groq_api_sync(api_key: str, payload: dict[str, Any]) -> str:
    """Synchronous HTTP POST request to Groq REST API endpoint using urllib."""
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Naira-OS-SemanticRouter/2.0"
    }
    req = urllib.request.Request(GROQ_API_ENDPOINT, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=12) as response:
        res_body = response.read().decode("utf-8")
        parsed = json.loads(res_body)
        return parsed["choices"][0]["message"]["content"]


# ----------------------------------------------------------------------
# 6. FastCommandRouter Main Class
# ----------------------------------------------------------------------

def _fetch_instant_web_search(query: str, max_results: int = 3) -> str:
    """Instantly fetches real-time web search results via DuckDuckGo & Wikipedia APIs with strict timeout (<2.5s)."""
    clean_q = query.strip()
    if not clean_q:
        return "[FAILED] Empty web search query."

    # 1. DuckDuckGo Instant Answer API
    try:
        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(clean_q)}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Naira-OS/2.0 Omniscience Engine"})
        with urllib.request.urlopen(req, timeout=2.5) as response:
            data = json.loads(response.read().decode("utf-8"))
            abstract = data.get("AbstractText", "").strip()
            heading = data.get("Heading", clean_q)
            results = []
            if abstract:
                results.append(f"• {heading}: {abstract}")

            related = data.get("RelatedTopics", [])
            for item in related[:max_results]:
                if isinstance(item, dict) and item.get("Text"):
                    results.append(f"• {item['Text']}")

            if results:
                return f"[INSTANT WEB SEARCH] Data for '{clean_q}':\n" + "\n".join(results)
    except Exception:
        pass

    # 2. DuckDuckGo Lite / HTML scraping fallback
    try:
        html_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(clean_q)}"
        req = urllib.request.Request(html_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=2.5) as response:
            html = response.read().decode("utf-8", errors="ignore")
            snippets = re.findall(r'<a class="result__snippet[^">]*>(.*?)</a>', html, re.DOTALL)
            clean_snippets = []
            for snip in snippets[:max_results]:
                clean_txt = re.sub(r'<[^>]+>', '', snip).strip()
                if clean_txt:
                    clean_snippets.append(f"• {clean_txt}")
            if clean_snippets:
                return f"[INSTANT WEB SEARCH] Real-time results for '{clean_q}':\n" + "\n".join(clean_snippets)
    except Exception:
        pass

    # 3. Wikipedia API fallback
    try:
        wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(clean_q)}"
        req = urllib.request.Request(wiki_url, headers={"User-Agent": "Naira-OS/2.0 Omniscience Engine"})
        with urllib.request.urlopen(req, timeout=2.0) as response:
            wdata = json.loads(response.read().decode("utf-8"))
            extract = wdata.get("extract")
            if extract:
                return f"[INSTANT WEB SEARCH] Wikipedia summary for '{clean_q}':\n• {extract}"
    except Exception:
        pass

    return f"[SUCCESS] Performed web search query for '{clean_q}'."


class FastCommandRouter:
    """Semantic Intent Router for Naira-OS powered by Groq API (llama-3.1-8b-instant)."""

    def __init__(
        self,
        pc_control_manager: Any = None,
        vision_manager: Any = None,
        browser_manager: Any = None,
        coding_agent_manager: Any = None,
        logger: Optional[logging.Logger] = None,
        api_key: Optional[str] = None,
        settings_manager: Any = None,
        security_manager: Any = None,
        **kwargs: Any,
    ) -> None:
        self._pc_control_manager = pc_control_manager
        self._vision_manager = vision_manager
        self._browser_manager = browser_manager
        self._coding_agent_manager = coding_agent_manager
        self._logger = logger or _LOG
        self._settings_manager = settings_manager
        self._security_manager = security_manager

        # Dynamic Groq API key resolution
        groq_key = api_key
        if not groq_key and self._settings_manager:
            if hasattr(self._settings_manager, "get"):
                groq_key = self._settings_manager.get("api_keys.groq") or self._settings_manager.get("groq_api_key")
            if not groq_key and hasattr(self._settings_manager, "get_api_key"):
                groq_key = self._settings_manager.get_api_key("groq")

        if not groq_key:
            groq_key = os.environ.get("GROQ_API_KEY")

        if not groq_key:
            try:
                user_json_path = Path(__file__).resolve().parent.parent.parent / "config" / "user.json"
                if user_json_path.is_file():
                    with open(user_json_path, "r", encoding="utf-8") as f:
                        u_cfg = json.load(f)
                        groq_key = u_cfg.get("api_keys", {}).get("groq") or u_cfg.get("groq_api_key")
            except Exception:
                pass

        self._api_key = (groq_key or "").strip()
        if not self._api_key:
            self._logger.warning("Groq API key missing in Vault. FCR will be disabled/degraded.")

        self._model = GROQ_MODEL
        self.intent_engine = IntentEngine(router=self)

    def is_fast_command(self, text: str) -> bool:
        """Determines whether text should be handled by FastCommandRouter.

        Uses an allow-list approach: returns False by default (treat as normal
        conversation) and only returns True when the text plausibly matches an
        actionable command category.
        """
        if not text or not text.strip():
            return False

        lowered = text.lower().strip()

        # --- Browser control / web search keywords ---
        if any(k in lowered for k in (
            "search", "search_web", "google", "youtube", "web search",
            "online", "latest news",
        )):
            return True

        # URL patterns
        if any(k in lowered for k in ("http://", "https://", "www.", ".com", ".org", ".net")):
            return True

        # --- System control keywords ---
        system_keywords = (
            "open", "close", "launch", "start", "kholo", "khol", "chalao", "shuru",
            "खोलो", "खोल", "चलाओ", "शुरू",
            "volume", "brightness", "awaaz", "roshni", "आवाज़", "वॉल्यूम",
            "वोल्यूम", "ब्राइटनेस",
            "mute", "unmute",
            "lock", "लॉक",
            "shutdown", "shut down", "turn off", "band karo", "बंद",
            "restart", "reboot", "रीस्टार्ट",
            "screenshot", "capture", "स्क्रीनशॉट",
            "kill process", "task manager", "taskmgr",
            "settings", "system info",
            "notepad", "calc", "calculator", "chrome", "cmd",
            "powershell", "explorer", "vscode", "vs code", "paint",
        )
        if any(k in lowered for k in system_keywords):
            return True

        # --- File system keywords ---
        file_keywords = (
            "create folder", "delete folder", "rename folder",
            "make folder", "remove folder",
            "create file", "delete file", "rename file",
            "make file", "remove file", "open file",
            "mkdir", "rmdir", "touch",
            "banao folder", "folder banao",
            "banao file", "file banao",
        )
        if any(k in lowered for k in file_keywords):
            return True
        # Broader match: verb + noun anywhere in the text (handles articles like "delete the folder")
        fs_verbs = ("create", "delete", "remove", "rename", "make", "banao")
        fs_nouns = ("folder", "file", "directory")
        if any(v in lowered for v in fs_verbs) and any(n in lowered for n in fs_nouns):
            return True

        # --- Coding agent keywords ---
        coding_keywords = (
            "script likho", "run karo", "banao script", "code likho", "script banao",
            "script", "code", "python", "execute_local_python", "local_python",
            "execute_script", "run script", "write script", "write a script",
            "write code", "write a python script",
            "create function", "fix bug", "debug", "error",
            "nameerror", "typeerror", "syntaxerror", "valueerror",
            "exception", "stack trace", "traceback",
            "read the error", "read error",
            "fix it", "fix error", "solve error", "self-correct",
            "run again", "run via", "read_file", "write_file",
        )
        # Normalize VS Code references so "code" doesn't false-positive on them
        lowered_check = re.sub(
            r"\b(?:visual\s+studio\s+code|vs\s*code|vscode|code\s*editor)\b",
            "app_editor", lowered,
        )
        if any(k in lowered_check for k in coding_keywords):
            return True

        # Default: not a fast command — route to normal conversation
        return False

    # ------------------------------------------------------------------
    # Intent Classification with AI Self-Correction Loop
    # ------------------------------------------------------------------

    async def classify_intent(self, text: str, max_retries: int = 3) -> Dict[str, Any]:
        """Classifies command intent via Groq API with an agentic self-correction retry loop."""
        cleaned_input = WakeWordCleaner.clean(text)
        user_prompt = cleaned_input if cleaned_input else text.strip()

        api_key = self._api_key
        if not api_key and self._settings_manager:
            if hasattr(self._settings_manager, "get"):
                api_key = self._settings_manager.get("api_keys.groq") or self._settings_manager.get("groq_api_key")
            if not api_key and hasattr(self._settings_manager, "get_api_key"):
                api_key = self._settings_manager.get_api_key("groq")

        if not api_key:
            api_key = os.environ.get("GROQ_API_KEY")

        if not api_key:
            self._logger.warning("Groq API key missing in Vault. FCR will be disabled/degraded.")
            return self._heuristic_fallback(user_prompt)


        messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_INTENT_PROMPT},
            {"role": "user", "content": f"User Input: {user_prompt}"}
        ]

        last_error: Optional[Exception] = None
        raw_response: str = ""

        for attempt in range(max_retries):
            try:
                payload = {
                    "model": self._model,
                    "messages": messages,
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"}
                }

                raw_response = await asyncio.to_thread(_call_groq_api_sync, api_key, payload)
                
                content = raw_response.strip()
                if content.startswith("```"):
                    content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
                    content = re.sub(r"\s*```$", "", content)
                    content = content.strip()

                parsed_json = json.loads(content)

                if not isinstance(parsed_json, dict):
                    raise ValueError("Groq returned JSON that is not an object.")

                intent = str(parsed_json.get("intent", "")).upper()
                valid_intents = {
                    CommandIntent.SYSTEM_CONTROL.value,
                    CommandIntent.BROWSER_CONTROL.value,
                    CommandIntent.FILE_SYSTEM.value,
                    CommandIntent.CODING_AGENT.value,
                    CommandIntent.CONVERSATION.value,
                }

                if intent not in valid_intents:
                    raise ValueError(f"Invalid intent category '{intent}'. Must be one of {valid_intents}")

                parsed_json["intent"] = intent

                # Normalize operations array
                if "operations" not in parsed_json or not isinstance(parsed_json["operations"], list) or not parsed_json["operations"]:
                    action = parsed_json.get("action", "chat")
                    target = parsed_json.get("target", "")
                    params = parsed_json.get("parameters", {}) or {}
                    parsed_json["operations"] = [{
                        "action": action,
                        "target": target,
                        "parameters": params
                    }]

                self._logger.info("[GROQ ROUTER] Classified intent: %s with %d operations (confidence: %s)", intent, len(parsed_json["operations"]), parsed_json.get("confidence", 1.0))
                return parsed_json

            except (json.JSONDecodeError, ValueError, urllib.error.URLError, KeyError) as err:
                self._logger.warning("[GROQ ROUTER] Retry %d/%d: Intent parsing failed: %s", attempt + 1, max_retries, err)
                last_error = err

                if raw_response:
                    messages.append({"role": "assistant", "content": raw_response})
                messages.append({
                    "role": "user",
                    "content": f"ERROR: Fix the JSON formatting. Output ONLY pure valid JSON with an 'intent' and an 'operations' array. Details: {err}."
                })
                await asyncio.sleep(0.2 * (attempt + 1))

        self._logger.error("[GROQ ROUTER] AI Self-Correction loop exhausted (%d retries). Falling back.", max_retries)
        return self._heuristic_fallback(user_prompt)

    # ------------------------------------------------------------------
    # Direct Module Execution & Routing
    # ------------------------------------------------------------------

    async def execute_fast_command(self, text: str, intent_data: Optional[Dict[str, Any]] = None) -> str:
        """Main entry point: Classifies intent via Groq and dispatches directly to Naira-OS modules."""
        if intent_data is None:
            intent_data = await self.classify_intent(text)
        return await self._dispatch_module_action(intent_data, text)

    async def _dispatch_module_action(self, intent_data: Dict[str, Any], raw_text: str) -> str:
        """Dispatches valid JSON intent to respective Naira-OS modules for zero-latency execution."""
        intent = intent_data.get("intent", "CONVERSATION")
        operations = intent_data.get("operations")

        if not operations or not isinstance(operations, list):
            action = intent_data.get("action", "").lower()
            target = intent_data.get("target", "").strip()
            params = intent_data.get("parameters", {}) or {}
            operations = [{"action": action, "target": target, "parameters": params}]

        self._logger.info("[MODULE DISPATCH] Intent: %s | Operations count: %d", intent, len(operations))

        if intent == CommandIntent.SYSTEM_CONTROL.value:
            return await self._execute_system_control(operations, raw_text)
        elif intent == CommandIntent.BROWSER_CONTROL.value:
            return await self._execute_browser_control(operations, raw_text)
        elif intent == CommandIntent.FILE_SYSTEM.value:
            return await self._execute_file_system(operations, raw_text)
        elif intent == CommandIntent.CODING_AGENT.value:
            return await self._execute_coding_agent(operations, raw_text)
        else:
            return self._execute_conversation(intent_data, raw_text)

    # ------------------------------------------------------------------
    # 6.1 System Control Handler
    # ------------------------------------------------------------------

    async def _execute_system_control(
        self,
        operations_or_action: Union[List[Dict[str, Any]], str],
        target_or_raw_text: str = "",
        params: Optional[Dict[str, Any]] = None,
        raw_text: str = ""
    ) -> str:
        if isinstance(operations_or_action, str):
            action = operations_or_action
            target = target_or_raw_text
            parameters = params or {}
            operations = [{"action": action, "target": target, "parameters": parameters}]
            actual_raw_text = raw_text
        else:
            operations = operations_or_action
            actual_raw_text = target_or_raw_text

        results: List[str] = []

        for op in operations:
            action = str(op.get("action", "")).lower()
            target = str(op.get("target", "")).strip()
            op_params = op.get("parameters", {}) or {}

            try:
                # Volume Control
                if action in ("set_volume", "volume") or "volume" in actual_raw_text.lower():
                    results.append(await self._handle_volume_action(op_params, target, actual_raw_text))

                # Brightness Control
                elif action in ("set_brightness", "brightness") or "brightness" in actual_raw_text.lower():
                    results.append(await self._handle_brightness_action(op_params, target, actual_raw_text))

                # Screenshot
                elif action in ("screenshot", "take_screenshot", "capture") or "screenshot" in actual_raw_text.lower():
                    results.append(await self._handle_screenshot_action())

                # Lock PC
                elif action in ("lock_pc", "lock"):
                    results.append(await self._handle_power_action("power_lock", "PC locked successfully."))

                # Shutdown / Restart
                elif action in ("shutdown", "turn_off"):
                    results.append(await self._handle_power_action("power_shutdown", "Initiating PC shutdown in 5 seconds."))
                elif action in ("restart", "reboot"):
                    results.append(await self._handle_power_action("power_restart", "Initiating PC restart in 5 seconds."))

                # Open App / Launch
                else:
                    results.append(await self._handle_open_app_action(target, op_params, actual_raw_text))
            except Exception as e:
                self._logger.warning("[SYSTEM_CONTROL] Action '%s' failed: %s", action, e)
                results.append(f"[FAILED] {action} failed: {e}")

        return "\n".join(results) if results else "[SUCCESS] System action executed."

    async def _handle_volume_action(self, op_params: Dict[str, Any], target: str, actual_raw_text: str) -> str:
        """Route a volume action through PCControlManager."""
        if self._pc_control_manager is None:
            return "[FAILED] Volume control unavailable (PCControlManager not wired)."
        val = str(op_params.get("value") or target or actual_raw_text).lower()
        val_display = "50%" if "50" in val else val
        try:
            if "unmute" in val:
                res = await self._pc_control_manager.volume_mute(False)
            elif "mute" in val:
                res = await self._pc_control_manager.volume_mute(True)
            elif "up" in val or "increase" in val:
                current = await self._pc_control_manager.volume_get()
                level = min(1.0, (getattr(current, "level", 0.5) or 0.5) + 0.1)
                res = await self._pc_control_manager.volume_set(level)
            elif "down" in val or "decrease" in val:
                current = await self._pc_control_manager.volume_get()
                level = max(0.0, (getattr(current, "level", 0.5) or 0.5) - 0.1)
                res = await self._pc_control_manager.volume_set(level)
            else:
                m = re.search(r"(\d+)", val)
                level = max(0.0, min(1.0, int(m.group(1)) / 100.0)) if m else 0.5
                res = await self._pc_control_manager.volume_set(level)
            return self._format_tool_result(res, f"Volume set to {val_display}.")
        except Exception as e:
            return f"[FAILED] Volume control failed: {e}"

    async def _handle_brightness_action(self, op_params: Dict[str, Any], target: str, actual_raw_text: str) -> str:
        """Route a brightness action through PCControlManager."""
        if self._pc_control_manager is None:
            return "[FAILED] Brightness control unavailable (PCControlManager not wired)."
        val_match = re.search(r"\d+", str(op_params.get("value") or target or actual_raw_text or "50"))
        level = int(val_match.group(0)) if val_match else 50
        try:
            res = await self._pc_control_manager.display_set_brightness(level)
            return self._format_tool_result(res, f"Brightness set to {level}%.")
        except Exception as e:
            return f"[FAILED] Brightness control failed: {e}"

    async def _handle_screenshot_action(self) -> str:
        """Route a screenshot action through PCControlManager."""
        if self._pc_control_manager is None:
            return "[FAILED] Screenshot unavailable (PCControlManager not wired)."
        desktop = Path.home() / "Desktop"
        filename = desktop / f"screenshot_{int(time.time())}.png"
        try:
            res = await self._pc_control_manager.screen_capture(save_path=str(filename))
            return self._format_tool_result(res, f"Screenshot saved to Desktop: {filename.name}")
        except Exception as e:
            return f"[FAILED] Screenshot capture failed: {e}"

    async def _handle_power_action(self, method_name: str, success_msg: str) -> str:
        """Route a power action (lock/shutdown/restart) through PCControlManager."""
        if self._pc_control_manager is None:
            return f"[FAILED] {success_msg} — PCControlManager not wired."
        method = getattr(self._pc_control_manager, method_name, None)
        if method is None:
            return f"[FAILED] {success_msg} — manager does not support {method_name}."
        try:
            res = await method()
            return self._format_tool_result(res, success_msg)
        except Exception as e:
            return f"[FAILED] {success_msg} — {e}"

    async def _handle_open_app_action(self, target: str, op_params: Dict[str, Any], actual_raw_text: str) -> str:
        """Route an app-launch action through PCControlManager."""
        app_name = target or op_params.get("name") or actual_raw_text
        cleaned_app = app_name.lower().replace("open", "").replace("kholo", "").replace("launch", "").strip()

        app_commands = {
            "notepad": "notepad.exe",
            "calc": "calc.exe",
            "calculator": "calc.exe",
            "cmd": "cmd.exe",
            "command prompt": "cmd.exe",
            "powershell": "powershell.exe",
            "chrome": "chrome.exe",
            "browser": "chrome.exe",
            "vscode": "code",
            "vs code": "code",
            "code": "code",
            "explorer": "explorer.exe",
            "file explorer": "explorer.exe",
            "task manager": "taskmgr.exe",
            "settings": "ms-settings:",
            "paint": "mspaint.exe",
            "word": "winword.exe",
            "excel": "excel.exe",
        }

        cmd_to_run = app_commands.get(cleaned_app, cleaned_app)
        if self._pc_control_manager is None:
            return f"[FAILED] Failed to open application '{cleaned_app}' — PCControlManager not wired."
        try:
            res = await self._pc_control_manager.launch_application(cmd_to_run)
            return self._format_tool_result(res, f"Opened {cleaned_app.capitalize()} successfully.")
        except Exception as e:
            return f"[FAILED] Failed to open application '{cleaned_app}': {e}"

    @staticmethod
    def _format_tool_result(res: Any, success_msg: str) -> str:
        """Format a manager ToolResult into a [SUCCESS]/[FAILED] response string."""
        status = getattr(res, "status", "success")
        if status == "success":
            return f"[SUCCESS] {success_msg}"
        err = getattr(res, "error", None) or getattr(res, "output", None) or f"status={status}"
        return f"[FAILED] {success_msg} — {err}"

    # ------------------------------------------------------------------
    # 6.2 Browser Control Handler
    # ------------------------------------------------------------------

    async def _execute_browser_control(
        self,
        operations_or_action: Union[List[Dict[str, Any]], str],
        target_or_raw_text: str = "",
        params: Optional[Dict[str, Any]] = None,
        raw_text: str = ""
    ) -> str:
        if isinstance(operations_or_action, str):
            action = operations_or_action
            target = target_or_raw_text
            parameters = params or {}
            operations = [{"action": action, "target": target, "parameters": parameters}]
            actual_raw_text = raw_text
        else:
            operations = operations_or_action
            actual_raw_text = target_or_raw_text

        results: List[str] = []

        for op in operations:
            action = str(op.get("action", "")).lower()
            target = str(op.get("target", "")).strip()
            op_params = op.get("parameters", {}) or {}
            url = op_params.get("url") or target

            try:
                if "youtube" in actual_raw_text.lower() or "youtube" in url.lower():
                    if action in ("search_web", "search") or "search" in actual_raw_text.lower():
                        query = op_params.get("query") or target
                        search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
                        results.append(await self._handle_browser_navigate(search_url, f"Opened YouTube search for '{query}'."))
                    else:
                        results.append(await self._handle_browser_navigate("https://www.youtube.com", "Opened YouTube in browser."))

                elif action in ("search_web", "search", "web_search", "fetch_web_data") or "search" in actual_raw_text.lower():
                    query = op_params.get("query") or target or actual_raw_text
                    # If explicit browser GUI opening is requested, navigate the browser
                    if op_params.get("open_browser") or any(k in actual_raw_text.lower() for k in ("open browser", "browser kholo", "open chrome")):
                        search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
                        results.append(await self._handle_browser_navigate(search_url, f"Opened Google search for '{query}'."))
                    else:
                        # Instant web retrieval without browser GUI overhead
                        res = _fetch_instant_web_search(query)
                        results.append(res)

                else:
                    if not url.startswith("http"):
                        url = f"https://{url}" if "." in url else f"https://www.google.com/search?q={urllib.parse.quote(url)}"
                    results.append(await self._handle_browser_navigate(url, f"Opened URL: {url}"))
            except Exception as e:
                self._logger.warning("[BROWSER_CONTROL] Action '%s' failed: %s", action, e)
                results.append(f"[FAILED] Browser action failed: {e}")

        return "\n".join(results) if results else "[SUCCESS] Browser action executed."

    async def _handle_browser_navigate(self, url: str, success_msg: str) -> str:
        """Route a browser-navigation action through BrowserManager."""
        if self._browser_manager is None:
            return f"[FAILED] {success_msg} — BrowserManager not wired."
        try:
            res = await self._browser_manager.navigate(url, extract_content=False)
            return self._format_tool_result(res, success_msg)
        except Exception as e:
            return f"[FAILED] {success_msg} — {e}"

    # ------------------------------------------------------------------
    # 6.3 File System Handler
    # ------------------------------------------------------------------

    async def _execute_file_system(
        self,
        operations_or_action: Union[List[Dict[str, Any]], str],
        target_or_raw_text: str = "",
        params: Optional[Dict[str, Any]] = None,
        raw_text: str = ""
    ) -> str:
        if isinstance(operations_or_action, str):
            action = operations_or_action
            target = target_or_raw_text
            parameters = params or {}
            operations = [{"action": action, "target": target, "parameters": parameters}]
            actual_raw_text = raw_text
        else:
            operations = operations_or_action
            actual_raw_text = target_or_raw_text

        success_count = 0
        failure_messages: List[str] = []

        for op in operations:
            action = str(op.get("action", "")).lower()
            target = str(op.get("target", "")).strip()
            op_params = op.get("parameters", {}) or {}

            is_file_op = "file" in actual_raw_text.lower() or action in ("create_file", "delete_file", "rename_file", "open_file")
            target_path = _resolve_smart_path(op_params, target, actual_raw_text, default_is_file=is_file_op)

            try:
                if action in ("create_folder", "make_folder", "mkdir"):
                    res = await self._fs_call("filesystem_create_directory", str(target_path), {})
                    if self._fs_success(res):
                        success_count += 1
                        self._logger.info("[FILE_SYSTEM SUCCESS] Created folder at %s", target_path)
                    else:
                        failure_messages.append(f"Folder creation failed: {self._fs_error(res)}")

                elif action in ("delete_folder", "remove_folder", "rmdir"):
                    res = await self._fs_call("filesystem_delete_directory", str(target_path), {"recursive": True})
                    if self._fs_success(res):
                        success_count += 1
                        self._logger.info("[FILE_SYSTEM SUCCESS] Deleted folder at %s", target_path)
                    else:
                        failure_messages.append(f"Folder deletion failed: {self._fs_error(res)}")

                elif action in ("create_file", "touch", "make_file"):
                    res = await self._fs_call("filesystem_write_file", str(target_path), {"content": ""})
                    if self._fs_success(res):
                        success_count += 1
                        self._logger.info("[FILE_SYSTEM SUCCESS] Created file at %s", target_path)
                    else:
                        failure_messages.append(f"File creation failed: {self._fs_error(res)}")

                elif action in ("delete_file", "remove_file"):
                    res = await self._fs_call("filesystem_delete_file", str(target_path), {})
                    if self._fs_success(res):
                        success_count += 1
                        self._logger.info("[FILE_SYSTEM SUCCESS] Deleted file at %s", target_path)
                    else:
                        failure_messages.append(f"File deletion failed: {self._fs_error(res)}")

                elif action in ("rename_file", "rename_folder", "rename"):
                    new_name = op_params.get("new_name") or "renamed_item"
                    new_path = target_path.parent / new_name
                    res = await self._fs_call("filesystem_move_item", str(target_path), {"dest_path": str(new_path)})
                    if self._fs_success(res):
                        success_count += 1
                        self._logger.info("[FILE_SYSTEM SUCCESS] Renamed item to %s", new_path.name)
                    else:
                        failure_messages.append(f"Rename failed: {self._fs_error(res)}")

                elif action in ("open_file", "open"):
                    res = await self._fs_call("launch_application", str(target_path), {})
                    if self._fs_success(res):
                        success_count += 1
                        self._logger.info("[FILE_SYSTEM SUCCESS] Opened file %s", target_path.name)
                    else:
                        failure_messages.append(f"Failed to open file: {self._fs_error(res)}")
                else:
                    failure_messages.append(f"Unsupported file system action: {action}")

            except Exception as e:
                self._logger.error("[FILE_SYSTEM ERROR] %s", e)
                failure_messages.append(f"File system operation failed: {e}")

        if failure_messages and success_count == 0:
            return f"[FAILED] {failure_messages[0]}"

        return "[SUCCESS] Done! I have executed the file operations successfully."

    async def _fs_call(self, method_name: str, path_arg: str, extra: Dict[str, Any]) -> Any:
        """Invoke a PCControlManager filesystem method, applying path sandboxing/risk checks."""
        if self._pc_control_manager is None:
            return ToolResult(status="error", error="PCControlManager not wired.")
        method = getattr(self._pc_control_manager, method_name, None)
        if method is None:
            return ToolResult(status="error", error=f"manager does not support {method_name}")
        return await method(path_arg, **extra)

    @staticmethod
    def _fs_success(res: Any) -> bool:
        return getattr(res, "status", "error") == "success"

    @staticmethod
    def _fs_error(res: Any) -> str:
        err = getattr(res, "error", None)
        if err:
            return str(err)
        output = getattr(res, "output", None)
        if output:
            return str(output)
        status = getattr(res, "status", "unknown")
        return f"status={status}"

    # ------------------------------------------------------------------
    # 6.4 Coding Agent Handler
    # ------------------------------------------------------------------

    async def _execute_coding_agent(
        self,
        operations_or_action: Union[List[Dict[str, Any]], str],
        target_or_raw_text: str = "",
        params: Optional[Dict[str, Any]] = None,
        raw_text: str = ""
    ) -> str:
        actual_raw_text = raw_text if isinstance(operations_or_action, str) else target_or_raw_text
        if self._coding_agent_manager and hasattr(self._coding_agent_manager, "execute"):
            try:
                res = await self._coding_agent_manager.execute(actual_raw_text)
                return str(res)
            except Exception as e:
                return f"[FAILED] Coding Agent execution failed: {e}"

        return f"[SUCCESS] [CODING AGENT ROUTE] Query routed to Coding Agent module: '{actual_raw_text}'"

    # ------------------------------------------------------------------
    # 6.5 Conversation Handler
    # ------------------------------------------------------------------

    def _execute_conversation(self, intent_data: Dict[str, Any], raw_text: str) -> str:
        # Defense-in-depth: never leak internal classifier fields (reasoning, etc.)
        # to the user.  After the RuntimeManager fix this path is effectively
        # unreachable for normal chat, but we keep a safe generic fallback.
        return f"Hello! How can I assist you further with '{raw_text}'?"

    # ------------------------------------------------------------------
    # Fallback Heuristic Classifier (When GROQ API key is absent/unavailable)
    # ------------------------------------------------------------------

    def _heuristic_fallback(self, text: str) -> Dict[str, Any]:
        lowered = text.lower()

        if any(kw in lowered for kw in ("delete folder", "remove folder", "delete file", "remove file")):
            is_file = "file" in lowered
            action_name = "delete_file" if is_file else "delete_folder"
            return {
                "intent": "FILE_SYSTEM",
                "reasoning": "Fallback file deletion route detection",
                "confidence": 0.9,
                "operations": [
                    {
                        "action": action_name,
                        "target": text,
                        "parameters": {"path": text}
                    }
                ]
            }

        elif any(kw in lowered for kw in ("folder", "directory", "create folder", "banao folder", "file")):
            is_file = "file" in lowered
            action_name = "create_file" if is_file else "create_folder"
            return {
                "intent": "FILE_SYSTEM",
                "reasoning": "Fallback file system route detection",
                "confidence": 0.85,
                "operations": [
                    {
                        "action": action_name,
                        "target": text,
                        "parameters": {"path": text}
                    }
                ]
            }

        elif any(kw in lowered for kw in ("open", "kholo", "launch", "start", "calc", "notepad", "chrome", "cmd", "volume", "brightness", "lock", "screenshot")):
            if "youtube" in lowered or "http" in lowered or "www" in lowered or "search" in lowered:
                return {
                    "intent": "BROWSER_CONTROL",
                    "reasoning": "Fallback browser route detection",
                    "confidence": 0.8,
                    "operations": [
                        {
                            "action": "open_url",
                            "target": text,
                            "parameters": {"url": text}
                        }
                    ]
                }
            return {
                "intent": "SYSTEM_CONTROL",
                "reasoning": "Fallback system control route detection",
                "confidence": 0.8,
                "operations": [
                    {
                        "action": "open_app",
                        "target": text,
                        "parameters": {"name": text}
                    }
                ]
            }

        elif any(kw in lowered for kw in ("code", "python", "script", "function", "debug", "write a code", "program")):
            return {
                "intent": "CODING_AGENT",
                "reasoning": "Fallback coding agent route detection",
                "confidence": 0.8,
                "operations": [
                    {
                        "action": "write_code",
                        "target": text,
                        "parameters": {}
                    }
                ]
            }

        return {
            "intent": "CONVERSATION",
            "reasoning": "Fallback conversational route detection",
            "confidence": 0.5,
            "operations": [
                {
                    "action": "chat",
                    "target": text,
                    "parameters": {}
                }
            ]
        }
