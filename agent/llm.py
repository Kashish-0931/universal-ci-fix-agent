import os
import json
from pathlib import Path
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])
SYSTEM_PROMPT = """
You are an autonomous CI/CD Fixing Agent operating inside automated pipelines.

TASK:
Analyze CI/CD error logs and produce a minimal deterministic fix or a safe suggestion.

STRICT RULES:
- NEVER hallucinate files, modules, or imports
- NEVER invent new filenames
- Prefer pip install **only** for ModuleNotFoundError, but if needed suggest safe commands
- Do NOT add imports for NameError
- ALWAYS provide a "fix_explanation" even if no command is suggested
- ALWAYS include a safe suggested fix for the user to try, even if uncertain

CLASSIFICATION:
- NameError → syntax or typo
- ModuleNotFoundError → dependency
- ImportError → dependency
- SyntaxError → syntax

FIX RULES:
- If a function name is misspelled → rename function or call
- Modify ONLY the file mentioned in the traceback
- Provide at least one suggested fix, even if it’s generic guidance

OUTPUT:
- VALID JSON ONLY, matching this schema:

{
    "error_type": "string",
    "error_detected": "string",
    "root_cause": "string",
    "fix_explanation": "string",
    "files_to_change": { "filename": "exact replacement content" },
    "command": ["list of safe shell commands if needed"],
    "confidence": number
}

- Always include "fix_explanation" with a textual description
- Always include "files_to_change" with at least one file, even if content is unchanged
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

    # Allow all commands, block only destructive ones
    DANGEROUS_COMMANDS = {
        "rm", "shutdown", "reboot", "mkfs",
        "dd", "kill", "killall", "poweroff"
    }

    command = data.get("command", [])

    if command and command[0] in DANGEROUS_COMMANDS:
        raise ValueError(f"Blocked dangerous command: {command[0]}")

    filename, code = next(iter(data["files_to_change"].items()))

    # ✅ PATH CHECK MUST BE INSIDE FUNCTION
    path = Path(filename)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Invalid file path: {filename}")

    # --- NEW LINE: extract suggested fix from LLM output ---
    # We'll use fix_explanation if command is empty, else join commands
    if command:
        suggested_fix = " && ".join(command)
    else:
        suggested_fix = data.get("fix_explanation", "No suggestion available")

    return filename, code, command, data["confidence"], suggested_fix
