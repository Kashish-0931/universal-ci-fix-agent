import os
import json
import re
from pathlib import Path
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])

# ------------------ Helpers ------------------
def extract_traceback_file(error_log: str) -> str | None:
    """Extract the Python file from a traceback."""
    match = re.search(r'File "([^"]+\.py)"', error_log)
    if match:
        return match.group(1)
    return None


def extract_missing_module(error_log: str) -> str | None:
    """Extract missing module name from ImportError or ModuleNotFoundError."""
    match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_log)
    if match:
        return match.group(1)
    return None


# ------------------ Main LLM Call ------------------
def ask_llm(error_log: str, system_prompt: str = None, expect_json: bool = True):
    """
    Query LLM to analyze CI/CD errors and return safe code-based suggestions.

    Returns:
        filename: str
        code: str
        commands: list (always empty for safety)
        confidence: float
        suggested_fix: str
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

    # Call LLM
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

        # Extract filename and code
        if not isinstance(data["files_to_change"], dict) or len(data["files_to_change"]) != 1:
            raise ValueError("files_to_change must reference exactly one file")
        filename, code = next(iter(data["files_to_change"].items()))

        # Replace unknown/hallucinated filenames with traceback info
        if filename in ("unknown_file.py", "file.py", "unknown.py") or not filename.strip():
            traceback_file = extract_traceback_file(error_log)
            filename = traceback_file or "<unchanged>"
            code = "<unchanged>"

        # Ignore any shell commands completely
        commands = []

        # Dependency fallback for missing modules
        if data["error_type"] in ("ModuleNotFoundError", "ImportError"):
            missing_module = extract_missing_module(error_log)
            traceback_file = extract_traceback_file(error_log)
            if missing_module:
                # Provide pip install suggestion in explanation, not as shell command
                data["fix_explanation"] = f"Install missing module: {missing_module}"
            if traceback_file:
                filename = traceback_file
                code = "<unchanged>"

        # ------------------ Suggested fix ------------------
        # Provide code-based suggestion
        if code == "<unchanged>" or not code.strip():
            match = re.search(r'File "[^"]+", line \d+\n\s*(.+)', error_log)
            code_line = match.group(1).strip() if match else "Check the code near reported line"
            suggested_fix = code_line
        else:
            suggested_fix = code

        # Confidence fallback
        confidence = data.get("confidence", 0.5)

        return filename, code, commands, confidence, suggested_fix

    else:
        # Plain text mode (for CD)
        return raw

