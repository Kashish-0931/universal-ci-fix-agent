import os
import json
from pathlib import Path
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])

SYSTEM_PROMPT = """
You are an autonomous CI/CD Fixing Agent.

You operate inside automated pipelines where human intervention is minimal.

Your task:
Analyze CI/CD error logs and produce deterministic, actionable fixes.

STRICT RULES:
- NEVER give vague advice
- NEVER say "it depends"
- NEVER suggest manual debugging
- NEVER mention yourself, the model, or reasoning steps
- NEVER output markdown
- NEVER output explanations outside JSON
- NEVER hallucinate files that do not logically exist

YOU MUST:
1. Identify the exact root cause of the failure
2. Classify the error type (dependency, syntax, config, test, build, permission, env)
3. Propose the minimal fix required to unblock the pipeline
4. Specify exactly which file(s) must be modified
5. Provide exact content to add or replace
6. Provide the exact shell command required to apply or verify the fix (may be empty)
7. Assign a confidence score based on certainty

FILE RULES:
- If dependency is missing → use requirements.txt
- If requirements.txt does not exist → create it
- Never modify unrelated files
- Prefer minimal changes

OUTPUT FORMAT:
Respond with VALID JSON ONLY.
No comments. No markdown. No extra keys.

JSON SCHEMA:
{
  "error_type": "string",
  "error_detected": "string",
  "root_cause": "string",
  "fix_explanation": "string",
  "files_to_change": {
    "filename": "exact content to add or replace"
  },
  "command": ["string"],
  "confidence": number
}
"""

def ask_llm(error_log: str):
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"ERROR LOG:\n{error_log}"}
        ]
    )

    raw = response.choices[0].message.content.strip()
    print("\nRAW LLM OUTPUT:\n", raw)

    data = json.loads(raw)

    required = [
        "error_type",
        "error_detected",
        "root_cause",
        "fix_explanation",
        "files_to_change",
        "command",
        "confidence"
    ]

    for k in required:
        if k not in data:
            raise ValueError(f"Missing key: {k}")

    if not isinstance(data["files_to_change"], dict):
        raise ValueError("files_to_change must be an object")

    if len(data["files_to_change"]) != 1:
        raise ValueError("Exactly one file change allowed")

    # 🔥 ONLY CHANGE: allow all commands, block only destructive ones
    DANGEROUS_COMMANDS = {
        "rm", "shutdown", "reboot", "mkfs",
        "dd", "kill", "killall", "poweroff"
    }

    command = data.get("command", [])

    if command and command[0] in DANGEROUS_COMMANDS:
        raise ValueError(f"Blocked dangerous command: {command[0]}")

    filename, code = next(iter(data["files_to_change"].items()))

    # Block hallucinated files (except requirements.txt)
   # Allow new or nested files, but block absolute paths
    path = Path(filename)

if path.is_absolute() or ".." in path.parts:
    raise ValueError(f"Invalid file path: {filename}")
