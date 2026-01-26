import os
import json
import re
from pathlib import Path
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])

SYSTEM_PROMPT = """
You are an autonomous CI/CD Fixing Agent operating inside automated pipelines.

TASK:
Analyze CI/CD error logs and produce a minimal, deterministic fix or a safe suggestion.

STRICT RULES:
- NEVER hallucinate files, modules, or imports
- NEVER invent filenames like unknown_file.py
- NEVER modify files not mentioned in the traceback
- Dependency errors MUST NOT create new files
- Always be conservative and safe

ERROR CLASSIFICATION:
- ModuleNotFoundError → missing dependency
- ImportError → missing dependency
- NameError → typo or missing definition
- SyntaxError → syntax issue
- AssertionError → test failure
- Other → unknown (give safe guidance)

DEPENDENCY RULES:
- If error is ModuleNotFoundError or ImportError:
  - Root cause is missing dependency
  - files_to_change MUST reference the exact file from traceback
  - Code content must be unchanged
  - command MUST include a pip install suggestion
  - NEVER invent filenames

FIX RULES:
- Modify ONLY the file mentioned in the traceback
- If no code change is required, return the file unchanged
- Always provide fix_explanation
- Always provide at least one safe suggestion

OUTPUT:
Return VALID JSON ONLY matching this schema:

{
  "error_type": "string",
  "error_detected": "string",
  "root_cause": "string",
  "fix_explanation": "string",
  "files_to_change": { "filename": "exact replacement content or <unchanged>" },
  "command": ["safe shell commands"],
  "confidence": number
}
"""

# ------------------ HELPERS ------------------

def extract_traceback_file(error_log: str) -> str | None:
    """
    Extract first file path from traceback.
    """
    match = re.search(r'File "([^"]+\.py)"', error_log)
    if match:
        return match.group(1)
    return None


def extract_missing_module(error_log: str) -> str | None:
    """
    Extract missing module name from ModuleNotFoundError.
    """
    match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_log)
    if match:
        return match.group(1)
    return None


# ------------------ MAIN LLM CALL ------------------

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

    # ------------------ VALIDATION ------------------

    REQUIRED_KEYS = {
        "error_type",
        "error_detected",
        "root_cause",
        "fix_explanation",
        "files_to_change",
        "command",
        "confidence"
    }

    missing = REQUIRED_KEYS - data.keys()
    if missing:
        raise ValueError(f"Missing required keys: {missing}")

    if not isinstance(data["files_to_change"], dict):
        raise ValueError("files_to_change must be an object")

    if len(data["files_to_change"]) != 1:
        raise ValueError("Exactly one file must be referenced")

    filename, code = next(iter(data["files_to_change"].items()))

    # 🚫 Block hallucinated filenames
    if filename in ("unknown_file.py", "unknown.py", "file.py"):
        raise ValueError("Hallucinated filename detected")

    path = Path(filename)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Invalid file path: {filename}")

    # ------------------ COMMAND SAFETY ------------------

    DANGEROUS_COMMANDS = {
        "rm", "shutdown", "reboot", "mkfs",
        "dd", "kill", "killall", "poweroff"
    }

    commands = data.get("command", [])
    for cmd in commands:
        if cmd.split()[0] in DANGEROUS_COMMANDS:
            raise ValueError(f"Blocked dangerous command: {cmd}")

    # ------------------ FALLBACK CORRECTIONS ------------------

    error_type = data["error_type"]

    # Dependency error fallback
    if error_type in ("ModuleNotFoundError", "ImportError"):
        missing_module = extract_missing_module(error_log)
        traceback_file = extract_traceback_file(error_log)

        if missing_module and not commands:
            commands = [f"pip install {missing_module}"]

        if traceback_file:
            filename = traceback_file
            code = "<unchanged>"

    # Always ensure suggestion exists
    if commands:
        suggested_fix = " && ".join(commands)
    else:
        suggested_fix = data["fix_explanation"]

    return (
        filename,
        code,
        commands,
        data["confidence"],
        suggested_fix
    )
