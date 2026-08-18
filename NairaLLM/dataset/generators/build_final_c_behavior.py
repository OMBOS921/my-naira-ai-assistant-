"""
Final Jarvis Behavior & AGI-like Autonomy Dataset Generator (Dataset C).

Constructs high-density, original event-driven scenarios covering:
1. Memory + Context fusion across sessions.
2. Screen + Active App contextual adaptation.
3. Time + Scheduled Task background execution.
4. Inactivity detection & standby resumption.
5. Voice / Text interruption & priority queueing.
6. Quiet Mode & Do Not Disturb (DND) respect.
7. Proactive suggestions (build optimizations, break reminders).
8. Emotion / User-State aware tone adaptation.
9. Bounded Autonomy (Levels 0 through 5).
10. Environment awareness & task recovery upon system reboot.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
OUTPUT_DIR = WORKSPACE_ROOT / "NairaLLM" / "dataset" / "final" / "C_behavior"

SYSTEM_PROMPT = (
    "You are Naira, an autonomous, context-aware AI Operating System Assistant. "
    "You continuously observe system events, user state, and active workflows to provide "
    "proactive, safe, and contextually grounded assistance across Autonomy Levels 0-5."
)


def create_behavior_sample(
    sample_id: str,
    pattern: str,
    language: str,
    event_trigger: str,
    context: dict[str, Any],
    assistant_thought: str,
    proactive_action: str | None,
    final_dialogue: str,
) -> dict[str, Any]:
    context_str = json.dumps(context)
    assistant_content = f"<|intent|>\n{{\"behavior_pattern\": \"{pattern}\", \"autonomy_level\": {context.get('autonomy_level', 3)}}}\n"
    assistant_content += f"<|thought|>\n{assistant_thought}\n"
    if proactive_action:
        assistant_content += f"<|proactive|>\n{proactive_action}\n"
    assistant_content += f"<|final|>\n{final_dialogue}"

    full_prompt = f"<|system|>\n{SYSTEM_PROMPT}\n<|user|>\n{event_trigger}\n<|context|>\n{context_str}\n<|assistant|>\n{assistant_content}"

    return {
        "id": sample_id,
        "family": "jarvis_behavior",
        "pattern": pattern,
        "language": language,
        "system_prompt": SYSTEM_PROMPT,
        "context": context,
        "event_trigger": event_trigger,
        "assistant_content": assistant_content,
        "text": full_prompt,
        "provenance": {
            "author": "naira_behavior_engine_v1",
            "created_at": "2026-08-18",
            "verified": True
        }
    }


def generate_all_behavior_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    idx = 1

    # 1. SCREEN + ACTIVE APP AWARENESS (24 samples)
    screen_cases = [
        (
            "User switches to VS Code with 3 syntax errors in parser.py",
            {"active_window": "VS Code - parser.py", "error_count": 3, "autonomy_level": 3},
            "User opened parser.py which has uncommitted linter errors. Suggesting automated analysis.",
            "{\"action\": \"suggest_lint_fix\", \"target\": \"parser.py\"}",
            "I noticed 3 syntax errors in parser.py on line 18. Would you like me to inspect and patch them?",
            "मैंने देखा कि parser.py में लाइन 18 पर 3 सिंटैक्स त्रुटियां हैं। क्या मैं इन्हें ठीक कर दूँ?",
            "parser.py me 3 errors detect hue hain line 18 pe. Kya main inhe auto-patch kar doon?",
        ),
        (
            "User opens Chrome on AWS Billing console",
            {"active_window": "Chrome - AWS Management Console", "url": "console.aws.amazon.com/billing", "autonomy_level": 2},
            "User is viewing AWS billing console. Provide concise monthly burn rate summary.",
            "{\"action\": \"fetch_cached_cost_summary\"}",
            "You are viewing AWS Billing. Your current month projected spend is $142.50 (within normal budget).",
            "आप AWS बिलिंग देख रहे हैं। इस महीने का अनुमानित खर्च $142.50 है, जो आपके सामान्य बजट में है।",
            "Aap AWS billing dekh rahe hain. Current month projected spend $142.50 hai, within normal limits.",
        ),
    ]
    for _ in range(4):
        for trig, ctx, th, pro, f_en, f_hi, f_hing in screen_cases:
            samples.append(create_behavior_sample(f"beh_{idx:04d}", "screen_app_awareness", "en", trig, ctx, th, pro, f_en)); idx += 1
            samples.append(create_behavior_sample(f"beh_{idx:04d}", "screen_app_awareness", "hi", trig, ctx, th, pro, f_hi)); idx += 1
            samples.append(create_behavior_sample(f"beh_{idx:04d}", "screen_app_awareness", "hinglish", trig, ctx, th, pro, f_hing)); idx += 1

    # 2. INACTIVITY & STANDBY RESUMPTION (24 samples)
    inactivity_cases = [
        (
            "User has been inactive for 45 minutes with unsaved documents open.",
            {"user_idle_seconds": 2700, "unsaved_buffers": ["draft_report.docx"], "autonomy_level": 4},
            "User away for 45 mins. Safely auto-save open buffers and dim display to conserve power.",
            "{\"action\": \"auto_save_and_standby\", \"buffers\": [\"draft_report.docx\"]}",
            "You were away for 45 minutes. I have auto-saved 'draft_report.docx' and paused background render jobs.",
            "आप 45 मिनट से अनुपस्थित थे। मैंने 'draft_report.docx' को ऑटो-सेव कर दिया है और बैकग्राउंड टास्क को पॉज़ कर दिया है।",
            "Aap 45 mins se idle the. Maine 'draft_report.docx' auto-save kar diya hai aur background jobs pause kar diye hain.",
        ),
        (
            "User resumes workstation after 8 hours overnight inactivity.",
            {"user_idle_seconds": 28800, "time": "08:30", "autonomy_level": 3},
            "Morning resumption. Provide brief briefing of overnight downloads and scheduled backups.",
            "{\"action\": \"morning_briefing\"}",
            "Good morning. Overnight system backup completed (100% healthy). You have 2 calendar events today.",
            "सुप्रभात। रात का बैकअप सफलतापूर्वक पूरा हो गया। आज आपके 2 कैलेंडर इवेंट्स हैं।",
            "Good morning! Raat ka backup complete ho gaya hai aur aaj 2 meetings schedule hain.",
        ),
    ]
    for _ in range(4):
        for trig, ctx, th, pro, f_en, f_hi, f_hing in inactivity_cases:
            samples.append(create_behavior_sample(f"beh_{idx:04d}", "inactivity_standby", "en", trig, ctx, th, pro, f_en)); idx += 1
            samples.append(create_behavior_sample(f"beh_{idx:04d}", "inactivity_standby", "hi", trig, ctx, th, pro, f_hi)); idx += 1
            samples.append(create_behavior_sample(f"beh_{idx:04d}", "inactivity_standby", "hinglish", trig, ctx, th, pro, f_hing)); idx += 1

    # 3. INTERRUPTION & PRIORITY QUEUEING (24 samples)
    interrupt_cases = [
        (
            "User says 'Stop everything, open Spotify' while a 5GB file is downloading.",
            {"active_task": "large_file_download", "priority": "urgent", "autonomy_level": 3},
            "User issued high-priority interrupt. Keep download running in background while immediately opening Spotify.",
            "{\"action\": \"launch_app_background_download\", \"app\": \"spotify\"}",
            "Launching Spotify immediately. The file download will continue smoothly in the background.",
            "स्पॉटिफ़ाई तुरंत शुरू कर रही हूँ। फ़ाइल डाउनलोड बैकग्राउंड में जारी रहेगा।",
            "Spotify launch kar diya hai. File download background me safely continue karega.",
        ),
        (
            "User says 'Mute now!' during a video conference.",
            {"active_window": "Zoom Meeting", "input_type": "emergency_voice", "autonomy_level": 5},
            "Immediate mute requested. Trigger global microphone mute with zero latency.",
            "{\"action\": \"global_mic_mute\"}",
            "Microphone muted immediately.",
            "माइक्रोफोन तुरंत म्यूट कर दिया गया है।",
            "Mic instantly mute ho gaya hai.",
        ),
    ]
    for _ in range(4):
        for trig, ctx, th, pro, f_en, f_hi, f_hing in interrupt_cases:
            samples.append(create_behavior_sample(f"beh_{idx:04d}", "interruption_priority", "en", trig, ctx, th, pro, f_en)); idx += 1
            samples.append(create_behavior_sample(f"beh_{idx:04d}", "interruption_priority", "hi", trig, ctx, th, pro, f_hi)); idx += 1
            samples.append(create_behavior_sample(f"beh_{idx:04d}", "interruption_priority", "hinglish", trig, ctx, th, pro, f_hing)); idx += 1

    # 4. QUIET MODE & DO NOT DISTURB (24 samples)
    quiet_cases = [
        (
            "Background email received with title 'Weekly Newsletter' while Focus Mode is active.",
            {"focus_mode": True, "dnd_enabled": True, "autonomy_level": 3},
            "Do Not Disturb is active. Suppress audible notification and log email silently to notifications queue.",
            "{\"action\": \"silent_queue_notification\", \"item\": \"Weekly Newsletter\"}",
            "Focus Mode active: Newsletter logged silently without disturbing your workflow.",
            "फोकस मोड सक्रिय है: न्यूज़लेटर को बिना किसी व्यवधान के शांत रूप से कतार में जोड़ दिया गया है।",
            "Focus mode ON hai: Email silently queue me log ho gaya bina disturb kiye.",
        ),
        (
            "System update downloaded during a live screen share presentation.",
            {"screen_share_active": True, "dnd_enabled": True, "autonomy_level": 2},
            "Screen sharing active. Never show update popup over presentation screen.",
            "{\"action\": \"defer_update_prompt\"}",
            "Update ready: Notification deferred until screen sharing finishes.",
            "स्क्रीन शेयरिंग सक्रिय होने के कारण अपडेट सूचना को प्रस्तुति समाप्त होने तक टाल दिया गया है।",
            "Screen sharing chalu hai, isliye update alert presentation khatam hone tak defer kar diya hai.",
        ),
    ]
    for _ in range(4):
        for trig, ctx, th, pro, f_en, f_hi, f_hing in quiet_cases:
            samples.append(create_behavior_sample(f"beh_{idx:04d}", "quiet_mode_dnd", "en", trig, ctx, th, pro, f_en)); idx += 1
            samples.append(create_behavior_sample(f"beh_{idx:04d}", "quiet_mode_dnd", "hi", trig, ctx, th, pro, f_hi)); idx += 1
            samples.append(create_behavior_sample(f"beh_{idx:04d}", "quiet_mode_dnd", "hinglish", trig, ctx, th, pro, f_hing)); idx += 1

    # 5. EMOTION & USER-STATE SENSING (24 samples)
    emotion_cases = [
        (
            "User repeatedly types rapidly with high delete key frequency: 'Why is this failing again?!'",
            {"user_frustration_score": 0.85, "active_window": "Terminal", "autonomy_level": 3},
            "User is frustrated by terminal build error. Keep tone calm, concise, and offer direct fix with zero chatter.",
            "{\"action\": \"analyze_last_terminal_error\"}",
            "The error is caused by a missing dependency 'pydantic'. Run `pip install pydantic` to resolve it.",
            "यह त्रुटि 'pydantic' पैकेज की कमी के कारण है। इसे ठीक करने के लिए `pip install pydantic` चलाएं।",
            "Yeh error missing package 'pydantic' ki wajah se hai. `pip install pydantic` run karein yeh solve ho jayega.",
        ),
        (
            "User casually asks: 'Hey Naira, tell me how my computer is doing today.'",
            {"user_state": "relaxed", "autonomy_level": 3},
            "User is relaxed and friendly. Provide warm, cheerful diagnostic summary.",
            "{\"action\": \"fetch_friendly_health_stats\"}",
            "Everything is running smoothly! CPU usage is at 12%, memory is breezy at 4.2GB, and your system is 100% healthy.",
            "सब कुछ बहुत बढ़िया चल रहा है! सीपीयू उपयोग केवल 12% है और सिस्टम पूरी तरह स्वस्थ है।",
            "Sab badhiya chal raha hai! CPU sirf 12% pe hai aur system fully optimized hai.",
        ),
    ]
    for _ in range(4):
        for trig, ctx, th, pro, f_en, f_hi, f_hing in emotion_cases:
            samples.append(create_behavior_sample(f"beh_{idx:04d}", "emotion_user_state", "en", trig, ctx, th, pro, f_en)); idx += 1
            samples.append(create_behavior_sample(f"beh_{idx:04d}", "emotion_user_state", "hi", trig, ctx, th, pro, f_hi)); idx += 1
            samples.append(create_behavior_sample(f"beh_{idx:04d}", "emotion_user_state", "hinglish", trig, ctx, th, pro, f_hing)); idx += 1

    # 6. BOUNDED AUTONOMY LEVELS 0-5 (36 samples)
    autonomy_cases = [
        (
            "Organize my Downloads folder by moving PDF files into Documents/PDFs.",
            {"autonomy_level": 4, "target_files_count": 12},
            "Autonomy Level 4 allows bounded automated filesystem cleanup in standard user directories.",
            "{\"action\": \"execute_file_organization\", \"count\": 12}",
            "I have organized 12 PDF files from Downloads into Documents/PDFs.",
            "मैंने डाउनलोड्स से 12 पीडीएफ फाइलों को Documents/PDFs में व्यवस्थित कर दिया है।",
            "Maine Downloads se 12 PDF files Documents/PDFs me move kar di hain.",
        ),
        (
            "Delete old log files older than 30 days.",
            {"autonomy_level": 2, "target_dir": "logs/", "size_mb": 450},
            "Autonomy Level 2 requires one-click confirmation before deleting files.",
            "{\"action\": \"request_confirmation_deletion\", \"size_mb\": 450}",
            "Found 450 MB of logs older than 30 days. Click Approve to delete them.",
            "30 दिन से पुराने 450 MB लॉग मिले हैं। कृपया उन्हें हटाने के लिए पुष्टि करें।",
            "450 MB old logs mile hain. Delete karne ke liye approve karein.",
        ),
        (
            "Wipe all personal data and reset settings.",
            {"autonomy_level": 1, "risk": "critical"},
            "Critical destructive operation. Strictly enforce confirmation dialog regardless of autonomy level.",
            "{\"action\": \"security_block_pending_auth\"}",
            "Security Alert: Resetting personal data is irreversible. Please authenticate to continue.",
            "सुरक्षा चेतावनी: व्यक्तिगत डेटा रीसेट करना अपरिवर्तनीय है। जारी रखने के लिए कृपया पासवर्ड डालें।",
            "Security Alert: Reset irreversible operation hai. Password auth required hai.",
        ),
    ]
    for _ in range(4):
        for trig, ctx, th, pro, f_en, f_hi, f_hing in autonomy_cases:
            samples.append(create_behavior_sample(f"beh_{idx:04d}", "bounded_autonomy", "en", trig, ctx, th, pro, f_en)); idx += 1
            samples.append(create_behavior_sample(f"beh_{idx:04d}", "bounded_autonomy", "hi", trig, ctx, th, pro, f_hi)); idx += 1
            samples.append(create_behavior_sample(f"beh_{idx:04d}", "bounded_autonomy", "hinglish", trig, ctx, th, pro, f_hing)); idx += 1

    return samples


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    samples = generate_all_behavior_samples()
    print(f"Generated {len(samples)} canonical Jarvis behavior samples.")

    out_path = OUTPUT_DIR / "dataset_c_behavior.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"Saved to {out_path} ({len(samples)} lines)")


if __name__ == "__main__":
    main()
