import os
import json
import re
from pathlib import Path
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])

# ------------------ Helpers ------------------
def extract_traceback_file(error_log: str) -> str | None:
    match = re.search(r'File "([^"]+\.py)"', error_log)
    if match:
        return match.group(1)
    return None

def extract_missing_module(error_log: str) -> str | None:
    match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_log)
    if match:
        return match.group(1)
    return None

# ------------------ Main LLM Call ------------------
def ask_llm(error_log: str, system_prompt: str = None, expect_json: bool = True):
    """
    If expect_json=True, parse LLM output as CI JSON.
    If expect_json=False, return plain text (for CD).
    """
    if system_prompt is None:
        system_prompt = """
You are an autonomous CI/CD fixing agent.

TASK:
Analyze any CI/CD error log and provide:
- Root cause in simple terms
- Safe minimal fix or suggestion
- Do not modify files not mentioned in traceback
- Never invent filenames or commands
- Do not produce dangerous shell commands (rm, shutdown, reboot, mkfs, dd, kill, poweroff)
- Only suggest `pip install <missing_module>` for ModuleNotFoundError / ImportError
- Output must match EXACTLY this JSON schema:
{
  "error_type": "string",
  "error_detected": "string",
  "root_cause": "string",
  "fix_explanation": "string",
  "files_to_change": {
    "filename": "exact replacement content or <unchanged>"
  },
  "command": ["safe shell commands"],
  "confidence": number
}
If you cannot safely fix the issue, return "<unchanged>" for files_to_change and an empty command array.
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        temperature=0,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"ERROR LOG:\n{error_log}"}
        ]
    )

    raw = response.choices[0].message.content.strip()
    print("\nRAW LLM OUTPUT:\n", raw)

    if expect_json:
        data = json.loads(raw)

        REQUIRED_KEYS = {
            "error_type", "error_detected", "root_cause", "fix_explanation",
            "files_to_change", "command", "confidence"
        }
        missing = REQUIRED_KEYS - data.keys()
        if missing:
            raise ValueError(f"Missing required keys: {missing}")

        # Extract file & code
        if not isinstance(data["files_to_change"], dict) or len(data["files_to_change"]) != 1:
            raise ValueError("files_to_change must reference exactly one file")
        filename, code = next(iter(data["files_to_change"].items()))

        # Block hallucinated filenames
        if filename in ("unknown_file.py", "file.py", "unknown.py") or not filename.strip():
            traceback_file = extract_traceback_file(error_log)
            filename = traceback_file or "<unchanged>"
            code = "<unchanged>"

        # ------------------ COMMAND SAFETY ------------------
        DANGEROUS_COMMANDS = {"rm", "shutdown", "reboot", "mkfs", "dd", "kill", "killall", "poweroff"}
        commands = data.get("command", [])
        safe_commands = [cmd for cmd in commands if cmd.split()[0] not in DANGEROUS_COMMANDS]
        commands = safe_commands

        # ------------------ Dependency fallback ------------------
        if data["error_type"] in ("ModuleNotFoundError", "ImportError"):
            missing_module = extract_missing_module(error_log)
            traceback_file = extract_traceback_file(error_log)
            if missing_module:
                commands = [f"pip install {missing_module}"]
            if traceback_file:
                filename = traceback_file
                code = "<unchanged>"

        # ------------------ Suggested fix ------------------
       # ------------------ Suggested fix ------------------
# Always provide a code-based suggestion; ignore shell commands
if code == "<unchanged>" or not code.strip():
    # Try to extract the faulty line from the traceback
    match = re.search(r'File "[^"]+", line \d+\n\s*(.+)', error_log)
    code_line = match.group(1).strip() if match else "Check the code near reported line"
    suggested_fix = code_line
else:
    suggested_fix = code

# Commands array is always empty for safety
commands = []

# Return safe output
return filename, code, commands, data.get("confidence", 0.5), suggested_fix
