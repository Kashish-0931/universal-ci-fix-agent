import os
import json
from pathlib import Path
from groq import Groq

# ---------- CLIENT ----------
client = Groq(api_key=os.environ["GROQ_API_KEY"])

# ---------- SYSTEM PROMPT ----------
SYSTEM_PROMPT = """
You are an autonomous CI/CD Fixing Agent operating inside automated pipelines.

STRICT RULES (DO NOT VIOLATE):
- Output VALID JSON only (no markdown, no text)
- Follow the schema EXACTLY
- NEVER invent new files
- NEVER invent dependencies
- Modify ONLY the file mentioned in the traceback
- If unsure, keep file content unchanged and explain why
- Prefer NO FIX over a WRONG FIX

DEPENDENCY RULES:
- Suggest pip/npm install ONLY if error explicitly says dependency missing
- Do NOT suggest installs for path or import resolution issues

SCHEMA (DO NOT CHANGE):
{
    "error_type": "string",
    "error_detected": "string",
    "root_cause": "string",
    "fix_explanation": "string",
    "files_to_change": { "filename": "exact replacement content" },
    "command": ["safe shell commands only"],
    "confidence": number
}
"""

# ---------- ERROR CLASSIFICATION (INTERNAL ONLY) ----------
def classify_error(error_log: str) -> str:
    if "ModuleNotFoundError" in error_log:
        return "module_not_found"
    if "ImportError" in error_log:
        return "import_error"
    if "SyntaxError" in error_log:
        return "syntax_error"
    if "NameError" in error_log:
        return "name_error"
    if "TypeError" in error_log:
        return "type_error"
    if "ReferenceError" in error_log:
        return "js_reference_error"
    if "Cannot find module" in error_log:
        return "node_module_missing"
    return "unknown"

# ---------- LLM CALL ----------
def ask_llm(error_log: str):
    error_class = classify_error(error_log)

    context_hint = f"""
ERROR CLASSIFICATION: {error_class}

Guidance:
- If import/path related → suggest PYTHONPATH or relative import fix
- If dependency missing → suggest install command
- If unknown → do NOT modify code
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": context_hint},
            {"role": "user", "content": f"ERROR LOG:\n{error_log}"}
        ]
    )

    raw = response.choices[0].message.content.strip()
    print("\nRAW LLM OUTPUT:\n", raw)

    # ---------- STRICT JSON PARSE ----------
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError("LLM did not return valid JSON")

    # ---------- SCHEMA VALIDATION ----------
    required_keys = [
        "error_type",
        "error_detected",
        "root_cause",
        "fix_explanation",
        "files_to_change",
        "command",
        "confidence"
    ]

    for key in required_keys:
        if key not in data:
            raise ValueError(f"Missing key: {key}")

    if not isinstance(data["files_to_change"], dict):
        raise ValueError("files_to_change must be an object")

    if len(data["files_to_change"]) != 1:
        raise ValueError("Exactly one file must be modified")

    # ---------- FILE PATH SAFETY ----------
    filename, code = next(iter(data["files_to_change"].items()))
    path = Path(filename)

    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Invalid file path: {filename}")

    # ---------- COMMAND SAFETY ----------
    DANGEROUS = {
        "rm", "shutdown", "reboot", "mkfs",
        "dd", "kill", "killall", "poweroff"
    }

    commands = data.get("command", [])
    for cmd in commands:
        if cmd.split()[0] in DANGEROUS:
            raise ValueError(f"Blocked dangerous command: {cmd}")

    # ---------- SMART POST-FIX GUARDS ----------
    # Prevent wrong installs for import/path issues
    if error_class in {"module_not_found", "import_error"}:
        if commands and any("pip install" in c or "npm install" in c for c in commands):
            data["command"] = ["export PYTHONPATH=."]
            data["fix_explanation"] += " Dependency install removed; path issue suspected."
            data["confidence"] = min(data["confidence"], 0.6)

    # Unknown errors → safe fallback
    if error_class == "unknown":
        data["command"] = []
        data["confidence"] = min(data["confidence"], 0.4)

    # ---------- SUGGESTED FIX (USED BY OTHER FILES) ----------
    if data["command"]:
        suggested_fix = " && ".join(data["command"])
    else:
        suggested_fix = data["fix_explanation"]

    return filename, code, data["command"], data["confidence"], suggested_fix
