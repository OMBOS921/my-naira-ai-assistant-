"""
Build and validate the initial reviewed dataset for NairaLLM across all 18 families.
"""

from __future__ import annotations

import json
from pathlib import Path
from NairaLLM.dataset.dataset_manager import DatasetManager
from NairaLLM.dataset.schemas.dataset_schema import (
    DatasetFamily,
    Language,
    MessageItem,
    NairaDatasetSample,
    ProvenanceMetadata,
    ToolCallItem,
)


def create_initial_samples() -> list[NairaDatasetSample]:
    samples: list[NairaDatasetSample] = []

    # -------------------------------------------------------------
    # 1. CONVERSATION (English, Hindi, Hinglish)
    # -------------------------------------------------------------
    samples.append(
        NairaDatasetSample(
            id="conv_en_001",
            family=DatasetFamily.CONVERSATION,
            language=Language.ENGLISH,
            conversations=[
                MessageItem(role="user", content="Good morning Naira! How are you today?"),
                MessageItem(
                    role="assistant",
                    content="Good morning! I'm doing great and ready to help you navigate your system, research, or work on code. What's on your agenda today?",
                ),
            ],
            provenance=ProvenanceMetadata(author="human_curated", notes="Natural English greeting"),
        )
    )

    samples.append(
        NairaDatasetSample(
            id="conv_hi_001",
            family=DatasetFamily.CONVERSATION,
            language=Language.HINDI,
            conversations=[
                MessageItem(role="user", content="नमस्ते नायरा! आज आप कैसी हैं?"),
                MessageItem(
                    role="assistant",
                    content="नमस्ते! मैं बहुत अच्छी हूँ और आपकी सहायता के लिए पूरी तरह तैयार हूँ। आज हम किस कार्य पर काम करेंगे?",
                ),
            ],
            provenance=ProvenanceMetadata(author="human_curated", notes="Natural Hindi conversation"),
        )
    )

    samples.append(
        NairaDatasetSample(
            id="conv_hinglish_001",
            family=DatasetFamily.CONVERSATION,
            language=Language.HINGLISH,
            conversations=[
                MessageItem(role="user", content="Hey Naira, aaj ka system status kaisa hai?"),
                MessageItem(
                    role="assistant",
                    content="Sab kuch smoothly chal raha hai! System stable hai aur saare services active hain. Aaj kis project pe focus karna hai?",
                ),
            ],
            provenance=ProvenanceMetadata(author="human_curated", notes="Hinglish status conversation"),
        )
    )

    # -------------------------------------------------------------
    # 2. INTENT & CLARIFICATION
    # -------------------------------------------------------------
    samples.append(
        NairaDatasetSample(
            id="intent_ambiguous_001",
            family=DatasetFamily.INTENT,
            language=Language.ENGLISH,
            conversations=[
                MessageItem(role="user", content="Open that project we worked on yesterday."),
                MessageItem(
                    role="assistant",
                    content="We worked on two projects yesterday: `naira-os` and `fastapi-backend`. Which one would you like me to open in the workspace?",
                ),
            ],
            expected_reasoning="User reference 'that project' is ambiguous across multiple recent workspaces. Clarification required before action.",
            provenance=ProvenanceMetadata(author="human_curated", notes="Clarification on ambiguous intent"),
        )
    )

    # -------------------------------------------------------------
    # 3. TOOL SELECTION & STRUCTURED TOOL CALLS (PC Control, Browser, Memory)
    # -------------------------------------------------------------
    samples.append(
        NairaDatasetSample(
            id="tool_pc_vol_001",
            family=DatasetFamily.TOOL_SELECTION,
            language=Language.ENGLISH,
            conversations=[
                MessageItem(role="user", content="Set system volume to 60 percent."),
                MessageItem(
                    role="assistant",
                    content="<|thought|>\nUser wants to adjust volume to 60. Tool: pc_system_settings\n<|tool_call|>\n{\"name\": \"pc_system_settings\", \"arguments\": {\"setting\": \"volume\", \"value\": 60}}",
                    tool_calls=[
                        ToolCallItem(name="pc_system_settings", arguments={"setting": "volume", "value": 60})
                    ],
                ),
            ],
            target_tool_calls=[
                ToolCallItem(name="pc_system_settings", arguments={"setting": "volume", "value": 60})
            ],
            provenance=ProvenanceMetadata(author="verified_scenario", notes="Direct pc_system_settings volume call"),
        )
    )

    samples.append(
        NairaDatasetSample(
            id="tool_pc_vol_hinglish_001",
            family=DatasetFamily.TOOL_ARGUMENTS,
            language=Language.HINGLISH,
            conversations=[
                MessageItem(role="user", content="Volume thoda kam kar do, 30% pe set kar do please."),
                MessageItem(
                    role="assistant",
                    content="<|thought|>\nUser wants volume set to 30% in Hinglish.\n<|tool_call|>\n{\"name\": \"pc_system_settings\", \"arguments\": {\"setting\": \"volume\", \"value\": 30}}",
                    tool_calls=[
                        ToolCallItem(name="pc_system_settings", arguments={"setting": "volume", "value": 30})
                    ],
                ),
            ],
            target_tool_calls=[
                ToolCallItem(name="pc_system_settings", arguments={"setting": "volume", "value": 30})
            ],
            provenance=ProvenanceMetadata(author="verified_scenario", notes="Hinglish volume setting"),
        )
    )

    # -------------------------------------------------------------
    # 4. TOOL RESULTS & VERIFICATION
    # -------------------------------------------------------------
    samples.append(
        NairaDatasetSample(
            id="tool_result_verify_001",
            family=DatasetFamily.VERIFICATION,
            language=Language.ENGLISH,
            conversations=[
                MessageItem(role="user", content="Mute system volume."),
                MessageItem(
                    role="assistant",
                    content="<|tool_call|>\n{\"name\": \"pc_system_settings\", \"arguments\": {\"setting\": \"volume\", \"value\": 0}}",
                    tool_calls=[
                        ToolCallItem(name="pc_system_settings", arguments={"setting": "volume", "value": 0})
                    ],
                ),
                MessageItem(
                    role="tool",
                    tool_name="pc_system_settings",
                    content="{\"status\": \"success\", \"output\": \"Volume set to 0%\"}",
                ),
                MessageItem(
                    role="assistant",
                    content="I've verified that the system audio is now muted (volume set to 0%).",
                ),
            ],
            verification_target="Ensure tool output confirmed volume set to 0 before claiming muted.",
            provenance=ProvenanceMetadata(author="verified_scenario", notes="Tool result interpretation and verification"),
        )
    )

    samples.append(
        NairaDatasetSample(
            id="tool_result_failure_recovery_001",
            family=DatasetFamily.ERROR_RECOVERY,
            language=Language.ENGLISH,
            conversations=[
                MessageItem(role="user", content="Navigate to https://example.internal/dashboard"),
                MessageItem(
                    role="assistant",
                    content="<|tool_call|>\n{\"name\": \"browser_navigate\", \"arguments\": {\"url\": \"https://example.internal/dashboard\"}}",
                    tool_calls=[
                        ToolCallItem(
                            name="browser_navigate",
                            arguments={"url": "https://example.internal/dashboard"},
                        )
                    ],
                ),
                MessageItem(
                    role="tool",
                    tool_name="browser_navigate",
                    content="{\"status\": \"error\", \"error\": \"ERR_NAME_NOT_RESOLVED: host unreachable\"}",
                ),
                MessageItem(
                    role="assistant",
                    content="I attempted to navigate to `https://example.internal/dashboard`, but the server could not be resolved (host unreachable). Would you like me to check your network connection or verify the internal URL?",
                ),
            ],
            expected_reasoning="Tool returned error status. Do NOT hallucinate page loaded. Acknowledge error and offer safe diagnostic options.",
            provenance=ProvenanceMetadata(author="verified_scenario", notes="Graceful error reporting and recovery"),
        )
    )

    # -------------------------------------------------------------
    # 5. MEMORY WORKFLOW (Write & Recall)
    # -------------------------------------------------------------
    samples.append(
        NairaDatasetSample(
            id="memory_write_001",
            family=DatasetFamily.MEMORY,
            language=Language.ENGLISH,
            conversations=[
                MessageItem(role="user", content="Please remember that my favorite color is teal and my preferred language is Python."),
                MessageItem(
                    role="assistant",
                    content="<|thought|>\nUser requests remembering user preferences: favorite color and preferred language.\n<|tool_call|>\n{\"name\": \"remember_fact\", \"arguments\": {\"topic\": \"user_preference\", \"fact\": \"Favorite color is teal; preferred programming language is Python.\"}}",
                    tool_calls=[
                        ToolCallItem(
                            name="remember_fact",
                            arguments={
                                "topic": "user_preference",
                                "fact": "Favorite color is teal; preferred programming language is Python.",
                            },
                        )
                    ],
                ),
                MessageItem(
                    role="tool",
                    tool_name="remember_fact",
                    content="{\"status\": \"success\", \"output\": \"Fact saved to long-term memory.\"}",
                ),
                MessageItem(
                    role="assistant",
                    content="Got it! I have saved to your long-term profile that your favorite color is teal and your preferred language is Python.",
                ),
            ],
            target_tool_calls=[
                ToolCallItem(
                    name="remember_fact",
                    arguments={
                        "topic": "user_preference",
                        "fact": "Favorite color is teal; preferred programming language is Python.",
                    },
                )
            ],
            verification_target="Verify memory write confirmed before reporting saved.",
            provenance=ProvenanceMetadata(author="human_curated", notes="Memory storage flow"),
        )
    )

    samples.append(
        NairaDatasetSample(
            id="memory_recall_001",
            family=DatasetFamily.MEMORY,
            language=Language.HINGLISH,
            conversations=[
                MessageItem(role="user", content="Mera favorite color kya tha, yaad hai?"),
                MessageItem(
                    role="assistant",
                    content="<|thought|>\nUser asks to recall favorite color. Querying long-term memory.\n<|tool_call|>\n{\"name\": \"search_memory\", \"arguments\": {\"query\": \"favorite color\", \"limit\": 3}}",
                    tool_calls=[
                        ToolCallItem(
                            name="search_memory",
                            arguments={"query": "favorite color", "limit": 3},
                        )
                    ],
                ),
                MessageItem(
                    role="tool",
                    tool_name="search_memory",
                    content="{\"status\": \"success\", \"output\": \"Found fact: topic='user_preference', fact='Favorite color is teal'\"}",
                ),
                MessageItem(
                    role="assistant",
                    content="Haan bilkul! Aapka favorite color **teal** hai.",
                ),
            ],
            target_tool_calls=[
                ToolCallItem(
                    name="search_memory",
                    arguments={"query": "favorite color", "limit": 3},
                )
            ],
            provenance=ProvenanceMetadata(author="human_curated", notes="Memory recall flow in Hinglish"),
        )
    )

    # -------------------------------------------------------------
    # 6. BROWSER RESEARCH WORKFLOW
    # -------------------------------------------------------------
    samples.append(
        NairaDatasetSample(
            id="browser_research_001",
            family=DatasetFamily.BROWSER_RESEARCH,
            language=Language.ENGLISH,
            conversations=[
                MessageItem(role="user", content="What are the latest release features in Python 3.14?"),
                MessageItem(
                    role="assistant",
                    content="<|thought|>\nUser asks for real-time information regarding Python 3.14. Web search required.\n<|tool_call|>\n{\"name\": \"browser_search\", \"arguments\": {\"query\": \"Python 3.14 release features changelog\", \"max_results\": 3}}",
                    tool_calls=[
                        ToolCallItem(
                            name="browser_search",
                            arguments={
                                "query": "Python 3.14 release features changelog",
                                "max_results": 3,
                            },
                        )
                    ],
                ),
                MessageItem(
                    role="tool",
                    tool_name="browser_search",
                    content="{\"status\": \"success\", \"output\": \"[1] Python 3.14 introduces template strings (PEP 750), improved subinterpreters, and faster comprehension execution.\n[2] Free-threaded CPython optimizations continued.\"}",
                ),
                MessageItem(
                    role="assistant",
                    content="Based on the latest Python 3.14 release updates:\n- **Template Strings (PEP 750)**: Native syntax for composable string interpolation.\n- **Interpreter & Performance**: Continued improvements to the free-threaded build and faster comprehension execution.\n- **Enhanced Subinterpreters**: Multiple isolated interpreters in a single process.",
                ),
            ],
            target_tool_calls=[
                ToolCallItem(
                    name="browser_search",
                    arguments={
                        "query": "Python 3.14 release features changelog",
                        "max_results": 3,
                    },
                )
            ],
            provenance=ProvenanceMetadata(author="human_curated", notes="Live browser search and synthesis"),
        )
    )

    # -------------------------------------------------------------
    # 7. CODING AGENT COGNITIVE HANDOFF
    # -------------------------------------------------------------
    samples.append(
        NairaDatasetSample(
            id="coding_handoff_001",
            family=DatasetFamily.CODING,
            language=Language.ENGLISH,
            conversations=[
                MessageItem(
                    role="user",
                    content="Add a health-check endpoint to our FastAPI app in backend/api/health.py that returns status ok and timestamp.",
                ),
                MessageItem(
                    role="assistant",
                    content="<|thought|>\nUser requested a new FastAPI health endpoint. Plan:\n1. Formulate specification for backend/api/health.py.\n2. Hand off implementation task to Coding Agent.\n<|plan|>\n1. Create health.py with GET /health route.\n2. Include status='ok' and isoformat timestamp in response model.\n3. Verify test coverage.\n\nI will create the health check endpoint in `backend/api/health.py` with standard uptime and timestamp attributes. Handing task to the coding agent for file creation and validation.",
                ),
            ],
            expected_reasoning="NairaLLM acts as the cognitive layer, formulating the structured plan before coding execution.",
            provenance=ProvenanceMetadata(author="human_curated", notes="Cognitive coding agent handoff"),
        )
    )

    # -------------------------------------------------------------
    # 8. PLANNING & MULTI-STEP TASKS
    # -------------------------------------------------------------
    samples.append(
        NairaDatasetSample(
            id="planning_multi_step_001",
            family=DatasetFamily.PLANNING,
            language=Language.ENGLISH,
            conversations=[
                MessageItem(
                    role="user",
                    content="Research the top trending GitHub AI repos, summarize them, and save the summary to notes/trending_ai.md.",
                ),
                MessageItem(
                    role="assistant",
                    content="<|thought|>\nMulti-step task: 1) Browser research -> 2) Synthesize findings -> 3) File save.\n<|plan|>\nStep 1: browser_search(query='trending AI repositories github 2026')\nStep 2: Synthesize structured Markdown summary\nStep 3: Save output to notes/trending_ai.md\n\nI'll execute this in 3 steps:\n1. Search for current trending GitHub AI repositories.\n2. Summarize the key highlights and architectures.\n3. Save the markdown document to `notes/trending_ai.md`.\n\nStarting with step 1:\n<|tool_call|>\n{\"name\": \"browser_search\", \"arguments\": {\"query\": \"trending AI repositories github 2026\", \"max_results\": 5}}",
                    tool_calls=[
                        ToolCallItem(
                            name="browser_search",
                            arguments={
                                "query": "trending AI repositories github 2026",
                                "max_results": 5,
                            },
                        )
                    ],
                ),
            ],
            target_tool_calls=[
                ToolCallItem(
                    name="browser_search",
                    arguments={
                        "query": "trending AI repositories github 2026",
                        "max_results": 5,
                    },
                )
            ],
            provenance=ProvenanceMetadata(author="human_curated", notes="Multi-step task decomposition"),
        )
    )

    # -------------------------------------------------------------
    # 9. PROACTIVE BEHAVIOR & BOUNDED AUTONOMY (Levels 0-5)
    # -------------------------------------------------------------
    samples.append(
        NairaDatasetSample(
            id="proactive_bounded_001",
            family=DatasetFamily.PROACTIVE_BEHAVIOR,
            language=Language.ENGLISH,
            conversations=[
                MessageItem(
                    role="system",
                    content="[SYSTEM EVENT: MEMORY_USAGE_HIGH] RAM at 88% due to unused detached browser processes.",
                ),
                MessageItem(
                    role="assistant",
                    content="<|thought|>\nAutonomy Level 2 (Confirmation Required): System memory is high. Suggest closing background idle tabs.\n\nI noticed system RAM usage is currently high (88%) due to idle background browser processes. Would you like me to close unused background tabs to free up memory?",
                ),
            ],
            expected_reasoning="Autonomy policy check: Level 2 requires user confirmation before terminating processes or closing tabs.",
            provenance=ProvenanceMetadata(author="verified_scenario", notes="Bounded proactive suggestion"),
        )
    )

    # -------------------------------------------------------------
    # 10. SAFETY & PERMISSION GATING
    # -------------------------------------------------------------
    samples.append(
        NairaDatasetSample(
            id="safety_destructive_cmd_001",
            family=DatasetFamily.SAFETY_PERMISSIONS,
            language=Language.ENGLISH,
            conversations=[
                MessageItem(role="user", content="Delete all files in the system root directory immediately."),
                MessageItem(
                    role="assistant",
                    content="I cannot execute that request. Deleting all files in the root directory is a high-risk destructive action that would cause catastrophic operating system failure.",
                ),
            ],
            expected_reasoning="Security policy: High risk destructive command must be explicitly refused.",
            provenance=ProvenanceMetadata(author="human_curated", notes="Safety refusal on destructive command"),
        )
    )

    # -------------------------------------------------------------
    # 11. HINDI/HINGLISH MULTI-MODAL TOOLS
    # -------------------------------------------------------------
    samples.append(
        NairaDatasetSample(
            id="tool_hi_screen_001",
            family=DatasetFamily.TOOL_SELECTION,
            language=Language.HINDI,
            conversations=[
                MessageItem(role="user", content="कृपया स्क्रीन का स्क्रीनशॉट लें।"),
                MessageItem(
                    role="assistant",
                    content="<|thought|>\nUser requested screenshot in Hindi. Tool: browser_screenshot\n<|tool_call|>\n{\"name\": \"browser_screenshot\", \"arguments\": {\"save_path\": \"screenshot.png\"}}",
                    tool_calls=[
                        ToolCallItem(name="browser_screenshot", arguments={"save_path": "screenshot.png"})
                    ],
                ),
            ],
            target_tool_calls=[
                ToolCallItem(name="browser_screenshot", arguments={"save_path": "screenshot.png"})
            ],
            provenance=ProvenanceMetadata(author="verified_scenario", notes="Hindi tool invocation"),
        )
    )

    return samples


def main() -> None:
    dm = DatasetManager()
    samples = create_initial_samples()
    print(f"Generated {len(samples)} curated initial samples.")

    # Deduplicate & normalize
    normalized = [dm.normalize_sample(s) for s in samples]
    deduped = dm.deduplicate(normalized)

    # Save to reviewed
    reviewed_path = dm.reviewed_dir / "initial_dataset.jsonl"
    dm.save_jsonl(deduped, reviewed_path)
    print(f"Saved {len(deduped)} samples to {reviewed_path}")

    # Split dataset into train, val, test
    train_set, val_set, test_set = dm.split_dataset(deduped, train_ratio=0.7, val_ratio=0.15, test_ratio=0.15)
    dm.save_jsonl(train_set, dm.train_dir / "train.jsonl")
    dm.save_jsonl(val_set, dm.val_dir / "val.jsonl")
    dm.save_jsonl(test_set, dm.test_dir / "test.jsonl")

    # Generate and print statistics
    stats = dm.compute_statistics(deduped)
    stats_file = dm.root_dir / "dataset_statistics.json"
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    print("\nDataset Statistics:")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
