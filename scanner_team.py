import os
from openai import OpenAI

# OmniRoute Local Connection
client = OpenAI(
    base_url="http://localhost:20128/v1",
    api_key="sk-788ed03069a20a0e-01ac6a-35978b3"  # OmniRoute key agar set ho toh yahan daalein
)

# Model configuration (Aap OmniRoute mein jo model chahein wo use kar sakte hain)
MODEL_NAME = "aug/sonnet4.6" # ya deepseek / kimi model jo OmniRoute mein set ho

def get_project_files(root_dir):
    file_contents = {}
    for dirpath, _, filenames in os.walk(root_dir):
        if "__pycache__" in dirpath or ".git" in dirpath:
            continue
        for file in filenames:
            if file.endswith((".py", ".json", ".env", ".md", ".txt")):
                full_path = os.path.join(dirpath, file)
                rel_path = os.path.relpath(full_path, root_dir)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        file_contents[rel_path] = f.read()
                except Exception as e:
                    print(f"Could not read {rel_path}: {e}")
    return file_contents

project_path = r"C:\Users\user\Desktop\Project-AIF-main"
print("📂 Scanning project files...")
files_data = get_project_files(project_path)
code_base_summary = "\n\n".join([f"--- FILE: {path} ---\n{content[:2000]}" for path, content in files_data.items()])

# 10 Agents System Prompts
agents = [
    ("Agent 1: Architecture Analyzer", "Analyze the overall directory structure and project layout."),
    ("Agent 2: Core Logic Inspector", "Inspect the main python scripts and core execution flow."),
    ("Agent 3: Dependency Auditor", "Evaluate external libraries (yarl, pytest, etc.) and environment setup."),
    ("Agent 4: Testing Specialist", "Review testing frameworks, pytest setup, and assertions."),
    ("Agent 5: Audio Subsystem Expert", "Analyze sounddevice and soundfile data handling modules."),
    ("Agent 6: Security Auditor", "Scan for potential security vulnerabilities, hardcoded secrets, or unsafe practices."),
    ("Agent 7: Performance Reviewer", "Identify potential performance bottlenecks or memory issues."),
    ("Agent 8: Code Quality Advisor", "Suggest refactoring, readability improvements, and clean code standards."),
    ("Agent 9: Integration Mapper", "Map out how different modules and components communicate with each other."),
    ("Agent 10: Kimi K3 Master Explainer", "Synthesize reports from all previous agents and explain the entire project code comprehensively and simply to the user.")
]

agent_reports = {}

print("🤖 Running 10 Code Scan Agents via OmniRoute...")

for name, role in agents[:-1]: # Agents 1 to 9
    print(f"-> Running {name}...")
    prompt = f"You are an expert AI code scanner agent. Your role: {role}\n\nHere is the project code:\n{code_base_summary[:10000]}"
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}]
        )
        agent_reports[name] = response.choices[0].message.content
    except Exception as e:
        agent_reports[name] = f"Error: {e}"

# Agent 10: Kimi K3 Master Aggregator
print("-> Running Agent 10 (Kimi K3 Master Explainer)...")
combined_reports = "\n\n".join([f"### {name}\n{report}" for name, report in agent_reports.items()])
final_prompt = f"""
You are Kimi K3, the master explainer agent. 
You have received reports from 9 specialized code scanning agents regarding the project 'Project-AIF-main'.
Your task is to thoroughly explain the entire project, its architecture, core features, and how it works, in a clear, structured, and easy-to-understand manner for the developer.

Here are the agents' reports:
{combined_reports}
"""

try:
    final_response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": final_prompt}]
    )
    final_output = final_response.choices[0].message.content
    
    # Save report to a markdown file
    report_file = os.path.join(project_path, "project_scan_report.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(final_output)
    print(f"\n✨ Scan Complete! Master report saved successfully at:\n{report_file}")

except Exception as e:
    print(f"Error in final synthesis: {e}")