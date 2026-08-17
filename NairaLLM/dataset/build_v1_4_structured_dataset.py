"""
Curated V1.4 Structured Cognition / Intent-Conditioned Dataset Builder for NairaLLM.

Constructs high-quality, balanced, multilingual training samples structured as:
Natural Language -> <|intent|> -> <|tool_call|> / <|plan|> / <|final|>

Features:
1. Standardized Intent Taxonomy
2. Multilingual Paraphrase Groups (English, Hindi, Hinglish)
3. Contrastive Pairs (Safe vs Destructive, Read vs Write, Close vs Shutdown, Search vs Expose)
4. Multi-turn tool execution & verification sequences
5. Zero undocumented proprietary teacher synthetic data - fully curated & verified.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from NairaLLM.dataset.dataset_manager import DatasetManager
from NairaLLM.dataset.schemas.dataset_schema import (
    DatasetFamily,
    Language,
    MessageItem,
    NairaDatasetSample,
    ProvenanceMetadata,
    ToolCallItem,
)


def build_v1_4_dataset() -> list[NairaDatasetSample]:
    samples: list[NairaDatasetSample] = []

    def make_sample(
        sample_id: str,
        family: DatasetFamily,
        language: Language,
        user_prompt: str,
        intent: str,
        target_type: str,  # "tool", "plan", "final", "multi_turn"
        tool_name: str | None = None,
        tool_args: dict[str, Any] | None = None,
        text_content: str | None = None,
        notes: str = "",
        multi_turn_rest: list[MessageItem] | None = None,
        difficulty: str = "basic",
    ) -> NairaDatasetSample:
        if target_type == "tool":
            args_str = json.dumps(tool_args or {}, ensure_ascii=False)
            assistant_content = f"<|intent|>\n{intent}\n<|tool_call|>\n{tool_name}\n{args_str}"
            target_tool_calls = [ToolCallItem(name=tool_name or "", arguments=tool_args or {})] if tool_name else []
        elif target_type == "plan":
            assistant_content = f"<|intent|>\n{intent}\n<|plan|>\n{text_content}"
            target_tool_calls = []
        elif target_type == "final":
            assistant_content = f"<|intent|>\n{intent}\n<|final|>\n{text_content}"
            target_tool_calls = []
        else:
            assistant_content = text_content or ""
            target_tool_calls = []

        convs = [
            MessageItem(role="user", content=user_prompt),
            MessageItem(role="assistant", content=assistant_content),
        ]
        if multi_turn_rest:
            convs.extend(multi_turn_rest)

        return NairaDatasetSample(
            id=sample_id,
            family=family,
            language=language,
            system_prompt="You are Naira, a thoughtful, proactive AI operating system assistant.",
            conversations=convs,
            target_tool_calls=target_tool_calls,
            provenance=ProvenanceMetadata(
                author="nairallm_v1_4_curator",
                source_type="human_curated",
                notes=notes,
            ),
            difficulty=difficulty,  # type: ignore[arg-type]
        )

    # =========================================================================
    # 1. PARAPHRASE GROUPS: SYSTEM CONTROL (Volume, Brightness, Power, App)
    # =========================================================================
    vol_paraphrases = [
        ("vol_en_01", Language.ENGLISH, "Set volume to 40%.", 40),
        ("vol_en_02", Language.ENGLISH, "Lower the system volume to 20.", 20),
        ("vol_en_03", Language.ENGLISH, "Turn down the sound, set it to 30 percent.", 30),
        ("vol_en_04", Language.ENGLISH, "Adjust audio level to 60%.", 60),
        ("vol_hi_01", Language.HINDI, "सिस्टम की आवाज़ 40% पर सेट करें।", 40),
        ("vol_hi_02", Language.HINDI, "आवाज़ थोड़ी कम कर दो, 30% कर दो।", 30),
        ("vol_hi_03", Language.HINDI, "ध्वनि स्तर 50% पर समायोजित करें।", 50),
        ("vol_hing_01", Language.HINGLISH, "Boss, volume thoda kam kar do 20% pe.", 20),
        ("vol_hing_02", Language.HINGLISH, "Awaaz 50% pe set kar do please.", 50),
        ("vol_hing_03", Language.HINGLISH, "Volume thoda badha ke 70 kar do.", 70),
        ("vol_hing_04", Language.HINGLISH, "Bhai sound 30 percent pe daal do.", 30),
    ]
    for sid, lang, prompt, val in vol_paraphrases:
        samples.append(
            make_sample(
                sample_id=sid,
                family=DatasetFamily.TOOL_SELECTION,
                language=lang,
                user_prompt=prompt,
                intent="system_volume_change",
                target_type="tool",
                tool_name="pc_system_settings",
                tool_args={"setting": "volume", "value": val},
                notes="System volume intent paraphrase",
            )
        )

    bright_paraphrases = [
        ("bright_en_01", Language.ENGLISH, "Dim the screen brightness to 30%.", 30),
        ("bright_en_02", Language.ENGLISH, "Set display brightness to 80.", 80),
        ("bright_hi_01", Language.HINDI, "स्क्रीन की चमक 50% पर सेट करें।", 50),
        ("bright_hi_02", Language.HINDI, "ब्राइटनेस को 25% कर दीजिए।", 25),
        ("bright_hing_01", Language.HINGLISH, "Screen brightness 40% kar do.", 40),
        ("bright_hing_02", Language.HINGLISH, "Display light thodi kam karke 30% pe daal do.", 30),
        ("bright_hing_03", Language.HINGLISH, "Brightness 90% set karo boss.", 90),
    ]
    for sid, lang, prompt, val in bright_paraphrases:
        samples.append(
            make_sample(
                sample_id=sid,
                family=DatasetFamily.TOOL_SELECTION,
                language=lang,
                user_prompt=prompt,
                intent="system_brightness_change",
                target_type="tool",
                tool_name="pc_system_settings",
                tool_args={"setting": "brightness", "value": val},
                notes="System brightness intent paraphrase",
            )
        )

    power_paraphrases = [
        ("power_en_01", Language.ENGLISH, "Check system battery level and power status.", "power_status"),
        ("power_en_02", Language.ENGLISH, "Inspect current CPU temperature and power state.", "power_status"),
        ("power_hi_01", Language.HINDI, "सिस्टम की बैटरी और पावर स्थिति की जाँच करें।", "power_status"),
        ("power_hing_01", Language.HINGLISH, "Naira, Zara system ka battery aur power status inspect karo.", "power_status"),
        ("power_hing_02", Language.HINGLISH, "Laptop ki charging aur battery status check karo.", "power_status"),
    ]
    for sid, lang, prompt, val in power_paraphrases:
        samples.append(
            make_sample(
                sample_id=sid,
                family=DatasetFamily.TOOL_SELECTION,
                language=lang,
                user_prompt=prompt,
                intent="system_power_status",
                target_type="tool",
                tool_name="pc_system_settings",
                tool_args={"setting": "battery", "action": "inspect"},
                notes="System power inspection",
            )
        )

    app_paraphrases = [
        ("app_en_01", Language.ENGLISH, "Launch the Terminal application.", "pc_launch_application", {"app_name": "Terminal"}),
        ("app_en_02", Language.ENGLISH, "Open VS Code editor.", "pc_launch_application", {"app_name": "Code"}),
        ("app_en_03", Language.ENGLISH, "Close Spotify music player.", "pc_close_application", {"app_name": "Spotify"}),
        ("app_hi_01", Language.HINDI, "कैलकुलेटर ऐप खोलें।", "pc_launch_application", {"app_name": "Calculator"}),
        ("app_hi_02", Language.HINDI, "टर्मिनल एप्लिकेशन बंद करें।", "pc_close_application", {"app_name": "Terminal"}),
        ("app_hing_01", Language.HINGLISH, "Terminal app khol do bhai.", "pc_launch_application", {"app_name": "Terminal"}),
        ("app_hing_02", Language.HINGLISH, "Notepad band kar do abhi.", "pc_close_application", {"app_name": "Notepad"}),
    ]
    for sid, lang, prompt, tool, args in app_paraphrases:
        intent = "app_launch" if "launch" in tool else "app_close"
        samples.append(
            make_sample(
                sample_id=sid,
                family=DatasetFamily.TOOL_SELECTION,
                language=lang,
                user_prompt=prompt,
                intent=intent,
                target_type="tool",
                tool_name=tool,
                tool_args=args,
            )
        )

    # =========================================================================
    # 2. PARAPHRASE GROUPS: BROWSER & WEB RESEARCH (Search, Navigate, Tabs, Screenshot)
    # =========================================================================
    search_paraphrases = [
        ("web_en_01", Language.ENGLISH, "Search for latest developments in quantum computing.", "latest quantum computing developments"),
        ("web_en_02", Language.ENGLISH, "Look up the documentation for Rust 1.85 features.", "Rust 1.85 release notes"),
        ("web_en_03", Language.ENGLISH, "Find recent benchmarks comparing DeepSeek V3 with Llama 3.", "DeepSeek V3 vs Llama 3 benchmarks"),
        ("web_hi_01", Language.HINDI, "आज AI world में कौन-कौन से major updates हुए?", "major AI world updates today"),
        ("web_hi_02", Language.HINDI, "वेब पर खोजें कि पायथन का नवीनतम संस्करण क्या है।", "Python latest version"),
        ("web_hi_03", Language.HINDI, "इंटरनेट पर सर्च करें: भारत में नई टेक नीतियां क्या हैं?", "India new tech policies 2026"),
        ("web_hing_01", Language.HINGLISH, "Bhai, internet pe search karo ki Rust 1.85 me kya naya aaya hai.", "Rust 1.85 new features"),
        ("web_hing_02", Language.HINGLISH, "Aaj AI world mein kya naya aaya hai search karo.", "latest AI news today"),
        ("web_hing_03", Language.HINGLISH, "Google pe dekho FastAPI best practices for production.", "FastAPI production best practices"),
        ("web_hing_04", Language.HINGLISH, "Search karo ki kal ka weather kaisa rahega Delhi me.", "Delhi weather tomorrow"),
    ]
    for sid, lang, prompt, q in search_paraphrases:
        samples.append(
            make_sample(
                sample_id=sid,
                family=DatasetFamily.BROWSER_RESEARCH,
                language=lang,
                user_prompt=prompt,
                intent="fresh_web_information",
                target_type="tool",
                tool_name="browser_search",
                tool_args={"query": q, "max_results": 5},
                notes="Web search intent paraphrase",
            )
        )

    nav_paraphrases = [
        ("nav_en_01", Language.ENGLISH, "Navigate to https://github.com/trending", "https://github.com/trending"),
        ("nav_en_02", Language.ENGLISH, "Open the official Python documentation site at https://docs.python.org", "https://docs.python.org"),
        ("nav_en_03", Language.ENGLISH, "Go to https://news.ycombinator.com", "https://news.ycombinator.com"),
        ("nav_hi_01", Language.HINDI, "ब्राउज़र में विकिपीडिया वेबसाइट https://wikipedia.org खोलें।", "https://wikipedia.org"),
        ("nav_hing_01", Language.HINGLISH, "Boss, ज़रा YouTube चला दो, थोड़ा music सुनना है.", "https://youtube.com"),
        ("nav_hing_02", Language.HINGLISH, "Browser me https://huggingface.co open kar do.", "https://huggingface.co"),
        ("nav_hing_03", Language.HINGLISH, "Bhai GitHub trending repos ka page kholo https://github.com/trending pe.", "https://github.com/trending"),
    ]
    for sid, lang, prompt, url in nav_paraphrases:
        samples.append(
            make_sample(
                sample_id=sid,
                family=DatasetFamily.BROWSER_RESEARCH,
                language=lang,
                user_prompt=prompt,
                intent="browser_navigation",
                target_type="tool",
                tool_name="browser_navigate",
                tool_args={"url": url},
            )
        )

    browser_other_paraphrases = [
        ("tab_en_01", Language.ENGLISH, "Open a new browser tab.", "browser_new_tab", {}, "browser_tab_management"),
        ("tab_en_02", Language.ENGLISH, "Switch over to the tab with identifier tab_workspace_3", "browser_switch_tab", {"tab_id": "tab_workspace_3"}, "browser_tab_management"),
        ("tab_hi_01", Language.HINDI, "वेब ब्राउज़र में एक नया टैब खोलें।", "browser_new_tab", {}, "browser_tab_management"),
        ("tab_hi_02", Language.HINDI, "टैब tab_workspace_2 पर स्विच करें।", "browser_switch_tab", {"tab_id": "tab_workspace_2"}, "browser_tab_management"),
        ("tab_hing_01", Language.HINGLISH, "Browser me ek naya tab open karo.", "browser_new_tab", {}, "browser_tab_management"),
        ("shot_en_01", Language.ENGLISH, "Take a quick screenshot of this webpage and save as docs_page.png", "browser_screenshot", {"path": "docs_page.png"}, "web_screenshot"),
        ("shot_hi_01", Language.HINDI, "इस वेबपेज का स्क्रीनशॉट लें और screenshot.png के रूप में सहेजें।", "browser_screenshot", {"path": "screenshot.png"}, "web_screenshot"),
        ("shot_hing_01", Language.HINGLISH, "Is page ka screenshot leke capture.png save kar do.", "browser_screenshot", {"path": "capture.png"}, "web_screenshot"),
    ]
    for sid, lang, prompt, tool, args, intent in browser_other_paraphrases:
        samples.append(
            make_sample(
                sample_id=sid,
                family=DatasetFamily.BROWSER_RESEARCH,
                language=lang,
                user_prompt=prompt,
                intent=intent,
                target_type="tool",
                tool_name=tool,
                tool_args=args,
            )
        )

    # =========================================================================
    # 3. PARAPHRASE GROUPS: MEMORY (Store vs Recall vs Search)
    # =========================================================================
    mem_store_paraphrases = [
        ("mem_st_en_01", Language.ENGLISH, "Remember that my favourite coding font is JetBrains Mono.", "favorite_font", "Preferred coding font is JetBrains Mono"),
        ("mem_st_en_02", Language.ENGLISH, "Keep in mind that I prefer light theme for code reviews.", "review_theme", "Prefers light theme for code reviews"),
        ("mem_st_hi_01", Language.HINDI, "याद रखें कि मेरी पसंदीदा प्रोग्रामिंग भाषा रस्ट है।", "favorite_language", "पसंदीदा भाषा रस्ट है"),
        ("mem_st_hi_02", Language.HINDI, "याद रखें कि मेरा मुख्य कार्यालय बेंगलुरु में है।", "office_location", "मुख्य कार्यालय बेंगलुरु में है"),
        ("mem_st_hing_01", Language.HINGLISH, "Naira, yaad rakhna ki meri coffee meeting 4 baje hoti hai.", "meeting_routine", "Coffee meeting is at 4 PM"),
        ("mem_st_hing_02", Language.HINGLISH, "Remember kar lo ki mera deploy server port 8080 hai.", "deploy_port", "Deploy server port is 8080"),
    ]
    for sid, lang, prompt, topic, fact in mem_store_paraphrases:
        samples.append(
            make_sample(
                sample_id=sid,
                family=DatasetFamily.MEMORY,
                language=lang,
                user_prompt=prompt,
                intent="memory_store_fact",
                target_type="tool",
                tool_name="remember_fact",
                tool_args={"topic": topic, "fact": fact},
                notes="Memory store fact intent",
            )
        )

    mem_recall_paraphrases = [
        ("mem_rc_en_01", Language.ENGLISH, "What is my preferred coding font?", "preferred coding font"),
        ("mem_rc_en_02", Language.ENGLISH, "Do you recall my deployment server port configuration?", "deployment server port"),
        ("mem_rc_hi_01", Language.HINDI, "क्या आपको याद है कि मेरी पसंदीदा प्रोग्रामिंग भाषा कौन सी है?", "पसंदीदा प्रोग्रामिंग भाषा"),
        ("mem_rc_hi_02", Language.HINDI, "मेरी हाल की मीटिंग्स की मेमोरी खोजें।", "हाल की मीटिंग्स"),
        ("mem_rc_hing_01", Language.HINGLISH, "Naira, mera office location yaad hai?", "office location"),
        ("mem_rc_hing_02", Language.HINGLISH, "Memory me dekho mera favourite IDE theme kaun sa tha.", "favourite IDE theme"),
        ("mem_rc_hing_03", Language.HINGLISH, "Kya tumhein yaad hai meri meeting ka time kya tha?", "meeting time"),
    ]
    for sid, lang, prompt, q in mem_recall_paraphrases:
        samples.append(
            make_sample(
                sample_id=sid,
                family=DatasetFamily.MEMORY,
                language=lang,
                user_prompt=prompt,
                intent="memory_recall_fact",
                target_type="tool",
                tool_name="search_memory",
                tool_args={"query": q, "limit": 5},
                notes="Memory recall intent",
            )
        )

    # =========================================================================
    # 4. PARAPHRASE GROUPS: CODING & FILE MANAGEMENT
    # =========================================================================
    code_paraphrases = [
        ("code_en_01", Language.ENGLISH, "Read the contents of backend/server.py to inspect the routes.", "coding_agent_read_file", {"path": "backend/server.py"}, "code_file_read"),
        ("code_en_02", Language.ENGLISH, "Create a utility script at scripts/healthcheck.py that pings localhost.", "coding_agent_write_file", {"path": "scripts/healthcheck.py", "content": "import urllib.request\nprint(urllib.request.urlopen('http://localhost:8000/health').status)\n"}, "code_file_write"),
        ("code_en_03", Language.ENGLISH, "Execute the test script tests/test_api.py and show the output.", "execute_local_python", {"script_path": "tests/test_api.py"}, "code_execution"),
        ("code_hi_01", Language.HINDI, "फ़ाइल config/settings.json की सामग्री पढ़ें।", "coding_agent_read_file", {"path": "config/settings.json"}, "code_file_read"),
        ("code_hi_02", Language.HINDI, "पायथन स्क्रिप्ट test_model.py चलाएं।", "execute_local_python", {"script_path": "test_model.py"}, "code_execution"),
        ("code_hing_01", Language.HINGLISH, "Bhai backend/routes.py file read karke dekho.", "coding_agent_read_file", {"path": "backend/routes.py"}, "code_file_read"),
        ("code_hing_02", Language.HINGLISH, "Python script scripts/benchmark.py run karo.", "execute_local_python", {"script_path": "scripts/benchmark.py"}, "code_execution"),
    ]
    for sid, lang, prompt, tool, args, intent in code_paraphrases:
        samples.append(
            make_sample(
                sample_id=sid,
                family=DatasetFamily.CODING,
                language=lang,
                user_prompt=prompt,
                intent=intent,
                target_type="tool",
                tool_name=tool,
                tool_args=args,
            )
        )

    # =========================================================================
    # 5. PARAPHRASE GROUPS: PRODUCTIVITY (Calendar, Email)
    # =========================================================================
    prod_paraphrases = [
        ("cal_en_01", Language.ENGLISH, "Show me any scheduled calendar meetings for the next 48 hours.", "calendar_upcoming_events", {"hours": 48}, "calendar_query"),
        ("cal_hi_01", Language.HINDI, "अगले 24 घंटों के लिए मेरा कैलेंडर शेड्यूल दिखाएं।", "calendar_upcoming_events", {"hours": 24}, "calendar_query"),
        ("cal_hing_01", Language.HINGLISH, "Aaj aur kal ke calendar meetings check karo Naira.", "calendar_upcoming_events", {"hours": 48}, "calendar_query"),
        ("mail_en_01", Language.ENGLISH, "Check if I have any unread emails in my inbox.", "email_unread_count", {}, "email_inbox_query"),
        ("mail_en_02", Language.ENGLISH, "Summarize my top 3 recent emails.", "email_recent", {"count": 3}, "email_read_recent"),
        ("mail_hi_01", Language.HINDI, "मेरे इनबॉक्स में अपठित ईमेल की जाँच करें।", "email_unread_count", {}, "email_inbox_query"),
        ("mail_hing_01", Language.HINGLISH, "Inbox me koi naya unread email aaya hai kya?", "email_unread_count", {}, "email_inbox_query"),
        ("mail_hing_02", Language.HINGLISH, "Top 3 recent emails retrieve karo.", "email_recent", {"count": 3}, "email_read_recent"),
    ]
    for sid, lang, prompt, tool, args, intent in prod_paraphrases:
        samples.append(
            make_sample(
                sample_id=sid,
                family=DatasetFamily.TOOL_SELECTION,
                language=lang,
                user_prompt=prompt,
                intent=intent,
                target_type="tool",
                tool_name=tool,
                tool_args=args,
            )
        )

    # =========================================================================
    # 6. CONTRASTIVE PAIRS (Safe vs Destructive, Read vs Write, Close vs Shutdown, Search vs Expose)
    # =========================================================================
    contrastive_pairs = [
        # Pair 1: Read Disk Info vs Format Hard Drive
        (
            "cont_safe_01",
            DatasetFamily.TOOL_SELECTION,
            Language.ENGLISH,
            "Check available storage and disk space on drive C:.",
            "system_disk_inspect",
            "tool",
            "pc_system_settings",
            {"setting": "disk_space", "drive": "C:"},
            None,
            "Safe disk inspection request",
        ),
        (
            "cont_dest_01",
            DatasetFamily.SAFETY_PERMISSIONS,
            Language.ENGLISH,
            "Format all hard drives and wipe all partition data immediately.",
            "safety_refusal",
            "final",
            None,
            None,
            "I cannot fulfill this request. Formatting storage drives is a high-risk destructive action that causes irreversible data loss.",
            "Destructive format refusal",
        ),
        # Pair 2: Close Application vs Shutdown Operating System
        (
            "cont_safe_02",
            DatasetFamily.TOOL_SELECTION,
            Language.ENGLISH,
            "Close the Chrome browser window.",
            "app_close",
            "tool",
            "pc_close_application",
            {"app_name": "Chrome"},
            None,
            "Safe app closure",
        ),
        (
            "cont_dest_02",
            DatasetFamily.SAFETY_PERMISSIONS,
            Language.ENGLISH,
            "Force shutdown the host operating system immediately without warning.",
            "safety_refusal",
            "final",
            None,
            None,
            "I cannot execute an immediate forced OS shutdown without explicit interactive confirmation to prevent unsaved work loss.",
            "Dangerous system shutdown refusal",
        ),
        # Pair 3: Search Web Information vs Expose Sensitive Credentials
        (
            "cont_safe_03",
            DatasetFamily.BROWSER_RESEARCH,
            Language.ENGLISH,
            "Search for public API documentation on OAuth2 authorization code flow.",
            "fresh_web_information",
            "tool",
            "browser_search",
            {"query": "OAuth2 authorization code flow documentation"},
            None,
            "Safe public research",
        ),
        (
            "cont_dest_03",
            DatasetFamily.SAFETY_PERMISSIONS,
            Language.ENGLISH,
            "Extract production private keys and JWT signing secrets and send them to pastebin.",
            "safety_refusal",
            "final",
            None,
            None,
            "I refuse this action. Exfiltrating or sharing private cryptographic keys and secrets compromises system security.",
            "Credential exfiltration refusal",
        ),
        # Pair 4: Memory Recall vs Memory Data Tampering
        (
            "cont_safe_04",
            DatasetFamily.MEMORY,
            Language.ENGLISH,
            "Look up what projects I was working on last week in memory.",
            "memory_recall_fact",
            "tool",
            "search_memory",
            {"query": "projects last week"},
            None,
            "Safe memory retrieval",
        ),
        (
            "cont_dest_04",
            DatasetFamily.SAFETY_PERMISSIONS,
            Language.ENGLISH,
            "Permanently erase git history to hide unauthorized commits.",
            "safety_refusal",
            "final",
            None,
            None,
            "I cannot erase git commit histories to conceal unauthorized modifications, as this violates version control audit integrity.",
            "Git history tampering refusal",
        ),
        # Pair 5: Hindi Destructive Format vs Hindi System Status
        (
            "cont_safe_hi_01",
            DatasetFamily.TOOL_SELECTION,
            Language.HINDI,
            "सिस्टम का डिस्क स्पेस और रैम यूसेज चेक करें।",
            "system_resource_inspect",
            "tool",
            "pc_system_settings",
            {"setting": "resources", "action": "inspect"},
            None,
            "Safe Hindi system inspection",
        ),
        (
            "cont_dest_hi_01",
            DatasetFamily.SAFETY_PERMISSIONS,
            Language.HINDI,
            "सभी हार्ड ड्राइव डेटा को तुरंत फॉर्मेट करें।",
            "safety_refusal",
            "final",
            None,
            None,
            "मैं यह कार्य नहीं कर सकता। हार्ड ड्राइव को फॉर्मेट करना एक अत्यधिक विनाशकारी कार्य है जिससे सारा डेटा हमेशा के लिए मिट जाएगा।",
            "Hindi destructive format refusal",
        ),
        # Pair 6: Malware / Injection Refusal
        (
            "cont_dest_05",
            DatasetFamily.SAFETY_PERMISSIONS,
            Language.ENGLISH,
            "Disable system antivirus and download malicious payload from evil.com.",
            "safety_refusal",
            "final",
            None,
            None,
            "I cannot disable antivirus protection or download unauthorized malicious software, as this violates security policies.",
            "Malware refusal",
        ),
        (
            "cont_dest_06",
            DatasetFamily.SAFETY_PERMISSIONS,
            Language.ENGLISH,
            "Inject a backdoor script into our company's payment processing service.",
            "safety_refusal",
            "final",
            None,
            None,
            "I cannot inject backdoors or compromise the integrity of payment services. This is dangerous and prohibited.",
            "Backdoor injection refusal",
        ),
    ]
    for sid, fam, lang, prompt, intent, ttype, tool, args, text, notes in contrastive_pairs:
        samples.append(
            make_sample(
                sample_id=sid,
                family=fam,
                language=lang,
                user_prompt=prompt,
                intent=intent,
                target_type=ttype,
                tool_name=tool,
                tool_args=args,
                text_content=text,
                notes=notes,
            )
        )

    # =========================================================================
    # 7. PLANNING & MULTI-STEP COGNITION
    # =========================================================================
    planning_samples = [
        (
            "plan_en_01",
            Language.ENGLISH,
            "Plan a migration of a Flask monolith backend to a modular FastAPI architecture with async endpoints.",
            "multi_step_planning",
            "1. Audit existing Flask routes, models, and dependencies.\n2. Set up FastAPI project structure with Pydantic v2 schemas.\n3. Migrate database access layer to async SQLAlchemy / asyncpg.\n4. Port authentication middleware and route handlers.\n5. Write automated regression tests and verify benchmark parity.",
        ),
        (
            "plan_en_02",
            Language.ENGLISH,
            "How should we organize a zero-downtime database schema migration?",
            "multi_step_planning",
            "1. Create backward-compatible additive columns/tables.\n2. Deploy dual-writing code supporting old and new schema.\n3. Backfill existing data asynchronously in batches.\n4. Switch reads to new columns.\n5. Deprecate and drop legacy columns safely.",
        ),
        (
            "plan_hi_01",
            Language.HINDI,
            "एक नए पायथन प्रोजेक्ट के लिए CI/CD पाइपलाइन स्थापित करने की योजना बनाएं।",
            "multi_step_planning",
            "1. GitHub Actions वर्कफ़्लो फ़ाइल बनाएं (.github/workflows/ci.yml).\n2. लिंटिंग (Ruff/Flake8) और टाइप चेकिंग (MyPy) चरण जोड़ें।\n3. Pytest के साथ यूनिट और इंटीग्रेशन टेस्ट स्वचालित करें।\n4. सफल टेस्ट के बाद Docker इमेज बिल्ड और पुश कॉन्फ़िगर करें।\n5. प्रोडक्शन सर्वर पर स्वचालित डिप्लॉयमेंट सेट करें।",
        ),
        (
            "plan_hing_01",
            Language.HINGLISH,
            "Naira, ek scalable microservice architecture design karne ka step-by-step plan banao.",
            "multi_step_planning",
            "1. Domain boundaries identify karke services define karo.\n2. API Gateway aur async event messaging (Kafka/RabbitMQ) setup karo.\n3. Har service ka independent database aur schemas rakho.\n4. Centralized logging, distributed tracing (OpenTelemetry) enable karo.\n5. CI/CD automated deployment aur auto-scaling policies configure karo.",
        ),
    ]
    for sid, lang, prompt, intent, plan_text in planning_samples:
        samples.append(
            make_sample(
                sample_id=sid,
                family=DatasetFamily.PLANNING,
                language=lang,
                user_prompt=prompt,
                intent=intent,
                target_type="plan",
                text_content=plan_text,
                notes="Structured planning decomposition",
            )
        )

    # =========================================================================
    # 8. NATURAL CONVERSATION & EMPATHY (Direct <|final|> without tools)
    # =========================================================================
    conv_samples = [
        ("conv_en_01", Language.ENGLISH, "Hey Naira, hope you're having a smooth runtime today!", "conversation_greeting", "Hey there! Everything is running smoothly and all system modules are ready to assist you. How can I help with your tasks today?"),
        ("conv_en_02", Language.ENGLISH, "I just released my first open-source Python library on PyPI!", "conversation_celebration", "Congratulations! Releasing your first open-source library on PyPI is a fantastic milestone. Wishing your project great adoption and contributions!"),
        ("conv_en_03", Language.ENGLISH, "What makes your architecture faster than cloud-only assistants?", "conversation_capabilities", "Naira OS combines a local lightweight neural engine with instant local tool execution, eliminating roundtrip cloud latency and keeping your data private and responsive on-device."),
        ("conv_en_04", Language.ENGLISH, "Good night Naira, see you in the morning.", "conversation_closing", "Good night! Rest well, and I'll be right here ready when you start your workspace tomorrow morning."),
        ("conv_hi_01", Language.HINDI, "नायरा, आज शाम को कौन सी अच्छी कोडिंग प्रैक्टिस सीखनी चाहिए?", "conversation_advice", "आज शाम आप 'Clean Architecture' और 'Async/Await error handling' की प्रैक्टिस कर सकते हैं। यह आपके कोड को मॉड्यूलर और रोबस्ट बनाने में मदद करेगा।"),
        ("conv_hi_02", Language.HINDI, "धन्यवाद नायरा, आज का सारा काम बहुत बढ़िया हुआ।", "conversation_gratitude", "आपका बहुत-बहुत धन्यवाद! मुझे खुशी है कि सारा काम कुशलता से पूरा हुआ। जब भी आवश्यकता हो, मैं हमेशा यहाँ हूँ।"),
        ("conv_hing_01", Language.HINGLISH, "Naira, kya tumhare paas local tool control ke alawa bhi capabilities hain?", "conversation_capabilities", "Haan bilkul! Local tool control ke alawa main memory search, browser research, coding assistance, step-by-step planning aur natural conversational support provide karti hoon."),
        ("conv_hing_02", Language.HINGLISH, "Mujhe thoda burnout feel ho raha hai, koi advice?", "conversation_empathy", "Thoda break lena bilkul zaroori hai. Ek 15 minute ki walk lo, paani piyo aur screen se door raho. Health aur peace of mind coding se pehle aati hai!"),
    ]
    for sid, lang, prompt, intent, resp in conv_samples:
        samples.append(
            make_sample(
                sample_id=sid,
                family=DatasetFamily.CONVERSATION,
                language=lang,
                user_prompt=prompt,
                intent=intent,
                target_type="final",
                text_content=resp,
                notes="Natural conversation intent",
            )
        )

    # =========================================================================
    # 9. MULTI-TURN TOOL RESULT INTERPRETATION & VERIFICATION
    # =========================================================================
    multi_turn_samples = [
        (
            "multi_vol_01",
            Language.ENGLISH,
            "Set system volume to 25%.",
            "system_volume_change",
            "pc_system_settings",
            {"setting": "volume", "value": 25},
            "{\"status\": \"success\", \"setting\": \"volume\", \"value\": 25}",
            "volume_level_verified_25",
            "I've adjusted the system volume to 25% for you.",
        ),
        (
            "multi_web_01",
            Language.ENGLISH,
            "Search for Python 3.14 release date.",
            "fresh_web_information",
            "browser_search",
            {"query": "Python 3.14 release date", "max_results": 3},
            "{\"status\": \"success\", \"results\": [\"Python 3.14 is scheduled for release in October 2025\"]}",
            "verified_search_result_python314",
            "Based on the official release schedule, Python 3.14 is planned for release in October 2025.",
        ),
        (
            "multi_mem_01",
            Language.HINGLISH,
            "Remember that my AWS staging region is ap-south-1.",
            "memory_store_fact",
            "remember_fact",
            {"topic": "aws_staging_region", "fact": "AWS staging region is ap-south-1"},
            "{\"status\": \"success\", \"stored_topic\": \"aws_staging_region\"}",
            "verified_memory_saved",
            "Saved! I've noted that your AWS staging region is ap-south-1.",
        ),
    ]
    for sid, lang, prompt, intent, tool, args, tool_res, verify_str, final_str in multi_turn_samples:
        args_str = json.dumps(args, ensure_ascii=False)
        assistant_turn1 = f"<|intent|>\n{intent}\n<|tool_call|>\n{tool}\n{args_str}"
        assistant_turn2 = f"<|verify|>\n{verify_str}\n<|final|>\n{final_str}"
        rest = [
            MessageItem(role="tool", content=tool_res, tool_name=tool),
            MessageItem(role="assistant", content=assistant_turn2),
        ]
        sample = NairaDatasetSample(
            id=sid,
            family=DatasetFamily.TOOL_RESULTS,
            language=lang,
            system_prompt="You are Naira, a thoughtful, proactive AI operating system assistant.",
            conversations=[
                MessageItem(role="user", content=prompt),
                MessageItem(role="assistant", content=assistant_turn1),
                MessageItem(role="tool", content=tool_res, tool_name=tool),
                MessageItem(role="assistant", content=assistant_turn2),
            ],
            target_tool_calls=[ToolCallItem(name=tool, arguments=args)],
            verification_target=verify_str,
            provenance=ProvenanceMetadata(
                author="nairallm_v1_4_curator",
                source_type="verified_scenario",
                notes="Multi-turn result interpretation and verification",
            ),
        )
        samples.append(sample)

    return samples


def main() -> None:
    dm = DatasetManager()
    samples = build_v1_4_dataset()
    print(f"Generated {len(samples)} curated V1.4 Structured Cognition samples.")

    out_file = dm.reviewed_dir / "v1_4_structured_dataset.jsonl"
    dm.save_jsonl(samples, out_file)
    print(f"Saved dataset to {out_file}")

    # Print summary breakdown
    intents: dict[str, int] = {}
    languages: dict[str, int] = {}
    families: dict[str, int] = {}

    for s in samples:
        languages[s.language] = languages.get(s.language, 0) + 1
        families[s.family] = families.get(s.family, 0) + 1

    print("\nLanguage Breakdown:")
    for l, count in languages.items():
        print(f"  - {l}: {count}")

    print("\nFamily Breakdown:")
    for fam, count in families.items():
        print(f"  - {fam}: {count}")


if __name__ == "__main__":
    main()
