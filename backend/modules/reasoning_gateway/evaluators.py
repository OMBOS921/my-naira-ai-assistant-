"""
Evaluators for the Reasoning Gateway.

Pure, deterministic evaluation functions for the 10 routing criteria:
1. Intent category
2. Complexity score (0-100)
3. Ambiguity level (0.0-1.0)
4. Memory availability
5. Local capability availability
6. Live web search sufficiency
7. Planning requirement
8. Creativity requirement
9. Tool requirement
10. User clarification requirement
"""

from __future__ import annotations

import re
from typing import Any

from backend.modules.reasoning_gateway.gateway_types import (
    IntentCategory,
    ReasoningGatewayDecision,
)

# Pattern definitions for fast deterministic regex matching
_GREETING_PATTERNS = re.compile(
    r"^(?:hi|hello|hey|good morning|good afternoon|good evening|thanks|thank you|bye|goodbye|hey naira|hi naira)\b[!.]?$",
    re.IGNORECASE,
)

_MEMORY_PATTERNS = re.compile(
    r"\b(?:what is my|do you remember|my name|my favorite|my email|my phone|where do i|who am i|what did i say|remember that)\b",
    re.IGNORECASE,
)

_WEB_SEARCH_PATTERNS = re.compile(
    r"\b(?:weather in|latest price|stock price|sports score|today's news|current price|who won the|what is the time in|score of|live score)\b",
    re.IGNORECASE,
)

_LOCAL_CAPABILITY_PATTERNS = re.compile(
    r"^(?:what time is it|what is the date|system status|battery status|current date|uptime)\b[?.]?$",
    re.IGNORECASE,
)

_CLARIFICATION_PATTERNS = re.compile(
    r"^(?:do it|run that|run|open|send|delete|search|fix it|start|stop|execute|process)\b[!]?$",
    re.IGNORECASE,
)

_CODING_PATTERNS = re.compile(
    r"\b(?:"
    r"def |class |import |function|write code|fix bug|python script|git commit|pytest|refactor|"
    r"syntax error|type error|nameerror|valueerror|stack trace|traceback|async def|return |"
    r"script likho|run karo|chalao|banao script|code likho|script banao|script|code|python|"
    r"execute_local_python|local_python|execute_script|run script|write script|write a script|"
    r"create script|debug|error|read the error|read error|fix it|fix error|solve error|self-correct|run again"
    r")\b",
    re.IGNORECASE,
)

_PLANNING_PATTERNS = re.compile(
    r"\b(?:build an app|create a project|multi-step|roadmap|step 1|first do|workflow|architect|project plan|and then|uske baad|phir|self-correct|run again)\b",
    re.IGNORECASE,
)

_CREATIVE_PATTERNS = re.compile(
    r"\b(?:write a poem|tell a story|creative writing|brainstorm names|generate tagline|poem about|story about|song lyrics|write an essay)\b",
    re.IGNORECASE,
)

_COMPLEX_ANALYSIS_PATTERNS = re.compile(
    r"\b(?:compare and contrast|analyze the|trade-offs|pros and cons|explain the difference|deep dive|performance comparison|evaluating)\b",
    re.IGNORECASE,
)

_BROWSER_PATTERNS = re.compile(
    r"\b(?:navigate to|click on|fill field|fill input|browser scroll|extract text from page|open website|type into|browser_)\b",
    re.IGNORECASE,
)


def evaluate_request(
    request_text: str,
    context: dict[str, Any] | None = None,
    memory_manager: object | None = None,
    tool_manager: object | None = None,
) -> ReasoningGatewayDecision:
    """Evaluate an inbound request against all 10 criteria and return a structured decision.

    Execution time is strictly sub-millisecond (< 1ms).
    """
    text = request_text.strip()
    if not text:
        return ReasoningGatewayDecision(
            category=IntentCategory.GREETING,
            complexity_score=0,
            llm_required=False,
            memory_lookup=False,
            web_search_only=False,
            planning_required=False,
            clarification_required=False,
            confidence=1.0,
            reasoning="Empty request handled without LLM.",
            ambiguity_level=0.0,
        )

    # 1. Ambiguity & Clarification evaluation
    is_ambiguous_short = bool(_CLARIFICATION_PATTERNS.match(text))
    ambiguity_level = 0.9 if is_ambiguous_short else (0.4 if len(text.split()) < 3 and not _GREETING_PATTERNS.match(text) and not _LOCAL_CAPABILITY_PATTERNS.match(text) else 0.1)
    clarification_required = is_ambiguous_short or (ambiguity_level > 0.7)

    # 2. Greeting check
    is_greeting = bool(_GREETING_PATTERNS.match(text))

    # 3. Local capability check
    is_local_cap = bool(_LOCAL_CAPABILITY_PATTERNS.match(text))

    # 4. Memory availability check
    is_memory_q = bool(_MEMORY_PATTERNS.search(text))
    has_memory_match = False
    if is_memory_q and memory_manager is not None:
        search_fn = getattr(memory_manager, "search", None) or getattr(memory_manager, "recall", None)
        if callable(search_fn):
            try:
                mem_res = search_fn(text)
                if mem_res:
                    has_memory_match = True
            except Exception:
                pass
    memory_available = is_memory_q or has_memory_match

    # 5. Live web search sufficiency check
    is_web_q = bool(_WEB_SEARCH_PATTERNS.search(text))

    # 6. Coding, Planning, Creative, Analysis, Browser checks
    is_coding = bool(_CODING_PATTERNS.search(text))
    is_planning = bool(_PLANNING_PATTERNS.search(text))
    is_creative = bool(_CREATIVE_PATTERNS.search(text))
    is_analysis = bool(_COMPLEX_ANALYSIS_PATTERNS.search(text))
    is_browser = bool(_BROWSER_PATTERNS.search(text))

    # 7. Tool requirement
    tool_required = is_coding or is_planning or is_browser or (tool_manager is not None and bool(getattr(tool_manager, "has_tool_for", lambda _: False)(text)))

    # 8. Complexity score calculation (0 to 100)
    words = text.split()
    length_factor = min(len(words) * 3, 40)
    logic_words = re.findall(r"\b(?:if|then|else|because|unless|where|and|or|not|step)\b", text, re.IGNORECASE)
    logic_factor = min(len(logic_words) * 10, 30)
    domain_factor = 30 if (is_coding or is_planning or is_analysis or is_browser) else (15 if is_creative else 0)
    complexity_score = min(length_factor + logic_factor + domain_factor, 100)

    # Category determination
    if is_greeting:
        category = IntentCategory.GREETING
    elif is_local_cap:
        category = IntentCategory.LOCAL_CAPABILITY
    elif clarification_required:
        category = IntentCategory.CLARIFICATION
    elif is_memory_q:
        category = IntentCategory.MEMORY_RECALL
    elif is_browser:
        category = IntentCategory.BROWSER
    elif is_web_q:
        category = IntentCategory.WEB_SEARCH
    elif is_coding:
        category = IntentCategory.CODING
    elif is_planning:
        category = IntentCategory.PLANNING
    elif is_creative:
        category = IntentCategory.CREATIVE_WRITING
    elif is_analysis:
        category = IntentCategory.COMPLEX_ANALYSIS
    else:
        category = IntentCategory.REASONING


    # Routing Decision rules:
    # - If memory alone can answer -> skip LLM
    # - If web search plus deterministic summarisation is enough -> avoid LLM
    # - If clarification required -> avoid LLM (ask clarification)
    # - If greeting / local capability -> skip LLM
    # - Only invoke LLM for genuine reasoning, planning, coding, creative writing, complex analysis, or unresolved ambiguity.

    memory_lookup = (category == IntentCategory.MEMORY_RECALL) and memory_available
    web_search_only = (category == IntentCategory.WEB_SEARCH)

    if category in (IntentCategory.GREETING, IntentCategory.LOCAL_CAPABILITY):
        llm_required = False
        confidence = 0.98
        reason = f"Deterministic bypass for {category.value}"
    elif clarification_required:
        llm_required = False
        confidence = 0.95
        reason = "Ambiguous request requires user clarification before LLM execution"
    elif memory_lookup:
        llm_required = False
        confidence = 0.92
        reason = "Request satisfied directly from Memory lookup without LLM"
    elif web_search_only:
        llm_required = False
        confidence = 0.90
        reason = "Request satisfied via direct web search and deterministic formatting"
    else:
        llm_required = True
        confidence = 0.95
        reason = f"Request requires LLM reasoning for category {category.value} (complexity score: {complexity_score})"

    return ReasoningGatewayDecision(
        category=category,
        complexity_score=complexity_score,
        llm_required=llm_required,
        memory_lookup=memory_lookup,
        web_search_only=web_search_only,
        planning_required=is_planning,
        clarification_required=clarification_required,
        confidence=confidence,
        reasoning=reason,
        ambiguity_level=ambiguity_level,
        memory_available=memory_available,
        local_capability_available=is_local_cap,
        web_search_sufficient=is_web_q,
        creativity_required=is_creative,
        tool_required=tool_required,
    )
