"""
Autonomous Task Engine prompts and formatters.
"""

from __future__ import annotations

from typing import Any

PLANNING_PROMPT_TEMPLATE = """You are an autonomous AI task execution agent.
Your primary goal is: {goal}

Current Step: {current_step} / {max_steps}

Execution History:
{steps_summary}

Determine the next step to achieve the goal.
Respond in JSON format with the following keys:
- "thought": Reasoning about current state and what to do next.
- "action": Tool name to execute, or "FINAL_ANSWER" if goal is fully achieved.
- "action_input": Key-value dictionary of arguments for the tool, or final summary text if action is "FINAL_ANSWER".

JSON response:
"""

FINAL_SUMMARY_PROMPT_TEMPLATE = """You are an autonomous AI task execution agent.
The user's goal was: {goal}

The task has completed after {total_steps} steps. Here is the step history:
{steps_summary}

Provide a clear, concise final summary of what was accomplished and the final result.
"""


def format_steps_summary(steps: list[Any]) -> str:
    """Format step history into a clean string for LLM prompts."""
    if not steps:
        return "No steps executed yet."

    formatted: list[str] = []
    for s in steps:
        step_num = getattr(s, "step_number", "?")
        thought = getattr(s, "thought", "")
        action = getattr(s, "action", "")
        result = getattr(s, "result", "")
        error = getattr(s, "error", None)

        status_str = f"Error: {error}" if error else f"Result: {result}"
        formatted.append(
            f"Step {step_num}:\n"
            f"  Thought: {thought}\n"
            f"  Action: {action}\n"
            f"  {status_str}"
        )

    return "\n".join(formatted)
